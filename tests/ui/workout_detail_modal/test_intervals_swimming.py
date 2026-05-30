"""Tests for ui.workout_detail_modal — Intervals tab (swimming laps)."""

from __future__ import annotations

from contextlib import ExitStack
from typing import Any
from unittest.mock import patch

from ui import workout_detail_modal as wdm

from ._stubs import _all_patches, _ButtonStub, _DummyElement, _make_row


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
        """Row with at least one Lap event → True."""
        assert wdm._row_has_swim_laps({"swimming_events": [{"type": "Lap"}]})

    def test_returns_false_for_segment_only_list(self) -> None:
        """Segment-only list produces no intervals → False (tab must stay disabled)."""
        assert not wdm._row_has_swim_laps({"swimming_events": [{"type": "Segment"}]})

    def test_returns_true_when_lap_mixed_with_segment(self) -> None:
        """At least one Lap event alongside Segment events → True."""
        events = [{"type": "Segment"}, {"type": "Lap"}, {"type": "Segment"}]
        assert wdm._row_has_swim_laps({"swimming_events": events})


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
        # Tab order: overview[0], activity[1], route[2], profile[3], intervals[4]
        assert not tab_stubs[4]._enabled

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
        assert not tab_stubs[4]._enabled

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
        assert tab_stubs[4]._enabled


class TestIntervalsTabSection:
    """Tests for the Intervals tab rendering in the modal."""

    def _make_swim_row(self, with_laps: bool = True) -> dict[str, Any]:
        """Build a Swimming workout row with optional lap events."""
        row: dict[str, Any] = {
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

        next_btn = created_buttons[2]
        next_btn.click()
        assert not swim_table._visible


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
                "swimming_events": [{"type": "Lap"}],
            }
        ]
        tab_stubs, make_tab = self._make_tab_stubs()

        with ExitStack() as stack:
            for p in _all_patches(tab_side_effect=make_tab):
                stack.enter_context(p)
            fn = wdm.create_workout_detail_modal(rows)

        fn(0)
        assert not tab_stubs[1]._enabled


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


class TestBuildSwimDisplayRowsStrokeTranslation:
    """Unit tests for stroke-label translation in _build_swim_display_rows()."""

    def _make_interval(self, stroke: str) -> Any:
        """Build a minimal SwimInterval with a single lap of the given stroke."""
        from logic.workout_manager.swimming import SwimInterval, SwimLap

        lap = SwimLap(
            lap_number=1,
            distance_m=50.0,
            duration_s=60.0,
            stroke_style=stroke,
            swolf=None,
        )
        return SwimInterval(laps=[lap])

    def test_freestyle_stroke_is_translated(self) -> None:
        """'Freestyle' stroke label must pass through t()."""
        rows = wdm._build_swim_display_rows([self._make_interval("Freestyle")])
        assert rows[0]["stroke"] == "Freestyle"

    def test_backstroke_is_translated(self) -> None:
        """'Backstroke' stroke label must pass through t()."""
        rows = wdm._build_swim_display_rows([self._make_interval("Backstroke")])
        assert rows[0]["stroke"] == "Backstroke"

    def test_breaststroke_is_translated(self) -> None:
        """'Breaststroke' stroke label must pass through t()."""
        rows = wdm._build_swim_display_rows([self._make_interval("Breaststroke")])
        assert rows[0]["stroke"] == "Breaststroke"

    def test_butterfly_is_translated(self) -> None:
        """'Butterfly' stroke label must pass through t()."""
        rows = wdm._build_swim_display_rows([self._make_interval("Butterfly")])
        assert rows[0]["stroke"] == "Butterfly"

    def test_kickboard_is_translated(self) -> None:
        """'Kickboard' stroke label must pass through t()."""
        rows = wdm._build_swim_display_rows([self._make_interval("Kickboard")])
        assert rows[0]["stroke"] == "Kickboard"

    def test_mixed_stroke_is_translated(self) -> None:
        """'Mixed' stroke label must pass through t()."""
        from logic.workout_manager.swimming import SwimInterval, SwimLap

        interval = SwimInterval(
            laps=[
                SwimLap(
                    lap_number=1,
                    distance_m=50.0,
                    duration_s=60.0,
                    stroke_style="Freestyle",
                    swolf=None,
                ),
                SwimLap(
                    lap_number=2,
                    distance_m=50.0,
                    duration_s=60.0,
                    stroke_style="Backstroke",
                    swolf=None,
                ),
            ],
        )
        rows = wdm._build_swim_display_rows([interval])
        assert rows[0]["stroke"] == "Mixed"

    def test_unknown_stroke_is_translated(self) -> None:
        """'Unknown' stroke label must pass through t()."""
        rows = wdm._build_swim_display_rows([self._make_interval("Unknown")])
        assert rows[0]["stroke"] == "Unknown"

    def test_all_strokes_translated_in_french(self) -> None:
        """All stroke labels are wrapped in t() and appear translated in French."""
        fr_expected = {
            "Freestyle": "Nage libre",
            "Backstroke": "Dos crawlé",
            "Breaststroke": "Brasse",
            "Butterfly": "Papillon",
            "Kickboard": "Planche",
        }
        for stroke, expected_fr in fr_expected.items():
            interval = self._make_interval(stroke)
            with patch("i18n._core.get_language", return_value="fr"):
                rows = wdm._build_swim_display_rows([interval])
            assert rows[0]["stroke"] == expected_fr, (
                f"Expected French translation for '{stroke}' to be '{expected_fr}'"
            )

    def test_empty_intervals_returns_empty_list(self) -> None:
        """No intervals → empty rows list."""
        assert wdm._build_swim_display_rows([]) == []
