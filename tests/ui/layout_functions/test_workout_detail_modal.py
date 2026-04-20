"""Tests for ui.workout_detail_modal module."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from unittest.mock import patch

from ui import workout_detail_modal as wdm


def _make_row(
    *,
    activity_type: str = "Running",
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
    """Build a minimal workout row dict matching _build_workout_rows() output."""
    return {
        "id": f"{date_sort}_{idx}",
        "date_sort": date_sort,
        "date": date,
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


class _DummyElement:
    """Generic stub for NiceGUI UI elements; supports context-manager and chaining."""

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        self._visible = True
        self._text = ""
        self._props_added: list[str] = []
        self._props_removed: list[str] = []

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

    def on(self, *_a: Any, **_kw: Any) -> _DummyElement:
        return self

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


class TestFieldDisplay:
    """Tests for the _FIELD_DISPLAY constant."""

    def test_all_expected_keys_present(self) -> None:
        """_FIELD_DISPLAY should cover all generic row fields shown in the table."""
        field_keys = {key for key, _ in wdm._FIELD_DISPLAY}
        for expected in ["date", "activity_type", "duration", "distance", "calories"]:
            assert expected in field_keys

    def test_labels_are_non_empty_strings(self) -> None:
        """Every label in _FIELD_DISPLAY should be a callable returning a non-empty string."""
        for _key, label_fn in wdm._FIELD_DISPLAY:
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
        stub = _DummyElement()

        with (
            patch("ui.workout_detail_modal.ui.dialog", return_value=stub),
            patch("ui.workout_detail_modal.ui.card", return_value=stub),
            patch("ui.workout_detail_modal.ui.row", return_value=stub),
            patch("ui.workout_detail_modal.ui.label", return_value=stub),
            patch("ui.workout_detail_modal.ui.button", return_value=stub),
        ):
            fn = wdm.create_workout_detail_modal(rows)

        assert callable(fn)

    def test_open_at_handles_negative_index_without_error(self) -> None:
        """open_at() should not raise for negative indices (clamped to 0)."""
        rows = [_make_row(idx=0), _make_row(idx=1)]
        stub = _DummyElement()

        with (
            patch("ui.workout_detail_modal.ui.dialog", return_value=stub),
            patch("ui.workout_detail_modal.ui.card", return_value=stub),
            patch("ui.workout_detail_modal.ui.row", return_value=stub),
            patch("ui.workout_detail_modal.ui.label", return_value=stub),
            patch("ui.workout_detail_modal.ui.button", return_value=stub),
        ):
            fn = wdm.create_workout_detail_modal(rows)

        fn(-5)  # Should not raise

    def test_open_at_handles_out_of_bounds_index_without_error(self) -> None:
        """open_at() should not raise for indices beyond the row list length (clamped to last)."""
        rows = [_make_row(idx=0)]
        stub = _DummyElement()

        with (
            patch("ui.workout_detail_modal.ui.dialog", return_value=stub),
            patch("ui.workout_detail_modal.ui.card", return_value=stub),
            patch("ui.workout_detail_modal.ui.row", return_value=stub),
            patch("ui.workout_detail_modal.ui.label", return_value=stub),
            patch("ui.workout_detail_modal.ui.button", return_value=stub),
        ):
            fn = wdm.create_workout_detail_modal(rows)

        fn(100)  # Should not raise

    def test_open_at_non_first_row_enables_prev_button(self) -> None:
        """Opening a non-first row should call props(remove='disabled') on the prev button."""
        rows = [_make_row(idx=0), _make_row(idx=1)]
        stub = _DummyElement()
        created_buttons: list[_ButtonStub] = []

        def make_button(*args: Any, **kwargs: Any) -> _ButtonStub:
            btn = _ButtonStub(*args, **kwargs)
            created_buttons.append(btn)
            return btn

        with (
            patch("ui.workout_detail_modal.ui.dialog", return_value=stub),
            patch("ui.workout_detail_modal.ui.card", return_value=stub),
            patch("ui.workout_detail_modal.ui.row", return_value=stub),
            patch("ui.workout_detail_modal.ui.label", return_value=stub),
            patch("ui.workout_detail_modal.ui.button", side_effect=make_button),
        ):
            fn = wdm.create_workout_detail_modal(rows)

        prev_btn = created_buttons[1]  # close=0, prev=1, next=2
        fn(1)  # Open at the second (non-first) row
        assert "disabled" in prev_btn._props_removed

    def test_navigate_forward_moves_to_next_row(self) -> None:
        """Clicking the next button should advance to the second row."""
        rows = [
            _make_row(idx=0, activity_type="Running"),
            _make_row(idx=1, activity_type="Cycling"),
        ]
        stub = _DummyElement()
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

        with (
            patch("ui.workout_detail_modal.ui.dialog", return_value=stub),
            patch("ui.workout_detail_modal.ui.card", return_value=stub),
            patch("ui.workout_detail_modal.ui.row", return_value=stub),
            patch("ui.workout_detail_modal.ui.label", side_effect=make_label),
            patch("ui.workout_detail_modal.ui.button", side_effect=make_button),
        ):
            fn = wdm.create_workout_detail_modal(rows)

        # nav_counter is the last label created (title + 8 field labels + 8 value labels + counter)
        nav_counter = label_stubs[-1]
        next_btn = created_buttons[2]  # close=0, prev=1, next=2
        fn(0)  # Start at row 0 → counter shows "1 / 2"
        next_btn.click()  # Navigate forward via the captured on_click lambda
        assert nav_counter._text == "2 / 2"

    def test_navigate_backward_does_nothing_at_first_row(self) -> None:
        """Clicking prev at the first row should be a no-op (out-of-bounds guard)."""
        rows = [_make_row(idx=0), _make_row(idx=1)]
        stub = _DummyElement()
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

        with (
            patch("ui.workout_detail_modal.ui.dialog", return_value=stub),
            patch("ui.workout_detail_modal.ui.card", return_value=stub),
            patch("ui.workout_detail_modal.ui.row", return_value=stub),
            patch("ui.workout_detail_modal.ui.label", side_effect=make_label),
            patch("ui.workout_detail_modal.ui.button", side_effect=make_button),
        ):
            fn = wdm.create_workout_detail_modal(rows)

        nav_counter = label_stubs[-1]
        prev_btn = created_buttons[1]  # close=0, prev=1, next=2
        fn(0)  # Start at row 0 → counter shows "1 / 2"
        prev_btn.click()  # Attempt to navigate before the first row
        assert nav_counter._text == "1 / 2"  # Still on row 0
