"""Test suite for WorkoutManager date filtering functionality."""

from datetime import datetime

import pandas as pd

import logic.workout_manager as wm


class TestGetCountWithDateFiltering:
    """Test get_count with date filtering."""

    def test_get_count_with_start_date(self) -> None:
        """Test get_count filters by start date."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running", "Running"],
                    "startDate": pd.to_datetime(["2024-01-01", "2024-02-01", "2024-03-01"]),
                }
            )
        )

        assert workouts.get_count(start_date=datetime(2024, 2, 1)) == 2

    def test_get_count_with_end_date(self) -> None:
        """Test get_count filters by end date."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running", "Running"],
                    "startDate": pd.to_datetime(["2024-01-01", "2024-02-01", "2024-03-01"]),
                }
            )
        )

        assert workouts.get_count(end_date=datetime(2024, 2, 1)) == 2

    def test_get_count_with_date_range(self) -> None:
        """Test get_count filters by date range (inclusive)."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running", "Running", "Running"],
                    "startDate": pd.to_datetime(
                        ["2024-01-01", "2024-02-01", "2024-02-15", "2024-03-01"]
                    ),
                }
            )
        )

        # Should include both 2024-02-01 and 2024-02-15 (inclusive)
        assert (
            workouts.get_count(start_date=datetime(2024, 2, 1), end_date=datetime(2024, 2, 28)) == 2
        )

    def test_get_count_with_activity_and_date_range(self) -> None:
        """Test get_count filters by both activity and date range."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Cycling", "Running", "Cycling"],
                    "startDate": pd.to_datetime(
                        ["2024-01-01", "2024-01-15", "2024-02-01", "2024-02-15"]
                    ),
                }
            )
        )

        assert workouts.get_count("Running", start_date=datetime(2024, 2, 1)) == 1

    def test_get_count_with_pandas_timestamp(self) -> None:
        """Test get_count accepts pd.Timestamp for dates."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running", "Running"],
                    "startDate": pd.to_datetime(["2024-01-01", "2024-02-01", "2024-03-01"]),
                }
            )
        )

        assert workouts.get_count(start_date=pd.Timestamp("2024-02-01")) == 2

    def test_get_count_includes_last_day_for_date_only_end_date(self) -> None:
        """Test date-only end_date includes workouts throughout that day."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running", "Running"],
                    "startDate": pd.to_datetime(
                        ["2024-02-01 08:00", "2024-02-01 23:59", "2024-02-02 00:00"]
                    ),
                }
            )
        )

        assert workouts.get_count(end_date=datetime(2024, 2, 1)) == 2

    def test_get_count_respects_time_specific_end_date(self) -> None:
        """Test time-specific end_date does not include later times in the day."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running"],
                    "startDate": pd.to_datetime(["2024-02-01 08:00", "2024-02-01 13:00"]),
                }
            )
        )

        assert workouts.get_count(end_date=datetime(2024, 2, 1, 12, 0)) == 1

    def test_get_count_no_matching_dates(self) -> None:
        """Test get_count returns 0 when no dates match."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running"],
                    "startDate": pd.to_datetime(["2024-01-01", "2024-01-15"]),
                }
            )
        )

        assert workouts.get_count(start_date=datetime(2024, 3, 1)) == 0


class TestGetTotalDistanceWithDateFiltering:
    """Test get_total_distance with date filtering."""

    def test_get_total_distance_with_date_range(self) -> None:
        """Test get_total_distance filters by date range."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running", "Running"],
                    "distance": [5000, 10000, 8000],
                    "startDate": pd.to_datetime(["2024-01-01", "2024-02-01", "2024-03-01"]),
                }
            )
        )

        # Only February workout (10000m = 10km)
        result = workouts.get_total_distance(
            start_date=datetime(2024, 2, 1), end_date=datetime(2024, 2, 28)
        )
        assert result == 10

    def test_get_total_distance_with_activity_and_dates(self) -> None:
        """Test get_total_distance filters by both activity and dates."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Cycling", "Running"],
                    "distance": [5000, 10000, 8000],
                    "startDate": pd.to_datetime(["2024-01-01", "2024-01-15", "2024-02-01"]),
                }
            )
        )

        # Only Running workouts in January: 5000m = 5km
        result = workouts.get_total_distance(
            "Running", start_date=datetime(2024, 1, 1), end_date=datetime(2024, 1, 31)
        )
        assert result == 5

    def test_get_total_distance_includes_last_day_for_date_only_end_date(self) -> None:
        """Test date-only end_date includes workouts throughout that day."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running", "Running"],
                    "distance": [1000, 2000, 3000],
                    "startDate": pd.to_datetime(
                        ["2024-02-01 08:00", "2024-02-01 23:59", "2024-02-02 00:00"]
                    ),
                }
            )
        )

        assert workouts.get_total_distance(end_date=datetime(2024, 2, 1), unit="m") == 3000

    def test_get_total_distance_respects_time_specific_end_date(self) -> None:
        """Test time-specific end_date excludes later times in the day."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running"],
                    "distance": [1000, 2000],
                    "startDate": pd.to_datetime(["2024-02-01 08:00", "2024-02-01 13:00"]),
                }
            )
        )

        assert workouts.get_total_distance(end_date=datetime(2024, 2, 1, 12, 0), unit="m") == 1000


class TestGetTotalDurationWithDateFiltering:
    """Test get_total_duration with date filtering."""

    def test_get_total_duration_with_date_range(self) -> None:
        """Test get_total_duration filters by date range."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running", "Running"],
                    "duration": [3600, 7200, 5400],  # 1h, 2h, 1.5h
                    "startDate": pd.to_datetime(["2024-01-01", "2024-02-01", "2024-03-01"]),
                }
            )
        )

        # Only February workout: 2 hours
        result = workouts.get_total_duration(
            start_date=datetime(2024, 2, 1), end_date=datetime(2024, 2, 28)
        )
        assert result == 2


class TestGetTotalElevationWithDateFiltering:
    """Test get_total_elevation with date filtering."""

    def test_get_total_elevation_with_date_range(self) -> None:
        """Test get_total_elevation filters by date range."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running", "Running"],
                    "ElevationAscended": [100, 200, 150],  # 100m, 200m, 150m
                    "startDate": pd.to_datetime(["2024-01-01", "2024-02-01", "2024-03-01"]),
                }
            )
        )

        # Only February workout: 200m = 0.2km (unit="km" is default)
        result = workouts.get_total_elevation(
            start_date=datetime(2024, 2, 1), end_date=datetime(2024, 2, 28)
        )
        assert result == 0  # 0.2km rounds down to 0


class TestGetTotalCaloriesWithDateFiltering:
    """Test get_total_calories with date filtering."""

    def test_get_total_calories_with_date_range(self) -> None:
        """Test get_total_calories filters by date range."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running", "Running"],
                    "sumActiveEnergyBurned": [300, 500, 400],
                    "startDate": pd.to_datetime(["2024-01-01", "2024-02-01", "2024-03-01"]),
                }
            )
        )

        # Only February workout: 500 kcal
        result = workouts.get_total_calories(
            start_date=datetime(2024, 2, 1), end_date=datetime(2024, 2, 28)
        )
        assert result == 500


class TestGetByActivityWithDateFiltering:
    """Test get_*_by_activity methods with date filtering."""

    def test_get_count_by_activity_with_dates(self) -> None:
        """Test get_count_by_activity filters by date range."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Cycling", "Running", "Cycling"],
                    "startDate": pd.to_datetime(
                        ["2024-01-01", "2024-01-15", "2024-02-01", "2024-02-15"]
                    ),
                }
            )
        )

        result = workouts.get_count_by_activity(
            start_date=datetime(2024, 2, 1), end_date=datetime(2024, 2, 28)
        )
        assert result == {"Running": 1, "Cycling": 1}

    def test_get_distance_by_activity_with_dates(self) -> None:
        """Test get_distance_by_activity filters by date range."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Cycling", "Running"],
                    "distance": [5000, 10000, 8000],
                    "startDate": pd.to_datetime(["2024-01-01", "2024-01-15", "2024-02-01"]),
                }
            )
        )

        result = workouts.get_distance_by_activity(start_date=datetime(2024, 2, 1))
        assert result == {"Running": 8}  # 8000m = 8km

    def test_get_calories_by_activity_with_dates(self) -> None:
        """Test get_calories_by_activity filters by date range."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Cycling", "Running"],
                    "sumActiveEnergyBurned": [300, 500, 400],
                    "startDate": pd.to_datetime(["2024-01-01", "2024-01-15", "2024-02-01"]),
                }
            )
        )

        result = workouts.get_calories_by_activity(
            start_date=datetime(2024, 1, 1), end_date=datetime(2024, 1, 31)
        )
        assert result == {"Running": 300, "Cycling": 500}

    def test_get_duration_by_activity_with_dates(self) -> None:
        """Test get_duration_by_activity filters by date range."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Cycling", "Running"],
                    "duration": [3600, 7200, 5400],
                    "startDate": pd.to_datetime(["2024-01-01", "2024-01-15", "2024-02-01"]),
                }
            )
        )

        result = workouts.get_duration_by_activity(
            start_date=datetime(2024, 1, 1), end_date=datetime(2024, 1, 31)
        )
        assert result == {"Running": 1, "Cycling": 2}  # Hours

    def test_get_elevation_by_activity_with_dates(self) -> None:
        """Test get_elevation_by_activity filters by date range."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Cycling", "Running"],
                    "ElevationAscended": [100, 200, 150],  # meters
                    "startDate": pd.to_datetime(["2024-01-01", "2024-01-15", "2024-02-01"]),
                }
            )
        )

        result = workouts.get_elevation_by_activity(unit="m", start_date=datetime(2024, 2, 1))
        assert result == {"Running": 150}  # meters


class TestGetByPeriodWithDateFiltering:
    """Test get_*_by_period methods with date filtering."""

    def test_get_count_by_period_with_dates(self) -> None:
        """Test get_count_by_period filters by date range."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"] * 6,
                    "startDate": pd.to_datetime(
                        [
                            "2024-01-01",
                            "2024-01-15",
                            "2024-02-01",
                            "2024-02-15",
                            "2024-03-01",
                            "2024-03-15",
                        ]
                    ),
                }
            )
        )

        result = workouts.get_count_by_period(
            "M", start_date=datetime(2024, 2, 1), end_date=datetime(2024, 2, 28)
        )
        # Should only have February data
        assert "2024-02" in result
        assert result["2024-02"] == 2
        assert "2024-01" not in result
        assert "2024-03" not in result

    def test_get_distance_by_period_with_dates(self) -> None:
        """Test get_distance_by_period filters by date range."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running", "Running", "Running"],
                    "distance": [5000, 10000, 8000, 12000],
                    "startDate": pd.to_datetime(
                        ["2024-01-01", "2024-01-15", "2024-02-01", "2024-03-01"]
                    ),
                }
            )
        )

        result = workouts.get_distance_by_period(
            "M", start_date=datetime(2024, 1, 1), end_date=datetime(2024, 2, 28)
        )
        assert "2024-01" in result
        assert result["2024-01"] == 15  # (5000+10000)/1000 = 15km
        assert "2024-02" in result
        assert result["2024-02"] == 8  # 8000/1000 = 8km
        assert "2024-03" not in result

    def test_get_calories_by_period_with_dates(self) -> None:
        """Test get_calories_by_period filters by date range."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running", "Running"],
                    "sumActiveEnergyBurned": [300, 500, 400],
                    "startDate": pd.to_datetime(["2024-01-01", "2024-02-01", "2024-03-01"]),
                }
            )
        )

        result = workouts.get_calories_by_period("M", start_date=datetime(2024, 2, 1))
        assert "2024-02" in result
        assert result["2024-02"] == 500
        assert "2024-03" in result
        assert result["2024-03"] == 400
        assert "2024-01" not in result

    def test_get_duration_by_period_with_dates(self) -> None:
        """Test get_duration_by_period filters by date range."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running", "Running"],
                    "duration": [3600, 7200, 5400],
                    "startDate": pd.to_datetime(["2024-01-01", "2024-02-01", "2024-03-01"]),
                }
            )
        )

        result = workouts.get_duration_by_period("M", end_date=datetime(2024, 2, 28))
        assert "2024-01" in result
        assert result["2024-01"] == 1  # 3600/3600 = 1 hour
        assert "2024-02" in result
        assert result["2024-02"] == 2  # 7200/3600 = 2 hours
        assert "2024-03" not in result

    def test_get_elevation_by_period_with_dates(self) -> None:
        """Test get_elevation_by_period filters by date range."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running", "Running"],
                    "ElevationAscended": [100, 200, 150],
                    "startDate": pd.to_datetime(["2024-01-01", "2024-02-01", "2024-03-01"]),
                }
            )
        )

        result = workouts.get_elevation_by_period(
            "M", unit="m", start_date=datetime(2024, 1, 1), end_date=datetime(2024, 2, 28)
        )
        assert "2024-01" in result
        assert result["2024-01"] == 100
        assert "2024-02" in result
        assert result["2024-02"] == 200
        assert "2024-03" not in result


class TestDateFilteringEdgeCases:
    """Test edge cases for date filtering."""

    def test_date_filtering_without_start_date_column(self) -> None:
        """Test date filtering when startDate column is missing."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running"],
                    "distance": [5000, 10000],
                }
            )
        )

        # Should return all workouts when no startDate column exists
        result = workouts.get_count(start_date=datetime(2024, 1, 1))
        assert result == 2

    def test_date_filtering_with_exact_boundary(self) -> None:
        """Test date filtering is inclusive of boundaries."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running", "Running"],
                    "startDate": pd.to_datetime(["2024-01-01", "2024-01-15", "2024-01-31"]),
                }
            )
        )

        # Should include both Jan 1 and Jan 31 (inclusive)
        result = workouts.get_count(start_date=datetime(2024, 1, 1), end_date=datetime(2024, 1, 31))
        assert result == 3

    def test_date_filtering_single_day(self) -> None:
        """Test date filtering for a single day."""
        workouts = wm.WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running", "Running"],
                    "startDate": pd.to_datetime(["2024-01-14", "2024-01-15", "2024-01-16"]),
                }
            )
        )

        result = workouts.get_count(
            start_date=datetime(2024, 1, 15), end_date=datetime(2024, 1, 15)
        )
        assert result == 1
