"""Test suite for ExportParser statistics methods"""

import pandas as pd

import logic.workout_manager as wm


class TestGetStatistics:
    """Test suite for ExportParser.get_statistics method."""

    def test_get_statistics_empty_dataframe(self) -> None:
        """Test get_statistics with empty running_workouts DataFrame."""
        workouts = wm.WorkoutManager(pd.DataFrame())

        assert "No workout loaded." in workouts.get_statistics()

    def test_get_statistics_with_workouts_no_distance(self) -> None:
        """Test get_statistics with workouts but no distance column."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running"],
                    "duration": [3600, 1800],
                }
            )
        )

        stats = workouts.get_statistics()

        assert "Total workouts: 2" in stats
        assert "Total duration of 1h 30m 0s." in stats

    def test_get_statistics_with_distance(self) -> None:
        """Test get_statistics with distance column."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running"],
                    "duration": [3600, 3600],
                    "distance": [5000, 10000],
                }
            )
        )

        stats = workouts.get_statistics()

        assert "Total workouts: 2" in stats
        assert "Total distance of 15 km." in stats
        assert "Total duration of 2h 0m 0s." in stats

    def test_get_statistics_duration_calculation(self) -> None:
        """Test duration formatting (hours, minutes, seconds)."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "duration": [3661],  # 1h 1m 1s
                }
            )
        )

        stats = workouts.get_statistics()

        assert "Total duration of 1h 1m 1s." in stats

    def test_get_statistics_single_workout(self) -> None:
        """Test get_statistics with a single workout."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "duration": [1800],
                    "distance": [5500],
                }
            )
        )

        stats = workouts.get_statistics()

        assert "Total workouts: 1" in stats
        assert "Total distance of 6 km." in stats
        assert "Total duration of 0h 30m 0s." in stats

    def test_get_statistics_zero_distance(self) -> None:
        """Test get_statistics with zero total distance."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "duration": [1800],
                    "distance": [0.0],
                }
            )
        )

        stats = workouts.get_statistics()

        assert "Total distance of 0 km." in stats

    def test_get_statistics_large_duration(self) -> None:
        """Test get_statistics with large duration (multiple hours)."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "duration": [36000],  # 10 hours
                }
            )
        )

        stats = workouts.get_statistics()

        assert "Total duration of 10h 0m 0s." in stats
