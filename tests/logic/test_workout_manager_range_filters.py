"""Tests for WorkoutManager get_distance_bounds() and get_duration_bounds() methods."""

import pandas as pd
import pytest

import logic.workout_manager as wm


class TestGetDistanceBounds:
    """Tests for WorkoutManager.get_distance_bounds()."""

    def test_empty_workouts_returns_zero_bounds(self) -> None:
        """Empty DataFrame should return (0.0, 0.0)."""
        manager = wm.WorkoutManager()
        assert manager.get_distance_bounds() == pytest.approx((0.0, 0.0))

    def test_no_distance_column_returns_zero_bounds(self) -> None:
        """DataFrame without distance column should return (0.0, 0.0)."""
        manager = wm.WorkoutManager(
            pd.DataFrame({"activityType": ["Running"], "duration": [3600.0]})
        )
        assert manager.get_distance_bounds() == pytest.approx((0.0, 0.0))

    def test_all_zero_distances_returns_zero_bounds(self) -> None:
        """Workouts with zero or null distances should return (0.0, 0.0)."""
        manager = wm.WorkoutManager(
            pd.DataFrame({"activityType": ["Yoga", "Yoga"], "distance": [0.0, None]})
        )
        assert manager.get_distance_bounds() == pytest.approx((0.0, 0.0))

    def test_single_workout_returns_same_min_max(self) -> None:
        """Single workout returns same value for min and max."""
        manager = wm.WorkoutManager(
            pd.DataFrame({"activityType": ["Running"], "distance": [5000.0]})
        )
        lo, hi = manager.get_distance_bounds()
        assert lo == pytest.approx(5.0)
        assert hi == pytest.approx(5.0)

    def test_multiple_workouts_returns_correct_bounds(self) -> None:
        """Multiple workouts: min and max distances returned in km."""
        manager = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running", "Cycling"],
                    "distance": [3000.0, 10000.0, 30000.0],
                }
            )
        )
        lo, hi = manager.get_distance_bounds()
        assert lo == pytest.approx(3.0)
        assert hi == pytest.approx(30.0)

    def test_bounds_in_metres(self) -> None:
        """Requesting bounds in 'm' returns values in metres."""
        manager = wm.WorkoutManager(
            pd.DataFrame({"activityType": ["Running"], "distance": [5000.0]})
        )
        lo, hi = manager.get_distance_bounds(unit="m")
        assert lo == pytest.approx(5000.0)
        assert hi == pytest.approx(5000.0)

    def test_bounds_ignore_nan_and_zero(self) -> None:
        """NaN and zero distances are excluded from bounds calculation."""
        manager = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Yoga", "Cycling"],
                    "distance": [8000.0, None, 0.0],
                }
            )
        )
        lo, hi = manager.get_distance_bounds()
        assert lo == pytest.approx(8.0)
        assert hi == pytest.approx(8.0)


class TestGetDurationBounds:
    """Tests for WorkoutManager.get_duration_bounds()."""

    def test_empty_workouts_returns_zero_bounds(self) -> None:
        """Empty DataFrame should return (0.0, 0.0)."""
        manager = wm.WorkoutManager()
        assert manager.get_duration_bounds() == pytest.approx((0.0, 0.0))

    def test_no_duration_column_returns_zero_bounds(self) -> None:
        """DataFrame without duration column should return (0.0, 0.0)."""
        manager = wm.WorkoutManager(
            pd.DataFrame({"activityType": ["Running"], "distance": [5000.0]})
        )
        assert manager.get_duration_bounds() == pytest.approx((0.0, 0.0))

    def test_single_workout_returns_same_min_max(self) -> None:
        """Single workout returns same value for min and max in minutes."""
        manager = wm.WorkoutManager(
            pd.DataFrame({"activityType": ["Running"], "duration": [3600.0]})
        )
        lo, hi = manager.get_duration_bounds()
        assert lo == pytest.approx(60.0)
        assert hi == pytest.approx(60.0)

    def test_multiple_workouts_returns_correct_bounds(self) -> None:
        """Multiple workouts: min and max durations returned in minutes."""
        manager = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Walking", "Cycling"],
                    "duration": [1800.0, 3600.0, 7200.0],
                }
            )
        )
        lo, hi = manager.get_duration_bounds()
        assert lo == pytest.approx(30.0)
        assert hi == pytest.approx(120.0)

    def test_bounds_in_hours(self) -> None:
        """Requesting bounds in 'h' returns values in hours."""
        manager = wm.WorkoutManager(
            pd.DataFrame({"activityType": ["Running"], "duration": [7200.0]})
        )
        lo, hi = manager.get_duration_bounds(unit="h")
        assert lo == pytest.approx(2.0)
        assert hi == pytest.approx(2.0)

    def test_bounds_in_seconds(self) -> None:
        """Requesting bounds in 's' returns values in seconds."""
        manager = wm.WorkoutManager(
            pd.DataFrame({"activityType": ["Running"], "duration": [3600.0]})
        )
        lo, hi = manager.get_duration_bounds(unit="s")
        assert lo == pytest.approx(3600.0)
        assert hi == pytest.approx(3600.0)

    def test_unsupported_unit_raises_error(self) -> None:
        """Unsupported unit should raise ValueError."""
        manager = wm.WorkoutManager(
            pd.DataFrame({"activityType": ["Running"], "duration": [3600.0]})
        )
        with pytest.raises(ValueError, match="Unsupported duration unit"):
            manager.get_duration_bounds(unit="days")

    def test_bounds_ignore_nan_and_zero(self) -> None:
        """NaN and zero durations are excluded from bounds calculation."""
        manager = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Rest", "Cycling"],
                    "duration": [3600.0, None, 0.0],
                }
            )
        )
        lo, hi = manager.get_duration_bounds()
        assert lo == pytest.approx(60.0)
        assert hi == pytest.approx(60.0)
