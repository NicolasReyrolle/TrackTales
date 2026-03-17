"""Tests for WorkoutManager count/duration by period methods."""

import pandas as pd

from logic import workout_manager as wm


class TestGetCountByPeriod:
    """Test suite for WorkoutManager.get_count_by_period method."""

    def test_get_count_by_period_empty(self) -> None:
        workouts = wm.WorkoutManager()

        result = workouts.get_count_by_period("M")

        assert result == {}

    def test_get_count_by_period_missing_columns(self) -> None:
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "startDate": pd.to_datetime(["2024-01-01"]),
                }
            )
        )

        result = workouts.get_count_by_period("M")

        assert result == {}

    def test_get_count_by_period_missing_start_date_column(self) -> None:
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                }
            )
        )

        result = workouts.get_count_by_period("M")

        assert result == {}

    def test_get_count_by_period_non_datetime_start_date(self) -> None:
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "startDate": ["2024-01-01"],
                }
            )
        )

        result = workouts.get_count_by_period("M")

        assert result == {}

    def test_get_count_by_period_groups_by_month(self) -> None:
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running", "Cycling"],
                    "startDate": pd.to_datetime(["2024-01-05", "2024-01-20", "2024-02-03"]),
                }
            )
        )

        result = workouts.get_count_by_period("M", fill_missing_periods=False)

        assert result == {
            "2024-01": 2,
            "2024-02": 1,
        }

    def test_get_count_by_period_filters_activity(self) -> None:
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running", "Cycling"],
                    "startDate": pd.to_datetime(["2024-01-05", "2024-02-20", "2024-02-03"]),
                }
            )
        )

        result = workouts.get_count_by_period(
            "M",
            fill_missing_periods=False,
            activity_type="Running",
        )

        assert result == {
            "2024-01": 1,
            "2024-02": 1,
        }

    def test_get_count_by_period_multiple_activities_in_month(self) -> None:
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"] * 9 + ["Cycling"],
                    "startDate": pd.to_datetime(["2024-01-05"] * 9 + ["2024-01-20"]),
                }
            )
        )

        result = workouts.get_count_by_period("M", fill_missing_periods=False)

        assert result == {"2024-01": 10}

    def test_get_count_by_period_no_fill_missing(self) -> None:
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running"],
                    "startDate": pd.to_datetime(["2024-01-05", "2024-02-05"]),
                }
            )
        )

        result = workouts.get_count_by_period("M", fill_missing_periods=False)

        assert result == {"2024-01": 1, "2024-02": 1}

    def test_get_count_by_period_with_fill_missing_periods(self) -> None:
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Cycling"],
                    "startDate": pd.to_datetime(["2023-12-31", "2024-02-01"]),
                }
            )
        )

        result = workouts.get_count_by_period("M")

        assert result == {
            "2023-12": 1,
            "2024-01": 0,
            "2024-02": 1,
        }

    def test_get_count_by_period_groups_by_year(self) -> None:
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running", "Cycling"],
                    "startDate": pd.to_datetime(["2023-12-31", "2024-01-01", "2024-06-15"]),
                }
            )
        )

        result = workouts.get_count_by_period("Y", fill_missing_periods=False)

        assert result == {
            "2023": 1,
            "2024": 2,
        }

    def test_get_count_by_period_single_in_month(self) -> None:
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "startDate": pd.to_datetime(["2024-03-15"]),
                }
            )
        )

        result = workouts.get_count_by_period("M", fill_missing_periods=False)

        assert result == {"2024-03": 1}


class TestGetDurationByPeriod:
    """Test suite for WorkoutManager.get_duration_by_period method."""

    def test_get_duration_by_period_empty(self) -> None:
        workouts = wm.WorkoutManager()

        result = workouts.get_duration_by_period("M")

        assert result == {}

    def test_get_duration_by_period_missing_columns(self) -> None:
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "startDate": pd.to_datetime(["2024-01-01"]),
                }
            )
        )

        result = workouts.get_duration_by_period("M")

        assert result == {}

    def test_get_duration_by_period_missing_start_date_column(self) -> None:
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "duration": [3600.0],
                }
            )
        )

        result = workouts.get_duration_by_period("M")

        assert result == {}

    def test_get_duration_by_period_non_datetime_start_date(self) -> None:
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "startDate": ["2024-01-01"],
                    "duration": [3600.0],
                }
            )
        )

        result = workouts.get_duration_by_period("M")

        assert result == {}

    def test_get_duration_by_period_groups_by_month(self) -> None:
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running", "Cycling"],
                    "startDate": pd.to_datetime(["2024-01-05", "2024-01-20", "2024-02-03"]),
                    "duration": [3600.0, 1800.0, 7200.0],
                }
            )
        )

        result = workouts.get_duration_by_period("M", fill_missing_periods=False)

        assert result == {
            "2024-01": 2,
            "2024-02": 2,
        }

    def test_get_duration_by_period_filters_activity(self) -> None:
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running", "Cycling"],
                    "startDate": pd.to_datetime(["2024-01-05", "2024-02-20", "2024-02-03"]),
                    "duration": [3600.0, 7200.0, 10800.0],
                }
            )
        )

        result = workouts.get_duration_by_period(
            "M",
            fill_missing_periods=False,
            activity_type="Running",
        )

        assert result == {
            "2024-01": 1,
            "2024-02": 2,
        }

    def test_get_duration_by_period_multiple_in_period(self) -> None:
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running"],
                    "startDate": pd.to_datetime(["2024-01-05", "2024-02-05"]),
                    "duration": [36000.0, 360.0],
                }
            )
        )

        result = workouts.get_duration_by_period("M", fill_missing_periods=False)

        assert result == {"2024-01": 10}

    def test_get_duration_by_period_with_fill_missing_periods(self) -> None:
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Cycling"],
                    "startDate": pd.to_datetime(["2023-12-31", "2024-02-01"]),
                    "duration": [3600.0, 7200.0],
                }
            )
        )

        result = workouts.get_duration_by_period("M", fill_missing_periods=True)

        assert result == {
            "2023-12": 1,
            "2024-01": 0,
            "2024-02": 2,
        }

    def test_get_duration_by_period_groups_by_year(self) -> None:
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running", "Cycling"],
                    "startDate": pd.to_datetime(["2023-12-31", "2024-01-01", "2024-06-15"]),
                    "duration": [3600.0, 7200.0, 10800.0],
                }
            )
        )

        result = workouts.get_duration_by_period("Y", fill_missing_periods=False)

        assert result == {
            "2023": 1,
            "2024": 5,
        }

    def test_get_duration_by_period_fractional_hours(self) -> None:
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running"],
                    "startDate": pd.to_datetime(["2024-01-05", "2024-01-10"]),
                    "duration": [5400.0, 5400.0],
                }
            )
        )

        result = workouts.get_duration_by_period("M", fill_missing_periods=False)

        assert result == {"2024-01": 3}
