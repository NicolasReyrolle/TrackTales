"""Shared helpers for ui.layout function tests."""

from __future__ import annotations

from types import TracebackType
from typing import Any


def translated_message(message: str, **kwargs: Any) -> str:
    """Test helper to mimic translation with formatting placeholders."""
    return f"tr:{message.format(**kwargs)}"


class DummyRow:
    """Simple context manager stub with chainable classes() method."""

    def __enter__(self) -> DummyRow:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Exit method that does nothing."""
        pass

    def classes(self, *_args: Any, **_kwargs: Any) -> DummyRow:
        """Mock method to allow chaining."""
        return self


class DummyComponent:
    """Generic chainable NiceGUI component stub."""

    def classes(self, *_args: Any, **_kwargs: Any) -> DummyComponent:
        """Return self for class chaining."""
        return self

    def bind_enabled_from(self, *_args: Any, **_kwargs: Any) -> DummyComponent:
        """Return self for bind_enabled_from chaining."""
        return self

    def bind_value(self, *_args: Any, **_kwargs: Any) -> DummyComponent:
        """Return self for bind_value chaining."""
        return self

    def bind_text_from(self, *_args: Any, **_kwargs: Any) -> DummyComponent:
        """Return self for bind_text_from chaining."""
        return self

    def bind_visibility_from(self, *_args: Any, **_kwargs: Any) -> DummyComponent:
        """Return self for bind_visibility_from chaining."""
        return self

    def props(self, *_args: Any, **_kwargs: Any) -> DummyComponent:
        """Return self for props chaining."""
        return self

    def update(self, *_args: Any, **_kwargs: Any) -> None:
        """No-op stub for NiceGUI element.update()."""

    def on(self, *_args: Any, **_kwargs: Any) -> DummyComponent:
        """Return self for on() chaining."""
        return self


class DummyContext(DummyComponent):
    """Context-manager capable component stub."""

    def __enter__(self) -> DummyContext:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Exit method that does nothing."""
        pass


class DummyTab(DummyComponent):
    """Minimal tab object with a name attribute."""

    def __init__(self, name: str):
        self.name = name


class DummyTabs(DummyContext):
    """Tabs container that stores callback and selected value."""

    def __init__(self, on_change: Any = None):
        self.on_change = on_change
        self.value: Any = None


class DummyTable(DummyComponent):
    """Table stub that records slot additions and event handlers."""

    def __init__(self) -> None:
        self.slots: list[tuple[str, str]] = []
        self._event_handlers: dict[str, Any] = {}

    def add_slot(self, slot_name: str, slot_template: str) -> None:
        """Record slot content added by table rendering."""
        self.slots.append((slot_name, slot_template))

    def on(self, event: str, handler: Any, **_kwargs: Any) -> DummyTable:
        """Record event handlers registered on the table."""
        self._event_handlers[event] = handler
        return self

    def fire(self, event: str, args: Any = None) -> None:
        """Fire a registered event handler with a stub event object."""
        handler = self._event_handlers.get(event)
        if handler is None:
            raise KeyError(f"No handler registered for event '{event}'")

        class _Event:
            pass

        e = _Event()
        e.args = args  # type: ignore[attr-defined]
        handler(e)
