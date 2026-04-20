"""Tests for ui.workout_table module."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from app_state import state
from ui import workout_table as wt

from ._helpers import DummyComponent, DummyTable


class TestBuildWorkoutRows:
    """Tests for _build_workout_rows()."""

    def _make_workouts(self, rows: list[dict[str, Any]]) -> pd.DataFrame:
        """Build a DataFrame suitable for WorkoutManager from a list of row dicts."""
        return pd.DataFrame(rows)

    def test_returns_empty_list_when_workouts_empty(self) -> None:
        """Empty workouts DataFrame should produce no rows."""

        original_workouts: Any = state.workouts
        workouts_mock = MagicMock()
        workouts_mock._filter_workouts.return_value = pd.DataFrame()
        try:
            state.workouts = workouts_mock
            result = wt._build_workout_rows()
        finally:
            state.workouts = original_workouts
        assert result == []

    def test_formats_date_duration_and_activity(self) -> None:
        """Rows should include formatted date, duration and activity type."""

        original_workouts: Any = state.workouts
        original_file_loaded = state.file_loaded

        workouts_mock = MagicMock()
        workouts_mock._filter_workouts.return_value = pd.DataFrame(
            [
                {
                    "activityType": "Running",
                    "startDate": pd.Timestamp("2025-09-16"),
                    "duration": 3660.0,  # 1 h 1 min
                }
            ]
        )

        try:
            state.workouts = workouts_mock
            state.file_loaded = True
            rows = wt._build_workout_rows()
        finally:
            state.workouts = original_workouts
            state.file_loaded = original_file_loaded

        assert len(rows) == 1
        row = rows[0]
        assert row["activity_type"] == "Running"
        assert "duration" in row
        assert row["duration_sort"] == pytest.approx(3660.0)
        assert "date" in row
        assert row["date_sort"] != pytest.approx(0.0)  # valid timestamp

    def test_missing_optional_columns_use_sentinel(self) -> None:
        """Rows missing optional numeric columns should use _MISSING_SORT sentinel."""

        original_workouts: Any = state.workouts
        workouts_mock = MagicMock()
        workouts_mock._filter_workouts.return_value = pd.DataFrame(
            [
                {
                    "activityType": "Cycling",
                    "startDate": pd.Timestamp("2025-01-01"),
                    "duration": 1800.0,
                    # No distance, calories, HR, elevation, power columns
                }
            ]
        )

        try:
            state.workouts = workouts_mock
            rows = wt._build_workout_rows()
        finally:
            state.workouts = original_workouts

        assert len(rows) == 1
        row = rows[0]
        assert row["distance_sort"] == wt._MISSING_SORT
        assert row["distance"] == "–"
        assert row["calories_sort"] == wt._MISSING_SORT
        assert row["calories"] == "–"
        assert row["avg_hr_sort"] == wt._MISSING_SORT
        assert row["avg_hr"] == "–"
        assert row["elevation_sort"] == wt._MISSING_SORT
        assert row["elevation"] == "–"
        assert row["avg_power_sort"] == wt._MISSING_SORT
        assert row["avg_power"] == "–"

    def test_optional_columns_formatted_when_present(self) -> None:
        """Optional columns should be formatted when their values are present."""

        original_workouts: Any = state.workouts
        workouts_mock = MagicMock()
        workouts_mock._filter_workouts.return_value = pd.DataFrame(
            [
                {
                    "activityType": "Running",
                    "startDate": pd.Timestamp("2025-09-16"),
                    "duration": 3600.0,
                    "distance": 10000.0,  # metres → 10.0 km
                    "sumActiveEnergyBurned": 650.0,
                    "averageHeartRate": 130.0,
                    "ElevationAscended": 65.0,  # metres
                    "averageRunningPower": 210.0,
                }
            ]
        )

        try:
            state.workouts = workouts_mock
            rows = wt._build_workout_rows()
        finally:
            state.workouts = original_workouts

        assert len(rows) == 1
        row = rows[0]
        assert row["distance"] == "10.0 km"
        assert row["distance_sort"] == pytest.approx(10000.0)
        assert row["calories"] == "650 kcal"
        assert row["calories_sort"] == pytest.approx(650.0)
        assert row["avg_hr"] == "130 bpm"
        assert row["avg_hr_sort"] == pytest.approx(130.0)
        assert row["elevation"] == "65 m"
        assert row["elevation_sort"] == pytest.approx(65.0)
        assert row["avg_power"] == "210 W"
        assert row["avg_power_sort"] == pytest.approx(210.0)

    def test_rows_sorted_by_date_descending(self) -> None:
        """Rows should be ordered most-recent first."""

        original_workouts: Any = state.workouts
        workouts_mock = MagicMock()
        workouts_mock._filter_workouts.return_value = pd.DataFrame(
            [
                {
                    "activityType": "Running",
                    "startDate": pd.Timestamp("2025-01-01"),
                    "duration": 3600.0,
                },
                {
                    "activityType": "Running",
                    "startDate": pd.Timestamp("2025-06-01"),
                    "duration": 1800.0,
                },
            ]
        )

        try:
            state.workouts = workouts_mock
            rows = wt._build_workout_rows()
        finally:
            state.workouts = original_workouts

        assert len(rows) == 2
        assert rows[0]["date_sort"] > rows[1]["date_sort"]

    def test_row_ids_are_unique(self) -> None:
        """Every row must have a distinct ``id`` field."""

        original_workouts: Any = state.workouts
        workouts_mock = MagicMock()
        workouts_mock._filter_workouts.return_value = pd.DataFrame(
            [
                {
                    "activityType": "Running",
                    "startDate": pd.Timestamp("2025-01-01"),
                    "duration": 3600.0,
                },
                {
                    "activityType": "Running",
                    "startDate": pd.Timestamp("2025-01-01"),  # same timestamp
                    "duration": 1800.0,
                },
            ]
        )

        try:
            state.workouts = workouts_mock
            rows = wt._build_workout_rows()
        finally:
            state.workouts = original_workouts

        ids = [r["id"] for r in rows]
        assert len(set(ids)) == len(ids)


class TestFindRowIndex:
    """Tests for _find_row_index()."""

    def test_returns_correct_index_for_matching_id(self) -> None:
        """Should return the index of the row whose id matches."""
        rows: list[dict[str, Any]] = [
            {"id": "a", "activity_type": "Running"},
            {"id": "b", "activity_type": "Cycling"},
            {"id": "c", "activity_type": "Walking"},
        ]
        assert wt._find_row_index("b", rows) == 1

    def test_returns_none_for_unknown_id(self) -> None:
        """Should return None when the id is not found."""
        rows: list[dict[str, Any]] = [
            {"id": "a"},
            {"id": "b"},
        ]
        assert wt._find_row_index("xyz", rows) is None

    def test_returns_none_for_empty_rows(self) -> None:
        """Should return None when the row list is empty."""
        assert wt._find_row_index("any", []) is None

    def test_uses_get_so_missing_key_returns_none(self) -> None:
        """Should not raise KeyError when a row dict has no 'id' key."""
        rows: list[dict[str, Any]] = [{"activity_type": "Running"}]
        assert wt._find_row_index("any", rows) is None


class TestRenderWorkoutTable:
    """Tests for render_workout_table()."""

    def test_shows_empty_state_when_file_not_loaded(self) -> None:
        """Tab should display an empty-state label when no file has been loaded."""
        original_file_loaded = state.file_loaded

        try:
            state.file_loaded = False

            with patch("ui.workout_table.ui.label", return_value=DummyComponent()) as label_mock:
                wt.render_workout_table.func()

            label_mock.assert_called_once()
            assert any(
                "Load a file" in str(call.args[0])
                for call in label_mock.call_args_list
                if call.args
            )
        finally:
            state.file_loaded = original_file_loaded

    def test_renders_table_with_slots_when_loaded(self) -> None:
        """Table should be created with one body-cell slot per column when data is loaded."""
        original_file_loaded = state.file_loaded
        original_workouts: Any = state.workouts

        workouts_mock = MagicMock()
        workouts_mock._filter_workouts.return_value = pd.DataFrame(
            [
                {
                    "activityType": "Running",
                    "startDate": pd.Timestamp("2025-09-16"),
                    "duration": 3660.0,
                }
            ]
        )

        table_stub = DummyTable()

        try:
            state.file_loaded = True
            state.workouts = workouts_mock

            with (
                patch("ui.workout_table.ui.table", return_value=table_stub) as table_mock,
                patch("ui.workout_table.create_workout_detail_modal", return_value=lambda _: None),
            ):
                wt.render_workout_table.func()

            table_mock.assert_called_once()
            # One slot per data column plus the actions column:
            # date, activity_type, duration, distance, calories,
            # avg_hr, elevation, avg_power, actions
            assert len(table_stub.slots) == 9
            slot_names = [s[0] for s in table_stub.slots]
            assert "body-cell-date" in slot_names
            assert "body-cell-activity_type" in slot_names
            assert "body-cell-duration" in slot_names
            assert "body-cell-distance" in slot_names
            assert "body-cell-calories" in slot_names
            assert "body-cell-avg_hr" in slot_names
            assert "body-cell-elevation" in slot_names
            assert "body-cell-avg_power" in slot_names
            assert "body-cell-actions" in slot_names
        finally:
            state.file_loaded = original_file_loaded
            state.workouts = original_workouts

    def test_table_pagination_default_sort_date_descending(self) -> None:
        """Table should be initialised with date sort descending."""
        original_file_loaded = state.file_loaded
        original_workouts: Any = state.workouts

        workouts_mock = MagicMock()
        workouts_mock._filter_workouts.return_value = pd.DataFrame(
            [
                {
                    "activityType": "Running",
                    "startDate": pd.Timestamp("2025-09-16"),
                    "duration": 3660.0,
                }
            ]
        )

        try:
            state.file_loaded = True
            state.workouts = workouts_mock

            with (
                patch("ui.workout_table.ui.table", return_value=DummyTable()) as table_mock,
                patch("ui.workout_table.create_workout_detail_modal", return_value=lambda _: None),
            ):
                wt.render_workout_table.func()

            call_kwargs = table_mock.call_args
            pagination = call_kwargs.kwargs.get("pagination", {})
            assert pagination.get("sortBy") == "date_sort"
            assert pagination.get("descending") is True
        finally:
            state.file_loaded = original_file_loaded
            state.workouts = original_workouts

    def test_no_table_when_file_not_loaded(self) -> None:
        """ui.table should not be created when no file is loaded."""
        original_file_loaded = state.file_loaded

        try:
            state.file_loaded = False

            with (
                patch("ui.workout_table.ui.label", return_value=DummyComponent()),
                patch("ui.workout_table.ui.table") as table_mock,
            ):
                wt.render_workout_table.func()

            table_mock.assert_not_called()
        finally:
            state.file_loaded = original_file_loaded

    def test_open_detail_event_fires_for_known_row_id(self) -> None:
        """Firing 'open_detail' for a known row id should call the open_detail callable."""
        original_file_loaded = state.file_loaded
        original_workouts: Any = state.workouts

        workouts_mock = MagicMock()
        workouts_mock._filter_workouts.return_value = pd.DataFrame(
            [
                {
                    "activityType": "Running",
                    "startDate": pd.Timestamp("2025-09-16"),
                    "duration": 3660.0,
                }
            ]
        )

        table_stub = DummyTable()
        open_detail_calls: list[int] = []

        try:
            state.file_loaded = True
            state.workouts = workouts_mock

            with (
                patch("ui.workout_table.ui.table", return_value=table_stub),
                patch(
                    "ui.workout_table.create_workout_detail_modal",
                    return_value=lambda idx: open_detail_calls.append(idx),
                ),
            ):
                wt.render_workout_table.func()

            # Extract the row id that was built for this row.
            rows = wt._build_workout_rows()
            assert rows, "Expected at least one row from the mock workouts"
            row_id = rows[0]["id"]

            # Fire the event as Quasar would when the button is clicked.
            table_stub.fire("open_detail", row_id)

            assert open_detail_calls == [0]
        finally:
            state.file_loaded = original_file_loaded
            state.workouts = original_workouts

    def test_open_detail_event_ignored_for_unknown_row_id(self) -> None:
        """Firing 'open_detail' for an unknown row id should be a no-op."""
        original_file_loaded = state.file_loaded
        original_workouts: Any = state.workouts

        workouts_mock = MagicMock()
        workouts_mock._filter_workouts.return_value = pd.DataFrame(
            [
                {
                    "activityType": "Running",
                    "startDate": pd.Timestamp("2025-09-16"),
                    "duration": 3660.0,
                }
            ]
        )

        table_stub = DummyTable()
        open_detail_calls: list[int] = []

        try:
            state.file_loaded = True
            state.workouts = workouts_mock

            with (
                patch("ui.workout_table.ui.table", return_value=table_stub),
                patch(
                    "ui.workout_table.create_workout_detail_modal",
                    return_value=lambda idx: open_detail_calls.append(idx),
                ),
            ):
                wt.render_workout_table.func()

            table_stub.fire("open_detail", "nonexistent-id")

            # No calls expected when id is not found.
            assert open_detail_calls == []
        finally:
            state.file_loaded = original_file_loaded
            state.workouts = original_workouts


class TestBuildWorkoutRowsRangeFiltering:
    """Tests for distance and duration range filtering in _build_workout_rows()."""

    def _make_workouts_mock(self, rows: list[dict[str, Any]]) -> MagicMock:
        mock = MagicMock()
        mock._filter_workouts.return_value = pd.DataFrame(rows)
        return mock

    def test_distance_range_filter_excludes_outside_rows(self) -> None:
        """Workouts outside the distance range should not appear in the result."""
        original_workouts: Any = state.workouts
        original_dist = dict(state.distance_range)

        workouts_mock = self._make_workouts_mock(
            [
                {
                    "activityType": "Running",
                    "startDate": pd.Timestamp("2025-01-01"),
                    "duration": 1800.0,
                    "distance": 3000.0,
                },  # 3 km – too short
                {
                    "activityType": "Running",
                    "startDate": pd.Timestamp("2025-01-02"),
                    "duration": 3600.0,
                    "distance": 8000.0,
                },  # 8 km – in range
                {
                    "activityType": "Running",
                    "startDate": pd.Timestamp("2025-01-03"),
                    "duration": 7200.0,
                    "distance": 15000.0,
                },  # 15 km – too long
            ]
        )

        try:
            state.workouts = workouts_mock
            state.distance_range = {"min": 5.0, "max": 10.0}
            rows = wt._build_workout_rows()
        finally:
            state.workouts = original_workouts
            state.distance_range = original_dist

        assert len(rows) == 1
        assert rows[0]["distance_sort"] == pytest.approx(8000.0)

    def test_distance_range_zero_zero_applies_no_filter(self) -> None:
        """Default {"min": 0, "max": 0} state should not filter any workouts."""
        original_workouts: Any = state.workouts
        original_dist = dict(state.distance_range)

        workouts_mock = self._make_workouts_mock(
            [
                {
                    "activityType": "Running",
                    "startDate": pd.Timestamp("2025-01-01"),
                    "duration": 1800.0,
                    "distance": 1000.0,
                },
                {
                    "activityType": "Running",
                    "startDate": pd.Timestamp("2025-01-02"),
                    "duration": 3600.0,
                    "distance": 42000.0,
                },
            ]
        )

        try:
            state.workouts = workouts_mock
            state.distance_range = {"min": 0.0, "max": 0.0}
            rows = wt._build_workout_rows()
        finally:
            state.workouts = original_workouts
            state.distance_range = original_dist

        assert len(rows) == 2

    def test_duration_range_filter_excludes_outside_rows(self) -> None:
        """Workouts outside the duration range should not appear in the result."""
        original_workouts: Any = state.workouts
        original_dur = dict(state.duration_range_min)

        workouts_mock = self._make_workouts_mock(
            [
                {
                    "activityType": "Running",
                    "startDate": pd.Timestamp("2025-01-01"),
                    "duration": 600.0,
                    "distance": 2000.0,
                },  # 10 min – too short
                {
                    "activityType": "Running",
                    "startDate": pd.Timestamp("2025-01-02"),
                    "duration": 3600.0,
                    "distance": 10000.0,
                },  # 60 min – in range
                {
                    "activityType": "Running",
                    "startDate": pd.Timestamp("2025-01-03"),
                    "duration": 9000.0,
                    "distance": 25000.0,
                },  # 150 min – too long
            ]
        )

        try:
            state.workouts = workouts_mock
            state.duration_range_min = {"min": 30.0, "max": 90.0}
            rows = wt._build_workout_rows()
        finally:
            state.workouts = original_workouts
            state.duration_range_min = original_dur

        assert len(rows) == 1
        assert rows[0]["duration_sort"] == pytest.approx(3600.0)

    def test_duration_range_zero_zero_applies_no_filter(self) -> None:
        """Default {"min": 0, "max": 0} state should not filter any workouts."""
        original_workouts: Any = state.workouts
        original_dur = dict(state.duration_range_min)

        workouts_mock = self._make_workouts_mock(
            [
                {
                    "activityType": "Running",
                    "startDate": pd.Timestamp("2025-01-01"),
                    "duration": 600.0,
                    "distance": 2000.0,
                },
                {
                    "activityType": "Running",
                    "startDate": pd.Timestamp("2025-01-02"),
                    "duration": 7200.0,
                    "distance": 20000.0,
                },
            ]
        )

        try:
            state.workouts = workouts_mock
            state.duration_range_min = {"min": 0.0, "max": 0.0}
            rows = wt._build_workout_rows()
        finally:
            state.workouts = original_workouts
            state.duration_range_min = original_dur

        assert len(rows) == 2

    def test_combined_distance_and_duration_filter(self) -> None:
        """Both distance and duration range filters apply simultaneously."""
        original_workouts: Any = state.workouts
        original_dist = dict(state.distance_range)
        original_dur = dict(state.duration_range_min)

        workouts_mock = self._make_workouts_mock(
            [
                # passes distance, fails duration
                {
                    "activityType": "Running",
                    "startDate": pd.Timestamp("2025-01-01"),
                    "duration": 600.0,
                    "distance": 8000.0,
                },
                # passes both
                {
                    "activityType": "Running",
                    "startDate": pd.Timestamp("2025-01-02"),
                    "duration": 3600.0,
                    "distance": 8000.0,
                },
                # fails distance
                {
                    "activityType": "Running",
                    "startDate": pd.Timestamp("2025-01-03"),
                    "duration": 3600.0,
                    "distance": 1000.0,
                },
            ]
        )

        try:
            state.workouts = workouts_mock
            state.distance_range = {"min": 5.0, "max": 15.0}
            state.duration_range_min = {"min": 30.0, "max": 90.0}
            rows = wt._build_workout_rows()
        finally:
            state.workouts = original_workouts
            state.distance_range = original_dist
            state.duration_range_min = original_dur

        assert len(rows) == 1
        assert rows[0]["distance_sort"] == pytest.approx(8000.0)
        assert rows[0]["duration_sort"] == pytest.approx(3600.0)


class TestSafeFloat:
    """Unit tests for _safe_float() helper."""

    def test_returns_none_for_none(self) -> None:
        """None input should return None."""
        assert wt._safe_float(None) is None

    def test_returns_none_for_non_numeric_string(self) -> None:
        """Non-numeric string should return None (TypeError/ValueError branch)."""
        assert wt._safe_float("not-a-number") is None

    def test_returns_float_for_numeric_string(self) -> None:
        """A numeric string should be converted to float."""
        result = wt._safe_float("3.14")
        assert result == pytest.approx(3.14)

    def test_returns_none_for_nan(self) -> None:
        """float('nan') should return None."""
        assert wt._safe_float(float("nan")) is None


class TestExtractDistanceField:
    """Unit tests for _extract_distance_field() helper."""

    def test_zero_distance_returns_dash(self) -> None:
        """Zero-metre distance should produce '–' as the display string."""
        row = {"distance": 0.0}
        sort_val, display = wt._extract_distance_field(row)
        assert sort_val == pytest.approx(0.0)
        assert display == "–"

    def test_negative_distance_returns_dash(self) -> None:
        """Negative distance should also produce '–'."""
        row = {"distance": -100.0}
        _, display = wt._extract_distance_field(row)
        assert display == "–"

    def test_imperial_distance_uses_miles(self) -> None:
        """distance_unit='mi' should format in miles."""
        from units import METERS_TO_MILES

        row = {"distance": 1609.344}  # 1 mile
        _, display = wt._extract_distance_field(row, distance_unit="mi")
        expected = f"{1609.344 * METERS_TO_MILES:.1f} mi"
        assert display == expected


class TestBuildWorkoutRowsImperial:
    """Tests for imperial unit rendering in _build_workout_rows()."""

    def _make_workouts_mock(self, rows: list[dict[str, Any]]) -> MagicMock:
        mock = MagicMock()
        mock._filter_workouts.return_value = pd.DataFrame(rows)
        return mock

    def test_elevation_displayed_in_feet_for_imperial(self) -> None:
        """Elevation column should show 'ft' when unit system is imperial."""
        from unittest.mock import patch

        from units import METERS_TO_FEET

        original_workouts: Any = state.workouts
        workouts_mock = self._make_workouts_mock(
            [
                {
                    "activityType": "Running",
                    "startDate": pd.Timestamp("2025-01-01"),
                    "duration": 3600.0,
                    "distance": 10000.0,
                    "ElevationAscended": 100.0,  # metres
                }
            ]
        )

        try:
            state.workouts = workouts_mock
            with patch("ui.workout_table.get_elevation_unit", return_value="ft"):
                rows = wt._build_workout_rows()
        finally:
            state.workouts = original_workouts

        assert len(rows) == 1
        expected_ft = int(round(100.0 * METERS_TO_FEET))
        assert rows[0]["elevation"] == f"{expected_ft} ft"

    def test_distance_displayed_in_miles_for_imperial(self) -> None:
        """Distance column should show 'mi' when unit system is imperial."""
        from unittest.mock import patch

        from units import METERS_TO_MILES

        original_workouts: Any = state.workouts
        workouts_mock = self._make_workouts_mock(
            [
                {
                    "activityType": "Running",
                    "startDate": pd.Timestamp("2025-01-01"),
                    "duration": 3600.0,
                    "distance": 1609.344,  # 1 mile
                }
            ]
        )

        try:
            state.workouts = workouts_mock
            with patch("ui.workout_table.get_distance_unit", return_value="mi"):
                rows = wt._build_workout_rows()
        finally:
            state.workouts = original_workouts

        assert len(rows) == 1
        expected_mi = f"{1609.344 * METERS_TO_MILES:.1f} mi"
        assert rows[0]["distance"] == expected_mi

    def test_all_rows_filtered_out_returns_empty(self) -> None:
        """Applying a range filter that excludes all rows should return []."""
        original_workouts: Any = state.workouts
        original_dist = dict(state.distance_range)

        workouts_mock = self._make_workouts_mock(
            [
                {
                    "activityType": "Running",
                    "startDate": pd.Timestamp("2025-01-01"),
                    "duration": 3600.0,
                    "distance": 1000.0,
                },
            ]
        )

        try:
            state.workouts = workouts_mock
            # Range 20–50 km excludes the 1 km workout
            state.distance_range = {"min": 20.0, "max": 50.0}
            rows = wt._build_workout_rows()
        finally:
            state.workouts = original_workouts
            state.distance_range = original_dist

        assert rows == []


class TestFormatPace:
    """Unit tests for _format_pace()."""

    def test_positive_speed_produces_pace_string(self) -> None:
        """A positive speed should produce a 'mm:ss /km' string."""
        # 10 km/h → 6:00 /km
        result = wt._format_pace(10.0)
        assert result == "6:00 /km"

    def test_zero_speed_returns_dash(self) -> None:
        """Zero speed should return '–'."""
        assert wt._format_pace(0.0) == "–"

    def test_negative_speed_returns_dash(self) -> None:
        """Negative speed should return '–'."""
        assert wt._format_pace(-5.0) == "–"

    def test_fractional_seconds_rounded(self) -> None:
        """Fractional seconds should be rounded to the nearest integer."""
        # 9 km/h → 6.666... min/km → 6:40
        result = wt._format_pace(9.0)
        assert result == "6:40 /km"

    def test_seconds_rollover_increments_minutes(self) -> None:
        """When rounded seconds == 60, minutes should increment and seconds reset."""
        # Craft a speed so that pace_min has fractional seconds that round to 60.
        # pace_min = 60 / speed. We need (pace_min - floor(pace_min)) * 60 ≈ 59.5+
        # speed = 60 / (n + 59.5/60) for some integer n.
        # For n=6: speed = 60 / 6.9916... ≈ 8.582 km/h
        # → pace ≈ 6.9916 min/km → 6 min 59.5 s → rounds to 7:00
        result = wt._format_pace(60.0 / (6 + 59.5 / 60))
        # seconds 59.5 rounds to 60 → should produce 7:00, not 6:60
        assert "60" not in result
        assert result == "7:00 /km"


class TestNearestVo2Max:
    """Unit tests for _nearest_vo2_max()."""

    def test_returns_dash_when_date_is_none(self) -> None:
        """Should return '–' when workout_date is None."""
        result = wt._nearest_vo2_max(None)
        assert result == "–"

    def test_returns_dash_when_no_vo2_records(self) -> None:
        """Should return '–' when VO2Max records are absent."""
        from app_state import state
        from logic.records_by_type import RecordsByType

        original = state.records_by_type
        try:
            state.records_by_type = RecordsByType(data={})
            result = wt._nearest_vo2_max(pd.Timestamp("2025-01-01"))
        finally:
            state.records_by_type = original
        assert result == "–"

    def test_returns_nearest_record_by_date(self) -> None:
        """Should return the VO2 max value from the nearest-in-time record."""
        from app_state import state
        from logic.records_by_type import RecordsByType

        vo2_df = pd.DataFrame(
            [
                {"startDate": "2025-01-01 10:00:00", "value": 50.0},
                {"startDate": "2025-06-01 10:00:00", "value": 52.0},
            ]
        )
        original = state.records_by_type
        try:
            state.records_by_type = RecordsByType(data={"VO2Max": vo2_df})
            # Workout on 2025-01-02 → nearest is 2025-01-01 record (value 50.0)
            result = wt._nearest_vo2_max(pd.Timestamp("2025-01-02"))
        finally:
            state.records_by_type = original
        assert result == "50.0 mL/min·kg"

    def test_returns_dash_when_nearest_record_has_none_value(self) -> None:
        """Should return '–' when the nearest VO2Max record has a null/NaN value."""
        from app_state import state
        from logic.records_by_type import RecordsByType

        # Record exists but value is None (e.g. exported without measurement)
        vo2_df = pd.DataFrame([{"startDate": "2025-01-01 10:00:00", "value": None}])
        original = state.records_by_type
        try:
            state.records_by_type = RecordsByType(data={"VO2Max": vo2_df})
            result = wt._nearest_vo2_max(pd.Timestamp("2025-01-01"))
        finally:
            state.records_by_type = original
        assert result == "–"


class TestExtractRunningFields:
    """Unit tests for _extract_running_fields()."""

    def _make_row(self, **kwargs: Any) -> dict[str, Any]:
        """Build a minimal row dict with running statistics."""
        base: dict[str, Any] = {
            "activityType": "Running",
            "averageRunningSpeed": 10.0,  # 10 km/h → 6:00 /km
            "averageRunningCadence": 178.0,
            "averageRunningStrideLength": 0.91,
            "averageRunningVerticalOscillation": 8.8,
            "averageRunningGroundContactTime": 304.0,
            "sumStepCount": 9787.0,
        }
        base.update(kwargs)
        return base

    def test_pace_derived_from_speed(self) -> None:
        """Pace should be derived from averageRunningSpeed."""
        row = self._make_row(averageRunningSpeed=10.0)
        result = wt._extract_running_fields(row, None)
        assert result["pace"] == "6:00 /km"

    def test_cadence_formatted(self) -> None:
        """Cadence should show 'spm' unit."""
        row = self._make_row(averageRunningCadence=178.0)
        result = wt._extract_running_fields(row, None)
        assert result["cadence"] == "178 spm"

    def test_stride_length_formatted(self) -> None:
        """Stride length should show 'm' unit to 2 decimal places."""
        row = self._make_row(averageRunningStrideLength=0.91)
        result = wt._extract_running_fields(row, None)
        assert result["stride_length"] == "0.91 m"

    def test_vertical_oscillation_formatted(self) -> None:
        """Vertical oscillation should show 'cm' unit."""
        row = self._make_row(averageRunningVerticalOscillation=8.8)
        result = wt._extract_running_fields(row, None)
        assert result["vertical_oscillation"] == "8.8 cm"

    def test_ground_contact_time_formatted(self) -> None:
        """Ground contact time should show 'ms' unit."""
        row = self._make_row(averageRunningGroundContactTime=304.0)
        result = wt._extract_running_fields(row, None)
        assert result["ground_contact_time"] == "304 ms"

    def test_step_count_formatted(self) -> None:
        """Step count should be an integer string."""
        row = self._make_row(sumStepCount=9787.0)
        result = wt._extract_running_fields(row, None)
        assert result["step_count"] == "9787"

    def test_missing_speed_produces_dash(self) -> None:
        """Missing averageRunningSpeed should produce '–' for pace."""
        row = self._make_row()
        del row["averageRunningSpeed"]
        result = wt._extract_running_fields(row, None)
        assert result["pace"] == "–"

    def test_empty_splits_when_no_route(self) -> None:
        """No route data should produce an empty splits list."""
        row = self._make_row()
        result = wt._extract_running_fields(row, None)
        assert result["splits"] == []

    def test_splits_computed_from_route(self) -> None:
        """Splits should be computed from a WorkoutRoute when present."""
        from datetime import timedelta

        from logic.workout_manager.workout_route import RoutePoint, WorkoutRoute

        start = pd.Timestamp("2024-01-01 10:00:00")
        base_time = start.to_pydatetime().replace(tzinfo=None)
        # 3 m/s × 1001 seconds ≈ 3003 m (via avg-speed calc) → ≥ 3 complete 1km splits
        points = [
            RoutePoint(
                time=base_time + timedelta(seconds=i),
                latitude=0.0,
                longitude=0.0,
                altitude=100.0,
                speed=3.0,
            )
            for i in range(1001)
        ]
        route = WorkoutRoute(points=points)
        row = self._make_row(route=route, distance=3000.0)
        result = wt._extract_running_fields(row, None)
        assert len(result["splits"]) >= 3

    def test_splits_computed_from_route_parts(self) -> None:
        """Splits should be merged from route_parts (multiple GPS segments) when present."""
        from datetime import timedelta

        from logic.workout_manager.workout_route import RoutePoint, WorkoutRoute

        base_time = pd.Timestamp("2024-01-01 10:00:00").to_pydatetime().replace(tzinfo=None)

        # Two separate route segments, each covering ~1500 m at 3 m/s.
        def _make_part(t_offset: int, n: int) -> WorkoutRoute:
            return WorkoutRoute(
                points=[
                    RoutePoint(
                        time=base_time + timedelta(seconds=t_offset + i),
                        latitude=0.0,
                        longitude=0.0,
                        altitude=0.0,
                        speed=3.0,
                    )
                    for i in range(n)
                ]
            )

        part1 = _make_part(0, 501)  # 500 s × 3 m/s = 1500 m
        part2 = _make_part(501, 501)  # another 1500 m segment
        row = self._make_row(route_parts=[part1, part2], distance=3000.0)
        result = wt._extract_running_fields(row, None)
        # Merged route is ≥ 3000 m → at least 3 complete 1 km splits
        assert len(result["splits"]) >= 3

    def test_running_fields_included_for_running_workouts(self) -> None:
        """Running-specific keys should be present in the row dict for Running workouts."""
        original_workouts: Any = state.workouts
        workouts_mock = MagicMock()
        workouts_mock._filter_workouts.return_value = pd.DataFrame(
            [
                {
                    "activityType": "Running",
                    "startDate": pd.Timestamp("2025-09-16"),
                    "duration": 3600.0,
                    "averageRunningSpeed": 10.0,
                    "averageRunningCadence": 178.0,
                }
            ]
        )
        try:
            state.workouts = workouts_mock
            rows = wt._build_workout_rows()
        finally:
            state.workouts = original_workouts
        assert len(rows) == 1
        row = rows[0]
        assert "pace" in row
        assert "cadence" in row
        assert "splits" in row

    def test_running_fields_absent_for_non_running_workouts(self) -> None:
        """Non-Running workouts should not have running-specific keys."""
        original_workouts: Any = state.workouts
        workouts_mock = MagicMock()
        workouts_mock._filter_workouts.return_value = pd.DataFrame(
            [
                {
                    "activityType": "Cycling",
                    "startDate": pd.Timestamp("2025-01-01"),
                    "duration": 3600.0,
                }
            ]
        )
        try:
            state.workouts = workouts_mock
            rows = wt._build_workout_rows()
        finally:
            state.workouts = original_workouts
        assert len(rows) == 1
        row = rows[0]
        assert "pace" not in row
        assert "cadence" not in row
        assert "splits" not in row
