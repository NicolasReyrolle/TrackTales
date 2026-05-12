"""Tests for ui.workout_detail_modal module — core modal, field displays, row helpers."""

from __future__ import annotations

import asyncio
from contextlib import ExitStack
from typing import Any
from unittest.mock import patch

import pytest

import ui.workout_detail_modal.comparisons as wdmc
from ui import workout_detail_modal as wdm

from ._stubs import _all_patches, _ButtonStub, _DummyElement, _make_row


class TestFieldDisplay:
    """Tests for the _FIELD_DISPLAY constant."""

    def test_all_expected_keys_present(self) -> None:
        """_FIELD_DISPLAY should cover all generic row fields shown in the table."""
        field_keys = {key for key, _ in wdm._FIELD_DISPLAY}
        for expected in [
            "date",
            "activity_type",
            "duration",
            "distance",
            "calories",
            "vo2_max",
            "temperature",
            "humidity",
        ]:
            assert expected in field_keys

    def test_labels_are_non_empty_strings(self) -> None:
        """Every label in _FIELD_DISPLAY should be a callable returning a non-empty string."""
        for _key, label_fn in wdm._FIELD_DISPLAY:
            assert callable(label_fn)
            assert label_fn() and isinstance(label_fn(), str)


class TestWalkingFieldDisplay:
    """Tests for the _WALKING_FIELD_DISPLAY constant."""

    def test_all_expected_keys_present(self) -> None:
        """_WALKING_FIELD_DISPLAY should include pace, cadence, step_length, and step_count."""
        field_keys = {key for key, _ in wdm._WALKING_FIELD_DISPLAY}
        for expected in ["pace", "cadence", "step_length", "step_count"]:
            assert expected in field_keys

    def test_labels_are_non_empty_strings(self) -> None:
        """Every label in _WALKING_FIELD_DISPLAY should return a non-empty string."""
        for _key, label_fn in wdm._WALKING_FIELD_DISPLAY:
            assert callable(label_fn)
            assert label_fn() and isinstance(label_fn(), str)


class TestHikingFieldDisplay:
    """Tests for the _HIKING_FIELD_DISPLAY constant."""

    def test_all_expected_keys_present(self) -> None:
        """_HIKING_FIELD_DISPLAY should cover elevation, pace, cadence, step_length, step_count."""
        field_keys = {key for key, _ in wdm._HIKING_FIELD_DISPLAY}
        for expected in ["elevation", "pace", "cadence", "step_length", "step_count"]:
            assert expected in field_keys

    def test_labels_are_non_empty_strings(self) -> None:
        """Every label in _HIKING_FIELD_DISPLAY should return a non-empty string."""
        for _key, label_fn in wdm._HIKING_FIELD_DISPLAY:
            assert callable(label_fn)
            assert label_fn() and isinstance(label_fn(), str)


class TestRunningFieldDisplay:
    """Tests for _RUNNING_FIELD_DISPLAY constant and running section in the modal."""

    def test_all_expected_running_keys_present(self) -> None:
        """_RUNNING_FIELD_DISPLAY should include pace, cadence, stride length, and step count.

        VO2 max was moved to the generic Overview display (_FIELD_DISPLAY) since Apple Watch
        reports it for all workout types, not only running.
        """
        keys = {key for key, _ in wdm._RUNNING_FIELD_DISPLAY}
        for expected in ["pace", "cadence", "stride_length", "step_count"]:
            assert expected in keys

    def test_vo2_max_not_in_running_field_display(self) -> None:
        """vo2_max should NOT appear in _RUNNING_FIELD_DISPLAY (it is generic)."""
        keys = {key for key, _ in wdm._RUNNING_FIELD_DISPLAY}
        assert "vo2_max" not in keys

    def test_running_labels_are_non_empty_strings(self) -> None:
        """Every label in _RUNNING_FIELD_DISPLAY should be callable and non-empty."""
        for _key, label_fn in wdm._RUNNING_FIELD_DISPLAY:
            assert callable(label_fn)
            assert label_fn() and isinstance(label_fn(), str)


class TestCreateWorkoutDetailModal:
    """Tests for create_workout_detail_modal()."""

    def test_returns_noop_for_empty_rows(self) -> None:
        """create_workout_detail_modal([]) should return a no-op callable."""
        fn = wdm.create_workout_detail_modal([])
        # Should not raise for any index
        fn(0)
        fn(99)

    def test_returns_callable_for_non_empty_rows(self) -> None:
        """create_workout_detail_modal(rows) should return a callable."""
        rows = [_make_row(idx=0)]
        with ExitStack() as stack:
            for p in _all_patches():
                stack.enter_context(p)
            fn = wdm.create_workout_detail_modal(rows)

        assert callable(fn)

    def test_open_at_handles_negative_index_without_error(self) -> None:
        """open_at() should not raise for negative indices (clamped to 0)."""
        rows = [_make_row(idx=0), _make_row(idx=1)]
        with ExitStack() as stack:
            for p in _all_patches():
                stack.enter_context(p)
            fn = wdm.create_workout_detail_modal(rows)

        fn(-5)  # Should not raise

    def test_open_at_handles_out_of_bounds_index_without_error(self) -> None:
        """open_at() should not raise for indices beyond the row list length (clamped to last)."""
        rows = [_make_row(idx=0)]
        with ExitStack() as stack:
            for p in _all_patches():
                stack.enter_context(p)
            fn = wdm.create_workout_detail_modal(rows)

        fn(100)  # Should not raise

    def test_open_at_non_first_row_enables_prev_button(self) -> None:
        """Opening a non-first row should call set_enabled(True) on the prev button."""
        rows = [_make_row(idx=0), _make_row(idx=1)]
        created_buttons: list[_ButtonStub] = []

        def make_button(*args: Any, **kwargs: Any) -> _ButtonStub:
            btn = _ButtonStub(*args, **kwargs)
            created_buttons.append(btn)
            return btn

        with ExitStack() as stack:
            for p in _all_patches(button_side_effect=make_button):
                stack.enter_context(p)
            fn = wdm.create_workout_detail_modal(rows)

        prev_btn = created_buttons[1]  # Button order: [0] close, [1] prev, [2] next
        fn(1)  # Open at the second (non-first) row — prev should be enabled
        assert prev_btn._enabled is True

    def test_navigate_forward_moves_to_next_row(self) -> None:
        """Clicking the next button should advance to the second row."""
        rows = [
            _make_row(idx=0, activity_type="Running"),
            _make_row(idx=1, activity_type="Cycling", raw_activity_type="Cycling"),
        ]
        label_stubs: list[_DummyElement] = []
        created_buttons: list[_ButtonStub] = []

        def make_label(*_a: Any, **_kw: Any) -> _DummyElement:
            lbl = _DummyElement()
            label_stubs.append(lbl)
            return lbl

        def make_button(*args: Any, **kwargs: Any) -> _ButtonStub:
            btn = _ButtonStub(*args, **kwargs)
            created_buttons.append(btn)
            return btn

        with ExitStack() as stack:
            for p in _all_patches(label_side_effect=make_label, button_side_effect=make_button):
                stack.enter_context(p)
            fn = wdm.create_workout_detail_modal(rows)

        # nav_counter is always the last label created in create_workout_detail_modal.
        nav_counter = label_stubs[-1]
        next_btn = created_buttons[2]  # Button order: [0] close, [1] prev, [2] next
        fn(0)  # Start at row 0 → counter shows "1 / 2"
        next_btn.click()  # Navigate forward via the captured on_click lambda
        assert nav_counter._text == "2 / 2"

    def test_navigate_backward_does_nothing_at_first_row(self) -> None:
        """Clicking prev at the first row should be a no-op (out-of-bounds guard)."""
        rows = [_make_row(idx=0), _make_row(idx=1)]
        label_stubs: list[_DummyElement] = []
        created_buttons: list[_ButtonStub] = []

        def make_label(*_a: Any, **_kw: Any) -> _DummyElement:
            lbl = _DummyElement()
            label_stubs.append(lbl)
            return lbl

        def make_button(*args: Any, **kwargs: Any) -> _ButtonStub:
            btn = _ButtonStub(*args, **kwargs)
            created_buttons.append(btn)
            return btn

        with ExitStack() as stack:
            for p in _all_patches(label_side_effect=make_label, button_side_effect=make_button):
                stack.enter_context(p)
            fn = wdm.create_workout_detail_modal(rows)

        nav_counter = label_stubs[-1]
        prev_btn = created_buttons[1]  # Button order: [0] close, [1] prev, [2] next
        fn(0)  # Start at row 0 → counter shows "1 / 2"
        prev_btn.click()  # Attempt to navigate before the first row
        assert nav_counter._text == "1 / 2"  # Still on row 0

    def test_route_tab_change_triggers_route_refresh(self) -> None:
        """Switching to the Route tab should trigger Route-tab refresh."""
        from datetime import timedelta

        import pandas as pd

        from logic.workout_manager.workout_route import RoutePoint, WorkoutRoute

        base_time = pd.Timestamp("2024-01-01").to_pydatetime()
        route = WorkoutRoute(
            points=[
                RoutePoint(
                    time=base_time + timedelta(seconds=i),
                    latitude=48.85 + (i * 0.0001),
                    longitude=2.35 + (i * 0.0001),
                    altitude=35.0,
                    speed=3.0,
                )
                for i in range(3)
            ]
        )
        rows = [{**_make_row(idx=0), "route": route}]
        tabs_stub = _DummyElement()
        route_refresh_row_calls: list[dict[str, Any]] = []

        def capture_route_refresh(
            _no_route_label: Any, _route_map: Any, row: dict[str, Any]
        ) -> None:
            route_refresh_row_calls.append(row)

        with ExitStack() as stack:
            for p in _all_patches(tabs_stub=tabs_stub):
                stack.enter_context(p)
            stack.enter_context(
                patch(
                    "ui.workout_detail_modal._do_refresh_route_tab",
                    side_effect=capture_route_refresh,
                )
            )
            fn = wdm.create_workout_detail_modal(rows)
            fn(0)
            assert not route_refresh_row_calls
            tabs_stub.fire_value_change("route")
            assert route_refresh_row_calls

    def test_profile_tab_change_triggers_profile_refresh(self) -> None:
        """Switching to the Profile tab should trigger Profile-tab refresh."""
        from datetime import timedelta

        import pandas as pd

        from logic.workout_manager.workout_route import RoutePoint, WorkoutRoute

        base_time = pd.Timestamp("2024-01-01").to_pydatetime()
        route = WorkoutRoute(
            points=[
                RoutePoint(
                    time=base_time + timedelta(seconds=i),
                    latitude=48.85 + (i * 0.0001),
                    longitude=2.35 + (i * 0.0001),
                    altitude=35.0,
                    speed=3.0,
                )
                for i in range(3)
            ]
        )
        rows = [{**_make_row(idx=0), "route": route}]
        tabs_stub = _DummyElement()
        profile_refresh_row_calls: list[dict[str, Any]] = []

        def capture_profile_refresh(
            _no_route_label: Any, _route_profile_chart: Any, row: dict[str, Any]
        ) -> None:
            profile_refresh_row_calls.append(row)

        with ExitStack() as stack:
            for p in _all_patches(tabs_stub=tabs_stub):
                stack.enter_context(p)
            stack.enter_context(
                patch(
                    "ui.workout_detail_modal._do_refresh_route_profile_tab",
                    side_effect=capture_profile_refresh,
                )
            )
            fn = wdm.create_workout_detail_modal(rows)
            fn(0)
            assert not profile_refresh_row_calls
            tabs_stub.fire_value_change("profile")
            assert profile_refresh_row_calls

    def test_fit_route_bounds_after_init_invalidates_and_fits_bounds(self) -> None:
        """Post-init helper should invalidate size and then fit route bounds."""
        route_map = _DummyElement()
        points = [[48.85, 2.35], [48.851, 2.351]]

        asyncio.run(wdm._fit_route_bounds_after_init(route_map, points))

        assert route_map._initialized_calls == 1
        assert route_map._run_map_method_calls[0][0] == ("invalidateSize", False)
        assert route_map._run_map_method_calls[1][0] == (
            "fitBounds",
            points,
            {"padding": [20, 20]},
        )

    def test_fit_route_bounds_after_init_ignores_timeout(self) -> None:
        """Map-fit helper should ignore JS timeout when tab changes during loading."""

        class _TimeoutMap(_DummyElement):
            async def initialized(self) -> None:
                raise TimeoutError

        route_map = _TimeoutMap()
        points = [[48.85, 2.35], [48.851, 2.351]]

        asyncio.run(wdm._fit_route_bounds_after_init(route_map, points))

        assert not route_map._run_map_method_calls

    def test_do_refresh_route_tab_schedules_post_init_fit(self) -> None:
        """Route refresh should schedule a post-init fit for reliable centering."""
        from datetime import timedelta

        import pandas as pd

        from logic.workout_manager.workout_route import RoutePoint, WorkoutRoute

        base_time = pd.Timestamp("2024-01-01").to_pydatetime()
        route = WorkoutRoute(
            points=[
                RoutePoint(
                    time=base_time + timedelta(seconds=i),
                    latitude=48.85 + (i * 0.0001),
                    longitude=2.35 + (i * 0.0001),
                    altitude=35.0,
                    speed=3.0,
                )
                for i in range(3)
            ]
        )
        row = {**_make_row(idx=0), "route": route}
        no_route_label = _DummyElement()
        route_map = _DummyElement()

        def run_coroutine_sync(coro: Any) -> Any:
            return asyncio.run(coro)

        with patch(
            "ui.workout_detail_modal.background_tasks.create",
            side_effect=run_coroutine_sync,
        ) as create_bg:
            wdm._do_refresh_route_tab(no_route_label, route_map, row)

        assert create_bg.call_count == 1
        assert route_map._run_map_method_calls[-1][0][0] == "fitBounds"

    def test_do_refresh_profile_tab_mutates_chart_options_in_place(self) -> None:
        """Profile refresh should mutate chart options in place (NiceGUI options has no setter)."""
        from datetime import timedelta

        import pandas as pd

        from logic.workout_manager.workout_route import RoutePoint, WorkoutRoute

        class _ReadOnlyChart:
            _INITIAL_SERIES_DATA = [[1, 2, 3]]

            def __init__(self) -> None:
                self._visible = True
                self._options_store: dict[str, Any] = {
                    "series": [{"data": self._INITIAL_SERIES_DATA.copy()}]
                }

            @property
            def options(self) -> dict[str, Any]:
                return self._options_store

            def set_visibility(self, visible: bool) -> None:
                self._visible = visible

            def update(self) -> None:
                return

        base_time = pd.Timestamp("2024-01-01").to_pydatetime()
        route = WorkoutRoute(
            points=[
                RoutePoint(
                    time=base_time + timedelta(seconds=i),
                    latitude=48.85 + (i * 0.0001),
                    longitude=2.35 + (i * 0.0001),
                    altitude=35.0 + i,
                    speed=3.0,
                )
                for i in range(3)
            ]
        )
        row = {**_make_row(idx=0), "route": route}
        no_route_label = _DummyElement()
        route_profile_chart = _ReadOnlyChart()

        def execute_background_task_synchronously(coro: Any) -> Any:
            return asyncio.run(coro)

        with patch(
            "ui.workout_detail_modal.background_tasks.create",
            side_effect=execute_background_task_synchronously,
        ):
            wdm._do_refresh_route_profile_tab(no_route_label, route_profile_chart, row)

        assert route_profile_chart.options["backgroundColor"] == "transparent"
        profile_data = route_profile_chart.options["series"][0]["data"]
        assert isinstance(profile_data, list)
        assert len(profile_data) == 3
        assert profile_data[0][1] == 35.0


class TestRouteTabLocalizationAndCoverage:
    """Focused tests for route tab localization and route-parts behavior."""

    @staticmethod
    def _build_route(points: list[tuple[float, float]]) -> Any:
        from datetime import timedelta

        import pandas as pd

        from logic.workout_manager.workout_route import RoutePoint, WorkoutRoute

        base_time = pd.Timestamp("2024-01-01 10:00:00").to_pydatetime()
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

    def test_get_row_routes_prefers_non_empty_route_parts(self) -> None:
        """Route parts should be preferred over the merged fallback route."""
        part = self._build_route([(48.85, 2.35), (48.851, 2.351)])
        fallback = self._build_route([(47.0, 2.0), (47.001, 2.001)])
        row = {"route_parts": [part], "route": fallback}

        assert wdm._get_row_routes(row) == [part]

    def test_do_refresh_route_tab_uses_translated_route_and_marker_labels(self) -> None:
        """Route refresh should pass translated route index/start/end labels to tooltips."""
        row = {"route_parts": [self._build_route([(48.85, 2.35), (48.851, 2.351)])]}
        no_route_label = _DummyElement()
        route_map = _DummyElement()

        t_calls: list[tuple[str, dict[str, str]]] = []
        tooltip_texts: list[str] = []

        def fake_t(message: str, **kwargs: str) -> str:
            t_calls.append((message, kwargs))
            if message == "Route {index}":
                return f"Parcours {kwargs['index']}"
            if message == "Start":
                return "Départ"
            if message == "End":
                return "Arrivée"
            return message

        def capture_run_layer_method(_layer_id: str, method: str, text: str) -> _DummyElement:
            if method == "bindTooltip":
                tooltip_texts.append(text)
            return route_map

        def run_coroutine_sync(coro: Any) -> Any:
            return asyncio.run(coro)

        with (
            patch("ui.workout_detail_modal.t", side_effect=fake_t),
            patch.object(route_map, "run_layer_method", side_effect=capture_run_layer_method),
            patch(
                "ui.workout_detail_modal.background_tasks.create",
                side_effect=run_coroutine_sync,
            ),
        ):
            wdm._do_refresh_route_tab(no_route_label, route_map, row)

        assert ("Route {index}", {"index": "1"}) in t_calls
        assert ("Start", {}) in t_calls
        assert ("End", {}) in t_calls
        assert "Parcours 1" in tooltip_texts
        assert "Départ - Parcours 1" in tooltip_texts
        assert "Arrivée - Parcours 1" in tooltip_texts

    def test_do_refresh_route_tab_falls_back_when_points_are_invalid(self) -> None:
        """Route tab should fall back to world view when every route point is invalid."""
        from datetime import datetime

        from logic.workout_manager.workout_route import RoutePoint, WorkoutRoute

        invalid_route = WorkoutRoute(
            points=[
                RoutePoint(
                    time=datetime(2024, 1, 1, 10, 0, 0),
                    latitude=float("nan"),
                    longitude=2.35,
                    altitude=100.0,
                    speed=3.0,
                )
            ]
        )
        row = {"route": invalid_route}
        no_route_label = _DummyElement()
        route_map = _DummyElement()

        with (
            patch.object(route_map, "set_center") as set_center,
            patch.object(route_map, "set_zoom") as set_zoom,
        ):
            wdm._do_refresh_route_tab(no_route_label, route_map, row)

        assert not no_route_label._visible
        assert route_map._visible
        set_center.assert_called_once_with((0.0, 0.0))
        set_zoom.assert_called_once_with(1)

    def test_build_route_profile_chart_config_includes_altitude_and_metric_columns(self) -> None:
        """Route profile config should include altitude and sampled pace/speed metadata."""
        from datetime import timedelta

        import pandas as pd

        from logic.workout_manager.workout_route import RoutePoint, WorkoutRoute

        base_time = pd.Timestamp("2024-01-01").to_pydatetime()
        route = WorkoutRoute(
            points=[
                RoutePoint(
                    time=base_time + timedelta(seconds=i * 10),
                    latitude=48.85 + (i * 0.0001),
                    longitude=2.35 + (i * 0.0001),
                    altitude=100.0 + i,
                    speed=3.0 + i,
                )
                for i in range(3)
            ]
        )

        config = wdm._build_route_profile_chart_config([route])
        altitude_series = config["series"][0]
        pace_series = config["series"][1]
        altitude_data = altitude_series["data"]
        pace_data = pace_series["data"]

        assert config["backgroundColor"] == "transparent"
        assert config["legend"]["top"] == 8
        assert config["xAxis"]["nameLocation"] == "middle"
        assert config["xAxis"]["nameGap"] == 42
        assert isinstance(config["yAxis"], list)
        assert config["yAxis"][0]["scale"] is True
        assert config["yAxis"][0]["nameLocation"] == "middle"
        assert config["yAxis"][0]["nameGap"] == 52
        assert config["yAxis"][1]["scale"] is True
        assert config["yAxis"][1]["nameLocation"] == "middle"
        assert config["yAxis"][1]["nameGap"] == 56
        assert altitude_data[0][1] == 100.0
        assert pace_data[1][2] is not None  # pace min/km
        assert pace_data[1][3] is not None  # speed km/h

    def test_build_route_profile_chart_config_smooths_pause_spikes(self) -> None:
        """Pause-like segments should not inject extreme pace spikes into profile samples."""
        from datetime import timedelta

        import pandas as pd

        from logic.workout_manager.workout_route import RoutePoint, WorkoutRoute

        base_time = pd.Timestamp("2024-01-01").to_pydatetime()
        route = WorkoutRoute(
            points=[
                RoutePoint(
                    time=base_time,
                    latitude=48.8500,
                    longitude=2.3500,
                    altitude=100.0,
                    speed=0.0,
                ),
                RoutePoint(
                    time=base_time + timedelta(seconds=60),
                    latitude=48.8509,
                    longitude=2.3500,
                    altitude=101.0,
                    speed=0.0,
                ),
                RoutePoint(
                    time=base_time + timedelta(seconds=240),
                    latitude=48.8510,
                    longitude=2.3500,
                    altitude=102.0,
                    speed=0.0,
                ),
                RoutePoint(
                    time=base_time + timedelta(seconds=300),
                    latitude=48.8519,
                    longitude=2.3500,
                    altitude=103.0,
                    speed=0.0,
                ),
            ]
        )

        config = wdm._build_route_profile_chart_config([route])
        data = config["series"][0]["data"]
        segment_time_s = 60.0
        expected_distance_m = WorkoutRoute.haversine_m(48.8500, 2.3500, 48.8509, 2.3500)
        expected_pace_min_per_km = (segment_time_s / 60.0) / (expected_distance_m / 1000.0)

        assert data[2][2] is not None
        assert data[2][2] == pytest.approx(expected_pace_min_per_km, rel=0.05)

    def test_build_route_profile_chart_config_skips_empty_altitude_dataframe(self) -> None:
        """Routes with empty altitude data should produce no profile points."""
        from datetime import timedelta

        import pandas as pd

        from logic.workout_manager.workout_route import RoutePoint, WorkoutRoute

        base_time = pd.Timestamp("2024-01-01").to_pydatetime()
        route = WorkoutRoute(
            points=[
                RoutePoint(
                    time=base_time + timedelta(seconds=i * 10),
                    latitude=48.85 + (i * 0.0001),
                    longitude=2.35 + (i * 0.0001),
                    altitude=100.0 + i,
                    speed=3.0 + i,
                )
                for i in range(2)
            ]
        )
        with patch.object(route, "to_dataframe", return_value=pd.DataFrame({"altitude": []})):
            config = wdm._build_route_profile_chart_config([route])

        assert config["series"][0]["data"] == []

    def test_build_route_profile_chart_config_skips_invalid_route_points(self) -> None:
        """Routes with fewer than two valid map points should not emit profile points."""
        from datetime import timedelta

        import pandas as pd

        from logic.workout_manager.workout_route import RoutePoint, WorkoutRoute

        base_time = pd.Timestamp("2024-01-01").to_pydatetime()
        route = WorkoutRoute(
            points=[
                RoutePoint(
                    time=base_time,
                    latitude=48.85,
                    longitude=2.35,
                    altitude=100.0,
                    speed=3.0,
                ),
                RoutePoint(
                    time=base_time + timedelta(seconds=10),
                    latitude=float("nan"),
                    longitude=2.3501,
                    altitude=101.0,
                    speed=3.2,
                ),
            ]
        )

        with patch.object(
            route,
            "to_dataframe",
            return_value=pd.DataFrame({"altitude": [100.0, 101.0]}),
        ):
            config = wdm._build_route_profile_chart_config([route])

        assert config["series"][0]["data"] == []

    def test_do_refresh_route_tab_uses_plain_route_polyline(self) -> None:
        """Route refresh should use a single plain polyline per route."""
        from datetime import timedelta

        import pandas as pd

        from logic.workout_manager.workout_route import RoutePoint, WorkoutRoute

        base_time = pd.Timestamp("2024-01-01").to_pydatetime()
        route = WorkoutRoute(
            points=[
                RoutePoint(
                    time=base_time + timedelta(seconds=i * 10),
                    latitude=48.85 + (i * 0.0001),
                    longitude=2.35 + (i * 0.0001),
                    altitude=35.0 + i,
                    speed=2.0 + (i * 2.0),
                )
                for i in range(3)
            ]
        )
        row = {"route": route}
        no_route_label = _DummyElement()
        route_map = _DummyElement()
        polyline_colors: list[str] = []
        tooltip_texts: list[str] = []

        def capture_layer(name: str, args: list[Any]) -> _DummyElement:
            if name == "polyline":
                polyline_colors.append(args[1]["color"])
            return _DummyElement()

        def capture_tooltip(_layer_id: str, method: str, text: str) -> _DummyElement:
            if method == "bindTooltip":
                tooltip_texts.append(text)
            return route_map

        def run_coroutine_sync(coro: Any) -> Any:
            return asyncio.run(coro)

        with (
            patch.object(route_map, "generic_layer", side_effect=capture_layer),
            patch.object(route_map, "run_layer_method", side_effect=capture_tooltip),
            patch(
                "ui.workout_detail_modal.background_tasks.create", side_effect=run_coroutine_sync
            ),
        ):
            wdm._do_refresh_route_tab(no_route_label, route_map, row)

        assert polyline_colors == ["#2563eb"]
        assert "Route 1" in tooltip_texts


class TestActivityTabSection:
    """Tests for the Activity tab rendering in the modal."""

    def test_running_container_hidden_for_non_running_activity(self) -> None:
        """Running container should be hidden when raw_activity_type is not 'Running'."""
        rows = [_make_row(idx=0, activity_type="Cycling", raw_activity_type="Cycling")]
        column_stubs: list[_DummyElement] = []

        def make_column(*_a: Any, **_kw: Any) -> _DummyElement:
            col = _DummyElement()
            column_stubs.append(col)
            return col

        with ExitStack() as stack:
            for p in _all_patches(column_side_effect=make_column):
                stack.enter_context(p)
            fn = wdm.create_workout_detail_modal(rows)

        fn(0)
        running_container = column_stubs[2]
        assert not running_container._visible

    def test_running_container_visible_for_running_activity(self) -> None:
        """Running container should be visible when raw_activity_type is 'Running'."""
        rows = [
            {
                **_make_row(idx=0, activity_type="Running", raw_activity_type="Running"),
                "pace": "6:00 /km",
                "splits": [],
            },
        ]
        column_stubs: list[_DummyElement] = []

        def make_column(*_a: Any, **_kw: Any) -> _DummyElement:
            col = _DummyElement()
            column_stubs.append(col)
            return col

        with ExitStack() as stack:
            for p in _all_patches(column_side_effect=make_column):
                stack.enter_context(p)
            fn = wdm.create_workout_detail_modal(rows)

        fn(0)
        running_container = column_stubs[2]
        assert running_container._visible

    def test_running_container_visible_when_activity_type_is_translated(self) -> None:
        """Running container must use raw_activity_type, not the translated display label.

        Simulates the French locale where activity_type='Course à pied' but
        raw_activity_type='Running'.  The running container must still be shown.
        """
        rows = [
            {
                **_make_row(
                    idx=0,
                    activity_type="Course à pied",  # French display label
                    raw_activity_type="Running",  # raw Apple Health type (always English)
                ),
                "pace": "6:00 /km",
                "splits": [],
            },
        ]
        column_stubs: list[_DummyElement] = []

        def make_column(*_a: Any, **_kw: Any) -> _DummyElement:
            col = _DummyElement()
            column_stubs.append(col)
            return col

        with ExitStack() as stack:
            for p in _all_patches(column_side_effect=make_column):
                stack.enter_context(p)
            fn = wdm.create_workout_detail_modal(rows)

        fn(0)
        running_container = column_stubs[2]
        assert running_container._visible  # must be shown despite translated label

    def test_walking_container_hidden_for_non_walking_activity(self) -> None:
        """Walking container should be hidden when raw_activity_type is not 'Walking'."""
        rows = [_make_row(idx=0, activity_type="Cycling", raw_activity_type="Cycling")]
        column_stubs: list[_DummyElement] = []

        def make_column(*_a: Any, **_kw: Any) -> _DummyElement:
            col = _DummyElement()
            column_stubs.append(col)
            return col

        with ExitStack() as stack:
            for p in _all_patches(column_side_effect=make_column):
                stack.enter_context(p)
            fn = wdm.create_workout_detail_modal(rows)

        fn(0)
        walking_container = column_stubs[3]
        assert not walking_container._visible

    def test_walking_container_visible_for_walking_activity(self) -> None:
        """Walking container should be visible when raw_activity_type is 'Walking'."""
        rows = [
            {
                **_make_row(idx=0, activity_type="Walking", raw_activity_type="Walking"),
                "pace": "12:00 /km",
                "cadence": "110 spm",
                "step_length": "0.72 m",
                "step_count": "6500",
                "splits": [],
            },
        ]
        column_stubs: list[_DummyElement] = []

        def make_column(*_a: Any, **_kw: Any) -> _DummyElement:
            col = _DummyElement()
            column_stubs.append(col)
            return col

        with ExitStack() as stack:
            for p in _all_patches(column_side_effect=make_column):
                stack.enter_context(p)
            fn = wdm.create_workout_detail_modal(rows)

        fn(0)
        running_container = column_stubs[2]
        walking_container = column_stubs[3]
        assert not running_container._visible
        assert walking_container._visible

    def test_walking_container_uses_raw_activity_type(self) -> None:
        """Walking container must use raw_activity_type, not the translated display label.

        Simulates a locale where activity_type is translated but raw_activity_type
        remains 'Walking'.  The walking container must still be shown.
        """
        rows = [
            {
                **_make_row(
                    idx=0,
                    activity_type="Marche",  # translated display label
                    raw_activity_type="Walking",  # raw Apple Health type (always English)
                ),
                "pace": "12:00 /km",
                "cadence": "110 spm",
                "step_length": "0.72 m",
                "step_count": "6500",
                "splits": [],
            },
        ]
        column_stubs: list[_DummyElement] = []

        def make_column(*_a: Any, **_kw: Any) -> _DummyElement:
            col = _DummyElement()
            column_stubs.append(col)
            return col

        with ExitStack() as stack:
            for p in _all_patches(column_side_effect=make_column):
                stack.enter_context(p)
            fn = wdm.create_workout_detail_modal(rows)

        fn(0)
        walking_container = column_stubs[3]
        assert walking_container._visible  # must be shown despite translated label

    def test_hiking_container_hidden_for_non_hiking_activity(self) -> None:
        """Hiking container should be hidden when raw_activity_type is not 'Hiking'."""
        rows = [_make_row(idx=0, activity_type="Cycling", raw_activity_type="Cycling")]
        column_stubs: list[_DummyElement] = []

        def make_column(*_a: Any, **_kw: Any) -> _DummyElement:
            col = _DummyElement()
            column_stubs.append(col)
            return col

        with ExitStack() as stack:
            for p in _all_patches(column_side_effect=make_column):
                stack.enter_context(p)
            fn = wdm.create_workout_detail_modal(rows)

        fn(0)
        hiking_container = column_stubs[4]
        assert not hiking_container._visible

    def test_hiking_container_visible_for_hiking_activity(self) -> None:
        """Hiking container should be visible when raw_activity_type is 'Hiking'."""
        rows = [
            {
                **_make_row(idx=0, activity_type="Hiking", raw_activity_type="Hiking"),
                "pace": "15:00 /km",
                "cadence": "95 spm",
                "step_length": "0.65 m",
                "step_count": "8000",
                "elevation": "250 m",
                "splits": [],
            },
        ]
        column_stubs: list[_DummyElement] = []

        def make_column(*_a: Any, **_kw: Any) -> _DummyElement:
            col = _DummyElement()
            column_stubs.append(col)
            return col

        with ExitStack() as stack:
            for p in _all_patches(column_side_effect=make_column):
                stack.enter_context(p)
            fn = wdm.create_workout_detail_modal(rows)

        fn(0)
        running_container = column_stubs[2]
        walking_container = column_stubs[3]
        hiking_container = column_stubs[4]
        assert not running_container._visible
        assert not walking_container._visible
        assert hiking_container._visible

    def test_hiking_container_uses_raw_activity_type(self) -> None:
        """Hiking container must use raw_activity_type, not the translated display label."""
        rows = [
            {
                **_make_row(
                    idx=0,
                    activity_type="Randonnée",  # translated display label
                    raw_activity_type="Hiking",  # raw Apple Health type (always English)
                ),
                "pace": "15:00 /km",
                "step_count": "8000",
                "elevation": "250 m",
                "splits": [],
            },
        ]
        column_stubs: list[_DummyElement] = []

        def make_column(*_a: Any, **_kw: Any) -> _DummyElement:
            col = _DummyElement()
            column_stubs.append(col)
            return col

        with ExitStack() as stack:
            for p in _all_patches(column_side_effect=make_column):
                stack.enter_context(p)
            fn = wdm.create_workout_detail_modal(rows)

        fn(0)
        hiking_container = column_stubs[4]
        assert hiking_container._visible  # must be shown despite translated label


class TestTabEnableState:
    """Tests for Activity and Splits tab enable/disable state."""

    def _make_tab_stubs(self) -> tuple[list[_DummyElement], Any]:
        """Return (tab_stubs list, tab_side_effect factory)."""
        tab_stubs: list[_DummyElement] = []

        def make_tab(*_a: Any, **_kw: Any) -> _DummyElement:
            tab = _DummyElement()
            tab_stubs.append(tab)
            return tab

        return tab_stubs, make_tab

    def test_activity_tab_disabled_for_unsupported_activity(self) -> None:
        """Activity tab should be disabled when no type-specific data is available."""
        rows = [_make_row(idx=0, activity_type="Cycling", raw_activity_type="Cycling")]
        tab_stubs, make_tab = self._make_tab_stubs()

        with ExitStack() as stack:
            for p in _all_patches(tab_side_effect=make_tab):
                stack.enter_context(p)
            fn = wdm.create_workout_detail_modal(rows)

        fn(0)
        assert not tab_stubs[1]._enabled

    def test_activity_tab_enabled_for_running(self) -> None:
        """Activity tab should be enabled for Running workouts."""
        rows = [
            {
                **_make_row(idx=0, activity_type="Running", raw_activity_type="Running"),
                "pace": "6:00 /km",
                "splits": [],
            }
        ]
        tab_stubs, make_tab = self._make_tab_stubs()

        with ExitStack() as stack:
            for p in _all_patches(tab_side_effect=make_tab):
                stack.enter_context(p)
            fn = wdm.create_workout_detail_modal(rows)

        fn(0)
        assert tab_stubs[1]._enabled

    def test_activity_tab_enabled_for_walking(self) -> None:
        """Activity tab should be enabled for Walking workouts."""
        rows = [
            {
                **_make_row(idx=0, activity_type="Walking", raw_activity_type="Walking"),
                "pace": "12:00 /km",
                "cadence": "110 spm",
                "step_length": "0.72 m",
                "step_count": "6500",
                "splits": [],
            }
        ]
        tab_stubs, make_tab = self._make_tab_stubs()

        with ExitStack() as stack:
            for p in _all_patches(tab_side_effect=make_tab):
                stack.enter_context(p)
            fn = wdm.create_workout_detail_modal(rows)

        fn(0)
        assert tab_stubs[1]._enabled

    def test_activity_tab_disabled_for_walking_with_no_data(self) -> None:
        """Activity tab should be disabled for a Walking workout with all fields missing."""
        rows = [_make_row(idx=0, activity_type="Walking", raw_activity_type="Walking")]
        tab_stubs, make_tab = self._make_tab_stubs()

        with ExitStack() as stack:
            for p in _all_patches(tab_side_effect=make_tab):
                stack.enter_context(p)
            fn = wdm.create_workout_detail_modal(rows)

        fn(0)
        assert not tab_stubs[1]._enabled

    def test_activity_tab_enabled_for_hiking(self) -> None:
        """Activity tab should be enabled for Hiking workouts with data."""
        rows = [
            {
                **_make_row(idx=0, activity_type="Hiking", raw_activity_type="Hiking"),
                "elevation": "250 m",
                "pace": "15:00 /km",
                "step_count": "8000",
                "splits": [],
            }
        ]
        tab_stubs, make_tab = self._make_tab_stubs()

        with ExitStack() as stack:
            for p in _all_patches(tab_side_effect=make_tab):
                stack.enter_context(p)
            fn = wdm.create_workout_detail_modal(rows)

        fn(0)
        assert tab_stubs[1]._enabled

    def test_activity_tab_disabled_for_hiking_with_no_data(self) -> None:
        """Activity tab should be disabled for a Hiking workout with all fields missing."""
        rows = [
            {
                **_make_row(idx=0, activity_type="Hiking", raw_activity_type="Hiking"),
                # Override all hiking-specific fields to the missing sentinel
                "elevation": "–",
                "pace": "–",
                "cadence": "–",
                "step_length": "–",
                "step_count": "–",
            }
        ]
        tab_stubs, make_tab = self._make_tab_stubs()

        with ExitStack() as stack:
            for p in _all_patches(tab_side_effect=make_tab):
                stack.enter_context(p)
            fn = wdm.create_workout_detail_modal(rows)

        fn(0)
        assert not tab_stubs[1]._enabled

    def test_splits_tab_disabled_when_no_route(self) -> None:
        """Intervals tab should be disabled when the workout has no GPS route and no swim laps."""
        rows = [_make_row(idx=0, activity_type="Running", raw_activity_type="Running")]
        tab_stubs, make_tab = self._make_tab_stubs()

        with ExitStack() as stack:
            for p in _all_patches(tab_side_effect=make_tab):
                stack.enter_context(p)
            fn = wdm.create_workout_detail_modal(rows)

        fn(0)
        assert not tab_stubs[3]._enabled

    def test_route_tab_disabled_when_no_route(self) -> None:
        """Route tab should be disabled when the workout has no GPS route."""
        rows = [_make_row(idx=0, activity_type="Running", raw_activity_type="Running")]
        tab_stubs, make_tab = self._make_tab_stubs()

        with ExitStack() as stack:
            for p in _all_patches(tab_side_effect=make_tab):
                stack.enter_context(p)
            fn = wdm.create_workout_detail_modal(rows)

        fn(0)
        assert not tab_stubs[2]._enabled

    def test_splits_tab_enabled_when_route_present(self) -> None:
        """Intervals tab should be enabled when the workout has a non-empty GPS route."""
        from datetime import timedelta

        import pandas as pd

        from logic.workout_manager.workout_route import RoutePoint, WorkoutRoute

        base_time = pd.Timestamp("2024-01-01 10:00:00").to_pydatetime()
        points = [
            RoutePoint(
                time=base_time + timedelta(seconds=i),
                latitude=0.0,
                longitude=0.0,
                altitude=100.0,
                speed=3.0,
            )
            for i in range(100)
        ]
        route = WorkoutRoute(points=points)
        rows = [
            {
                **_make_row(idx=0, activity_type="Running", raw_activity_type="Running"),
                "route": route,
                "splits": [],
            }
        ]
        tab_stubs, make_tab = self._make_tab_stubs()

        with ExitStack() as stack:
            for p in _all_patches(tab_side_effect=make_tab):
                stack.enter_context(p)
            fn = wdm.create_workout_detail_modal(rows)

        fn(0)
        assert tab_stubs[3]._enabled

    def test_route_tab_enabled_when_route_present(self) -> None:
        """Route tab should be enabled when the workout has a non-empty GPS route."""
        from datetime import timedelta

        import pandas as pd

        from logic.workout_manager.workout_route import RoutePoint, WorkoutRoute

        base_time = pd.Timestamp("2024-01-01 10:00:00").to_pydatetime()
        points = [
            RoutePoint(
                time=base_time + timedelta(seconds=i),
                latitude=0.0,
                longitude=0.0,
                altitude=100.0,
                speed=3.0,
            )
            for i in range(100)
        ]
        route = WorkoutRoute(points=points)
        rows = [
            {
                **_make_row(idx=0, activity_type="Running", raw_activity_type="Running"),
                "route": route,
                "splits": [],
            }
        ]
        tab_stubs, make_tab = self._make_tab_stubs()

        with ExitStack() as stack:
            for p in _all_patches(tab_side_effect=make_tab):
                stack.enter_context(p)
            fn = wdm.create_workout_detail_modal(rows)

        fn(0)
        assert tab_stubs[2]._enabled


class TestRowHasRoute:
    """Tests for the _row_has_route helper."""

    def test_returns_false_when_no_route_key(self) -> None:
        """Row without a 'route' key should return False."""
        assert not wdmc._row_has_route({})

    def test_returns_false_when_route_is_none(self) -> None:
        """Row with route=None should return False."""
        assert not wdmc._row_has_route({"route": None})

    def test_returns_false_for_empty_route(self) -> None:
        """Row with an empty WorkoutRoute should return False."""
        from logic.workout_manager.workout_route import WorkoutRoute

        assert not wdmc._row_has_route({"route": WorkoutRoute(points=[])})

    def test_returns_true_for_non_empty_route(self) -> None:
        """Row with a non-empty WorkoutRoute should return True."""
        from datetime import timedelta

        import pandas as pd

        from logic.workout_manager.workout_route import RoutePoint, WorkoutRoute

        base_time = pd.Timestamp("2024-01-01").to_pydatetime()
        points = [
            RoutePoint(
                time=base_time + timedelta(seconds=i),
                latitude=0.0,
                longitude=0.0,
                altitude=0.0,
                speed=1.0,
            )
            for i in range(5)
        ]
        assert wdmc._row_has_route({"route": WorkoutRoute(points=points)})


class TestGetRowRoutes:
    """Tests for the _get_row_routes helper."""

    def test_prefers_non_empty_route_parts_over_merged_route(self) -> None:
        """When route_parts is present, _get_row_routes returns only non-empty parts."""
        from datetime import timedelta

        import pandas as pd

        from logic.workout_manager.workout_route import RoutePoint, WorkoutRoute

        base_time = pd.Timestamp("2024-01-01").to_pydatetime()
        part = WorkoutRoute(
            points=[
                RoutePoint(
                    time=base_time + timedelta(seconds=i),
                    latitude=48.0 + (i * 0.0001),
                    longitude=2.0 + (i * 0.0001),
                    altitude=0.0,
                    speed=3.0,
                )
                for i in range(3)
            ]
        )
        merged_route = WorkoutRoute(points=[])
        routes = wdm._get_row_routes(
            {"route_parts": [WorkoutRoute(points=[]), part], "route": merged_route}
        )
        assert routes == [part]

    def test_falls_back_to_route_when_route_parts_missing(self) -> None:
        """_get_row_routes should return the merged route when route_parts is absent."""
        from datetime import timedelta

        import pandas as pd

        from logic.workout_manager.workout_route import RoutePoint, WorkoutRoute

        base_time = pd.Timestamp("2024-01-01").to_pydatetime()
        route = WorkoutRoute(
            points=[
                RoutePoint(
                    time=base_time + timedelta(seconds=i),
                    latitude=48.0 + (i * 0.0001),
                    longitude=2.0 + (i * 0.0001),
                    altitude=0.0,
                    speed=3.0,
                )
                for i in range(3)
            ]
        )
        routes = wdm._get_row_routes({"route": route})
        assert routes == [route]

    def test_falls_back_to_route_when_route_parts_is_empty_list(self) -> None:
        """_get_row_routes should return merged route when route_parts is empty."""
        from datetime import timedelta

        import pandas as pd

        from logic.workout_manager.workout_route import RoutePoint, WorkoutRoute

        base_time = pd.Timestamp("2024-01-01").to_pydatetime()
        route = WorkoutRoute(
            points=[
                RoutePoint(
                    time=base_time + timedelta(seconds=i),
                    latitude=48.0 + (i * 0.0001),
                    longitude=2.0 + (i * 0.0001),
                    altitude=0.0,
                    speed=3.0,
                )
                for i in range(3)
            ]
        )
        routes = wdm._get_row_routes({"route_parts": [], "route": route})
        assert routes == [route]


class TestRowHasActivityData:
    """Tests for the _row_has_activity_data helper."""

    def test_returns_false_for_cycling_with_no_data_fields(self) -> None:
        """Cycling row with no cycling-specific field values → False."""
        assert not wdm._row_has_activity_data({"raw_activity_type": "Cycling"})

    def test_returns_false_when_no_raw_activity_type(self) -> None:
        """Row without raw_activity_type key → False."""
        assert not wdm._row_has_activity_data({})

    def test_returns_false_for_walking_with_all_missing_fields(self) -> None:
        """Walking row where every field is '–' (absent from export) → False."""
        assert not wdm._row_has_activity_data(
            {
                "raw_activity_type": "Walking",
                "pace": "–",
                "cadence": "–",
                "step_length": "–",
                "step_count": "–",
            }
        )

    def test_returns_true_for_walking_with_any_data_field(self) -> None:
        """Walking row with at least one real field value → True."""
        assert wdm._row_has_activity_data(
            {
                "raw_activity_type": "Walking",
                "pace": "12:30 /km",
                "cadence": "–",
                "step_length": "–",
                "step_count": "–",
            }
        )

    def test_returns_false_for_running_with_all_missing_fields(self) -> None:
        """Running row where every field is '–' → False."""
        assert not wdm._row_has_activity_data({"raw_activity_type": "Running"})

    def test_returns_true_for_running_with_pace(self) -> None:
        """Running row with a pace value → True."""
        assert wdm._row_has_activity_data({"raw_activity_type": "Running", "pace": "5:30 /km"})

    def test_ignores_empty_string_values(self) -> None:
        """Empty string values are treated the same as '–' → False."""
        assert not wdm._row_has_activity_data(
            {"raw_activity_type": "Walking", "pace": "", "cadence": ""}
        )

    def test_returns_false_for_hiking_with_all_missing_fields(self) -> None:
        """Hiking row where every field is '–' (absent from export) → False."""
        assert not wdm._row_has_activity_data(
            {
                "raw_activity_type": "Hiking",
                "elevation": "–",
                "pace": "–",
                "cadence": "–",
                "step_length": "–",
                "step_count": "–",
            }
        )

    def test_returns_false_for_hiking_with_only_elevation(self) -> None:
        """Hiking row with only elevation data and all locomotion fields missing → False.

        Elevation is a generic field shown in the Overview tab and is NOT included
        in the schema-derived Activity tab enablement keys for Hiking.  The Activity
        tab is enabled only when locomotion statistics (pace, cadence, step length,
        or step count) are present.
        """
        assert not wdm._row_has_activity_data(
            {
                "raw_activity_type": "Hiking",
                "elevation": "250 m",
                "pace": "–",
                "cadence": "–",
                "step_length": "–",
                "step_count": "–",
            }
        )

    def test_returns_true_for_hiking_with_step_data(self) -> None:
        """Hiking row with a step count value → True."""
        assert wdm._row_has_activity_data(
            {
                "raw_activity_type": "Hiking",
                "elevation": "–",
                "pace": "–",
                "cadence": "–",
                "step_length": "–",
                "step_count": "8000",
            }
        )

    def test_returns_false_for_truly_unknown_activity(self) -> None:
        """A truly unknown activity type not in PER_TYPE_FIELDS → False."""
        assert not wdm._row_has_activity_data({"raw_activity_type": "Yoga"})

    def test_activity_field_keys_derived_from_schema(self) -> None:
        """_ACTIVITY_FIELD_KEYS must contain exactly the schema-registered activity types."""
        from logic.workout_detail_schema import PER_TYPE_FIELDS

        assert set(wdm._ACTIVITY_FIELD_KEYS.keys()) == set(PER_TYPE_FIELDS.keys())

    def test_activity_field_keys_use_schema_display_row_keys(self) -> None:
        """Every key in _ACTIVITY_FIELD_KEYS must appear as display_row_key in the schema."""
        from logic.workout_detail_schema import PER_TYPE_FIELDS

        for activity, keys in wdm._ACTIVITY_FIELD_KEYS.items():
            schema_keys = {
                f.display_row_key
                for f in PER_TYPE_FIELDS[activity]
                if f.display_row_key is not None
            }
            assert set(keys) == schema_keys, (
                f"'{activity}': _ACTIVITY_FIELD_KEYS {set(keys)} "
                f"≠ schema display_row_keys {schema_keys}"
            )


class TestDistanceFormatTwoDecimals:
    """Tests that distance is formatted with 2 decimal places."""

    def test_metric_distance_has_two_decimals(self) -> None:
        """Metric distances should show 2 decimal places."""
        from ui import workout_table as wt

        row = {"distance": 10000.0}  # 10 km
        _, display = wt._extract_distance_field(row, distance_unit="km")
        assert display == "10.00 km"

    def test_metric_distance_non_round_has_two_decimals(self) -> None:
        """Non-round metric distances should show 2 decimal places."""
        from ui import workout_table as wt

        row = {"distance": 5678.0}  # 5.678 km
        _, display = wt._extract_distance_field(row, distance_unit="km")
        assert display == "5.68 km"

    def test_imperial_distance_has_two_decimals(self) -> None:
        """Imperial distances should show 2 decimal places."""
        from ui import workout_table as wt
        from units import METERS_TO_MILES

        row = {"distance": 1609.344}  # exactly 1 mile
        _, display = wt._extract_distance_field(row, distance_unit="mi")
        expected = f"{1609.344 * METERS_TO_MILES:.2f} mi"
        assert display == expected


class TestCyclingFieldDisplay:
    """Tests for the _CYCLING_FIELD_DISPLAY constant and cycling section in the modal."""

    def test_all_expected_cycling_keys_present(self) -> None:
        """_CYCLING_FIELD_DISPLAY should include speed, cadence, power, and FTP."""
        keys = {key for key, _ in wdm._CYCLING_FIELD_DISPLAY}
        for expected in ["cycling_speed", "cycling_cadence", "cycling_power", "cycling_ftp"]:
            assert expected in keys

    def test_cycling_labels_are_non_empty_strings(self) -> None:
        """Every label in _CYCLING_FIELD_DISPLAY should be callable and non-empty."""
        for _key, label_fn in wdm._CYCLING_FIELD_DISPLAY:
            assert callable(label_fn)
            assert label_fn() and isinstance(label_fn(), str)


class TestCyclingActivityTabSection:
    """Tests for the cycling Activity tab container in the modal."""

    def test_cycling_container_visible_for_cycling_activity(self) -> None:
        """Cycling container should be visible when raw_activity_type is 'Cycling'."""
        rows = [
            {
                **_make_row(idx=0, activity_type="Cycling", raw_activity_type="Cycling"),
                "cycling_speed": "25.0 km/h",
                "cycling_cadence": "85 rpm",
                "cycling_power": "200 W",
                "splits": [],
            }
        ]
        column_stubs: list[_DummyElement] = []

        def make_column(*_a: Any, **_kw: Any) -> _DummyElement:
            col = _DummyElement()
            column_stubs.append(col)
            return col

        with ExitStack() as stack:
            for p in _all_patches(column_side_effect=make_column):
                stack.enter_context(p)
            fn = wdm.create_workout_detail_modal(rows)

        fn(0)
        # Column order includes centered wrappers: overview[0], activity[1], then
        # running[2], walking[3], hiking[4], swimming[5], cycling[6].
        cycling_container = column_stubs[6]
        assert cycling_container._visible

    def test_cycling_container_hidden_for_non_cycling_activity(self) -> None:
        """Cycling container should be hidden when raw_activity_type is not 'Cycling'."""
        rows = [_make_row(idx=0, activity_type="Running", raw_activity_type="Running")]
        column_stubs: list[_DummyElement] = []

        def make_column(*_a: Any, **_kw: Any) -> _DummyElement:
            col = _DummyElement()
            column_stubs.append(col)
            return col

        with ExitStack() as stack:
            for p in _all_patches(column_side_effect=make_column):
                stack.enter_context(p)
            fn = wdm.create_workout_detail_modal(rows)

        fn(0)
        cycling_container = column_stubs[6]
        assert not cycling_container._visible

    def test_activity_tab_enabled_for_cycling_with_data(self) -> None:
        """Activity tab should be enabled for Cycling workouts that have speed/cadence/power."""
        rows = [
            {
                **_make_row(idx=0, activity_type="Cycling", raw_activity_type="Cycling"),
                "cycling_speed": "25.0 km/h",
                "splits": [],
            }
        ]
        tab_stubs: list[_DummyElement] = []

        def make_tab(*_a: Any, **_kw: Any) -> _DummyElement:
            tab = _DummyElement()
            tab_stubs.append(tab)
            return tab

        with ExitStack() as stack:
            for p in _all_patches(tab_side_effect=make_tab):
                stack.enter_context(p)
            fn = wdm.create_workout_detail_modal(rows)

        fn(0)
        assert tab_stubs[1]._enabled

    def test_activity_tab_disabled_for_cycling_with_no_data(self) -> None:
        """Activity tab should be disabled for Cycling with no cycling-specific fields."""
        rows = [_make_row(idx=0, activity_type="Cycling", raw_activity_type="Cycling")]
        tab_stubs: list[_DummyElement] = []

        def make_tab(*_a: Any, **_kw: Any) -> _DummyElement:
            tab = _DummyElement()
            tab_stubs.append(tab)
            return tab

        with ExitStack() as stack:
            for p in _all_patches(tab_side_effect=make_tab):
                stack.enter_context(p)
            fn = wdm.create_workout_detail_modal(rows)

        fn(0)
        assert not tab_stubs[1]._enabled
