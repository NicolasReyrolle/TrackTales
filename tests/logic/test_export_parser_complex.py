"""Tests for complex workout parsing and route handling."""

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from xml.etree.ElementTree import Element
from zipfile import ZipFile

import pandas as pd
import pytest

from logic.export_parser import ExportParser, WorkoutRecord
from logic.workout_route import RoutePoint, WorkoutRoute


class TestComplexRealWorldWorkout:
    """Test parsing of a complex real-world Apple Health workout with multiple elements."""

    def test_parse_complex_workout_with_all_elements(
        self,
        create_health_zip: Callable[..., str],
        load_export_fragment: Callable[[str], str],
        build_health_export_xml: Callable[[list[str]], str],
    ) -> None:
        """Test parsing a complex running workout with multiple activities and route"""

        xml_content = build_health_export_xml([load_export_fragment("workout_running.xml")])
        zip_path = create_health_zip(xml_content=xml_content)

        parser = ExportParser()
        with parser:
            health_data = parser.parse(str(zip_path))

        # Verify the workout was parsed
        assert len(health_data.workouts) == 1

        # Get the parsed workout record
        workout = health_data.workouts.iloc[0]

        # Verify basic attributes
        assert workout["activityType"] == "Running"
        assert workout["startDate"] == pd.Timestamp("2025-09-16 16:14:50")
        assert workout["endDate"] == "2025-09-16 17:15:43 +0100"
        assert workout["duration"] == 3653
        assert workout["durationUnit"] == "seconds"
        assert workout["source"] == "Apple Watch"

        # Verify metadata entries were captured
        assert not workout["IndoorWorkout"]  # "0" converts to False
        assert workout["TimeZone"] == "Europe/Paris"
        assert workout["WeatherHumidity"] == pytest.approx(  # type: ignore[misc]
            64.0, abs=0.001
        )  # "6400 %" -> 64.0
        assert workout["WeatherTemperature"] == pytest.approx(  # type: ignore[misc]
            16.650, abs=0.001
        )  # 61.9694 degF -> ~16.650 degC

        # Verify statistics were captured
        assert workout["sumStepCount"] == pytest.approx(9787.18)  # type: ignore[misc]
        assert workout["averageRunningGroundContactTime"] == pytest.approx(  # type: ignore[misc]
            303.967
        )
        assert workout["minimumRunningGroundContactTime"] == 231
        assert workout["maximumRunningGroundContactTime"] == 353
        assert workout["averageRunningPower"] == pytest.approx(208.697)  # type: ignore[misc]
        assert workout["sumActiveEnergyBurned"] == pytest.approx(1655.465)  # type: ignore[misc]
        assert workout["distance"] == 8955
        assert workout["averageHeartRate"] == pytest.approx(130.153)  # type: ignore[misc]

        # Verify metadata entries for elevation
        assert workout["ElevationAscended"] == pytest.approx(65.75, abs=0.01)  # type: ignore[misc]

    def test_parse_workout_with_multiple_route_parts(
        self,
        tmp_path: Path,
        load_export_fragment: Callable[[str], str],
        build_health_export_xml: Callable[[list[str]], str],
    ) -> None:
        """A workout containing multiple WorkoutRoute entries should preserve route parts.

        Analytics should use route_parts (window-bounded parts), while route remains
        as a backward-compatible merged representation.
        """
        workout_fragment = load_export_fragment("workout_running_multiple_parts.xml")
        route_dir = Path(__file__).resolve().parents[1] / "fixtures" / "exports" / "workout-routes"
        route_files = sorted(route_dir.glob("route_2025-09-26_*.gpx"))

        zip_path = tmp_path / "running_multi_parts.zip"
        with ZipFile(zip_path, "w") as zf:
            xml_content = build_health_export_xml([workout_fragment])
            zf.writestr("apple_health_export/export.xml", xml_content)
            for route_file in route_files:
                zf.writestr(
                    f"apple_health_export/workout-routes/{route_file.name}",
                    route_file.read_bytes(),
                )

        parser = ExportParser()
        with parser:
            health_data = parser.parse(str(zip_path))

        assert len(health_data.workouts) == 1
        workout = health_data.workouts.iloc[0]

        assert isinstance(workout["route"], WorkoutRoute)
        assert isinstance(workout["route_parts"], list)

        merged_route = workout["route"]
        assert isinstance(merged_route, WorkoutRoute)

        route_parts = [part for part in workout["route_parts"] if isinstance(part, WorkoutRoute)]
        assert route_parts
        assert len(route_parts) == len(route_files)

        expected_points = len(route_parts[0].points)
        for route_part in route_parts[1:]:
            expected_points += len(route_part.points)

        # Account for deduplication at part boundaries when adjacent files share one point.
        dedup_boundaries = 0
        for previous, current in zip(route_parts, route_parts[1:]):
            if previous.points and current.points and previous.points[-1] == current.points[0]:
                dedup_boundaries += 1

        assert len(merged_route.points) == expected_points - dedup_boundaries

    def test_route_windows_without_matching_points_are_skipped(
        self,
        tmp_path: Path,
        load_export_fragment: Callable[[str], str],
        build_health_export_xml: Callable[[list[str]], str],
    ) -> None:
        """WorkoutRoute windows with no points are intentionally dropped from route_parts."""
        workout_fragment = load_export_fragment("workout_running_too_fast.xml")
        route_dir = Path(__file__).resolve().parents[1] / "fixtures" / "exports" / "workout-routes"
        route_files = sorted(route_dir.glob("route_2024-12-26_*.gpx"))

        zip_path = tmp_path / "running_too_fast.zip"
        with ZipFile(zip_path, "w") as zf:
            xml_content = build_health_export_xml([workout_fragment])
            zf.writestr("apple_health_export/export.xml", xml_content)
            for route_file in route_files:
                zf.writestr(
                    f"apple_health_export/workout-routes/{route_file.name}",
                    route_file.read_bytes(),
                )

        parser = ExportParser()
        with parser:
            health_data = parser.parse(str(zip_path))

        assert len(health_data.workouts) == 1
        workout = health_data.workouts.iloc[0]
        route_parts = [part for part in workout["route_parts"] if isinstance(part, WorkoutRoute)]
        assert route_parts

        missing_window_start = pd.Timestamp("2024-12-26 14:53:58 +0100").to_pydatetime()
        missing_window_end = pd.Timestamp("2024-12-26 14:54:27 +0100").to_pydatetime()
        points_in_missing_window = [
            point
            for route_part in route_parts
            for point in route_part.points
            if missing_window_start <= point.time <= missing_window_end
        ]
        assert points_in_missing_window == []

    def test_workout_activity_stats_and_metadata_are_ignored(
        self,
        create_health_zip: Callable[..., str],
        build_health_export_xml: Callable[[list[str]], str],
    ) -> None:
        """Ensure data inside WorkoutActivity is not loaded into the workout record."""

        workout_fragment = """
<Workout workoutActivityType="HKWorkoutActivityTypeRunning"
         startDate="2024-01-01 10:00:00 +0000"
         endDate="2024-01-01 10:10:00 +0000" duration="10" durationUnit="min">
  <WorkoutActivity>
    <WorkoutStatistics type="HKQuantityTypeIdentifierActiveEnergyBurned" sum="123" unit="kcal"/>
    <MetadataEntry key="HKWeatherHumidity" value="5000 %"/>
  </WorkoutActivity>
</Workout>
""".strip()

        xml_content = build_health_export_xml([workout_fragment])
        zip_path = create_health_zip(xml_content=xml_content)

        parser = ExportParser()
        with parser:
            health_data = parser.parse(str(zip_path))

        workouts = health_data.workouts
        assert len(workouts) == 1

        assert "sumActiveEnergyBurned" not in workouts.columns
        assert "WeatherHumidity" not in workouts.columns

    def test_parse_multiple_separate_workouts_with_different_distance_units(
        self,
        tmp_path: Path,
        load_export_fragment: Callable[[str], str],
        build_health_export_xml: Callable[[list[str]], str],
    ) -> None:
        """Test parsing an export file containing separate swimming and running workouts.

        This verifies that:
        - Swimming workout with distance in meters (750 m) is correctly parsed
        - Running workout with distance in kilometers (8.95512 km) is correctly parsed
        - Both workouts are parsed as separate records with their correct distance units
        """

        swimming_workout = load_export_fragment("workout_swimming.xml")
        running_workout = load_export_fragment("workout_running.xml")

        # Create HealthData XML with both separate workouts
        xml_content = build_health_export_xml([swimming_workout, running_workout])

        zip_path = tmp_path / "multiple_workouts.zip"
        with ZipFile(zip_path, "w") as zf:
            zf.writestr("apple_health_export/export.xml", xml_content.encode("utf-8"))

        parser = ExportParser()
        with parser:
            health_data = parser.parse(str(zip_path))

        # Should parse as two separate workout records
        workouts = health_data.workouts
        assert len(workouts) == 2

        # First workout: Swimming
        swimming = workouts.iloc[0]
        assert swimming["activityType"] == "Swimming"
        assert swimming["distance"] == 750
        assert swimming["averageHeartRate"] == pytest.approx(102.834)  # type: ignore[misc]

        # Second workout: Running
        running = workouts.iloc[1]
        assert running["activityType"] == "Running"
        assert running["distance"] == 8955
        assert running["averageHeartRate"] == pytest.approx(130.153)  # type: ignore[misc]
        assert running["ElevationAscended"] == pytest.approx(65.75, abs=0.01)  # type: ignore[misc]

    def test_metadata_not_duplicated_when_present_at_multiple_levels(
        self,
        create_health_zip: Callable[..., str],
        load_export_fragment: Callable[[str], str],
        build_health_export_xml: Callable[[list[str]], str],
    ) -> None:
        """Test that duplicate metadata entries at the top-level Workout are not processed twice.

        The workout_running.xml fixture has duplicate MetadataEntry elements at the top-level
        <Workout> element:
        - First set appears before <WorkoutActivity> (lines 2-7)
        - Same entries appear again after <WorkoutActivity> (lines 66-71)
        - The <WorkoutActivity> contains only one metadata key "WOIntervalStepKeyPath" which is
          skipped by the parser and doesn't overlap with top-level metadata

        The parser should process each unique metadata key only once with its original value,
        not accumulate or double the values when encountering the same key multiple times.

        This test verifies that duplicate top-level metadata entries are ignored after their first
        occurrence and that the resulting workout record contains the correct, non-duplicated
        values for humidity, elevation, temperature, and boolean flags.
        """

        xml_content = build_health_export_xml([load_export_fragment("workout_running.xml")])
        zip_path = create_health_zip(xml_content=xml_content)

        parser = ExportParser()
        with parser:
            health_data = parser.parse(str(zip_path))

        workouts = health_data.workouts
        assert len(workouts) == 1
        workout = workouts.iloc[0]

        # Test metadata that appears twice at top-level Workout (before and after WorkoutActivity)
        # Original value: "6400 %" -> should be 64.0, NOT 128.0 (doubled)
        assert workout["WeatherHumidity"] == pytest.approx(64.0, abs=0.001)  # type: ignore[misc]

        # Original value: "6575 cm" -> should be 65.75 m, NOT 131.5 m (doubled)
        assert workout["ElevationAscended"] == pytest.approx(65.75, abs=0.01)  # type: ignore[misc]

        # Original value: "61.9694 degF" -> should be ~16.65°C, NOT ~33.3°C (doubled)
        assert workout["WeatherTemperature"] == pytest.approx(  # type: ignore[misc]
            16.650, abs=0.001
        )

        # Boolean metadata should remain False/True, not become True
        # (0 + 0 = 0, but semantically wrong)
        assert not workout["IndoorWorkout"]  # Should be False, not processed twice


class TestLoadRoute:
    """Test the _load_route method."""

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
            result = parser._load_route(zf, "/workout-routes/test_route.gpx")  # type: ignore[misc]

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
            result = parser._load_route(zf, "/workout-routes/empty_route.gpx")  # type: ignore[misc]

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
            # This should raise a ValueError when trying to parse empty time string
            with pytest.raises(ValueError):
                parser._load_route(zf, "/workout-routes/incomplete_route.gpx")  # type: ignore[misc]


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

        # Create a route element with FileReference child
        route_elem = Element("WorkoutRoute")
        file_ref = Element("FileReference", attrib={"path": "/workout-routes/test_route.gpx"})
        route_elem.append(file_ref)

        parser = ExportParser()
        record: WorkoutRecord = {"activityType": "Running"}

        with ZipFile(zip_path, "r") as zf:
            parser._process_workout_route(route_elem, record, zf)  # type: ignore[misc]

        # Verify route data is loaded
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
            parser._process_workout_route(route_elem, record, zf)  # type: ignore[misc]

        # Record should remain unchanged if no FileReference
        assert record == {"activityType": "Running"}


class TestClipRouteToWindow:
    """Tests for ExportParser.clip_route_to_window (binary-search implementation)."""

    def _make_route(self, iso_times: list[str]) -> WorkoutRoute:
        """Build a WorkoutRoute with one point per ISO timestamp."""
        points = [
            RoutePoint(
                time=datetime.fromisoformat(t.replace("Z", "+00:00")),
                latitude=float(i),
                longitude=float(i),
                altitude=0.0,
            )
            for i, t in enumerate(iso_times)
        ]
        return WorkoutRoute(points=points)

    def test_clip_keeps_points_within_window(self) -> None:
        """Points inside [window_start, window_end] must be returned."""
        route = self._make_route(
            [
                "2024-01-01T10:00:00Z",
                "2024-01-01T10:01:00Z",
                "2024-01-01T10:02:00Z",
                "2024-01-01T10:03:00Z",
                "2024-01-01T10:04:00Z",
            ]
        )
        start = datetime.fromisoformat("2024-01-01T10:01:00+00:00")
        end = datetime.fromisoformat("2024-01-01T10:03:00+00:00")

        clipped = ExportParser.clip_route_to_window(route, start, end)

        assert len(clipped.points) == 3
        assert clipped.points[0].time == datetime.fromisoformat("2024-01-01T10:01:00+00:00")
        assert clipped.points[-1].time == datetime.fromisoformat("2024-01-01T10:03:00+00:00")

    def test_clip_no_window_returns_copy_of_all_points(self) -> None:
        """When either bound is None all route points are returned."""
        route = self._make_route(
            ["2024-01-01T10:00:00Z", "2024-01-01T10:01:00Z", "2024-01-01T10:02:00Z"]
        )

        clipped_no_start = ExportParser.clip_route_to_window(route, None, route.points[-1].time)
        clipped_no_end = ExportParser.clip_route_to_window(route, route.points[0].time, None)
        clipped_both_none = ExportParser.clip_route_to_window(route, None, None)

        assert len(clipped_no_start.points) == 3
        assert len(clipped_no_end.points) == 3
        assert len(clipped_both_none.points) == 3

    def test_clip_empty_route_returns_empty(self) -> None:
        """Clipping an empty route should return an empty route."""
        route = WorkoutRoute(points=[])
        start = datetime.fromisoformat("2024-01-01T10:00:00+00:00")
        end = datetime.fromisoformat("2024-01-01T10:05:00+00:00")

        clipped = ExportParser.clip_route_to_window(route, start, end)

        assert not clipped.points

    def test_clip_window_outside_range_returns_empty(self) -> None:
        """A window entirely before or after route points returns an empty route."""
        route = self._make_route(
            ["2024-01-01T10:00:00Z", "2024-01-01T10:01:00Z", "2024-01-01T10:02:00Z"]
        )
        # window after all points
        start_after = datetime.fromisoformat("2024-01-01T11:00:00+00:00")
        end_after = datetime.fromisoformat("2024-01-01T11:05:00+00:00")
        assert not ExportParser.clip_route_to_window(route, start_after, end_after).points

        # window before all points
        start_before = datetime.fromisoformat("2024-01-01T09:00:00+00:00")
        end_before = datetime.fromisoformat("2024-01-01T09:59:00+00:00")
        assert not ExportParser.clip_route_to_window(route, start_before, end_before).points

    def test_clip_uses_sorted_times_cache(self) -> None:
        """Clipping the same route twice should return the same sorted_times list object."""
        route = self._make_route(
            ["2024-01-01T10:00:00Z", "2024-01-01T10:01:00Z", "2024-01-01T10:02:00Z"]
        )
        start = datetime.fromisoformat("2024-01-01T10:00:00+00:00")
        end = datetime.fromisoformat("2024-01-01T10:02:00+00:00")

        ExportParser.clip_route_to_window(route, start, end)
        times_first = route.sorted_times()

        # Second clip must reuse the cached list (same object identity)
        ExportParser.clip_route_to_window(route, start, end)
        times_second = route.sorted_times()

        assert times_first is times_second
