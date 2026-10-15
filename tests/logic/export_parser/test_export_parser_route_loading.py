"""Tests for ExportParser route loading and processing."""

from datetime import datetime
from pathlib import Path
from zipfile import ZipFile

import pytest
from lxml.etree import Element

from logic.export_parser import ExportParser, WorkoutRecord
from logic.workout_manager.workout_route import WorkoutRoute


class TestLoadRoute:
    """Test the _load_route method."""

    def test_external_entities_are_not_resolved(self, tmp_path: Path) -> None:
        """Apple Health and GPX parsing must not expand external entities."""
        sentinel = tmp_path / "sentinel.txt"
        sentinel.write_text("9876.5", encoding="utf-8")
        entity_uri = sentinel.as_uri()
        zip_path = tmp_path / "external_entity_export.zip"
        xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE HealthData [<!ENTITY external SYSTEM "{entity_uri}">]>
<HealthData>
    <Workout workoutActivityType="HKWorkoutActivityTypeRunning"
        startDate="2024-01-01 10:00:00 +0000" endDate="2024-01-01 10:01:00 +0000"
        duration="1" durationUnit="min">
        <MetadataEntry key="test">&external;</MetadataEntry>
        <WorkoutRoute startDate="2024-01-01 10:00:00 +0000"
            endDate="2024-01-01 10:01:00 +0000">
            <FileReference path="/workout-routes/external_entity.gpx"/>
        </WorkoutRoute>
    </Workout>
</HealthData>
"""
        gpx_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE gpx [<!ENTITY external SYSTEM "{entity_uri}">]>
<gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1">
    <trk><trkseg>
        <trkpt lat="48.8566" lon="2.3522">
            <ele>&external;</ele>
            <time>2024-01-01T10:00:00Z</time>
        </trkpt>
    </trkseg></trk>
</gpx>
"""
        with ZipFile(zip_path, "w") as zf:
            zf.writestr("apple_health_export/export.xml", xml_content)
            zf.writestr(
                "apple_health_export/workout-routes/external_entity.gpx",
                gpx_content,
            )

        with ExportParser() as parser:
            health_data = parser.parse(str(zip_path))

        workout = health_data.workouts.iloc[0]
        assert "&external;" in workout["xmlFragment"]
        assert "9876.5" not in workout["xmlFragment"]
        assert workout["route"].points[0].altitude == pytest.approx(0.0)

    def test_load_route_with_valid_gpx(self, tmp_path: Path) -> None:
        """Test loading a valid GPX route file."""
        zip_path = tmp_path / "route_export.zip"
        gpx_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1">
    <trk>
        <trkseg>
            <trkpt lat="48.8566" lon="2.3522">
                <ele>100.5</ele>
                <time>2024-01-01T10:00:00Z</time>
            </trkpt>
            <trkpt lat="48.8567" lon="2.3523">
                <ele>101.2</ele>
                <time>2024-01-01T10:01:00Z</time>
            </trkpt>
        </trkseg>
    </trk>
</gpx>
"""
        with ZipFile(zip_path, "w") as zf:
            zf.writestr("apple_health_export/workout-routes/test_route.gpx", gpx_content)

        parser = ExportParser()
        with ZipFile(zip_path, "r") as zf:
            result = parser._load_route(zf, "/workout-routes/test_route.gpx")

        assert result is not None
        assert len(result.points) == 2
        assert result.duration_seconds == pytest.approx(60.0, abs=1e-9)  # type: ignore[arg-type]
        assert result.distance_meters > 0.0
        assert result.elevation_gain_m > 0.0
        assert result.elevation_loss_m == pytest.approx(0.0, abs=1e-9)  # type: ignore[arg-type]

    def test_load_route_empty_gpx(self, tmp_path: Path) -> None:
        """Test loading an empty GPX file."""
        zip_path = tmp_path / "route_export.zip"
        gpx_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1">
    <trk>
        <trkseg>
        </trkseg>
    </trk>
</gpx>
"""
        with ZipFile(zip_path, "w") as zf:
            zf.writestr("apple_health_export/workout-routes/empty_route.gpx", gpx_content)

        parser = ExportParser()
        with ZipFile(zip_path, "r") as zf:
            result = parser._load_route(zf, "/workout-routes/empty_route.gpx")

        assert result is not None
        assert len(result.points) == 0

    def test_load_route_missing_ele_and_time(self, tmp_path: Path) -> None:
        """Test loading GPX with missing altitude and time elements."""
        zip_path = tmp_path / "route_export.zip"
        gpx_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1">
    <trk>
        <trkseg>
            <trkpt lat="48.8566" lon="2.3522">
            </trkpt>
        </trkseg>
    </trk>
</gpx>
"""
        with ZipFile(zip_path, "w") as zf:
            zf.writestr("apple_health_export/workout-routes/incomplete_route.gpx", gpx_content)

        parser = ExportParser()
        with ZipFile(zip_path, "r") as zf:
            result = parser._load_route(zf, "/workout-routes/incomplete_route.gpx")

        assert result is not None
        assert result.points == []

    def test_load_route_logs_malformed_trackpoint_error_details(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Malformed trackpoints should include error details in debug logs."""
        zip_path = tmp_path / "route_export.zip"
        gpx_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1">
    <trk>
        <trkseg>
            <trkpt lat="48.8566" lon="2.3522">
                <time>not-a-time</time>
            </trkpt>
        </trkseg>
    </trk>
</gpx>
"""
        with ZipFile(zip_path, "w") as zf:
            zf.writestr("apple_health_export/workout-routes/malformed_route.gpx", gpx_content)

        parser = ExportParser()
        with ZipFile(zip_path, "r") as zf, caplog.at_level("DEBUG"):
            result = parser._load_route(zf, "/workout-routes/malformed_route.gpx")

        assert result is not None
        assert result.points == []
        assert any(
            "Skipping malformed GPX trackpoint for /workout-routes/malformed_route.gpx (error:"
            in record.message
            for record in caplog.records
        )

    def test_load_route_with_speed_extension(self, tmp_path: Path) -> None:
        """GPX trackpoints with a speed extension should populate RoutePoint.speed."""
        zip_path = tmp_path / "route_speed.zip"
        gpx_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1">
    <trk><trkseg>
        <trkpt lat="48.8566" lon="2.3522">
            <ele>100.0</ele>
            <time>2024-01-01T10:00:00Z</time>
            <extensions><speed>3.5</speed></extensions>
        </trkpt>
        <trkpt lat="48.8567" lon="2.3523">
            <ele>101.0</ele>
            <time>2024-01-01T10:01:00Z</time>
            <extensions><speed>not-a-number</speed></extensions>
        </trkpt>
        <trkpt lat="48.8568" lon="2.3524">
            <ele>102.0</ele>
            <time>2024-01-01T10:02:00Z</time>
            <extensions><other>42</other></extensions>
        </trkpt>
    </trkseg></trk>
</gpx>
"""
        with ZipFile(zip_path, "w") as zf:
            zf.writestr("apple_health_export/workout-routes/speed_route.gpx", gpx_content)

        parser = ExportParser()
        with ZipFile(zip_path, "r") as zf:
            result = parser._load_route(zf, "/workout-routes/speed_route.gpx")

        assert result is not None
        assert len(result.points) == 3
        assert result.points[0].speed == pytest.approx(3.5)
        assert result.points[1].speed == pytest.approx(0.0)  # ValueError fallback
        assert result.points[2].speed == pytest.approx(0.0)  # no speed element

    def test_load_route_missing_lat_lon_does_not_emit_duplicate_malformed_log(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Missing coordinates should only emit the dedicated missing-lat/lon log."""
        zip_path = tmp_path / "route_export.zip"
        gpx_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1">
    <trk>
        <trkseg>
            <trkpt lat="" lon="">
                <time>2024-01-01T10:00:00Z</time>
            </trkpt>
        </trkseg>
    </trk>
</gpx>
"""
        with ZipFile(zip_path, "w") as zf:
            zf.writestr("apple_health_export/workout-routes/missing_coords_route.gpx", gpx_content)

        parser = ExportParser()
        with ZipFile(zip_path, "r") as zf, caplog.at_level("DEBUG"):
            result = parser._load_route(zf, "/workout-routes/missing_coords_route.gpx")

        assert result is not None
        assert result.points == []
        assert any(
            "Skipping GPX trackpoint with missing latitude/longitude" in record.message
            for record in caplog.records
        )
        assert not any(
            "Skipping malformed GPX trackpoint for /workout-routes/missing_coords_route.gpx"
            in record.message
            for record in caplog.records
        )


class TestProcessWorkoutRoute:
    """Test the _process_workout_route method."""

    def test_process_workout_route_with_file_reference(self, tmp_path: Path) -> None:
        """Test processing a workout route with FileReference."""
        zip_path = tmp_path / "route_export.zip"
        gpx_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1">
    <trk>
        <trkseg>
            <trkpt lat="48.8566" lon="2.3522">
                <ele>100.0</ele>
                <time>2024-01-01T10:00:00Z</time>
            </trkpt>
        </trkseg>
    </trk>
</gpx>
"""
        xml_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<HealthData>
    <Workout workoutActivityType="HKWorkoutActivityTypeRunning"
             startDate="2024-01-01" endDate="2024-01-01" duration="30">
        <WorkoutRoute sourceName="Apple Watch">
            <FileReference path="/workout-routes/test_route.gpx"/>
        </WorkoutRoute>
    </Workout>
</HealthData>
"""
        with ZipFile(zip_path, "w") as zf:
            zf.writestr("apple_health_export/export.xml", xml_content)
            zf.writestr("apple_health_export/workout-routes/test_route.gpx", gpx_content)

        route_elem = Element("WorkoutRoute")
        file_ref = Element("FileReference", attrib={"path": "/workout-routes/test_route.gpx"})
        route_elem.append(file_ref)

        parser = ExportParser()
        record: WorkoutRecord = {"activityType": "Running"}

        with ZipFile(zip_path, "r") as zf:
            parser._process_workout_route(route_elem, record, zf)

        assert record.get("route") is not None
        assert isinstance(record.get("route"), WorkoutRoute)

    def test_process_workout_route_empty_route_element(self, tmp_path: Path) -> None:
        """Test processing an empty workout route element."""
        zip_path = tmp_path / "route_export.zip"
        xml_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<HealthData>
</HealthData>
"""
        with ZipFile(zip_path, "w") as zf:
            zf.writestr("apple_health_export/export.xml", xml_content)

        route_elem = Element("WorkoutRoute")

        parser = ExportParser()
        record: WorkoutRecord = {"activityType": "Running"}

        with ZipFile(zip_path, "r") as zf:
            parser._process_workout_route(route_elem, record, zf)

        assert record == {"activityType": "Running"}

    def test_process_workout_route_clips_points_with_active_end(self, tmp_path: Path) -> None:
        """active_end should clamp WorkoutRoute windows so trailing points are excluded."""
        zip_path = tmp_path / "route_export.zip"
        gpx_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1">
    <trk><trkseg>
        <trkpt lat="48.8566" lon="2.3522"><ele>100.0</ele><time>2024-01-01T10:00:00Z</time></trkpt>
        <trkpt lat="48.8567" lon="2.3523"><ele>101.0</ele><time>2024-01-01T10:01:00Z</time></trkpt>
        <trkpt lat="48.8568" lon="2.3524"><ele>102.0</ele><time>2024-01-01T10:02:00Z</time></trkpt>
    </trkseg></trk>
</gpx>
"""
        with ZipFile(zip_path, "w") as zf:
            zf.writestr("apple_health_export/workout-routes/test_route.gpx", gpx_content)

        route_elem = Element(
            "WorkoutRoute",
            attrib={
                "startDate": "2024-01-01 10:00:00 +0000",
                "endDate": "2024-01-01 10:03:00 +0000",
            },
        )
        route_elem.append(
            Element("FileReference", attrib={"path": "/workout-routes/test_route.gpx"})
        )

        parser = ExportParser()
        record: WorkoutRecord = {"activityType": "Running"}
        active_end = datetime.fromisoformat("2024-01-01T10:01:00+00:00")

        with ZipFile(zip_path, "r") as zf:
            parser._process_workout_route(route_elem, record, zf, active_end=active_end)

        route_parts = record.get("route_parts")
        assert isinstance(route_parts, list)
        assert len(route_parts) == 1
        first_part = route_parts[0]
        assert isinstance(first_part, WorkoutRoute)
        assert len(first_part.points) == 2
        assert first_part.points[-1].time == active_end

        merged_route = record.get("route")
        assert isinstance(merged_route, WorkoutRoute)
        assert len(merged_route.points) == 2

    def test_process_workout_route_deduplicates_overlapping_windows(self, tmp_path: Path) -> None:
        """Partially overlapping windows trim overlap; suffix-only window is skipped."""
        zip_path = tmp_path / "route_export_overlap.zip"
        gpx_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1">
    <trk><trkseg>
        <trkpt lat="48.8566" lon="2.3522"><ele>100.0</ele><time>2024-01-01T10:00:00Z</time></trkpt>
        <trkpt lat="48.8567" lon="2.3523"><ele>101.0</ele><time>2024-01-01T10:01:00Z</time></trkpt>
        <trkpt lat="48.8568" lon="2.3524"><ele>102.0</ele><time>2024-01-01T10:02:00Z</time></trkpt>
        <trkpt lat="48.8569" lon="2.3525"><ele>103.0</ele><time>2024-01-01T10:03:00Z</time></trkpt>
        <trkpt lat="48.8570" lon="2.3526"><ele>104.0</ele><time>2024-01-01T10:04:00Z</time></trkpt>
    </trkseg></trk>
</gpx>
"""
        with ZipFile(zip_path, "w") as zf:
            zf.writestr("apple_health_export/workout-routes/test_overlap.gpx", gpx_content)

        # Window 1: 10:00 -> 10:02 (points at 10:00, 10:01, 10:02)
        route_elem_1 = Element(
            "WorkoutRoute",
            attrib={
                "startDate": "2024-01-01 10:00:00 +0000",
                "endDate": "2024-01-01 10:02:00 +0000",
            },
        )
        route_elem_1.append(
            Element("FileReference", attrib={"path": "/workout-routes/test_overlap.gpx"})
        )

        # Window 2: 10:01 -> 10:04 (overlaps 10:01-10:02, unique suffix 10:03-10:04)
        route_elem_2 = Element(
            "WorkoutRoute",
            attrib={
                "startDate": "2024-01-01 10:01:00 +0000",
                "endDate": "2024-01-01 10:04:00 +0000",
            },
        )
        route_elem_2.append(
            Element("FileReference", attrib={"path": "/workout-routes/test_overlap.gpx"})
        )

        # Window 3: 10:03 -> 10:04 (suffix of Window 2, completely duplicate)
        route_elem_3 = Element(
            "WorkoutRoute",
            attrib={
                "startDate": "2024-01-01 10:03:00 +0000",
                "endDate": "2024-01-01 10:04:00 +0000",
            },
        )
        route_elem_3.append(
            Element("FileReference", attrib={"path": "/workout-routes/test_overlap.gpx"})
        )

        parser = ExportParser()
        record: WorkoutRecord = {"activityType": "Running"}

        with ZipFile(zip_path, "r") as zf:
            parser._process_workout_route(route_elem_1, record, zf)
            parser._process_workout_route(route_elem_2, record, zf)
            parser._process_workout_route(route_elem_3, record, zf)

        route_parts = record.get("route_parts")
        assert isinstance(route_parts, list)
        assert len(route_parts) == 2

        part_1, part_2 = route_parts
        assert [p.time.isoformat() for p in part_1.points] == [
            "2024-01-01T10:00:00+00:00",
            "2024-01-01T10:01:00+00:00",
            "2024-01-01T10:02:00+00:00",
        ]
        assert [p.time.isoformat() for p in part_2.points] == [
            "2024-01-01T10:03:00+00:00",
            "2024-01-01T10:04:00+00:00",
        ]
