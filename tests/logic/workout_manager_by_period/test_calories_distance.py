"""Tests for WorkoutManager calories/distance by period methods."""

# pylint: disable=missing-function-docstring,duplicate-code,line-too-long

import pandas as pd

from logic import workout_manager as wm


class TestGetCaloriesByPeriod:
    """Test suite for WorkoutManager.get_calories_by_period method."""

    def test_get_calories_by_period_empty(self) -> None:
        """Return empty dict for empty DataFrame."""
        workouts = wm.WorkoutManager()

        result = workouts.get_calories_by_period("M")

        assert result == {}

    def test_get_calories_by_period_missing_columns(self) -> None:
        """Return empty dict when required columns are missing."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "startDate": pd.to_datetime(["2024-01-01"]),
                }
            )
        )

        result = workouts.get_calories_by_period("M")

        assert result == {}

    def test_get_calories_by_period_missing_start_date_column(self) -> None:
        """Return empty dict when startDate column is missing."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "sumActiveEnergyBurned": [300.0],
                }
            )
        )

        result = workouts.get_calories_by_period("M")

        assert result == {}

    def test_get_calories_by_period_non_datetime_start_date(self) -> None:
        """Return empty dict when startDate is not datetime-like."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "startDate": ["2024-01-01"],
                    "sumActiveEnergyBurned": [300.0],
                }
            )
        )

        result = workouts.get_calories_by_period("M")

        assert result == {}

    def test_get_calories_by_period_groups_by_month(self) -> None:
        """Aggregate calories by month without grouping threshold."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running", "Cycling"],
                    "startDate": pd.to_datetime(["2024-01-05", "2024-01-20", "2024-02-03"]),
                    "sumActiveEnergyBurned": [300.0, 200.0, 450.0],
                }
            )
        )

        result = workouts.get_calories_by_period("M")

        assert all(isinstance(key, str) for key in result.keys())
        assert result == {"2024-01": 500, "2024-02": 450}

    def test_get_calories_by_period_filters_activity(self) -> None:
        """Aggregate calories by month for a specific activity."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running", "Cycling"],
                    "startDate": pd.to_datetime(["2024-01-05", "2024-02-20", "2024-02-03"]),
                    "sumActiveEnergyBurned": [300.0, 200.0, 450.0],
                }
            )
        )

        result = workouts.get_calories_by_period("M", activity_type="Running")

        assert result == {"2024-01": 300, "2024-02": 200}

    def test_get_calories_by_period_filters_zero_values(self) -> None:
        """Drop zero-valued periods when filter_zeros applies."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running"],
                    "startDate": pd.to_datetime(["2024-01-05", "2024-02-05"]),
                    "sumActiveEnergyBurned": [0.0, 150.0],
                }
            )
        )

        result = workouts.get_calories_by_period("M", fill_missing_periods=False)

        assert result == {"2024-02": 150}


class TestGetDistanceByPeriod:
    """Test suite for WorkoutManager.get_distance_by_period method."""

    def test_get_distance_by_period_empty(self) -> None:
        workouts = wm.WorkoutManager()
        assert workouts.get_distance_by_period("M") == {}

    def test_get_distance_by_period_missing_columns(self) -> None:
        workouts = wm.WorkoutManager(
            pd.DataFrame({"activityType": ["Running"], "startDate": pd.to_datetime(["2024-01-01"])})
        )
        assert workouts.get_distance_by_period("M") == {}

    def test_get_distance_by_period_missing_start_date_column(self) -> None:
        workouts = wm.WorkoutManager(
            pd.DataFrame({"activityType": ["Running"], "distance": [5000.0]})
        )
        assert workouts.get_distance_by_period("M") == {}

    def test_get_distance_by_period_non_datetime_start_date(self) -> None:
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "startDate": ["2024-01-01"],
                    "distance": [5000.0],
                }
            )
        )
        assert workouts.get_distance_by_period("M") == {}

    def test_get_distance_by_period_groups_by_month_km(self) -> None:
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running", "Cycling"],
                    "startDate": pd.to_datetime(["2024-01-05", "2024-01-20", "2024-02-03"]),
                    "distance": [5000.0, 7000.0, 20000.0],
                }
            )
        )
        assert workouts.get_distance_by_period("M") == {"2024-01": 12, "2024-02": 20}

    def test_get_distance_by_period_groups_by_month_meters(self) -> None:
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Cycling"],
                    "startDate": pd.to_datetime(["2024-01-05", "2024-02-03"]),
                    "distance": [5000.0, 20000.0],
                }
            )
        )
        assert workouts.get_distance_by_period("M", unit="m") == {"2024-01": 5000, "2024-02": 20000}

    def test_get_distance_by_period_groups_by_month_miles(self) -> None:
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "startDate": pd.to_datetime(["2024-01-05"]),
                    "distance": [1609.34],
                }
            )
        )
        assert workouts.get_distance_by_period("M", unit="mi") == {"2024-01": 1}

    def test_get_distance_by_period_filters_activity(self) -> None:
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running", "Cycling"],
                    "startDate": pd.to_datetime(["2024-01-05", "2024-02-20", "2024-02-03"]),
                    "distance": [5000.0, 10000.0, 20000.0],
                }
            )
        )
        assert workouts.get_distance_by_period("M", activity_type="Running") == {
            "2024-01": 5,
            "2024-02": 10,
        }

    def test_get_distance_by_period_filters_zero_values(self) -> None:
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running"],
                    "startDate": pd.to_datetime(["2024-01-05", "2024-02-05"]),
                    "distance": [0.0, 10000.0],
                }
            )
        )
        assert workouts.get_distance_by_period("M") == {"2024-01": 0, "2024-02": 10}

    def test_get_distance_by_period_with_fill_missing_periods(self) -> None:
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running"],
                    "startDate": pd.to_datetime(["2023-12-31", "2024-02-01"]),
                    "distance": [5000.0, 10000.0],
                }
            )
        )
        assert workouts.get_distance_by_period("M") == {"2023-12": 5, "2024-01": 0, "2024-02": 10}

    def test_get_distance_by_period_groups_by_year(self) -> None:
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running", "Cycling"],
                    "startDate": pd.to_datetime(["2023-12-31", "2024-01-01", "2024-06-15"]),
                    "distance": [5000.0, 10000.0, 20000.0],
                }
            )
        )
        assert workouts.get_distance_by_period("Y") == {"2023": 5, "2024": 30}
