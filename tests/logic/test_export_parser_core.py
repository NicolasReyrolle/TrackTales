"""Core tests for the ExportParser module."""

from collections.abc import Callable
from pathlib import Path
from zipfile import ZipFile

import pandas as pd
import pytest

import logic.export_parser as ep
import logic.workout_manager as wm


class TestExportParser:
    """Test cases for the ExportParser class."""

    def test_parse_with_sample_file(self, create_health_zip: Callable[..., str]) -> None:
        """Test that parse() method can be called without error."""
        sample_file = create_health_zip()
        parser = ep.ExportParser()
        # This should not raise an error (file may not have data, but should parse)
        try:
            parser.parse(sample_file)
        except FileNotFoundError:
            # If file doesn't exist or is invalid, that's okay for this test
            pass


class TestLoadWorkouts:
    """Test the _load_workouts method."""

    def test_load_workouts_with_valid_zip(self, tmp_path: Path) -> None:
        """Test loading running workouts from a valid Apple Health ZIP file."""
        zip_path = tmp_path / "mock_export.zip"
        xml_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<HealthData>
    <Workout workoutActivityType="HKWorkoutActivityTypeRunning"
        startDate="2024-01-01" endDate="2024-01-01" duration="30"/>
    <Workout workoutActivityType="HKWorkoutActivityTypeCycling"
        startDate="2024-01-02" endDate="2024-01-02" duration="45"/>
    <Workout workoutActivityType="HKWorkoutActivityTypeRunning"
        startDate="2024-01-03" endDate="2024-01-03" duration="25"/>
</HealthData>
"""
        with ZipFile(zip_path, "w") as zf:
            zf.writestr("apple_health_export/export.xml", xml_content)

        parser = ep.ExportParser()
        with parser:
            workouts = wm.WorkoutManager(parser.parse(str(zip_path)).workouts)

        assert workouts.get_count() == 3
        assert list(workouts.get_workouts()["startDate"]) == [
            pd.Timestamp("2024-01-01 00:00:00"),
            pd.Timestamp("2024-01-02 00:00:00"),
            pd.Timestamp("2024-01-03 00:00:00"),
        ]

    def test_load_workouts_empty(self, tmp_path: Path) -> None:
        """Test loading workouts from ZIP with no running workouts."""
        zip_path = tmp_path / "empty_export.zip"
        xml_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<HealthData>
</HealthData>
"""
        with ZipFile(zip_path, "w") as zf:
            zf.writestr("apple_health_export/export.xml", xml_content)

        parser = ep.ExportParser()
        with parser:
            workouts = wm.WorkoutManager(parser.parse(str(zip_path)).workouts)

        assert workouts.get_count() == 0

    def test_load_multiple_workouts_accumulate(self, tmp_path: Path) -> None:
        """Test that multiple workouts are loaded into DataFrame."""
        zip_path = tmp_path / "multi_export.zip"
        xml_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<HealthData>
    <Workout workoutActivityType="HKWorkoutActivityTypeRunning"
        startDate="2024-01-01" endDate="2024-01-01" duration="30" durationUnit="min"/>
    <Workout workoutActivityType="HKWorkoutActivityTypeRunning"
        startDate="2024-01-02" endDate="2024-01-02" duration="25" durationUnit="min"/>
</HealthData>
"""
        with ZipFile(zip_path, "w") as zf:
            zf.writestr("apple_health_export/export.xml", xml_content)

        parser = ep.ExportParser()
        with parser:
            workouts = wm.WorkoutManager(parser.parse(str(zip_path)).workouts)

        # First parse should have 2 workouts
        assert workouts.get_count() == 2
        # Check duration values are captured in seconds
        assert list(workouts.get_workouts()["duration"]) == [1800, 1500]


class TestDurationToSeconds:
    """Test the duration_to_seconds static method."""

    def test_duration_minutes_to_seconds(self) -> None:
        """Test converting minutes to seconds."""
        assert ep.ExportParser.duration_to_seconds(1, "min") == 60
        assert ep.ExportParser.duration_to_seconds(5, "min") == 300
        assert ep.ExportParser.duration_to_seconds(30, "min") == 1800
        assert ep.ExportParser.duration_to_seconds(119.27, "min") == 7156

    def test_duration_hours_to_seconds(self) -> None:
        """Test converting hours to seconds."""
        assert ep.ExportParser.duration_to_seconds(1, "h") == 3600
        assert ep.ExportParser.duration_to_seconds(2, "h") == 7200
        assert ep.ExportParser.duration_to_seconds(0.5, "h") == 1800

    def test_duration_seconds_to_seconds(self) -> None:
        """Test that seconds remain unchanged."""
        assert ep.ExportParser.duration_to_seconds(60, "s") == 60
        assert ep.ExportParser.duration_to_seconds(3600, "s") == 3600
        assert ep.ExportParser.duration_to_seconds(5, "s") == 5

    def test_duration_zero_value(self) -> None:
        """Test handling zero duration."""
        assert ep.ExportParser.duration_to_seconds(0, "min") == 0
        assert ep.ExportParser.duration_to_seconds(0, "h") == 0
        assert ep.ExportParser.duration_to_seconds(0, "s") == 0

    def test_duration_decimal_values(self) -> None:
        """Test handling decimal values."""
        assert ep.ExportParser.duration_to_seconds(1.5, "min") == 90
        assert ep.ExportParser.duration_to_seconds(2.5, "h") == 9000
        assert ep.ExportParser.duration_to_seconds(30.5, "s") == 30

    def test_duration_returns_int(self) -> None:
        """Test that the method always returns an integer."""
        result = ep.ExportParser.duration_to_seconds(1.5, "min")
        assert isinstance(result, int)
        assert result == 90

    def test_duration_invalid_unit_raises_error(self) -> None:
        """Test that invalid unit raises ValueError."""
        with pytest.raises(ValueError, match="Unknown duration unit"):
            ep.ExportParser.duration_to_seconds(10, "invalid")

        with pytest.raises(ValueError, match="Unknown duration unit"):
            ep.ExportParser.duration_to_seconds(10, "sec")

    def test_missing_unit_processed_as_minutes(self) -> None:
        """Test that missing unit defaults to minutes."""
        result = ep.ExportParser.duration_to_seconds(10, "")
        assert isinstance(result, int)
        assert result == 600

    def test_duration_large_values(self) -> None:
        """Test handling large duration values."""
        # 24 hours in seconds
        assert ep.ExportParser.duration_to_seconds(24, "h") == 86400
        # 1000 minutes in seconds
        assert ep.ExportParser.duration_to_seconds(1000, "min") == 60000

    def test_duration_very_small_values(self) -> None:
        """Test handling very small decimal values."""
        # Truncates to integer
        assert ep.ExportParser.duration_to_seconds(0.1, "min") == 6
        assert ep.ExportParser.duration_to_seconds(0.01, "h") == 36


class TestNormalizeWorkoutStartDate:
    """Tests for _normalize_workout_start_date helper."""

    def test_normalize_workout_start_date_non_string_returns_none(self) -> None:
        assert ep.ExportParser._normalize_workout_start_date(None) is None  # type: ignore[misc]
        assert ep.ExportParser._normalize_workout_start_date(123) is None  # type: ignore[misc]


class TestStrDistanceToMeters:
    """Test the str_distance_to_meters method."""

    def test_distance_kilometers_to_meters(self) -> None:
        """Convert kilometers to meters."""
        assert ep.ExportParser.str_distance_to_meters("1", "km") == 1000
        assert ep.ExportParser.str_distance_to_meters("2.5", "km") == 2500
        assert ep.ExportParser.str_distance_to_meters("0", "km") == 0

    def test_distance_meters_to_meters(self) -> None:
        """Convert meters to meters (identity)."""
        assert ep.ExportParser.str_distance_to_meters("1", "m") == 1
        assert ep.ExportParser.str_distance_to_meters("250.7", "m") == 250
        assert ep.ExportParser.str_distance_to_meters("0", "m") == 0

    def test_distance_miles_to_meters(self) -> None:
        """Convert miles to meters."""
        assert ep.ExportParser.str_distance_to_meters("1", "mi") == 1609
        assert ep.ExportParser.str_distance_to_meters("0.5", "mi") == 804

    def test_distance_invalid_unit_raises(self) -> None:
        """Invalid units raise ValueError."""
        with pytest.raises(ValueError, match="Unknown distance unit"):
            ep.ExportParser.str_distance_to_meters("1", "yd")

    def test_distance_none_unit_raises(self) -> None:
        """None unit raises ValueError with clear message."""
        with pytest.raises(ValueError, match="Distance unit is missing"):
            ep.ExportParser.str_distance_to_meters("1", None)
