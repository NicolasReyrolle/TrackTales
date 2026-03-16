"""Test suite for missing coverage in WorkoutManager methods."""

from datetime import datetime

import pandas as pd
import pytest

import logic.workout_manager as wm


class TestGetDistanceByActivityUnits:
    """Test suite for get_distance_by_activity with different units."""

    def test_get_distance_by_activity_meters(self) -> None:
        """Test get_distance_by_activity with meters as unit."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Cycling"],
                    "distance": [5000, 10000],  # 5km and 10km
                }
            )
        )

        result = workouts.get_distance_by_activity(unit="m")

        assert result == {"Running": 5000, "Cycling": 10000}

    def test_get_distance_by_activity_miles(self) -> None:
        """Test get_distance_by_activity with miles as unit."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "distance": [1609.34],
                }
            )
        )

        result = workouts.get_distance_by_activity(unit="mi")

        assert result == {"Running": 1}

    def test_get_distance_by_activity_multiple_activities_meters(self) -> None:
        """Test multiple activities with meters unit."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Walking", "Cycling"],
                    "distance": [5000, 2000, 15000],
                }
            )
        )

        result = workouts.get_distance_by_activity(unit="m", combination_threshold=0)

        assert result == {"Running": 5000, "Walking": 2000, "Cycling": 15000}

    def test_get_distance_by_activity_with_grouping_meters(self) -> None:
        """Test get_distance_by_activity with grouping in meters."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Cycling", "Walking", "Yoga"],
                    "distance": [10000, 5000, 500, 200],
                }
            )
        )

        result = workouts.get_distance_by_activity(unit="m", combination_threshold=5.0)

        # Result should be in meters, with total ~ 15700m
        # Walking (500m, 3.18%) and Yoga (200m, 1.27%) are each below 5% threshold
        # So both should be grouped into "Others" = 700m
        assert result["Running"] == 10000
        assert result["Cycling"] == 5000
        assert result["Others"] == 700
        # Verify total is preserved
        assert sum(result.values()) == 15700

    def test_get_distance_by_activity_invalid_unit(self) -> None:
        """Test get_distance_by_activity with invalid unit raises error."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "distance": [5000],
                }
            )
        )

        with pytest.raises(ValueError, match="Unsupported unit"):
            workouts.get_distance_by_activity(unit="yards")

    def test_get_distance_by_activity_miles_with_grouping(self) -> None:
        """Test distance by activity in miles with grouping."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Cycling", "Walking"],
                    "distance": [8046.7, 4023.35, 1609.34],  # 5mi, 2.5mi, 1mi
                }
            )
        )

        result = workouts.get_distance_by_activity(unit="mi", combination_threshold=0)

        assert result["Running"] == 5
        assert result["Cycling"] == 2
        assert result["Walking"] == 1


class TestCountByActivityMissingColumn:
    """Test suite for get_count_by_activity with missing columns."""

    def test_get_count_by_activity_missing_activity_type_column(self) -> None:
        """Test get_count_by_activity when activityType column is missing."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "duration": [3600, 3600, 3600],
                }
            )
        )

        result = workouts.get_count_by_activity()

        assert result == {}

    def test_get_count_by_activity_empty_dataframe(self) -> None:
        """Test get_count_by_activity with empty DataFrame."""
        workouts = wm.WorkoutManager(pd.DataFrame())

        result = workouts.get_count_by_activity()

        assert result == {}


class TestAggregateByPeriodInternalBranches:
    """Tests for internal _aggregate_by_period edge branches."""

    def test_aggregate_by_period_returns_empty_when_filtered_workouts_are_empty(self) -> None:
        """Date filters that remove all workouts should return an empty dictionary."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "startDate": [pd.Timestamp("2024-01-01")],
                    "duration": [3600],
                }
            )
        )

        result = workouts._aggregate_by_period(  # pylint: disable=protected-access  # type: ignore[attr-defined]
            column="duration",
            period="M",
            aggregation=lambda grouped: grouped.sum(),
            transformation=lambda s: s,
            start_date=datetime(2030, 1, 1),
            end_date=datetime(2030, 1, 31),
        )

        assert result == {}

    def test_aggregate_by_period_returns_empty_when_aggregation_result_is_empty(self) -> None:
        """Empty aggregation output should return an empty dictionary."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "startDate": [pd.Timestamp("2024-01-01")],
                    "duration": [3600],
                }
            )
        )

        result = workouts._aggregate_by_period(  # pylint: disable=protected-access  # type: ignore[attr-defined]
            column="duration",
            period="M",
            aggregation=lambda _grouped: pd.Series(dtype=float),
            transformation=lambda s: s,
        )

        assert result == {}

    def test_aggregate_by_period_returns_empty_when_filtering_hook_returns_empty(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Force the post-filter empty branch to execute deterministically."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "startDate": [pd.Timestamp("2024-01-01")],
                    "duration": [3600],
                }
            )
        )

        def _empty_filter(*_args: object, **_kwargs: object) -> pd.DataFrame:
            return pd.DataFrame(
                {
                    "activityType": pd.Series(dtype="object"),
                    "startDate": pd.Series(dtype="datetime64[ns]"),
                    "duration": pd.Series(dtype="int64"),
                }
            )

        monkeypatch.setattr(workouts, "_filter_workouts", _empty_filter)

        result = workouts._aggregate_by_period(  # pylint: disable=protected-access  # type: ignore[attr-defined]
            column="duration",
            period="M",
            aggregation=lambda grouped: grouped.sum(),
            transformation=lambda s: s,
        )

        assert result == {}


class TestDistanceByActivityEdgeCases:
    """Test suite for edge cases in get_distance_by_activity."""

    def test_get_distance_by_activity_zero_distance_entries(self) -> None:
        """Test get_distance_by_activity with zero distance entries."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Walking"],
                    "distance": [5000, 0],
                }
            )
        )

        result = workouts.get_distance_by_activity()

        # Walking with 0 distance might be filtered or shown
        assert "Running" in result
        assert result["Running"] == 5

    def test_get_distance_by_activity_rounding_consistency(self) -> None:
        """Test that rounding is consistent across different values."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Activity1", "Activity2", "Activity3"],
                    "distance": [1500, 2500, 3000],  # 1.5km, 2.5km, 3km
                }
            )
        )

        result = workouts.get_distance_by_activity(combination_threshold=0)

        # 1.5 rounds to 2, 2.5 rounds to 2 (banker's rounding in modern Python)
        assert result["Activity1"] in [1, 2]
        assert result["Activity2"] in [2, 3]
        assert result["Activity3"] == 3


class TestConvertDistance:
    """Test suite for convert_distance utility."""

    def test_convert_distance_km(self) -> None:
        """Meters should convert to kilometers using the expected divisor."""
        workouts = wm.WorkoutManager(pd.DataFrame())

        result = workouts.convert_distance("km", 2500)

        assert result == pytest.approx(2.5)  # type: ignore[misc]

    def test_get_distance_by_activity_very_small_distances(self) -> None:
        """Test get_distance_by_activity with very small distances."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Walking"],
                    "distance": [100, 50],  # 0.1km and 0.05km
                }
            )
        )

        result = workouts.get_distance_by_activity()

        # Both should round to 0 and be filtered
        assert result == {}

    def test_get_distance_by_activity_float_activity_types(self) -> None:
        """Test get_distance_by_activity preserves activity type names."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["High Intensity Running", "Easy Walking", "Mountain Cycling"],
                    "distance": [5000, 3000, 10000],
                }
            )
        )

        result = workouts.get_distance_by_activity(combination_threshold=0)

        assert "High Intensity Running" in result
        assert "Easy Walking" in result
        assert "Mountain Cycling" in result


class TestElevationByActivityEdgeCases:
    """Test suite for edge cases in get_elevation_by_activity."""

    def test_get_elevation_by_activity_all_values_below_threshold(self) -> None:
        """Test elevation by activity when all values are below threshold."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Walk1", "Walk2", "Walk3"],
                    "ElevationAscended": [100, 150, 200],
                }
            )
        )

        result = workouts.get_elevation_by_activity(combination_threshold=50.0, unit="km")

        # Total = 450m → 0.45km, threshold_value = 0.45 * 0.5 = 0.225km
        # Values after div(1000): Walk1(0.1), Walk2(0.15), Walk3(0.2)
        # Walk1(0.1) cumulative=0.1 <= 0.225 → grouped to Others
        # Walk2(0.15) cumulative=0.25 > 0.225 → stays separate
        # Walk3(0.2) stays separate
        # After rounding: all values round to 0 (filter_zeros=False so they remain)
        assert result == {"Walk2": 0, "Walk3": 0, "Others": 0}
        # Total is preserved (all round to 0)
        assert sum(result.values()) == 0


class TestCaloriesByActivityEdgeCases:
    """Test suite for edge cases in get_calories_by_activity."""

    def test_get_calories_by_activity_missing_column(self) -> None:
        """Test calories by activity when sumActiveEnergyBurned column is missing."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Cycling"],
                    "distance": [5000, 10000],
                }
            )
        )

        result = workouts.get_calories_by_activity()

        assert result == {}

    def test_get_calories_by_activity_fractional_calories(self) -> None:
        """Test calories by activity with fractional calorie values."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "sumActiveEnergyBurned": [250.5],
                }
            )
        )

        result = workouts.get_calories_by_activity(combination_threshold=0)

        # 250.5 should round to 250 or 251
        assert result["Running"] in [250, 251]


class TestDurationByActivityEdgeCases:
    """Test suite for edge cases in get_duration_by_activity."""

    def test_get_duration_by_activity_sub_hour_durations(self) -> None:
        """Test duration by activity with durations less than 1 hour."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Yoga", "Walking", "Running"],
                    "duration": [900, 1200, 3600],  # 15min, 20min, 1hr
                }
            )
        )

        result = workouts.get_duration_by_activity()

        # Yoga (0.25h) and Walking (0.33h) both round to 0 and are filtered
        # Only Running (1h -> 1) remains
        assert result == {"Running": 1}

    def test_get_duration_by_activity_fractional_hours(self) -> None:
        """Test duration by activity with various fractional hours."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Cycling", "Walking"],
                    "duration": [5400, 7200, 1800],  # 1.5h, 2h, 0.5h
                }
            )
        )

        result = workouts.get_duration_by_activity()

        # Total = 4h, threshold = 0.4h
        # Sorted: Walking(0.5h), Running(1.5h), Cycling(2.0h)
        # Walking(0.5h) cumulative=0.5 > 0.4 → stays separate
        # After rounding: Walking rounds to 0 and is filtered, Running→2, Cycling→2
        assert result == {"Running": 2, "Cycling": 2}
        # Walking is not present because round(0.5) = 0 and zeros are filtered

    def test_get_duration_by_activity_boundary_cases(self) -> None:
        """Test duration by activity at rounding boundaries."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Activity1", "Activity2", "Activity3"],
                    "duration": [1800, 5400, 3600],  # 0.5h, 1.5h, 1h
                }
            )
        )

        result = workouts.get_duration_by_activity(combination_threshold=0)

        # 0.5h might round to 0 or 1
        # 1.5h should round to 2
        # 1h should be 1
        assert result.get("Activity3") == 1


class TestGroupSmallValuesEdgeCases:
    """Additional edge cases for group_small_values method."""

    def test_group_small_values_negative_threshold(self) -> None:
        """Test group_small_values with negative threshold."""
        manager = wm.WorkoutManager()
        data = {"A": 100, "B": 50, "C": 10}

        result = manager.group_small_values(data, threshold_percent=-5.0)

        # Negative threshold should behave like 0 (no grouping)
        assert all(key in result for key in ["A", "B", "C"])

    def test_group_small_values_over_100_threshold(self) -> None:
        """Test group_small_values with threshold over 100%."""
        manager = wm.WorkoutManager()
        data = {"A": 100, "B": 50, "C": 10}

        result = manager.group_small_values(data, threshold_percent=150.0)

        # Over 100% threshold - all values might group as "Others"
        assert isinstance(result, dict)
        assert sum(result.values()) == sum(data.values())  # Total preserved

    def test_group_small_values_identical_values(self) -> None:
        """Test group_small_values with all identical values."""
        manager = wm.WorkoutManager()
        data = {"A": 50, "B": 50, "C": 50, "D": 50}

        result = manager.group_small_values(data, threshold_percent=10.0)

        # Total = 200, threshold = 20
        # Each value is 50 > 20, so no value is small enough to be grouped
        # All values remain separate
        assert len(result) == 4
        assert "Others" not in result

    def test_group_small_values_single_very_small_value(self) -> None:
        """Test group_small_values with one very small and others large."""
        manager = wm.WorkoutManager()
        data = {"Large1": 1000, "Large2": 500, "Small": 1}

        result = manager.group_small_values(data, threshold_percent=10.0)

        # Total = 1501, threshold = 150.1
        # Small (1) << 150.1, so it should be in "Others" or small group
        assert "Large1" in result
        assert "Large2" in result


class TestGetDateBounds:
    """Test suite for WorkoutManager.get_date_bounds method."""

    def test_get_date_bounds_default_when_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test default bounds when no workouts are loaded."""

        class _FixedDatetime(datetime):
            @classmethod
            def now(cls, tz=None) -> datetime:  # type: ignore[override]
                return cls(2024, 1, 2)

        monkeypatch.setattr(wm, "datetime", _FixedDatetime)

        manager = wm.WorkoutManager()

        assert manager.get_date_bounds() == ("2000/01/01", "2024/01/02")

    def test_get_date_bounds_default_when_missing_start_date(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test default bounds when startDate column is missing."""

        class _FixedDatetime(datetime):
            @classmethod
            def now(cls, tz=None) -> datetime:  # type: ignore[override]
                return cls(2024, 1, 2)

        monkeypatch.setattr(wm, "datetime", _FixedDatetime)

        manager = wm.WorkoutManager(pd.DataFrame({"activityType": ["Running"]}))

        assert manager.get_date_bounds() == ("2000/01/01", "2024/01/02")

    def test_get_date_bounds_with_dates(self) -> None:
        """Test min/max bounds with valid startDate values."""
        manager = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Cycling", "Swimming"],
                    "startDate": pd.to_datetime(["2024-03-15", "2024-01-01", "2024-02-10"]),
                }
            )
        )

        assert manager.get_date_bounds() == ("2024/01/01", "2024/03/15")
