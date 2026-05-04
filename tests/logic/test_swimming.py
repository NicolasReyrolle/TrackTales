"""Tests for swimming interval computation and export parser integration."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from logic.export_parser import ExportParser
from logic.workout_manager.swimming import (
    SwimInterval,
    SwimLap,
    build_swim_interval_display_rows,
    build_swim_intervals,
    format_swim_duration,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_lap(
    start: str,
    duration_s: float,
    stroke_style: int = 4,
    swolf: float | None = None,
) -> dict:
    """Build a minimal lap event dict for tests."""
    event: dict = {"type": "Lap", "start_date": start, "duration_s": duration_s}
    event["stroke_style"] = stroke_style
    if swolf is not None:
        event["swolf"] = swolf
    return event


def _make_segment(start: str, duration_s: float) -> dict:
    """Build a minimal segment event dict for tests."""
    return {"type": "Segment", "start_date": start, "duration_s": duration_s}


# ---------------------------------------------------------------------------
# FormatSwimDuration
# ---------------------------------------------------------------------------


class TestFormatSwimDuration:
    """Unit tests for format_swim_duration."""

    def test_zero_seconds(self) -> None:
        assert format_swim_duration(0) == "0:00"

    def test_one_minute_exactly(self) -> None:
        assert format_swim_duration(60) == "1:00"

    def test_ninety_seconds(self) -> None:
        assert format_swim_duration(90) == "1:30"

    def test_fractional_rounds(self) -> None:
        # 65.7 seconds rounds to 66 → 1:06
        assert format_swim_duration(65.7) == "1:06"

    def test_large_value(self) -> None:
        # 125 seconds = 2:05
        assert format_swim_duration(125) == "2:05"


# ---------------------------------------------------------------------------
# BuildSwimIntervals – basic cases
# ---------------------------------------------------------------------------


class TestBuildSwimIntervalsEmpty:
    """Edge cases for build_swim_intervals with no/empty data."""

    def test_none_returns_empty(self) -> None:
        assert build_swim_intervals(None, 50.0) == []

    def test_empty_list_returns_empty(self) -> None:
        assert build_swim_intervals([], 50.0) == []

    def test_only_segment_events_no_laps_returns_empty(self) -> None:
        events = [_make_segment("2025-01-01 10:00:00 +0000", 120.0)]
        assert build_swim_intervals(events, 50.0) == []


class TestBuildSwimIntervalsGrouping:
    """Test that consecutive laps are correctly grouped into intervals."""

    def test_two_consecutive_laps_form_one_interval(self) -> None:
        events = [
            _make_segment("2025-01-01 10:00:00 +0000", 130.0),
            _make_lap("2025-01-01 10:00:00 +0000", 65.0, swolf=96.8),
            _make_lap("2025-01-01 10:01:05 +0000", 65.0, swolf=114.8),
        ]
        intervals = build_swim_intervals(events, 50.0)
        assert len(intervals) == 1
        assert len(intervals[0].laps) == 2

    def test_two_groups_separated_by_pause(self) -> None:
        events = [
            _make_segment("2025-01-01 10:00:00 +0000", 130.0),
            _make_lap("2025-01-01 10:00:00 +0000", 65.0),
            _make_lap("2025-01-01 10:01:05 +0000", 65.0),
            # Pause: 2 minutes gap
            _make_lap("2025-01-01 10:04:10 +0000", 65.0),
            _make_segment("2025-01-01 10:04:10 +0000", 65.0),
        ]
        intervals = build_swim_intervals(events, 50.0)
        assert len(intervals) == 2
        assert len(intervals[0].laps) == 2
        assert len(intervals[1].laps) == 1

    def test_pause_computed_between_intervals(self) -> None:
        events = [
            # Segment 1: 2 laps, 130 seconds total, starts at 10:00:00
            _make_segment("2025-01-01 10:00:00 +0000", 130.0),
            _make_lap("2025-01-01 10:00:00 +0000", 65.0),
            _make_lap("2025-01-01 10:01:05 +0000", 65.0),
            # Pause: Segment 1 ends at 10:02:10, Segment 2 starts at 10:05:00 → 170 sec pause
            _make_lap("2025-01-01 10:05:00 +0000", 65.0),
            _make_segment("2025-01-01 10:05:00 +0000", 65.0),
        ]
        intervals = build_swim_intervals(events, 50.0)
        assert intervals[0].pause_s is not None
        assert intervals[0].pause_s == pytest.approx(170.0, abs=1.0)
        assert intervals[1].pause_s is None  # last interval has no pause

    def test_last_interval_has_no_pause(self) -> None:
        events = [
            _make_segment("2025-01-01 10:00:00 +0000", 65.0),
            _make_lap("2025-01-01 10:00:00 +0000", 65.0),
        ]
        intervals = build_swim_intervals(events, 50.0)
        assert intervals[-1].pause_s is None


class TestBuildSwimIntervalsLapFields:
    """Test SwimLap field values populated by build_swim_intervals."""

    def test_lap_number_sequential(self) -> None:
        events = [
            _make_segment("2025-01-01 10:00:00 +0000", 130.0),
            _make_lap("2025-01-01 10:00:00 +0000", 65.0),
            _make_lap("2025-01-01 10:01:05 +0000", 65.0),
            _make_lap("2025-01-01 10:04:00 +0000", 65.0),
            _make_segment("2025-01-01 10:04:00 +0000", 65.0),
        ]
        intervals = build_swim_intervals(events, 50.0)
        nums = [lap.lap_number for interval in intervals for lap in interval.laps]
        assert nums == [1, 2, 3]

    def test_distance_uses_lap_length(self) -> None:
        events = [
            _make_segment("2025-01-01 10:00:00 +0000", 65.0),
            _make_lap("2025-01-01 10:00:00 +0000", 65.0),
        ]
        intervals = build_swim_intervals(events, 25.0)
        assert intervals[0].laps[0].distance_m == pytest.approx(25.0)

    def test_duration_stored_in_seconds(self) -> None:
        events = [
            _make_segment("2025-01-01 10:00:00 +0000", 78.5),
            _make_lap("2025-01-01 10:00:00 +0000", 78.5),
        ]
        intervals = build_swim_intervals(events, 50.0)
        assert intervals[0].laps[0].duration_s == pytest.approx(78.5)

    def test_stroke_style_translated_to_label(self) -> None:
        events = [
            _make_segment("2025-01-01 10:00:00 +0000", 65.0),
            _make_lap("2025-01-01 10:00:00 +0000", 65.0, stroke_style=4),
        ]
        intervals = build_swim_intervals(events, 50.0)
        assert intervals[0].laps[0].stroke_style == "Breaststroke"

    def test_stroke_style_freestyle(self) -> None:
        events = [
            _make_segment("2025-01-01 10:00:00 +0000", 65.0),
            _make_lap("2025-01-01 10:00:00 +0000", 65.0, stroke_style=2),
        ]
        intervals = build_swim_intervals(events, 50.0)
        assert intervals[0].laps[0].stroke_style == "Freestyle"

    def test_stroke_style_unknown_when_missing(self) -> None:
        # Lap with no stroke_style key
        event: dict = {"type": "Lap", "start_date": "2025-01-01 10:00:00 +0000", "duration_s": 65.0}
        events = [_make_segment("2025-01-01 10:00:00 +0000", 65.0), event]
        intervals = build_swim_intervals(events, 50.0)
        assert intervals[0].laps[0].stroke_style == "Unknown"

    def test_swolf_populated(self) -> None:
        events = [
            _make_segment("2025-01-01 10:00:00 +0000", 65.0),
            _make_lap("2025-01-01 10:00:00 +0000", 65.0, swolf=96.8),
        ]
        intervals = build_swim_intervals(events, 50.0)
        assert intervals[0].laps[0].swolf == pytest.approx(96.8)

    def test_swolf_none_when_missing(self) -> None:
        events = [
            _make_segment("2025-01-01 10:00:00 +0000", 65.0),
            _make_lap("2025-01-01 10:00:00 +0000", 65.0),
        ]
        intervals = build_swim_intervals(events, 50.0)
        assert intervals[0].laps[0].swolf is None


class TestBuildSwimIntervalsOrphans:
    """Test that laps not covered by any segment are collected into a tail interval."""

    def test_orphan_laps_appended_at_end(self) -> None:
        events = [
            _make_segment("2025-01-01 10:00:00 +0000", 65.0),
            _make_lap("2025-01-01 10:00:00 +0000", 65.0),
            # This lap falls outside the segment window
            _make_lap("2025-01-01 10:30:00 +0000", 65.0),
        ]
        intervals = build_swim_intervals(events, 50.0)
        assert len(intervals) == 2
        assert len(intervals[1].laps) == 1
        assert intervals[1].laps[0].lap_number == 2


# ---------------------------------------------------------------------------
# ExportParser integration – swimming fixture
# ---------------------------------------------------------------------------


class TestExportParserSwimmingEvents:
    """Test that ExportParser collects WorkoutEvent data from swimming workouts."""

    def test_swimming_events_parsed(
        self,
        create_health_zip: Callable[..., str],
        load_export_fragment: Callable[[str], str],
        build_health_export_xml: Callable[[list[str]], str],
    ) -> None:
        """swimming_events list should be populated from the fixture XML."""
        xml = build_health_export_xml([load_export_fragment("workout_swimming.xml")])
        zip_path = create_health_zip(xml_content=xml)

        with ExportParser() as parser:
            health_data = parser.parse(zip_path)

        assert len(health_data.workouts) == 1
        workout = health_data.workouts.iloc[0]
        assert workout["activityType"] == "Swimming"

        events = workout.get("swimming_events")
        assert isinstance(events, list)
        # 15 laps + 9 segments = 24 events
        assert len(events) == 24

    def test_swimming_events_contain_laps_and_segments(
        self,
        create_health_zip: Callable[..., str],
        load_export_fragment: Callable[[str], str],
        build_health_export_xml: Callable[[list[str]], str],
    ) -> None:
        """Both Lap and Segment event types should be captured."""
        xml = build_health_export_xml([load_export_fragment("workout_swimming.xml")])
        zip_path = create_health_zip(xml_content=xml)

        with ExportParser() as parser:
            health_data = parser.parse(zip_path)

        events = health_data.workouts.iloc[0]["swimming_events"]
        types = [e["type"] for e in events]
        assert "Lap" in types
        assert "Segment" in types

    def test_swimming_lap_has_stroke_style(
        self,
        create_health_zip: Callable[..., str],
        load_export_fragment: Callable[[str], str],
        build_health_export_xml: Callable[[list[str]], str],
    ) -> None:
        """Lap events should have stroke_style populated for laps that have it."""
        xml = build_health_export_xml([load_export_fragment("workout_swimming.xml")])
        zip_path = create_health_zip(xml_content=xml)

        with ExportParser() as parser:
            health_data = parser.parse(zip_path)

        events = health_data.workouts.iloc[0]["swimming_events"]
        lap_events = [e for e in events if e["type"] == "Lap"]
        # Most laps have stroke style 4 (Breaststroke); one has 0 (Unknown/kickboard)
        stroke_styles = [e.get("stroke_style") for e in lap_events if "stroke_style" in e]
        assert len(stroke_styles) > 0
        assert 4 in stroke_styles  # Breaststroke

    def test_swimming_events_have_swolf(
        self,
        create_health_zip: Callable[..., str],
        load_export_fragment: Callable[[str], str],
        build_health_export_xml: Callable[[list[str]], str],
    ) -> None:
        """Both Lap and Segment events should have SWOLF scores where present."""
        xml = build_health_export_xml([load_export_fragment("workout_swimming.xml")])
        zip_path = create_health_zip(xml_content=xml)

        with ExportParser() as parser:
            health_data = parser.parse(zip_path)

        events = health_data.workouts.iloc[0]["swimming_events"]
        lap_events = [e for e in events if e["type"] == "Lap"]
        swolf_values = [e["swolf"] for e in lap_events if "swolf" in e]
        # All laps except the last (which has no SWOLF in the fixture) should have it
        assert len(swolf_values) >= 14
        # Verify the first lap's SWOLF is approximately correct
        first_lap = next(e for e in lap_events)
        assert first_lap["swolf"] == pytest.approx(96.77981960773468, abs=0.001)

    def test_build_swim_intervals_from_fixture(
        self,
        create_health_zip: Callable[..., str],
        load_export_fragment: Callable[[str], str],
        build_health_export_xml: Callable[[list[str]], str],
    ) -> None:
        """End-to-end: parsed events produce 9 intervals matching the fixture segments."""
        xml = build_health_export_xml([load_export_fragment("workout_swimming.xml")])
        zip_path = create_health_zip(xml_content=xml)

        with ExportParser() as parser:
            health_data = parser.parse(zip_path)

        workout = health_data.workouts.iloc[0]
        events = workout["swimming_events"]
        lap_length = float(workout["LapLength"])  # 50 m

        intervals = build_swim_intervals(events, lap_length)
        # The fixture has 9 segments
        assert len(intervals) == 9
        # Total laps across all intervals must equal 15
        total_laps = sum(len(i.laps) for i in intervals)
        assert total_laps == 15
        # All distances should be 50 m (the pool length)
        for interval in intervals:
            for lap in interval.laps:
                assert lap.distance_m == pytest.approx(50.0)

    def test_non_swimming_workout_no_events(
        self,
        create_health_zip: Callable[..., str],
        load_export_fragment: Callable[[str], str],
        build_health_export_xml: Callable[[list[str]], str],
    ) -> None:
        """Running workouts should not have swimming_events populated."""
        xml = build_health_export_xml([load_export_fragment("workout_running.xml")])
        zip_path = create_health_zip(xml_content=xml)

        with ExportParser() as parser:
            health_data = parser.parse(zip_path)

        workout = health_data.workouts.iloc[0]
        assert workout["activityType"] == "Running"
        # Either not present or empty
        events = workout.get("swimming_events")
        assert events is None or events == []


# ---------------------------------------------------------------------------
# BuildSwimIntervalDisplayRows – merged per-interval rows
# ---------------------------------------------------------------------------


def _make_swim_lap(
    lap_number: int,
    distance_m: float = 50.0,
    duration_s: float = 65.0,
    stroke_style: str = "Breaststroke",
    swolf: float | None = 100.0,
) -> SwimLap:
    """Build a SwimLap for unit-testing the display-row builder."""
    return SwimLap(
        lap_number=lap_number,
        distance_m=distance_m,
        duration_s=duration_s,
        stroke_style=stroke_style,
        swolf=swolf,
    )


class TestBuildSwimIntervalDisplayRowsEmpty:
    """Edge cases for build_swim_interval_display_rows with no/empty data."""

    def test_empty_list_returns_empty(self) -> None:
        assert build_swim_interval_display_rows([]) == []

    def test_interval_with_no_laps_is_skipped(self) -> None:
        """An interval with an empty laps list should produce no row."""
        result = build_swim_interval_display_rows([SwimInterval(laps=[], pause_s=None)])
        assert result == []


class TestBuildSwimIntervalDisplayRowsMerging:
    """Test that laps within one interval are merged into a single display row."""

    def test_single_lap_single_interval(self) -> None:
        """One interval, one lap → one row."""
        interval = SwimInterval(
            laps=[_make_swim_lap(1, distance_m=50.0, duration_s=65.0)],
            pause_s=None,
        )
        rows = build_swim_interval_display_rows([interval])
        assert len(rows) == 1
        assert rows[0]["num"] == 1
        assert rows[0]["dist"] == "50 m"
        assert rows[0]["dur"] == "1:05"
        assert rows[0]["pause"] == ""

    def test_two_laps_merged_into_one_row(self) -> None:
        """Two laps in one interval → single row with summed distance and duration."""
        interval = SwimInterval(
            laps=[
                _make_swim_lap(1, distance_m=50.0, duration_s=65.0),
                _make_swim_lap(2, distance_m=50.0, duration_s=78.0),
            ],
            pause_s=None,
        )
        rows = build_swim_interval_display_rows([interval])
        assert len(rows) == 1
        assert rows[0]["dist"] == "100 m"
        assert rows[0]["dur"] == "2:23"  # 143 s = 2:23

    def test_two_intervals_produce_two_rows(self) -> None:
        """Two separate intervals → two rows."""
        intervals = [
            SwimInterval(laps=[_make_swim_lap(1)], pause_s=90.0),
            SwimInterval(laps=[_make_swim_lap(2)], pause_s=None),
        ]
        rows = build_swim_interval_display_rows(intervals)
        assert len(rows) == 2

    def test_interval_numbers_are_sequential(self) -> None:
        """Interval numbers should be 1-based sequential integers."""
        intervals = [
            SwimInterval(laps=[_make_swim_lap(1)], pause_s=30.0),
            SwimInterval(laps=[_make_swim_lap(2)], pause_s=45.0),
            SwimInterval(laps=[_make_swim_lap(3)], pause_s=None),
        ]
        rows = build_swim_interval_display_rows(intervals)
        assert [r["num"] for r in rows] == [1, 2, 3]


class TestBuildSwimIntervalDisplayRowsStroke:
    """Test stroke style merging in display rows."""

    def test_single_stroke_preserved(self) -> None:
        """All laps with the same stroke → that stroke label is shown."""
        interval = SwimInterval(
            laps=[
                _make_swim_lap(1, stroke_style="Freestyle"),
                _make_swim_lap(2, stroke_style="Freestyle"),
            ],
            pause_s=None,
        )
        rows = build_swim_interval_display_rows([interval])
        assert rows[0]["stroke"] == "Freestyle"

    def test_mixed_strokes_produce_mixed_label(self) -> None:
        """Laps with different stroke styles → 'Mixed'."""
        interval = SwimInterval(
            laps=[
                _make_swim_lap(1, stroke_style="Freestyle"),
                _make_swim_lap(2, stroke_style="Breaststroke"),
            ],
            pause_s=None,
        )
        rows = build_swim_interval_display_rows([interval])
        assert rows[0]["stroke"] == "Mixed"

    def test_all_unknown_strokes_returns_unknown(self) -> None:
        """Laps all marked Unknown → 'Unknown'."""
        interval = SwimInterval(
            laps=[_make_swim_lap(1, stroke_style="Unknown")],
            pause_s=None,
        )
        rows = build_swim_interval_display_rows([interval])
        assert rows[0]["stroke"] == "Unknown"

    def test_one_known_one_unknown_uses_known(self) -> None:
        """One lap Unknown, other Freestyle → 'Freestyle' (Unknown is excluded)."""
        interval = SwimInterval(
            laps=[
                _make_swim_lap(1, stroke_style="Unknown"),
                _make_swim_lap(2, stroke_style="Freestyle"),
            ],
            pause_s=None,
        )
        rows = build_swim_interval_display_rows([interval])
        assert rows[0]["stroke"] == "Freestyle"


class TestBuildSwimIntervalDisplayRowsSwolf:
    """Test SWOLF averaging in display rows."""

    def test_swolf_averaged_across_laps(self) -> None:
        """SWOLF should be the mean of non-None lap SWOLFs."""
        interval = SwimInterval(
            laps=[
                _make_swim_lap(1, swolf=96.0),
                _make_swim_lap(2, swolf=104.0),
            ],
            pause_s=None,
        )
        rows = build_swim_interval_display_rows([interval])
        assert rows[0]["swolf"] == "100.0"

    def test_swolf_none_laps_excluded_from_average(self) -> None:
        """Laps with None SWOLF should not contribute to the average."""
        interval = SwimInterval(
            laps=[
                _make_swim_lap(1, swolf=None),
                _make_swim_lap(2, swolf=100.0),
            ],
            pause_s=None,
        )
        rows = build_swim_interval_display_rows([interval])
        assert rows[0]["swolf"] == "100.0"

    def test_all_swolf_none_produces_dash(self) -> None:
        """When all laps have no SWOLF, the display value should be '–'."""
        interval = SwimInterval(
            laps=[_make_swim_lap(1, swolf=None)],
            pause_s=None,
        )
        rows = build_swim_interval_display_rows([interval])
        assert rows[0]["swolf"] == "–"

    def test_swolf_format_one_decimal(self) -> None:
        """SWOLF should be formatted to one decimal place."""
        interval = SwimInterval(
            laps=[_make_swim_lap(1, swolf=97.777)],
            pause_s=None,
        )
        rows = build_swim_interval_display_rows([interval])
        assert rows[0]["swolf"] == "97.8"


class TestBuildSwimIntervalDisplayRowsPause:
    """Test rest/pause formatting in display rows."""

    def test_pause_formatted_correctly(self) -> None:
        """Pause duration should be formatted as m:ss."""
        intervals = [
            SwimInterval(laps=[_make_swim_lap(1)], pause_s=90.0),
            SwimInterval(laps=[_make_swim_lap(2)], pause_s=None),
        ]
        rows = build_swim_interval_display_rows(intervals)
        assert rows[0]["pause"] == "1:30"
        assert rows[1]["pause"] == ""

    def test_zero_pause_is_empty_string(self) -> None:
        """A pause of 0 s should produce an empty string (not '0:00')."""
        intervals = [
            SwimInterval(laps=[_make_swim_lap(1)], pause_s=0.0),
            SwimInterval(laps=[_make_swim_lap(2)], pause_s=None),
        ]
        rows = build_swim_interval_display_rows(intervals)
        assert rows[0]["pause"] == ""


class TestBuildSwimIntervalDisplayRowsFixture:
    """Integration: build_swim_interval_display_rows from real fixture data."""

    def test_fixture_produces_nine_rows(
        self,
        create_health_zip: Callable[..., str],
        load_export_fragment: Callable[[str], str],
        build_health_export_xml: Callable[[list[str]], str],
    ) -> None:
        """The swimming fixture has 9 segments → 9 display rows (one per set)."""
        xml = build_health_export_xml([load_export_fragment("workout_swimming.xml")])
        zip_path = create_health_zip(xml_content=xml)

        with ExportParser() as parser:
            health_data = parser.parse(zip_path)

        workout = health_data.workouts.iloc[0]
        events = workout["swimming_events"]
        lap_length = float(workout["LapLength"])
        intervals = build_swim_intervals(events, lap_length)
        rows = build_swim_interval_display_rows(intervals)

        # 9 segments → 9 display rows, not 15 (individual laps)
        assert len(rows) == 9

    def test_first_set_merges_two_laps(
        self,
        create_health_zip: Callable[..., str],
        load_export_fragment: Callable[[str], str],
        build_health_export_xml: Callable[[list[str]], str],
    ) -> None:
        """Laps 1 and 2 belong to the same segment → merged into one 100 m row."""
        xml = build_health_export_xml([load_export_fragment("workout_swimming.xml")])
        zip_path = create_health_zip(xml_content=xml)

        with ExportParser() as parser:
            health_data = parser.parse(zip_path)

        workout = health_data.workouts.iloc[0]
        events = workout["swimming_events"]
        lap_length = float(workout["LapLength"])
        intervals = build_swim_intervals(events, lap_length)
        rows = build_swim_interval_display_rows(intervals)

        first_row = rows[0]
        # Segment 1 has 2 laps of 50 m each → 100 m total
        assert first_row["dist"] == "100 m"
        # SWOLF should be a numeric string (not "–")
        assert first_row["swolf"] != "–"
        # Last interval has no pause
        assert rows[-1]["pause"] == ""
