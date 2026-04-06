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

            with patch("ui.workout_table.ui.table", return_value=table_stub) as table_mock:
                wt.render_workout_table.func()

            table_mock.assert_called_once()
            # One slot per column: date, activity_type, duration, distance, calories,
            # avg_hr, elevation, avg_power
            assert len(table_stub.slots) == 8
            slot_names = [s[0] for s in table_stub.slots]
            assert "body-cell-date" in slot_names
            assert "body-cell-activity_type" in slot_names
            assert "body-cell-duration" in slot_names
            assert "body-cell-distance" in slot_names
            assert "body-cell-calories" in slot_names
            assert "body-cell-avg_hr" in slot_names
            assert "body-cell-elevation" in slot_names
            assert "body-cell-avg_power" in slot_names
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

            with patch("ui.workout_table.ui.table", return_value=DummyTable()) as table_mock:
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
