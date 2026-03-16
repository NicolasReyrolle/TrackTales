"""Test suite for WorkoutManager by_activity methods"""

import pandas as pd

import logic.workout_manager as wm


class TestGetCaloriesByActivity:
    """Test suite for WorkoutManager.get_calories_by_activity method."""

    def test_get_calories_by_activity_empty(self) -> None:
        """Test get_calories_by_activity with empty DataFrame."""
        workouts = wm.WorkoutManager()

        result = workouts.get_calories_by_activity()

        assert result == {}

    def test_get_calories_by_activity_single_activity(self) -> None:
        """Test get_calories_by_activity with a single activity."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "sumActiveEnergyBurned": [250.5],
                }
            )
        )

        result = workouts.get_calories_by_activity()

        assert result == {"Running": 250}

    def test_get_calories_by_activity_multiple_no_grouping(self) -> None:
        """Test get_calories_by_activity with multiple activities, all above threshold."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Cycling", "Swimming"],
                    "sumActiveEnergyBurned": [300.0, 400.0, 300.0],
                }
            )
        )

        result = workouts.get_calories_by_activity()

        # Total = 1000, threshold = 100, all activities >= 100
        assert result == {"Running": 300, "Cycling": 400, "Swimming": 300}

    def test_get_calories_by_activity_with_grouping_default(self) -> None:
        """Test get_calories_by_activity with default 10% threshold grouping."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Cycling", "Walking", "Yoga", "Stretching"],
                    "sumActiveEnergyBurned": [500.0, 300.0, 150.0, 30.0, 20.0],
                }
            )
        )

        result = workouts.get_calories_by_activity()

        # Total = 1000, threshold (10%) = 100
        # Running (500), Cycling (300), Walking (150) stay separate
        # Yoga (30) and Stretching (20) grouped into Others (50)
        assert result == {"Running": 500, "Cycling": 300, "Walking": 150, "Others": 50}

    def test_get_calories_by_activity_custom_threshold(self) -> None:
        """Test get_calories_by_activity with custom threshold."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Cycling", "Walking"],
                    "sumActiveEnergyBurned": [500.0, 300.0, 200.0],
                }
            )
        )

        result = workouts.get_calories_by_activity(combination_threshold=25.0)

        # Total = 1000, threshold (25%) = 250
        # Running (500) and Cycling (300) stay separate
        # Walking (200) grouped into Others
        assert result == {"Running": 500, "Cycling": 300, "Others": 200}

    def test_get_calories_by_activity_zero_threshold(self) -> None:
        """Test get_calories_by_activity with zero threshold (no grouping)."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Cycling", "Walking", "Yoga"],
                    "sumActiveEnergyBurned": [500.0, 300.0, 50.0, 10.0],
                }
            )
        )

        result = workouts.get_calories_by_activity(combination_threshold=0.0)

        # No grouping should occur
        assert result == {"Running": 500, "Cycling": 300, "Walking": 50, "Yoga": 10}

    def test_get_calories_by_activity_negative_threshold(self) -> None:
        """Test get_calories_by_activity with negative threshold (no grouping)."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Walking"],
                    "sumActiveEnergyBurned": [500.0, 50.0],
                }
            )
        )

        result = workouts.get_calories_by_activity(combination_threshold=-5.0)

        # No grouping should occur with negative threshold
        assert result == {"Running": 500, "Walking": 50}

    def test_get_calories_by_activity_missing_activity_column(self) -> None:
        """Test get_calories_by_activity when activityType column is missing."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "duration": [3600],
                    "sumActiveEnergyBurned": [250.0],
                }
            )
        )

        result = workouts.get_calories_by_activity()

        assert result == {}

    def test_get_calories_by_activity_missing_calories_column(self) -> None:
        """Test get_calories_by_activity when sumActiveEnergyBurned column is missing."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "duration": [3600],
                }
            )
        )

        result = workouts.get_calories_by_activity()

        assert result == {}

    def test_get_calories_by_activity_all_below_threshold(self) -> None:
        """Test get_calories_by_activity when smallest values are accumulated."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Walking", "Yoga", "Stretching"],
                    "sumActiveEnergyBurned": [500.0, 50.0, 30.0, 20.0],
                }
            )
        )

        result = workouts.get_calories_by_activity(combination_threshold=10.0)

        # Total = 600, threshold (10%) = 60
        # Sorted: Stretching(20), Yoga(30), Walking(50), Running(500)
        # Cumulative: 20 <= 60 (group), 20+30=50 <= 60 (group), 50+50=100 > 60 (stop)
        # Stretching (20) and Yoga (30) grouped into Others (50)
        assert result == {"Running": 500, "Walking": 50, "Others": 50}

    def test_get_calories_by_activity_aggregates_same_activity(self) -> None:
        """Test get_calories_by_activity aggregates multiple workouts of same activity."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running", "Cycling", "Cycling"],
                    "sumActiveEnergyBurned": [250.0, 250.0, 150.0, 150.0],
                }
            )
        )

        result = workouts.get_calories_by_activity()

        # Total = 800, threshold (10%) = 80
        # Running total: 500, Cycling total: 300
        assert result == {"Running": 500, "Cycling": 300}

    def test_get_calories_by_activity_rounding(self) -> None:
        """Test get_calories_by_activity rounds values correctly."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Cycling"],
                    "sumActiveEnergyBurned": [250.7, 249.3],
                }
            )
        )

        result = workouts.get_calories_by_activity()

        # Values should be rounded: 250.7 -> 251, 249.3 -> 249
        assert result == {"Running": 251, "Cycling": 249}

    def test_get_calories_by_activity_100_percent_threshold(self) -> None:
        """Test get_calories_by_activity with 100% threshold."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Cycling", "Walking"],
                    "sumActiveEnergyBurned": [500.0, 300.0, 200.0],
                }
            )
        )

        result = workouts.get_calories_by_activity(combination_threshold=100.0)

        # Total = 1000, threshold (100%) = 1000
        # All activities < 1000, all grouped into Others
        assert result == {"Others": 1000}

    def test_get_calories_by_activity_boundary_at_threshold(self) -> None:
        """Test get_calories_by_activity with value exactly at threshold."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Cycling", "Walking"],
                    "sumActiveEnergyBurned": [500.0, 400.0, 100.0],
                }
            )
        )

        result = workouts.get_calories_by_activity(combination_threshold=10.0)

        # Total = 1000, threshold (10%) = 100
        # Sorted: Walking(100), Cycling(400), Running(500)
        # Cumulative: Walking(100) <= 100, so Walking is grouped into Others
        assert result == {"Running": 500, "Cycling": 400, "Others": 100}

    def test_get_calories_by_activity_realistic_distribution(self) -> None:
        """Test get_calories_by_activity with realistic activity distribution."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": [
                        "Running",
                        "Walking",
                        "FunctionalStrengthTraining",
                        "Hiking",
                        "TraditionalStrengthTraining",
                        "Swimming",
                        "Cycling",
                        "Badminton",
                        "Elliptical",
                        "Other",
                        "CoreTraining",
                        "SkatingSports",
                    ],
                    "sumActiveEnergyBurned": [
                        6566.0,  # 65.66%
                        1442.0,  # 14.42%
                        720.0,  # 7.20%
                        650.0,  # 6.50%
                        299.0,  # 2.99%
                        139.0,  # 1.39%
                        119.0,  # 1.19%
                        31.0,  # 0.31%
                        21.0,  # 0.21%
                        6.0,  # 0.06%
                        4.0,  # 0.04%
                        3.0,  # 0.03%
                    ],
                }
            )
        )

        result = workouts.get_calories_by_activity(combination_threshold=10.0)

        # Total = 10000, threshold (10%) = 1000
        # Sorted: SkatingSports(3), CoreTraining(4), Other(6), Elliptical(21), Badminton(31),
        #         Cycling(119), Swimming(139), TraditionalStrengthTraining(299), Hiking(650),
        #         FunctionalStrengthTraining(720), Walking(1442), Running(6566)
        # Cumulative grouping: 3+4+6+21+31+119+139+299 = 622 <= 1000 (grouped)
        #                      622+650 = 1272 > 1000 (Hiking and larger stay separate)
        # Result: Running, Walking, FunctionalStrengthTraining, Hiking separate; Others = 622
        assert result == {
            "Running": 6566,
            "Walking": 1442,
            "FunctionalStrengthTraining": 720,
            "Hiking": 650,
            "Others": 622,
        }
        # Verify we have exactly 5 lines
        assert len(result) == 5
        # Verify Others cumulated value
        assert result["Others"] == 299 + 139 + 119 + 31 + 21 + 6 + 4 + 3


class TestGetDistanceByActivity:
    """Test suite for WorkoutManager.get_distance_by_activity method."""

    def test_get_distance_by_activity_empty(self) -> None:
        """Test get_distance_by_activity with empty DataFrame."""
        workouts = wm.WorkoutManager()

        result = workouts.get_distance_by_activity()

        assert result == {}

    def test_get_distance_by_activity_missing_column(self) -> None:
        """Test get_distance_by_activity when distance column is missing."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "duration": [3600],
                }
            )
        )

        result = workouts.get_distance_by_activity()

        assert result == {}

    def test_get_distance_by_activity_single_activity(self) -> None:
        """Test get_distance_by_activity with single activity."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "distance": [5000],  # 5000 meters = 5 km
                }
            )
        )

        result = workouts.get_distance_by_activity()

        assert result == {"Running": 5}  # Default unit is km

    def test_get_distance_by_activity_multiple_activities(self) -> None:
        """Test get_distance_by_activity with multiple activities."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Cycling", "Walking"],
                    "distance": [5000, 10000, 3000],  # distances in meters
                }
            )
        )

        result = workouts.get_distance_by_activity()

        # All values converted from meters to km (default unit)
        assert result == {"Running": 5, "Cycling": 10, "Walking": 3}

    def test_get_distance_by_activity_with_grouping(self) -> None:
        """Test get_distance_by_activity with threshold grouping."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Cycling", "Walking", "Yoga"],
                    "distance": [10000, 5000, 500, 200],  # distances in meters
                }
            )
        )

        result = workouts.get_distance_by_activity(combination_threshold=5.0)

        # Total = 15700 m = 15.7 km, threshold (5%) = 0.785 km
        # Sorted by value: Yoga(0.2km), Walking(0.5km), Cycling(5km), Running(10km)
        # Cumulative: 0.2+0.5 = 0.7km <= 0.785km, grouped into Others (rounds to 1 km)
        assert result == {"Running": 10, "Cycling": 5, "Others": 1}


class TestGetCountByActivity:
    """Test suite for WorkoutManager.get_count_by_activity method."""

    def test_get_count_by_activity_empty(self) -> None:
        """Test get_count_by_activity with empty DataFrame."""
        workouts = wm.WorkoutManager()

        result = workouts.get_count_by_activity()

        assert result == {}

    def test_get_count_by_activity_single_activity(self) -> None:
        """Test get_count_by_activity with single activity."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                }
            )
        )

        result = workouts.get_count_by_activity()

        assert result == {"Running": 1}

    def test_get_count_by_activity_multiple_workouts_same_type(self) -> None:
        """Test get_count_by_activity aggregates same activity type."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running", "Running"],
                }
            )
        )

        result = workouts.get_count_by_activity()

        assert result == {"Running": 3}

    def test_get_count_by_activity_multiple_activities(self) -> None:
        """Test get_count_by_activity with multiple activities."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running", "Cycling", "Walking", "Walking"],
                }
            )
        )

        result = workouts.get_count_by_activity()

        assert result == {"Running": 2, "Cycling": 1, "Walking": 2}

    def test_get_count_by_activity_with_grouping(self) -> None:
        """Test get_count_by_activity with threshold grouping."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"] * 50
                    + ["Cycling"] * 30
                    + ["Walking"] * 10
                    + ["Yoga"] * 5
                    + ["Swimming"] * 5,
                }
            )
        )

        result = workouts.get_count_by_activity(combination_threshold=10.0)

        # Total = 100, threshold (10%) = 10
        # Sorted: Yoga(5), Swimming(5), Walking(10), Cycling(30), Running(50)
        # Cumulative: 5+5 = 10 <= 10, grouped into Others
        assert result == {"Running": 50, "Cycling": 30, "Walking": 10, "Others": 10}


class TestGetDurationByActivity:
    """Test suite for WorkoutManager.get_duration_by_activity method."""

    def test_get_duration_by_activity_empty(self) -> None:
        """Test get_duration_by_activity with empty DataFrame."""
        workouts = wm.WorkoutManager()

        result = workouts.get_duration_by_activity()

        assert result == {}

    def test_get_duration_by_activity_missing_column(self) -> None:
        """Test get_duration_by_activity when duration column is missing."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "distance": [5000],
                }
            )
        )

        result = workouts.get_duration_by_activity()

        assert result == {}

    def test_get_duration_by_activity_single_activity(self) -> None:
        """Test get_duration_by_activity with single activity."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "duration": [3600],
                }
            )
        )

        result = workouts.get_duration_by_activity()

        assert result == {"Running": 1}

    def test_get_duration_by_activity_multiple_activities(self) -> None:
        """Test get_duration_by_activity with multiple activities."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Cycling", "Walking"],
                    "duration": [3600, 7200, 900],
                }
            )
        )

        result = workouts.get_duration_by_activity()
        # Walking is 900s = 0.25h, rounds to 0 hours, so it should be excluded
        assert result == {"Running": 1, "Cycling": 2}

    def test_get_duration_by_activity_aggregates_same_type(self) -> None:
        """Test get_duration_by_activity aggregates same activity type."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running", "Cycling"],
                    "duration": [3600, 1800, 3600],
                }
            )
        )

        result = workouts.get_duration_by_activity()

        # Running total: 3600 + 1800 = 5400 seconds = 1.5 hours rounded to 2
        assert result == {"Running": 2, "Cycling": 1}

    def test_get_duration_by_activity_with_grouping(self) -> None:
        """Test get_duration_by_activity with threshold grouping."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Cycling", "Walking", "Yoga"],
                    "duration": [10000, 5000, 500, 200],
                }
            )
        )

        result = workouts.get_duration_by_activity(combination_threshold=5.0)

        # Total = 15700, threshold (5%) = 785
        # Sorted: Yoga(200), Walking(500), Cycling(5000), Running(10000)
        # Cumulative: 200+500 = 700 <= 785, grouped into Others, but not shown as rounded to 0
        assert result == {"Running": 3, "Cycling": 1}


class TestGetElevationByActivity:
    """Test suite for WorkoutManager.get_elevation_by_activity method."""

    def test_get_elevation_by_activity_empty(self) -> None:
        """Test get_elevation_by_activity with empty DataFrame."""
        workouts = wm.WorkoutManager()

        result = workouts.get_elevation_by_activity()

        assert result == {}

    def test_get_elevation_by_activity_missing_column(self) -> None:
        """Test get_elevation_by_activity when ElevationAscended column is missing."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "duration": [3600],
                }
            )
        )

        result = workouts.get_elevation_by_activity()

        assert result == {}

    def test_get_elevation_by_activity_single_activity(self) -> None:
        """Test get_elevation_by_activity with single activity."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Hiking"],
                    "ElevationAscended": [5000],
                }
            )
        )

        result = workouts.get_elevation_by_activity(unit="km")

        assert result == {"Hiking": 5}

    def test_get_elevation_by_activity_multiple_activities(self) -> None:
        """Test get_elevation_by_activity with multiple activities."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Hiking", "Running", "Cycling"],
                    "ElevationAscended": [8000, 1400, 2000],
                }
            )
        )

        result = workouts.get_elevation_by_activity(unit="km")

        assert result == {"Hiking": 8, "Cycling": 2, "Running": 1}

    def test_get_elevation_by_activity_aggregates_same_type(self) -> None:
        """Test get_elevation_by_activity aggregates same activity type."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Hiking", "Hiking", "Running"],
                    "ElevationAscended": [5000, 3000, 1000],
                }
            )
        )

        result = workouts.get_elevation_by_activity(unit="km")

        # Hiking total: 5000 + 3000 = 8000
        assert result == {"Hiking": 8, "Running": 1}

    def test_get_elevation_by_activity_with_grouping(self) -> None:
        """Test get_elevation_by_activity with threshold grouping."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Hiking", "Running", "Walking", "Cycling"],
                    "ElevationAscended": [5000, 3000, 500, 200],
                }
            )
        )

        result = workouts.get_elevation_by_activity(combination_threshold=10.0, unit="km")

        # Total = 8700, threshold (10%) = 870
        # Sorted: Cycling(200), Walking(500), Running(3000), Hiking(5000)
        # Cumulative: 200+500 = 700 <= 870, grouped into Others
        assert result == {"Hiking": 5, "Running": 3, "Others": 1}

    def test_get_elevation_by_activity_zero_elevation(self) -> None:
        """Test get_elevation_by_activity with zero elevation."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "ElevationAscended": [0],
                }
            )
        )

        result = workouts.get_elevation_by_activity()

        assert result == {"Running": 0}
