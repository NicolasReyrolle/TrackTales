"""Test suite for WorkoutManager total aggregation methods"""

import numpy as np
import pandas as pd
import pytest

import logic.workout_manager as wm


class TestGetTotalDistance:
    """Test suite for WorkoutManager.get_total_distance method."""

    def test_get_total_distance_empty(self) -> None:
        """Test get_total_distance with empty DataFrame."""
        workouts = wm.WorkoutManager()

        assert workouts.get_total_distance() == 0

    def test_get_total_distance_single_workout(self) -> None:
        """Test get_total_distance with a single workout."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "distance": [5500],
                }
            )
        )

        assert workouts.get_total_distance() == 6  # 5.5 rounded to 6

    def test_get_total_distance_multiple_workouts(self) -> None:
        """Test get_total_distance with multiple workouts."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Cycling", "Swimming"],
                    "distance": [5000, 10000, 3500],
                }
            )
        )

        assert workouts.get_total_distance() == 18  # 5 + 10 + 3.5 = 18.5 rounded to 18

    def test_get_total_distance_filter_activity(self) -> None:
        """Test get_total_distance with activity type filter."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running", "Cycling"],
                    "distance": [5000, 7000, 20000],
                }
            )
        )

        assert workouts.get_total_distance("Running") == 12
        assert workouts.get_total_distance("Cycling") == 20

    def test_get_total_distance_all_keyword(self) -> None:
        """Test get_total_distance with 'All' keyword returns all activities."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Walking", "Cycling"],
                    "distance": [5000, 3000, 15000],
                }
            )
        )

        assert workouts.get_total_distance("All") == 23

    def test_get_total_distance_no_match(self) -> None:
        """Test get_total_distance with activity type that doesn't exist."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Cycling"],
                    "distance": [5000, 10000],
                }
            )
        )

        assert workouts.get_total_distance("Swimming") == 0

    def test_get_total_distance_zero_distance(self) -> None:
        """Test get_total_distance with zero total distance."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Walking"],
                    "distance": [0.0, 0.0],
                }
            )
        )

        assert workouts.get_total_distance() == 0

    def test_get_total_distance_kilometers(self) -> None:
        """Test get_total_distance returns km by default and when specified."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Cycling"],
                    "distance": [1500, 2500],  # meters
                }
            )
        )
        # 1500 + 2500 = 4000 meters = 4 km
        assert workouts.get_total_distance(unit="km") == 4

    def test_get_total_distance_meters(self) -> None:
        """Test get_total_distance returns meters when specified."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Cycling"],
                    "distance": [1500, 2500],
                }
            )
        )
        assert workouts.get_total_distance(unit="m") == 4000

    def test_get_total_distance_miles(self) -> None:
        """Test get_total_distance returns miles when specified."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Cycling"],
                    "distance": [1609.34, 3218.68],  # 1 mi + 2 mi in meters
                }
            )
        )
        # 1609.34 + 3218.68 = 4828.02 meters = 3 miles
        assert workouts.get_total_distance(unit="mi") == 3

    def test_get_total_distance_invalid_unit(self) -> None:
        """Test get_total_distance with invalid unit raises ValueError."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "distance": [1000],
                }
            )
        )
        with pytest.raises(ValueError, match="Unsupported unit"):
            workouts.get_total_distance(unit="yd")

    def test_get_total_distance_no_distance_column(self) -> None:
        """Test get_total_distance when distance column is missing."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Cycling"],
                    "duration": [3600, 1800],
                }
            )
        )

        assert workouts.get_total_distance() == 0

    def test_get_total_distance_large_values(self) -> None:
        """Test get_total_distance with large distance values."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Cycling"],
                    "distance": [100500, 250750],
                }
            )
        )

        assert workouts.get_total_distance() == 351  # 100.5 + 250.75 = 351.25 rounded to 351

    def test_get_total_distance_rounding(self) -> None:
        """Test rounding behavior of get_total_distance."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Walking"],
                    "distance": [5400, 2400],  # Total: 7.8, should round to 8
                }
            )
        )

        assert workouts.get_total_distance() == 8

    def test_get_total_distance_rounding_down(self) -> None:
        """Test rounding down behavior of get_total_distance."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Walking"],
                    "distance": [5200, 2100],  # Total: 7.3, should round to 7
                }
            )
        )

        assert workouts.get_total_distance() == 7


class TestGetTotalDuration:
    """Test suite for WorkoutManager.get_total_duration method."""

    def test_get_total_duration_empty(self) -> None:
        """Test get_total_duration with empty DataFrame."""
        workouts = wm.WorkoutManager()

        assert workouts.get_total_duration() == 0

    def test_get_total_duration_single_hour(self) -> None:
        """Test get_total_duration with a single 1-hour workout."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "duration": [3600],  # 1 hour in seconds
                }
            )
        )

        assert workouts.get_total_duration() == 1

    def test_get_total_duration_multiple_workouts(self) -> None:
        """Test get_total_duration with multiple workouts."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Walking", "Cycling"],
                    "duration": [3600, 1800, 7200],  # 1h + 30m + 2h = 3.5h → 4
                }
            )
        )

        assert workouts.get_total_duration() == 4

    def test_get_total_duration_filter_activity(self) -> None:
        """Test get_total_duration filters by activity type."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running", "Walking"],
                    "duration": [3600, 3600, 3600],  # 1h each
                }
            )
        )

        assert workouts.get_total_duration() == 3
        assert workouts.get_total_duration("All") == 3
        assert workouts.get_total_duration("Running") == 2
        assert workouts.get_total_duration("Walking") == 1

    def test_get_total_duration_no_match(self) -> None:
        """Test get_total_duration with non-existent activity type."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Walking"],
                    "duration": [3600, 3600],
                }
            )
        )

        assert workouts.get_total_duration("Swimming") == 0

    def test_get_total_duration_partial_hour(self) -> None:
        """Test get_total_duration rounds to nearest hour."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "duration": [5400],  # 1.5 hours → 2 hours
                }
            )
        )

        assert workouts.get_total_duration() == 2

    def test_get_total_duration_no_duration_column(self) -> None:
        """Test get_total_duration when duration column doesn't exist."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                }
            )
        )

        assert workouts.get_total_duration() == 0

    def test_get_total_duration_large_values(self) -> None:
        """Test get_total_duration with large duration values."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "duration": [36000],  # 10 hours
                }
            )
        )

        assert workouts.get_total_duration() == 10


class TestGetTotalElevation:
    """Test suite for WorkoutManager.get_total_elevation method."""

    def test_get_total_elevation_empty(self) -> None:
        """Test get_total_elevation with empty DataFrame."""
        workouts = wm.WorkoutManager()

        assert workouts.get_total_elevation() == 0

    def test_get_total_elevation_single_workout(self) -> None:
        """Test get_total_elevation with a single workout."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "ElevationAscended": [150.0],
                }
            )
        )

        assert workouts.get_total_elevation() == 0

    def test_get_total_elevation_multiple_workouts(self) -> None:
        """Test get_total_elevation with multiple workouts."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Hiking", "Cycling"],
                    "ElevationAscended": [800.0, 250.0, 50.0],  # Total 1.1 km
                }
            )
        )

        assert workouts.get_total_elevation() == 1

    def test_get_total_elevation_filter_activity(self) -> None:
        """Test get_total_elevation filters by activity type."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Hiking", "Hiking", "Cycling"],
                    "ElevationAscended": [150.0, 250.0, 800.0],
                }
            )
        )

        assert workouts.get_total_elevation() == 1
        assert workouts.get_total_elevation("All") == 1
        assert workouts.get_total_elevation("Hiking") == 0
        assert workouts.get_total_elevation("Cycling") == 1

    def test_get_total_elevation_no_match(self) -> None:
        """Test get_total_elevation with non-existent activity type."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Hiking"],
                    "ElevationAscended": [150.0],
                }
            )
        )

        assert workouts.get_total_elevation("Swimming") == 0

    def test_get_total_elevation_zero(self) -> None:
        """Test get_total_elevation with zero elevation."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "ElevationAscended": [0.0],
                }
            )
        )

        assert workouts.get_total_elevation() == 0

    def test_get_total_elevation_rounding(self) -> None:
        """Test get_total_elevation rounds to nearest integer."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Hiking"],
                    "ElevationAscended": [1557],  # Should round to 2
                }
            )
        )

        assert workouts.get_total_elevation() == 2

    def test_get_total_elevation_no_column(self) -> None:
        """Test get_total_elevation when ElevationAscended column doesn't exist."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Hiking"],
                    "duration": [3600],
                }
            )
        )

        assert workouts.get_total_elevation() == 0

    def test_get_total_elevation_large_values(self) -> None:
        """Test get_total_elevation with large elevation values."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Hiking"],
                    "ElevationAscended": [2500.6],  # Mountain climb (rounds to 3)
                }
            )
        )

        assert workouts.get_total_elevation() == 3

    def test_get_total_elevation_unit_km(self) -> None:
        """Test get_total_elevation with km unit (default)."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Hiking"],
                    "ElevationAscended": [1500.0],  # 1.5 km
                }
            )
        )

        assert workouts.get_total_elevation(unit="km") == 2
        assert workouts.get_total_elevation() == 2  # Default is km

    def test_get_total_elevation_unit_m(self) -> None:
        """Test get_total_elevation with meters unit."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Hiking"],
                    "ElevationAscended": [1557.0],  # 1557 meters
                }
            )
        )

        assert workouts.get_total_elevation(unit="m") == 1557

    def test_get_total_elevation_unit_mi(self) -> None:
        """Test get_total_elevation with miles unit."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Hiking"],
                    "ElevationAscended": [1609.34],  # 1 mile in meters
                }
            )
        )

        assert workouts.get_total_elevation(unit="mi") == 1

    def test_get_total_elevation_invalid_unit(self) -> None:
        """Test get_total_elevation with invalid unit raises ValueError."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Hiking"],
                    "ElevationAscended": [1000.0],
                }
            )
        )

        with pytest.raises(ValueError, match="Unsupported unit"):
            workouts.get_total_elevation(unit="yards")


class TestGetTotalCalories:
    """Test suite for WorkoutManager.get_total_calories method."""

    def test_get_total_calories_empty(self) -> None:
        """Test get_total_calories with empty DataFrame."""
        workouts = wm.WorkoutManager()

        assert workouts.get_total_calories() == 0

    def test_get_total_calories_single_workout(self) -> None:
        """Test get_total_calories with a single workout."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "sumActiveEnergyBurned": [250.5],
                }
            )
        )

        assert workouts.get_total_calories() == 250  # 250.5 rounded to nearest int

    def test_get_total_calories_multiple_workouts(self) -> None:
        """Test get_total_calories with multiple workouts."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Cycling", "Swimming"],
                    "sumActiveEnergyBurned": [300.0, 400.5, 200.3],
                }
            )
        )

        assert workouts.get_total_calories() == 901  # 300 + 400.5 + 200.3 = 900.8 → 901

    def test_get_total_calories_filter_activity(self) -> None:
        """Test get_total_calories filters by activity type."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running", "Cycling"],
                    "sumActiveEnergyBurned": [300.0, 250.0, 500.0],
                }
            )
        )

        assert workouts.get_total_calories() == 1050
        assert workouts.get_total_calories("Running") == 550
        assert workouts.get_total_calories("Cycling") == 500

    def test_get_total_calories_all_keyword(self) -> None:
        """Test get_total_calories with 'All' keyword returns all activities."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Walking", "Cycling"],
                    "sumActiveEnergyBurned": [300.0, 150.0, 400.0],
                }
            )
        )

        assert workouts.get_total_calories("All") == 850

    def test_get_total_calories_no_match(self) -> None:
        """Test get_total_calories with non-existent activity type."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Cycling"],
                    "sumActiveEnergyBurned": [300.0, 400.0],
                }
            )
        )

        assert workouts.get_total_calories("Swimming") == 0

    def test_get_total_calories_zero(self) -> None:
        """Test get_total_calories with zero calories."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "sumActiveEnergyBurned": [0.0],
                }
            )
        )

        assert workouts.get_total_calories() == 0

    def test_get_total_calories_rounding_up(self) -> None:
        """Test get_total_calories rounds up correctly."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Walking"],
                    "sumActiveEnergyBurned": [250.7, 249.6],
                }
            )
        )

        assert workouts.get_total_calories() == 500  # 250.7 + 249.6 = 500.3 → 500

    def test_get_total_calories_rounding_down(self) -> None:
        """Test get_total_calories rounds down correctly."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Walking"],
                    "sumActiveEnergyBurned": [250.2, 249.2],
                }
            )
        )

        assert workouts.get_total_calories() == 499  # 250.2 + 249.2 = 499.4 → 499

    def test_get_total_calories_no_column(self) -> None:
        """Test get_total_calories when sumActiveEnergyBurned column missing."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "duration": [3600],
                }
            )
        )

        assert workouts.get_total_calories() == 0

    def test_get_total_calories_large_values(self) -> None:
        """Test get_total_calories with large calorie values."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "sumActiveEnergyBurned": [5000.75],
                }
            )
        )

        assert workouts.get_total_calories() == 5001

    def test_get_total_calories_multiple_same_activity(self) -> None:
        """Test get_total_calories with multiple workouts of same activity type."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running", "Running"],
                    "sumActiveEnergyBurned": [250.0, 300.0, 275.5],
                }
            )
        )

        assert workouts.get_total_calories("Running") == 826  # 250 + 300 + 275.5 = 825.5 → 826
        assert workouts.get_total_calories() == 826


class TestGetLongestWorkout:
    """Test suite for WorkoutManager.get_longest_workout method."""

    def test_get_longest_workout_empty(self) -> None:
        """Test get_longest_workout with empty DataFrame."""
        workouts = wm.WorkoutManager()

        assert workouts.get_longest_workout(["Running"]) == pytest.approx(0.0)  # type: ignore[misc]

    def test_get_longest_workout_single_match(self) -> None:
        """Test get_longest_workout with a single matching workout."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "distance": [10000],  # 10 km
                }
            )
        )

        assert workouts.get_longest_workout(["Running"]) == pytest.approx(  # type: ignore[misc]
            10.0
        )

    def test_get_longest_workout_multiple_activities_picks_max(self) -> None:
        """Test get_longest_workout returns the longest workout distance."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running", "Running"],
                    "distance": [5000, 12000, 8000],
                }
            )
        )

        assert workouts.get_longest_workout(["Running"]) == pytest.approx(  # type: ignore[misc]
            12.0
        )

    def test_get_longest_workout_filters_by_activity_type(self) -> None:
        """Test get_longest_workout only considers the specified activity types."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Cycling", "Walking"],
                    "distance": [5000, 50000, 3000],
                }
            )
        )

        assert workouts.get_longest_workout(["Running"]) == pytest.approx(5.0)  # type: ignore[misc]
        assert workouts.get_longest_workout(["Cycling"]) == pytest.approx(  # type: ignore[misc]
            50.0
        )
        assert workouts.get_longest_workout(["Walking"]) == pytest.approx(3.0)  # type: ignore[misc]

    def test_get_longest_workout_multiple_activity_types(self) -> None:
        """Test get_longest_workout with multiple activity types."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Walking", "Hiking", "Running"],
                    "distance": [4000, 9000, 6000],
                }
            )
        )

        expected = pytest.approx(9.0)  # type: ignore[misc]
        assert workouts.get_longest_workout(["Walking", "Hiking"]) == expected

    def test_get_longest_workout_no_match(self) -> None:
        """Test get_longest_workout with no matching activity type returns 0."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "distance": [5000],
                }
            )
        )

        assert workouts.get_longest_workout(["Cycling"]) == pytest.approx(0.0)  # type: ignore[misc]

    def test_get_longest_workout_no_distance_column(self) -> None:
        """Test get_longest_workout when distance column is missing returns 0."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "duration": [3600],
                }
            )
        )

        assert workouts.get_longest_workout(["Running"]) == pytest.approx(0.0)  # type: ignore[misc]

    def test_get_longest_workout_unit_km(self) -> None:
        """Test get_longest_workout returns km by default."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "distance": [15000],  # 15 km
                }
            )
        )

        expected = pytest.approx(15.0)  # type: ignore[misc]
        assert workouts.get_longest_workout(["Running"], unit="km") == expected

    def test_get_longest_workout_unit_miles(self) -> None:
        """Test get_longest_workout returns miles when specified."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "distance": [1609.34],  # 1 mile
                }
            )
        )

        expected = pytest.approx(1.0)  # type: ignore[misc]
        assert workouts.get_longest_workout(["Running"], unit="mi") == expected

    def test_get_longest_workout_empty_activity_types_list(self) -> None:
        """Test get_longest_workout with empty activity types list returns 0."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "distance": [5000],
                }
            )
        )

        assert workouts.get_longest_workout([]) == pytest.approx(0.0)  # type: ignore[misc]


class TestGetLongestWorkoutDetails:
    """Test suite for WorkoutManager.get_longest_workout_details method."""

    def test_get_longest_workout_details_empty(self) -> None:
        """Test returns None for empty DataFrame."""
        workouts = wm.WorkoutManager()
        assert workouts.get_longest_workout_details(["Running"]) is None

    def test_get_longest_workout_details_no_match(self) -> None:
        """Test returns None when no matching activity type exists."""
        workouts = wm.WorkoutManager(
            pd.DataFrame({"activityType": ["Running"], "distance": [5000], "duration": [3600]})
        )
        assert workouts.get_longest_workout_details(["Cycling"]) is None

    def test_get_longest_workout_details_returns_max_row(self) -> None:
        """Test returns details of the single longest workout."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running"],
                    "distance": [5000, 12000],
                    "duration": [1800.0, 3600.0],
                    "startDate": pd.to_datetime(["2024-01-01", "2024-02-15"]),
                }
            )
        )
        result = workouts.get_longest_workout_details(["Running"])
        assert result is not None
        assert result["distance"] == pytest.approx(12.0)  # type: ignore[misc]
        assert result["duration"] == pytest.approx(3600.0)  # type: ignore[misc]

    def test_get_longest_workout_details_multiple_activity_types(self) -> None:
        """Test returns the longest workout across multiple activity types."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Walking", "Hiking"],
                    "distance": [4000, 9000],
                    "duration": [2400.0, 5400.0],
                    "startDate": pd.to_datetime(["2024-03-01", "2024-04-10"]),
                }
            )
        )
        result = workouts.get_longest_workout_details(["Walking", "Hiking"])
        assert result is not None
        assert result["distance"] == pytest.approx(9.0)  # type: ignore[misc]
        assert result["duration"] == pytest.approx(5400.0)  # type: ignore[misc]

    def test_get_longest_workout_details_missing_duration_column(self) -> None:
        """Test returns None duration when duration column is absent."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "distance": [10000],
                    "startDate": pd.to_datetime(["2024-05-01"]),
                }
            )
        )
        result = workouts.get_longest_workout_details(["Running"])
        assert result is not None
        assert result["distance"] == pytest.approx(10.0)  # type: ignore[misc]
        assert result["duration"] is None

    def test_get_longest_workout_details_unit_miles(self) -> None:
        """Test distance is converted to the requested unit."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "distance": [1609.34],  # 1 mile
                    "duration": [600.0],
                    "startDate": pd.to_datetime(["2024-06-01"]),
                }
            )
        )
        result = workouts.get_longest_workout_details(["Running"], unit="mi")
        assert result is not None
        assert result["distance"] == pytest.approx(1.0)  # type: ignore[misc]

    def test_get_longest_workout_details_nan_duration(self) -> None:
        """Test returns None for duration when the duration value is NaN."""

        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "distance": [8000],
                    "duration": [np.nan],
                    "startDate": pd.to_datetime(["2024-07-01"]),
                }
            )
        )
        result = workouts.get_longest_workout_details(["Running"])
        assert result is not None
        assert result["distance"] == pytest.approx(8.0)  # type: ignore[misc]
        assert result["duration"] is None
