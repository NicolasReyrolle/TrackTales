"""Test suite for WorkoutManager core methods (count, get_workouts)"""

import pandas as pd

import logic.workout_manager as wm


class TestCount:
    """Test suite for WorkoutManager.get_count method."""

    def test_count_empty(self) -> None:
        """Test count with empty DataFrame."""
        workouts = wm.WorkoutManager()

        assert workouts.get_count() == 0
        assert workouts.get_count("All") == 0

    def test_count_single_workout(self) -> None:
        """Test count with a single workout."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                }
            )
        )

        assert workouts.get_count() == 1

    def test_count_multiple_workouts(self) -> None:
        """Test count with multiple workouts."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Cycling", "Swimming"],
                }
            )
        )

        assert workouts.get_count() == 3
        assert workouts.get_count("All") == 3

    def test_count_filter_by_activity(self) -> None:
        """Test count filters by activity type."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running", "Cycling", "Swimming"],
                }
            )
        )

        assert workouts.get_count() == 4
        assert workouts.get_count("Running") == 2
        assert workouts.get_count("Cycling") == 1
        assert workouts.get_count("Swimming") == 1

    def test_count_nonexistent_activity(self) -> None:
        """Test count with non-existent activity type."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Cycling"],
                }
            )
        )

        assert workouts.get_count("Walking") == 0


class TestGetWorkouts:
    """Test suite for WorkoutManager.get_workouts method."""

    def test_get_workouts_empty(self) -> None:
        """Test get_workouts with empty DataFrame."""
        workouts = wm.WorkoutManager()
        result = workouts.get_workouts()

        assert isinstance(result, pd.DataFrame)
        assert result.empty

    def test_get_workouts_returns_dataframe(self) -> None:
        """Test get_workouts returns the internal DataFrame."""
        df = pd.DataFrame(
            {
                "activityType": ["Running", "Cycling"],
                "duration": [3600, 1800],
            }
        )
        workouts = wm.WorkoutManager(df)
        result = workouts.get_workouts()

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2
        assert list(result["activityType"]) == ["Running", "Cycling"]

    def test_get_workouts_preserves_data(self) -> None:
        """Test get_workouts preserves all columns and data."""
        df = pd.DataFrame(
            {
                "activityType": ["Running"],
                "duration": [3600],
                "distance": [5000],
                "startDate": ["2024-01-01"],
            }
        )
        workouts = wm.WorkoutManager(df)
        result = workouts.get_workouts()

        assert "activityType" in result.columns
        assert "duration" in result.columns
        assert "distance" in result.columns
        assert "startDate" in result.columns
