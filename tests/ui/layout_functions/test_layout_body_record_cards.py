"""Tests for workout detail interactions in the layout body."""

from __future__ import annotations

from contextlib import ExitStack
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app_state import state
from ui import layout

from ._helpers import DummyComponent, DummyContext, DummyTab, DummyTabs


def test_render_body_record_card_click_opens_detail_modal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Clicking a record card should open the workout detail modal at that workout."""
    fake_app = SimpleNamespace(storage=SimpleNamespace(user={"input_file_path": ""}))
    stat_card_calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    original_record_indexes = dict(state.metrics_workout_index)

    def _capture_stat_card(*_args: Any, **kwargs: Any) -> None:
        stat_card_calls.append((_args, kwargs))

    try:
        state.metrics_workout_index["longest_run"] = 42
        monkeypatch.setattr(layout, "render_best_segments_tab", MagicMock())
        with ExitStack() as stack:
            stack.enter_context(patch("ui.layout.ui.row", return_value=DummyContext()))
            stack.enter_context(patch("ui.layout.ui.input", return_value=DummyComponent()))
            stack.enter_context(patch("ui.layout.ui.button", return_value=DummyComponent()))
            stack.enter_context(patch("ui.layout.ui.spinner", return_value=DummyComponent()))
            stack.enter_context(patch("ui.layout.ui.label", return_value=DummyComponent()))
            stack.enter_context(patch("ui.layout.app", fake_app))
            stack.enter_context(patch("ui.layout.ui.tabs", return_value=DummyTabs()))
            stack.enter_context(
                patch(
                    "ui.layout.ui.tab",
                    side_effect=lambda name, _label: DummyTab(name),  # type: ignore[arg-type]
                )
            )
            stack.enter_context(patch("ui.layout.ui.tab_panels", return_value=DummyContext()))
            stack.enter_context(patch("ui.layout.ui.tab_panel", return_value=DummyContext()))
            stack.enter_context(patch("ui.layout.stat_card", side_effect=_capture_stat_card))
            stack.enter_context(patch("ui.layout.render_activity_graphs"))
            stack.enter_context(patch("ui.layout.render_trends_tab"))
            stack.enter_context(patch("ui.layout.render_health_data_tab"))
            stack.enter_context(patch("ui.layout.render_running_tab"))
            stack.enter_context(patch("ui.layout.render_workout_table"))
            stack.enter_context(patch("ui.layout.render_distance_range_selector"))
            stack.enter_context(patch("ui.layout.render_duration_range_selector"))
            build_rows_mock = stack.enter_context(
                patch("ui.layout._build_workout_rows", return_value=[{"workout_index": 42}])
            )
            create_modal_mock = stack.enter_context(patch("ui.layout.create_workout_detail_modal"))
            open_detail_mock = MagicMock()
            create_modal_mock.return_value = open_detail_mock
            layout.render_body()

            longest_run_call = next(
                (call for call in stat_card_calls if call[0][2] == "longest_run"),
                None,
            )
            assert longest_run_call is not None
            on_click = longest_run_call[1].get("on_click")
            assert callable(on_click)
            on_click()
            build_rows_mock.assert_called_once_with(
                activity_type="All",
                skip_range_filters=True,
            )
            open_detail_mock.assert_called_once_with(0)
    finally:
        state.metrics_workout_index = original_record_indexes


def test_render_body_record_card_click_no_workout_index_is_noop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Record-card click should no-op when no workout index is available."""
    fake_app = SimpleNamespace(storage=SimpleNamespace(user={"input_file_path": ""}))
    stat_card_calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    original_record_indexes = dict(state.metrics_workout_index)

    def _capture_stat_card(*_args: Any, **kwargs: Any) -> None:
        stat_card_calls.append((_args, kwargs))

    try:
        state.metrics_workout_index["longest_run"] = None
        monkeypatch.setattr(layout, "render_best_segments_tab", MagicMock())
        with ExitStack() as stack:
            stack.enter_context(patch("ui.layout.ui.row", return_value=DummyContext()))
            stack.enter_context(patch("ui.layout.ui.input", return_value=DummyComponent()))
            stack.enter_context(patch("ui.layout.ui.button", return_value=DummyComponent()))
            stack.enter_context(patch("ui.layout.ui.spinner", return_value=DummyComponent()))
            stack.enter_context(patch("ui.layout.ui.label", return_value=DummyComponent()))
            stack.enter_context(patch("ui.layout.app", fake_app))
            stack.enter_context(patch("ui.layout.ui.tabs", return_value=DummyTabs()))
            stack.enter_context(
                patch(
                    "ui.layout.ui.tab",
                    side_effect=lambda name, _label: DummyTab(name),  # type: ignore[arg-type]
                )
            )
            stack.enter_context(patch("ui.layout.ui.tab_panels", return_value=DummyContext()))
            stack.enter_context(patch("ui.layout.ui.tab_panel", return_value=DummyContext()))
            stack.enter_context(patch("ui.layout.stat_card", side_effect=_capture_stat_card))
            stack.enter_context(patch("ui.layout.render_activity_graphs"))
            stack.enter_context(patch("ui.layout.render_trends_tab"))
            stack.enter_context(patch("ui.layout.render_health_data_tab"))
            stack.enter_context(patch("ui.layout.render_running_tab"))
            stack.enter_context(patch("ui.layout.render_workout_table"))
            stack.enter_context(patch("ui.layout.render_distance_range_selector"))
            stack.enter_context(patch("ui.layout.render_duration_range_selector"))
            build_rows_mock = stack.enter_context(patch("ui.layout._build_workout_rows"))
            create_modal_mock = stack.enter_context(patch("ui.layout.create_workout_detail_modal"))
            layout.render_body()

            longest_run_call = next(
                (call for call in stat_card_calls if call[0][2] == "longest_run"),
                None,
            )
            assert longest_run_call is not None
            on_click = longest_run_call[1].get("on_click")
            assert callable(on_click)
            on_click()
            build_rows_mock.assert_not_called()
            create_modal_mock.assert_not_called()
    finally:
        state.metrics_workout_index = original_record_indexes


def test_render_body_record_card_click_no_matching_row_is_noop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Record-card click should no-op when workout index is not found in built rows."""
    fake_app = SimpleNamespace(storage=SimpleNamespace(user={"input_file_path": ""}))
    stat_card_calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    original_record_indexes = dict(state.metrics_workout_index)

    def _capture_stat_card(*_args: Any, **kwargs: Any) -> None:
        stat_card_calls.append((_args, kwargs))

    try:
        state.metrics_workout_index["longest_run"] = 42
        monkeypatch.setattr(layout, "render_best_segments_tab", MagicMock())
        with ExitStack() as stack:
            stack.enter_context(patch("ui.layout.ui.row", return_value=DummyContext()))
            stack.enter_context(patch("ui.layout.ui.input", return_value=DummyComponent()))
            stack.enter_context(patch("ui.layout.ui.button", return_value=DummyComponent()))
            stack.enter_context(patch("ui.layout.ui.spinner", return_value=DummyComponent()))
            stack.enter_context(patch("ui.layout.ui.label", return_value=DummyComponent()))
            stack.enter_context(patch("ui.layout.app", fake_app))
            stack.enter_context(patch("ui.layout.ui.tabs", return_value=DummyTabs()))
            stack.enter_context(
                patch(
                    "ui.layout.ui.tab",
                    side_effect=lambda name, _label: DummyTab(name),  # type: ignore[arg-type]
                )
            )
            stack.enter_context(patch("ui.layout.ui.tab_panels", return_value=DummyContext()))
            stack.enter_context(patch("ui.layout.ui.tab_panel", return_value=DummyContext()))
            stack.enter_context(patch("ui.layout.stat_card", side_effect=_capture_stat_card))
            stack.enter_context(patch("ui.layout.render_activity_graphs"))
            stack.enter_context(patch("ui.layout.render_trends_tab"))
            stack.enter_context(patch("ui.layout.render_health_data_tab"))
            stack.enter_context(patch("ui.layout.render_running_tab"))
            stack.enter_context(patch("ui.layout.render_workout_table"))
            stack.enter_context(patch("ui.layout.render_distance_range_selector"))
            stack.enter_context(patch("ui.layout.render_duration_range_selector"))
            build_rows_mock = stack.enter_context(
                patch(
                    "ui.layout._build_workout_rows",
                    return_value=[{"workout_index": None}, {"workout_index": 100}],
                )
            )
            create_modal_mock = stack.enter_context(patch("ui.layout.create_workout_detail_modal"))
            layout.render_body()

            longest_run_call = next(
                (call for call in stat_card_calls if call[0][2] == "longest_run"),
                None,
            )
            assert longest_run_call is not None
            on_click = longest_run_call[1].get("on_click")
            assert callable(on_click)
            on_click()
            build_rows_mock.assert_called_once_with(
                activity_type="All",
                skip_range_filters=True,
            )
            create_modal_mock.assert_not_called()
    finally:
        state.metrics_workout_index = original_record_indexes
