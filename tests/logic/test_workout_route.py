"""Unit tests for workout route domain models and calculations."""

import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
from zipfile import ZipFile

import pytest

from logic.export_parser import ExportParser
from logic.workout_manager import WorkoutManager
from logic.workout_route import RoutePoint, WorkoutRoute
from tests.conftest import build_health_export_xml, load_export_fragment


def _point(
    iso_time: str,
    latitude: float,
    longitude: float,
    altitude: float = 0.0,
) -> RoutePoint:
    """Build a RoutePoint from a UTC ISO datetime string."""
    return RoutePoint(
        time=datetime.fromisoformat(iso_time.replace("Z", "+00:00")),
        latitude=latitude,
        longitude=longitude,
        altitude=altitude,
    )


def _load_gpx_route(gpx_path: Path) -> WorkoutRoute:
    """Load a WorkoutRoute from a GPX file fixture."""
    # GPX namespace URI, not a transport URL, disable sonar alert
    namespace = {"gpx": "http://www.topografix.com/GPX/1/1"}  # NOSONAR
    root = ET.parse(gpx_path).getroot()
    points: list[RoutePoint] = []

    for trkpt in root.findall(".//gpx:trkpt", namespace):
        ele = trkpt.find("gpx:ele", namespace)
        point_time = trkpt.find("gpx:time", namespace)
        lat_value = trkpt.get("lat")
        lon_value = trkpt.get("lon")
        if (
            ele is None
            or ele.text is None
            or point_time is None
            or point_time.text is None
            or lat_value is None
            or lon_value is None
        ):
            continue
        points.append(
            RoutePoint(
                time=datetime.fromisoformat(point_time.text.replace("Z", "+00:00")),
                latitude=float(lat_value),
                longitude=float(lon_value),
                altitude=float(ele.text),
            )
        )

    return WorkoutRoute(points=points)


class TestWorkoutRoute:
    """Test WorkoutRoute calculations and helpers."""

    def test_empty_route_metrics(self) -> None:
        """An empty route should report zeroed metrics."""
        route = WorkoutRoute(points=[])

        assert route.is_empty
        assert route.duration_seconds == pytest.approx(0.0, abs=1e-9)  # type: ignore[arg-type]
        assert route.distance_meters == pytest.approx(0.0, abs=1e-9)  # type: ignore[arg-type]
        assert route.elevation_gain_m == pytest.approx(0.0, abs=1e-9)  # type: ignore[arg-type]
        assert route.elevation_loss_m == pytest.approx(0.0, abs=1e-9)  # type: ignore[arg-type]

    def test_single_point_route_metrics(self) -> None:
        """A route with one point has no duration, distance, or elevation changes."""
        route = WorkoutRoute(points=[_point("2024-01-01T10:00:00Z", 48.8566, 2.3522, 100.0)])

        assert not route.is_empty
        assert route.duration_seconds == pytest.approx(0.0, abs=1e-9)  # type: ignore[arg-type]
        assert route.distance_meters == pytest.approx(0.0, abs=1e-9)  # type: ignore[arg-type]
        assert route.elevation_gain_m == pytest.approx(0.0, abs=1e-9)  # type: ignore[arg-type]
        assert route.elevation_loss_m == pytest.approx(0.0, abs=1e-9)  # type: ignore[arg-type]

    def test_duration_distance_and_elevation_metrics(self) -> None:
        """Duration, distance, gain, and loss should be accumulated across segments."""
        route = WorkoutRoute(
            points=[
                _point("2024-01-01T10:00:00Z", 48.8566, 2.3522, 100.0),
                _point("2024-01-01T10:01:00Z", 48.8567, 2.3523, 105.0),
                _point("2024-01-01T10:03:00Z", 48.8568, 2.3524, 103.0),
            ]
        )

        assert route.duration_seconds == pytest.approx(180.0, abs=1e-9)  # type: ignore[arg-type]
        assert route.distance_meters > 0.0
        assert route.elevation_gain_m == pytest.approx(5.0)  # type: ignore[misc]
        assert route.elevation_loss_m == pytest.approx(2.0)  # type: ignore[misc]

    def test_to_dataframe_contains_expected_columns_and_values(self) -> None:
        """to_dataframe should preserve point ordering and field values."""
        point_a = _point("2024-01-01T10:00:00Z", 48.8566, 2.3522, 100.0)
        point_b = _point("2024-01-01T10:01:00Z", 48.8567, 2.3523, 101.0)
        route = WorkoutRoute(points=[point_a, point_b])

        df = route.to_dataframe()

        assert list(df.columns) == ["time", "latitude", "longitude", "altitude"]
        assert len(df) == 2
        assert df.iloc[0]["time"] == point_a.time
        assert df.iloc[0]["latitude"] == point_a.latitude
        assert df.iloc[0]["longitude"] == point_a.longitude
        assert df.iloc[0]["altitude"] == point_a.altitude

    def test_add_point_appends_to_route(self) -> None:
        """add_point should append a new RoutePoint to the route."""
        route = WorkoutRoute(points=[])
        new_point = _point("2024-01-01T10:00:00Z", 48.8566, 2.3522, 100.0)

        route.add_point(new_point)

        assert len(route.points) == 1
        assert route.points[0] == new_point
        assert not route.is_empty

    def test_find_fastest_segment_from_real_gpx_fixture(self) -> None:
        """find_fastest_segment should return the known best traveled 1000m segment."""
        route_path = (
            Path(__file__).resolve().parents[1]
            / "fixtures"
            / "exports"
            / "workout-routes"
            / "route_2025-09-16_6.15pm.gpx"
        )
        route = _load_gpx_route(route_path)

        result = route.find_fastest_segment(1000.0)

        assert result is not None
        assert result == pytest.approx(375.0)  # type: ignore[misc]

    def test_find_fastest_segment_applies_realistic_distance_scaling(self) -> None:
        """A modest route/workout distance mismatch should be normalized."""
        start_time = datetime.fromisoformat("2024-01-01T10:00:00+00:00")
        route = WorkoutRoute(
            points=[
                RoutePoint(
                    time=start_time,
                    latitude=0.0,
                    longitude=0.0,
                    altitude=0.0,
                    speed=1.0,
                ),
                RoutePoint(
                    time=start_time + timedelta(seconds=95),
                    latitude=0.0,
                    longitude=0.0,
                    altitude=0.0,
                    speed=1.0,
                ),
            ]
        )

        scale_factor = WorkoutRoute.calculate_distance_scale_factor(95.0, 100.0)

        result = route.find_fastest_segment(100.0, distance_scale_factor=scale_factor)

        assert scale_factor > 1.0
        assert result == pytest.approx(95.0)  # type: ignore[misc]

    def test_calculate_distance_scale_factor_rejects_unrealistic_mismatch(self) -> None:
        """Large route/workout distance mismatches should not be normalized."""
        scale_factor = WorkoutRoute.calculate_distance_scale_factor(1000.0, 1300.0)

        assert scale_factor == pytest.approx(1.0)  # type: ignore[misc]

    def test_find_fastest_segment_from_real_gpx_fixture_not_found(self) -> None:
        """find_fastest_segment should return None if no segment meets the required length."""
        route_path = (
            Path(__file__).resolve().parents[1]
            / "fixtures"
            / "exports"
            / "workout-routes"
            / "route_2025-09-16_6.15pm.gpx"
        )
        route = _load_gpx_route(route_path)

        # Distance is approx 8km so we should not find a result
        result = route.find_fastest_segment(10000.0)

        assert result is None

    def test_find_fastest_segment_window_returns_duration_and_timestamps(self) -> None:
        """find_fastest_segment_window should match find_fastest_segment duration
        and give timestamps."""
        route_path = (
            Path(__file__).resolve().parents[1]
            / "fixtures"
            / "exports"
            / "workout-routes"
            / "route_2025-09-16_6.15pm.gpx"
        )
        route = _load_gpx_route(route_path)

        window = route.find_fastest_segment_window(1000.0)

        assert window is not None
        duration_s, seg_start, seg_end = window
        assert duration_s == pytest.approx(375.0)  # type: ignore[misc]
        # The window should span exactly the returned duration
        elapsed = (seg_end - seg_start).total_seconds()
        assert elapsed == pytest.approx(duration_s)  # type: ignore[misc]

    def test_find_fastest_segment_window_returns_none_when_no_segment(self) -> None:
        """find_fastest_segment_window should return None when no segment meets the length."""
        route_path = (
            Path(__file__).resolve().parents[1]
            / "fixtures"
            / "exports"
            / "workout-routes"
            / "route_2025-09-16_6.15pm.gpx"
        )
        route = _load_gpx_route(route_path)

        result = route.find_fastest_segment_window(10000.0)

        assert result is None


class TestWorkoutRouteEndToEnd:
    """End-to-end checks using real workout and GPX fixtures."""

    def test_running_route_metrics_vs_workout_manager(self, tmp_path: Path) -> None:
        """Compare route-derived metrics against workout/manager metrics from real fixtures.

        Route and workout metrics are compared with explicit tolerances to account
        for known calculation model differences (e.g., GPS polyline distance versus
        workout summary values).
        """

        workout_xml = load_export_fragment("workout_running.xml")
        route_file = (
            Path(__file__).resolve().parents[1]
            / "fixtures"
            / "exports"
            / "workout-routes"
            / "route_2025-09-16_6.15pm.gpx"
        )

        zip_path = tmp_path / "running_with_route.zip"
        with ZipFile(zip_path, "w") as zf:
            zf.writestr("apple_health_export/export.xml", build_health_export_xml([workout_xml]))
            zf.writestr(
                "apple_health_export/workout-routes/route_2025-09-16_6.15pm.gpx",
                route_file.read_bytes(),
            )

        parser = ExportParser()
        with parser:
            parsed = parser.parse(str(zip_path))

        manager = WorkoutManager(parsed.workouts)
        workouts = manager.workouts

        assert len(workouts) == 1
        workout = workouts.iloc[0]
        route = workout["route"]

        assert isinstance(route, WorkoutRoute)
        assert route.points

        route_metrics = {
            "distance_m": route.distance_meters,
            "duration_s": route.duration_seconds,
            "elevation_gain_m": route.elevation_gain_m,
        }
        manager_metrics = {
            "distance_m": float(manager.get_total_distance("Running", unit="m")),
            "duration_s": float(workout["duration"]),
            "elevation_gain_m": float(manager.get_total_elevation("Running", unit="m")),
        }

        # Sanity checks ensure the comparison is meaningful and based on parsed data.
        assert route_metrics["distance_m"] > 0
        assert route_metrics["duration_s"] > 0
        assert route_metrics["elevation_gain_m"] >= 0
        assert manager_metrics["distance_m"] > 0
        assert manager_metrics["duration_s"] > 0
        assert manager_metrics["elevation_gain_m"] >= 0

        tolerance = 0.01  # 1% relative tolerance

        assert route_metrics["distance_m"] == pytest.approx(  # type: ignore[misc]
            manager_metrics["distance_m"],
            rel=tolerance,
        )
        assert route_metrics["duration_s"] == pytest.approx(  # type: ignore[misc]
            manager_metrics["duration_s"],
            rel=tolerance,
        )

        # Elevation comparison uses ratio bounds instead of percent tolerance because these
        # metrics are fundamentally different:
        # - route.elevation_gain_m:
        #       raw point-to-point GPS altitude deltas (noisy, ~±5-10m per sample)
        # - manager.elevation_gain_m:
        #       Apple's processed health metric (barometer-filtered, sensor-fused)
        # Raw GPS accumulates small per-point errors (~±2m) across 100+ track points, resulting in
        # 30-50% higher values than devices with barometric pressure smoothing. Ratio bounds of
        # 0.70-1.50 acknowledge this inherent measurement method variance
        # while ensuring data integrity.
        elevation_ratio = route_metrics["elevation_gain_m"] / manager_metrics["elevation_gain_m"]
        assert 0.70 <= elevation_ratio <= 1.50, (
            f"Elevation ratio {elevation_ratio:.2f} outside bounds [0.70, 1.50]. "
            f"Route: {route_metrics['elevation_gain_m']:.2f}m, "
            f"Manager: {manager_metrics['elevation_gain_m']:.2f}m"
        )


class TestSortedTimes:
    """Tests for the WorkoutRoute.sorted_times() caching helper."""

    def test_sorted_times_returns_point_timestamps(self) -> None:
        """sorted_times() should return timestamps matching point order."""
        p1 = _point("2024-01-01T10:00:00Z", 48.0, 2.0)
        p2 = _point("2024-01-01T10:01:00Z", 48.1, 2.1)
        p3 = _point("2024-01-01T10:02:00Z", 48.2, 2.2)
        route = WorkoutRoute(points=[p1, p2, p3])

        times = route.sorted_times()

        assert times == [p1.time, p2.time, p3.time]

    def test_sorted_times_is_cached(self) -> None:
        """sorted_times() should return the same list object on repeated calls."""
        route = WorkoutRoute(
            points=[
                _point("2024-01-01T10:00:00Z", 48.0, 2.0),
                _point("2024-01-01T10:01:00Z", 48.1, 2.1),
            ]
        )

        first = route.sorted_times()
        second = route.sorted_times()

        assert first is second

    def test_sorted_times_cache_invalidated_on_add_point(self) -> None:
        """Adding a point should invalidate the sorted_times cache."""
        p1 = _point("2024-01-01T10:00:00Z", 48.0, 2.0)
        p2 = _point("2024-01-01T10:01:00Z", 48.1, 2.1)
        route = WorkoutRoute(points=[p1])

        before = route.sorted_times()
        assert len(before) == 1

        route.add_point(p2)
        after = route.sorted_times()

        assert len(after) == 2
        assert after[1] == p2.time
        # Cache was rebuilt: new list object
        assert before is not after

    def test_sorted_times_empty_route(self) -> None:
        """sorted_times() should return an empty list for a route with no points."""
        route = WorkoutRoute(points=[])

        assert route.sorted_times() == []
