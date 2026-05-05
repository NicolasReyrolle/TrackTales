"""Tests for ui.workout_detail_modal module — core modal, field displays, row helpers."""

from __future__ import annotations

from contextlib import ExitStack
from typing import Any

from ui import workout_detail_modal as wdm

from ._modal_stubs import _all_patches, _ButtonStub, _DummyElement, _make_row


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
        # Container order: running[0], walking[1], hiking[2], swimming[3], cycling[4]
        cycling_container = column_stubs[4]
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
        cycling_container = column_stubs[4]
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
