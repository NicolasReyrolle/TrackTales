"""Tests for ui.workout_detail_modal — Intervals tab (GPS splits)."""

from __future__ import annotations

from contextlib import ExitStack
from datetime import timedelta
from typing import Any

import pandas as pd
import pytest

from ui import workout_detail_modal as wdm

from ._stubs import _all_patches, _ButtonStub, _DummyElement, _make_row


class TestSplitsTabSection:
    """Tests for the Splits tab rendering in the modal."""

    def test_splits_table_hidden_when_no_splits(self) -> None:
        """Splits table should be hidden when splits list is empty."""
        rows = [
            {
                **_make_row(idx=0, activity_type="Running", raw_activity_type="Running"),
                "pace": "6:00 /km",
                "splits": [],
            },
        ]
        table_stubs: list[_DummyElement] = []
        tabs_stub = _DummyElement()

        def make_table(*_a: Any, **_kw: Any) -> _DummyElement:
            tbl = _DummyElement()
            table_stubs.append(tbl)
            return tbl

        with ExitStack() as stack:
            for p in _all_patches(table_side_effect=make_table, tabs_stub=tabs_stub):
                stack.enter_context(p)
            fn = wdm.create_workout_detail_modal(rows)

        fn(0)
        tabs_stub.fire_value_change("intervals")
        splits_table = table_stubs[1]
        assert not splits_table._visible

    def test_splits_table_visible_and_populated_when_splits_present(self) -> None:
        """Splits table should be visible and contain one row per split."""
        splits_data = [
            {"split": 1, "pace_min_per_km": 5.5, "elevation_change_m": 3.0},
            {"split": 2, "pace_min_per_km": 5.75, "elevation_change_m": -1.0},
        ]
        rows = [
            {
                **_make_row(idx=0, activity_type="Running", raw_activity_type="Running"),
                "pace": "5:39 /km",
                "splits": splits_data,
            },
        ]
        table_stubs: list[_DummyElement] = []
        tabs_stub = _DummyElement()

        def make_table(*_a: Any, **_kw: Any) -> _DummyElement:
            tbl = _DummyElement()
            table_stubs.append(tbl)
            return tbl

        with ExitStack() as stack:
            for p in _all_patches(table_side_effect=make_table, tabs_stub=tabs_stub):
                stack.enter_context(p)
            fn = wdm.create_workout_detail_modal(rows)

        fn(0)
        tabs_stub.fire_value_change("intervals")
        splits_table = table_stubs[1]
        assert splits_table._visible
        assert len(splits_table.rows) == 2
        assert splits_table.rows[0]["split"] == 1
        assert splits_table.rows[1]["split"] == 2

    def test_splits_table_hidden_for_non_running_activity(self) -> None:
        """Splits table should be hidden when the workout has no splits (non-running)."""
        rows = [_make_row(idx=0, activity_type="Cycling", raw_activity_type="Cycling")]
        table_stubs: list[_DummyElement] = []
        tabs_stub = _DummyElement()

        def make_table(*_a: Any, **_kw: Any) -> _DummyElement:
            tbl = _DummyElement()
            table_stubs.append(tbl)
            return tbl

        with ExitStack() as stack:
            for p in _all_patches(table_side_effect=make_table, tabs_stub=tabs_stub):
                stack.enter_context(p)
            fn = wdm.create_workout_detail_modal(rows)

        fn(0)
        tabs_stub.fire_value_change("intervals")
        splits_table = table_stubs[1]
        assert not splits_table._visible

    def test_pace_converted_to_min_per_mi_for_imperial_splits(self) -> None:
        """Pace values should be scaled from min/km to min/mi when distance_unit is 'mi'."""
        splits_data = [{"split": 1, "pace_min_per_km": 6.0, "elevation_change_m": 0.0}]
        rows = [
            {
                **_make_row(idx=0, activity_type="Running", raw_activity_type="Running"),
                "pace": "6:00 /km",
                "splits": splits_data,
                "distance_unit": "mi",
            },
        ]
        table_stubs: list[_DummyElement] = []
        tabs_stub = _DummyElement()

        def make_table(*_a: Any, **_kw: Any) -> _DummyElement:
            tbl = _DummyElement()
            table_stubs.append(tbl)
            return tbl

        with ExitStack() as stack:
            for p in _all_patches(table_side_effect=make_table, tabs_stub=tabs_stub):
                stack.enter_context(p)
            fn = wdm.create_workout_detail_modal(rows)

        fn(0)
        tabs_stub.fire_value_change("intervals")
        splits_table = table_stubs[1]
        assert splits_table._visible
        assert len(splits_table.rows) == 1
        pace_str = splits_table.rows[0]["pace_str"]
        minutes = int(pace_str.split(":")[0])
        assert minutes == 9

    def test_splits_table_shows_average_heart_rate_when_available(self) -> None:
        """Intervals table should expose per-split average heart rate when present."""
        splits_data = [
            {
                "split": 1,
                "pace_min_per_km": 5.5,
                "elevation_change_m": 3.0,
                "avg_heart_rate": 149.5,
            }
        ]
        rows = [
            {
                **_make_row(idx=0, activity_type="Running", raw_activity_type="Running"),
                "pace": "5:30 /km",
                "splits": splits_data,
            },
        ]
        table_stubs: list[_DummyElement] = []
        tabs_stub = _DummyElement()

        def make_table(*_a: Any, **_kw: Any) -> _DummyElement:
            tbl = _DummyElement()
            table_stubs.append(tbl)
            return tbl

        with ExitStack() as stack:
            for p in _all_patches(table_side_effect=make_table, tabs_stub=tabs_stub):
                stack.enter_context(p)
            fn = wdm.create_workout_detail_modal(rows)

        fn(0)
        tabs_stub.fire_value_change("intervals")
        splits_table = table_stubs[1]
        assert splits_table.rows[0]["avg_hr_str"] == "150 bpm"

    def test_navigate_while_on_splits_tab_refreshes_splits(self) -> None:
        """Navigating while the Intervals tab is active should refresh splits."""
        splits_row0 = [{"split": 1, "pace_min_per_km": 5.0, "elevation_change_m": 0.0}]
        rows = [
            {
                **_make_row(idx=0, activity_type="Running", raw_activity_type="Running"),
                "pace": "5:00 /km",
                "splits": splits_row0,
            },
            {
                **_make_row(idx=1, activity_type="Running", raw_activity_type="Running"),
                "pace": "5:00 /km",
                "splits": [],
            },
        ]
        table_stubs: list[_DummyElement] = []
        created_buttons: list[_ButtonStub] = []
        tabs_stub = _DummyElement()

        def make_table(*_a: Any, **_kw: Any) -> _DummyElement:
            tbl = _DummyElement()
            table_stubs.append(tbl)
            return tbl

        def make_button(*args: Any, **kwargs: Any) -> _ButtonStub:
            btn = _ButtonStub(*args, **kwargs)
            created_buttons.append(btn)
            return btn

        with ExitStack() as stack:
            for p in _all_patches(
                table_side_effect=make_table,
                button_side_effect=make_button,
                tabs_stub=tabs_stub,
            ):
                stack.enter_context(p)
            fn = wdm.create_workout_detail_modal(rows)

        fn(0)
        tabs_stub.fire_value_change("intervals")
        splits_table = table_stubs[1]
        assert splits_table._visible

        next_btn = created_buttons[2]  # Button order: [0] close, [1] prev, [2] next
        next_btn.click()
        assert not splits_table._visible


class TestSplitsColumnHeader:
    """Tests for the splits table column-header unit label."""

    def _create_modal_with_du(self, distance_unit: str) -> list[Any]:
        """Create modal with one run row using *distance_unit*, return captured tables."""
        splits_data = [{"split": 1, "pace_min_per_km": 6.0, "elevation_change_m": 0.0}]
        rows = [
            {
                **_make_row(idx=0, activity_type="Running", raw_activity_type="Running"),
                "splits": splits_data,
                "distance_unit": distance_unit,
            },
        ]
        table_stubs: list[Any] = []

        def make_table(*_a: Any, **_kw: Any) -> Any:
            tbl = _DummyElement(*_a, **_kw)
            table_stubs.append(tbl)
            return tbl

        with ExitStack() as stack:
            for p in _all_patches(table_side_effect=make_table):
                stack.enter_context(p)
            wdm.create_workout_detail_modal(rows)

        return table_stubs

    def test_initial_header_is_km_when_metric(self) -> None:
        """The split-number column label should start as 'km' for metric rows."""
        table_stubs = self._create_modal_with_du("km")
        splits_table = table_stubs[1]
        assert splits_table.columns[0]["label"] == "km"

    def test_initial_header_is_mi_when_imperial(self) -> None:
        """The split-number column label should start as 'mi' for imperial rows."""
        table_stubs = self._create_modal_with_du("mi")
        splits_table = table_stubs[1]
        assert splits_table.columns[0]["label"] == "mi"

    def test_header_updated_to_mi_when_intervals_tab_opened(self) -> None:
        """Column label should update to 'mi' when Intervals tab is opened in imperial mode."""
        splits_data = [{"split": 1, "pace_min_per_km": 6.0, "elevation_change_m": 0.0}]
        rows = [
            {
                **_make_row(idx=0, activity_type="Running", raw_activity_type="Running"),
                "splits": splits_data,
                "distance_unit": "mi",
            },
        ]
        table_stubs: list[Any] = []
        tabs_stub = _DummyElement()

        def make_table(*_a: Any, **_kw: Any) -> Any:
            tbl = _DummyElement(*_a, **_kw)
            table_stubs.append(tbl)
            return tbl

        with ExitStack() as stack:
            for p in _all_patches(table_side_effect=make_table, tabs_stub=tabs_stub):
                stack.enter_context(p)
            fn = wdm.create_workout_detail_modal(rows)

        fn(0)
        tabs_stub.fire_value_change("intervals")
        splits_table = table_stubs[1]
        assert splits_table.columns[0]["label"] == "mi"


class TestComputeSplitsLazy:
    """Unit tests for _compute_splits_lazy()."""

    def _make_route(self, n_points: int = 1001, speed_m_s: float = 3.0) -> Any:
        """Build a WorkoutRoute with *n_points* evenly-spaced speed-only points."""
        from logic.workout_manager.workout_route import RoutePoint, WorkoutRoute

        base_time = pd.Timestamp("2024-01-01 10:00:00").to_pydatetime().replace(tzinfo=None)
        points = [
            RoutePoint(
                time=base_time + timedelta(seconds=i),
                latitude=0.0,
                longitude=0.0,
                altitude=0.0,
                speed=speed_m_s,
            )
            for i in range(n_points)
        ]
        return WorkoutRoute(points=points)

    def test_returns_empty_list_and_caches_when_no_route(self) -> None:
        """Should return [] and cache the result in the row dict when route is absent."""
        row: dict[str, Any] = {"distance_unit": "km", "distance_sort": 3000.0}
        result = wdm._compute_splits_lazy(row)
        assert result == []
        assert row["splits"] == []

    def test_computes_splits_from_route(self) -> None:
        """Should compute ≥ 3 km splits for a ~3 km route and cache them."""
        route = self._make_route(n_points=1001, speed_m_s=3.0)
        row: dict[str, Any] = {"route": route, "distance_unit": "km", "distance_sort": 3000.0}
        result = wdm._compute_splits_lazy(row)
        assert len(result) >= 3
        assert row["splits"] is result

    def test_caches_result_on_second_call(self) -> None:
        """A second call should return the same list object without recomputing."""
        route = self._make_route(n_points=1001, speed_m_s=3.0)
        row: dict[str, Any] = {"route": route, "distance_unit": "km", "distance_sort": 3000.0}
        first = wdm._compute_splits_lazy(row)
        second = wdm._compute_splits_lazy(row)
        assert second is first

    def test_uses_mile_split_distance_for_imperial(self) -> None:
        """In imperial mode the split interval should be ~1609 m, yielding fewer splits."""
        route = self._make_route(n_points=1001, speed_m_s=3.0)
        row_km: dict[str, Any] = {"route": route, "distance_unit": "km", "distance_sort": 3000.0}
        row_mi: dict[str, Any] = {"route": route, "distance_unit": "mi", "distance_sort": 3000.0}
        splits_km = wdm._compute_splits_lazy(row_km)
        splits_mi = wdm._compute_splits_lazy(row_mi)
        assert len(splits_km) > len(splits_mi)

    def test_splits_computed_lazily_in_modal(self) -> None:
        """Splits should not be computed on modal open; only when the Splits tab is shown."""
        from logic.workout_manager.workout_route import RoutePoint, WorkoutRoute

        base_time = pd.Timestamp("2024-01-01 10:00:00").to_pydatetime().replace(tzinfo=None)
        points = [
            RoutePoint(
                time=base_time + timedelta(seconds=i),
                latitude=0.0,
                longitude=0.0,
                altitude=0.0,
                speed=3.0,
            )
            for i in range(1001)
        ]
        route = WorkoutRoute(points=points)

        rows = [
            {
                **_make_row(idx=0, activity_type="Running", raw_activity_type="Running"),
                "pace": "5:33 /km",
                "distance_unit": "km",
                "route": route,
            },
        ]
        table_stubs: list[_DummyElement] = []
        tabs_stub = _DummyElement()

        def make_table(*_a: Any, **_kw: Any) -> _DummyElement:
            tbl = _DummyElement()
            table_stubs.append(tbl)
            return tbl

        with ExitStack() as stack:
            for p in _all_patches(table_side_effect=make_table, tabs_stub=tabs_stub):
                stack.enter_context(p)
            fn = wdm.create_workout_detail_modal(rows)

        fn(0)
        assert "splits" not in rows[0]

        tabs_stub.fire_value_change("intervals")
        splits_table = table_stubs[1]
        assert splits_table._visible
        assert len(splits_table.rows) >= 3

    def test_lazy_route_enrichment_uses_utc_workout_bounds(self) -> None:
        """Lazy modal enrichment should use UTC workout bounds when matching HR samples."""
        from app_state import state
        from logic.records_by_type import RecordsByType
        from logic.workout_manager.workout_route import RoutePoint, WorkoutRoute

        original_records = state.records_by_type
        route = WorkoutRoute(
            points=[
                RoutePoint(
                    time=pd.Timestamp("2025-01-02 10:00:00+00:00").to_pydatetime(),
                    latitude=48.85,
                    longitude=2.35,
                    altitude=35.0,
                    speed=3.0,
                ),
                RoutePoint(
                    time=pd.Timestamp("2025-01-02 10:05:00+00:00").to_pydatetime(),
                    latitude=48.86,
                    longitude=2.36,
                    altitude=36.0,
                    speed=3.1,
                ),
            ]
        )
        heart_rate_df = pd.DataFrame(
            [
                {"startDate": "2025-01-02 10:00:10+00:00", "value": 141},
                {"startDate": "2025-01-02 10:04:50+00:00", "value": 149},
            ]
        )
        row: dict[str, Any] = {
            "route": route,
            "distance_unit": "km",
            "distance_sort": 3000.0,
            "workout_start_utc": pd.Timestamp("2025-01-02 10:00:00"),
            "workout_end_utc": pd.Timestamp("2025-01-02 10:10:00"),
        }

        try:
            state.records_by_type = RecordsByType(data={"HeartRate": heart_rate_df})
            wdm._ensure_row_heart_rate_enriched(row)
        finally:
            state.records_by_type = original_records

        assert row["route"].points[0].heart_rate == pytest.approx(141.0)
        assert row["route"].points[1].heart_rate == pytest.approx(149.0)

    def test_computed_splits_include_average_heart_rate_when_loaded_lazily(self) -> None:
        """Lazy split computation should derive per-split average heart rate from records."""
        from app_state import state
        from logic.records_by_type import RecordsByType
        from logic.workout_manager.workout_route import RoutePoint, WorkoutRoute

        original_records = state.records_by_type
        base_time = pd.Timestamp("2024-01-01 10:00:00").to_pydatetime().replace(tzinfo=None)
        points = [
            RoutePoint(
                time=base_time + timedelta(seconds=i),
                latitude=0.0,
                longitude=0.0,
                altitude=0.0,
                speed=3.0,
            )
            for i in range(1001)
        ]
        route = WorkoutRoute(points=points)
        heart_rate_df = pd.DataFrame(
            [
                {
                    "startDate": (base_time + timedelta(seconds=i)).isoformat(),
                    "value": 140.0 + (i % 2),
                }
                for i in range(1001)
            ]
        )
        row: dict[str, Any] = {
            "route": route,
            "distance_unit": "km",
            "distance_sort": 3000.0,
            "workout_start_utc": pd.Timestamp(base_time),
            "workout_end_utc": pd.Timestamp(base_time + timedelta(seconds=1000)),
        }

        try:
            state.records_by_type = RecordsByType(data={"HeartRate": heart_rate_df})
            result = wdm._compute_splits_lazy(row)
        finally:
            state.records_by_type = original_records

        assert result
        assert result[0]["avg_heart_rate"] == pytest.approx(140.5, abs=0.6)
        assert "splits" in row
        assert len(row["splits"]) >= 3
