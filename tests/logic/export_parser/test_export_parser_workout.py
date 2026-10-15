"""Tests for workout processing functionality."""

from pathlib import Path
from zipfile import ZipFile

import pytest
from lxml.etree import Element

import logic.export_parser as ep


class TestCreateWorkoutRecord:
    """Test the _create_workout_record method."""

    def test_create_workout_record_with_all_attributes(self) -> None:
        """Test creating a workout record with all attributes."""
        elem = Element(
            "Workout",
            attrib={
                "workoutActivityType": "HKWorkoutActivityTypeRunning",
                "duration": "30",
                "startDate": "2024-01-01 10:00:00",
                "endDate": "2024-01-01 10:30:00",
                "sourceName": "Apple Watch",
            },
        )
        parser = ep.ExportParser()
        record = parser._create_workout_record(elem, "Running")  # type: ignore[misc]

        assert record["activityType"] == "Running"
        assert isinstance(record.get("duration"), int)
        assert record.get("duration") == 1800
        assert record.get("startDate") == "2024-01-01 10:00:00"
        assert record.get("endDate") == "2024-01-01 10:30:00"
        assert record.get("source") == "Apple Watch"

    def test_create_workout_record_with_missing_attributes(self) -> None:
        """Test creating a workout record with missing attributes."""
        elem = Element("Workout", attrib={"workoutActivityType": "HKWorkoutActivityTypeRunning"})
        parser = ep.ExportParser()
        record = parser._create_workout_record(elem, "Running")  # type: ignore[misc]

        assert record["activityType"] == "Running"
        assert record.get("duration") is None
        assert record.get("startDate") is None
        assert record.get("endDate") is None
        assert record.get("source") is None


class TestProcessWorkoutStatistics:
    """Test the _process_workout_statistics method."""

    def test_process_workout_statistics_with_sum(self) -> None:
        """Test processing workout statistics with sum value."""
        elem = Element(
            "WorkoutStatistics",
            attrib={
                "type": "HKQuantityTypeIdentifierDistanceWalkingRunning",
                "sum": "5.2",
                "unit": "km",
            },
        )
        parser = ep.ExportParser()
        record: ep.WorkoutRecord = {"activityType": "Running"}

        parser._process_workout_statistics(elem, record)  # type: ignore[misc]

        assert isinstance(record.get("distance"), int)
        assert record.get("distance") == 5200

    def test_process_workout_statistics_with_average(self) -> None:
        """Test processing workout statistics with average value."""
        elem = Element(
            "WorkoutStatistics",
            attrib={
                "type": "HKQuantityTypeIdentifierHeartRate",
                "average": "150",
                "unit": "count/min",
            },
        )
        parser = ep.ExportParser()
        record: ep.WorkoutRecord = {"activityType": "Running"}

        parser._process_workout_statistics(elem, record)  # type: ignore[misc]

        assert isinstance(record.get("averageHeartRate"), float)
        assert record.get("averageHeartRate") == 150
        assert record.get("averageHeartRateUnit") == "count/min"

    def test_process_workout_statistics_with_multiple_values(self) -> None:
        """Test processing workout statistics with multiple values."""
        elem = Element(
            "WorkoutStatistics",
            attrib={
                "type": "HKQuantityTypeIdentifierSpeed",
                "minimum": "8.0",
                "unit": "km/h",
                "maximum": "12.0",
            },
        )
        parser = ep.ExportParser()
        record: ep.WorkoutRecord = {"activityType": "Running"}

        parser._process_workout_statistics(elem, record)  # type: ignore[misc]

        assert isinstance(record.get("minimumSpeed"), float)
        assert record.get("minimumSpeed") == pytest.approx(8.0)  # type: ignore[misc]
        assert record.get("minimumSpeedUnit") == "km/h"
        assert isinstance(record.get("maximumSpeed"), float)
        assert record.get("maximumSpeed") == pytest.approx(12.0)  # type: ignore[misc]
        assert record.get("maximumSpeedUnit") == "km/h"

    def test_process_workout_statistics_with_no_values(self) -> None:
        """Test processing workout statistics with no values (all attributes missing)."""
        elem = Element(
            "WorkoutStatistics",
            attrib={
                "type": "HKQuantityTypeIdentifierEnergy",
            },
        )
        parser = ep.ExportParser()
        record: ep.WorkoutRecord = {"activityType": "Running"}

        parser._process_workout_statistics(elem, record)  # type: ignore[misc]

        # Should not add any statistics since no values are present
        assert len(record) == 1  # Only activityType

    def test_process_workout_statistics_with_distance_swimming(self) -> None:
        """Test processing workout statistics for swimming distance."""
        elem = Element(
            "WorkoutStatistics",
            attrib={
                "type": "HKQuantityTypeIdentifierDistanceSwimming",
                "sum": "2.5",
                "unit": "km",
            },
        )
        parser = ep.ExportParser()
        record: ep.WorkoutRecord = {"activityType": "Swimming"}

        parser._process_workout_statistics(elem, record)  # type: ignore[misc]

        assert isinstance(record.get("distance"), int)
        assert record.get("distance") == 2500

    def test_process_workout_statistics_with_distance_cycling(self) -> None:
        """Test processing workout statistics for cycling distance."""
        elem = Element(
            "WorkoutStatistics",
            attrib={
                "type": "HKQuantityTypeIdentifierDistanceCycling",
                "sum": "15.8",
                "unit": "km",
            },
        )
        parser = ep.ExportParser()
        record: ep.WorkoutRecord = {"activityType": "Cycling"}

        parser._process_workout_statistics(elem, record)  # type: ignore[misc]

        assert isinstance(record.get("distance"), int)
        assert record.get("distance") == 15800


class TestProcessMetadataEntry:
    """Test the _process_metadata_entry method."""

    def test_process_metadata_entry_with_simple_value(self) -> None:
        """Test processing a simple metadata entry."""
        elem = Element(
            "MetadataEntry",
            attrib={"key": "HKMetadataKeyTimeZone", "value": "Europe/Luxembourg"},
        )
        parser = ep.ExportParser()
        record: ep.WorkoutRecord = {"activityType": "Running"}

        parser._process_metadata_entry(elem, record)  # type: ignore[misc]

        assert record.get("MetadataKeyTimeZone") == "Europe/Luxembourg"

    def test_process_metadata_entry_with_value_and_unit(self) -> None:
        """Test processing metadata entry with value and unit."""
        elem = Element(
            "MetadataEntry",
            attrib={"key": "HKMetadataKeyElevationAscended", "value": "100 m"},
        )
        parser = ep.ExportParser()
        record: ep.WorkoutRecord = {"activityType": "Running"}

        parser._process_metadata_entry(elem, record)  # type: ignore[misc]
        assert isinstance(record.get("MetadataKeyElevationAscended"), float)
        assert record.get("MetadataKeyElevationAscended") == pytest.approx(  # type: ignore[misc]
            100.0
        )
        assert record.get("MetadataKeyElevationAscendedUnit") == "m"

    def test_process_metadata_entry_with_boolean_conversion(self) -> None:
        """Test metadata entry with boolean conversion."""
        elem = Element(
            "MetadataEntry",
            attrib={"key": "HKMetadataKeyIsIndoorWorkout", "value": "1"},
        )
        parser = ep.ExportParser()
        record: ep.WorkoutRecord = {"activityType": "Running"}

        parser._process_metadata_entry(elem, record)  # type: ignore[misc]

        assert record.get("MetadataKeyIsIndoorWorkout") is True

    def test_process_metadata_entry_skips_interval_step_key(self) -> None:
        """Test that WOIntervalStepKeyPath is skipped."""
        elem = Element(
            "MetadataEntry",
            attrib={"key": "HKWOIntervalStepKeyPath", "value": "0.0.0"},
        )

        parser = ep.ExportParser()
        record: ep.WorkoutRecord = {"activityType": "Running"}

        parser._process_metadata_entry(elem, record)  # type: ignore[misc]

        # Should be skipped, so record remains unchanged
        assert record == {"activityType": "Running"}


class TestProcessWorkoutChildren:
    """Test the _process_workout_children method."""

    def test_process_workout_children_with_statistics(self, tmp_path: Path) -> None:
        """Test processing workout with child statistics."""
        zip_path = tmp_path / "test_export.zip"
        xml_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<HealthData>
</HealthData>
"""
        with ZipFile(zip_path, "w") as zf:
            zf.writestr("apple_health_export/export.xml", xml_content)

        parent = Element("Workout")
        stats_elem = Element(
            "WorkoutStatistics",
            attrib={
                "type": "HKQuantityTypeIdentifierDistance",
                "sum": "10.0",
                "unit": "km",
            },
        )
        parent.append(stats_elem)

        parser = ep.ExportParser()
        record: ep.WorkoutRecord = {"activityType": "Running"}

        with ZipFile(zip_path, "r") as zf:
            parser._process_workout_children(parent, record, zf)  # type: ignore[misc]

        assert isinstance(record.get("distance"), int)
        assert record.get("distance") == 10000

    def test_process_workout_children_with_metadata(self, tmp_path: Path) -> None:
        """Test processing workout with child metadata entries."""
        zip_path = tmp_path / "test_export.zip"
        xml_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<HealthData>
</HealthData>
"""
        with ZipFile(zip_path, "w") as zf:
            zf.writestr("apple_health_export/export.xml", xml_content)

        parent = Element("Workout")
        metadata_elem = Element(
            "MetadataEntry",
            attrib={"key": "HKMetadataKeyTimeZone", "value": "Europe/Paris"},
        )
        parent.append(metadata_elem)

        parser = ep.ExportParser()
        record: ep.WorkoutRecord = {"activityType": "Running"}

        with ZipFile(zip_path, "r") as zf:
            parser._process_workout_children(parent, record, zf)  # type: ignore[misc]

        assert record.get("MetadataKeyTimeZone") == "Europe/Paris"

    def test_process_workout_children_mixed(self, tmp_path: Path) -> None:
        """Test processing workout with mixed children."""
        zip_path = tmp_path / "test_export.zip"
        xml_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<HealthData>
</HealthData>
"""
        with ZipFile(zip_path, "w") as zf:
            zf.writestr("apple_health_export/export.xml", xml_content)

        parent = Element("Workout")
        stats_elem = Element(
            "WorkoutStatistics",
            attrib={
                "type": "HKQuantityTypeIdentifierDistance",
                "sum": "5.0",
                "unit": "km",
            },
        )
        metadata_elem = Element(
            "MetadataEntry", attrib={"key": "HKMetadataKeyTimeZone", "value": "UTC"}
        )
        parent.append(stats_elem)
        parent.append(metadata_elem)

        parser = ep.ExportParser()
        record: ep.WorkoutRecord = {"activityType": "Running"}

        with ZipFile(zip_path, "r") as zf:
            parser._process_workout_children(parent, record, zf)  # type: ignore[misc]

        assert isinstance(record.get("distance"), int)
        assert record.get("distance") == 5000
        assert record.get("MetadataKeyTimeZone") == "UTC"

    def test_process_workout_children_with_unknown_element(self, tmp_path: Path) -> None:
        """Test processing workout with unknown child element (should be ignored)."""
        zip_path = tmp_path / "test_export.zip"
        xml_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<HealthData>
</HealthData>
"""
        with ZipFile(zip_path, "w") as zf:
            zf.writestr("apple_health_export/export.xml", xml_content)

        parent = Element("Workout")
        unknown_elem = Element("UnknownElement", attrib={"some": "attribute"})
        parent.append(unknown_elem)

        parser = ep.ExportParser()
        record: ep.WorkoutRecord = {"activityType": "Running"}

        with ZipFile(zip_path, "r") as zf:
            parser._process_workout_children(parent, record, zf)  # type: ignore[misc]

        # Should only have activityType, unknown element should be ignored
        assert record == {"activityType": "Running"}


class TestApplyEstimatedElevation:
    """Tests for _apply_estimated_elevation branches."""

    def test_skips_when_elevation_already_present(self) -> None:
        """Does nothing when ElevationAscended is already set."""
        record: ep.WorkoutRecord = {"activityType": "Running", "ElevationAscended": 50.0}  # type: ignore[typeddict-unknown-key]
        ep.ExportParser._apply_estimated_elevation(record)  # type: ignore[misc]
        assert record["ElevationAscended"] == 50.0  # type: ignore[typeddict-item]

    def test_skips_when_no_route_and_no_route_parts(self) -> None:
        """Does nothing when neither route nor route_parts is present."""
        record: ep.WorkoutRecord = {"activityType": "Running"}
        ep.ExportParser._apply_estimated_elevation(record)  # type: ignore[misc]
        assert "ElevationAscended" not in record

    def test_skips_when_route_is_none(self) -> None:
        """Does nothing when route key exists but is None."""
        record: ep.WorkoutRecord = {"activityType": "Running", "route": None}  # type: ignore[typeddict-unknown-key]
        ep.ExportParser._apply_estimated_elevation(record)  # type: ignore[misc]
        assert "ElevationAscended" not in record

    def test_sets_elevation_from_single_route(self) -> None:
        """Sets ElevationAscended from a single route when route_parts is absent."""
        from datetime import datetime

        from logic.workout_manager.workout_route import RoutePoint, WorkoutRoute

        route = WorkoutRoute(
            points=[
                RoutePoint(
                    time=datetime(2024, 1, 1, 10, 0), latitude=0.0, longitude=0.0, altitude=100.0
                ),
                RoutePoint(
                    time=datetime(2024, 1, 1, 10, 1), latitude=0.0, longitude=0.0, altitude=110.0
                ),
            ]
        )
        record: ep.WorkoutRecord = {"activityType": "Running", "route": route}  # type: ignore[typeddict-unknown-key]
        ep.ExportParser._apply_estimated_elevation(record)  # type: ignore[misc]
        assert "ElevationAscended" in record
        assert record["ElevationAscendedUnit"] == "m"  # type: ignore[typeddict-item]

    def test_skips_when_all_route_parts_return_none_gain(self) -> None:
        """Does nothing when route_parts exist but all return None for estimated gain."""
        from unittest.mock import MagicMock

        from logic.workout_manager.workout_route import WorkoutRoute

        mock_part = MagicMock(spec=WorkoutRoute)
        mock_part.estimated_elevation_gain_m.return_value = None
        record: ep.WorkoutRecord = {"activityType": "Running", "route_parts": [mock_part]}  # type: ignore[typeddict-unknown-key]
        ep.ExportParser._apply_estimated_elevation(record)  # type: ignore[misc]
        assert "ElevationAscended" not in record


class TestUpdateMotionTimestamps:
    """Tests for _update_motion_timestamps."""

    def test_updates_last_paused_when_none(self) -> None:
        from datetime import datetime

        dt = datetime(2024, 1, 1, 10, 0)
        paused, resumed = ep.ExportParser._update_motion_timestamps(  # type: ignore[misc]
            "HKWorkoutEventTypeMotionPaused", dt, None, None
        )
        assert paused == dt
        assert resumed is None

    def test_updates_last_paused_when_newer(self) -> None:
        from datetime import datetime

        earlier = datetime(2024, 1, 1, 10, 0)
        later = datetime(2024, 1, 1, 10, 5)
        paused, resumed = ep.ExportParser._update_motion_timestamps(  # type: ignore[misc]
            "HKWorkoutEventTypeMotionPaused", later, earlier, None
        )
        assert paused == later

    def test_does_not_update_last_paused_when_older(self) -> None:
        from datetime import datetime

        earlier = datetime(2024, 1, 1, 10, 0)
        later = datetime(2024, 1, 1, 10, 5)
        paused, _ = ep.ExportParser._update_motion_timestamps(  # type: ignore[misc]
            "HKWorkoutEventTypeMotionPaused", earlier, later, None
        )
        assert paused == later

    def test_updates_last_resumed(self) -> None:
        from datetime import datetime

        dt = datetime(2024, 1, 1, 10, 0)
        paused, resumed = ep.ExportParser._update_motion_timestamps(  # type: ignore[misc]
            "HKWorkoutEventTypeMotionResumed", dt, None, None
        )
        assert paused is None
        assert resumed == dt

    def test_ignores_unknown_event_type(self) -> None:
        from datetime import datetime

        dt = datetime(2024, 1, 1, 10, 0)
        paused, resumed = ep.ExportParser._update_motion_timestamps(  # type: ignore[misc]
            "HKWorkoutEventTypeLap", dt, None, None
        )
        assert paused is None
        assert resumed is None


class TestNestedElevationPrecedence:
    """Test precedence and aggregation of nested activity and interval elevations."""

    def test_interval_elevation_deferred_and_overridden_by_later_top_level_elevation(
        self, tmp_path: Path
    ) -> None:
        """Top-level HKElevationAscended after interval activity must take precedence."""
        zip_path = tmp_path / "test_export.zip"
        with ZipFile(zip_path, "w") as zf:
            zf.writestr("apple_health_export/export.xml", b"<HealthData></HealthData>")

        workout = Element("Workout")
        interval = Element("WorkoutActivity")
        interval.append(
            Element(
                "MetadataEntry",
                attrib={"key": "WOIntervalStepKeyPath", "value": "0.0.0"},
            )
        )
        interval.append(
            Element(
                "MetadataEntry",
                attrib={"key": "HKElevationAscended", "value": "25 m"},
            )
        )
        workout.append(interval)

        top_elevation = Element(
            "MetadataEntry",
            attrib={"key": "HKElevationAscended", "value": "100 m"},
        )
        workout.append(top_elevation)

        parser = ep.ExportParser()
        record: ep.WorkoutRecord = {"activityType": "Running"}

        with ZipFile(zip_path, "r") as zf:
            parser._process_workout_children(workout, record, zf)  # type: ignore[misc]

        assert record.get("ElevationAscended") == pytest.approx(100.0)
        assert record.get("ElevationAscendedUnit") == "m"

    def test_non_interval_activity_elevation_deferred_and_overridden_by_later_top_level(
        self, tmp_path: Path
    ) -> None:
        """Top-level HKElevationAscended after non-interval WorkoutActivity must take precedence."""
        zip_path = tmp_path / "test_export.zip"
        with ZipFile(zip_path, "w") as zf:
            zf.writestr("apple_health_export/export.xml", b"<HealthData></HealthData>")

        workout = Element("Workout")
        activity = Element("WorkoutActivity")
        activity.append(
            Element(
                "MetadataEntry",
                attrib={"key": "HKElevationAscended", "value": "30 m"},
            )
        )
        workout.append(activity)

        top_elevation = Element(
            "MetadataEntry",
            attrib={"key": "HKElevationAscended", "value": "150 m"},
        )
        workout.append(top_elevation)

        parser = ep.ExportParser()
        record: ep.WorkoutRecord = {"activityType": "Running"}

        with ZipFile(zip_path, "r") as zf:
            parser._process_workout_children(workout, record, zf)  # type: ignore[misc]

        assert record.get("ElevationAscended") == pytest.approx(150.0)
        assert record.get("ElevationAscendedUnit") == "m"

    def test_multiple_interval_activities_elevations_are_aggregated(self, tmp_path: Path) -> None:
        """Multiple interval activities without top-level elevation must aggregate their gains."""
        zip_path = tmp_path / "test_export.zip"
        with ZipFile(zip_path, "w") as zf:
            zf.writestr("apple_health_export/export.xml", b"<HealthData></HealthData>")

        workout = Element("Workout")
        for idx, elev_m in enumerate([20, 35, 15]):
            interval = Element("WorkoutActivity")
            interval.append(
                Element(
                    "MetadataEntry",
                    attrib={"key": "WOIntervalStepKeyPath", "value": f"{idx}.0.0"},
                )
            )
            interval.append(
                Element(
                    "MetadataEntry",
                    attrib={"key": "HKElevationAscended", "value": f"{elev_m} m"},
                )
            )
            workout.append(interval)

        parser = ep.ExportParser()
        record: ep.WorkoutRecord = {"activityType": "Running"}

        with ZipFile(zip_path, "r") as zf:
            parser._process_workout_children(workout, record, zf)  # type: ignore[misc]

        assert record.get("ElevationAscended") == pytest.approx(70.0)
        assert record.get("ElevationAscendedUnit") == "m"

    def test_multiple_non_interval_activities_elevations_are_aggregated(
        self, tmp_path: Path
    ) -> None:
        """Multiple non-interval activities without top-level elevation must aggregate
        their gains.
        """
        zip_path = tmp_path / "test_export.zip"
        with ZipFile(zip_path, "w") as zf:
            zf.writestr("apple_health_export/export.xml", b"<HealthData></HealthData>")

        workout = Element("Workout")
        for elev_m in [40, 60]:
            activity = Element("WorkoutActivity")
            activity.append(
                Element(
                    "MetadataEntry",
                    attrib={"key": "HKElevationAscended", "value": f"{elev_m} m"},
                )
            )
            workout.append(activity)

        parser = ep.ExportParser()
        record: ep.WorkoutRecord = {"activityType": "Running"}

        with ZipFile(zip_path, "r") as zf:
            parser._process_workout_children(workout, record, zf)  # type: ignore[misc]

        assert record.get("ElevationAscended") == pytest.approx(100.0)
        assert record.get("ElevationAscendedUnit") == "m"

    def test_earlier_top_level_elevation_precedes_nested_elevation(self, tmp_path: Path) -> None:
        """Top-level elevation placed before WorkoutActivity must also take precedence."""
        zip_path = tmp_path / "test_export.zip"
        with ZipFile(zip_path, "w") as zf:
            zf.writestr("apple_health_export/export.xml", b"<HealthData></HealthData>")

        workout = Element("Workout")
        top_elevation = Element(
            "MetadataEntry",
            attrib={"key": "HKElevationAscended", "value": "200 m"},
        )
        workout.append(top_elevation)

        interval = Element("WorkoutActivity")
        interval.append(
            Element(
                "MetadataEntry",
                attrib={"key": "WOIntervalStepKeyPath", "value": "0.0.0"},
            )
        )
        interval.append(
            Element(
                "MetadataEntry",
                attrib={"key": "HKElevationAscended", "value": "50 m"},
            )
        )
        workout.append(interval)

        parser = ep.ExportParser()
        record: ep.WorkoutRecord = {"activityType": "Running"}

        with ZipFile(zip_path, "r") as zf:
            parser._process_workout_children(workout, record, zf)  # type: ignore[misc]

        assert record.get("ElevationAscended") == pytest.approx(200.0)
        assert record.get("ElevationAscendedUnit") == "m"


class TestExtractElevationAscendedBoolBranch:
    """Tests for the bool branch in _extract_elevation_ascended."""

    def test_elevation_value_of_zero_parsed_as_bool_returns_none(self) -> None:
        """parse_value returns False for '0 m'; to_number must recover the numeric value."""
        elem = Element(
            "MetadataEntry",
            attrib={"key": "HKElevationAscended", "value": "0 m"},
        )
        # parse_value("0 m") -> (0.0, "m") which is not bool, so this hits the elif branch.
        # To hit the bool branch we need a bare "0" or "1" without unit.
        # parse_value("1") -> (True, None) — bool branch with no unit.
        elem_bool = Element(
            "MetadataEntry",
            attrib={"key": "HKElevationAscended", "value": "1"},
        )
        result = ep.ExportParser._extract_elevation_ascended(elem_bool)  # type: ignore[misc]
        assert result == (1.0, "m")

    def test_elevation_bool_zero_recovers_numeric_zero(self) -> None:
        """parse_value returns False for bare '0'; to_number recovers 0.0."""
        elem = Element(
            "MetadataEntry",
            attrib={"key": "HKElevationAscended", "value": "0"},
        )
        result = ep.ExportParser._extract_elevation_ascended(elem)  # type: ignore[misc]
        assert result == (0.0, "m")


class TestProcessIntervalActivityElevationWithoutNestedList:
    """Tests for _process_interval_activity_elevation called without nested_elevations."""

    def test_elevation_written_to_record_when_not_already_present(self) -> None:
        """When nested_elevations is None and record has no elevation, write directly."""
        elem = Element("WorkoutActivity")
        elem.append(
            Element(
                "MetadataEntry",
                attrib={"key": "HKElevationAscended", "value": "42 m"},
            )
        )
        parser = ep.ExportParser()
        record: ep.WorkoutRecord = {"activityType": "Running"}
        parser._process_interval_activity_elevation(elem, record)  # type: ignore[misc]
        assert record.get("ElevationAscended") == pytest.approx(42.0)

    def test_elevation_not_overwritten_when_already_present(self) -> None:
        """When nested_elevations is None and record already has elevation, skip."""
        elem = Element("WorkoutActivity")
        elem.append(
            Element(
                "MetadataEntry",
                attrib={"key": "HKElevationAscended", "value": "99 m"},
            )
        )
        parser = ep.ExportParser()
        record: ep.WorkoutRecord = {"activityType": "Running", "ElevationAscended": 10.0}  # type: ignore[typeddict-unknown-key]
        parser._process_interval_activity_elevation(elem, record)  # type: ignore[misc]
        assert record.get("ElevationAscended") == pytest.approx(10.0)


class TestProcessWorkoutActivityChildren:
    """Tests for _process_workout_activity_children (non-interval WorkoutActivity)."""

    def test_workout_statistics_fill_missing_only(self, tmp_path: Path) -> None:
        """WorkoutStatistics inside a non-interval activity fills missing keys only."""
        zip_path = tmp_path / "test.zip"
        with ZipFile(zip_path, "w") as zf:
            zf.writestr("apple_health_export/export.xml", b"<HealthData></HealthData>")

        activity = Element("WorkoutActivity")
        activity.append(
            Element(
                "WorkoutStatistics",
                attrib={
                    "type": "HKQuantityTypeIdentifierDistanceWalkingRunning",
                    "sum": "3",
                    "unit": "km",
                },
            )
        )
        parser = ep.ExportParser()
        record: ep.WorkoutRecord = {"activityType": "Running"}
        with ZipFile(zip_path) as zf:
            parser._process_workout_activity_children(activity, record, zf, active_end=None)  # type: ignore[misc]
        assert record.get("distance") == 3000

    def test_workout_statistics_does_not_overwrite_existing(self, tmp_path: Path) -> None:
        """WorkoutStatistics inside a non-interval activity must not overwrite existing keys."""
        zip_path = tmp_path / "test.zip"
        with ZipFile(zip_path, "w") as zf:
            zf.writestr("apple_health_export/export.xml", b"<HealthData></HealthData>")

        activity = Element("WorkoutActivity")
        activity.append(
            Element(
                "WorkoutStatistics",
                attrib={
                    "type": "HKQuantityTypeIdentifierDistanceWalkingRunning",
                    "sum": "99",
                    "unit": "km",
                },
            )
        )
        parser = ep.ExportParser()
        record: ep.WorkoutRecord = {"activityType": "Running", "distance": 5000}  # type: ignore[typeddict-unknown-key]
        with ZipFile(zip_path) as zf:
            parser._process_workout_activity_children(activity, record, zf, active_end=None)  # type: ignore[misc]
        assert record.get("distance") == 5000

    def test_metadata_entry_elevation_written_when_absent(self, tmp_path: Path) -> None:
        """ElevationAscended MetadataEntry is written when not already in record."""
        zip_path = tmp_path / "test.zip"
        with ZipFile(zip_path, "w") as zf:
            zf.writestr("apple_health_export/export.xml", b"<HealthData></HealthData>")

        activity = Element("WorkoutActivity")
        activity.append(
            Element(
                "MetadataEntry",
                attrib={"key": "HKElevationAscended", "value": "55 m"},
            )
        )
        parser = ep.ExportParser()
        record: ep.WorkoutRecord = {"activityType": "Running"}
        with ZipFile(zip_path) as zf:
            parser._process_workout_activity_children(activity, record, zf, active_end=None)  # type: ignore[misc]
        assert record.get("ElevationAscended") == pytest.approx(55.0)

    def test_metadata_entry_elevation_not_overwritten(self, tmp_path: Path) -> None:
        """ElevationAscended MetadataEntry is skipped when already in record."""
        zip_path = tmp_path / "test.zip"
        with ZipFile(zip_path, "w") as zf:
            zf.writestr("apple_health_export/export.xml", b"<HealthData></HealthData>")

        activity = Element("WorkoutActivity")
        activity.append(
            Element(
                "MetadataEntry",
                attrib={"key": "HKElevationAscended", "value": "99 m"},
            )
        )
        parser = ep.ExportParser()
        record: ep.WorkoutRecord = {"activityType": "Running", "ElevationAscended": 20.0}  # type: ignore[typeddict-unknown-key]
        with ZipFile(zip_path) as zf:
            parser._process_workout_activity_children(activity, record, zf, active_end=None)  # type: ignore[misc]
        assert record.get("ElevationAscended") == pytest.approx(20.0)

    def test_non_elevation_metadata_entry_is_written(self, tmp_path: Path) -> None:
        """Non-elevation MetadataEntry inside a non-interval activity is written normally."""
        zip_path = tmp_path / "test.zip"
        with ZipFile(zip_path, "w") as zf:
            zf.writestr("apple_health_export/export.xml", b"<HealthData></HealthData>")

        activity = Element("WorkoutActivity")
        activity.append(
            Element(
                "MetadataEntry",
                attrib={"key": "HKMetadataKeyTimeZone", "value": "Europe/Paris"},
            )
        )
        parser = ep.ExportParser()
        record: ep.WorkoutRecord = {"activityType": "Running"}
        with ZipFile(zip_path) as zf:
            parser._process_workout_activity_children(activity, record, zf, active_end=None)  # type: ignore[misc]
        assert record.get("MetadataKeyTimeZone") == "Europe/Paris"

    def test_workout_route_inside_non_interval_activity_is_processed(self, tmp_path: Path) -> None:
        """WorkoutRoute inside a non-interval WorkoutActivity is loaded."""
        route_gpx = b"""<?xml version="1.0" encoding="UTF-8"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1">
    <trk><trkseg>
        <trkpt lat="0" lon="0"><ele>100</ele><time>2024-01-01T10:00:00Z</time></trkpt>
        <trkpt lat="0" lon="0.01"><ele>110</ele><time>2024-01-01T10:01:00Z</time></trkpt>
    </trkseg></trk>
</gpx>
"""
        zip_path = tmp_path / "test.zip"
        with ZipFile(zip_path, "w") as zf:
            zf.writestr("apple_health_export/export.xml", b"<HealthData></HealthData>")
            zf.writestr("apple_health_export/workout-routes/activity.gpx", route_gpx)

        route_elem = Element(
            "WorkoutRoute",
            attrib={
                "startDate": "2024-01-01 10:00:00 +0000",
                "endDate": "2024-01-01 10:02:00 +0000",
            },
        )
        route_elem.append(
            Element("FileReference", attrib={"path": "/workout-routes/activity.gpx"})
        )
        activity = Element("WorkoutActivity")
        activity.append(route_elem)

        parser = ep.ExportParser()
        record: ep.WorkoutRecord = {"activityType": "Running"}
        with ZipFile(zip_path) as zf:
            parser._process_workout_activity_children(activity, record, zf, active_end=None)  # type: ignore[misc]
        assert record.get("route") is not None


class TestCollectWorkoutEventEdgeCases:
    """Tests for early-return branches in _collect_workout_event."""

    def test_non_lap_segment_event_is_ignored(self) -> None:
        """WorkoutEvent with type other than Lap/Segment must be ignored."""
        child = Element(
            "WorkoutEvent",
            attrib={
                "type": "HKWorkoutEventTypeMotionPaused",
                "date": "2024-01-01 10:00:00 +0000",
                "duration": "60",
                "durationUnit": "s",
            },
        )
        parser = ep.ExportParser()
        record: ep.WorkoutRecord = {"activityType": "Swimming"}
        parser._collect_workout_event(child, record)  # type: ignore[misc]
        assert "swimming_events" not in record

    def test_lap_event_with_missing_duration_is_ignored(self) -> None:
        """Lap event without duration must be ignored."""
        child = Element(
            "WorkoutEvent",
            attrib={
                "type": "HKWorkoutEventTypeLap",
                "date": "2024-01-01 10:00:00 +0000",
            },
        )
        parser = ep.ExportParser()
        record: ep.WorkoutRecord = {"activityType": "Swimming"}
        parser._collect_workout_event(child, record)  # type: ignore[misc]
        assert "swimming_events" not in record
