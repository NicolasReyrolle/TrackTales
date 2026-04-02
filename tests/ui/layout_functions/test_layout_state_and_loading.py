"""Focused tests for ui.layout state/scheduling/loading branches."""

from __future__ import annotations

import asyncio
from datetime import datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from app_state import state
from ui import layout

from ._helpers import DummyComponent, DummyContext, DummyTab, DummyTabs


class _FakeTask:
    """Minimal task-like object supporting done callbacks."""

    def __init__(self) -> None:
        self.callbacks: list[Any] = []

    def add_done_callback(self, callback: Any) -> None:
        """Add a callback to be called when the task is done."""
        self.callbacks.append(callback)


def test_schedule_best_segments_load_sets_and_clears_task() -> None:
    """Scheduling best segments should keep a task ref and clear it on completion."""
    original_task = state.best_segments_task
    fake_task = _FakeTask()

    def _fake_create_task(coro: Any) -> _FakeTask:
        coro.close()
        return fake_task

    try:
        with patch("ui.layout.asyncio.create_task", side_effect=_fake_create_task):
            layout.schedule_best_segments_load(force=True)

        assert state.best_segments_task is fake_task
        assert len(fake_task.callbacks) == 1

        fake_task.callbacks[0](fake_task)
        assert state.best_segments_task is None
    finally:
        state.best_segments_task = original_task


def test_schedule_health_data_load_sets_and_clears_task() -> None:
    """Scheduling health data should keep a task ref and clear it on completion."""
    original_task = state.health_data_task
    fake_task = _FakeTask()

    def _fake_create_task(coro: Any) -> _FakeTask:
        coro.close()
        return fake_task

    try:
        with patch("ui.layout.asyncio.create_task", side_effect=_fake_create_task):
            layout.schedule_health_data_load(force=True)

        assert state.health_data_task is fake_task
        assert len(fake_task.callbacks) == 1

        fake_task.callbacks[0](fake_task)
        assert state.health_data_task is None
    finally:
        state.health_data_task = original_task


def test_build_health_data_graphs_handles_empty_cp_evolution() -> None:
    """Health graph builders should emit correct data; CP/W' empty when evolution frame is empty."""
    original_records = state.records_by_type
    original_workouts = state.workouts

    records_mock = MagicMock()
    records_mock.heart_rate_stats.return_value = pd.DataFrame(
        {"period": [pd.Period("2025-01", freq="M")], "avg": [60.0]}
    )
    records_mock.weight_stats.return_value = pd.DataFrame(
        {"period": [pd.Period("2025-01", freq="M")], "avg": [70.5]}
    )
    records_mock.vo2_max_stats.return_value = pd.DataFrame(
        {"period": [pd.Period("2025-01", freq="M")], "avg": [50.1]}
    )
    records_mock.get.return_value = pd.DataFrame()

    workouts_mock = MagicMock()
    workouts_mock.get_critical_power_evolution.return_value = pd.DataFrame(
        columns=["period", "critical_power_w", "w_prime_kj"]
    )

    try:
        state.records_by_type = records_mock
        state.workouts = workouts_mock

        fast_graphs = layout._build_fast_health_graphs()
        assert fast_graphs["heart_rate"] == {"2025-01": 60.0}
        assert fast_graphs["body_mass"] == {"2025-01": 70.5}
        assert fast_graphs["vo2_max"] == {"2025-01": 50.1}

        cp_graphs = layout._build_cp_graphs()
        assert not cp_graphs["critical_power"]
        assert not cp_graphs["w_prime"]
    finally:
        state.records_by_type = original_records
        state.workouts = original_workouts


@pytest.mark.asyncio
async def test_load_health_data_success_and_exception_paths() -> None:
    """load_health_data should set flags on success and recover cleanly on exception."""
    original_loading = state.health_data_loading
    original_loaded = state.health_data_loaded
    original_file_loaded = state.file_loaded
    original_graphs = state.health_data_graphs

    try:
        state.health_data_loading = False
        state.health_data_loaded = False
        state.file_loaded = True
        state.health_data_graphs = {}

        with patch("ui.layout.render_health_data_tab.refresh") as refresh_mock:
            with patch(
                "ui.layout.asyncio.to_thread", new=AsyncMock(return_value={"heart_rate": {}})
            ):
                await layout.load_health_data(force=True)

        assert state.health_data_loaded is True
        assert state.health_data_loading is False
        assert refresh_mock.call_count == 3

        state.health_data_loaded = False
        with patch("ui.layout.render_health_data_tab.refresh") as refresh_mock:
            with patch("ui.layout._logger.exception") as exception_mock:
                with patch(
                    "ui.layout.asyncio.to_thread", new=AsyncMock(side_effect=RuntimeError("boom"))
                ):
                    await layout.load_health_data(force=True)

        exception_mock.assert_called_once()
        assert state.health_data_loaded is False
        assert state.health_data_loading is False
        assert refresh_mock.call_count == 2
    finally:
        state.health_data_loading = original_loading
        state.health_data_loaded = original_loaded
        state.file_loaded = original_file_loaded
        state.health_data_graphs = original_graphs


@pytest.mark.asyncio
async def test_load_health_data_early_return_guards() -> None:
    """load_health_data should return early for loading/loaded/not-file-loaded guards."""
    original_loading = state.health_data_loading
    original_loaded = state.health_data_loaded
    original_file_loaded = state.file_loaded

    try:
        with patch("ui.layout.render_health_data_tab.refresh") as refresh_mock:
            state.health_data_loading = True
            state.health_data_loaded = False
            state.file_loaded = True
            await layout.load_health_data(force=True)
            refresh_mock.assert_not_called()

            state.health_data_loading = False
            state.health_data_loaded = True
            state.file_loaded = True
            await layout.load_health_data(force=False)
            refresh_mock.assert_not_called()

            state.health_data_loading = False
            state.health_data_loaded = False
            state.file_loaded = False
            await layout.load_health_data(force=True)
            refresh_mock.assert_not_called()
    finally:
        state.health_data_loading = original_loading
        state.health_data_loaded = original_loaded
        state.file_loaded = original_file_loaded


def test_refresh_summary_metrics_updates_values_and_display() -> None:
    """Summary refresh should populate both raw metrics and formatted display values."""
    original_workouts = state.workouts
    original_metrics = dict(state.metrics)
    original_display = dict(state.metrics_display)
    original_activity = state.selected_activity_type

    workouts_mock = MagicMock()
    workouts_mock.get_count.return_value = 7
    workouts_mock.get_total_distance.return_value = 42.0
    workouts_mock.get_total_duration.return_value = 3.5
    workouts_mock.get_total_elevation.return_value = 1.2
    workouts_mock.get_total_calories.return_value = 1234

    try:
        state.workouts = workouts_mock
        state.selected_activity_type = "Running"

        layout._refresh_summary_metrics()  # type: ignore[attr-defined]

        assert state.metrics["count"] == 7
        assert state.metrics["distance"] == pytest.approx(42.0)  # type: ignore[arg-type]
        assert state.metrics["duration"] == pytest.approx(3.5)  # type: ignore[arg-type]
        assert state.metrics["elevation"] == pytest.approx(1.2)  # type: ignore[arg-type]
        assert state.metrics["calories"] == 1234
        assert state.metrics_display["count"] == "7"
    finally:
        state.workouts = original_workouts
        state.metrics = original_metrics
        state.metrics_display = original_display
        state.selected_activity_type = original_activity


def test_set_longest_metric_from_details_branches() -> None:
    """Longest-workout helper should handle no details and invalid numeric payloads."""
    original_metrics = dict(state.metrics)
    original_display = dict(state.metrics_display)
    original_tooltip = dict(state.metrics_tooltip)

    try:
        layout._set_longest_metric_from_details(  # type: ignore[attr-defined]
            "longest_run", None, "en"
        )
        assert state.metrics_tooltip["longest_run"] == "No data"

        details = {
            "distance": "bad",
            "date": datetime(2025, 2, 3),
            "duration": "oops",
        }
        layout._set_longest_metric_from_details(  # type: ignore[attr-defined]
            "longest_run", details, "en"
        )
        assert state.metrics["longest_run"] == pytest.approx(0.0)  # type: ignore[arg-type]
        assert state.metrics_display["longest_run"] == "0.0"
        assert state.metrics_tooltip["longest_run"] == "02/03/2025"

        duration_only = {"distance": 12.3, "duration": 3661}
        layout._set_longest_metric_from_details(  # type: ignore[attr-defined]
            "longest_run", duration_only, "en"
        )
        assert state.metrics_tooltip["longest_run"] == "1 h 01 min 01 s"

        no_date_no_duration = {"distance": 1.0}
        layout._set_longest_metric_from_details(  # type: ignore[attr-defined]
            "longest_run", no_date_no_duration, "en"
        )
        assert state.metrics_tooltip["longest_run"] == "No data"
    finally:
        state.metrics = original_metrics
        state.metrics_display = original_display
        state.metrics_tooltip = original_tooltip


def test_refresh_longest_workout_metrics_uses_expected_activity_groups() -> None:
    """Longest metrics refresh should query expected activity groups and map results."""
    original_workouts = state.workouts

    workouts_mock = MagicMock()
    workouts_mock.get_longest_workout_details.side_effect = [
        {"distance": 12.0, "date": datetime(2025, 1, 1), "duration": 3600},
        None,
        {"distance": 40.0, "date": datetime(2025, 1, 2), "duration": 5400},
    ]

    try:
        state.workouts = workouts_mock
        with patch("ui.layout.get_language", return_value="en"):
            layout._refresh_longest_workout_metrics()  # type: ignore[attr-defined]

        calls = workouts_mock.get_longest_workout_details.call_args_list
        assert calls[0].args[0] == ["Running"]
        assert calls[1].args[0] == ["Walking", "Hiking"]
        assert calls[2].args[0] == ["Cycling"]
    finally:
        state.workouts = original_workouts


def test_render_activity_select_wires_binding_and_callback() -> None:
    """render_activity_select should wire options, callback and state binding."""
    select_component = DummyComponent()

    with (
        patch("ui.layout.ui.select", return_value=select_component) as select_mock,
        patch("ui.layout.build_activity_select_options", return_value={"All": "All"}),
    ):
        layout.render_activity_select.func()

    assert select_mock.call_count == 1
    kwargs = select_mock.call_args.kwargs
    assert kwargs["on_change"] is layout.refresh_data


@pytest.mark.asyncio
async def test_reset_state_helpers_cancel_inflight_tasks() -> None:
    """Reset helpers should cancel in-flight tasks and reset cached state."""
    best_task = asyncio.create_task(asyncio.sleep(60))
    health_task = asyncio.create_task(asyncio.sleep(60))

    original_best_task = state.best_segments_task
    original_best_loading = state.best_segments_loading
    original_best_rows = list(state.best_segments_rows)
    original_best_loaded = state.best_segments_loaded

    original_health_task = state.health_data_task
    original_health_loading = state.health_data_loading
    original_health_loaded = state.health_data_loaded
    original_health_graphs = dict(state.health_data_graphs)

    try:
        state.best_segments_task = best_task
        state.best_segments_loading = True
        state.best_segments_rows = [{"id": "x"}]
        state.best_segments_loaded = True

        state.health_data_task = health_task
        state.health_data_loading = True
        state.health_data_loaded = True
        state.health_data_graphs = {"heart_rate": {"2025-01": 60.0}}

        layout._reset_best_segments_state()  # type: ignore[attr-defined]
        layout._reset_health_data_state()  # type: ignore[attr-defined]

        await asyncio.sleep(0)
        assert best_task.cancelled()
        assert health_task.cancelled()

        assert state.best_segments_task is None
        assert state.best_segments_loading is False
        assert not state.best_segments_rows
        assert state.best_segments_loaded is False

        assert state.health_data_task is None
        assert state.health_data_loading is False
        assert state.health_data_loaded is False
        assert state.health_data_graphs["heart_rate"] == {}
    finally:
        state.best_segments_task = original_best_task
        state.best_segments_loading = original_best_loading
        state.best_segments_rows = original_best_rows
        state.best_segments_loaded = original_best_loaded

        state.health_data_task = original_health_task
        state.health_data_loading = original_health_loading
        state.health_data_loaded = original_health_loaded
        state.health_data_graphs = original_health_graphs


def test_refresh_data_schedules_load_for_selected_tab() -> None:
    """refresh_data should only schedule deferred loading for the active tab."""
    original_selected_tab = state.selected_main_tab

    try:
        with patch("ui.layout._refresh_summary_metrics"):
            with patch("ui.layout._refresh_longest_workout_metrics"):
                with patch("ui.layout._reset_best_segments_state"):
                    with patch("ui.layout._reset_health_data_state"):
                        with patch("ui.layout.render_activity_graphs.refresh"):
                            with patch("ui.layout.render_trends_graphs.refresh"):
                                with patch("ui.layout.render_health_data_tab.refresh"):
                                    with patch("ui.layout.render_best_segments_tab.refresh"):
                                        with patch(
                                            "ui.layout.render_distance_range_selector.refresh"
                                        ):
                                            with patch(
                                                "ui.layout.render_duration_range_selector.refresh"
                                            ):
                                                with patch(
                                                    "ui.layout.render_workout_table.refresh"
                                                ):
                                                    with patch(
                                                        "ui.layout.schedule_best_segments_load"
                                                    ) as best_mock:
                                                        with patch(
                                                            "ui.layout.schedule_health_data_load"
                                                        ) as health_mock:
                                                            state.selected_main_tab = (
                                                                "best_segments"
                                                            )
                                                            layout.refresh_data()
                                                            best_mock.assert_called_once()
                                                            health_mock.assert_not_called()

                                                            best_mock.reset_mock()
                                                            health_mock.reset_mock()
                                                            state.selected_main_tab = "health_data"
                                                            layout.refresh_data()
                                                            health_mock.assert_called_once()
                                                            best_mock.assert_not_called()
    finally:
        state.selected_main_tab = original_selected_tab


def test_render_left_drawer_renders_export_actions() -> None:
    """Left drawer should include both JSON and CSV export actions."""
    with (
        patch("ui.layout.ui.left_drawer", return_value=DummyContext()),
        patch("ui.layout.ui.label", return_value=DummyContext()),
        patch("ui.layout.render_activity_select") as activity_mock,
        patch("ui.layout.render_date_range_selector") as date_mock,
        patch("ui.layout.render_period_selector") as period_mock,
        patch("ui.layout.ui.separator"),
        patch("ui.layout.ui.dropdown_button", return_value=DummyContext()),
        patch("ui.layout.ui.button", return_value=DummyContext()) as button_mock,
    ):
        layout.render_left_drawer()

    activity_mock.assert_called_once()
    date_mock.assert_called_once()
    period_mock.assert_called_once()
    labels = [call.args[0] for call in button_mock.call_args_list if call.args]
    assert "to JSON" in labels
    assert "to CSV" in labels


@pytest.mark.asyncio
async def test_pick_file_notifies_or_sets_input_value() -> None:
    """pick_file should notify when no file selected and update state when selected."""
    had_input_file = hasattr(state, "input_file")
    original_input = getattr(state, "input_file", None)
    state.input_file = SimpleNamespace(value="")  # type: ignore[assignment]

    try:
        with patch("ui.layout.LocalFilePicker", new=AsyncMock(return_value=[])):
            with patch("ui.layout.ui.notify") as notify_mock:
                await layout.pick_file()
        notify_mock.assert_called_once_with("No file selected")

        with patch("ui.layout.LocalFilePicker", new=AsyncMock(return_value=["C:/x.zip"])):
            await layout.pick_file()
        assert state.input_file.value == "C:/x.zip"
    finally:
        if had_input_file:
            state.input_file = original_input  # type: ignore[assignment]
        else:
            delattr(state, "input_file")


@pytest.mark.asyncio
async def test_load_file_guards_success_and_error() -> None:
    """load_file should handle guard conditions, success path, and parse errors."""
    had_input_file = hasattr(state, "input_file")
    original_input = getattr(state, "input_file", None)
    original_loading = state.loading
    original_status = state.loading_status
    original_file_loaded = state.file_loaded
    original_activity_options = list(state.activity_options)
    original_workouts = state.workouts
    original_records = state.records_by_type
    original_distance_range = dict(state.distance_range_km)
    original_duration_range = dict(state.duration_range_min)

    state.input_file = SimpleNamespace(value="")  # type: ignore[assignment]
    state.loading = False
    state.loading_status = ""
    state.file_loaded = False

    try:
        with patch("ui.layout.ui.notify") as notify_mock:
            await layout.load_file()
        notify_mock.assert_called_once_with("Please select an Apple Health export file first.")

        state.input_file.value = "C:/export.zip"
        state.loading = True
        with patch("ui.layout.asyncio.to_thread", new=AsyncMock()) as thread_mock:
            await layout.load_file()
        thread_mock.assert_not_called()

        state.loading = False
        workouts = MagicMock()
        records = MagicMock()

        def _to_thread_success(_func: Any, _path: str, progress_callback: Any) -> Any:
            """Simulate successful file loading with progress callback."""
            progress_callback(55, "Building")
            assert state.loading_status.startswith("55% -")
            return workouts, ["All", "Running"], records

        fake_loop = SimpleNamespace(
            call_soon_threadsafe=lambda callback: callback()  # type: ignore[arg-type]
        )

        with patch("ui.layout.asyncio.get_running_loop", return_value=fake_loop):
            with patch(
                "ui.layout.asyncio.to_thread", new=AsyncMock(side_effect=_to_thread_success)
            ):
                with patch("ui.layout.render_activity_select.refresh") as activity_refresh:
                    with patch("ui.layout.render_date_range_selector.refresh") as date_refresh:
                        with patch("ui.layout.refresh_data") as refresh_data_mock:
                            with patch("ui.layout.ui.notify") as notify_mock:
                                await layout.load_file()

        assert state.workouts is workouts
        assert state.records_by_type is records
        assert state.file_loaded is True
        assert state.activity_options == ["All", "Running"]
        activity_refresh.assert_called_once()
        date_refresh.assert_called_once()
        refresh_data_mock.assert_called_once()
        notify_mock.assert_called_once_with("File parsed successfully.")
        assert state.loading is False
        assert state.loading_status == ""

        state.loading = False
        with patch(
            "ui.layout.asyncio.to_thread", new=AsyncMock(side_effect=RuntimeError("bad zip"))
        ):
            with patch("ui.layout.ui.notify") as notify_mock:
                await layout.load_file()

        notify_mock.assert_called_once()
        message = notify_mock.call_args.args[0]
        assert "Error parsing file:" in message
        assert state.loading is False
        assert state.loading_status == ""
    finally:
        if had_input_file:
            state.input_file = original_input  # type: ignore[assignment]
        else:
            delattr(state, "input_file")
        state.loading = original_loading
        state.loading_status = original_status
        state.file_loaded = original_file_loaded
        state.activity_options = original_activity_options
        state.workouts = original_workouts
        state.records_by_type = original_records
        state.distance_range_km = original_distance_range
        state.duration_range_min = original_duration_range


def test_render_period_selector_period_change_schedules_health_load_on_health_tab() -> None:
    """Changing trends period should schedule health-data reload when health tab is active."""
    original_tab = state.selected_main_tab

    class _DummyRadio:
        def __init__(self, _options: dict[str, str], on_change: Any = None) -> None:
            self.on_change = on_change

        def bind_value(self, *_args: Any, **_kwargs: Any) -> _DummyRadio:
            """Simulate binding that returns self for chaining."""
            return self

        def props(self, *_args: Any, **_kwargs: Any) -> _DummyRadio:
            """Simulate setting props that returns self for chaining."""
            return self

    radios: list[_DummyRadio] = []

    def _radio_factory(options: dict[str, str], on_change: Any = None) -> _DummyRadio:
        radio = _DummyRadio(options, on_change)
        radios.append(radio)
        return radio

    try:
        state.selected_main_tab = "health_data"
        with patch("ui.layout.ui.label"):
            with patch("ui.layout.ui.radio", side_effect=_radio_factory):
                with patch("ui.layout.render_trends_graphs") as render_trends_graphs_mock:
                    with patch("ui.layout.render_health_data_tab") as render_health_data_tab_mock:
                        with patch("ui.layout._reset_health_data_state"):
                            with patch("ui.layout.schedule_health_data_load") as schedule_mock:
                                layout.render_period_selector()
                                radios[0].on_change()

        render_trends_graphs_mock.refresh.assert_called_once()
        render_health_data_tab_mock.refresh.assert_called_once()
        schedule_mock.assert_called_once()
    finally:
        state.selected_main_tab = original_tab


def test_render_body_health_data_tab_change_schedules_load() -> None:
    """Switching to the health_data tab should schedule health-data loading."""
    tabs_created: list[DummyTabs] = []
    fake_app = SimpleNamespace(storage=SimpleNamespace(user={"input_file_path": ""}))

    def _tabs_factory(on_change: Any = None) -> DummyTabs:
        tabs = DummyTabs(on_change=on_change)
        tabs_created.append(tabs)
        return tabs

    with (
        patch("ui.layout.ui.row", return_value=DummyContext()),
        patch("ui.layout.ui.input", return_value=DummyComponent()),
        patch("ui.layout.ui.button", return_value=DummyComponent()),
        patch("ui.layout.ui.spinner", return_value=DummyComponent()),
        patch("ui.layout.ui.label", return_value=DummyComponent()),
        patch("ui.layout.app", fake_app),
        patch("ui.layout.ui.tabs", side_effect=_tabs_factory),
        patch(
            "ui.layout.ui.tab",
            side_effect=lambda name, _label: DummyTab(name),  # type: ignore[arg-type]
        ),
        patch("ui.layout.ui.tab_panels", return_value=DummyContext()),
        patch("ui.layout.ui.tab_panel", return_value=DummyContext()),
        patch("ui.layout.stat_card"),
        patch("ui.layout.render_activity_graphs"),
        patch("ui.layout.render_trends_tab"),
        patch("ui.layout.render_health_data_tab"),
        patch("ui.layout.render_best_segments_tab"),
        patch("ui.layout.render_workout_table"),
        patch("ui.layout.render_distance_range_selector"),
        patch("ui.layout.render_duration_range_selector"),
        patch("ui.layout.schedule_health_data_load") as health_load_mock,
    ):
        layout.render_body()
        on_change = tabs_created[0].on_change
        on_change(SimpleNamespace(value=SimpleNamespace(name="health_data")))

    health_load_mock.assert_called_once()


def test_render_header_builds_language_menu_items() -> None:
    """Header should create one language menu item per LANGUAGES entry."""

    class _DummyDarkMode:
        def __init__(self) -> None:
            self.value = False

        def enable(self) -> None:
            """Simulate enabling dark mode."""
            self.value = True

        def disable(self) -> None:
            """Simulate disabling dark mode."""
            self.value = False

    class _DummyButton(DummyComponent):
        def __init__(self, context: bool = False) -> None:
            self._context = context

        def __enter__(self) -> _DummyButton:
            return self

        def __exit__(self, *_args: Any) -> None:
            """Exit method that does nothing."""
            pass

    def _button_factory(*_args: Any, **kwargs: Any) -> _DummyButton:
        return _DummyButton(context=kwargs.get("icon") == "language")

    with (
        patch("ui.layout.ui.dark_mode", return_value=_DummyDarkMode()),
        patch("ui.layout.ui.header", return_value=DummyContext()),
        patch("ui.layout.ui.image", return_value=DummyComponent()),
        patch("ui.layout.ui.label", return_value=DummyComponent()),
        patch("ui.layout.ui.button", side_effect=_button_factory),
        patch("ui.layout.ui.menu", return_value=DummyContext()),
        patch("ui.layout.ui.menu_item") as menu_item_mock,
        patch("ui.layout.LANGUAGES", {"en": "English", "fr": "Français"}),
    ):
        layout.render_header()

    assert menu_item_mock.call_count == 2
