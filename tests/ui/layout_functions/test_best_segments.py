"""Tests for ui.layout best-segments loading and rendering."""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd

import ui.best_segments as best_segments_module
from app_state import state
from logic.workout_manager import STANDARD_SEGMENT_DISTANCES
from ui import layout

from ._helpers import DummyComponent, DummyContext, DummyTab, DummyTable, DummyTabs


def _annotate_with_missing_power(df: pd.DataFrame, _running_power_df: object) -> pd.DataFrame:
    """Return a copy with missing segment power values."""
    return df.assign(segment_avg_power=None)


def _annotate_with_nan_power(df: pd.DataFrame, _running_power_df: object) -> pd.DataFrame:
    """Return a copy with NaN segment power values."""
    return df.assign(segment_avg_power=float("nan"))


def _annotate_passthrough(df: pd.DataFrame, _running_power_df: object) -> pd.DataFrame:
    """Return the unmodified DataFrame."""
    return df


class TestBestSegmentsTabData:
    """Tests for best-segments computation and async loading."""

    async def test_load_best_segments_data_formats_values(self) -> None:
        """Public loader should format rows with km, seconds, speed, and yyyy-mm-dd date."""
        original_workouts: Any = state.workouts
        original_file_loaded = state.file_loaded
        original_rows = state.best_segments_rows
        original_loading = state.best_segments_loading
        original_loaded = state.best_segments_loaded

        workouts_mock = MagicMock()
        workouts_mock.get_best_segments.return_value = pd.DataFrame(
            [
                {
                    "startDate": pd.Timestamp("2025-09-16"),
                    "distance": 1000,
                    "duration_s": 404.0,
                }
            ]
        )
        workouts_mock.annotate_segments_with_power.side_effect = _annotate_with_missing_power

        try:
            state.workouts = workouts_mock
            state.file_loaded = True
            state.best_segments_rows = []
            state.best_segments_loading = False
            state.best_segments_loaded = False

            with patch("ui.layout.render_best_segments_tab.refresh"):
                await layout.load_best_segments_data(force=True)

            assert state.best_segments_rows == [
                {
                    "id": "1000",
                    "distance": "1.0 km",
                    "duration": "6 min 44 s",
                    "average_speed": "8.91 km/h",
                    "avg_power": "–",
                    "avg_power_confidence_icon": "help_outline",
                    "avg_power_confidence_tooltip": "No matching power data",
                    "start_date": "09/16/2025",
                    "children": [],
                }
            ]
            workouts_mock.get_best_segments.assert_called_once_with(
                distances=STANDARD_SEGMENT_DISTANCES,
                start_date=None,
                end_date=None,
            )
        finally:
            state.workouts = original_workouts
            state.file_loaded = original_file_loaded
            state.best_segments_rows = original_rows
            state.best_segments_loading = original_loading
            state.best_segments_loaded = original_loaded

    async def test_load_best_segments_data_formats_special_distance_labels(self) -> None:
        """Distances under 1km are in meters, half/full marathon are shown by name."""
        original_workouts: Any = state.workouts
        original_file_loaded = state.file_loaded
        original_rows = state.best_segments_rows
        original_loading = state.best_segments_loading
        original_loaded = state.best_segments_loaded

        workouts_mock = MagicMock()
        workouts_mock.get_best_segments.return_value = pd.DataFrame(
            [
                {
                    "startDate": pd.Timestamp("2025-09-16"),
                    "distance": 100,
                    "duration_s": 20.0,
                },
                {
                    "startDate": pd.Timestamp("2025-09-16"),
                    "distance": 21097,
                    "duration_s": 5000.0,
                },
                {
                    "startDate": pd.Timestamp("2025-09-16"),
                    "distance": 42195,
                    "duration_s": 10000.0,
                },
            ]
        )
        workouts_mock.annotate_segments_with_power.side_effect = _annotate_with_missing_power

        try:
            state.workouts = workouts_mock
            state.file_loaded = True
            state.best_segments_rows = []
            state.best_segments_loading = False
            state.best_segments_loaded = False

            with patch("ui.layout.render_best_segments_tab.refresh"):
                await layout.load_best_segments_data(force=True)

            assert [row["distance"] for row in state.best_segments_rows] == [
                "100 m",
                "Half-marathon",
                "Marathon",
            ]
            assert [row["duration"] for row in state.best_segments_rows] == [
                "20 s",
                "1 h 23 min 20 s",
                "2 h 46 min 40 s",
            ]
        finally:
            state.workouts = original_workouts
            state.file_loaded = original_file_loaded
            state.best_segments_rows = original_rows
            state.best_segments_loading = original_loading
            state.best_segments_loaded = original_loaded

    async def test_load_best_segments_data_renders_nan_power_as_dash(self) -> None:
        """NaN segment power should be shown as missing value, not as literal nan W."""
        original_workouts: Any = state.workouts
        original_file_loaded = state.file_loaded
        original_rows = state.best_segments_rows
        original_loading = state.best_segments_loading
        original_loaded = state.best_segments_loaded

        workouts_mock = MagicMock()
        workouts_mock.get_best_segments.return_value = pd.DataFrame(
            [
                {
                    "startDate": pd.Timestamp("2025-09-16"),
                    "distance": 1000,
                    "duration_s": 404.0,
                }
            ]
        )
        workouts_mock.annotate_segments_with_power.side_effect = _annotate_with_nan_power

        try:
            state.workouts = workouts_mock
            state.file_loaded = True
            state.best_segments_rows = []
            state.best_segments_loading = False
            state.best_segments_loaded = False

            with patch("ui.layout.render_best_segments_tab.refresh"):
                await layout.load_best_segments_data(force=True)

            assert state.best_segments_rows[0]["avg_power"] == "–"
        finally:
            state.workouts = original_workouts
            state.file_loaded = original_file_loaded
            state.best_segments_rows = original_rows
            state.best_segments_loading = original_loading
            state.best_segments_loaded = original_loaded

    async def test_load_best_segments_data_formats_date_by_language(self) -> None:
        """Date formatting should follow selected language (fr: dd/mm/yyyy)."""
        original_workouts: Any = state.workouts
        original_file_loaded = state.file_loaded
        original_rows = state.best_segments_rows
        original_loading = state.best_segments_loading
        original_loaded = state.best_segments_loaded

        workouts_mock = MagicMock()
        workouts_mock.get_best_segments.return_value = pd.DataFrame(
            [
                {
                    "startDate": pd.Timestamp("2025-09-16"),
                    "distance": 1000,
                    "duration_s": 404.0,
                }
            ]
        )
        workouts_mock.annotate_segments_with_power.side_effect = _annotate_with_missing_power

        try:
            state.workouts = workouts_mock
            state.file_loaded = True
            state.best_segments_rows = []
            state.best_segments_loading = False
            state.best_segments_loaded = False

            with patch("ui.best_segments.get_language", return_value="fr"):
                with patch("ui.layout.render_best_segments_tab.refresh"):
                    await layout.load_best_segments_data(force=True)

            assert state.best_segments_rows[0]["start_date"] == "16/09/2025"
        finally:
            state.workouts = original_workouts
            state.file_loaded = original_file_loaded
            state.best_segments_rows = original_rows
            state.best_segments_loading = original_loading
            state.best_segments_loaded = original_loaded

    async def test_load_best_segments_data_populates_rows(self) -> None:
        """Loader should set loading flags, populate rows, and mark data as loaded."""
        original_file_loaded = state.file_loaded
        original_rows = state.best_segments_rows
        original_loading = state.best_segments_loading
        original_loaded = state.best_segments_loaded

        expected_rows = [{"distance": "1.0 km"}]

        try:
            state.file_loaded = True
            state.best_segments_rows = []
            state.best_segments_loading = False
            state.best_segments_loaded = False

            with patch("ui.layout.render_best_segments_tab.refresh") as refresh_mock:
                with patch(
                    "ui.best_segments.asyncio.to_thread", new=AsyncMock(return_value=expected_rows)
                ):
                    await layout.load_best_segments_data()

            assert state.best_segments_rows == expected_rows
            assert state.best_segments_loaded is True
            assert state.best_segments_loading is False
            assert refresh_mock.call_count == 2
        finally:
            state.file_loaded = original_file_loaded
            state.best_segments_rows = original_rows
            state.best_segments_loading = original_loading
            state.best_segments_loaded = original_loaded

    async def test_load_best_segments_data_returns_early_when_file_not_loaded(self) -> None:
        """Loader should do nothing when no export file is loaded."""
        original_file_loaded = state.file_loaded
        original_rows = state.best_segments_rows
        original_loading = state.best_segments_loading
        original_loaded = state.best_segments_loaded

        try:
            state.file_loaded = False
            state.best_segments_rows = [{"distance": "existing"}]
            state.best_segments_loading = False
            state.best_segments_loaded = False

            with patch("ui.layout.render_best_segments_tab.refresh") as refresh_mock:
                with patch("ui.best_segments.asyncio.to_thread", new=AsyncMock()) as to_thread_mock:
                    await layout.load_best_segments_data()

            assert state.best_segments_rows == [{"distance": "existing"}]
            assert state.best_segments_loading is False
            assert state.best_segments_loaded is False
            refresh_mock.assert_not_called()
            to_thread_mock.assert_not_called()
        finally:
            state.file_loaded = original_file_loaded
            state.best_segments_rows = original_rows
            state.best_segments_loading = original_loading
            state.best_segments_loaded = original_loaded

    async def test_load_best_segments_data_returns_early_when_already_loading(self) -> None:
        """Concurrent calls should return immediately when loading is already in progress."""
        original_file_loaded = state.file_loaded
        original_loading = state.best_segments_loading
        original_loaded = state.best_segments_loaded

        try:
            state.file_loaded = True
            state.best_segments_loading = True
            state.best_segments_loaded = False

            with patch("ui.layout.render_best_segments_tab.refresh") as refresh_mock:
                with patch("ui.best_segments.asyncio.to_thread", new=AsyncMock()) as to_thread_mock:
                    await layout.load_best_segments_data(force=True)

            refresh_mock.assert_not_called()
            to_thread_mock.assert_not_called()
            assert state.best_segments_loading is True
        finally:
            state.file_loaded = original_file_loaded
            state.best_segments_loading = original_loading
            state.best_segments_loaded = original_loaded

    async def test_load_best_segments_data_returns_early_when_loaded_and_not_forced(self) -> None:
        """Cached results should not be recomputed unless force=True."""
        original_file_loaded = state.file_loaded
        original_loading = state.best_segments_loading
        original_loaded = state.best_segments_loaded

        try:
            state.file_loaded = True
            state.best_segments_loading = False
            state.best_segments_loaded = True

            with patch("ui.layout.render_best_segments_tab.refresh") as refresh_mock:
                with patch("ui.best_segments.asyncio.to_thread", new=AsyncMock()) as to_thread_mock:
                    await layout.load_best_segments_data(force=False)

            refresh_mock.assert_not_called()
            to_thread_mock.assert_not_called()
        finally:
            state.file_loaded = original_file_loaded
            state.best_segments_loading = original_loading
            state.best_segments_loaded = original_loaded

    def test_build_best_segments_rows_skips_empty_groups(self) -> None:
        """Groups with no records should be ignored instead of raising errors."""

        original_workouts: Any = state.workouts
        original_range = state.date_range_text

        class _GroupFrame:  # pylint: disable=too-few-public-methods
            """Minimal frame-like object exposing only methods used by builder."""

            def __init__(self, records: list[Any]) -> None:
                """Store tuple-like records to return from itertuples."""
                self._records = records

            def sort_values(self, _column: str) -> _GroupFrame:
                """Return self to mimic DataFrame sorting chain."""
                return self

            def itertuples(self, index: bool = False) -> list[Any]:
                """Return prebuilt records in tuple-like form."""
                _ = index
                return self._records

        class _BestSegmentsFrame:  # pylint: disable=too-few-public-methods
            """Minimal frame-like object exposing only groupby used by builder."""

            def __init__(self, groups: list[tuple[str, _GroupFrame]]) -> None:
                """Store grouped records to be yielded by groupby."""
                self._groups = groups

            def groupby(self, _key: str, sort: bool = True) -> list[tuple[str, _GroupFrame]]:
                """Return predefined groups regardless of key/sort arguments."""
                _ = sort
                return self._groups

        empty_group = _GroupFrame([])
        valid_group = _GroupFrame(
            [
                SimpleNamespace(
                    distance=5000.0,
                    duration_s=1500.0,
                    startDate=pd.Timestamp("2025-09-17"),
                ),
            ]
        )

        workouts_mock = MagicMock()
        workouts_mock.get_best_segments.return_value = _BestSegmentsFrame(
            [("1000", empty_group), ("5000", valid_group)]
        )
        workouts_mock.annotate_segments_with_power.side_effect = _annotate_passthrough

        try:
            state.workouts = workouts_mock
            state.date_range_text = ""
            build_rows = cast(
                Callable[[], list[dict[str, Any]]],
                getattr(best_segments_module, "_build_best_segments_rows"),  # pyright: ignore[reportPrivateUsage]
            )
            with patch("ui.best_segments.get_language", return_value="en"):
                rows = build_rows()

            assert len(rows) == 1
            assert rows[0]["id"] == "5000"
            assert rows[0]["distance"] == "5.0 km"
        finally:
            state.workouts = original_workouts
            state.date_range_text = original_range

    async def test_load_best_segments_data_logs_and_resets_when_background_fails(self) -> None:
        """Background compute errors should be logged and loading flag reset."""
        original_file_loaded = state.file_loaded
        original_rows = state.best_segments_rows
        original_loading = state.best_segments_loading
        original_loaded = state.best_segments_loaded

        try:
            state.file_loaded = True
            state.best_segments_rows = []
            state.best_segments_loading = False
            state.best_segments_loaded = False

            with patch("ui.layout.render_best_segments_tab.refresh") as refresh_mock:
                with patch("ui.best_segments._logger.exception") as exception_mock:
                    with patch(
                        "ui.best_segments.asyncio.to_thread",
                        new=AsyncMock(side_effect=RuntimeError("boom")),
                    ):
                        await layout.load_best_segments_data(force=True)

            exception_mock.assert_called_once()
            assert state.best_segments_loading is False
            assert state.best_segments_loaded is False
            assert refresh_mock.call_count == 2
        finally:
            state.file_loaded = original_file_loaded
            state.best_segments_rows = original_rows
            state.best_segments_loading = original_loading
            state.best_segments_loaded = original_loaded

    async def test_load_best_segments_data_skips_rows_without_start_date(self) -> None:
        """Rows without a valid startDate should be filtered out during loading."""
        original_workouts: Any = state.workouts
        original_file_loaded = state.file_loaded
        original_rows = state.best_segments_rows
        original_loading = state.best_segments_loading
        original_loaded = state.best_segments_loaded

        workouts_mock = MagicMock()
        workouts_mock.get_best_segments.return_value = pd.DataFrame(
            [
                {
                    "startDate": None,
                    "distance": 1000,
                    "duration_s": 404.0,
                }
            ]
        )
        workouts_mock.annotate_segments_with_power.side_effect = _annotate_with_missing_power

        try:
            state.workouts = workouts_mock
            state.file_loaded = True
            state.best_segments_rows = []
            state.best_segments_loading = False
            state.best_segments_loaded = False

            with patch("ui.layout.render_best_segments_tab.refresh"):
                await layout.load_best_segments_data(force=True)

            assert state.best_segments_rows == []
            assert state.best_segments_loaded is True
        finally:
            state.workouts = original_workouts
            state.file_loaded = original_file_loaded
            state.best_segments_rows = original_rows
            state.best_segments_loading = original_loading
            state.best_segments_loaded = original_loaded


class TestBestSegmentsTabRendering:
    """Tests for best-segments tab rendering branches."""

    def test_render_best_segments_tab_shows_loading_state(self) -> None:
        """Loading flag should render spinner state and skip table rendering."""
        original_loading = state.best_segments_loading
        original_loaded = state.best_segments_loaded

        try:
            state.best_segments_loading = True
            state.best_segments_loaded = False

            with (
                patch("ui.best_segments.ui.card", return_value=DummyContext()),
                patch("ui.best_segments.ui.row", return_value=DummyContext()),
                patch("ui.best_segments.ui.spinner") as spinner_mock,
                patch("ui.best_segments.ui.label") as label_mock,
                patch("ui.best_segments.ui.table") as table_mock,
            ):
                layout.render_best_segments_tab.func()

            spinner_mock.assert_called_once()
            assert any(
                "Loading best segments" in str(call.args[0])
                for call in label_mock.call_args_list
                if call.args
            )
            table_mock.assert_not_called()
        finally:
            state.best_segments_loading = original_loading
            state.best_segments_loaded = original_loaded

    def test_render_best_segments_tab_renders_table_and_slots_when_loaded(self) -> None:
        """Loaded state should render table with custom header/body slots."""
        original_rows = state.best_segments_rows
        original_loading = state.best_segments_loading
        original_loaded = state.best_segments_loaded
        table_stub = DummyTable()

        try:
            state.best_segments_rows = [
                {
                    "id": "1000",
                    "distance": "1.0 km",
                    "duration": "6 min 44 s",
                    "average_speed": "8.91 km/h",
                    "avg_power": "–",
                    "start_date": "09/16/2025",
                    "children": [],
                }
            ]
            state.best_segments_loading = False
            state.best_segments_loaded = True

            with (
                patch("ui.best_segments.ui.card", return_value=DummyContext()),
                patch("ui.best_segments.ui.label", return_value=DummyComponent()),
                patch("ui.best_segments.ui.table", return_value=table_stub) as table_mock,
            ):
                layout.render_best_segments_tab.func()

            table_mock.assert_called_once()
            assert len(table_stub.slots) == 2
            assert table_stub.slots[0][0] == "header"
            assert table_stub.slots[1][0] == "body"
        finally:
            state.best_segments_rows = original_rows
            state.best_segments_loading = original_loading
            state.best_segments_loaded = original_loaded

    def test_render_best_segments_tab_only_one_table_when_loaded(self) -> None:
        """Loaded state with no CP card should render exactly one table."""
        original_rows = state.best_segments_rows
        original_loading = state.best_segments_loading
        original_loaded = state.best_segments_loaded

        table_stub = DummyTable()

        try:
            state.best_segments_rows = []
            state.best_segments_loading = False
            state.best_segments_loaded = True

            with (
                patch("ui.best_segments.ui.card", return_value=DummyContext()),
                patch("ui.best_segments.ui.label", return_value=DummyComponent()),
                patch("ui.best_segments.ui.table", return_value=table_stub) as table_mock,
            ):
                layout.render_best_segments_tab.func()

            # Only the best-segments table; CP card was removed
            table_mock.assert_called_once()
        finally:
            state.best_segments_rows = original_rows
            state.best_segments_loading = original_loading
            state.best_segments_loaded = original_loaded


def test_render_body_tab_change_to_best_segments_schedules_async_load() -> None:
    """Selecting the best-segments tab should schedule async loading."""
    tabs_created: list[DummyTabs] = []
    fake_app = SimpleNamespace(storage=SimpleNamespace(user={"input_file_path": ""}))

    def _tabs_factory(on_change: Any = None) -> DummyTabs:
        tabs = DummyTabs(on_change=on_change)
        tabs_created.append(tabs)
        return tabs

    def _tab_factory(name: str, _label: str) -> DummyTab:
        return DummyTab(name)

    with (
        patch("ui.layout.ui.row", return_value=DummyContext()),
        patch("ui.layout.ui.input", return_value=DummyComponent()),
        patch("ui.layout.ui.button", return_value=DummyComponent()),
        patch("ui.layout.ui.spinner", return_value=DummyComponent()),
        patch("ui.layout.ui.label", return_value=DummyComponent()),
        patch("ui.layout.app", fake_app),
        patch("ui.layout.ui.tabs", side_effect=_tabs_factory),
        patch("ui.layout.ui.tab", side_effect=_tab_factory),
        patch("ui.layout.ui.tab_panels", return_value=DummyContext()),
        patch("ui.layout.ui.tab_panel", return_value=DummyContext()),
        patch("ui.layout.stat_card"),
        patch("ui.layout.render_activity_graphs"),
        patch("ui.layout.render_trends_tab"),
        patch("ui.layout.render_health_data_tab"),
        patch("ui.layout.render_best_segments_tab"),
        patch("ui.layout.load_best_segments_data", new=AsyncMock()),
        patch("ui.layout.asyncio.create_task") as create_task_mock,
    ):

        def _close_coro(coro: Any) -> None:
            coro.close()

        create_task_mock.side_effect = _close_coro

        layout.render_body()
        assert tabs_created

        on_change = tabs_created[0].on_change
        assert on_change is not None
        on_change(SimpleNamespace(value=SimpleNamespace(name="best_segments")))

    create_task_mock.assert_called_once()


def _make_render_body_stubs() -> tuple[list[DummyTabs], list[dict[str, Any]], SimpleNamespace]:
    """Return (tabs_created, tab_panels_calls, fake_app) factories for render_body() patching."""
    tabs_created: list[DummyTabs] = []
    tab_panels_calls: list[dict[str, Any]] = []
    fake_app = SimpleNamespace(storage=SimpleNamespace(user={"input_file_path": ""}))
    return tabs_created, tab_panels_calls, fake_app


def _make_tabs_factory(tabs_created: list[DummyTabs]) -> Any:
    """Return a ui.tabs side_effect that appends each created tab container to tabs_created."""

    def factory(on_change: Any = None) -> DummyTabs:
        tabs = DummyTabs(on_change=on_change)
        tabs_created.append(tabs)
        return tabs

    return factory


def _make_tab_panels_factory(tab_panels_calls: list[dict[str, Any]]) -> Any:
    """Return a ui.tab_panels side_effect that records each call's kwargs."""

    def factory(*args: Any, **kwargs: Any) -> DummyContext:
        tab_panels_calls.append({"args": args, "kwargs": kwargs})
        return DummyContext()

    return factory


def _dummy_tab_factory(name: str, _label: str) -> DummyTab:
    """Simple ui.tab side_effect that returns a DummyTab."""
    return DummyTab(name)


def test_render_body_initializes_tabs_from_state() -> None:
    """render_body() should restore the previously selected tab from state, not force 'summary'."""
    tabs_created, tab_panels_calls, fake_app = _make_render_body_stubs()
    tab_panels_factory = _make_tab_panels_factory(tab_panels_calls)

    original_tab = state.selected_main_tab
    try:
        state.selected_main_tab = "activities"

        with (
            patch("ui.layout.ui.row", return_value=DummyContext()),
            patch("ui.layout.ui.input", return_value=DummyComponent()),
            patch("ui.layout.ui.button", return_value=DummyComponent()),
            patch("ui.layout.ui.spinner", return_value=DummyComponent()),
            patch("ui.layout.ui.label", return_value=DummyComponent()),
            patch("ui.layout.app", fake_app),
            patch("ui.layout.ui.tabs", side_effect=_make_tabs_factory(tabs_created)),
            patch("ui.layout.ui.tab", side_effect=_dummy_tab_factory),
            patch("ui.layout.ui.tab_panels", side_effect=tab_panels_factory),
            patch("ui.layout.ui.tab_panel", return_value=DummyContext()),
            patch("ui.layout.stat_card"),
            patch("ui.layout.render_activity_graphs"),
            patch("ui.layout.render_trends_tab"),
            patch("ui.layout.render_health_data_tab"),
            patch("ui.layout.render_best_segments_tab"),
        ):
            layout.render_body()

        assert tabs_created
        assert tabs_created[0].value == "activities"
        assert tab_panels_calls
        assert tab_panels_calls[0]["kwargs"].get("value") == "activities"
    finally:
        state.selected_main_tab = original_tab


def test_render_body_defaults_tabs_to_summary_when_state_empty() -> None:
    """render_body() should default to 'summary' tab when state has no stored tab."""
    tabs_created, tab_panels_calls, fake_app = _make_render_body_stubs()
    tab_panels_factory = _make_tab_panels_factory(tab_panels_calls)

    original_tab = state.selected_main_tab
    try:
        state.selected_main_tab = ""

        with (
            patch("ui.layout.ui.row", return_value=DummyContext()),
            patch("ui.layout.ui.input", return_value=DummyComponent()),
            patch("ui.layout.ui.button", return_value=DummyComponent()),
            patch("ui.layout.ui.spinner", return_value=DummyComponent()),
            patch("ui.layout.ui.label", return_value=DummyComponent()),
            patch("ui.layout.app", fake_app),
            patch("ui.layout.ui.tabs", side_effect=_make_tabs_factory(tabs_created)),
            patch("ui.layout.ui.tab", side_effect=_dummy_tab_factory),
            patch("ui.layout.ui.tab_panels", side_effect=tab_panels_factory),
            patch("ui.layout.ui.tab_panel", return_value=DummyContext()),
            patch("ui.layout.stat_card"),
            patch("ui.layout.render_activity_graphs"),
            patch("ui.layout.render_trends_tab"),
            patch("ui.layout.render_health_data_tab"),
            patch("ui.layout.render_best_segments_tab"),
        ):
            layout.render_body()

        assert tabs_created
        assert tabs_created[0].value == "summary"
        assert tab_panels_calls
        assert tab_panels_calls[0]["kwargs"].get("value") == "summary"
    finally:
        state.selected_main_tab = original_tab
