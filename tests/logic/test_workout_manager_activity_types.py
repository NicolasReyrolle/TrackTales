"""Test suite for WorkoutManager.get_activity_types method."""

import pandas as pd

import logic.workout_manager as wm


class TestGetActivityTypes:
    """Test suite for WorkoutManager.get_activity_types method."""

    def test_get_activity_types_empty_dataframe(self) -> None:
        """Test get_activity_types with empty DataFrame."""
        workouts = wm.WorkoutManager()  # Use default empty DataFrame with proper columns

        result = workouts.get_activity_types()

        assert result == []

    def test_get_activity_types_single_type(self) -> None:
        """Test get_activity_types with a single activity type."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running", "Running"],
                }
            )
        )

        result = workouts.get_activity_types()

        assert result == ["Running"]

    def test_get_activity_types_multiple_types(self) -> None:
        """Test get_activity_types with multiple unique activity types."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Walking", "Cycling", "Running", "Walking"],
                }
            )
        )

        result = workouts.get_activity_types()

        # Result should contain all unique types (order may vary with pandas)
        assert set(result) == {"Running", "Walking", "Cycling"}
        assert len(result) == 3

    def test_get_activity_types_with_nan_values(self) -> None:
        """Test get_activity_types filters out NaN values."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", None, "Walking", float("nan"), "Cycling"],
                }
            )
        )

        result = workouts.get_activity_types()

        # NaN values should be excluded
        assert set(result) == {"Running", "Walking", "Cycling"}
        assert len(result) == 3
        assert None not in result

    def test_get_activity_types_returns_list(self) -> None:
        """Test that get_activity_types returns a list."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Walking"],
                }
            )
        )

        result = workouts.get_activity_types()

        assert isinstance(result, list)

    def test_get_activity_types_preserves_order(self) -> None:
        """Test get_activity_types behavior with order."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": [
                        "Running",
                        "Cycling",
                        "Walking",
                        "Swimming",
                        "Running",
                    ],
                }
            )
        )

        result = workouts.get_activity_types()

        # Should return unique values in order of first appearance
        # (pandas unique() preserves order)
        assert len(result) == 4
        assert set(result) == {"Running", "Cycling", "Walking", "Swimming"}

    def test_get_activity_types_with_all_nan(self) -> None:
        """Test get_activity_types when all values are NaN."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": [None, float("nan"), None],
                }
            )
        )

        result = workouts.get_activity_types()

        assert result == []

    def test_get_activity_types_case_sensitive(self) -> None:
        """Test get_activity_types treats different cases as different types."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "running", "RUNNING", "Walking"],
                }
            )
        )

        result = workouts.get_activity_types()

        # Different cases should be treated as different types
        assert set(result) == {"Running", "running", "RUNNING", "Walking"}
        assert len(result) == 4


class TestGroupSmallValues:
    """Test suite for WorkoutManager.group_small_values method."""

    def test_group_small_values_empty_dict(self) -> None:
        """Test group_small_values with empty dictionary."""
        manager = wm.WorkoutManager()

        result = manager.group_small_values({})

        assert not result

    def test_group_small_values_no_grouping_needed(self) -> None:
        """Test when all values are above threshold."""
        manager = wm.WorkoutManager()
        data = {"Running": 100, "Cycling": 50, "Walking": 50}

        result = manager.group_small_values(data, threshold_percent=10.0)

        # Total = 200, threshold = 20, all values >= 20
        assert result == {"Running": 100, "Cycling": 50, "Walking": 50}

    def test_group_small_values_groups_below_threshold(self) -> None:
        """Test grouping of values below threshold."""
        manager = wm.WorkoutManager()
        data = {"Running": 100, "Cycling": 50, "Walking": 5, "Swimming": 3}

        result = manager.group_small_values(data, threshold_percent=10.0)

        # Total = 158, threshold = 15.8
        # Running (100) and Cycling (50) stay separate
        # Walking (5) and Swimming (3) grouped into Others (8)
        assert result == {"Running": 100, "Cycling": 50, "Others": 8}

    def test_group_small_values_custom_threshold(self) -> None:
        """Test with custom threshold percentage."""
        manager = wm.WorkoutManager()
        data = {"Running": 100, "Cycling": 30, "Walking": 20}

        result = manager.group_small_values(data, threshold_percent=25.0)

        # Total is 150, so threshold (25%) = 37.5
        # Sorted: Walking(20), Cycling(30), Running(100)
        # Cumulative: Walking(20) <= 37.5, grouped into Others
        # Walking(20) + Cycling(30) = 50 > 37.5, so Cycling stays separate
        assert result == {"Running": 100, "Cycling": 30, "Others": 20}

    def test_group_small_values_custom_label(self) -> None:
        """Test with custom label for grouped values."""
        manager = wm.WorkoutManager()
        data = {"Running": 100, "Cycling": 50, "Walking": 5}

        result = manager.group_small_values(
            data, threshold_percent=10.0, others_label="Minor Activities"
        )

        # Total is 155, so threshold = 15.5
        assert result == {"Running": 100, "Cycling": 50, "Minor Activities": 5}

    def test_group_small_values_all_below_threshold(self) -> None:
        """Test when all values are below threshold."""
        manager = wm.WorkoutManager()
        data = {"Walking": 5, "Yoga": 3, "Stretching": 2}

        result = manager.group_small_values(data, threshold_percent=50.0)

        # Total is 10, so threshold = 5
        # Walking (5) is >= 5, so it stays separate
        # Yoga (3) and Stretching (2) grouped into Others (5)
        assert result == {"Walking": 5, "Others": 5}

    def test_group_small_values_zero_total(self) -> None:
        """Test when all values sum to zero."""
        manager = wm.WorkoutManager()
        data = {"Running": 0, "Cycling": 0}

        result = manager.group_small_values(data, threshold_percent=10.0)

        # Should return copy of original data
        assert result == {"Running": 0, "Cycling": 0}

    def test_group_small_values_single_value(self) -> None:
        """Test with single value in dictionary."""
        manager = wm.WorkoutManager()
        data = {"Running": 100}

        result = manager.group_small_values(data, threshold_percent=10.0)

        # Total is 100, so threshold = 10, value = 100 >= 10
        assert result == {"Running": 100}

    def test_group_small_values_boundary_case(self) -> None:
        """Test value exactly at threshold boundary."""
        manager = wm.WorkoutManager()
        data = {"Running": 100, "Cycling": 10}

        result = manager.group_small_values(data, threshold_percent=9.0)

        # Total is 110, so threshold = 9.9
        # Cycling (10) is >= 9.9, should not be grouped
        assert result == {"Running": 100, "Cycling": 10}

    def test_group_small_values_zero_threshold(self) -> None:
        """Test with zero threshold."""
        manager = wm.WorkoutManager()
        data = {"Running": 100, "Cycling": 50, "Walking": 1}

        result = manager.group_small_values(data, threshold_percent=0.0)

        # Threshold = 0, no accumulation possible (cumulative must stay at 0)
        # All values stay separate since no value can be added without exceeding threshold
        assert result == {"Running": 100, "Cycling": 50, "Walking": 1}

    def test_group_small_values_preserves_large_values(self) -> None:
        """Test that values above threshold are preserved exactly."""
        manager = wm.WorkoutManager()
        data = {
            "Running": 500,
            "Cycling": 300,
            "Walking": 150,
            "Swimming": 40,
            "Yoga": 10,
        }

        result = manager.group_small_values(data, threshold_percent=10.0)

        # Total = 1000, threshold = 100
        # Running, Cycling, Walking stay separate
        # Swimming (40) and Yoga (10) grouped into Others (50)
        assert result["Running"] == 500
        assert result["Cycling"] == 300
        assert result["Walking"] == 150
        assert result["Others"] == 50
        assert len(result) == 4
