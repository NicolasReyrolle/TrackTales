"""Swimming workout interval computation.

Processes raw ``WorkoutEvent`` data (Lap and Segment events parsed from the
Apple Health export) into a structured list of :class:`SwimInterval` objects.

Each :class:`SwimInterval` groups consecutive pool laps that the Apple Watch
recorded as a single active segment (no pause between laps).  The pause
duration *after* an interval (until the swimmer pushes off for the next set)
is stored in :attr:`SwimInterval.pause_s`.

Usage::

    from logic.workout_manager.swimming import (
        build_swim_interval_display_rows,
        build_swim_intervals,
    )

    intervals = build_swim_intervals(row["swimming_events"], lap_length_m=50.0)
    display_rows = build_swim_interval_display_rows(intervals)
    for display_row in display_rows:
        print(display_row["num"], display_row["dist"], display_row["dur"])
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any


@dataclass
class SwimLap:
    """A single pool lap within an interval.

    Attributes:
        lap_number:   1-based sequential number across all laps in the session.
        distance_m:   Lap length in metres (pool length, e.g. 25 or 50).
        duration_s:   Lap duration in seconds.
        stroke_style: Human-readable stroke name (e.g. ``"Breaststroke"``).
        swolf:        SWOLF score for the lap; ``None`` when absent.
    """

    lap_number: int
    distance_m: float
    duration_s: float
    stroke_style: str
    swolf: float | None


@dataclass
class SwimInterval:
    """A group of consecutive laps with no meaningful pause between them.

    Attributes:
        laps:    Ordered list of laps in this interval (chronological).
        pause_s: Rest duration in seconds *after* this interval before the
                 next one begins.  ``None`` for the final interval.
    """

    laps: list[SwimLap] = field(default_factory=list)
    pause_s: float | None = None


# Stroke style code → human-readable label (mirrors SWIMMING_STROKE_STYLES in schema).
_STROKE_LABELS: dict[int, str] = {
    0: "Unknown",
    1: "Mixed",
    2: "Freestyle",
    3: "Backstroke",
    4: "Breaststroke",
    5: "Butterfly",
    6: "Kickboard",
}

#: Sentinel label used when an interval contains two or more distinct stroke styles.
_MIXED_STROKE_LABEL: str = "Mixed"


def _parse_event_date(raw: Any) -> datetime | None:
    """Parse a datetime stored in a swimming event dict.

    Accepts ``datetime`` objects (already parsed) and ISO-style strings such as
    ``"2025-09-13 15:39:24 +0100"``.

    Args:
        raw: Raw value from the event dict ``"start_date"`` field.

    Returns:
        A timezone-aware :class:`datetime`, or ``None`` if parsing fails.
    """
    if isinstance(raw, datetime):
        return raw
    if not isinstance(raw, str):
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d %H:%M:%S %z")
    except ValueError:
        return None


def _to_utc(dt: datetime) -> datetime:
    """Normalise *dt* to UTC for arithmetic comparisons."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _parse_laps(
    lap_events: list[dict[str, Any]],
) -> list[tuple[datetime, dict[str, Any]]]:
    """Parse lap events into sorted ``(utc_datetime, event)`` pairs."""
    result: list[tuple[datetime, dict[str, Any]]] = []
    for evt in lap_events:
        dt = _parse_event_date(evt.get("start_date"))
        if dt is not None:
            result.append((_to_utc(dt), evt))
    result.sort(key=lambda x: x[0])
    return result


def _parse_segments(
    segment_events: list[dict[str, Any]],
) -> list[tuple[datetime, float]]:
    """Parse segment events into sorted ``(utc_datetime, duration_s)`` pairs."""
    result: list[tuple[datetime, float]] = []
    for evt in segment_events:
        dt = _parse_event_date(evt.get("start_date"))
        dur = float(evt.get("duration_s") or 0.0)
        if dt is not None and dur > 0:
            result.append((_to_utc(dt), dur))
    result.sort(key=lambda x: x[0])
    return result


def _assign_laps_to_segments(
    laps_parsed: list[tuple[datetime, dict[str, Any]]],
    segments_parsed: list[tuple[datetime, float]],
) -> list[tuple[datetime, float, list[tuple[datetime, dict[str, Any]]]]]:
    """Assign each lap to the first segment whose time window contains it.

    Returns a list of ``(seg_start, seg_dur, laps)`` tuples in segment order,
    followed by a trailing tuple for any orphan laps not covered by a segment.
    """
    assigned: set[int] = set()
    interval_data: list[tuple[datetime, float, list[tuple[datetime, dict[str, Any]]]]] = []

    for seg_start, seg_dur in segments_parsed:
        seg_end = seg_start + timedelta(seconds=seg_dur)
        # Allow 1-second tolerance at boundaries to absorb timestamp rounding.
        window_start = seg_start - timedelta(seconds=1)
        window_end = seg_end + timedelta(seconds=1)
        group: list[tuple[datetime, dict[str, Any]]] = []
        for i, (lap_dt, lap_evt) in enumerate(laps_parsed):
            if i not in assigned and window_start <= lap_dt <= window_end:
                group.append((lap_dt, lap_evt))
                assigned.add(i)
        if group:
            group.sort(key=lambda x: x[0])
            interval_data.append((seg_start, seg_dur, group))

    # Collect orphan laps not covered by any segment (defensive edge case).
    orphan_laps = [(dt, evt) for i, (dt, evt) in enumerate(laps_parsed) if i not in assigned]
    if orphan_laps:
        orphan_laps.sort(key=lambda x: x[0])
        orphan_dur = sum(float(e.get("duration_s") or 0) for _, e in orphan_laps)
        interval_data.append((orphan_laps[0][0], orphan_dur, orphan_laps))

    return interval_data


def _build_swim_lap(
    evt: dict[str, Any],
    lap_number: int,
    lap_length_m: float,
) -> SwimLap:
    """Build a :class:`SwimLap` from a raw lap event dict."""
    raw_stroke = evt.get("stroke_style")
    stroke_label = (
        _STROKE_LABELS.get(int(raw_stroke), "Unknown") if raw_stroke is not None else "Unknown"
    )
    swolf_raw = evt.get("swolf")
    return SwimLap(
        lap_number=lap_number,
        distance_m=lap_length_m,
        duration_s=float(evt.get("duration_s") or 0.0),
        stroke_style=stroke_label,
        swolf=float(swolf_raw) if swolf_raw is not None else None,
    )


def build_swim_intervals(
    swimming_events: list[dict[str, Any]] | None,
    lap_length_m: float,
) -> list[SwimInterval]:
    """Build a structured interval list from raw swimming event data.

    The algorithm:

    1. Separate events into *segment* events and *lap* events.
    2. Sort segments by start date.
    3. For each segment, collect laps whose start date falls within the
       segment's time window (``[segment_start, segment_start + duration]``).
       Laps are assigned to the first segment whose window contains them.
    4. Any laps not captured by a segment are appended as a single final
       interval (defensive edge case).
    5. Compute the pause after each interval (except the last) as the time
       between the current segment's end and the next segment's start.

    Args:
        swimming_events: Raw event list as produced by the export parser.
            Each dict has keys ``"type"`` (``"Lap"`` or ``"Segment"``),
            ``"start_date"``, ``"duration_s"``, and optionally
            ``"stroke_style"`` (int) and ``"swolf"`` (float).
        lap_length_m:    Length of one pool lap in metres (e.g. ``50.0``).

    Returns:
        Ordered list of :class:`SwimInterval` objects.  An empty list is
        returned when *swimming_events* is ``None`` or empty.
    """
    if not swimming_events:
        return []

    lap_events = [e for e in swimming_events if e.get("type") == "Lap"]
    segment_events = [e for e in swimming_events if e.get("type") == "Segment"]

    if not lap_events:
        return []

    laps_parsed = _parse_laps(lap_events)
    segments_parsed = _parse_segments(segment_events)
    interval_data = _assign_laps_to_segments(laps_parsed, segments_parsed)

    intervals: list[SwimInterval] = []
    lap_number = 1
    for idx, (seg_start, seg_dur, group_laps) in enumerate(interval_data):
        laps_out = [
            _build_swim_lap(evt, lap_number + i, lap_length_m)
            for i, (_, evt) in enumerate(group_laps)
        ]
        lap_number += len(laps_out)

        pause_s: float | None = None
        if idx < len(interval_data) - 1:
            next_seg_start = interval_data[idx + 1][0]
            current_seg_end = seg_start + timedelta(seconds=seg_dur)
            pause_s = max(0.0, (next_seg_start - current_seg_end).total_seconds())

        intervals.append(SwimInterval(laps=laps_out, pause_s=pause_s))

    return intervals


def _merge_interval_stroke(laps: list[SwimLap]) -> str:
    """Return a single stroke label for *laps*, or ``"Mixed"`` if multiple are used."""
    strokes = {lap.stroke_style for lap in laps if lap.stroke_style != "Unknown"}
    if len(strokes) > 1:
        return _MIXED_STROKE_LABEL
    return next(iter(strokes)) if strokes else "Unknown"


def _average_swolf(laps: list[SwimLap]) -> float | None:
    """Return the average SWOLF across *laps* that have a score, or ``None``."""
    values = [lap.swolf for lap in laps if lap.swolf is not None]
    return sum(values) / len(values) if values else None


def build_swim_interval_display_rows(
    intervals: list[SwimInterval],
) -> list[dict[str, Any]]:
    """Build one display-ready dict per interval by merging all laps in each interval.

    The merged row contains:

    * ``"num"`` – 1-based interval (set) number.
    * ``"dist"`` – total distance formatted as ``"100 m"``.
    * ``"dur"`` – total duration formatted as ``"2:23"``.
    * ``"stroke"`` – stroke style, or ``"Mixed"`` when laps use different strokes.
    * ``"swolf"`` – average SWOLF across laps that have a score, or ``"–"``.
    * ``"pause"`` – rest duration after this interval formatted as ``"1:30"``, or
      ``""`` when this is the last interval or the pause is zero.

    Args:
        intervals: Ordered list of :class:`SwimInterval` objects as returned by
            :func:`build_swim_intervals`.

    Returns:
        List of row dicts ready for direct assignment to a ``ui.table``.
        Returns an empty list when *intervals* is empty.
    """
    rows: list[dict[str, Any]] = []
    for num, interval in enumerate(intervals, 1):
        if not interval.laps:
            continue
        total_dist = sum(lap.distance_m for lap in interval.laps)
        total_dur = sum(lap.duration_s for lap in interval.laps)
        stroke = _merge_interval_stroke(interval.laps)
        avg_swolf = _average_swolf(interval.laps)
        pause_str = (
            format_swim_duration(interval.pause_s)
            if interval.pause_s is not None and interval.pause_s > 0
            else ""
        )
        rows.append(
            {
                "num": num,
                "dist": f"{int(total_dist)} m" if total_dist > 0 else "–",
                "dur": format_swim_duration(total_dur),
                "stroke": stroke,
                "swolf": f"{avg_swolf:.1f}" if avg_swolf is not None else "–",
                "pause": pause_str,
            }
        )
    return rows


def format_swim_duration(seconds: float) -> str:
    """Format a duration in seconds as ``m:ss`` (e.g. ``"1:23"``).

    Args:
        seconds: Duration in seconds.

    Returns:
        Formatted string such as ``"1:23"`` or ``"0:45"``.
    """
    total = int(round(seconds))
    minutes, secs = divmod(total, 60)
    return f"{minutes}:{secs:02d}"
