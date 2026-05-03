"""Swimming workout interval computation.

Processes raw ``WorkoutEvent`` data (Lap and Segment events parsed from the
Apple Health export) into a structured list of :class:`SwimInterval` objects.

Each :class:`SwimInterval` groups consecutive pool laps that the Apple Watch
recorded as a single active segment (no pause between laps).  The pause
duration *after* an interval (until the swimmer pushes off for the next set)
is stored in :attr:`SwimInterval.pause_s`.

Usage::

    from logic.workout_manager.swimming import build_swim_intervals

    intervals = build_swim_intervals(row["swimming_events"], lap_length_m=50.0)
    for interval in intervals:
        for lap in interval.laps:
            print(lap.lap_number, lap.duration_s, lap.stroke_style)
        if interval.pause_s is not None:
            print("Rest:", interval.pause_s, "s")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any


@dataclass
class SwimLap:
    """A single pool lap within an interval.

    Attributes:
        lap_number:  1-based sequential number across all laps in the session.
        distance_m:  Lap length in metres (pool length, e.g. 25 or 50).
        duration_s:  Lap duration in seconds.
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

#: Minimum gap in seconds between two laps to be considered a new segment when
#: no explicit segment events are available.
_GAP_THRESHOLD_S: float = 10.0


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

    lap_events: list[dict[str, Any]] = []
    segment_events: list[dict[str, Any]] = []
    for evt in swimming_events:
        if evt.get("type") == "Lap":
            lap_events.append(evt)
        elif evt.get("type") == "Segment":
            segment_events.append(evt)

    if not lap_events:
        return []

    # Parse and attach datetime objects so we can sort / compare.
    laps_parsed: list[tuple[datetime, dict[str, Any]]] = []
    for evt in lap_events:
        dt = _parse_event_date(evt.get("start_date"))
        if dt is not None:
            laps_parsed.append((_to_utc(dt), evt))
    laps_parsed.sort(key=lambda x: x[0])

    segments_parsed: list[tuple[datetime, float]] = []
    for evt in segment_events:
        dt = _parse_event_date(evt.get("start_date"))
        dur = float(evt.get("duration_s") or 0.0)
        if dt is not None and dur > 0:
            segments_parsed.append((_to_utc(dt), dur))
    segments_parsed.sort(key=lambda x: x[0])

    # --- Assign laps to segments ---
    assigned: set[int] = set()  # indices into laps_parsed

    interval_data: list[tuple[datetime, float, list[tuple[datetime, dict[str, Any]]]]] = []
    # interval_data entries: (seg_start_utc, seg_duration_s, laps_in_segment)

    for seg_start, seg_dur in segments_parsed:
        seg_end = seg_start + timedelta(seconds=seg_dur)
        group: list[tuple[datetime, dict[str, Any]]] = []
        for i, (lap_dt, lap_evt) in enumerate(laps_parsed):
            if i in assigned:
                continue
            # Allow a small tolerance (1 second) at the boundaries.
            if seg_start - timedelta(seconds=1) <= lap_dt <= seg_end + timedelta(seconds=1):
                group.append((lap_dt, lap_evt))
                assigned.add(i)
        if group:
            group.sort(key=lambda x: x[0])
            interval_data.append((seg_start, seg_dur, group))

    # Defensive: collect any laps not captured by a segment.
    orphan_laps = [(dt, evt) for i, (dt, evt) in enumerate(laps_parsed) if i not in assigned]
    if orphan_laps:
        orphan_laps.sort(key=lambda x: x[0])
        # Treat as one extra interval at the end.
        orphan_start = orphan_laps[0][0]
        orphan_dur = sum(float(e.get("duration_s") or 0) for _, e in orphan_laps)
        interval_data.append((orphan_start, orphan_dur, orphan_laps))

    # --- Build SwimInterval objects ---
    intervals: list[SwimInterval] = []
    lap_number = 1
    for idx, (seg_start, seg_dur, group_laps) in enumerate(interval_data):
        laps_out: list[SwimLap] = []
        for _lap_dt, evt in group_laps:
            raw_stroke = evt.get("stroke_style")
            stroke_label = (
                _STROKE_LABELS.get(int(raw_stroke), "Unknown")
                if raw_stroke is not None
                else "Unknown"
            )
            swolf_raw = evt.get("swolf")
            swolf = float(swolf_raw) if swolf_raw is not None else None
            laps_out.append(
                SwimLap(
                    lap_number=lap_number,
                    distance_m=lap_length_m,
                    duration_s=float(evt.get("duration_s") or 0.0),
                    stroke_style=stroke_label,
                    swolf=swolf,
                )
            )
            lap_number += 1

        # Compute pause to the next interval.
        pause_s: float | None = None
        if idx < len(interval_data) - 1:
            next_seg_start = interval_data[idx + 1][0]
            current_seg_end = seg_start + timedelta(seconds=seg_dur)
            gap = (next_seg_start - current_seg_end).total_seconds()
            pause_s = max(0.0, gap)

        intervals.append(SwimInterval(laps=laps_out, pause_s=pause_s))

    return intervals


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
