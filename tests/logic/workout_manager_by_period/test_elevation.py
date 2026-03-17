"""Tests for WorkoutManager elevation by period methods."""

import pandas as pd

from logic import workout_manager as wm


class TestGetElevationByPeriod:
    """Test suite for WorkoutManager.get_elevation_by_period method."""

    def test_get_elevation_by_period_empty(self) -> None:
        workouts = wm.WorkoutManager()

        result = workouts.get_elevation_by_period("M")

        assert result == {}

    def test_get_elevation_by_period_missing_columns(self) -> None:
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "startDate": pd.to_datetime(["2024-01-01"]),
                }
            )
        )

        result = workouts.get_elevation_by_period("M")

        assert result == {}

    def test_get_elevation_by_period_missing_start_date_column(self) -> None:
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "ElevationAscended": [1000.0],
                }
            )
        )

        result = workouts.get_elevation_by_period("M")

        assert result == {}

    def test_get_elevation_by_period_non_datetime_start_date(self) -> None:
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "startDate": ["2024-01-01"],
                    "ElevationAscended": [1000.0],
                }
            )
        )

        result = workouts.get_elevation_by_period("M")

        assert result == {}

    def test_get_elevation_by_period_groups_by_month(self) -> None:
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running", "Cycling"],
                    "startDate": pd.to_datetime(["2024-01-05", "2024-01-20", "2024-02-03"]),
                    "ElevationAscended": [1000.0, 500.0, 5000.0],
                }
            )
        )

        result = workouts.get_elevation_by_period("M", fill_missing_periods=False, unit="km")

        assert result == {
            "2024-01": 2,
            "2024-02": 5,
        }

    def test_get_elevation_by_period_filters_activity(self) -> None:
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running", "Cycling"],
                    "startDate": pd.to_datetime(["2024-01-05", "2024-02-20", "2024-02-03"]),
                    "ElevationAscended": [1000.0, 2000.0, 5000.0],
                }
            )
        )

        result = workouts.get_elevation_by_period(
            "M",
            fill_missing_periods=False,
            activity_type="Running",
            unit="km",
        )

        assert result == {
            "2024-01": 1,
            "2024-02": 2,
        }

    def test_get_elevation_by_period_multiple_in_period(self) -> None:
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Cycling"],
                    "startDate": pd.to_datetime(["2024-01-05", "2024-02-05"]),
                    "ElevationAscended": [10000.0, 5000.0],
                }
            )
        )

        result = workouts.get_elevation_by_period("M", fill_missing_periods=False, unit="km")

        assert result == {
            "2024-01": 10,
            "2024-02": 5,
        }

    def test_get_elevation_by_period_preserves_zero_values(self) -> None:
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Cycling"],
                    "startDate": pd.to_datetime(["2024-01-05", "2024-02-05"]),
                    "ElevationAscended": [10000.0, 2000.0],
                }
            )
        )

        result = workouts.get_elevation_by_period("M", fill_missing_periods=False, unit="km")

        assert result == {"2024-01": 10, "2024-02": 2}

    def test_get_elevation_by_period_with_fill_missing_periods(self) -> None:
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Cycling"],
                    "startDate": pd.to_datetime(["2023-12-31", "2024-02-01"]),
                    "ElevationAscended": [10000.0, 30000.0],
                }
            )
        )

        result = workouts.get_elevation_by_period("M", unit="km")

        assert result == {
            "2023-12": 10,
            "2024-01": 0,
            "2024-02": 30,
        }

    def test_get_elevation_by_period_groups_by_year(self) -> None:
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running", "Cycling"],
                    "startDate": pd.to_datetime(["2023-12-31", "2024-01-01", "2024-06-15"]),
                    "ElevationAscended": [1000.0, 2000.0, 5000.0],
                }
            )
        )

        result = workouts.get_elevation_by_period("Y", fill_missing_periods=False, unit="km")

        assert result == {
            "2023": 1,
            "2024": 7,
        }

    def test_get_elevation_by_period_high_elevation(self) -> None:
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Hiking"],
                    "startDate": pd.to_datetime(["2024-08-15"]),
                    "ElevationAscended": [1500000.0],
                }
            )
        )

        result = workouts.get_elevation_by_period("M", fill_missing_periods=False, unit="km")

        assert result == {"2024-08": 1500}
