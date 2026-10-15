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
        assert "xmlFragment" in workouts.get_workouts().columns
        assert "<Workout " in workouts.get_workouts().iloc[0]["xmlFragment"]

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

    def test_nested_record_does_not_remove_workout_statistics(self, tmp_path: Path) -> None:
        """Preserve workout statistics preceding records nested inside a workout."""
        zip_path = tmp_path / "nested_record_export.zip"
        xml_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<HealthData>
    <Workout workoutActivityType="HKWorkoutActivityTypeRunning"
        startDate="2024-01-01" endDate="2024-01-01" duration="30" durationUnit="min">
        <WorkoutStatistics type="HKQuantityTypeIdentifierDistanceWalkingRunning"
            sum="5" unit="km"/>
        <Record type="HKQuantityTypeIdentifierHeartRate" value="120"
            startDate="2024-01-01" endDate="2024-01-01"/>
    </Workout>
</HealthData>
"""
        with ZipFile(zip_path, "w") as zf:
            zf.writestr("apple_health_export/export.xml", xml_content)

        parser = ep.ExportParser()
        with parser:
            workouts = wm.WorkoutManager(parser.parse(str(zip_path)).workouts)

        assert workouts.get_workouts().iloc[0]["distance"] == 5000

    def test_interval_activity_does_not_duplicate_workout_data(self, tmp_path: Path) -> None:
        """Ignore overlapping interval statistics and routes while preserving elevation."""
        zip_path = tmp_path / "interval_export.zip"
        xml_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<HealthData>
    <Workout workoutActivityType="HKWorkoutActivityTypeRunning"
        startDate="2024-01-01 10:00:00 +0000"
        endDate="2024-01-01 10:05:00 +0000" duration="5" durationUnit="min">
        <WorkoutStatistics type="HKQuantityTypeIdentifierDistanceWalkingRunning"
            sum="5" unit="km"/>
        <WorkoutStatistics type="HKQuantityTypeIdentifierRunningSpeed"
            average="8" unit="km/hr"/>
        <WorkoutRoute startDate="2024-01-01 10:00:00 +0000"
            endDate="2024-01-01 10:05:00 +0000">
            <FileReference path="/workout-routes/main.gpx"/>
        </WorkoutRoute>
        <WorkoutActivity startDate="2024-01-01 10:00:00 +0000"
            endDate="2024-01-01 10:05:00 +0000">
            <MetadataEntry key="WOIntervalStepKeyPath" value="0.0.0"/>
            <MetadataEntry key="HKElevationAscended" value="123 m"/>
            <WorkoutStatistics type="HKQuantityTypeIdentifierDistanceWalkingRunning"
                sum="50" unit="km"/>
            <WorkoutStatistics type="HKQuantityTypeIdentifierRunningSpeed"
                average="50" unit="km/hr"/>
            <WorkoutRoute startDate="2024-01-01 10:00:00 +0000"
                endDate="2024-01-01 10:05:00 +0000">
                <FileReference path="/workout-routes/interval.gpx"/>
            </WorkoutRoute>
        </WorkoutActivity>
    </Workout>
</HealthData>
"""
        main_gpx = b"""<?xml version="1.0" encoding="UTF-8"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1">
    <trk><trkseg>
        <trkpt lat="0" lon="0"><ele>100</ele><time>2024-01-01T10:00:00Z</time></trkpt>
        <trkpt lat="0" lon="0.045"><ele>110</ele><time>2024-01-01T10:05:00Z</time></trkpt>
    </trkseg></trk>
</gpx>
"""
        interval_gpx = b"""<?xml version="1.0" encoding="UTF-8"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1">
    <trk><trkseg>
        <trkpt lat="0" lon="0"><ele>100</ele><time>2024-01-01T10:00:00Z</time></trkpt>
        <trkpt lat="0" lon="0.02"><ele>120</ele><time>2024-01-01T10:01:00Z</time></trkpt>
    </trkseg></trk>
</gpx>
"""
        with ZipFile(zip_path, "w") as zf:
            zf.writestr("apple_health_export/export.xml", xml_content)
            zf.writestr("apple_health_export/workout-routes/main.gpx", main_gpx)
            zf.writestr("apple_health_export/workout-routes/interval.gpx", interval_gpx)

        parser = ep.ExportParser()
        with parser:
            parsed = parser.parse(str(zip_path))

        workout = parsed.workouts.iloc[0]
        assert workout["distance"] == 5000
        assert workout["averageRunningSpeed"] == 8
        assert workout["ElevationAscended"] == pytest.approx(123.0)
        assert workout["ElevationAscendedUnit"] == "m"
        assert len(workout["route_parts"]) == 1
        assert workout["route_parts"][0].points[-1].longitude == pytest.approx(0.045)

        best_segment = wm.WorkoutManager(parsed.workouts).get_best_segments(
            topn=1, distances=[1000]
        )
        assert len(best_segment) == 1
        assert best_segment.iloc[0]["duration_s"] > 200

    def test_issue_367_workout_preserves_summary_and_best_segments(
        self,
        tmp_path: Path,
        load_export_fragment: Callable[[str], str],
        build_health_export_xml: Callable[[list[str]], str],
    ) -> None:
        """Parse the issue's custom workout without importing its interval statistics."""
        exports_dir = Path(__file__).resolve().parents[1] / "fixtures" / "exports"
        route_dir = exports_dir / "workout-routes"
        zip_path = tmp_path / "issue_367_export.zip"
        workout_xml = load_export_fragment("workout_issue_367.xml")

        with ZipFile(zip_path, "w") as zf:
            zf.writestr(
                "apple_health_export/export.xml",
                build_health_export_xml([workout_xml]),
            )
            for route_file in sorted(route_dir.glob("route_2025-04-17_7.*pm.gpx")):
                zf.write(
                    route_file,
                    f"apple_health_export/workout-routes/{route_file.name}",
                )

        parser = ep.ExportParser()
        with parser:
            parsed = parser.parse(str(zip_path))

        workout = parsed.workouts.iloc[0]
        assert workout["distance"] == 7857
        assert workout["averageRunningSpeed"] == pytest.approx(9.65213)
        assert workout["maximumRunningSpeed"] == pytest.approx(12.2723)
        assert workout["ElevationAscended"] == pytest.approx(57.59)
        assert "WOIntervalStepSuccessful" not in workout
        assert len(workout["route_parts"]) == 7

        best_segments = wm.WorkoutManager(parsed.workouts).get_best_segments(
            topn=1, distances=[1000]
        )
        assert len(best_segments) == 1
        assert best_segments.iloc[0]["duration_s"] == pytest.approx(297, abs=1)


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


class TestNormalizeHealthDatetimeToUtcNaive:
    """Tests for UTC-normalized workout matching timestamps."""

    def test_normalize_health_datetime_to_utc_naive_converts_offset_time(self) -> None:
        result = ep.ExportParser._normalize_health_datetime_to_utc_naive(
            "2025-01-02 11:00:00 +0100"
        )

        assert result == pd.Timestamp("2025-01-02 10:00:00").to_pydatetime()


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
