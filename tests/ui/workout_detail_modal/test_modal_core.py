"""Tests for ui.workout_detail_modal — field display constants and modal lifecycle."""

from __future__ import annotations

import asyncio
from contextlib import ExitStack
from typing import Any
from unittest.mock import patch

import pandas as pd
import pytest

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

    def test_profile_tab_enabled_when_workout_has_hr_but_no_route(self) -> None:
        """Charts tab should be enabled for non-GPS workouts when HR samples exist."""
        from app_state import state
        from logic.records_by_type import RecordsByType

        original_records = state.records_by_type
        tabs_created: list[_DummyElement] = []

        def make_tab(*_a: Any, **_kw: Any) -> _DummyElement:
            tab = _DummyElement()
            tabs_created.append(tab)
            return tab

        row = {
            **_make_row(idx=0),
            "route": None,
            "workout_start_utc": pd.Timestamp("2025-01-02 10:00:00"),
            "workout_end_utc": pd.Timestamp("2025-01-02 10:10:00"),
        }
        heart_rate_df = pd.DataFrame(
            [
                {"startDate": "2025-01-02 10:00:10+00:00", "value": 141},
                {"startDate": "2025-01-02 10:04:50+00:00", "value": 149},
            ]
        )

        try:
            state.records_by_type = RecordsByType(data={"HeartRate": heart_rate_df})
            with ExitStack() as stack:
                for p in _all_patches(tab_side_effect=make_tab):
                    stack.enter_context(p)
                fn = wdm.create_workout_detail_modal([row])
            fn(0)
        finally:
            state.records_by_type = original_records

        route_tab = tabs_created[2]
        profile_tab = tabs_created[3]
        assert route_tab._enabled is False
        assert profile_tab._enabled is True

    def test_route_tab_change_triggers_route_refresh(self) -> None:
        """Switching to the Route tab should trigger Route-tab refresh."""
        from datetime import timedelta

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
                    "ui.workout_detail_modal.builder._do_refresh_route_tab",
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
                    "ui.workout_detail_modal.builder._do_refresh_route_profile_tab",
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
        """Charts refresh should mutate chart options in place (NiceGUI options has no setter)."""
        from datetime import timedelta

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
        assert profile_data[0][1] == pytest.approx(35.0)

    def test_do_refresh_profile_tab_uses_imperial_units(self) -> None:
        """Charts refresh should convert route chart labels/data when distance_unit is miles."""
        from datetime import timedelta

        from logic.workout_manager.workout_route import RoutePoint, WorkoutRoute
        from units import METERS_PER_KM, METERS_TO_FEET, METERS_TO_MILES

        class _ReadOnlyChart:
            def __init__(self) -> None:
                self._visible = True
                self._options_store: dict[str, Any] = {}

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
                    time=base_time + timedelta(seconds=i * 10),
                    latitude=48.85 + (i * 0.0001),
                    longitude=2.35 + (i * 0.0001),
                    altitude=100.0 + i,
                    speed=3.0,
                )
                for i in range(3)
            ]
        )
        row = {**_make_row(idx=0), "route": route, "distance_unit": "mi"}
        no_route_label = _DummyElement()
        route_profile_chart = _ReadOnlyChart()

        wdm._do_refresh_route_profile_tab(no_route_label, route_profile_chart, row)

        config = route_profile_chart.options
        profile_data = config["series"][0]["data"]
        km_to_miles = METERS_TO_MILES * METERS_PER_KM
        assert config["xAxis"]["name"].endswith("(mi)")
        assert config["yAxis"][0]["name"].endswith("(ft)")
        assert config["yAxis"][1]["name"].endswith("(/mi)")
        assert profile_data[0][1] == pytest.approx(100.0 * METERS_TO_FEET)
        assert profile_data[1][0] > 0
        assert profile_data[1][0] < 1
        assert profile_data[1][3] == pytest.approx(3.0 * 3.6 * km_to_miles)

    def test_do_refresh_heart_rate_profile_tab_shows_chart_without_route(self) -> None:
        """Standalone heart-rate chart should render even when the workout has no route."""
        from app_state import state
        from logic.records_by_type import RecordsByType
        from ui.workout_detail_modal import builder as wdm_builder

        class _ReadOnlyChart:
            def __init__(self) -> None:
                self._visible = True
                self._options_store: dict[str, Any] = {}

            @property
            def options(self) -> dict[str, Any]:
                return self._options_store

            def set_visibility(self, visible: bool) -> None:
                self._visible = visible

            def update(self) -> None:
                return

        original_records = state.records_by_type
        no_hr_label = _DummyElement()
        heart_rate_chart = _ReadOnlyChart()
        row = {
            **_make_row(idx=0),
            "route": None,
            "workout_start_utc": pd.Timestamp("2025-01-02 10:00:00"),
            "workout_end_utc": pd.Timestamp("2025-01-02 10:10:00"),
        }
        heart_rate_df = pd.DataFrame(
            [
                {"startDate": "2025-01-02 10:00:10+00:00", "value": 141},
                {"startDate": "2025-01-02 10:04:50+00:00", "value": 149},
            ]
        )

        try:
            state.records_by_type = RecordsByType(data={"HeartRate": heart_rate_df})
            wdm_builder._do_refresh_heart_rate_profile_tab(no_hr_label, heart_rate_chart, row)
        finally:
            state.records_by_type = original_records

        assert no_hr_label._visible is False
        assert heart_rate_chart._visible is True
        assert heart_rate_chart.options["backgroundColor"] == "transparent"
        assert heart_rate_chart.options["xAxis"]["name"].endswith("(min)")
        assert len(heart_rate_chart.options["series"][0]["data"]) == 2

    def test_do_refresh_heart_rate_profile_tab_uses_distance_with_route(self) -> None:
        """Standalone HR chart should use distance X-axis when route points exist."""
        from app_state import state
        from logic.records_by_type import RecordsByType
        from logic.workout_manager.workout_route import RoutePoint, WorkoutRoute
        from ui.workout_detail_modal import builder as wdm_builder

        class _ReadOnlyChart:
            def __init__(self) -> None:
                self._visible = True
                self._options_store: dict[str, Any] = {}

            @property
            def options(self) -> dict[str, Any]:
                return self._options_store

            def set_visibility(self, visible: bool) -> None:
                self._visible = visible

            def update(self) -> None:
                return

        base_time = pd.Timestamp("2025-01-02 10:00:00+00:00")
        route = WorkoutRoute(
            points=[
                RoutePoint(
                    time=base_time.to_pydatetime(),
                    latitude=48.85,
                    longitude=2.35,
                    altitude=100.0,
                    speed=3.0,
                ),
                RoutePoint(
                    time=(base_time + pd.Timedelta(seconds=60)).to_pydatetime(),
                    latitude=48.851,
                    longitude=2.351,
                    altitude=101.0,
                    speed=3.1,
                ),
            ]
        )

        original_records = state.records_by_type
        no_hr_label = _DummyElement()
        heart_rate_chart = _ReadOnlyChart()
        row = {
            **_make_row(idx=0),
            "route": route,
            "workout_start_utc": base_time,
            "workout_end_utc": base_time + pd.Timedelta(minutes=10),
            "distance_unit": "km",
        }
        heart_rate_df = pd.DataFrame(
            [
                {"startDate": "2025-01-02 10:00:10+00:00", "value": 141},
                {"startDate": "2025-01-02 10:01:00+00:00", "value": 149},
            ]
        )

        try:
            state.records_by_type = RecordsByType(data={"HeartRate": heart_rate_df})
            wdm_builder._do_refresh_heart_rate_profile_tab(no_hr_label, heart_rate_chart, row)
        finally:
            state.records_by_type = original_records

        assert no_hr_label._visible is False
        assert heart_rate_chart._visible is True
        assert heart_rate_chart.options["xAxis"]["name"].endswith("(km)")
        assert heart_rate_chart.options["series"][0]["type"] == "line"
