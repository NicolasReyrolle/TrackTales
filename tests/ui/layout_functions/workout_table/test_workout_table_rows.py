"""Tests for _build_workout_rows() and related helpers in ui.workout_table."""

from __future__ import annotations

import logging
from typing import Any
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from app_state import state
from ui.workout_table import rows as wt


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
        assert row["distance"] == "10.00 km"
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

    def test_vo2_dates_precomputed_when_vo2_max_records_present(self) -> None:
        """VO2Max dates should be pre-parsed once and used by _nearest_vo2_max for running rows.

        When state.records_by_type contains VO2Max data, _build_workout_rows pre-computes
        the start dates once so _nearest_vo2_max can skip re-parsing per workout.
        """
        from app_state import state
        from logic.records_by_type import RecordsByType

        original_workouts: Any = state.workouts
        original_records = state.records_by_type
        workouts_mock = MagicMock()
        workouts_mock._filter_workouts.return_value = pd.DataFrame(
            [
                {
                    "activityType": "Running",
                    "startDate": pd.Timestamp("2025-01-02"),
                    "duration": 3600.0,
                    "averageRunningSpeed": 10.0,
                }
            ]
        )
        vo2_df = pd.DataFrame([{"startDate": "2025-01-01", "value": 48.5}])
        try:
            state.workouts = workouts_mock
            state.records_by_type = RecordsByType(data={"VO2Max": vo2_df})
            rows = wt._build_workout_rows()
        finally:
            state.workouts = original_workouts
            state.records_by_type = original_records
        assert len(rows) == 1
        # vo2_max should have been populated via the pre-computed dates path.
        assert rows[0]["vo2_max"] == "48.5 mL/min·kg"

    def test_vo2_max_populated_for_non_running_activity(self) -> None:
        """vo2_max must be present in the row dict for non-Running activity types.

        Apple Watch reports VO2 max estimates for all workout types, so it is
        shown in the generic Overview tab regardless of the workout type.
        """
        from app_state import state
        from logic.records_by_type import RecordsByType

        original_workouts: Any = state.workouts
        original_records = state.records_by_type
        workouts_mock = MagicMock()
        workouts_mock._filter_workouts.return_value = pd.DataFrame(
            [
                {
                    "activityType": "Cycling",
                    "startDate": pd.Timestamp("2025-03-10"),
                    "duration": 3600.0,
                },
                {
                    "activityType": "Swimming",
                    "startDate": pd.Timestamp("2025-03-11"),
                    "duration": 1800.0,
                },
            ]
        )
        vo2_df = pd.DataFrame([{"startDate": "2025-03-10", "value": 52.0}])
        try:
            state.workouts = workouts_mock
            state.records_by_type = RecordsByType(data={"VO2Max": vo2_df})
            rows = wt._build_workout_rows()
        finally:
            state.workouts = original_workouts
            state.records_by_type = original_records
        assert len(rows) == 2
        # Every row should have a vo2_max entry regardless of activity type.
        for row in rows:
            assert "vo2_max" in row
            assert row["vo2_max"] != ""

    def test_routes_are_not_enriched_during_workout_row_building(self) -> None:
        """Workout row construction should keep route heart rate lazy until modal rendering."""
        from app_state import state
        from logic.records_by_type import RecordsByType
        from logic.workout_manager.workout_route import RoutePoint, WorkoutRoute

        original_workouts: Any = state.workouts
        original_records = state.records_by_type
        route = WorkoutRoute(
            points=[
                RoutePoint(
                    time=pd.Timestamp("2025-01-02 10:00:00+00:00").to_pydatetime(),
                    latitude=48.85,
                    longitude=2.35,
                    altitude=35.0,
                    speed=3.0,
                ),
                RoutePoint(
                    time=pd.Timestamp("2025-01-02 10:05:00+00:00").to_pydatetime(),
                    latitude=48.86,
                    longitude=2.36,
                    altitude=36.0,
                    speed=3.1,
                ),
            ]
        )
        workouts_mock = MagicMock()
        workouts_mock._filter_workouts.return_value = pd.DataFrame(
            [
                {
                    "activityType": "Running",
                    "startDate": pd.Timestamp("2025-01-02 10:00:00+00:00"),
                    "endDate": pd.Timestamp("2025-01-02 10:10:00+00:00"),
                    "duration": 600.0,
                    "route": route,
                }
            ]
        )
        heart_rate_df = pd.DataFrame(
            [
                {"startDate": "2025-01-02 10:00:10+00:00", "value": 141},
                {"startDate": "2025-01-02 10:04:50+00:00", "value": 149},
            ]
        )

        try:
            state.workouts = workouts_mock
            state.records_by_type = RecordsByType(data={"HeartRate": heart_rate_df})
            rows = wt._build_workout_rows()
        finally:
            state.workouts = original_workouts
            state.records_by_type = original_records

        assert rows[0]["route"].points[0].heart_rate is None
        assert rows[0]["route"].points[1].heart_rate is None

    def test_rows_preserve_utc_workout_bounds_for_lazy_heart_rate_matching(self) -> None:
        """Workout rows should keep UTC bounds so lazy modal enrichment can match samples."""
        from app_state import state
        from logic.records_by_type import RecordsByType
        from logic.workout_manager.workout_route import RoutePoint, WorkoutRoute

        original_workouts: Any = state.workouts
        original_records = state.records_by_type
        route = WorkoutRoute(
            points=[
                RoutePoint(
                    time=pd.Timestamp("2025-01-02 10:00:00+00:00").to_pydatetime(),
                    latitude=48.85,
                    longitude=2.35,
                    altitude=35.0,
                    speed=3.0,
                ),
                RoutePoint(
                    time=pd.Timestamp("2025-01-02 10:05:00+00:00").to_pydatetime(),
                    latitude=48.86,
                    longitude=2.36,
                    altitude=36.0,
                    speed=3.1,
                ),
            ]
        )
        workouts_mock = MagicMock()
        workouts_mock._filter_workouts.return_value = pd.DataFrame(
            [
                {
                    "activityType": "Running",
                    "startDate": pd.Timestamp("2025-01-02 11:00:00"),
                    "endDate": "2025-01-02 11:10:00 +0100",
                    "startDateUtc": pd.Timestamp("2025-01-02 10:00:00"),
                    "endDateUtc": pd.Timestamp("2025-01-02 10:10:00"),
                    "duration": 600.0,
                    "route": route,
                }
            ]
        )
        heart_rate_df = pd.DataFrame(
            [
                {"startDate": "2025-01-02 10:00:10+00:00", "value": 141},
                {"startDate": "2025-01-02 10:04:50+00:00", "value": 149},
            ]
        )

        try:
            state.workouts = workouts_mock
            state.records_by_type = RecordsByType(data={"HeartRate": heart_rate_df})
            rows = wt._build_workout_rows()
        finally:
            state.workouts = original_workouts
            state.records_by_type = original_records

        assert rows[0]["route"].points[0].heart_rate is None
        assert rows[0]["route"].points[1].heart_rate is None
        assert rows[0]["workout_start_utc"] == pd.Timestamp("2025-01-02 10:00:00")
        assert rows[0]["workout_end_utc"] == pd.Timestamp("2025-01-02 10:10:00")

    def test_missing_route_values_do_not_log_malformed_debug(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """NaN route placeholders should be left untouched without malformed-route logs."""
        from app_state import state
        from logic.records_by_type import RecordsByType

        original_workouts: Any = state.workouts
        original_records = state.records_by_type
        workouts_mock = MagicMock()
        workouts_mock._filter_workouts.return_value = pd.DataFrame(
            [
                {
                    "activityType": "Running",
                    "startDate": pd.Timestamp("2025-01-02 10:00:00+00:00"),
                    "endDate": pd.Timestamp("2025-01-02 10:10:00+00:00"),
                    "duration": 600.0,
                    "route": float("nan"),
                    "xmlFragment": '<Workout startDate="2025-01-02 11:00:00 +0100" />',
                }
            ]
        )
        heart_rate_df = pd.DataFrame(
            [
                {"startDate": "2025-01-02 10:00:10+00:00", "value": 141},
                {"startDate": "2025-01-02 10:04:50+00:00", "value": 149},
            ]
        )

        try:
            state.workouts = workouts_mock
            state.records_by_type = RecordsByType(data={"HeartRate": heart_rate_df})
            with caplog.at_level(logging.DEBUG, logger="ui.workout_table"):
                rows = wt._build_workout_rows()
        finally:
            state.workouts = original_workouts
            state.records_by_type = original_records

        assert len(rows) == 1
        assert pd.isna(rows[0]["route"])
        assert not any(
            "Skipping heart-rate route enrichment for malformed route" in record.message
            for record in caplog.records
        )

    def test_annotate_route_with_heart_rate_ignores_float_inputs(self) -> None:
        """Helper should return float/NaN route placeholders unchanged."""
        route = float("nan")
        heart_rate_samples = [
            (pd.Timestamp("2025-01-02 10:00:10+00:00").to_pydatetime(), 141.0),
        ]

        result = wt._annotate_route_with_heart_rate(route, heart_rate_samples)

        assert pd.isna(result)

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


class TestBuildWorkoutRowsImperial:
    """Tests for imperial unit rendering in _build_workout_rows()."""

    def _make_workouts_mock(self, rows: list[dict[str, Any]]) -> MagicMock:
        mock = MagicMock()
        mock._filter_workouts.return_value = pd.DataFrame(rows)
        return mock

    def test_elevation_displayed_in_feet_for_imperial(self) -> None:
        """Elevation column should show 'ft' when unit system is imperial."""
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
            with patch("ui.workout_table.rows.get_elevation_unit", return_value="ft"):
                rows = wt._build_workout_rows()
        finally:
            state.workouts = original_workouts

        assert len(rows) == 1
        expected_ft = int(round(100.0 * METERS_TO_FEET))
        assert rows[0]["elevation"] == f"{expected_ft} ft"

    def test_distance_displayed_in_miles_for_imperial(self) -> None:
        """Distance column should show 'mi' when unit system is imperial."""
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
            with patch("ui.workout_table.rows.get_distance_unit", return_value="mi"):
                rows = wt._build_workout_rows()
        finally:
            state.workouts = original_workouts

        assert len(rows) == 1
        expected_mi = f"{1609.344 * METERS_TO_MILES:.2f} mi"
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
