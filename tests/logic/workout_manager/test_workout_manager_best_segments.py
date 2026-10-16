"""Tests for WorkoutManager.get_best_segments and date-filtering."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zipfile import ZipFile

import pandas as pd
import pytest

from logic.export_parser import ExportParser
from logic.workout_manager import WorkoutManager
from logic.workout_manager.workout_route import RoutePoint, WorkoutRoute


def _two_point_route(
    duration_s: int,
    distance_deg_lon: float = 0.01,
    altitude_change: float = 1.0,
) -> WorkoutRoute:
    """Build a minimal route with one segment over ~1km for deterministic best-segment tests."""
    start_time = datetime(2025, 1, 1, tzinfo=UTC)
    end_time = start_time + pd.Timedelta(seconds=duration_s)
    return WorkoutRoute(
        points=[
            RoutePoint(time=start_time, latitude=0.0, longitude=0.0, altitude=0.0),
            RoutePoint(
                time=end_time,
                latitude=0.0,
                longitude=distance_deg_lon,
                altitude=altitude_change,
            ),
        ]
    )


class TestGetBestSegments:
    """Test suite for WorkoutManager.get_best_segments."""

    def test_returns_empty_dataframe_for_empty_manager(self) -> None:
        """No workouts should return an empty DataFrame with stable output columns."""
        manager = WorkoutManager()

        result = manager.get_best_segments(topn=3, distances=[1000])

        assert result.empty
        assert list(result.columns) == [
            "startDate",
            "distance",
            "duration_s",
            "segment_start",
            "segment_end",
            "elevation_change_m",
        ]

    def test_returns_empty_when_topn_is_non_positive(self) -> None:
        """Non-positive topn should return an empty DataFrame."""
        manager = WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "startDate": [pd.Timestamp("2025-01-01")],
                    "route": [_two_point_route(300)],
                }
            )
        )

        result = manager.get_best_segments(topn=0, distances=[1000])

        assert result.empty
        assert list(result.columns) == [
            "startDate",
            "distance",
            "duration_s",
            "segment_start",
            "segment_end",
            "elevation_change_m",
        ]

    def test_selects_fastest_segments_and_applies_topn(self) -> None:
        """topn should keep the fastest (smallest duration) segments per distance."""
        fast_route = _two_point_route(250)
        slow_route = _two_point_route(400, altitude_change=-2.0)

        manager = WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running", "Cycling"],
                    "startDate": [
                        pd.Timestamp("2025-01-02"),
                        pd.Timestamp("2025-01-01"),
                        pd.Timestamp("2025-01-03"),
                    ],
                    "route": [slow_route, fast_route, _two_point_route(200)],
                }
            )
        )

        top1 = manager.get_best_segments(topn=1, distances=[1000])
        assert len(top1) == 1
        assert int(top1.iloc[0]["distance"]) == 1000
        assert float(top1.iloc[0]["duration_s"]) == pytest.approx(250.0)  # type: ignore[misc]
        assert top1.iloc[0]["startDate"] == pd.Timestamp("2025-01-01")
        assert top1.iloc[0]["elevation_change_m"] == pytest.approx(1.0)  # type: ignore[misc]

        top2 = manager.get_best_segments(topn=2, distances=[1000])
        assert len(top2) == 2
        expected_durations = [pytest.approx(250.0), pytest.approx(400.0)]  # type: ignore[misc]
        assert list(top2["duration_s"]) == expected_durations
        expected_elevations = [pytest.approx(1.0), pytest.approx(-2.0)]  # type: ignore[misc]
        assert list(top2["elevation_change_m"]) == expected_elevations

    def test_with_real_fixture_running_route(
        self,
        tmp_path: Path,
        build_health_export_xml: Callable[[list[str]], str],
        load_export_fragment: Callable[[str], str],
    ) -> None:
        """Existing real fixture should produce a known best traveled 1000m segment."""
        workout_xml = load_export_fragment("workout_running.xml")
        route_file = (
            Path(__file__).resolve().parents[2]
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
        result = manager.get_best_segments(topn=1, distances=[1000])

        assert len(result) == 1
        assert int(result.iloc[0]["distance"]) == 1000
        expected_duration = pytest.approx(377.0, rel=1e-3)  # type: ignore[misc]
        assert float(result.iloc[0]["duration_s"]) == expected_duration

    def test_considers_each_route_part_separately(self) -> None:
        """Best-segment search should not bridge disjoint route parts."""
        start_time = datetime(2025, 9, 26, tzinfo=UTC)
        first_part = WorkoutRoute(
            points=[
                RoutePoint(time=start_time, latitude=0.0, longitude=0.0, altitude=0.0),
                RoutePoint(
                    time=start_time + pd.Timedelta(seconds=410),
                    latitude=0.0,
                    longitude=0.01,
                    altitude=0.0,
                ),
            ]
        )
        second_part = WorkoutRoute(
            points=[
                RoutePoint(
                    time=start_time + pd.Timedelta(seconds=670),
                    latitude=0.0,
                    longitude=0.01,
                    altitude=0.0,
                ),
                RoutePoint(
                    time=start_time + pd.Timedelta(seconds=930),
                    latitude=0.0,
                    longitude=0.02,
                    altitude=0.0,
                ),
            ]
        )

        merged_route = WorkoutRoute(points=first_part.points + second_part.points)

        manager = WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "startDate": [pd.Timestamp("2025-09-26")],
                    "route": [merged_route],
                    "route_parts": [[first_part, second_part]],
                }
            )
        )

        result = manager.get_best_segments(topn=2, distances=[1000])

        assert len(result) == 1
        assert list(result["distance"]) == [1000]
        assert abs(float(result.iloc[0]["duration_s"]) - 260.0) < 1e-6

    def test_route_fallback_splits_timestamp_reversals_into_monotonic_traces(self) -> None:
        """Route fallback should split on timestamp reversals and avoid bridge artifacts."""
        start_time = datetime(2025, 9, 26, tzinfo=UTC)
        route_with_reversal = WorkoutRoute(
            points=[
                RoutePoint(time=start_time, latitude=0.0, longitude=0.0, altitude=0.0),
                RoutePoint(
                    time=start_time + pd.Timedelta(seconds=400),
                    latitude=0.0,
                    longitude=0.01,
                    altitude=0.0,
                ),
                RoutePoint(
                    time=start_time + pd.Timedelta(seconds=200),
                    latitude=0.0,
                    longitude=0.01,
                    altitude=0.0,
                ),
                RoutePoint(
                    time=start_time + pd.Timedelta(seconds=460),
                    latitude=0.0,
                    longitude=0.02,
                    altitude=0.0,
                ),
            ]
        )

        manager = WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "startDate": [pd.Timestamp("2025-09-26")],
                    "route": [route_with_reversal],
                    "distance": [2000.0],
                }
            )
        )

        result = manager.get_best_segments(topn=1, distances=[1000])

        assert len(result) == 1
        assert list(result["distance"]) == [1000]
        assert abs(float(result.iloc[0]["duration_s"]) - 260.0) < 1e-6

    def test_last_unpaired_motion_paused_trims_vehicle_section(
        self,
        tmp_path: Path,
        load_export_fragment: Callable[[str], str],
        build_health_export_xml: Callable[[list[str]], str],
    ) -> None:
        """Active-end trimming removes vehicle GPS recorded after forgetting to stop the watch.

        Uses the Usain Bolt fixture XML (last MotionPaused at 16:46:13 +0100, no following
        MotionResumed) combined with a synthetic GPX that has:
          - 200 running points at ≈1 m/s (best 100 m ≈ 101 s)
          - 3 car points at ≈100 m/s starting 1 second after the last MotionPaused

        Without trimming the car section the best 100 m would be 1 s (impossible).
        With trimming it must be ≥ 100 s (realistic running pace).
        """
        # WorkoutRoute window: 14:30:02Z – 15:50:31Z (+0100 = UTC-1h)
        # Last MotionPaused in fixture: 2021-12-26 16:46:13 +0100 = 15:46:13Z
        t_run_start = datetime(2021, 12, 26, 14, 30, 2, tzinfo=UTC)
        t_car_start = datetime(2021, 12, 26, 15, 46, 14, tzinfo=UTC)  # 1s after pause

        step_deg = 0.000009  # ≈ 1 m at the equator (one degree latitude ≈ 111 139 m)
        running_points = "\n".join(
            f'      <trkpt lat="{i * step_deg:.9f}" lon="0.000000">'
            f"<ele>100</ele>"
            f"<time>{(t_run_start + timedelta(seconds=i)).strftime('%Y-%m-%dT%H:%M:%SZ')}</time>"
            "</trkpt>"
            for i in range(200)
        )
        car_points = "\n".join(
            f'      <trkpt lat="{(200 + i * 100) * step_deg:.9f}" lon="0.000000">'
            f"<ele>100</ele>"
            f"<time>{(t_car_start + timedelta(seconds=i)).strftime('%Y-%m-%dT%H:%M:%SZ')}</time>"
            "</trkpt>"
            for i in range(3)
        )
        gpx = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<gpx version="1.1" creator="Test" xmlns="http://www.topografix.com/GPX/1/1">'
            "<trk><trkseg>"
            f"{running_points}\n{car_points}"
            "</trkseg></trk></gpx>"
        )

        workout_xml = load_export_fragment("workout_running_usaint_bolt.xml")

        zip_path = tmp_path / "running_usaint_bolt_synthetic.zip"
        with ZipFile(zip_path, "w") as zf:
            zf.writestr("apple_health_export/export.xml", build_health_export_xml([workout_xml]))
            zf.writestr(
                "apple_health_export/workout-routes/route_2021-12-26_4.50pm.gpx",
                gpx.encode(),
            )

        parser = ExportParser()
        with parser:
            parsed = parser.parse(str(zip_path))

        manager = WorkoutManager(parsed.workouts)
        result = manager.get_best_segments(topn=1, distances=[100])

        assert len(result) == 1
        duration_s = float(result.iloc[0]["duration_s"])
        # Car section excluded; running at ≈1 m/s → need 101 steps for 100 m → 101 s
        assert duration_s >= 100.0, (
            f"Expected ≥ 100 s (car trimmed, running at 1 m/s), got {duration_s} s"
        )

    def test_real_fixture_too_fast_does_not_generate_one_second_100m(
        self,
        tmp_path: Path,
        load_export_fragment: Callable[[str], str],
        build_health_export_xml: Callable[[list[str]], str],
    ) -> None:
        """Window clipping and per-part analysis prevent impossible 100m=1s artifacts."""
        workout_xml = load_export_fragment("workout_running_too_fast.xml")
        route_dir = Path(__file__).resolve().parents[2] / "fixtures" / "exports" / "workout-routes"
        route_files = sorted(route_dir.glob("route_2024-12-26_*.gpx"))

        zip_path = tmp_path / "running_too_fast.zip"
        with ZipFile(zip_path, "w") as zf:
            zf.writestr("apple_health_export/export.xml", build_health_export_xml([workout_xml]))
            for route_file in route_files:
                zf.writestr(
                    f"apple_health_export/workout-routes/{route_file.name}",
                    route_file.read_bytes(),
                )

        parser = ExportParser()
        with parser:
            parsed = parser.parse(str(zip_path))

        manager = WorkoutManager(parsed.workouts)
        result = manager.get_best_segments(topn=1, distances=[100])

        assert len(result) == 1
        duration_s = float(result.iloc[0]["duration_s"])
        assert duration_s > 1.0

    def test_real_fixture_long_distance_includes_half_marathon_segments(
        self,
        tmp_path: Path,
        load_export_fragment: Callable[[str], str],
        build_health_export_xml: Callable[[list[str]], str],
    ) -> None:
        """Long-distance fixture should produce best segments beyond 5 km."""
        workout_xml = load_export_fragment("workout_running_long_distance.xml")
        route_file = (
            Path(__file__).resolve().parents[2]
            / "fixtures"
            / "exports"
            / "workout-routes"
            / "route_2025-11-30_6.06pm.gpx"
        )

        zip_path = tmp_path / "running_long_distance.zip"
        with ZipFile(zip_path, "w") as zf:
            zf.writestr("apple_health_export/export.xml", build_health_export_xml([workout_xml]))
            zf.writestr(
                "apple_health_export/workout-routes/route_2025-11-30_6.06pm.gpx",
                route_file.read_bytes(),
            )

        parser = ExportParser()
        with parser:
            parsed = parser.parse(str(zip_path))

        manager = WorkoutManager(parsed.workouts)
        distances = [100, 200, 400, 800, 1000, 5000, 10000, 15000, 21097]
        result = manager.get_best_segments(topn=1, distances=distances)

        available_distances = set(result["distance"].astype(int).tolist())
        assert 5000 in available_distances
        assert 10000 in available_distances
        assert 15000 in available_distances
        assert 21097 in available_distances

    def test_get_best_segments_ignores_single_point_route(self) -> None:
        """A route with fewer than two points should yield no best segment."""
        route = WorkoutRoute(
            points=[
                RoutePoint(
                    time=datetime(2025, 1, 1, tzinfo=UTC),
                    latitude=0.0,
                    longitude=0.0,
                    altitude=0.0,
                )
            ]
        )

        manager = WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "startDate": [pd.Timestamp("2025-01-01")],
                    "route": [route],
                }
            )
        )

        result = manager.get_best_segments(topn=1, distances=[100])

        assert result.empty

    def test_get_best_segments_handles_time_reversal_by_splitting_trace(self) -> None:
        """Timestamp reversals should split traces and still allow valid segment computation."""
        t0 = datetime(2025, 1, 1, tzinfo=UTC)
        route = WorkoutRoute(
            points=[
                RoutePoint(time=t0, latitude=0.0, longitude=0.0, altitude=0.0),
                RoutePoint(
                    time=t0 + timedelta(seconds=5),
                    latitude=0.0,
                    longitude=0.001,
                    altitude=0.0,
                ),
                RoutePoint(
                    time=t0 - timedelta(seconds=1),
                    latitude=0.0,
                    longitude=0.002,
                    altitude=0.0,
                ),
                RoutePoint(
                    time=t0 + timedelta(seconds=1),
                    latitude=0.0,
                    longitude=0.003,
                    altitude=0.0,
                ),
            ]
        )

        manager = WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "startDate": [pd.Timestamp("2025-01-01")],
                    "distance": [1000.0],
                    "route": [route],
                }
            )
        )

        result = manager.get_best_segments(topn=1, distances=[100])

        assert len(result) == 1
        assert int(result.iloc[0]["distance"]) == 100

    def test_get_best_segments_uses_default_distances_when_not_provided(self) -> None:
        """When distances is None, manager default segment distances should be used."""
        manager = WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "startDate": [pd.Timestamp("2025-01-01")],
                    "distance": [5000.0],
                    "route": [_two_point_route(300)],
                }
            )
        )

        result = manager.get_best_segments(topn=1, distances=None)

        assert not result.empty
        assert int(result.iloc[0]["distance"]) == 100

    def test_get_best_segments_skips_distance_above_run_distance(self) -> None:
        """Requested segment distance above run distance should be skipped."""
        manager = WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "startDate": [pd.Timestamp("2025-01-01")],
                    "distance": [500.0],
                    "route": [_two_point_route(300)],
                }
            )
        )

        result = manager.get_best_segments(topn=1, distances=[1000])

        assert result.empty
        assert list(result.columns) == [
            "startDate",
            "distance",
            "duration_s",
            "segment_start",
            "segment_end",
            "elevation_change_m",
        ]

    def test_get_best_segments_handles_nan_distance_by_using_route_trace(self) -> None:
        """NaN run distance should not block segment computation when route data exists."""
        manager = WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "startDate": [pd.Timestamp("2025-01-01")],
                    "distance": [float("nan")],
                    "route": [_two_point_route(300)],
                }
            )
        )

        result = manager.get_best_segments(topn=1, distances=[1000])

        assert len(result) == 1
        assert int(result.iloc[0]["distance"]) == 1000


class TestGetBestSegmentsDateFiltering:
    """Test date-range filtering in get_best_segments."""

    def test_get_best_segments_filters_by_start_date(self) -> None:
        """Workouts before start_date should be excluded."""
        manager = WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running"],
                    "startDate": [pd.Timestamp("2024-01-01"), pd.Timestamp("2024-06-01")],
                    "distance": [5000.0, 5000.0],
                    "route": [_two_point_route(300), _two_point_route(200)],
                }
            )
        )

        result = manager.get_best_segments(
            topn=5, distances=[1000], start_date=datetime(2024, 3, 1)
        )

        # Only the June workout should be included; January workout excluded
        assert not result.empty
        assert len(result) == 1
        assert result.iloc[0]["startDate"] == pd.Timestamp("2024-06-01")

    def test_get_best_segments_filters_by_end_date(self) -> None:
        """Workouts after end_date should be excluded."""
        manager = WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running"],
                    "startDate": [pd.Timestamp("2024-01-01"), pd.Timestamp("2024-06-01")],
                    "distance": [5000.0, 5000.0],
                    "route": [_two_point_route(300), _two_point_route(200)],
                }
            )
        )

        result = manager.get_best_segments(topn=5, distances=[1000], end_date=datetime(2024, 3, 31))

        # Only the January workout should be included; June workout excluded
        assert not result.empty
        assert len(result) == 1
        assert result.iloc[0]["startDate"] == pd.Timestamp("2024-01-01")

    def test_get_best_segments_filters_by_both_dates(self) -> None:
        """Only workouts within [start_date, end_date] should contribute."""
        manager = WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running", "Running"],
                    "startDate": [
                        pd.Timestamp("2024-01-01"),
                        pd.Timestamp("2024-03-15"),
                        pd.Timestamp("2024-06-01"),
                    ],
                    "distance": [5000.0, 5000.0, 5000.0],
                    "route": [_two_point_route(300), _two_point_route(200), _two_point_route(400)],
                }
            )
        )

        result = manager.get_best_segments(
            topn=5,
            distances=[1000],
            start_date=datetime(2024, 2, 1),
            end_date=datetime(2024, 4, 30),
        )

        # Only the March workout should be included
        assert not result.empty
        assert all(result["startDate"] >= pd.Timestamp("2024-02-01"))
        assert all(result["startDate"] <= pd.Timestamp("2024-04-30"))

    def test_get_best_segments_returns_empty_when_no_workouts_in_range(self) -> None:
        """Return empty DataFrame when date filter excludes all workouts."""
        manager = WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "startDate": [pd.Timestamp("2024-01-01")],
                    "distance": [5000.0],
                    "route": [_two_point_route(300)],
                }
            )
        )

        result = manager.get_best_segments(
            topn=5, distances=[1000], start_date=datetime(2024, 6, 1)
        )

        assert result.empty
        assert list(result.columns) == [
            "startDate",
            "distance",
            "duration_s",
            "segment_start",
            "segment_end",
            "elevation_change_m",
        ]

    def test_get_best_segments_end_date_is_inclusive(self) -> None:
        """A workout exactly on end_date should be included."""
        manager = WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "startDate": [pd.Timestamp("2024-03-31")],
                    "distance": [5000.0],
                    "route": [_two_point_route(300)],
                }
            )
        )

        result = manager.get_best_segments(topn=5, distances=[1000], end_date=datetime(2024, 3, 31))

        assert not result.empty


class TestBugConditionGpsInterruption:
    """Exploration tests for the GPS interruption scale-factor bug.

    These tests encode the EXPECTED (fixed) behavior.
    On unfixed code they are designed to FAIL — that failure is the proof the bug exists.

    Root cause: ``calculate_distance_scale_factor`` uses a symmetric ±10% guard
    (``abs(scale_factor - 1.0) <= 0.10``) which rejects any scale > 1.10, returning 1.0
    even when the GPS under-count is caused by legitimate pause-event recording gaps.

    Counterexamples observed on unfixed code:
    - ``calculate_distance_scale_factor(4440, 8695)`` → returns 1.0 instead of ≈ 1.9583
      (scale 1.9583 > 1.10, so the symmetric guard rejects it and falls back to 1.0)
    - ``calculate_distance_scale_factor(5370, 10580)`` → returns 1.0 instead of ≈ 1.9702
      (same symmetric guard rejection)
    - Issue-373 400 m best segment → ≈ 82 s (GPS-only distance) instead of ≈ 161 s (correct)
    - Issue-373 800 m best segment → ≈ 164 s instead of ≈ 322 s
    """

    def test_scale_factor_issue_373_returns_actual_ratio(self) -> None:
        """Unit: scale ≈ 1.96 must be returned, not the fallback 1.0.

        Bug condition: reference / route = 8695 / 4440 ≈ 1.9583, which is in (1.10, 2.0].
        Unfixed code returns 1.0 because the symmetric ±10% guard rejects it.
        """
        from logic.workout_manager.workout_route import WorkoutRoute

        result = WorkoutRoute.calculate_distance_scale_factor(
            route_distance_m=4440,
            reference_distance_m=8695,
        )
        assert result == pytest.approx(8695 / 4440, rel=1e-3)

    def test_scale_factor_second_example_returns_actual_ratio(self) -> None:
        """Unit: scale ≈ 1.97 must be returned, not the fallback 1.0.

        Bug condition: reference / route = 10580 / 5370 ≈ 1.9702, which is in (1.10, 2.0].
        Unfixed code returns 1.0 because the symmetric ±10% guard rejects it.
        """
        from logic.workout_manager.workout_route import WorkoutRoute

        result = WorkoutRoute.calculate_distance_scale_factor(
            route_distance_m=5370,
            reference_distance_m=10580,
        )
        assert result == pytest.approx(10580 / 5370, rel=1e-3)

    def test_issue_373_400m_best_segment(
        self,
        tmp_path: Path,
        build_health_export_xml: Callable[[list[str]], str],
        load_export_fragment: Callable[[str], str],
    ) -> None:
        """Integration: 400 m best segment for issue-373 workout uses GPS interruption scale.

        The fixture has GPS distance ≈ 4,507 m vs HealthKit 8,695 m (scale ≈ 1.929).
        Without the fix (scale rejected, falls back to 1.0) the 400 m window covers a raw
        400 GPS-m slice → ≈ 236 s.
        With the fix applied (scale ≈ 1.929) the window covers only ≈ 207 GPS-m → ≈ 114 s,
        confirming the scale factor is correctly accepted and applied.
        """
        workout_xml = load_export_fragment("workout_running_issue_373.xml")
        route_file = (
            Path(__file__).resolve().parents[2]
            / "fixtures"
            / "exports"
            / "workout-routes"
            / "route_2024-08-08_8.56pm.gpx"
        )

        zip_path = tmp_path / "issue_373.zip"
        with ZipFile(zip_path, "w") as zf:
            zf.writestr("apple_health_export/export.xml", build_health_export_xml([workout_xml]))
            zf.writestr(
                "apple_health_export/workout-routes/route_2024-08-08_8.56pm.gpx",
                route_file.read_bytes(),
            )

        parser = ExportParser()
        with parser:
            parsed = parser.parse(str(zip_path))

        manager = WorkoutManager(parsed.workouts)
        result = manager.get_best_segments(topn=1, distances=[400])

        assert len(result) == 1
        assert int(result.iloc[0]["distance"]) == 400
        # With scale ≈ 1.929 applied the window covers ~207 GPS-m; fixture yields ≈ 114 s.
        # Without the fix (scale=1.0) the window would cover 400 GPS-m yielding ≈ 236 s.
        assert float(result.iloc[0]["duration_s"]) == pytest.approx(114, abs=5)

    def test_issue_373_800m_best_segment(
        self,
        tmp_path: Path,
        build_health_export_xml: Callable[[list[str]], str],
        load_export_fragment: Callable[[str], str],
    ) -> None:
        """Integration: 800 m best segment for issue-373 workout uses GPS interruption scale.

        The fixture has GPS distance ≈ 4,507 m vs HealthKit 8,695 m (scale ≈ 1.929).
        Without the fix (scale=1.0) the 800 m window covers 800 GPS-m → ≈ 549 s.
        With the fix (scale ≈ 1.929) the window covers ~415 GPS-m → ≈ 247 s,
        confirming the scale factor is accepted and doubles the effective search distance.
        """
        workout_xml = load_export_fragment("workout_running_issue_373.xml")
        route_file = (
            Path(__file__).resolve().parents[2]
            / "fixtures"
            / "exports"
            / "workout-routes"
            / "route_2024-08-08_8.56pm.gpx"
        )

        zip_path = tmp_path / "issue_373_800m.zip"
        with ZipFile(zip_path, "w") as zf:
            zf.writestr("apple_health_export/export.xml", build_health_export_xml([workout_xml]))
            zf.writestr(
                "apple_health_export/workout-routes/route_2024-08-08_8.56pm.gpx",
                route_file.read_bytes(),
            )

        parser = ExportParser()
        with parser:
            parsed = parser.parse(str(zip_path))

        manager = WorkoutManager(parsed.workouts)
        result = manager.get_best_segments(topn=1, distances=[800])

        assert len(result) == 1
        assert int(result.iloc[0]["distance"]) == 800
        # With scale ≈ 1.929 applied the window covers ~415 GPS-m; fixture yields ≈ 247 s.
        # Without the fix (scale=1.0) the window would cover 800 GPS-m yielding ≈ 549 s.
        assert float(result.iloc[0]["duration_s"]) == pytest.approx(247, abs=5)


class TestScaleFactorWarningLogs:
    """Verify that _get_run_best_segment_rows emits the expected warning logs."""

    def _make_manager_with_scale(
        self,
        route_distance_deg: float,
        duration_s: int,
        declared_distance_m: float,
    ) -> "WorkoutManager":
        """Build a WorkoutManager whose single run has a specific GPS / HealthKit ratio."""
        from logic.workout_manager import WorkoutManager

        start_time = datetime(2025, 1, 1, tzinfo=UTC)
        end_time = start_time + pd.Timedelta(seconds=duration_s)
        route = WorkoutRoute(
            points=[
                RoutePoint(time=start_time, latitude=0.0, longitude=0.0, altitude=0.0),
                RoutePoint(
                    time=end_time,
                    latitude=0.0,
                    longitude=route_distance_deg,
                    altitude=0.0,
                ),
            ]
        )
        return WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "startDate": [pd.Timestamp("2025-01-01")],
                    "distance": [declared_distance_m],
                    "route": [route],
                }
            )
        )

    def test_warning_logged_when_gps_interruption_scale_accepted(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A warning is emitted when the GPS/HealthKit ratio is in (1.10, 2.0].

        The GPS route covers ~1,113 m (0.01 deg lon); HealthKit declares 2,000 m
        → raw_scale ≈ 1.80, which is in (1.10, 2.0] — interruption correction applied.
        """
        import logging

        from logic.workout_manager.segments import WorkoutManagerSegmentsMixin

        # ~1 113 m at the equator; HealthKit says 2 000 m → scale ≈ 1.80
        manager = self._make_manager_with_scale(
            route_distance_deg=0.01, duration_s=600, declared_distance_m=2000.0
        )

        with caplog.at_level(logging.WARNING, logger="logic.workout_manager.segments"):
            manager.get_best_segments(topn=1, distances=[100])

        warning_messages = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        assert any(
            "GPS interruption correction applied" in msg for msg in warning_messages
        ), f"Expected GPS interruption warning, got: {warning_messages}"

    def test_warning_logged_when_scale_exceeds_ceiling(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A warning is emitted when raw_scale > 2.0 (rejected at new ceiling).

        GPS route covers ~1,113 m; HealthKit declares 3,000 m → raw_scale ≈ 2.70 > 2.0.
        """
        import logging

        # ~1 113 m at the equator; HealthKit says 3 000 m → scale ≈ 2.70 (rejected)
        manager = self._make_manager_with_scale(
            route_distance_deg=0.01, duration_s=600, declared_distance_m=3000.0
        )

        with caplog.at_level(logging.WARNING, logger="logic.workout_manager.segments"):
            manager.get_best_segments(topn=1, distances=[100])

        warning_messages = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        assert any(
            "GPS distance scale factor rejected" in msg for msg in warning_messages
        ), f"Expected GPS rejection warning, got: {warning_messages}"

    def test_no_warning_logged_when_scale_within_tolerance(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """No warning is emitted when GPS/HealthKit ratio is within ±10%.

        GPS route covers ~1,113 m; HealthKit declares 1,150 m → scale ≈ 1.033.
        """
        import logging

        # ~1 113 m at the equator; HealthKit says 1 150 m → scale ≈ 1.03 (within ±10%)
        manager = self._make_manager_with_scale(
            route_distance_deg=0.01, duration_s=600, declared_distance_m=1150.0
        )

        with caplog.at_level(logging.WARNING, logger="logic.workout_manager.segments"):
            manager.get_best_segments(topn=1, distances=[100])

        warning_messages = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        gps_warnings = [
            msg
            for msg in warning_messages
            if "GPS interruption correction" in msg or "GPS distance scale factor rejected" in msg
        ]
        assert not gps_warnings, f"Expected no GPS warning, got: {gps_warnings}"
