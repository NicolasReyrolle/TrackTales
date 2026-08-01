"""Tests for WorkoutManager seasonal pattern aggregation methods."""

from typing import Any

import pandas as pd
import pytest

from logic.workout_manager import WorkoutManager

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

_DAY_OF_WEEK_LABELS = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]
_MONTH_OF_YEAR_LABELS = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]
_QUARTER_OF_YEAR_LABELS = ["Q1", "Q2", "Q3", "Q4"]


def _make_manager(**kwargs: Any) -> WorkoutManager:
    """Build a WorkoutManager from keyword column lists."""
    return WorkoutManager(pd.DataFrame(kwargs))


# ---------------------------------------------------------------------------
# _aggregate_by_seasonal_unit via get_count_by_day_of_week (edge cases)
# ---------------------------------------------------------------------------


class TestSeasonalEdgeCases:
    """Edge-case tests that verify the shared _aggregate_by_seasonal_unit guard conditions."""

    def test_empty_manager_returns_empty_dict(self) -> None:
        """An initialised but empty WorkoutManager returns {}."""
        assert WorkoutManager().get_count_by_day_of_week() == {}

    def test_missing_activity_type_column_returns_empty_dict(self) -> None:
        """Return {} when the required column is absent."""
        manager = WorkoutManager(pd.DataFrame({"startDate": pd.to_datetime(["2024-01-01"])}))
        assert manager.get_count_by_day_of_week() == {}

    def test_missing_start_date_column_returns_empty_dict(self) -> None:
        """Return {} when startDate column is missing."""
        manager = WorkoutManager(pd.DataFrame({"activityType": ["Running"]}))
        assert manager.get_count_by_day_of_week() == {}

    def test_non_datetime_start_date_returns_empty_dict(self) -> None:
        """Return {} when startDate column is not datetime."""
        manager = WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "startDate": ["2024-01-01"],  # plain string, not datetime
                }
            )
        )
        assert manager.get_count_by_day_of_week() == {}

    def test_all_positions_present_in_result(self) -> None:
        """Result must contain exactly the 7 day-of-week labels."""
        manager = _make_manager(
            activityType=["Running"],
            startDate=pd.to_datetime(["2024-01-01"]),  # Monday
        )
        result = manager.get_count_by_day_of_week()
        assert set(result.keys()) == set(_DAY_OF_WEEK_LABELS)

    def test_missing_days_are_filled_with_zero(self) -> None:
        """Days with no workouts must appear in the result with value 0.0."""
        manager = _make_manager(
            activityType=["Running"],
            startDate=pd.to_datetime(["2024-01-01"]),  # Monday only
        )
        result = manager.get_count_by_day_of_week()
        # All days except Monday should be 0
        for label in _DAY_OF_WEEK_LABELS:
            if label != "Monday":
                assert result[label] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# get_count_by_day_of_week
# ---------------------------------------------------------------------------


class TestGetCountByDayOfWeek:
    """Tests for workout count aggregated by day of week."""

    def test_counts_correctly_per_day(self) -> None:
        """Verify counts for a simple multi-day dataset."""
        # 2024-01-01 = Monday, 2024-01-06 = Saturday, 2024-01-08 = Monday
        manager = _make_manager(
            activityType=["Running", "Cycling", "Running"],
            startDate=pd.to_datetime(["2024-01-01", "2024-01-06", "2024-01-08"]),
        )
        result = manager.get_count_by_day_of_week()
        assert result["Monday"] == pytest.approx(2.0)
        assert result["Saturday"] == pytest.approx(1.0)
        assert result["Tuesday"] == pytest.approx(0.0)

    def test_activity_type_filter(self) -> None:
        """Filtering by activity type restricts which workouts contribute."""
        manager = _make_manager(
            activityType=["Running", "Cycling", "Running"],
            startDate=pd.to_datetime(["2024-01-01", "2024-01-01", "2024-01-06"]),
        )
        result = manager.get_count_by_day_of_week(activity_type="Running")
        assert result["Monday"] == pytest.approx(1.0)
        assert result["Saturday"] == pytest.approx(1.0)
        assert result["Sunday"] == pytest.approx(0.0)

    def test_date_range_filter(self) -> None:
        """Date filters exclude workouts outside the range."""
        manager = _make_manager(
            activityType=["Running", "Running"],
            startDate=pd.to_datetime(["2024-01-01", "2024-06-01"]),
        )
        result = manager.get_count_by_day_of_week(
            start_date=pd.Timestamp("2024-01-01"),
            end_date=pd.Timestamp("2024-03-31"),
        )
        assert result["Monday"] == pytest.approx(1.0)
        # June 1 is a Saturday; should be excluded
        assert result["Saturday"] == pytest.approx(0.0)

    def test_returns_floats(self) -> None:
        """All values in the returned dict are float."""
        manager = _make_manager(
            activityType=["Running"],
            startDate=pd.to_datetime(["2024-01-01"]),
        )
        result = manager.get_count_by_day_of_week()
        assert all(isinstance(v, float) for v in result.values())


# ---------------------------------------------------------------------------
# get_count_by_month_of_year
# ---------------------------------------------------------------------------


class TestGetCountByMonthOfYear:
    """Tests for workout count aggregated by month of year."""

    def test_all_month_labels_present(self) -> None:
        """Result always contains exactly the 12 month labels."""
        manager = _make_manager(
            activityType=["Running"],
            startDate=pd.to_datetime(["2024-03-15"]),  # March
        )
        result = manager.get_count_by_month_of_year()
        assert set(result.keys()) == set(_MONTH_OF_YEAR_LABELS)

    def test_counts_correctly_per_month(self) -> None:
        """Verify counts for workouts spanning multiple months."""
        manager = _make_manager(
            activityType=["Running", "Cycling", "Running"],
            startDate=pd.to_datetime(["2024-01-10", "2024-01-20", "2024-07-05"]),
        )
        result = manager.get_count_by_month_of_year()
        assert result["January"] == pytest.approx(2.0)
        assert result["July"] == pytest.approx(1.0)
        assert result["March"] == pytest.approx(0.0)

    def test_multi_year_data_sums_across_years(self) -> None:
        """Workouts in the same calendar month across different years are combined."""
        manager = _make_manager(
            activityType=["Running", "Running", "Running"],
            startDate=pd.to_datetime(["2023-06-01", "2024-06-15", "2024-07-01"]),
        )
        result = manager.get_count_by_month_of_year()
        assert result["June"] == pytest.approx(2.0)
        assert result["July"] == pytest.approx(1.0)

    def test_activity_type_filter(self) -> None:
        """Activity type filter works for month-of-year aggregation."""
        manager = _make_manager(
            activityType=["Running", "Cycling"],
            startDate=pd.to_datetime(["2024-03-01", "2024-03-02"]),
        )
        result = manager.get_count_by_month_of_year(activity_type="Running")
        assert result["March"] == pytest.approx(1.0)
        for label in _MONTH_OF_YEAR_LABELS:
            if label != "March":
                assert result[label] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# get_count_by_quarter_of_year
# ---------------------------------------------------------------------------


class TestGetCountByQuarterOfYear:
    """Tests for workout count aggregated by quarter of year."""

    def test_all_quarter_labels_present(self) -> None:
        """Result always contains exactly the 4 quarter labels."""
        manager = _make_manager(
            activityType=["Running"],
            startDate=pd.to_datetime(["2024-01-15"]),
        )
        result = manager.get_count_by_quarter_of_year()
        assert set(result.keys()) == set(_QUARTER_OF_YEAR_LABELS)

    def test_counts_correctly_per_quarter(self) -> None:
        """Verify counts for workouts spanning multiple quarters."""
        manager = _make_manager(
            activityType=["Running", "Cycling", "Running", "Running"],
            startDate=pd.to_datetime(["2024-01-10", "2024-04-01", "2024-07-15", "2024-07-20"]),
        )
        result = manager.get_count_by_quarter_of_year()
        assert result["Q1"] == pytest.approx(1.0)
        assert result["Q2"] == pytest.approx(1.0)
        assert result["Q3"] == pytest.approx(2.0)
        assert result["Q4"] == pytest.approx(0.0)

    def test_multi_year_data_sums_across_years(self) -> None:
        """Workouts in the same quarter across different years are combined."""
        manager = _make_manager(
            activityType=["Running", "Running"],
            startDate=pd.to_datetime(["2023-02-01", "2024-03-01"]),  # Both Q1
        )
        result = manager.get_count_by_quarter_of_year()
        assert result["Q1"] == pytest.approx(2.0)
        assert result["Q2"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# get_distance_by_day_of_week
# ---------------------------------------------------------------------------


class TestGetDistanceByDayOfWeek:
    """Tests for total distance aggregated by day of week."""

    def test_returns_empty_dict_when_column_missing(self) -> None:
        """Return {} when the distance column is absent."""
        manager = WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "startDate": pd.to_datetime(["2024-01-01"]),
                }
            )
        )
        assert manager.get_distance_by_day_of_week() == {}

    def test_default_unit_is_km(self) -> None:
        """Default unit is km (distance stored in meters)."""
        # 2024-01-01 = Monday
        manager = _make_manager(
            activityType=["Running"],
            startDate=pd.to_datetime(["2024-01-01"]),
            distance=[10_000.0],  # 10 km
        )
        result = manager.get_distance_by_day_of_week()
        assert result["Monday"] == pytest.approx(10.0)

    def test_unit_conversion_to_miles(self) -> None:
        """Distance is correctly converted to miles when requested."""
        manager = _make_manager(
            activityType=["Running"],
            startDate=pd.to_datetime(["2024-01-01"]),  # Monday
            distance=[1609.344],  # 1 mile in meters
        )
        result = manager.get_distance_by_day_of_week(unit="mi")
        assert result["Monday"] == pytest.approx(1.0, rel=1e-4)

    def test_aggregates_multiple_workouts_on_same_day(self) -> None:
        """Multiple workouts on the same day of week are summed."""
        # Both are Mondays
        manager = _make_manager(
            activityType=["Running", "Running"],
            startDate=pd.to_datetime(["2024-01-01", "2024-01-08"]),
            distance=[5_000.0, 7_000.0],
        )
        result = manager.get_distance_by_day_of_week()
        assert result["Monday"] == pytest.approx(12.0)  # 12 km total

    def test_activity_type_filter(self) -> None:
        """Only the specified activity type contributes to the totals."""
        manager = _make_manager(
            activityType=["Running", "Cycling"],
            startDate=pd.to_datetime(["2024-01-01", "2024-01-01"]),  # Both Monday
            distance=[5_000.0, 20_000.0],
        )
        result = manager.get_distance_by_day_of_week(activity_type="Running")
        assert result["Monday"] == pytest.approx(5.0)


# ---------------------------------------------------------------------------
# get_distance_by_month_of_year
# ---------------------------------------------------------------------------


class TestGetDistanceByMonthOfYear:
    """Tests for total distance aggregated by month of year."""

    def test_all_month_labels_present(self) -> None:
        manager = _make_manager(
            activityType=["Running"],
            startDate=pd.to_datetime(["2024-06-01"]),
            distance=[5_000.0],
        )
        result = manager.get_distance_by_month_of_year()
        assert set(result.keys()) == set(_MONTH_OF_YEAR_LABELS)

    def test_sums_distance_correctly(self) -> None:
        manager = _make_manager(
            activityType=["Running", "Running"],
            startDate=pd.to_datetime(["2024-01-10", "2024-01-20"]),
            distance=[5_000.0, 10_000.0],
        )
        result = manager.get_distance_by_month_of_year()
        assert result["January"] == pytest.approx(15.0)

    def test_multi_year_data_sums_across_years(self) -> None:
        manager = _make_manager(
            activityType=["Running", "Running"],
            startDate=pd.to_datetime(["2023-06-01", "2024-06-15"]),
            distance=[10_000.0, 20_000.0],
        )
        result = manager.get_distance_by_month_of_year()
        assert result["June"] == pytest.approx(30.0)

    def test_unit_conversion_to_meters(self) -> None:
        manager = _make_manager(
            activityType=["Running"],
            startDate=pd.to_datetime(["2024-03-01"]),
            distance=[5_000.0],
        )
        result = manager.get_distance_by_month_of_year(unit="m")
        assert result["March"] == pytest.approx(5_000.0)


# ---------------------------------------------------------------------------
# get_distance_by_quarter_of_year
# ---------------------------------------------------------------------------


class TestGetDistanceByQuarterOfYear:
    """Tests for total distance aggregated by quarter of year."""

    def test_all_quarter_labels_present(self) -> None:
        manager = _make_manager(
            activityType=["Running"],
            startDate=pd.to_datetime(["2024-04-01"]),
            distance=[10_000.0],
        )
        result = manager.get_distance_by_quarter_of_year()
        assert set(result.keys()) == set(_QUARTER_OF_YEAR_LABELS)

    def test_sums_correctly_per_quarter(self) -> None:
        manager = _make_manager(
            activityType=["Running", "Cycling"],
            startDate=pd.to_datetime(["2024-02-01", "2024-08-01"]),
            distance=[10_000.0, 20_000.0],
        )
        result = manager.get_distance_by_quarter_of_year()
        assert result["Q1"] == pytest.approx(10.0)
        assert result["Q3"] == pytest.approx(20.0)
        assert result["Q2"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# get_duration_by_day_of_week
# ---------------------------------------------------------------------------


class TestGetDurationByDayOfWeek:
    """Tests for total duration aggregated by day of week."""

    def test_returns_empty_dict_when_column_missing(self) -> None:
        manager = WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "startDate": pd.to_datetime(["2024-01-01"]),
                }
            )
        )
        assert manager.get_duration_by_day_of_week() == {}

    def test_duration_converted_to_hours(self) -> None:
        """Duration stored in seconds is returned in hours."""
        # 2024-01-01 = Monday; 3600 s = 1 h
        manager = _make_manager(
            activityType=["Running"],
            startDate=pd.to_datetime(["2024-01-01"]),
            duration=[3_600.0],
        )
        result = manager.get_duration_by_day_of_week()
        assert result["Monday"] == pytest.approx(1.0)

    def test_aggregates_multiple_workouts_on_same_day(self) -> None:
        manager = _make_manager(
            activityType=["Running", "Cycling"],
            startDate=pd.to_datetime(["2024-01-01", "2024-01-08"]),  # Both Mondays
            duration=[3_600.0, 7_200.0],
        )
        result = manager.get_duration_by_day_of_week()
        assert result["Monday"] == pytest.approx(3.0)  # 1 + 2 hours


# ---------------------------------------------------------------------------
# get_duration_by_month_of_year
# ---------------------------------------------------------------------------


class TestGetDurationByMonthOfYear:
    """Tests for total duration aggregated by month of year."""

    def test_all_month_labels_present(self) -> None:
        manager = _make_manager(
            activityType=["Running"],
            startDate=pd.to_datetime(["2024-05-01"]),
            duration=[3_600.0],
        )
        result = manager.get_duration_by_month_of_year()
        assert set(result.keys()) == set(_MONTH_OF_YEAR_LABELS)

    def test_sums_duration_correctly(self) -> None:
        manager = _make_manager(
            activityType=["Running", "Cycling"],
            startDate=pd.to_datetime(["2024-02-01", "2024-02-14"]),
            duration=[7_200.0, 3_600.0],  # 2h + 1h
        )
        result = manager.get_duration_by_month_of_year()
        assert result["February"] == pytest.approx(3.0)

    def test_missing_months_filled_with_zero(self) -> None:
        manager = _make_manager(
            activityType=["Running"],
            startDate=pd.to_datetime(["2024-11-01"]),
            duration=[3_600.0],
        )
        result = manager.get_duration_by_month_of_year()
        for label in _MONTH_OF_YEAR_LABELS:
            if label != "November":
                assert result[label] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# get_duration_by_quarter_of_year
# ---------------------------------------------------------------------------


class TestGetDurationByQuarterOfYear:
    """Tests for total duration aggregated by quarter of year."""

    def test_all_quarter_labels_present(self) -> None:
        manager = _make_manager(
            activityType=["Running"],
            startDate=pd.to_datetime(["2024-10-01"]),
            duration=[3_600.0],
        )
        result = manager.get_duration_by_quarter_of_year()
        assert set(result.keys()) == set(_QUARTER_OF_YEAR_LABELS)

    def test_sums_correctly_per_quarter(self) -> None:
        manager = _make_manager(
            activityType=["Running", "Cycling"],
            startDate=pd.to_datetime(["2024-01-15", "2024-10-01"]),
            duration=[3_600.0, 7_200.0],  # Q1=1h, Q4=2h
        )
        result = manager.get_duration_by_quarter_of_year()
        assert result["Q1"] == pytest.approx(1.0)
        assert result["Q4"] == pytest.approx(2.0)
        assert result["Q2"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# get_calories_by_day_of_week
# ---------------------------------------------------------------------------


class TestGetCaloriesByDayOfWeek:
    """Tests for total calories aggregated by day of week."""

    def test_returns_empty_dict_when_column_missing(self) -> None:
        manager = WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "startDate": pd.to_datetime(["2024-01-01"]),
                }
            )
        )
        assert manager.get_calories_by_day_of_week() == {}

    def test_all_day_labels_present(self) -> None:
        manager = _make_manager(
            activityType=["Running"],
            startDate=pd.to_datetime(["2024-01-01"]),
            sumActiveEnergyBurned=[500.0],
        )
        result = manager.get_calories_by_day_of_week()
        assert set(result.keys()) == set(_DAY_OF_WEEK_LABELS)

    def test_sums_calories_correctly(self) -> None:
        # 2024-01-01 = Monday; 2024-01-06 = Saturday
        manager = _make_manager(
            activityType=["Running", "Cycling"],
            startDate=pd.to_datetime(["2024-01-01", "2024-01-01"]),  # Both Monday
            sumActiveEnergyBurned=[300.0, 200.0],
        )
        result = manager.get_calories_by_day_of_week()
        assert result["Monday"] == pytest.approx(500.0)

    def test_activity_type_filter(self) -> None:
        manager = _make_manager(
            activityType=["Running", "Cycling"],
            startDate=pd.to_datetime(["2024-01-01", "2024-01-01"]),  # Both Monday
            sumActiveEnergyBurned=[300.0, 200.0],
        )
        result = manager.get_calories_by_day_of_week(activity_type="Running")
        assert result["Monday"] == pytest.approx(300.0)
        assert result["Saturday"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# get_calories_by_month_of_year
# ---------------------------------------------------------------------------


class TestGetCaloriesByMonthOfYear:
    """Tests for total calories aggregated by month of year."""

    def test_all_month_labels_present(self) -> None:
        manager = _make_manager(
            activityType=["Running"],
            startDate=pd.to_datetime(["2024-08-01"]),
            sumActiveEnergyBurned=[400.0],
        )
        result = manager.get_calories_by_month_of_year()
        assert set(result.keys()) == set(_MONTH_OF_YEAR_LABELS)

    def test_sums_correctly_per_month(self) -> None:
        manager = _make_manager(
            activityType=["Running", "Running"],
            startDate=pd.to_datetime(["2024-09-01", "2024-09-15"]),
            sumActiveEnergyBurned=[200.0, 350.0],
        )
        result = manager.get_calories_by_month_of_year()
        assert result["September"] == pytest.approx(550.0)

    def test_multi_year_data_sums_across_years(self) -> None:
        manager = _make_manager(
            activityType=["Running", "Running"],
            startDate=pd.to_datetime(["2023-12-01", "2024-12-01"]),
            sumActiveEnergyBurned=[100.0, 200.0],
        )
        result = manager.get_calories_by_month_of_year()
        assert result["December"] == pytest.approx(300.0)


# ---------------------------------------------------------------------------
# get_calories_by_quarter_of_year
# ---------------------------------------------------------------------------


class TestGetCaloriesByQuarterOfYear:
    """Tests for total calories aggregated by quarter of year."""

    def test_all_quarter_labels_present(self) -> None:
        manager = _make_manager(
            activityType=["Running"],
            startDate=pd.to_datetime(["2024-05-01"]),
            sumActiveEnergyBurned=[500.0],
        )
        result = manager.get_calories_by_quarter_of_year()
        assert set(result.keys()) == set(_QUARTER_OF_YEAR_LABELS)

    def test_sums_correctly_per_quarter(self) -> None:
        manager = _make_manager(
            activityType=["Running", "Cycling", "Running"],
            startDate=pd.to_datetime(["2024-01-10", "2024-04-05", "2024-04-20"]),
            sumActiveEnergyBurned=[300.0, 200.0, 400.0],
        )
        result = manager.get_calories_by_quarter_of_year()
        assert result["Q1"] == pytest.approx(300.0)
        assert result["Q2"] == pytest.approx(600.0)
        assert result["Q3"] == pytest.approx(0.0)
        assert result["Q4"] == pytest.approx(0.0)

    def test_activity_type_filter(self) -> None:
        manager = _make_manager(
            activityType=["Running", "Cycling"],
            startDate=pd.to_datetime(["2024-07-01", "2024-07-01"]),
            sumActiveEnergyBurned=[300.0, 500.0],
        )
        result = manager.get_calories_by_quarter_of_year(activity_type="Cycling")
        assert result["Q3"] == pytest.approx(500.0)
        assert result["Q1"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# KeyError guard: activity_type filter without activityType column
# ---------------------------------------------------------------------------


class TestSeasonalActivityTypeGuard:
    """Ensure no KeyError is raised when activityType column is absent."""

    def test_missing_activity_type_column_with_filter_returns_empty_dict(self) -> None:
        """Return {} when filtering by activity type but activityType column is absent."""
        manager = WorkoutManager(
            pd.DataFrame(
                {
                    "distance": [5_000.0],
                    "startDate": pd.to_datetime(["2024-01-01"]),
                }
            )
        )
        assert manager.get_distance_by_day_of_week(activity_type="Running") == {}

    def test_missing_activity_type_column_with_filter_month(self) -> None:
        manager = WorkoutManager(
            pd.DataFrame(
                {
                    "distance": [5_000.0],
                    "startDate": pd.to_datetime(["2024-01-01"]),
                }
            )
        )
        assert manager.get_distance_by_month_of_year(activity_type="Running") == {}

    def test_missing_activity_type_column_with_filter_year(self) -> None:
        manager = WorkoutManager(
            pd.DataFrame(
                {
                    "distance": [5_000.0],
                    "startDate": pd.to_datetime(["2024-01-01"]),
                }
            )
        )
        assert manager.get_distance_by_year(activity_type="Running") == {}


# ---------------------------------------------------------------------------
# get_count_by_year
# ---------------------------------------------------------------------------


class TestGetCountByYear:
    """Tests for workout count aggregated by calendar year."""

    def test_empty_manager_returns_empty_dict(self) -> None:
        assert WorkoutManager().get_count_by_year() == {}

    def test_single_year(self) -> None:
        manager = _make_manager(
            activityType=["Running", "Cycling"],
            startDate=pd.to_datetime(["2024-03-01", "2024-07-01"]),
        )
        result = manager.get_count_by_year()
        assert result == {"2024": pytest.approx(2.0)}

    def test_multiple_years(self) -> None:
        manager = _make_manager(
            activityType=["Running", "Running", "Cycling"],
            startDate=pd.to_datetime(["2023-01-10", "2024-06-15", "2024-11-01"]),
        )
        result = manager.get_count_by_year()
        assert result["2023"] == pytest.approx(1.0)
        assert result["2024"] == pytest.approx(2.0)

    def test_activity_type_filter(self) -> None:
        manager = _make_manager(
            activityType=["Running", "Cycling", "Running"],
            startDate=pd.to_datetime(["2023-01-01", "2023-06-01", "2024-01-01"]),
        )
        result = manager.get_count_by_year(activity_type="Running")
        assert result["2023"] == pytest.approx(1.0)
        assert result["2024"] == pytest.approx(1.0)
        assert "Cycling" not in result

    def test_returns_floats(self) -> None:
        manager = _make_manager(
            activityType=["Running"],
            startDate=pd.to_datetime(["2024-01-01"]),
        )
        result = manager.get_count_by_year()
        assert all(isinstance(v, float) for v in result.values())


# ---------------------------------------------------------------------------
# get_distance_by_year
# ---------------------------------------------------------------------------


class TestGetDistanceByYear:
    """Tests for total distance aggregated by calendar year."""

    def test_returns_empty_dict_when_column_missing(self) -> None:
        manager = WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "startDate": pd.to_datetime(["2024-01-01"]),
                }
            )
        )
        assert manager.get_distance_by_year() == {}

    def test_default_unit_is_km(self) -> None:
        manager = _make_manager(
            activityType=["Running"],
            startDate=pd.to_datetime(["2024-06-01"]),
            distance=[10_000.0],
        )
        result = manager.get_distance_by_year()
        assert result["2024"] == pytest.approx(10.0)

    def test_sums_across_multiple_workouts_same_year(self) -> None:
        manager = _make_manager(
            activityType=["Running", "Cycling"],
            startDate=pd.to_datetime(["2024-01-01", "2024-08-01"]),
            distance=[5_000.0, 10_000.0],
        )
        result = manager.get_distance_by_year()
        assert result["2024"] == pytest.approx(15.0)

    def test_separate_totals_per_year(self) -> None:
        manager = _make_manager(
            activityType=["Running", "Running"],
            startDate=pd.to_datetime(["2023-03-01", "2024-03-01"]),
            distance=[10_000.0, 20_000.0],
        )
        result = manager.get_distance_by_year()
        assert result["2023"] == pytest.approx(10.0)
        assert result["2024"] == pytest.approx(20.0)

    def test_unit_conversion_to_miles(self) -> None:
        manager = _make_manager(
            activityType=["Running"],
            startDate=pd.to_datetime(["2024-05-01"]),
            distance=[1609.344],
        )
        result = manager.get_distance_by_year(unit="mi")
        assert result["2024"] == pytest.approx(1.0, rel=1e-4)


# ---------------------------------------------------------------------------
# get_duration_by_year
# ---------------------------------------------------------------------------


class TestGetDurationByYear:
    """Tests for total duration aggregated by calendar year."""

    def test_returns_empty_dict_when_column_missing(self) -> None:
        manager = WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "startDate": pd.to_datetime(["2024-01-01"]),
                }
            )
        )
        assert manager.get_duration_by_year() == {}

    def test_duration_converted_to_hours(self) -> None:
        manager = _make_manager(
            activityType=["Running"],
            startDate=pd.to_datetime(["2024-01-01"]),
            duration=[7_200.0],  # 2 hours in seconds
        )
        result = manager.get_duration_by_year()
        assert result["2024"] == pytest.approx(2.0)

    def test_sums_correctly_across_years(self) -> None:
        manager = _make_manager(
            activityType=["Running", "Running"],
            startDate=pd.to_datetime(["2023-06-01", "2024-06-01"]),
            duration=[3_600.0, 7_200.0],
        )
        result = manager.get_duration_by_year()
        assert result["2023"] == pytest.approx(1.0)
        assert result["2024"] == pytest.approx(2.0)

    def test_activity_type_filter(self) -> None:
        manager = _make_manager(
            activityType=["Running", "Cycling"],
            startDate=pd.to_datetime(["2024-01-01", "2024-06-01"]),
            duration=[3_600.0, 7_200.0],
        )
        result = manager.get_duration_by_year(activity_type="Running")
        assert result["2024"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# get_calories_by_year
# ---------------------------------------------------------------------------


class TestGetCaloriesByYear:
    """Tests for total calories aggregated by calendar year."""

    def test_returns_empty_dict_when_column_missing(self) -> None:
        manager = WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "startDate": pd.to_datetime(["2024-01-01"]),
                }
            )
        )
        assert manager.get_calories_by_year() == {}

    def test_sums_calories_per_year(self) -> None:
        manager = _make_manager(
            activityType=["Running", "Cycling"],
            startDate=pd.to_datetime(["2024-03-01", "2024-09-01"]),
            sumActiveEnergyBurned=[300.0, 500.0],
        )
        result = manager.get_calories_by_year()
        assert result["2024"] == pytest.approx(800.0)

    def test_separate_totals_per_year(self) -> None:
        manager = _make_manager(
            activityType=["Running", "Running"],
            startDate=pd.to_datetime(["2023-01-01", "2024-01-01"]),
            sumActiveEnergyBurned=[200.0, 400.0],
        )
        result = manager.get_calories_by_year()
        assert result["2023"] == pytest.approx(200.0)
        assert result["2024"] == pytest.approx(400.0)

    def test_activity_type_filter(self) -> None:
        manager = _make_manager(
            activityType=["Running", "Cycling"],
            startDate=pd.to_datetime(["2024-01-01", "2024-01-01"]),
            sumActiveEnergyBurned=[300.0, 500.0],
        )
        result = manager.get_calories_by_year(activity_type="Running")
        assert result["2024"] == pytest.approx(300.0)
