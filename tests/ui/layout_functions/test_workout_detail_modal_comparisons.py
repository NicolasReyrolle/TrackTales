"""Tests for the route-comparison tab in the workout detail modal."""

from __future__ import annotations

from contextlib import ExitStack
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import patch

import pytest

from logic.workout_manager.workout_route import RoutePoint, WorkoutRoute
from ui import workout_detail_modal as wdm

from ._modal_stubs import _all_patches, _DummyElement, _make_row

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
# _route_endpoints
# ---------------------------------------------------------------------------


class TestRouteEndpoints:
    """Tests for wdm._route_endpoints()."""

    def test_returns_none_when_no_route(self) -> None:
        """Row with no route key should return None."""
        assert wdm._route_endpoints({}) is None

    def test_returns_none_for_empty_route(self) -> None:
        """Row with empty WorkoutRoute should return None."""
        row = {"route": WorkoutRoute(points=[])}
        assert wdm._route_endpoints(row) is None

    def test_returns_start_and_end_for_single_route(self) -> None:
        """Simple route should return (start_lat, start_lon, end_lat, end_lon)."""
        route = _build_route([(48.85, 2.35), (48.86, 2.36), (48.87, 2.37)])
        row = {"route": route}
        result = wdm._route_endpoints(row)
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
        result = wdm._route_endpoints(row)
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
    """Tests for wdm.find_similar_route_workouts()."""

    def test_returns_empty_when_current_has_no_route(self) -> None:
        """Current row without a route should produce an empty result."""
        current = _make_row_with_route(idx=0)
        other = _make_row_with_route(idx=1, route=_build_route([(48.85, 2.35), (48.87, 2.37)]))
        assert wdm.find_similar_route_workouts(current, [current, other]) == []

    def test_current_row_is_included_in_results(self) -> None:
        """The current row itself must always appear in the results."""
        route = _build_route([(48.85, 2.35), (48.87, 2.37)])
        current = _make_row_with_route(idx=0, route=route)
        result = wdm.find_similar_route_workouts(current, [current])
        assert current in result

    def test_identical_route_is_similar(self) -> None:
        """Two rows with identical start/end points and distance are similar."""
        route_a = _build_route([(48.85, 2.35), (48.86, 2.36), (48.87, 2.37)])
        route_b = _build_route([(48.85, 2.35), (48.87, 2.37)])
        row_a = _make_row_with_route(idx=0, route=route_a)
        row_b = _make_row_with_route(idx=1, route=route_b)
        result = wdm.find_similar_route_workouts(row_a, [row_a, row_b])
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
        result = wdm.find_similar_route_workouts(current, [current, cycling])
        assert cycling not in result

    def test_distant_start_point_excluded(self) -> None:
        """Row whose start point is far away must be excluded."""
        route_a = _build_route([(48.85, 2.35), (48.87, 2.37)])
        # Start ~10 km away (lat shifted by ~0.09 deg ≈ 10 km)
        route_b = _build_route([(49.85, 2.35), (48.87, 2.37)])
        current = _make_row_with_route(idx=0, route=route_a)
        far = _make_row_with_route(idx=1, route=route_b)
        result = wdm.find_similar_route_workouts(current, [current, far])
        assert far not in result

    def test_very_different_distance_excluded(self) -> None:
        """Row whose distance deviates by more than 20 % must be excluded."""
        route_a = _build_route([(48.85, 2.35), (48.87, 2.37)])
        route_b = _build_route([(48.85, 2.35), (48.87, 2.37)])
        current = _make_row_with_route(idx=0, route=route_a, distance_sort=10_000.0)
        different_dist = _make_row_with_route(idx=1, route=route_b, distance_sort=20_000.0)
        result = wdm.find_similar_route_workouts(current, [current, different_dist])
        assert different_dist not in result

    def test_sorted_by_duration_ascending(self) -> None:
        """Returned rows must be sorted fastest (lowest duration_sort) first."""
        route_pts = [(48.85, 2.35), (48.87, 2.37)]
        row_slow = _make_row_with_route(idx=0, route=_build_route(route_pts), duration_sort=7200.0)
        row_fast = _make_row_with_route(idx=1, route=_build_route(route_pts), duration_sort=3000.0)
        row_mid = _make_row_with_route(idx=2, route=_build_route(route_pts), duration_sort=4500.0)
        result = wdm.find_similar_route_workouts(row_slow, [row_slow, row_fast, row_mid])
        durations = [float(r.get("duration_sort") or 0.0) for r in result]
        assert durations == sorted(durations)

    def test_no_distance_sort_excluded(self) -> None:
        """Row without a valid distance_sort must be excluded."""
        route = _build_route([(48.85, 2.35), (48.87, 2.37)])
        current = _make_row_with_route(idx=0, route=route, distance_sort=10_000.0)
        no_dist = _make_row_with_route(idx=1, route=route)
        no_dist["distance_sort"] = None  # Remove the valid distance
        result = wdm.find_similar_route_workouts(current, [current, no_dist])
        assert no_dist not in result

    def test_current_row_without_distance_returns_empty(self) -> None:
        """Current row without valid distance_sort should return empty."""
        route = _build_route([(48.85, 2.35), (48.87, 2.37)])
        current = _make_row_with_route(idx=0, route=route)
        current["distance_sort"] = 0.0
        result = wdm.find_similar_route_workouts(current, [current])
        assert result == []


# ---------------------------------------------------------------------------
# _pace_from_row
# ---------------------------------------------------------------------------


class TestPaceFromRow:
    """Tests for wdm._pace_from_row()."""

    def test_returns_dash_for_zero_distance(self) -> None:
        """Row with zero distance_sort should return '–'."""
        row = {"duration_sort": 3600.0, "distance_sort": 0.0}
        assert wdm._pace_from_row(row, "km") == "–"

    def test_returns_dash_for_zero_duration(self) -> None:
        """Row with zero duration_sort should return '–'."""
        row = {"duration_sort": 0.0, "distance_sort": 10_000.0}
        assert wdm._pace_from_row(row, "km") == "–"

    def test_returns_dash_for_missing_values(self) -> None:
        """Row without duration_sort or distance_sort should return '–'."""
        assert wdm._pace_from_row({}, "km") == "–"

    def test_formats_pace_km(self) -> None:
        """3600 s over 10 km = 6:00 min/km."""
        row = {"duration_sort": 3600.0, "distance_sort": 10_000.0}
        result = wdm._pace_from_row(row, "km")
        assert result == "6:00 min/km"

    def test_formats_pace_mi(self) -> None:
        """Pace should scale for miles."""
        row = {"duration_sort": 3600.0, "distance_sort": 10_000.0}
        result = wdm._pace_from_row(row, "mi")
        assert "min/mi" in result


# ---------------------------------------------------------------------------
# _build_comparison_display_rows
# ---------------------------------------------------------------------------


class TestBuildComparisonDisplayRows:
    """Tests for wdm._build_comparison_display_rows()."""

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
        """Exactly 10 rows should appear when similar has 15 entries."""
        similar = self._make_similar(15)
        rows, _ = wdm._build_comparison_display_rows(similar, "row_0", "km")
        # Top 10 plus 1 overflow for current (rank 1) → but current IS in top 10
        assert len(rows) == 10

    def test_current_outside_top_10_appended(self) -> None:
        """Current workout ranked 12th should be appended after the top 10."""
        similar = self._make_similar(15)
        # current is row_11 (0-indexed), rank 12
        rows, rank = wdm._build_comparison_display_rows(similar, "row_11", "km")
        assert rank == 12
        assert len(rows) == 11  # top 10 + current
        last = rows[-1]
        assert last["rank_str"] == "→ 12"

    def test_current_inside_top_10_highlighted(self) -> None:
        """Current workout ranked 3rd should have '→ 3' in rank_str."""
        similar = self._make_similar(10)
        rows, rank = wdm._build_comparison_display_rows(similar, "row_2", "km")
        assert rank == 3
        current_row = next(r for r in rows if "→" in r["rank_str"])
        assert current_row["rank_str"] == "→ 3"

    def test_ranks_are_unique_integers(self) -> None:
        """rank field in each display row should be a unique integer."""
        similar = self._make_similar(12)
        rows, _ = wdm._build_comparison_display_rows(similar, "row_11", "km")
        rank_values = [r["rank"] for r in rows]
        assert len(rank_values) == len(set(rank_values))

    def test_unknown_current_id_returns_none_rank(self) -> None:
        """Unknown current_row_id should result in current_rank=None."""
        similar = self._make_similar(5)
        _, rank = wdm._build_comparison_display_rows(similar, "unknown", "km")
        assert rank is None

    def test_empty_similar_returns_empty_rows(self) -> None:
        """Empty similar list should return empty display rows and None rank."""
        rows, rank = wdm._build_comparison_display_rows([], "row_0", "km")
        assert rows == []
        assert rank is None

    def test_custom_top_n(self) -> None:
        """top_n=3 should limit leaderboard to 3 rows (plus overflow)."""
        similar = self._make_similar(10)
        rows, _ = wdm._build_comparison_display_rows(similar, "row_0", "km", top_n=3)
        # row_0 is rank 1 (inside top 3), so exactly 3 rows
        assert len(rows) == 3


# ---------------------------------------------------------------------------
# _do_refresh_comparisons_tab
# ---------------------------------------------------------------------------


class TestDoRefreshComparisonsTab:
    """Tests for wdm._do_refresh_comparisons_tab()."""

    def _dummy_widgets(self) -> tuple[_DummyElement, _DummyElement, _DummyElement, _DummyElement]:
        return _DummyElement(), _DummyElement(), _DummyElement(), _DummyElement()

    def test_no_route_shows_no_route_label(self) -> None:
        """Workout without GPS route should show the no-route placeholder."""
        no_route, no_similar, rank_lbl, table = self._dummy_widgets()
        row: dict[str, Any] = {}
        wdm._do_refresh_comparisons_tab(no_route, no_similar, rank_lbl, table, row, [row])
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
        wdm._do_refresh_comparisons_tab(no_route, no_similar, rank_lbl, table, row, [row])
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
        wdm._do_refresh_comparisons_tab(
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
            wdm, "find_similar_route_workouts", wraps=wdm.find_similar_route_workouts
        ) as mock_find:
            wdm._do_refresh_comparisons_tab(no_route, no_similar, rank_lbl, table, row_a, all_rows)
            wdm._do_refresh_comparisons_tab(no_route, no_similar, rank_lbl, table, row_a, all_rows)

        # Should only be called once due to caching in row["similar_routes"]
        assert mock_find.call_count == 1

    def test_rank_label_contains_rank_and_total(self) -> None:
        """Rank label should mention both the user's rank and total count."""
        no_route, no_similar, rank_lbl, table = self._dummy_widgets()
        route_pts = [(48.85, 2.35), (48.87, 2.37)]
        row_a = _make_row_with_route(idx=0, route=_build_route(route_pts), duration_sort=3000.0)
        row_b = _make_row_with_route(idx=1, route=_build_route(route_pts), duration_sort=4000.0)
        wdm._do_refresh_comparisons_tab(
            no_route, no_similar, rank_lbl, table, row_a, [row_a, row_b]
        )
        # row_a is fastest so rank=1, total=2
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
