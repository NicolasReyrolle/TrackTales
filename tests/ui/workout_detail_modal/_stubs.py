"""Shared test stubs and helpers for test_workout_detail_modal*.py modules."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any
from unittest.mock import patch


def _make_row(
    *,
    activity_type: str = "Running",
    raw_activity_type: str | None = None,
    date: str = "Sep 16, 2025",
    duration: str = "1h 00min",
    distance: str = "10.0 km",
    calories: str = "650 kcal",
    avg_hr: str = "130 bpm",
    elevation: str = "65 m",
    avg_power: str = "210 W",
    date_sort: float = 1742000000.0,
    idx: int = 0,
) -> dict[str, Any]:
    """Build a minimal workout row dict matching _build_workout_rows() output.

    ``raw_activity_type`` defaults to ``activity_type`` when not specified.  Set
    them to different values to simulate a language switch (e.g.
    ``activity_type="Course à pied", raw_activity_type="Running"``).
    """
    return {
        "id": f"{date_sort}_{idx}",
        "date_sort": date_sort,
        "date": date,
        "raw_activity_type": raw_activity_type if raw_activity_type is not None else activity_type,
        "activity_type": activity_type,
        "duration_sort": 3600.0,
        "duration": duration,
        "distance_sort": 10000.0,
        "distance": distance,
        "calories_sort": 650.0,
        "calories": calories,
        "avg_hr_sort": 130.0,
        "avg_hr": avg_hr,
        "elevation_sort": 65.0,
        "elevation": elevation,
        "avg_power_sort": 210.0,
        "avg_power": avg_power,
    }


class _DummyEvent:
    """Tab-change event stub that mimics the NiceGUI ``ValueChangeEventArguments`` object.

    Carries a *value* attribute so that ``on_value_change`` handlers registered
    on the tabs stub can be triggered in tests without a live NiceGUI session.
    """

    def __init__(self, value: str) -> None:
        self.value = value


class _DummyElement:
    """Generic stub for NiceGUI UI elements; supports context-manager and chaining."""

    _counter = 0

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        self._visible = True
        self._enabled = True
        self._text = ""
        type(self)._counter += 1
        self.id = f"dummy-layer-{type(self)._counter}"
        self._props_added: list[str] = []
        self._props_removed: list[str] = []
        self.rows: list[Any] = []
        self.options: dict[str, Any] = {}
        #: Captures the ``columns`` kwarg when used as a ``ui.table`` stub.
        #: Stored by reference so in-place mutations to the list are visible here.
        self.columns: list[Any] = _kwargs.get("columns", [])
        #: Tab value set when this stub is used as a ``ui.tab`` instance.
        self._tab_value: str | None = None
        #: Current value (used by the tabs stub to track the active tab).
        self.value: str = "overview"
        #: Registered on_value_change handlers (used for tab-change simulation).
        self._value_change_handlers: list[Any] = []
        #: Captures run_map_method calls in order for route-map assertions.
        self._run_map_method_calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
        #: Number of awaited calls to initialized(); used by async route-map tests.
        self._initialized_calls = 0

    def classes(self, *_a: Any, **_kw: Any) -> _DummyElement:
        return self

    def props(self, *args: Any, remove: str = "", **_kw: Any) -> _DummyElement:
        if args:
            self._props_added.append(str(args[0]))
        if remove:
            self._props_removed.append(remove)
        return self

    def set_text(self, text: str) -> None:
        self._text = text

    def set_visibility(self, visible: bool) -> None:
        self._visible = visible

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled

    def on(self, *_a: Any, **_kw: Any) -> _DummyElement:
        return self

    def on_value_change(self, handler: Any) -> _DummyElement:
        """Capture a value-change handler, mimicking NiceGUI's tabs widget API.

        Stored handlers are invoked when :meth:`fire_value_change` is called,
        allowing tests to simulate tab-switch events without a live NiceGUI session.
        """
        self._value_change_handlers.append(handler)
        return self

    def fire_value_change(self, value: str) -> None:
        """Simulate a NiceGUI tab-change event (e.g., clicking the Splits tab in tests).

        Updates *self.value* and dispatches a :class:`_DummyEvent` to every
        handler registered via :meth:`on_value_change`.
        """
        self.value = value
        event = _DummyEvent(value)
        for handler in self._value_change_handlers:
            result = handler(event)
            if asyncio.iscoroutine(result):
                asyncio.run(result)

    def update(self) -> None:
        """Stub for the NiceGUI ``update()`` method (e.g. used by ui.table)."""

    def clear(self) -> None:
        """Test stub for the NiceGUI container ``clear()`` method.

        The real NiceGUI implementation removes all child elements from the
        container.  This stub does nothing to avoid runtime errors in unit tests
        where no actual NiceGUI context is active.
        """

    def clear_layers(self) -> None:
        """Stub for ui.leaflet.clear_layers()."""

    def tile_layer(self, *_a: Any, **_kw: Any) -> _DummyElement:
        """Stub for ui.leaflet.tile_layer()."""
        return self

    def generic_layer(self, *_a: Any, **_kw: Any) -> _DummyElement:
        """Stub for ui.leaflet.generic_layer()."""
        return _DummyElement()

    def marker(self, *_a: Any, **_kw: Any) -> _DummyElement:
        """Stub for ui.leaflet.marker()."""
        return _DummyElement()

    def run_layer_method(self, *_a: Any, **_kw: Any) -> _DummyElement:
        """Stub for ui.leaflet.run_layer_method()."""
        return self

    def run_map_method(self, *_a: Any, **_kw: Any) -> _DummyElement:
        """Stub for ui.leaflet.run_map_method()."""
        self._run_map_method_calls.append((_a, _kw))
        return self

    def set_center(self, *_a: Any, **_kw: Any) -> None:
        """Stub for ui.leaflet.set_center()."""

    def set_zoom(self, *_a: Any, **_kw: Any) -> None:
        """Stub for ui.leaflet.set_zoom()."""

    async def initialized(self) -> None:
        """Stub for ui.leaflet.initialized()."""
        await asyncio.sleep(0)
        self._initialized_calls += 1

    def open(self) -> None:
        """Stub for dialog.open()."""

    def close(self) -> None:
        """Stub for dialog.close()."""

    def __enter__(self) -> _DummyElement:
        return self

    def __exit__(self, *_: Any) -> None:
        """Exit the context manager; does nothing in the stub."""


class _ButtonStub(_DummyElement):
    """Button stub that captures the *on_click* callback for test introspection."""

    def __init__(self, *_args: Any, **kwargs: Any) -> None:
        super().__init__(*_args, **kwargs)
        self._on_click: Callable[[], Any] | None = kwargs.get("on_click")

    def click(self) -> None:
        """Simulate a user click by invoking the captured *on_click* callback."""
        if self._on_click is not None:
            self._on_click()


def _all_patches(
    *,
    button_side_effect: Any = None,
    label_side_effect: Any = None,
    column_side_effect: Any = None,
    table_side_effect: Any = None,
    tab_side_effect: Any = None,
    tabs_stub: _DummyElement | None = None,
) -> list[Any]:
    """Return a list of context-manager patches for all NiceGUI elements used in the modal.

    Callers may override individual element factories via keyword arguments.
    Pass *tabs_stub* to receive the ``ui.tabs`` instance back for simulating
    tab-change events via :meth:`_DummyElement.fire_value_change`.
    Pass *tab_side_effect* to capture individual ``ui.tab`` instances (created in
    order: overview [0], activity [1], route [2], profile [3], intervals [4], comparisons [5]).
    """
    stub = _DummyElement()
    effective_tabs = tabs_stub if tabs_stub is not None else stub
    return [
        patch("ui.workout_detail_modal.ui.dialog", return_value=stub),
        patch("ui.workout_detail_modal.ui.card", return_value=stub),
        patch("ui.workout_detail_modal.ui.row", return_value=stub),
        patch("ui.workout_detail_modal.ui.element", return_value=stub),
        patch("ui.workout_detail_modal.ui.tabs", return_value=effective_tabs),
        patch(
            "ui.workout_detail_modal.ui.tab",
            side_effect=tab_side_effect or (lambda *a, **kw: _DummyElement()),
        ),
        patch("ui.workout_detail_modal.ui.tab_panels", return_value=stub),
        patch("ui.workout_detail_modal.ui.tab_panel", return_value=stub),
        patch(
            "ui.workout_detail_modal.ui.label",
            side_effect=label_side_effect or (lambda *a, **kw: _DummyElement()),
        ),
        patch(
            "ui.workout_detail_modal.ui.button",
            side_effect=button_side_effect or (lambda *a, **kw: _ButtonStub(*a, **kw)),
        ),
        patch(
            "ui.workout_detail_modal.ui.column",
            side_effect=column_side_effect or (lambda *a, **kw: _DummyElement()),
        ),
        patch(
            "ui.workout_detail_modal.ui.table",
            side_effect=table_side_effect or (lambda *a, **kw: _DummyElement()),
        ),
        patch("ui.workout_detail_modal.ui.leaflet", return_value=stub),
        patch("ui.workout_detail_modal.ui.echart", return_value=stub),
        patch("ui.workout_detail_modal.ui.html", return_value=stub),
        patch("ui.workout_detail_modal.ui.spinner", return_value=stub),
        patch("ui.workout_detail_modal.ui.add_head_html", return_value=None),
        patch("ui.workout_detail_modal.ui.run_javascript", return_value=None),
    ]
