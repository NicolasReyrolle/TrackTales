"""Tests for the route-comparison tab in the workout detail modal."""

from __future__ import annotations

from contextlib import ExitStack
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import patch

import pytest

import ui.workout_detail_modal.comparisons as wdmc
from logic.workout_manager.workout_route import RoutePoint, WorkoutRoute
from ui import workout_detail_modal as wdm

from ._stubs import _all_patches, _DummyElement, _make_row

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_route(
    points: list[tuple[float, float]],
    base_time: datetime | None = None,
) -> WorkoutRoute:
    """Build a WorkoutRoute from a list of (lat, lon) tuples."""
    if base_time is None:
        base_time = datetime(2024, 1, 1, 10, 0, 0)
    return WorkoutRoute(
        points=[
            RoutePoint(
                time=base_time + timedelta(seconds=i),
                latitude=lat,
                longitude=lon,
                altitude=100.0,
                speed=3.0,
            )
            for i, (lat, lon) in enumerate(points)
        ]
    )


def _make_row_with_route(
    *,
    idx: int = 0,
    date_sort: float = 1_700_000_000.0,
    date: str = "Jan 01, 2024",
    duration_sort: float = 3600.0,
    duration: str = "1h 00min",
    distance_sort: float = 10_000.0,
    distance: str = "10.0 km",
    activity_type: str = "Running",
    route: WorkoutRoute | None = None,
    distance_unit: str = "km",
) -> dict[str, Any]:
    """Build a minimal workout row with an optional GPS route."""
    row = _make_row(
        idx=idx,
        date_sort=date_sort,
        date=date,
        activity_type=activity_type,
    )
    row["duration_sort"] = duration_sort
    row["duration"] = duration
    row["distance_sort"] = distance_sort
    row["distance"] = distance
    row["distance_unit"] = distance_unit
    if route is not None:
        row["route"] = route
    return row


# ---------------------------------------------------------------------------
# _merge_adjacent_route_parts
# ---------------------------------------------------------------------------


class TestMergeAdjacentRouteParts:
    """Tests for wdmc._merge_adjacent_route_parts()."""

    def test_empty_list_returns_empty_route(self) -> None:
        """Empty input should return an empty WorkoutRoute."""
        result = wdmc._merge_adjacent_route_parts([])
        assert result.is_empty

    def test_single_route_returned_unchanged(self) -> None:
        """A single segment should be returned as-is."""
        route = _build_route([(48.85, 2.35), (48.87, 2.37)])
        result = wdmc._merge_adjacent_route_parts([route])
        assert result is route

    def test_adjacent_segments_merged(self) -> None:
        """Two segments that end/start within threshold should be merged."""
        # Segments are ~5 m apart (well within default 50 m threshold).
        part_a = _build_route([(48.8500, 2.3500), (48.8501, 2.3501)])
        part_b = _build_route([(48.8501, 2.3501), (48.8510, 2.3510)])
        result = wdmc._merge_adjacent_route_parts([part_a, part_b])
        assert len(result.points) == len(part_a.points) + len(part_b.points)
        assert result.points[0].latitude == pytest.approx(48.8500)
        assert result.points[-1].latitude == pytest.approx(48.8510)

    def test_non_adjacent_segments_return_first(self) -> None:
        """Segments more than threshold apart should fall back to the first segment."""
        # ~11 km gap between end of part_a and start of part_b (0.1 deg lat ≈ 11 km).
        part_a = _build_route([(48.8500, 2.3500), (48.8510, 2.3510)])
        part_b = _build_route([(48.9510, 2.3510), (48.9600, 2.3600)])
        result = wdmc._merge_adjacent_route_parts([part_a, part_b])
        assert result is part_a

    def test_three_adjacent_segments_all_merged(self) -> None:
        """Three adjacent segments should all be merged into one."""
        part_a = _build_route([(48.8500, 2.3500), (48.8501, 2.3501)])
        part_b = _build_route([(48.8501, 2.3501), (48.8502, 2.3502)])
        part_c = _build_route([(48.8502, 2.3502), (48.8510, 2.3510)])
        result = wdmc._merge_adjacent_route_parts([part_a, part_b, part_c])
        expected_len = len(part_a.points) + len(part_b.points) + len(part_c.points)
        assert len(result.points) == expected_len

    def test_middle_gap_falls_back_to_first(self) -> None:
        """Parts A-B adjacent but B-C not: falls back to first segment only."""
        part_a = _build_route([(48.8500, 2.3500), (48.8501, 2.3501)])
        part_b = _build_route([(48.8501, 2.3501), (48.8502, 2.3502)])
        part_c = _build_route([(48.9502, 2.3502), (48.9600, 2.3600)])  # far gap
        result = wdmc._merge_adjacent_route_parts([part_a, part_b, part_c])
        assert result is part_a

    def test_custom_threshold_respected(self) -> None:
        """A tight custom threshold should reject mildly separated segments."""
        # Place the second segment ~30 m away (approx 0.0003 degrees lat ≈ 33 m).
        part_a = _build_route([(48.8500, 2.3500), (48.8500, 2.3500)])
        part_b = _build_route([(48.8503, 2.3500), (48.8510, 2.3510)])
        # Default 50 m: should merge (gap ≈ 33 m < 50 m).
        merged = wdmc._merge_adjacent_route_parts([part_a, part_b])
        assert len(merged.points) == len(part_a.points) + len(part_b.points)
        # Very tight threshold (5 m): should fall back to first segment.
        fallback = wdmc._merge_adjacent_route_parts([part_a, part_b], adjacency_threshold_m=5.0)
        assert fallback is part_a


# ---------------------------------------------------------------------------
# _route_endpoints
# ---------------------------------------------------------------------------


class TestRouteEndpoints:
    """Tests for wdmc._route_endpoints()."""

    def test_returns_none_when_no_route(self) -> None:
        """Row with no route key should return None."""
        assert wdmc._route_endpoints({}) is None

    def test_returns_none_for_empty_route(self) -> None:
        """Row with empty WorkoutRoute should return None."""
        row = {"route": WorkoutRoute(points=[])}
        assert wdmc._route_endpoints(row) is None

    def test_returns_start_and_end_for_single_route(self) -> None:
        """Simple route should return (start_lat, start_lon, end_lat, end_lon)."""
        route = _build_route([(48.85, 2.35), (48.86, 2.36), (48.87, 2.37)])
        row = {"route": route}
        result = wdmc._route_endpoints(row)
        assert result is not None
        s_lat, s_lon, e_lat, e_lon = result
        assert s_lat == pytest.approx(48.85)
        assert s_lon == pytest.approx(2.35)
        assert e_lat == pytest.approx(48.87)
        assert e_lon == pytest.approx(2.37)

    def test_uses_first_and_last_route_parts(self) -> None:
        """Multi-part route should use first part's start and last part's end."""
        part_a = _build_route([(48.85, 2.35), (48.86, 2.36)])
        part_b = _build_route([(48.90, 2.40), (48.91, 2.41)])
        row = {"route_parts": [part_a, part_b]}
        result = wdmc._route_endpoints(row)
        assert result is not None
        s_lat, s_lon, e_lat, e_lon = result
        assert s_lat == pytest.approx(48.85)
        assert s_lon == pytest.approx(2.35)
        assert e_lat == pytest.approx(48.91)
        assert e_lon == pytest.approx(2.41)


# ---------------------------------------------------------------------------
# find_similar_route_workouts
# ---------------------------------------------------------------------------


class TestFindSimilarRouteWorkouts:
    """Tests for wdmc.find_similar_route_workouts()."""

    def test_returns_empty_when_current_has_no_route(self) -> None:
        """Current row without a route should produce an empty result."""
        current = _make_row_with_route(idx=0)
        other = _make_row_with_route(idx=1, route=_build_route([(48.85, 2.35), (48.87, 2.37)]))
        assert wdmc.find_similar_route_workouts(current, [current, other]) == []

    def test_current_row_is_included_in_results(self) -> None:
        """The current row itself must always appear in the results."""
        route = _build_route([(48.85, 2.35), (48.87, 2.37)])
        current = _make_row_with_route(idx=0, route=route)
        result = wdmc.find_similar_route_workouts(current, [current])
        assert current in result

    def test_identical_route_is_similar(self) -> None:
        """Two rows with identical GPS points are always similar."""
        route_pts = [(48.85, 2.35), (48.86, 2.36), (48.865, 2.365), (48.87, 2.37)]
        route_a = _build_route(route_pts)
        route_b = _build_route(route_pts)
        row_a = _make_row_with_route(idx=0, route=route_a)
        row_b = _make_row_with_route(idx=1, route=route_b)
        result = wdmc.find_similar_route_workouts(row_a, [row_a, row_b])
        assert row_a in result
        assert row_b in result

    def test_different_activity_type_excluded(self) -> None:
        """Rows with a different raw_activity_type must not appear."""
        route = _build_route([(48.85, 2.35), (48.87, 2.37)])
        current = _make_row_with_route(idx=0, activity_type="Running", route=route)
        cycling = _make_row_with_route(
            idx=1,
            activity_type="Cycling",
            route=_build_route([(48.85, 2.35), (48.87, 2.37)]),
        )
        result = wdmc.find_similar_route_workouts(current, [current, cycling])
        assert cycling not in result

    def test_distant_start_point_excluded(self) -> None:
        """Row whose start point is far away must be excluded."""
        route_a = _build_route([(48.85, 2.35), (48.87, 2.37)])
        # Start ~111 km away (lat shifted by 1.0 deg ≈ 111 km at this latitude)
        route_b = _build_route([(49.85, 2.35), (48.87, 2.37)])
        current = _make_row_with_route(idx=0, route=route_a)
        far = _make_row_with_route(idx=1, route=route_b)
        result = wdmc.find_similar_route_workouts(current, [current, far])
        assert far not in result

    def test_very_different_distance_excluded(self) -> None:
        """Row whose distance deviates by more than 5 % must be excluded."""
        route_a = _build_route([(48.85, 2.35), (48.87, 2.37)])
        route_b = _build_route([(48.85, 2.35), (48.87, 2.37)])
        current = _make_row_with_route(idx=0, route=route_a, distance_sort=10_000.0)
        different_dist = _make_row_with_route(idx=1, route=route_b, distance_sort=20_000.0)
        result = wdmc.find_similar_route_workouts(current, [current, different_dist])
        assert different_dist not in result

    def test_sorted_by_duration_ascending(self) -> None:
        """Returned rows must be sorted fastest (lowest duration_sort) first."""
        route_pts = [(48.85, 2.35), (48.87, 2.37)]
        row_slow = _make_row_with_route(idx=0, route=_build_route(route_pts), duration_sort=7200.0)
        row_fast = _make_row_with_route(idx=1, route=_build_route(route_pts), duration_sort=3000.0)
        row_mid = _make_row_with_route(idx=2, route=_build_route(route_pts), duration_sort=4500.0)
        result = wdmc.find_similar_route_workouts(row_slow, [row_slow, row_fast, row_mid])
        durations = [float(r.get("duration_sort") or 0.0) for r in result]
        assert durations == sorted(durations)

    def test_sentinel_duration_sort_not_ranked_fastest(self) -> None:
        """Rows with a non-positive duration_sort (e.g. -1.0 sentinel from
        _build_field_pair) must not be ranked ahead of real durations.

        Regression: the old ``r.get("duration_sort") or float("inf")`` sort
        key treated ``-1.0`` as truthy, so -1.0 < real_duration and would be
        ranked as fastest.  The fixed key treats any ``<= 0`` value as ``inf``
        so these rows sort to the end of the list.
        """
        route_pts = [(48.85, 2.35), (48.87, 2.37)]
        row_valid = _make_row_with_route(idx=0, route=_build_route(route_pts), duration_sort=3600.0)
        row_sentinel = _make_row_with_route(
            idx=1, route=_build_route(route_pts), duration_sort=-1.0
        )
        result = wdmc.find_similar_route_workouts(row_valid, [row_valid, row_sentinel])
        assert len(result) == 2
        # The row with a valid duration should come first.
        assert result[0] is row_valid
        assert result[-1] is row_sentinel

    def test_no_distance_sort_excluded(self) -> None:
        """Row without a valid distance_sort must be excluded."""
        route = _build_route([(48.85, 2.35), (48.87, 2.37)])
        current = _make_row_with_route(idx=0, route=route, distance_sort=10_000.0)
        no_dist = _make_row_with_route(idx=1, route=route)
        no_dist["distance_sort"] = None  # Remove the valid distance
        result = wdmc.find_similar_route_workouts(current, [current, no_dist])
        assert no_dist not in result

    def test_current_row_without_distance_returns_empty(self) -> None:
        """Current row without valid distance_sort should return empty."""
        route = _build_route([(48.85, 2.35), (48.87, 2.37)])
        current = _make_row_with_route(idx=0, route=route)
        current["distance_sort"] = 0.0
        result = wdmc.find_similar_route_workouts(current, [current])
        assert result == []

    def test_diverging_midpoint_excluded(self) -> None:
        """Route diverging at intermediate waypoints must be excluded."""
        # current: straight north along lon 2.35
        current_pts = [
            (48.850, 2.350),
            (48.855, 2.350),
            (48.860, 2.350),
            (48.865, 2.350),
            (48.870, 2.350),
        ]
        # candidate: same start/end but diverges midway by ~1 km east at lon 2.360
        candidate_pts = [
            (48.850, 2.350),
            (48.855, 2.360),
            (48.860, 2.360),
            (48.865, 2.360),
            (48.870, 2.350),
        ]
        current = _make_row_with_route(idx=0, route=_build_route(current_pts))
        diverged = _make_row_with_route(idx=1, route=_build_route(candidate_pts))
        result = wdmc.find_similar_route_workouts(current, [current, diverged])
        assert diverged not in result

    def test_matching_intermediate_waypoints_included(self) -> None:
        """Route with all waypoints close to current should be included."""
        pts = [
            (48.850, 2.350),
            (48.855, 2.350),
            (48.860, 2.350),
            (48.865, 2.350),
            (48.870, 2.350),
        ]
        current = _make_row_with_route(idx=0, route=_build_route(pts))
        similar_row = _make_row_with_route(idx=1, route=_build_route(pts))
        result = wdmc.find_similar_route_workouts(current, [current, similar_row])
        assert similar_row in result

    def test_reverse_direction_same_loop_included(self) -> None:
        """Two runs of the same loop in opposite directions must match.

        Real-world regression: two ~7.4 km GPS routes near Luxembourg
        (2026-02-12 and 2025-10-20) that share the same start/end area
        but are traversed in opposite directions.  Their 25%/75% waypoints
        are swapped relative to each other, which caused the forward-only
        shape check to reject them.  The fix retries with reversed fractions.

        Coordinates extracted from the actual user-provided GPX files.
        """
        # Route A (forward direction – 2026-02-12):
        #   start=(49.744235,6.097835), 25%=(49.73725,6.11424),
        #   50%=(49.72406,6.11945), 75%=(49.73491,6.10534), end=(49.744179,6.097686)
        route_a_pts = [
            (49.744235, 6.097835),  # start
            (49.73725, 6.11424),  # ~25 % of total distance
            (49.72406, 6.11945),  # ~50 %
            (49.73491, 6.10534),  # ~75 %
            (49.744179, 6.097686),  # end
        ]
        # Route B (reverse direction – 2025-10-20):
        #   start=(49.744498,6.097646), 25%=(49.73721,6.11422) ≈ A's 75%,
        #   50%=(49.72418,6.11916) ≈ A's 50%, 75%=(49.73511,6.10572) ≈ A's 25%,
        #   end=(49.744247,6.097666)
        route_b_pts = [
            (49.744498, 6.097646),  # start (32 m from A's start ✓)
            (49.73721, 6.11422),  # ~25 % of B ≈ 75 % of A
            (49.72418, 6.11916),  # ~50 %
            (49.73511, 6.10572),  # ~75 % of B ≈ 25 % of A
            (49.744247, 6.097666),  # end (8 m from A's end ✓)
        ]
        row_a = _make_row_with_route(idx=0, route=_build_route(route_a_pts), distance_sort=7381.0)
        row_b = _make_row_with_route(idx=1, route=_build_route(route_b_pts), distance_sort=7407.0)
        result = wdmc.find_similar_route_workouts(row_a, [row_a, row_b])
        assert row_b in result, "Opposite-direction run of same loop should be matched"


# ---------------------------------------------------------------------------
# _pace_from_row
# ---------------------------------------------------------------------------


class TestPaceFromRow:
    """Tests for wdmc._pace_from_row()."""

    def test_returns_dash_for_zero_distance(self) -> None:
        """Row with zero distance_sort should return '–'."""
        row = {"duration_sort": 3600.0, "distance_sort": 0.0}
        assert wdmc._pace_from_row(row, "km") == "–"

    def test_returns_dash_for_zero_duration(self) -> None:
        """Row with zero duration_sort should return '–'."""
        row = {"duration_sort": 0.0, "distance_sort": 10_000.0}
        assert wdmc._pace_from_row(row, "km") == "–"

    def test_returns_dash_for_missing_values(self) -> None:
        """Row without duration_sort or distance_sort should return '–'."""
        assert wdmc._pace_from_row({}, "km") == "–"

    def test_formats_pace_km(self) -> None:
        """3600 s over 10 km = 6:00 min/km."""
        row = {"duration_sort": 3600.0, "distance_sort": 10_000.0}
        result = wdmc._pace_from_row(row, "km")
        assert result == "6:00 min/km"

    def test_formats_pace_mi(self) -> None:
        """Pace should scale for miles."""
        row = {"duration_sort": 3600.0, "distance_sort": 10_000.0}
        result = wdmc._pace_from_row(row, "mi")
        assert "min/mi" in result


# ---------------------------------------------------------------------------
# _format_duration_diff
# ---------------------------------------------------------------------------


class TestFormatDurationDiff:
    """Tests for wdmc._format_duration_diff()."""

    def test_best_returns_dash(self) -> None:
        """Rank-1 entry (diff = 0) should return '–'."""
        assert wdmc._format_duration_diff(3600.0, 3600.0) == "–"

    def test_faster_than_best_returns_dash(self) -> None:
        """Entry faster than best (negative diff) should return '–'."""
        assert wdmc._format_duration_diff(3590.0, 3600.0) == "–"

    def test_formats_90_second_diff(self) -> None:
        """90 s difference should format as '+1:30'."""
        assert wdmc._format_duration_diff(3690.0, 3600.0) == "+1:30"

    def test_formats_3601_second_diff(self) -> None:
        """3661 s difference should format as '+61:01'."""
        assert wdmc._format_duration_diff(3600.0 + 3661, 3600.0) == "+61:01"

    def test_single_second_diff(self) -> None:
        """1 s difference should format as '+0:01'."""
        assert wdmc._format_duration_diff(3601.0, 3600.0) == "+0:01"

    def test_exactly_one_minute_diff(self) -> None:
        """60 s difference should format as '+1:00'."""
        assert wdmc._format_duration_diff(3660.0, 3600.0) == "+1:00"


# ---------------------------------------------------------------------------
# _build_comparison_display_rows
# ---------------------------------------------------------------------------


class TestBuildComparisonDisplayRows:
    """Tests for wdmc._build_comparison_display_rows()."""

    def _make_similar(self, n: int, base_duration: float = 3600.0) -> list[dict[str, Any]]:
        """Build *n* synthetic similar-route rows ordered by duration."""
        return [
            {
                "id": f"row_{i}",
                "date": f"Jan {i + 1:02d}, 2024",
                "duration": f"{int(base_duration * (i + 1) / n)}s",
                "duration_sort": base_duration * (i + 1) / n,
                "distance_sort": 10_000.0,
            }
            for i in range(n)
        ]

    def test_top_10_rows_included(self) -> None:
        """Top 10 + slowest shown when current (rank 1) is within top 10."""
        similar = self._make_similar(15)
        rows, _ = wdmc._build_comparison_display_rows(similar, "row_0", "km")
        # current is rank 1 (in top 10), slowest (row_14) is not → appended
        assert len(rows) == 11
        assert rows[-1]["rank"] == 15

    def test_rank_1_has_dash_diff(self) -> None:
        """Rank-1 row (fastest) should have '–' as diff_str."""
        similar = self._make_similar(3)
        rows, _ = wdmc._build_comparison_display_rows(similar, "row_0", "km")
        assert rows[0]["diff_str"] == "–"

    def test_rank_2_has_positive_diff(self) -> None:
        """Rank-2 row should have a '+mm:ss' diff_str relative to rank 1."""
        similar = [
            {
                "id": "a",
                "date": "Jan 01, 2024",
                "duration": "1h",
                "duration_sort": 3600.0,
                "distance_sort": 10_000.0,
            },
            {
                "id": "b",
                "date": "Jan 02, 2024",
                "duration": "1h 2min",
                "duration_sort": 3720.0,
                "distance_sort": 10_000.0,
            },
        ]
        rows, _ = wdmc._build_comparison_display_rows(similar, "a", "km")
        # 3720 - 3600 = 120 s = 2 min → "+2:00"
        assert rows[1]["diff_str"] == "+2:00"

    def test_current_outside_top_10_appended(self) -> None:
        """Current (rank 12) appended after top 10; slowest (rank 15) appended last."""
        similar = self._make_similar(15)
        # current is row_11 (0-indexed), rank 12
        rows, rank = wdmc._build_comparison_display_rows(similar, "row_11", "km")
        assert rank == 12
        assert len(rows) == 12  # top 10 + current + slowest
        current_row = next(r for r in rows if "→" in r["rank_str"])
        assert current_row["rank_str"] == "→ 12"
        assert rows[-1]["rank"] == 15  # slowest appended at end

    def test_current_inside_top_10_highlighted(self) -> None:
        """Current workout ranked 3rd should have '→ 3' in rank_str."""
        similar = self._make_similar(10)
        rows, rank = wdmc._build_comparison_display_rows(similar, "row_2", "km")
        assert rank == 3
        current_row = next(r for r in rows if "→" in r["rank_str"])
        assert current_row["rank_str"] == "→ 3"

    def test_ranks_are_unique_integers(self) -> None:
        """rank field in each display row should be a unique integer."""
        similar = self._make_similar(12)
        rows, _ = wdmc._build_comparison_display_rows(similar, "row_11", "km")
        rank_values = [r["rank"] for r in rows]
        assert len(rank_values) == len(set(rank_values))

    def test_unknown_current_id_returns_none_rank(self) -> None:
        """Unknown current_row_id should result in current_rank=None."""
        similar = self._make_similar(5)
        _, rank = wdmc._build_comparison_display_rows(similar, "unknown", "km")
        assert rank is None

    def test_empty_similar_returns_empty_rows(self) -> None:
        """Empty similar list should return empty display rows and None rank."""
        rows, rank = wdmc._build_comparison_display_rows([], "row_0", "km")
        assert rows == []
        assert rank is None

    def test_custom_top_n(self) -> None:
        """top_n=3 with 10 entries: 3 top rows + slowest appended."""
        similar = self._make_similar(10)
        rows, _ = wdmc._build_comparison_display_rows(similar, "row_0", "km", top_n=3)
        # row_0 is rank 1 (inside top 3), slowest (row_9) not shown → appended
        assert len(rows) == 4
        assert rows[-1]["rank"] == 10

    def test_slowest_already_in_top_n_not_duplicated(self) -> None:
        """When all entries fit within top_n the slowest is already shown; no duplicate."""
        similar = self._make_similar(5)
        rows, _ = wdmc._build_comparison_display_rows(similar, "row_0", "km", top_n=10)
        # All 5 rows fit in top_n; no extra row appended
        assert len(rows) == 5
        assert [r["rank"] for r in rows] == [1, 2, 3, 4, 5]

    def test_slowest_equals_current_outside_top_n_not_duplicated(self) -> None:
        """Current == slowest outside top_n should appear once only (highlighted)."""
        similar = self._make_similar(12)
        # row_11 is both the current and the slowest (rank 12)
        rows, rank = wdmc._build_comparison_display_rows(similar, "row_11", "km")
        assert rank == 12
        # top 10 + current (= slowest) once, no extra slowest row
        assert len(rows) == 11
        last = rows[-1]
        assert last["rank_str"] == "→ 12"

    def test_slowest_appended_when_current_in_top_n(self) -> None:
        """When current is inside top_n, slowest is appended as the final row."""
        similar = self._make_similar(15)
        # current = row_4 (rank 5, inside top 10); slowest = row_14 (rank 15)
        rows, rank = wdmc._build_comparison_display_rows(similar, "row_4", "km")
        assert rank == 5
        assert rows[-1]["rank"] == 15  # slowest at end

    def test_slowest_not_marked_as_current(self) -> None:
        """Slowest row appended when it differs from current must not use '→' prefix."""
        similar = self._make_similar(15)
        rows, _ = wdmc._build_comparison_display_rows(similar, "row_0", "km")
        slowest_row = rows[-1]
        assert "→" not in slowest_row["rank_str"]


# ---------------------------------------------------------------------------
# _do_refresh_comparisons_tab
# ---------------------------------------------------------------------------


class TestDoRefreshComparisonsTab:
    """Tests for wdmc._do_refresh_comparisons_tab()."""

    def _dummy_widgets(self) -> tuple[_DummyElement, _DummyElement, _DummyElement, _DummyElement]:
        return _DummyElement(), _DummyElement(), _DummyElement(), _DummyElement()

    def test_no_route_shows_no_route_label(self) -> None:
        """Workout without GPS route should show the no-route placeholder."""
        no_route, no_similar, rank_lbl, table = self._dummy_widgets()
        row: dict[str, Any] = {}
        wdmc._do_refresh_comparisons_tab(no_route, no_similar, rank_lbl, table, row, [row])
        assert no_route._visible
        assert not no_similar._visible
        assert not rank_lbl._visible
        assert not table._visible

    def test_no_similar_routes_shows_no_similar_label(self) -> None:
        """Route exists but no other similar workouts → show no-similar placeholder."""
        no_route, no_similar, rank_lbl, table = self._dummy_widgets()
        route = _build_route([(48.85, 2.35), (48.87, 2.37)])
        row = _make_row_with_route(idx=0, route=route)
        # Pass only current row; result will be [current] → len < 2
        wdmc._do_refresh_comparisons_tab(no_route, no_similar, rank_lbl, table, row, [row])
        assert not no_route._visible
        assert no_similar._visible
        assert not rank_lbl._visible
        assert not table._visible

    def test_similar_routes_shows_table_and_rank(self) -> None:
        """When similar workouts exist, table and rank label should be visible."""
        no_route, no_similar, rank_lbl, table = self._dummy_widgets()
        route_pts = [(48.85, 2.35), (48.87, 2.37)]
        row_a = _make_row_with_route(
            idx=0,
            route=_build_route(route_pts),
            duration_sort=3600.0,
        )
        row_b = _make_row_with_route(
            idx=1,
            route=_build_route(route_pts),
            duration_sort=4000.0,
        )
        wdmc._do_refresh_comparisons_tab(
            no_route, no_similar, rank_lbl, table, row_a, [row_a, row_b]
        )
        assert not no_route._visible
        assert not no_similar._visible
        assert rank_lbl._visible
        assert table._visible
        assert len(table.rows) == 2

    def test_similar_routes_cached_in_row(self) -> None:
        """Second call should reuse cached similar_routes from the row dict."""
        no_route, no_similar, rank_lbl, table = self._dummy_widgets()
        route_pts = [(48.85, 2.35), (48.87, 2.37)]
        row_a = _make_row_with_route(idx=0, route=_build_route(route_pts))
        row_b = _make_row_with_route(idx=1, route=_build_route(route_pts))
        all_rows = [row_a, row_b]

        with patch.object(
            wdmc, "find_similar_route_workouts", wraps=wdmc.find_similar_route_workouts
        ) as mock_find:
            wdmc._do_refresh_comparisons_tab(no_route, no_similar, rank_lbl, table, row_a, all_rows)
            wdmc._do_refresh_comparisons_tab(no_route, no_similar, rank_lbl, table, row_a, all_rows)

        # Should only be called once due to caching in row["similar_routes"]
        assert mock_find.call_count == 1

    def test_rank_label_contains_rank_and_total(self) -> None:
        """Rank label should mention both the rank and total count."""
        no_route, no_similar, rank_lbl, table = self._dummy_widgets()
        route_pts = [(48.85, 2.35), (48.87, 2.37)]
        row_a = _make_row_with_route(idx=0, route=_build_route(route_pts), duration_sort=3000.0)
        row_b = _make_row_with_route(idx=1, route=_build_route(route_pts), duration_sort=4000.0)
        wdmc._do_refresh_comparisons_tab(
            no_route, no_similar, rank_lbl, table, row_a, [row_a, row_b]
        )
        # row_a is fastest so rank=1, total=2; label uses "Rank: {rank} of {total}"
        assert "1" in rank_lbl._text
        assert "2" in rank_lbl._text


# ---------------------------------------------------------------------------
# Modal integration: Comparisons tab creation and tab-change handling
# ---------------------------------------------------------------------------


class TestComparisonsTabIntegration:
    """Integration tests for the Comparisons tab in create_workout_detail_modal."""

    def test_comparisons_tab_created(self) -> None:
        """create_workout_detail_modal should create a 'comparisons' ui.tab."""
        rows = [_make_row(idx=0)]
        tab_names: list[str] = []

        def capture_tab(*args: Any, **_kw: Any) -> _DummyElement:
            if args:
                tab_names.append(str(args[0]))
            return _DummyElement()

        with ExitStack() as stack:
            for p in _all_patches(tab_side_effect=capture_tab):
                stack.enter_context(p)
            wdm.create_workout_detail_modal(rows)

        assert "comparisons" in tab_names

    def test_comparisons_tab_disabled_without_route(self) -> None:
        """comparisons_tab should be disabled when the workout has no GPS route."""
        rows = [_make_row(idx=0)]
        tab_stubs: list[_DummyElement] = []

        def capture_tab(*_a: Any, **_kw: Any) -> _DummyElement:
            stub = _DummyElement()
            tab_stubs.append(stub)
            return stub

        with ExitStack() as stack:
            for p in _all_patches(tab_side_effect=capture_tab):
                stack.enter_context(p)
            fn = wdm.create_workout_detail_modal(rows)

        fn(0)
        # Tab order: overview[0], activity[1], route[2], intervals[3], comparisons[4]
        comparisons_tab = tab_stubs[4]
        assert not comparisons_tab._enabled

    def test_comparisons_tab_enabled_with_route(self) -> None:
        """comparisons_tab should be enabled when the workout has a GPS route."""
        route = _build_route([(48.85, 2.35), (48.87, 2.37)])
        rows = [{**_make_row(idx=0), "route": route}]
        tab_stubs: list[_DummyElement] = []

        def capture_tab(*_a: Any, **_kw: Any) -> _DummyElement:
            stub = _DummyElement()
            tab_stubs.append(stub)
            return stub

        with ExitStack() as stack:
            for p in _all_patches(tab_side_effect=capture_tab):
                stack.enter_context(p)
            fn = wdm.create_workout_detail_modal(rows)

        fn(0)
        comparisons_tab = tab_stubs[4]
        assert comparisons_tab._enabled

    def test_tab_change_to_comparisons_triggers_refresh(self) -> None:
        """Switching to the Comparisons tab should trigger a comparisons refresh."""
        route = _build_route([(48.85, 2.35), (48.87, 2.37)])
        rows = [{**_make_row(idx=0), "route": route}]
        tabs_stub = _DummyElement()
        refresh_calls: list[dict[str, Any]] = []

        def capture_refresh(
            _no_route: Any,
            _no_similar: Any,
            _rank_lbl: Any,
            _table: Any,
            row: dict[str, Any],
            _all_rows: Any,
        ) -> None:
            refresh_calls.append(row)

        with ExitStack() as stack:
            for p in _all_patches(tabs_stub=tabs_stub):
                stack.enter_context(p)
            stack.enter_context(
                patch(
                    "ui.workout_detail_modal._do_refresh_comparisons_tab",
                    side_effect=capture_refresh,
                )
            )
            fn = wdm.create_workout_detail_modal(rows)
            fn(0)
            assert not refresh_calls
            tabs_stub.fire_value_change("comparisons")
            assert len(refresh_calls) == 1


# ---------------------------------------------------------------------------
# _row_has_route
# ---------------------------------------------------------------------------


class TestRowHasRoute:
    """Tests for wdmc._row_has_route()."""

    def test_returns_false_for_empty_dict(self) -> None:
        """Row with no 'route' key should return False."""
        assert wdmc._row_has_route({}) is False

    def test_returns_false_for_non_workout_route_value(self) -> None:
        """Row with a non-WorkoutRoute value under 'route' should return False."""
        assert wdmc._row_has_route({"route": "not-a-route"}) is False
        assert wdmc._row_has_route({"route": 42}) is False

    def test_returns_false_for_empty_workout_route(self) -> None:
        """Row with an empty WorkoutRoute should return False."""
        assert wdmc._row_has_route({"route": WorkoutRoute(points=[])}) is False

    def test_returns_true_for_non_empty_workout_route(self) -> None:
        """Row with a non-empty WorkoutRoute should return True."""
        route = _build_route([(48.85, 2.35), (48.87, 2.37)])
        assert wdmc._row_has_route({"route": route}) is True


# ---------------------------------------------------------------------------
# _merge_adjacent_route_parts – empty segment skip
# ---------------------------------------------------------------------------


class TestMergeAdjacentRoutePartsEmptySegment:
    """Additional tests covering the empty-segment filtering behaviour."""

    def test_empty_segment_between_adjacent_parts_is_ignored(self) -> None:
        """An empty segment sandwiched between two adjacent real segments is
        filtered out; the two non-empty segments are still merged."""
        part_a = _build_route([(48.8500, 2.3500), (48.8501, 2.3501)])
        part_empty = WorkoutRoute(points=[])
        part_b = _build_route([(48.8501, 2.3501), (48.8510, 2.3510)])
        result = wdmc._merge_adjacent_route_parts([part_a, part_empty, part_b])
        assert len(result.points) == len(part_a.points) + len(part_b.points)

    def test_empty_segment_between_far_parts_falls_back(self) -> None:
        """An empty segment between two non-adjacent real segments must not
        cause a false merge.  The fix filters out empties first so the ~11 km
        gap between part_a and part_b is correctly detected and falls back to
        the first non-empty segment."""
        part_a = _build_route([(48.8500, 2.3500), (48.8510, 2.3510)])
        part_empty = WorkoutRoute(points=[])
        part_b = _build_route([(48.9510, 2.3510), (48.9600, 2.3600)])  # ~11 km away
        result = wdmc._merge_adjacent_route_parts([part_a, part_empty, part_b])
        # Should fall back to just part_a, not merge part_b in.
        assert result is part_a

    def test_all_empty_returns_empty_route(self) -> None:
        """Input consisting solely of empty segments returns an empty route."""
        result = wdmc._merge_adjacent_route_parts(
            [WorkoutRoute(points=[]), WorkoutRoute(points=[])]
        )
        assert result.is_empty

    def test_single_empty_returns_empty_route(self) -> None:
        """Single empty segment should return an empty WorkoutRoute."""
        result = wdmc._merge_adjacent_route_parts([WorkoutRoute(points=[])])
        assert result.is_empty


# ---------------------------------------------------------------------------
# _routes_shape_match – short routes where sample_point_at_fraction → None
# ---------------------------------------------------------------------------


class TestRoutesShapeMatchShortRoutes:
    """Tests covering the None-sample skip branch inside _routes_shape_match."""

    def test_single_point_routes_treated_as_matching(self) -> None:
        """Routes with only one point return None from sample_point_at_fraction.

        All fraction checks are skipped (continue), so the forward _check
        loop completes without returning False → returns True.
        """
        route_a = _build_route([(48.85, 2.35)])
        route_b = _build_route([(48.85, 2.35)])
        assert wdmc._routes_shape_match(route_a, route_b) is True

    def test_identical_two_point_routes_match(self) -> None:
        """Two-point routes with non-zero distance do produce sample points
        and match when they are identical."""
        pts = [(48.85, 2.35), (48.87, 2.37)]
        route_a = _build_route(pts)
        route_b = _build_route(pts)
        assert wdmc._routes_shape_match(route_a, route_b) is True


# ---------------------------------------------------------------------------
# _is_candidate_similar / find_similar_route_workouts – extra exclusion paths
# ---------------------------------------------------------------------------


class TestIsCandidateSimilarExtraPaths:
    """Extra tests that exercise uncovered branches of _is_candidate_similar."""

    def test_candidate_without_route_excluded(self) -> None:
        """Candidate with matching activity type but no GPS route is excluded.

        This exercises the ``endpoints is None`` branch (line 278).
        """
        route = _build_route([(48.85, 2.35), (48.87, 2.37)])
        current = _make_row_with_route(idx=0, route=route, distance_sort=2000.0)
        # Candidate has correct type and distance but no route at all.
        no_route_candidate = {
            "id": "no_route",
            "raw_activity_type": "Running",
            "distance_sort": 2000.0,
        }
        result = wdmc.find_similar_route_workouts(current, [current, no_route_candidate])
        assert no_route_candidate not in result

    def test_candidate_with_far_end_excluded(self) -> None:
        """Candidate whose end is far from the current end is excluded.

        Both start points are very close; the end of the candidate is moved
        ~111 km north so only the end-proximity check can reject it,
        exercising the ``return False`` branch for the end haversine check.
        """
        start = (48.85, 2.35)
        close_end = (48.87, 2.37)
        far_end = (49.87, 2.37)  # ~111 km north

        route_current = _build_route([start, close_end])
        # Same start, but end is very far.
        route_far_end = _build_route([start, far_end])

        current = _make_row_with_route(idx=0, route=route_current, distance_sort=2500.0)
        far = _make_row_with_route(
            idx=1,
            route=route_far_end,
            # distance_sort close enough to pass the ±5 % tolerance
            distance_sort=2550.0,
        )
        result = wdmc.find_similar_route_workouts(current, [current, far])
        assert far not in result


# ---------------------------------------------------------------------------
# _make_leaderboard_row – direct unit tests
# ---------------------------------------------------------------------------


class TestMakeLeaderboardRow:
    """Direct tests for the module-level _make_leaderboard_row helper."""

    def _row(self, duration_sort: float = 3600.0, date: str = "Jan 01, 2024") -> dict[str, Any]:
        return {
            "id": "r1",
            "date": date,
            "duration": "1h 00min",
            "duration_sort": duration_sort,
            "distance_sort": 10_000.0,
        }

    def test_non_current_has_plain_rank_str(self) -> None:
        """Non-current entry should have plain rank number in rank_str."""
        row = wdmc._make_leaderboard_row(3, self._row(), False, 3600.0, "km")
        assert row["rank"] == 3
        assert row["rank_str"] == "3"
        assert "→" not in row["rank_str"]

    def test_current_has_arrow_prefix(self) -> None:
        """Current entry should have '→ {rank}' in rank_str."""
        row = wdmc._make_leaderboard_row(1, self._row(), True, 3600.0, "km")
        assert row["rank_str"] == "→ 1"

    def test_diff_str_for_fastest(self) -> None:
        """Rank-1 entry (same duration as best) should have '–' as diff_str."""
        row = wdmc._make_leaderboard_row(1, self._row(3600.0), False, 3600.0, "km")
        assert row["diff_str"] == "–"

    def test_diff_str_for_slower_entry(self) -> None:
        """Entry 90 s slower than best should have '+1:30' as diff_str."""
        row = wdmc._make_leaderboard_row(2, self._row(3690.0), False, 3600.0, "km")
        assert row["diff_str"] == "+1:30"

    def test_date_and_duration_copied(self) -> None:
        """date and duration should be copied from the source row."""
        row = wdmc._make_leaderboard_row(1, self._row(date="Feb 14, 2024"), False, 3600.0, "km")
        assert row["date"] == "Feb 14, 2024"
        assert row["duration"] == "1h 00min"

    def test_missing_duration_sort_treated_as_zero(self) -> None:
        """Row without duration_sort should be treated as 0 seconds (diff_str '–')."""
        r: dict[str, Any] = {"id": "x", "date": "–", "duration": "–", "distance_sort": 1.0}
        result = wdmc._make_leaderboard_row(1, r, False, 0.0, "km")
        assert result["diff_str"] == "–"
