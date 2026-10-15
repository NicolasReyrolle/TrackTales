"""Tests for complex workout parsing and route handling."""

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from zipfile import ZipFile

import pandas as pd
import pytest

from logic.export_parser import ExportParser, WorkoutRecord
from logic.workout_manager.workout_route import RoutePoint, WorkoutRoute


class TestComplexRealWorldWorkout:
    """Test parsing of a complex real-world Apple Health workout with multiple elements."""

    def test_gpx_point_without_elevation_is_marked_unavailable(self) -> None:
        """An omitted GPX <ele> is distinct from a valid zero-meter altitude."""
        from lxml.etree import Element

        namespace = "http://www.topografix.com/GPX/1/1"
        point_elem = Element(f"{{{namespace}}}trkpt", attrib={"lat": "48.8566", "lon": "2.3522"})
        time_elem = Element(f"{{{namespace}}}time")
        time_elem.text = "2024-01-01T00:00:00Z"
        point_elem.append(time_elem)

        point_data = ExportParser._extract_gpx_point_data(point_elem)
        point = ExportParser._create_route_point(*point_data)

        assert point.altitude == pytest.approx(0.0)
        assert not point.altitude_available

    def test_estimated_elevation_uses_discrete_route_parts(self) -> None:
        """A merged boundary jump between route windows is not counted as climbing."""

        def make_route(altitude: float, start_hour: int) -> WorkoutRoute:
            return WorkoutRoute(
                points=[
                    RoutePoint(
                        time=datetime(2024, 1, 1, start_hour, minute),
                        latitude=48.8566,
                        longitude=2.3522,
                        altitude=altitude,
                    )
                    for minute in range(10)
                ]
            )

        route_parts = [make_route(100.0, 0), make_route(200.0, 1)]
        merged_route = WorkoutRoute(
            points=[point for route_part in route_parts for point in route_part.points]
        )
        record: WorkoutRecord = {
            "activityType": "Running",
            "route": merged_route,
            "route_parts": route_parts,
        }

        assert merged_route.estimated_elevation_gain_m() == pytest.approx(100.0)
        ExportParser._apply_estimated_elevation(record)

        assert record.get("ElevationAscended") == pytest.approx(0.0)

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

        assert len(health_data.workouts) == 1

        workout = health_data.workouts.iloc[0]

        assert workout["activityType"] == "Running"
        assert workout["startDate"] == pd.Timestamp("2025-09-16 16:14:50")
        assert workout["endDate"] == "2025-09-16 17:15:43 +0100"
        assert workout["duration"] == 3653
        assert workout["durationUnit"] == "seconds"
        assert workout["source"] == "Apple Watch"

        assert not workout["IndoorWorkout"]  # "0" converts to False
        assert workout["TimeZone"] == "Europe/Paris"
        assert workout["WeatherHumidity"] == pytest.approx(64.0, abs=0.001)  # "6400 %" -> 64.0
        assert workout["WeatherTemperature"] == pytest.approx(
            16.650, abs=0.001
        )  # 61.9694 degF -> ~16.650 degC

        assert workout["sumStepCount"] == pytest.approx(9787.18)
        assert workout["averageRunningGroundContactTime"] == pytest.approx(303.967)
        assert workout["minimumRunningGroundContactTime"] == 231
        assert workout["maximumRunningGroundContactTime"] == 353
        assert workout["averageRunningPower"] == pytest.approx(208.697)
        assert workout["sumActiveEnergyBurned"] == pytest.approx(655.465)
        assert workout["distance"] == 8955
        assert workout["averageHeartRate"] == pytest.approx(130.153)

        assert workout["ElevationAscended"] == pytest.approx(65.75, abs=0.01)

    def test_parse_complex_workout_loads_elevation_from_nested_activity(
        self,
        create_health_zip: Callable[..., str],
        load_export_fragment: Callable[[str], str],
        build_health_export_xml: Callable[[list[str]], str],
    ) -> None:
        """Elevation ascended is loaded from nested WorkoutActivity metadata."""

        xml_content = build_health_export_xml(
            [load_export_fragment("workout_running_long_distance.xml")]
        )
        zip_path = create_health_zip(xml_content=xml_content)

        parser = ExportParser()
        with parser:
            health_data = parser.parse(str(zip_path))

        assert len(health_data.workouts) == 1

        workout = health_data.workouts.iloc[0]

        assert workout["ElevationAscended"] == pytest.approx(428.75)

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
        route_dir = Path(__file__).resolve().parents[2] / "fixtures" / "exports" / "workout-routes"
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

        dedup_boundaries = 0
        for previous, current in zip(route_parts, route_parts[1:]):
            if previous.points and current.points and previous.points[-1] == current.points[0]:
                dedup_boundaries += 1

        assert len(merged_route.points) == expected_points - dedup_boundaries

    def test_elevation_estimated_from_route_when_missing(
        self,
        tmp_path: Path,
        load_export_fragment: Callable[[str], str],
        build_health_export_xml: Callable[[list[str]], str],
    ) -> None:
        """A workout without HKElevationAscended gets a noise-filtered gain from its route."""
        fragment = load_export_fragment("workout_running_without_elevation.xml")
        exports_dir = Path(__file__).resolve().parents[2] / "fixtures" / "exports"
        route_file = exports_dir / "workout-routes" / "route_2024-08-14_7.59pm.gpx"

        zip_path = tmp_path / "no_elevation.zip"
        with ZipFile(zip_path, "w") as zf:
            zf.writestr("apple_health_export/export.xml", build_health_export_xml([fragment]))
            zf.writestr(
                f"apple_health_export/workout-routes/{route_file.name}", route_file.read_bytes()
            )

        parser = ExportParser()
        with parser:
            health_data = parser.parse(str(zip_path))

        workout = health_data.workouts.iloc[0]
        raw_gain = workout["route"].elevation_gain_m
        assert workout["ElevationAscendedUnit"] == "m"
        assert 0.0 < workout["ElevationAscended"] < raw_gain / 2

    def test_route_windows_without_matching_points_are_skipped(
        self,
        tmp_path: Path,
        load_export_fragment: Callable[[str], str],
        build_health_export_xml: Callable[[list[str]], str],
    ) -> None:
        """WorkoutRoute windows with no points are intentionally dropped from route_parts."""
        workout_fragment = load_export_fragment("workout_running_too_fast.xml")
        route_dir = Path(__file__).resolve().parents[2] / "fixtures" / "exports" / "workout-routes"
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

    @pytest.mark.parametrize("interval_key", ["WOIntervalStepKeyPath", "HKWOIntervalStepKeyPath"])
    def test_interval_workout_activities_do_not_double_count_data(
        self,
        tmp_path: Path,
        load_export_fragment: Callable[[str], str],
        build_health_export_xml: Callable[[list[str]], str],
        interval_key: str,
    ) -> None:
        """Custom workout with interval activities and overlapping routes is not double-counted."""
        workout_fragment = load_export_fragment(
            "workout_running_multiple_routes_too_fast.xml"
        ).replace('key="WOIntervalStepKeyPath"', f'key="{interval_key}"')
        route_dir = Path(__file__).resolve().parents[2] / "fixtures" / "exports" / "workout-routes"

        zip_path = tmp_path / "running_multiple_routes.zip"
        with ZipFile(zip_path, "w") as zf:
            zf.writestr(
                "apple_health_export/export.xml", build_health_export_xml([workout_fragment])
            )
            for route_file in sorted(route_dir.glob("route_2025-04-17_*.gpx")):
                zf.writestr(
                    f"apple_health_export/workout-routes/{route_file.name}",
                    route_file.read_bytes(),
                )

        parser = ExportParser()
        with parser:
            health_data = parser.parse(str(zip_path))

        workout = health_data.workouts.iloc[0]
        assert "WOIntervalStepSuccessful" not in workout.index
        assert workout["distance"] == 7857
        speed_kmh = workout["distance"] / 1000 / (workout["duration"] / 3600)
        assert 9.0 < speed_kmh < 10.0

        route_parts = [part for part in workout["route_parts"] if isinstance(part, WorkoutRoute)]
        part_bounds = [(part.points[0].time, part.points[-1].time) for part in route_parts]
        assert len(part_bounds) == len(set(part_bounds))
        assert sum(part.distance_meters for part in route_parts) < workout["distance"]

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

        xml_content = build_health_export_xml([swimming_workout, running_workout])

        zip_path = tmp_path / "multiple_workouts.zip"
        with ZipFile(zip_path, "w") as zf:
            zf.writestr("apple_health_export/export.xml", xml_content.encode("utf-8"))

        parser = ExportParser()
        with parser:
            health_data = parser.parse(str(zip_path))

        workouts = health_data.workouts
        assert len(workouts) == 2

        swimming = workouts.iloc[0]
        assert swimming["activityType"] == "Swimming"
        assert swimming["distance"] == 750
        assert swimming["averageHeartRate"] == pytest.approx(102.834)

        running = workouts.iloc[1]
        assert running["activityType"] == "Running"
        assert running["distance"] == 8955
        assert running["averageHeartRate"] == pytest.approx(130.153)
        assert running["ElevationAscended"] == pytest.approx(65.75, abs=0.01)

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

        # Original value: "6400 %" -> should be 64.0, NOT 128.0 (doubled)
        assert workout["WeatherHumidity"] == pytest.approx(64.0, abs=0.001)

        # Original value: "6575 cm" -> should be 65.75 m, NOT 131.5 m (doubled)
        assert workout["ElevationAscended"] == pytest.approx(65.75, abs=0.01)

        # Original value: "61.9694 degF" -> should be ~16.65°C, NOT ~33.3°C (doubled)
        assert workout["WeatherTemperature"] == pytest.approx(16.650, abs=0.001)

        assert not workout["IndoorWorkout"]


class TestHikingWorkoutParsing:
    """Test parsing of a hiking workout fixture."""

    def test_hiking_workout_elevation_parsed_correctly(
        self,
        create_health_zip: Callable[..., str],
        load_export_fragment: Callable[[str], str],
        build_health_export_xml: Callable[[list[str]], str],
    ) -> None:
        """ElevationAscended in the hiking fixture should be converted from cm to m."""
        xml_content = build_health_export_xml([load_export_fragment("workout_hiking.xml")])
        zip_path = create_health_zip(xml_content=xml_content)

        with ExportParser() as parser:
            health_data = parser.parse(str(zip_path))

        assert len(health_data.workouts) == 1
        workout = health_data.workouts.iloc[0]

        assert workout["activityType"] == "Hiking"
        # "11937 cm" -> 119.37 m
        assert workout["ElevationAscended"] == pytest.approx(119.37, abs=0.01)
        # WeatherTemperature: "38.8818 degF" -> ~3.82 °C
        assert workout["WeatherTemperature"] == pytest.approx(3.82, abs=0.01)
        # WeatherHumidity: "7200 %" -> 72.0
        assert workout["WeatherHumidity"] == pytest.approx(72.0, abs=0.01)
        assert not workout["IndoorWorkout"]
        assert workout["TimeZone"] == "Europe/Paris"
