"""Tests for ui.workout_detail_modal module."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import ExitStack
from typing import Any
from unittest.mock import patch

from ui import workout_detail_modal as wdm


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

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        self._visible = True
        self._enabled = True
        self._text = ""
        self._props_added: list[str] = []
        self._props_removed: list[str] = []
        self.rows: list[Any] = []
        #: Current value (used by the tabs stub to track the active tab).
        self.value: str = "overview"
        #: Registered on_value_change handlers (used for tab-change simulation).
        self._value_change_handlers: list[Any] = []

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
            handler(event)

    def update(self) -> None:
        """Stub for the NiceGUI ``update()`` method (e.g. used by ui.table)."""

    def clear(self) -> None:
        """Test stub for the NiceGUI container ``clear()`` method.

        The real NiceGUI implementation removes all child elements from the
        container.  This stub does nothing to avoid runtime errors in unit tests
        where no actual NiceGUI context is active.
        """

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
    order: overview [0], activity [1], intervals [2]).
    """
    stub = _DummyElement()
    effective_tabs = tabs_stub if tabs_stub is not None else stub
    return [
        patch("ui.workout_detail_modal.ui.dialog", return_value=stub),
        patch("ui.workout_detail_modal.ui.card", return_value=stub),
        patch("ui.workout_detail_modal.ui.row", return_value=stub),
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
    ]


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
        """_RUNNING_FIELD_DISPLAY should include pace, cadence, stride length, and VO2 max."""
        keys = {key for key, _ in wdm._RUNNING_FIELD_DISPLAY}
        for expected in ["pace", "cadence", "stride_length", "vo2_max"]:
            assert expected in keys

    def test_running_labels_are_non_empty_strings(self) -> None:
        """Every label in _RUNNING_FIELD_DISPLAY should be callable and non-empty."""
        for _key, label_fn in wdm._RUNNING_FIELD_DISPLAY:
            assert callable(label_fn)
            assert label_fn() and isinstance(label_fn(), str)


class TestFormatSplitPace:
    """Unit tests for _format_split_pace()."""

    def test_integer_minutes(self) -> None:
        """An exact integer minute pace should format as 'mm:00'."""
        assert wdm._format_split_pace(5.0) == "5:00"

    def test_fractional_pace_rounded(self) -> None:
        """Fractional seconds should be rounded correctly."""
        # 4.5 min/km → 4 min 30 sec
        assert wdm._format_split_pace(4.5) == "4:30"

    def test_seconds_rollover(self) -> None:
        """When rounded seconds == 60, minutes should increment and seconds reset."""
        # pace where fractional part rounds to 60 → 4.999... ≈ 5:00
        result = wdm._format_split_pace(4.9999)
        # should show 5:00 (rollover) rather than 4:60
        assert "60" not in result


class TestFormatElevationChange:
    """Unit tests for _format_elevation_change()."""

    def test_positive_elevation_shows_plus(self) -> None:
        """Positive elevation change should show a '+' prefix."""
        assert wdm._format_elevation_change(5.3) == "+5 m"

    def test_negative_elevation_shows_minus(self) -> None:
        """Negative elevation change should show a '-' prefix."""
        assert wdm._format_elevation_change(-2.7) == "-3 m"

    def test_zero_elevation_shows_plus_zero(self) -> None:
        """Zero elevation change should show '+0 m'."""
        assert wdm._format_elevation_change(0.0) == "+0 m"


class TestFormatSplitRows:
    """Unit tests for _format_split_rows()."""

    def test_km_pace_not_scaled(self) -> None:
        """In km mode the pace value should be used as-is."""
        splits = [{"split": 1, "pace_min_per_km": 6.0, "elevation_change_m": 10.0}]
        rows = wdm._format_split_rows(splits, "km")
        assert rows[0]["split"] == 1
        assert rows[0]["pace_str"] == "6:00"
        assert rows[0]["elev_str"] == "+10 m"

    def test_mi_pace_is_scaled(self) -> None:
        """In mi mode the pace should be converted to min/mi (slower than min/km)."""
        splits = [{"split": 1, "pace_min_per_km": 6.0, "elevation_change_m": 0.0}]
        rows_km = wdm._format_split_rows(splits, "km")
        rows_mi = wdm._format_split_rows(splits, "mi")
        # min/mi pace should be larger than min/km for the same speed
        km_minutes = int(rows_km[0]["pace_str"].split(":")[0])
        mi_minutes = int(rows_mi[0]["pace_str"].split(":")[0])
        assert mi_minutes > km_minutes

    def test_multiple_splits_returned(self) -> None:
        """All splits in the input should be present in the output."""
        splits = [
            {"split": 1, "pace_min_per_km": 5.0, "elevation_change_m": 2.0},
            {"split": 2, "pace_min_per_km": 5.5, "elevation_change_m": -1.0},
        ]
        rows = wdm._format_split_rows(splits, "km")
        assert len(rows) == 2
        assert rows[1]["split"] == 2
        assert rows[1]["elev_str"] == "-1 m"


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
        running_container = column_stubs[0]
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
        running_container = column_stubs[0]
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
        running_container = column_stubs[0]
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
        walking_container = column_stubs[1]
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
        running_container = column_stubs[0]
        walking_container = column_stubs[1]
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
        walking_container = column_stubs[1]
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
        hiking_container = column_stubs[2]
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
        running_container = column_stubs[0]
        walking_container = column_stubs[1]
        hiking_container = column_stubs[2]
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
        hiking_container = column_stubs[2]
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
        assert not tab_stubs[2]._enabled

    def test_splits_tab_enabled_when_route_present(self) -> None:
        """Intervals tab should be enabled when the workout has a non-empty GPS route."""
        from datetime import timedelta

        from logic.workout_manager.workout_route import RoutePoint, WorkoutRoute

        base_time = __import__("pandas").Timestamp("2024-01-01 10:00:00").to_pydatetime()
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
        assert not wdm._row_has_route({})

    def test_returns_false_when_route_is_none(self) -> None:
        """Row with route=None should return False."""
        assert not wdm._row_has_route({"route": None})

    def test_returns_false_for_empty_route(self) -> None:
        """Row with an empty WorkoutRoute should return False."""
        from logic.workout_manager.workout_route import WorkoutRoute

        assert not wdm._row_has_route({"route": WorkoutRoute(points=[])})

    def test_returns_true_for_non_empty_route(self) -> None:
        """Row with a non-empty WorkoutRoute should return True."""
        from datetime import timedelta

        from logic.workout_manager.workout_route import RoutePoint, WorkoutRoute

        base_time = __import__("pandas").Timestamp("2024-01-01").to_pydatetime()
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
        assert wdm._row_has_route({"route": WorkoutRoute(points=points)})


class TestRowHasActivityData:
    """Tests for the _row_has_activity_data helper."""

    def test_returns_false_for_unknown_activity_type(self) -> None:
        """Unsupported activity type has no activity-specific field keys → False."""
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

    def test_returns_true_for_hiking_with_elevation_data(self) -> None:
        """Hiking row with an elevation gain value → True."""
        assert wdm._row_has_activity_data(
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
        tabs_stub.fire_value_change("intervals")  # Simulate user clicking the Intervals tab
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
        tabs_stub.fire_value_change("intervals")  # Simulate user clicking the Intervals tab
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
        tabs_stub.fire_value_change("intervals")  # Simulate user clicking the Intervals tab
        splits_table = table_stubs[1]
        assert not splits_table._visible

    def test_pace_converted_to_min_per_mi_for_imperial_splits(self) -> None:
        """Pace values should be scaled from min/km to min/mi when distance_unit is 'mi'."""
        # 6:00/km → ~9:39/mi via 6.0 / (1000 * METERS_TO_MILES).
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
        tabs_stub.fire_value_change("intervals")  # Simulate user clicking the Intervals tab
        splits_table = table_stubs[1]
        assert splits_table._visible
        assert len(splits_table.rows) == 1
        # 6 min/km / (1000 * METERS_TO_MILES) ≈ 9.656 min/mi → "9:39"
        pace_str = splits_table.rows[0]["pace_str"]
        minutes = int(pace_str.split(":")[0])
        assert minutes == 9

    def test_navigate_while_on_splits_tab_refreshes_splits(self) -> None:
        """Navigating while the Intervals tab is active should refresh splits.

        Covers the ``if detail_tabs.value == "intervals":`` branch inside ``_refresh()``.
        """
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
                "splits": [],  # second workout has no splits
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

        fn(0)  # Open at row 0 (Overview tab active)
        tabs_stub.fire_value_change("intervals")  # User switches to Intervals tab
        splits_table = table_stubs[1]
        assert splits_table._visible  # row 0 has splits

        # Navigate to row 1 while the Splits tab remains active
        next_btn = created_buttons[2]  # Button order: [0] close, [1] prev, [2] next
        next_btn.click()
        # Row 1 has empty splits — table should now be hidden
        assert not splits_table._visible


class TestComputeSplitsLazy:
    """Unit tests for _compute_splits_lazy()."""

    def _make_route(self, n_points: int = 1001, speed_m_s: float = 3.0) -> Any:
        """Build a WorkoutRoute with *n_points* evenly-spaced speed-only points."""
        from datetime import timedelta

        import pandas as pd

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
        assert row["splits"] is result  # cached in row dict

    def test_caches_result_on_second_call(self) -> None:
        """A second call should return the same list object without recomputing."""
        route = self._make_route(n_points=1001, speed_m_s=3.0)
        row: dict[str, Any] = {"route": route, "distance_unit": "km", "distance_sort": 3000.0}
        first = wdm._compute_splits_lazy(row)
        # Call again — the idempotency guard inside _compute_splits_lazy should
        # return the already-cached list without recomputing.
        second = wdm._compute_splits_lazy(row)
        assert second is first

    def test_uses_mile_split_distance_for_imperial(self) -> None:
        """In imperial mode the split interval should be ~1609 m, yielding fewer splits."""
        route = self._make_route(n_points=1001, speed_m_s=3.0)
        row_km: dict[str, Any] = {
            "route": route,
            "distance_unit": "km",
            "distance_sort": 3000.0,
        }
        row_mi: dict[str, Any] = {
            "route": route,
            "distance_unit": "mi",
            "distance_sort": 3000.0,
        }
        splits_km = wdm._compute_splits_lazy(row_km)
        splits_mi = wdm._compute_splits_lazy(row_mi)
        # ~3000 m / 1000 m → ≥ 3 km splits; ~3000 m / 1609 m → 1 mi split
        assert len(splits_km) > len(splits_mi)

    def test_splits_computed_lazily_in_modal(self) -> None:
        """Splits should not be computed on modal open; only when the Splits tab is shown.

        Verifies that ``row['splits']`` is absent after ``open_at()`` and is
        populated only after the user switches to the Splits tab.
        """
        from datetime import timedelta

        import pandas as pd

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
                # No 'splits' key — must not be computed until Splits tab is opened.
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

        fn(0)  # Open modal on the Overview tab
        # Splits must NOT be computed yet (Overview tab is active, not Splits).
        assert "splits" not in rows[0]

        tabs_stub.fire_value_change("intervals")  # User switches to the Intervals tab
        splits_table = table_stubs[1]
        # Lazy computation should have produced ≥ 3 splits and shown the table.
        assert splits_table._visible
        assert len(splits_table.rows) >= 3
        # Result must be cached in the row dict for subsequent navigations.
        assert "splits" in rows[0]
        assert len(rows[0]["splits"]) >= 3


# ---------------------------------------------------------------------------
# _row_has_swim_laps
# ---------------------------------------------------------------------------


class TestRowHasSwimLaps:
    """Tests for the _row_has_swim_laps helper."""

    def test_returns_false_when_no_key(self) -> None:
        """Row without swimming_events key → False."""
        assert not wdm._row_has_swim_laps({})

    def test_returns_false_for_none(self) -> None:
        """Row with swimming_events=None → False."""
        assert not wdm._row_has_swim_laps({"swimming_events": None})

    def test_returns_false_for_empty_list(self) -> None:
        """Row with empty swimming_events list → False."""
        assert not wdm._row_has_swim_laps({"swimming_events": []})

    def test_returns_true_for_non_empty_list(self) -> None:
        """Row with at least one event → True."""
        assert wdm._row_has_swim_laps({"swimming_events": [{"type": "Lap"}]})


# ---------------------------------------------------------------------------
# Intervals tab: enable/disable state
# ---------------------------------------------------------------------------


class TestIntervalsTabEnableState:
    """Tests for the Intervals tab enabled/disabled state (swimming only)."""

    def _make_tab_stubs(self) -> tuple[list[_DummyElement], Any]:
        tab_stubs: list[_DummyElement] = []

        def make_tab(*_a: Any, **_kw: Any) -> _DummyElement:
            t = _DummyElement()
            tab_stubs.append(t)
            return t

        return tab_stubs, make_tab

    def test_intervals_tab_disabled_for_running(self) -> None:
        """Intervals tab should be disabled for Running workouts."""
        rows = [
            {
                **_make_row(idx=0, activity_type="Running", raw_activity_type="Running"),
                "pace": "5:00 /km",
                "splits": [],
            }
        ]
        tab_stubs, make_tab = self._make_tab_stubs()

        with ExitStack() as stack:
            for p in _all_patches(tab_side_effect=make_tab):
                stack.enter_context(p)
            fn = wdm.create_workout_detail_modal(rows)

        fn(0)
        # Tab order: overview[0], activity[1], intervals[2]
        assert not tab_stubs[2]._enabled

    def test_intervals_tab_disabled_for_swimming_with_no_events(self) -> None:
        """Intervals tab should be disabled when swimming_events is empty."""
        rows = [
            {
                **_make_row(idx=0, activity_type="Swimming", raw_activity_type="Swimming"),
                "swimming_events": [],
                "swimming_location": "Pool",
            }
        ]
        tab_stubs, make_tab = self._make_tab_stubs()

        with ExitStack() as stack:
            for p in _all_patches(tab_side_effect=make_tab):
                stack.enter_context(p)
            fn = wdm.create_workout_detail_modal(rows)

        fn(0)
        assert not tab_stubs[2]._enabled

    def test_intervals_tab_enabled_for_swimming_with_events(self) -> None:
        """Intervals tab should be enabled when swimming_events contains data."""
        rows = [
            {
                **_make_row(idx=0, activity_type="Swimming", raw_activity_type="Swimming"),
                "swimming_events": [
                    {"type": "Lap", "start_date": "2025-01-01 10:00:00 +0000", "duration_s": 65.0}
                ],
                "swimming_location": "Pool",
                "lap_length_m": 50.0,
            }
        ]
        tab_stubs, make_tab = self._make_tab_stubs()

        with ExitStack() as stack:
            for p in _all_patches(tab_side_effect=make_tab):
                stack.enter_context(p)
            fn = wdm.create_workout_detail_modal(rows)

        fn(0)
        assert tab_stubs[2]._enabled


# ---------------------------------------------------------------------------
# Intervals tab: table population
# ---------------------------------------------------------------------------


class TestIntervalsTabSection:
    """Tests for the Intervals tab rendering in the modal."""

    def _make_swim_row(self, with_laps: bool = True) -> dict[str, Any]:
        """Build a Swimming workout row with optional lap events."""
        row = {
            **_make_row(idx=0, activity_type="Swimming", raw_activity_type="Swimming"),
            "swimming_location": "Pool",
            "swimming_lap_length": "50 m",
            "swimming_stroke_count": "200",
            "lap_length_m": 50.0,
        }
        if with_laps:
            row["swimming_events"] = [
                {
                    "type": "Segment",
                    "start_date": "2025-01-01 10:00:00 +0000",
                    "duration_s": 130.0,
                },
                {
                    "type": "Lap",
                    "start_date": "2025-01-01 10:00:00 +0000",
                    "duration_s": 65.0,
                    "stroke_style": 4,
                    "swolf": 96.8,
                },
                {
                    "type": "Lap",
                    "start_date": "2025-01-01 10:01:05 +0000",
                    "duration_s": 65.0,
                    "stroke_style": 4,
                    "swolf": 114.8,
                },
            ]
        else:
            row["swimming_events"] = []
        return row

    def test_swim_table_hidden_when_no_laps(self) -> None:
        """Swim table should be hidden when there are no lap events."""
        rows = [self._make_swim_row(with_laps=False)]
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
        # table_stubs[0] is the swim table; table_stubs[1] is splits
        swim_table = table_stubs[0]
        assert not swim_table._visible

    def test_swim_table_visible_and_populated_with_merged_rows(self) -> None:
        """Swim table should show one merged row per segment, not one per lap."""
        rows = [self._make_swim_row(with_laps=True)]
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
        swim_table = table_stubs[0]
        assert swim_table._visible
        # 2 laps in 1 segment → 1 merged row (not 2)
        assert len(swim_table.rows) == 1
        assert swim_table.rows[0]["dist"] == "100 m"
        assert swim_table.rows[0]["num"] == 1

    def test_navigate_while_on_intervals_tab_refreshes(self) -> None:
        """Navigating while Intervals tab is active should refresh the swim table."""
        row0 = self._make_swim_row(with_laps=True)
        row1 = {**self._make_swim_row(with_laps=False), "date_sort": 1742000001.0}
        rows = [row0, row1]
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
        swim_table = table_stubs[0]
        assert swim_table._visible

        # Navigate forward (row1 has no laps) while intervals tab is active
        next_btn = created_buttons[2]
        next_btn.click()
        assert not swim_table._visible


# ---------------------------------------------------------------------------
# Swimming Activity tab enabled by summary fields (not by events alone)
# ---------------------------------------------------------------------------


class TestSwimmingActivityTabEnableState:
    """Tests for Activity tab enable state for swimming workouts."""

    def _make_tab_stubs(self) -> tuple[list[_DummyElement], Any]:
        tab_stubs: list[_DummyElement] = []

        def make_tab(*_a: Any, **_kw: Any) -> _DummyElement:
            t = _DummyElement()
            tab_stubs.append(t)
            return t

        return tab_stubs, make_tab

    def test_activity_tab_enabled_for_swimming_with_summary_fields(self) -> None:
        """Activity tab enabled when swimming summary fields are present."""
        rows = [
            {
                **_make_row(idx=0, activity_type="Swimming", raw_activity_type="Swimming"),
                "swimming_location": "Pool",
                "swimming_events": [],
            }
        ]
        tab_stubs, make_tab = self._make_tab_stubs()

        with ExitStack() as stack:
            for p in _all_patches(tab_side_effect=make_tab):
                stack.enter_context(p)
            fn = wdm.create_workout_detail_modal(rows)

        fn(0)
        assert tab_stubs[1]._enabled

    def test_activity_tab_disabled_for_swimming_with_no_summary_fields(self) -> None:
        """Activity tab disabled when all swimming summary fields are missing."""
        rows = [
            {
                **_make_row(idx=0, activity_type="Swimming", raw_activity_type="Swimming"),
                "swimming_location": "–",
                "swimming_lap_length": "–",
                "swimming_stroke_count": "–",
                "swimming_events": [{"type": "Lap"}],  # events exist but summary absent
            }
        ]
        tab_stubs, make_tab = self._make_tab_stubs()

        with ExitStack() as stack:
            for p in _all_patches(tab_side_effect=make_tab):
                stack.enter_context(p)
            fn = wdm.create_workout_detail_modal(rows)

        fn(0)
        assert not tab_stubs[1]._enabled


# ---------------------------------------------------------------------------
# _row_has_activity_data – swimming
# ---------------------------------------------------------------------------


class TestRowHasActivityDataSwimming:
    """Tests for _row_has_activity_data with Swimming activity type."""

    def test_returns_true_when_location_present(self) -> None:
        """Swimming row with a location value → True."""
        assert wdm._row_has_activity_data(
            {"raw_activity_type": "Swimming", "swimming_location": "Pool"}
        )

    def test_returns_true_when_lap_length_present(self) -> None:
        """Swimming row with a lap length value → True."""
        assert wdm._row_has_activity_data(
            {"raw_activity_type": "Swimming", "swimming_lap_length": "50 m"}
        )

    def test_returns_false_when_all_summary_fields_missing(self) -> None:
        """Swimming row with all summary fields '–' → False."""
        assert not wdm._row_has_activity_data(
            {
                "raw_activity_type": "Swimming",
                "swimming_location": "–",
                "swimming_lap_length": "–",
                "swimming_stroke_count": "–",
            }
        )


# ---------------------------------------------------------------------------
# Distance formatting: 2 decimal places
# ---------------------------------------------------------------------------


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
