"""Tests for sport-specific field extraction helpers in ui.workout_table."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pandas as pd
import pytest

from app_state import state
from ui import workout_table as wt


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
        result = wt._extract_running_fields(row)
        assert result["pace"] == "6:00 /km"

    def test_cadence_formatted(self) -> None:
        """Cadence should show 'spm' unit."""
        row = self._make_row(averageRunningCadence=178.0)
        result = wt._extract_running_fields(row)
        assert result["cadence"] == "178 spm"

    def test_stride_length_formatted(self) -> None:
        """Stride length should show 'm' unit to 2 decimal places."""
        row = self._make_row(averageRunningStrideLength=0.91)
        result = wt._extract_running_fields(row)
        assert result["stride_length"] == "0.91 m"

    def test_vertical_oscillation_formatted(self) -> None:
        """Vertical oscillation should show 'cm' unit."""
        row = self._make_row(averageRunningVerticalOscillation=8.8)
        result = wt._extract_running_fields(row)
        assert result["vertical_oscillation"] == "8.8 cm"

    def test_ground_contact_time_formatted(self) -> None:
        """Ground contact time should show 'ms' unit."""
        row = self._make_row(averageRunningGroundContactTime=304.0)
        result = wt._extract_running_fields(row)
        assert result["ground_contact_time"] == "304 ms"

    def test_step_count_formatted(self) -> None:
        """Step count should be an integer string."""
        row = self._make_row(sumStepCount=9787.0)
        result = wt._extract_running_fields(row)
        assert result["step_count"] == "9787"

    def test_missing_speed_produces_dash(self) -> None:
        """Missing averageRunningSpeed should produce '–' for pace."""
        row = self._make_row()
        del row["averageRunningSpeed"]
        result = wt._extract_running_fields(row)
        assert result["pace"] == "–"

    def test_pace_formatted_in_imperial_mode(self) -> None:
        """Pace should be formatted as '/mi' when distance_unit is 'mi'."""
        row = self._make_row(averageRunningSpeed=10.0)
        result = wt._extract_running_fields(row, distance_unit="mi")
        assert result["pace"].endswith("/mi")
        assert "km" not in result["pace"]

    def test_distance_unit_stored_in_result(self) -> None:
        """The distance_unit used for splits and pace should be stored in the result dict."""
        row = self._make_row()
        result_km = wt._extract_row_data(row, 0, "en", distance_unit="km")
        result_mi = wt._extract_row_data(row, 0, "en", distance_unit="mi")
        assert result_km["distance_unit"] == "km"
        assert result_mi["distance_unit"] == "mi"

    def test_route_stored_for_lazy_splits_when_no_route(self) -> None:
        """When no route is present the 'route' key should be None (lazy splits return [])."""
        row = self._make_row()
        result = wt._extract_row_data(row, 0, "en")
        assert result["route"] is None
        assert "splits" not in result

    def test_route_stored_for_lazy_splits_from_route(self) -> None:
        """When a WorkoutRoute is present it should be stored in 'route' for lazy computation."""
        from datetime import timedelta

        from logic.workout_manager.workout_route import RoutePoint, WorkoutRoute

        start = pd.Timestamp("2024-01-01 10:00:00")
        base_time = start.to_pydatetime().replace(tzinfo=None)
        # 3 m/s × 1001 seconds ≈ 3003 m → ≥ 3 complete 1 km splits when computed lazily
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
        result = wt._extract_row_data(row, 0, "en")
        # Route stored for lazy computation; no pre-computed splits key.
        assert result["route"] is route
        assert "splits" not in result

    def test_route_stored_for_lazy_splits_from_merged_route(self) -> None:
        """A pre-merged route (simulating ExportParser output) should be stored for lazy splits.

        ExportParser always stores the fully de-duplicated merged route in ``row['route']``
        whenever ``route_parts`` are accumulated.  This test verifies the route reference
        is preserved so the modal can compute splits correctly.
        """
        from datetime import timedelta

        from logic.workout_manager.workout_route import RoutePoint, WorkoutRoute

        base_time = pd.Timestamp("2024-01-01 10:00:00").to_pydatetime().replace(tzinfo=None)

        # Simulate a merged route built from two segments of ~1500 m each.
        merged_points = [
            RoutePoint(
                time=base_time + timedelta(seconds=i),
                latitude=0.0,
                longitude=0.0,
                altitude=0.0,
                speed=3.0,
            )
            for i in range(1002)  # 1001 intervals × 3 m/s = 3003 m
        ]
        merged_route = WorkoutRoute(points=merged_points)
        row = self._make_row(route=merged_route, distance=3000.0)
        result = wt._extract_row_data(row, 0, "en")
        # Route reference stored; no eager split computation.
        assert result["route"] is merged_route
        assert "splits" not in result

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
        # Route is stored for lazy splits; no eager 'splits' key produced at table-build time.
        assert "route" in row

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
        # 'route' is always present in the base result; it is None when there is no GPS data.
        assert row["route"] is None


class TestExtractWalkingFields:
    """Unit tests for _extract_walking_fields()."""

    def _make_row(self, **kwargs: Any) -> dict[str, Any]:
        """Build a minimal row dict with walking statistics."""
        base: dict[str, Any] = {
            "activityType": "Walking",
            "averageWalkingSpeed": 5.0,  # 5 km/h → 12:00 /km
            "averageWalkingCadence": 110.0,
            "averageWalkingStepLength": 0.72,
            "sumStepCount": 6500.0,
        }
        base.update(kwargs)
        return base

    def test_pace_derived_from_walking_speed(self) -> None:
        """Pace should be derived from averageWalkingSpeed."""
        row = self._make_row(averageWalkingSpeed=5.0)
        result = wt._extract_walking_fields(row)
        assert result["pace"] == "12:00 /km"

    def test_cadence_formatted(self) -> None:
        """Cadence should show 'spm' unit."""
        row = self._make_row(averageWalkingCadence=110.0)
        result = wt._extract_walking_fields(row)
        assert result["cadence"] == "110 spm"

    def test_step_length_formatted(self) -> None:
        """Step length should show 'm' unit to 2 decimal places."""
        row = self._make_row(averageWalkingStepLength=0.72)
        result = wt._extract_walking_fields(row)
        assert result["step_length"] == "0.72 m"

    def test_step_count_formatted(self) -> None:
        """Step count should be an integer string."""
        row = self._make_row(sumStepCount=6500.0)
        result = wt._extract_walking_fields(row)
        assert result["step_count"] == "6500"

    def test_missing_speed_produces_dash(self) -> None:
        """Missing averageWalkingSpeed should produce '–' for pace."""
        row = self._make_row()
        del row["averageWalkingSpeed"]
        result = wt._extract_walking_fields(row)
        assert result["pace"] == "–"

    def test_pace_formatted_in_imperial_mode(self) -> None:
        """Pace should be formatted as '/mi' when distance_unit is 'mi'."""
        row = self._make_row(averageWalkingSpeed=5.0)
        result = wt._extract_walking_fields(row, distance_unit="mi")
        assert result["pace"].endswith("/mi")
        assert "km" not in result["pace"]

    def test_distance_unit_stored_in_result(self) -> None:
        """The distance_unit used for pace should be stored in the result dict."""
        row = self._make_row()
        result_km = wt._extract_row_data(row, 0, "en", distance_unit="km")
        result_mi = wt._extract_row_data(row, 0, "en", distance_unit="mi")
        assert result_km["distance_unit"] == "km"
        assert result_mi["distance_unit"] == "mi"

    def test_route_stored_for_lazy_splits_when_no_route(self) -> None:
        """When no route is present the 'route' key should be None."""
        row = self._make_row()
        result = wt._extract_row_data(row, 0, "en")
        assert result["route"] is None
        assert "splits" not in result

    def test_walking_fields_included_for_walking_workouts(self) -> None:
        """Walking-specific keys should be present in the row dict for Walking workouts."""
        original_workouts: Any = state.workouts
        workouts_mock = MagicMock()
        workouts_mock._filter_workouts.return_value = pd.DataFrame(
            [
                {
                    "activityType": "Walking",
                    "startDate": pd.Timestamp("2025-09-16"),
                    "duration": 1800.0,
                    "averageWalkingSpeed": 5.0,
                    "averageWalkingCadence": 110.0,
                    "sumStepCount": 6500.0,
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
        assert row["pace"] == "12:00 /km"
        assert row["cadence"] == "110 spm"
        assert row["step_count"] == "6500"
        assert "route" in row

    def test_walking_fields_absent_for_non_walking_workouts(self) -> None:
        """Non-Walking workouts should not have walking-specific keys."""
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
        assert "step_length" not in row
        assert "step_count" not in row


class TestExtractHikingFields:
    """Unit tests for _extract_hiking_fields()."""

    def _make_row(self, **kwargs: Any) -> dict[str, Any]:
        """Build a minimal row dict with hiking statistics."""
        base: dict[str, Any] = {
            "activityType": "Hiking",
            "averageWalkingSpeed": 4.0,  # 4 km/h → 15:00 /km
            "averageWalkingCadence": 95.0,
            "averageWalkingStepLength": 0.65,
            "sumStepCount": 8000.0,
        }
        base.update(kwargs)
        return base

    def test_pace_derived_from_walking_speed(self) -> None:
        """Pace should be derived from averageWalkingSpeed (same metric as walking)."""
        row = self._make_row(averageWalkingSpeed=4.0)
        result = wt._extract_hiking_fields(row)
        assert result["pace"] == "15:00 /km"

    def test_cadence_formatted(self) -> None:
        """Cadence should show 'spm' unit."""
        row = self._make_row(averageWalkingCadence=95.0)
        result = wt._extract_hiking_fields(row)
        assert result["cadence"] == "95 spm"

    def test_step_length_formatted(self) -> None:
        """Step length should show 'm' unit to 2 decimal places."""
        row = self._make_row(averageWalkingStepLength=0.65)
        result = wt._extract_hiking_fields(row)
        assert result["step_length"] == "0.65 m"

    def test_step_count_formatted(self) -> None:
        """Step count should be an integer string."""
        row = self._make_row(sumStepCount=8000.0)
        result = wt._extract_hiking_fields(row)
        assert result["step_count"] == "8000"

    def test_missing_speed_produces_dash(self) -> None:
        """Missing averageWalkingSpeed should produce '–' for pace."""
        row = self._make_row()
        del row["averageWalkingSpeed"]
        result = wt._extract_hiking_fields(row)
        assert result["pace"] == "–"

    def test_pace_formatted_in_imperial_mode(self) -> None:
        """Pace should be formatted as '/mi' when distance_unit is 'mi'."""
        row = self._make_row(averageWalkingSpeed=4.0)
        result = wt._extract_hiking_fields(row, distance_unit="mi")
        assert result["pace"].endswith("/mi")
        assert "km" not in result["pace"]

    def test_hiking_fields_included_for_hiking_workouts(self) -> None:
        """Hiking-specific keys should be present in the row dict for Hiking workouts."""
        original_workouts: Any = state.workouts
        workouts_mock = MagicMock()
        workouts_mock._filter_workouts.return_value = pd.DataFrame(
            [
                {
                    "activityType": "Hiking",
                    "startDate": pd.Timestamp("2025-09-16"),
                    "duration": 7200.0,
                    "averageWalkingSpeed": 4.0,
                    "averageWalkingCadence": 95.0,
                    "sumStepCount": 8000.0,
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
        assert row["pace"] == "15:00 /km"
        assert row["cadence"] == "95 spm"
        assert row["step_count"] == "8000"
        assert "route" in row

    def test_hiking_fields_absent_for_non_hiking_workouts(self) -> None:
        """Non-Hiking workouts should not have hiking-specific keys."""
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
        assert "step_count" not in row
        assert "pace" not in row


class TestExtractWeatherFields:
    """Unit tests for temperature and humidity extraction in _extract_row_data()."""

    def _make_row(self, **kwargs: Any) -> dict[str, Any]:
        """Build a minimal workout row with weather data."""
        base: dict[str, Any] = {
            "activityType": "Walking",
            "startDate": pd.Timestamp("2025-01-01"),
            "duration": 1000.0,
            "WeatherTemperature": 22.222,  # stored in °C (≈72 °F before parser conversion)
            "WeatherHumidity": 80.0,  # 80 % (already divided by 100 by parser)
        }
        base.update(kwargs)
        return base

    def test_temperature_displayed_in_celsius_for_metric(self) -> None:
        """Temperature should show °C when unit system is metric."""
        row = self._make_row()
        result = wt._extract_row_data(row, 0, "en", temperature_unit="°C")
        assert result["temperature"] == "22.2 °C"

    def test_temperature_displayed_in_fahrenheit_for_imperial(self) -> None:
        """Temperature should be converted back to °F for imperial unit system."""
        row = self._make_row(WeatherTemperature=0.0)  # 0 °C = 32 °F
        result = wt._extract_row_data(row, 0, "en", temperature_unit="°F")
        assert result["temperature"] == "32.0 °F"

    def test_temperature_conversion_accuracy(self) -> None:
        """22.222 °C should convert to approximately 72.0 °F."""
        row = self._make_row(WeatherTemperature=22.222)
        result = wt._extract_row_data(row, 0, "en", temperature_unit="°F")
        # 22.222 * 9/5 + 32 = 71.9996 ≈ 72.0 °F
        assert result["temperature"] == "72.0 °F"

    def test_missing_temperature_produces_dash(self) -> None:
        """Missing WeatherTemperature should produce '–'."""
        row = self._make_row()
        del row["WeatherTemperature"]
        result = wt._extract_row_data(row, 0, "en", temperature_unit="°C")
        assert result["temperature"] == "–"

    def test_humidity_displayed_as_integer_percentage(self) -> None:
        """Humidity should show as an integer percentage string."""
        row = self._make_row(WeatherHumidity=80.0)
        result = wt._extract_row_data(row, 0, "en")
        assert result["humidity"] == "80 %"

    def test_humidity_rounds_to_nearest_integer(self) -> None:
        """Fractional humidity should be rounded to nearest integer."""
        row = self._make_row(WeatherHumidity=65.6)
        result = wt._extract_row_data(row, 0, "en")
        assert result["humidity"] == "66 %"

    def test_missing_humidity_produces_dash(self) -> None:
        """Missing WeatherHumidity should produce '–'."""
        row = self._make_row()
        del row["WeatherHumidity"]
        result = wt._extract_row_data(row, 0, "en")
        assert result["humidity"] == "–"

    def test_weather_fields_in_build_workout_rows(self) -> None:
        """Weather fields should be present in rows built by _build_workout_rows()."""
        original_workouts: Any = state.workouts
        workouts_mock = MagicMock()
        workouts_mock._filter_workouts.return_value = pd.DataFrame(
            [
                {
                    "activityType": "Walking",
                    "startDate": pd.Timestamp("2025-01-01"),
                    "duration": 1000.0,
                    "WeatherTemperature": 22.222,
                    "WeatherHumidity": 80.0,
                }
            ]
        )
        try:
            state.workouts = workouts_mock
            rows = wt._build_workout_rows()
        finally:
            state.workouts = original_workouts
        assert len(rows) == 1
        assert rows[0]["temperature"] == "22.2 °C"
        assert rows[0]["humidity"] == "80 %"

    def test_weather_fields_missing_when_absent_from_workout(self) -> None:
        """Workouts without weather metadata should show '–' for temperature and humidity."""
        original_workouts: Any = state.workouts
        workouts_mock = MagicMock()
        workouts_mock._filter_workouts.return_value = pd.DataFrame(
            [
                {
                    "activityType": "Running",
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
        assert rows[0]["temperature"] == "–"
        assert rows[0]["humidity"] == "–"


# ---------------------------------------------------------------------------
# Swimming-specific field extraction
# ---------------------------------------------------------------------------


class TestExtractSwimmingFields:
    """Unit tests for _extract_swimming_fields() in workout_table."""

    def _make_row(self, **kwargs: Any) -> dict[str, Any]:
        """Build a minimal swimming row dict."""
        base: dict[str, Any] = {
            "activityType": "Swimming",
            "SwimmingLocationType": 1,  # Pool
            "LapLength": 25.0,
            "sumSwimmingStrokeCount": 200.0,
            "swimming_events": [],
        }
        base.update(kwargs)
        return base

    def test_pool_location_returns_translated_label(self) -> None:
        """SwimmingLocationType=1 (Pool) should produce the translated Pool label."""
        row = self._make_row(SwimmingLocationType=1)
        result = wt._extract_swimming_fields(pd.Series(row))
        # In English (default) t("Pool") == "Pool"
        assert result["swimming_location"] == "Pool"

    def test_open_water_location_returns_translated_label(self) -> None:
        """SwimmingLocationType=2 (Open Water) should produce the translated label."""
        row = self._make_row(SwimmingLocationType=2)
        result = wt._extract_swimming_fields(pd.Series(row))
        assert result["swimming_location"] == "Open Water"

    def test_missing_location_type_produces_dash(self) -> None:
        """Absent SwimmingLocationType → '–'."""
        row = self._make_row()
        del row["SwimmingLocationType"]
        result = wt._extract_swimming_fields(pd.Series(row))
        assert result["swimming_location"] == "–"

    def test_unknown_location_type_returns_raw_value(self) -> None:
        """An unrecognised integer code should fall back to the raw string value."""
        row = self._make_row(SwimmingLocationType=99)
        result = wt._extract_swimming_fields(pd.Series(row))
        # SWIMMING_LOCATION_TYPES.get(99, "99") → "99", then t("99") == "99"
        assert result["swimming_location"] == "99"

    def test_lap_length_formatted_in_metres(self) -> None:
        """LapLength (in metres) should be formatted as '<N> m'."""
        row = self._make_row(LapLength=50.0)
        result = wt._extract_swimming_fields(pd.Series(row))
        assert result["swimming_lap_length"] == "50 m"
        assert result["lap_length_m"] == pytest.approx(50.0)  # type: ignore[arg-type]

    def test_missing_lap_length_produces_dash(self) -> None:
        """Absent or zero LapLength → '–'."""
        row = self._make_row()
        del row["LapLength"]
        result = wt._extract_swimming_fields(pd.Series(row))
        assert result["swimming_lap_length"] == "–"
        assert result["lap_length_m"] == pytest.approx(0.0)  # type: ignore[arg-type]

    def test_stroke_count_formatted_as_integer(self) -> None:
        """sumSwimmingStrokeCount should be formatted as a rounded integer string."""
        row = self._make_row(sumSwimmingStrokeCount=199.7)
        result = wt._extract_swimming_fields(pd.Series(row))
        assert result["swimming_stroke_count"] == "200"

    def test_missing_stroke_count_produces_dash(self) -> None:
        """Absent sumSwimmingStrokeCount → '–'."""
        row = self._make_row()
        del row["sumSwimmingStrokeCount"]
        result = wt._extract_swimming_fields(pd.Series(row))
        assert result["swimming_stroke_count"] == "–"

    def test_swimming_events_passed_through_as_list(self) -> None:
        """swimming_events list should be preserved verbatim in the result."""
        events = [{"type": "Lap", "duration_s": 60.0}]
        row = self._make_row(swimming_events=events)
        result = wt._extract_swimming_fields(pd.Series(row))
        assert result["swimming_events"] == events

    def test_nan_swimming_events_treated_as_empty_list(self) -> None:
        """NaN in swimming_events (pandas default for missing objects) → empty list."""
        row = self._make_row(swimming_events=float("nan"))
        result = wt._extract_swimming_fields(pd.Series(row))
        assert result["swimming_events"] == []
        assert isinstance(result["swimming_events"], list)


# ---------------------------------------------------------------------------
# Cycling-specific field extraction
# ---------------------------------------------------------------------------


class TestExtractCyclingFields:
    """Unit tests for _extract_cycling_fields() in workout_table."""

    def _make_row(self, **kwargs: Any) -> dict[str, Any]:
        """Build a minimal cycling row dict with cycling statistics."""
        base: dict[str, Any] = {
            "activityType": "Cycling",
            "averageCyclingSpeed": 25.0,  # km/h
            "averageCyclingCadence": 85.0,
            "averageCyclingPower": 200.0,
            "averageCyclingFunctionalThresholdPower": 250.0,
        }
        base.update(kwargs)
        return base

    def test_speed_formatted_in_km_h(self) -> None:
        """Speed should be formatted in km/h for metric unit system."""
        row = self._make_row(averageCyclingSpeed=25.0)
        result = wt._extract_cycling_fields(row)
        assert result["cycling_speed"] == "25.0 km/h"

    def test_speed_formatted_in_mph(self) -> None:
        """Speed should be converted to mph for imperial unit system."""
        row = self._make_row(averageCyclingSpeed=25.0)
        result = wt._extract_cycling_fields(row, distance_unit="mi")
        assert "mph" in result["cycling_speed"]
        assert "km/h" not in result["cycling_speed"]

    def test_missing_speed_produces_dash(self) -> None:
        """Missing averageCyclingSpeed should produce '–'."""
        row = self._make_row()
        del row["averageCyclingSpeed"]
        result = wt._extract_cycling_fields(row)
        assert result["cycling_speed"] == "–"

    def test_zero_speed_produces_dash(self) -> None:
        """Zero averageCyclingSpeed should produce '–' (treated as absent)."""
        row = self._make_row(averageCyclingSpeed=0.0)
        result = wt._extract_cycling_fields(row)
        assert result["cycling_speed"] == "–"

    def test_negative_speed_produces_dash(self) -> None:
        """Negative averageCyclingSpeed should produce '–' (invalid value)."""
        row = self._make_row(averageCyclingSpeed=-5.0)
        result = wt._extract_cycling_fields(row)
        assert result["cycling_speed"] == "–"

    def test_cadence_formatted_in_rpm(self) -> None:
        """Cadence should show 'rpm' unit."""
        row = self._make_row(averageCyclingCadence=85.0)
        result = wt._extract_cycling_fields(row)
        assert result["cycling_cadence"] == "85 rpm"

    def test_missing_cadence_produces_dash(self) -> None:
        """Missing averageCyclingCadence should produce '–'."""
        row = self._make_row()
        del row["averageCyclingCadence"]
        result = wt._extract_cycling_fields(row)
        assert result["cycling_cadence"] == "–"

    def test_power_formatted_in_watts(self) -> None:
        """Power should show 'W' unit."""
        row = self._make_row(averageCyclingPower=200.0)
        result = wt._extract_cycling_fields(row)
        assert result["cycling_power"] == "200 W"

    def test_missing_power_produces_dash(self) -> None:
        """Missing averageCyclingPower should produce '–'."""
        row = self._make_row()
        del row["averageCyclingPower"]
        result = wt._extract_cycling_fields(row)
        assert result["cycling_power"] == "–"

    def test_ftp_formatted_in_watts(self) -> None:
        """Functional threshold power should show 'W' unit."""
        row = self._make_row(averageCyclingFunctionalThresholdPower=250.0)
        result = wt._extract_cycling_fields(row)
        assert result["cycling_ftp"] == "250 W"

    def test_missing_ftp_produces_dash(self) -> None:
        """Missing averageCyclingFunctionalThresholdPower should produce '–'."""
        row = self._make_row()
        del row["averageCyclingFunctionalThresholdPower"]
        result = wt._extract_cycling_fields(row)
        assert result["cycling_ftp"] == "–"

    def test_cycling_fields_included_for_cycling_workouts(self) -> None:
        """Cycling-specific keys should be present in the row dict for Cycling workouts."""
        original_workouts: Any = state.workouts
        workouts_mock = MagicMock()
        workouts_mock._filter_workouts.return_value = pd.DataFrame(
            [
                {
                    "activityType": "Cycling",
                    "startDate": pd.Timestamp("2025-07-14"),
                    "duration": 4354.0,
                    "averageCyclingSpeed": 25.0,
                    "averageCyclingCadence": 85.0,
                    "averageCyclingPower": 200.0,
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
        assert row["cycling_speed"] == "25.0 km/h"
        assert row["cycling_cadence"] == "85 rpm"
        assert row["cycling_power"] == "200 W"
        assert "route" in row

    def test_cycling_fields_absent_for_non_cycling_workouts(self) -> None:
        """Non-Cycling workouts should not have cycling-specific keys."""
        original_workouts: Any = state.workouts
        workouts_mock = MagicMock()
        workouts_mock._filter_workouts.return_value = pd.DataFrame(
            [
                {
                    "activityType": "Running",
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
        assert "cycling_speed" not in row
        assert "cycling_cadence" not in row
