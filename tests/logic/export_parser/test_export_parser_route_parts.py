"""Tests for route parts: clipping, merging, trimming, and split validation."""

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from zipfile import ZipFile

from logic.export_parser import ExportParser
from logic.workout_manager.workout_route import RoutePoint, WorkoutRoute


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
        start_after = datetime.fromisoformat("2024-01-01T11:00:00+00:00")
        end_after = datetime.fromisoformat("2024-01-01T11:05:00+00:00")
        assert not ExportParser.clip_route_to_window(route, start_after, end_after).points

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

        ExportParser.clip_route_to_window(route, start, end)
        times_second = route.sorted_times()

        assert times_first is times_second

    def test_clip_non_monotonic_route_falls_back_to_linear_scan(self) -> None:
        """Out-of-order route times should still clip correctly via linear fallback."""
        route = self._make_route(
            [
                "2024-01-01T10:00:00Z",
                "2024-01-01T10:03:00Z",
                "2024-01-01T10:01:00Z",
                "2024-01-01T10:02:00Z",
            ]
        )
        start = datetime.fromisoformat("2024-01-01T10:01:00+00:00")
        end = datetime.fromisoformat("2024-01-01T10:02:00+00:00")

        clipped = ExportParser.clip_route_to_window(route, start, end)

        assert [point.time for point in clipped.points] == [
            datetime.fromisoformat("2024-01-01T10:01:00+00:00"),
            datetime.fromisoformat("2024-01-01T10:02:00+00:00"),
        ]


class TestMergeRouteParts:
    """Tests for ExportParser._merge_route_parts."""

    @staticmethod
    def _make_point(minute: int, latitude: float, longitude: float) -> RoutePoint:
        return RoutePoint(
            time=datetime.fromisoformat(f"2024-01-01T10:{minute:02d}:00+00:00"),
            latitude=latitude,
            longitude=longitude,
            altitude=0.0,
        )

    def test_merge_empty_list_returns_none(self) -> None:
        """Merging an empty list of route parts returns None."""
        assert ExportParser._merge_route_parts([]) is None

    def test_merge_skips_overlapping_prefix_points(self) -> None:
        """Merged route should not duplicate overlapping points across parts."""
        first_part = WorkoutRoute(
            points=[
                self._make_point(0, 48.0, 2.0),
                self._make_point(1, 48.1, 2.1),
                self._make_point(2, 48.2, 2.2),
            ]
        )
        second_part = WorkoutRoute(
            points=[
                self._make_point(1, 48.1, 2.1),
                self._make_point(2, 48.2, 2.2),
                self._make_point(3, 48.3, 2.3),
            ]
        )

        merged = ExportParser._merge_route_parts([first_part, second_part])

        assert merged is not None
        merged_times = [point.time for point in merged.points]
        assert merged_times == [
            datetime.fromisoformat("2024-01-01T10:00:00+00:00"),
            datetime.fromisoformat("2024-01-01T10:01:00+00:00"),
            datetime.fromisoformat("2024-01-01T10:02:00+00:00"),
            datetime.fromisoformat("2024-01-01T10:03:00+00:00"),
        ]


class TestTrimOverlappingRoutePart:
    """Tests for ExportParser._trim_overlapping_route_part."""

    @staticmethod
    def _make_point(minute: int, latitude: float = 48.0, longitude: float = 2.0) -> RoutePoint:
        return RoutePoint(
            time=datetime.fromisoformat(f"2024-01-01T10:{minute:02d}:00+00:00"),
            latitude=latitude,
            longitude=longitude,
            altitude=0.0,
        )

    def test_trim_empty_route_part_returns_none(self) -> None:
        """A route part with no points returns None."""
        first_part = WorkoutRoute(points=[self._make_point(0), self._make_point(1)])
        empty_part = WorkoutRoute(points=[])
        result = ExportParser._trim_overlapping_route_part([first_part], empty_part)
        assert result is None

    def test_trim_suffix_empty_after_timestamp_dedup_returns_none(self) -> None:
        """A part whose points are new objects but share timestamps with
        existing parts returns None."""
        existing_point = self._make_point(0)
        existing_part = WorkoutRoute(points=[existing_point])
        # Different object, same timestamp — not in existing_points but time IS
        # in existing_timestamps
        duplicate_by_time = RoutePoint(
            time=existing_point.time,
            latitude=99.0,
            longitude=99.0,
            altitude=0.0,
        )
        new_part = WorkoutRoute(points=[duplicate_by_time])
        result = ExportParser._trim_overlapping_route_part([existing_part], new_part)
        assert result is None

    def test_trim_empty_existing_parts_returns_unchanged(self) -> None:
        """When there are no existing parts, route_part is returned unchanged."""
        route_part = WorkoutRoute(points=[self._make_point(0), self._make_point(1)])
        result = ExportParser._trim_overlapping_route_part([], route_part)
        assert result is route_part

    def test_trim_identical_part_returns_none(self) -> None:
        """An identical part has no unique points and returns None."""
        first_part = WorkoutRoute(points=[self._make_point(0), self._make_point(1)])
        second_part = WorkoutRoute(points=[self._make_point(0), self._make_point(1)])
        result = ExportParser._trim_overlapping_route_part([first_part], second_part)
        assert result is None

    def test_trim_suffix_of_existing_part_returns_none(self) -> None:
        """A window that is a suffix of an existing window is fully duplicate and returns None."""
        first_part = WorkoutRoute(
            points=[
                self._make_point(0),
                self._make_point(1),
                self._make_point(2),
                self._make_point(3),
            ]
        )
        suffix_part = WorkoutRoute(points=[self._make_point(2), self._make_point(3)])
        result = ExportParser._trim_overlapping_route_part([first_part], suffix_part)
        assert result is None

    def test_trim_partially_overlapping_window_preserves_unique_suffix(self) -> None:
        """Overlapping prefix points are trimmed while preserving the unique suffix points."""
        first_part = WorkoutRoute(
            points=[self._make_point(0), self._make_point(1), self._make_point(2)]
        )
        second_part = WorkoutRoute(
            points=[
                self._make_point(1),
                self._make_point(2),
                self._make_point(3),
                self._make_point(4),
            ]
        )
        result = ExportParser._trim_overlapping_route_part([first_part], second_part)
        assert result is not None
        assert [p.time for p in result.points] == [
            datetime.fromisoformat("2024-01-01T10:03:00+00:00"),
            datetime.fromisoformat("2024-01-01T10:04:00+00:00"),
        ]

    def test_trim_disjoint_window_returns_unchanged(self) -> None:
        """Non-overlapping windows are preserved without trimming."""
        first_part = WorkoutRoute(points=[self._make_point(0), self._make_point(1)])
        second_part = WorkoutRoute(points=[self._make_point(2), self._make_point(3)])
        result = ExportParser._trim_overlapping_route_part([first_part], second_part)
        assert result is second_part

    def test_trim_handles_multiple_existing_parts(self) -> None:
        """Points overlapping any previously accepted part are trimmed."""
        part_1 = WorkoutRoute(points=[self._make_point(0), self._make_point(1)])
        part_2 = WorkoutRoute(points=[self._make_point(2), self._make_point(3)])
        part_3 = WorkoutRoute(
            points=[self._make_point(3), self._make_point(4), self._make_point(5)]
        )
        result = ExportParser._trim_overlapping_route_part([part_1, part_2], part_3)
        assert result is not None
        assert [p.time for p in result.points] == [
            datetime.fromisoformat("2024-01-01T10:04:00+00:00"),
            datetime.fromisoformat("2024-01-01T10:05:00+00:00"),
        ]


class TestGetOrInitRouteParts:
    """Tests for get_or_init_route_parts."""

    def test_mixed_list_filters_non_route_items(self) -> None:
        """A list containing non-WorkoutRoute items is filtered to only WorkoutRoute instances."""
        from logic.gpx_loader import get_or_init_route_parts
        from logic.models import WorkoutRecord

        valid_part = WorkoutRoute(points=[])
        record: WorkoutRecord = {
            "activityType": "Running",
            "route_parts": [valid_part, "not-a-route", 42],  # type: ignore[list-item]
        }  # type: ignore[typeddict-unknown-key]
        result = get_or_init_route_parts(record)
        assert result == [valid_part]
        assert record["route_parts"] == [valid_part]  # type: ignore[typeddict-item]


class TestSplitsAcrossRouteGap:
    """Splits must not attribute a GPS gap's distance to the following split."""

    def test_splits_have_plausible_speeds_when_route_has_gap(
        self,
        tmp_path: Path,
        load_export_fragment: Callable[[str], str],
        build_health_export_xml: Callable[[list[str]], str],
    ) -> None:
        """Real 2025-04-17 export (issue #367): no split may show an aberrant ~62 km/h pace."""
        workout_fragment = load_export_fragment("workout_running_multiple_routes_too_fast.xml")
        route_dir = Path(__file__).resolve().parents[2] / "fixtures" / "exports" / "workout-routes"

        zip_path = tmp_path / "running_gap.zip"
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

        route = health_data.workouts.iloc[0]["route"]
        scale = WorkoutRoute.calculate_distance_scale_factor(
            route.distance_meters, health_data.workouts.iloc[0]["distance"]
        )
        splits = route.compute_splits(distance_scale_factor=scale)

        assert len(splits) == 7
        for split in splits:
            assert 5.0 < split["pace_min_per_km"] < 7.0
