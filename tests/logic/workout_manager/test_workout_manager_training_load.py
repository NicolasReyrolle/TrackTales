"""Tests for WorkoutManager training load aggregation."""

import pandas as pd

from logic.workout_manager import WorkoutManager


def _manager() -> WorkoutManager:
    return WorkoutManager(
        pd.DataFrame(
            {
                "activityType": ["Running", "Cycling", "Running"],
                "startDate": pd.to_datetime(["2024-01-01", "2024-01-15", "2024-02-01"]),
                "duration": [3600, 1800, 1800],
                "averageHeartRate": [150, 120, 140],
            }
        )
    )


def test_get_training_load_uses_duration_minutes_and_average_heart_rate() -> None:
    assert _manager().get_training_load() == 16800


def test_get_training_load_filters_activity_and_date_range() -> None:
    manager = _manager()
    assert manager.get_training_load("Running") == 13200
    assert (
        manager.get_training_load(
            start_date=pd.Timestamp("2024-01-01"),
            end_date=pd.Timestamp("2024-01-31"),
        )
        == 12600
    )


def test_get_training_load_returns_zero_without_required_metrics() -> None:
    manager = WorkoutManager(pd.DataFrame({"activityType": ["Running"], "duration": [3600]}))
    assert manager.get_training_load() == 0


def test_get_training_load_by_period_fills_missing_periods() -> None:
    manager = WorkoutManager(
        pd.DataFrame(
            {
                "activityType": ["Running", "Running"],
                "startDate": pd.to_datetime(["2024-01-01", "2024-03-01"]),
                "duration": [3600, 1800],
                "averageHeartRate": [150, 140],
            }
        )
    )
    result = manager.get_training_load_by_period("M")
    assert result == {"2024-01": 9000, "2024-02": 0, "2024-03": 4200}


def test_get_training_load_by_period_can_omit_empty_periods() -> None:
    result = _manager().get_training_load_by_period("M", fill_missing_periods=False)
    assert result == {"2024-01": 12600, "2024-02": 4200}


def test_get_training_load_ignores_workouts_with_missing_metric_values() -> None:
    manager = WorkoutManager(
        pd.DataFrame(
            {
                "activityType": ["Running", "Running"],
                "startDate": pd.to_datetime(["2024-01-01", "2024-02-01"]),
                "duration": [3600, 3600],
                "averageHeartRate": [150, None],
            }
        )
    )

    assert manager.get_training_load() == 9000
    assert manager.get_training_load_by_period("M", fill_missing_periods=False) == {"2024-01": 9000}
