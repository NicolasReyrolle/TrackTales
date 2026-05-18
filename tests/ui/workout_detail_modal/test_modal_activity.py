"""Activity-tab specific tests for ui.workout_detail_modal."""

from __future__ import annotations

from contextlib import ExitStack
from typing import Any

from ui import workout_detail_modal as wdm

from ._stubs import _all_patches, _DummyElement, _make_row


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
        running_container = column_stubs[2]
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
        running_container = column_stubs[2]
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
        running_container = column_stubs[2]
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
        walking_container = column_stubs[3]
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
        running_container = column_stubs[2]
        walking_container = column_stubs[3]
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
        walking_container = column_stubs[3]
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
        hiking_container = column_stubs[4]
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
        running_container = column_stubs[2]
        walking_container = column_stubs[3]
        hiking_container = column_stubs[4]
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
        hiking_container = column_stubs[4]
        assert hiking_container._visible  # must be shown despite translated label
