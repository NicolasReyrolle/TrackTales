"""Focused tests for ui.layout packaged-app quit header behavior."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from ui import layout

from ._helpers import DummyComponent, DummyContext, DummyDarkMode, preferences_button_factory


def test_render_header_builds_language_menu_items() -> None:
    """Header should create one preferences menu item per language and unit option."""
    with (
        patch("ui.layout.ui.dark_mode", return_value=DummyDarkMode()),
        patch("ui.layout.ui.header", return_value=DummyContext()),
        patch("ui.layout.ui.image", return_value=DummyComponent()),
        patch("ui.layout.ui.label", return_value=DummyComponent()),
        patch("ui.layout.ui.separator"),
        patch("ui.layout.ui.button", side_effect=preferences_button_factory),
        patch("ui.layout.ui.menu", return_value=DummyContext()),
        patch("ui.layout.ui.menu_item") as menu_item_mock,
        patch("ui.layout.LANGUAGES", {"en": "English", "fr": "Français"}),
        patch("ui.layout.UNIT_SYSTEMS", {"metric": "Metric", "imperial": "Imperial"}),
    ):
        layout.render_header()

    # 2 language items + 2 unit system items (metric, imperial)
    assert menu_item_mock.call_count == 4


def test_render_header_adds_quit_menu_item_for_packaged_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Packaged runs should expose a Quit action in the preferences menu."""
    monkeypatch.setattr(layout.sys, "frozen", True, raising=False)

    with (
        patch("ui.layout.ui.dark_mode", return_value=DummyDarkMode()),
        patch("ui.layout.ui.header", return_value=DummyContext()),
        patch("ui.layout.ui.image", return_value=DummyComponent()),
        patch("ui.layout.ui.label", return_value=DummyComponent()),
        patch("ui.layout.ui.separator"),
        patch("ui.layout.ui.button", side_effect=preferences_button_factory),
        patch("ui.layout.ui.menu", return_value=DummyContext()),
        patch("ui.layout.ui.menu_item") as menu_item_mock,
        patch("ui.layout.LANGUAGES", {"en": "English", "fr": "Français"}),
        patch("ui.layout.UNIT_SYSTEMS", {"metric": "Metric", "imperial": "Imperial"}),
    ):
        layout.render_header()

    assert menu_item_mock.call_count == 5
    quit_item = menu_item_mock.call_args_list[-1]
    assert quit_item.args[0] == "Quit TrackTales"
    assert quit_item.kwargs["on_click"] is layout._quit_packaged_app


@pytest.mark.asyncio
async def test_quit_packaged_app_notifies_and_shutdowns() -> None:
    """Quit action should notify the user and request a graceful app shutdown."""
    with (
        patch.object(layout.app, "shutdown") as shutdown_mock,
        patch("ui.layout.ui.notify") as notify_mock,
        patch("ui.layout.asyncio.sleep", new=AsyncMock()),
    ):
        await layout._quit_packaged_app()

    notify_mock.assert_called_once_with("TrackTales is shutting down...")
    shutdown_mock.assert_called_once_with()


@pytest.mark.asyncio
async def test_quit_packaged_app_returns_while_stopping() -> None:
    """Quit action should be a no-op when shutdown is already in progress."""
    stopping_state = type(layout.app._state).STOPPING

    with (
        patch.object(layout.app, "_state", stopping_state),
        patch.object(layout.app, "shutdown") as shutdown_mock,
        patch("ui.layout.ui.notify") as notify_mock,
        patch("ui.layout.asyncio.sleep", new=AsyncMock()) as sleep_mock,
    ):
        await layout._quit_packaged_app()

    notify_mock.assert_not_called()
    sleep_mock.assert_not_awaited()
    shutdown_mock.assert_not_called()
