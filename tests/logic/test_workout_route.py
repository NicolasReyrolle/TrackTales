"""Unit tests for workout route domain models and calculations."""

import xml.etree.ElementTree as ET
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from zipfile import ZipFile

import pytest

from logic.export_parser import ExportParser
from logic.workout_manager import WorkoutManager
from logic.workout_route import RoutePoint, WorkoutRoute


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
        duration_s, seg_start, seg_end, elevation_change = window
        assert duration_s == pytest.approx(375.0)  # type: ignore[misc]
        assert elevation_change == pytest.approx(-14.496923)  # type: ignore[misc]
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

    def test_running_route_metrics_vs_workout_manager(
        self,
        tmp_path: Path,
        load_export_fragment: Callable[[str], str],
        build_health_export_xml: Callable[[list[str]], str],
    ) -> None:
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


class TestComputeSplits:
    """Tests for WorkoutRoute.compute_splits()."""

    @staticmethod
    def _speed_route(
        num_points: int,
        seconds_per_point: float,
        speed_m_s: float,
        start_iso: str = "2024-01-01T10:00:00Z",
        altitude: float = 100.0,
    ) -> WorkoutRoute:
        """Build a route where each point has a constant GPS speed (m/s).

        Distance is computed from the average of consecutive point speeds so
        using a constant value gives a clean, predictable cumulative distance.
        """
        start = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
        points = [
            RoutePoint(
                time=start + timedelta(seconds=i * seconds_per_point),
                latitude=0.0,
                longitude=0.0,
                altitude=altitude,
                speed=speed_m_s,
            )
            for i in range(num_points)
        ]
        return WorkoutRoute(points=points)

    def test_empty_route_returns_empty(self) -> None:
        """compute_splits on an empty route should return an empty list."""
        assert WorkoutRoute(points=[]).compute_splits() == []

    def test_single_point_route_returns_empty(self) -> None:
        """compute_splits on a one-point route should return an empty list."""
        route = WorkoutRoute(points=[_point("2024-01-01T10:00:00Z", 0.0, 0.0)])
        assert route.compute_splits() == []

    def test_route_shorter_than_split_returns_empty(self) -> None:
        """A route covering less than split_distance_m returns no splits."""
        # 3 m/s * 100 s = 300 m total → less than 1 km
        route = self._speed_route(num_points=101, seconds_per_point=1.0, speed_m_s=3.0)
        assert route.compute_splits(split_distance_m=1000.0) == []

    def test_returns_correct_number_of_complete_splits(self) -> None:
        """Only complete splits should be returned; the partial last km is dropped."""
        # 3 m/s * 1 s/point = 3 m/point.
        # 3001 points gives 3000 s and 3 * 3000 = 9000 m with avg-speed calc.
        # But avg of (speed[i]+speed[i+1])/2 * dt for constant speed gives same result.
        # 9 000 m → 9 full splits of 1000 m; no partial split.
        route = self._speed_route(num_points=3001, seconds_per_point=1.0, speed_m_s=3.0)
        splits = route.compute_splits(split_distance_m=1000.0)
        assert len(splits) == 9

    def test_split_keys_present(self) -> None:
        """Each split dict must contain the expected keys."""
        route = self._speed_route(num_points=1001, seconds_per_point=1.0, speed_m_s=3.0)
        splits = route.compute_splits(split_distance_m=1000.0)
        assert len(splits) >= 1
        for split in splits:
            assert "split" in split
            assert "duration_s" in split
            assert "pace_min_per_km" in split
            assert "elevation_change_m" in split

    def test_split_numbers_are_sequential(self) -> None:
        """Split numbers should be 1-indexed and contiguous."""
        route = self._speed_route(num_points=3001, seconds_per_point=1.0, speed_m_s=3.0)
        splits = route.compute_splits(split_distance_m=1000.0)
        for i, split in enumerate(splits, start=1):
            assert split["split"] == i

    def test_pace_is_consistent_with_duration_and_distance(self) -> None:
        """pace_min_per_km should equal (duration_s / 60) * (1000 / split_distance_m)."""
        route = self._speed_route(num_points=1001, seconds_per_point=1.0, speed_m_s=3.0)
        splits = route.compute_splits(split_distance_m=1000.0)
        assert len(splits) >= 1
        for split in splits:
            expected_pace = float(split["duration_s"]) / 60.0 * (1000.0 / 1000.0)
            assert float(split["pace_min_per_km"]) == pytest.approx(expected_pace)  # type: ignore[misc]

    def test_elevation_change_reflects_altitude_difference(self) -> None:
        """elevation_change_m should equal end altitude minus start altitude for each split."""
        start = datetime.fromisoformat("2024-01-01T10:00:00Z".replace("Z", "+00:00"))
        # Create a route that ascends 1 m every second while moving at 3 m/s.
        points = [
            RoutePoint(
                time=start + timedelta(seconds=i),
                latitude=0.0,
                longitude=0.0,
                altitude=float(i),  # linearly increasing altitude
                speed=3.0,
            )
            for i in range(1001)
        ]
        route = WorkoutRoute(points=points)
        splits = route.compute_splits(split_distance_m=1000.0)
        assert len(splits) >= 1
        # Each 1000 m / 3 m/s = 333.3 s → altitude change ≈ 333 m
        for split in splits:
            assert float(split["elevation_change_m"]) == pytest.approx(  # type: ignore[misc]
                float(split["duration_s"]), rel=0.01
            )

    def test_scale_factor_changes_split_count(self) -> None:
        """A distance_scale_factor > 1 should reduce the number of splits (shorter route)."""
        route = self._speed_route(num_points=3001, seconds_per_point=1.0, speed_m_s=3.0)
        splits_no_scale = route.compute_splits(split_distance_m=1000.0, distance_scale_factor=1.0)
        # With a scale of 0.8, effective distance = 9000 * 0.8 = 7200 m → 7 splits.
        splits_scaled = route.compute_splits(split_distance_m=1000.0, distance_scale_factor=0.8)
        assert len(splits_scaled) < len(splits_no_scale)

    def test_real_gpx_fixture_produces_splits(self) -> None:
        """compute_splits should return at least one split for the real 8.9km GPX fixture."""
        route_path = (
            Path(__file__).resolve().parents[1]
            / "fixtures"
            / "exports"
            / "workout-routes"
            / "route_2025-09-16_6.15pm.gpx"
        )
        route = _load_gpx_route(route_path)
        splits = route.compute_splits(split_distance_m=1000.0)
        assert len(splits) >= 8
        for split in splits:
            assert float(split["pace_min_per_km"]) > 0

    def test_custom_split_distance(self) -> None:
        """compute_splits should honour arbitrary split_distance_m values."""
        route = self._speed_route(num_points=1001, seconds_per_point=1.0, speed_m_s=3.0)
        splits_500 = route.compute_splits(split_distance_m=500.0)
        splits_1000 = route.compute_splits(split_distance_m=1000.0)
        # Half the distance → roughly twice as many splits.
        assert len(splits_500) >= 2 * len(splits_1000) - 1
