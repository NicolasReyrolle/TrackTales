"""Tests for ui.workout_detail_modal — Intervals tab (GPS splits and swimming laps)."""

from __future__ import annotations

from contextlib import ExitStack
from typing import Any

from ui import workout_detail_modal as wdm

from ._modal_stubs import _all_patches, _ButtonStub, _DummyElement, _make_row


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
        """Row with at least one Lap event → True."""
        assert wdm._row_has_swim_laps({"swimming_events": [{"type": "Lap"}]})

    def test_returns_false_for_segment_only_list(self) -> None:
        """Segment-only list produces no intervals → False (tab must stay disabled)."""
        assert not wdm._row_has_swim_laps({"swimming_events": [{"type": "Segment"}]})

    def test_returns_true_when_lap_mixed_with_segment(self) -> None:
        """At least one Lap event alongside Segment events → True."""
        events = [{"type": "Segment"}, {"type": "Lap"}, {"type": "Segment"}]
        assert wdm._row_has_swim_laps({"swimming_events": events})


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
# _build_swim_display_rows – stroke label translation
# ---------------------------------------------------------------------------


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
        interval = self._make_interval("Freestyle")
        rows = wdm._build_swim_display_rows([interval])
        # In English t("Freestyle") == "Freestyle"
        assert rows[0]["stroke"] == "Freestyle"

    def test_backstroke_is_translated(self) -> None:
        """'Backstroke' stroke label must pass through t()."""
        interval = self._make_interval("Backstroke")
        rows = wdm._build_swim_display_rows([interval])
        assert rows[0]["stroke"] == "Backstroke"

    def test_breaststroke_is_translated(self) -> None:
        """'Breaststroke' stroke label must pass through t()."""
        interval = self._make_interval("Breaststroke")
        rows = wdm._build_swim_display_rows([interval])
        assert rows[0]["stroke"] == "Breaststroke"

    def test_butterfly_is_translated(self) -> None:
        """'Butterfly' stroke label must pass through t()."""
        interval = self._make_interval("Butterfly")
        rows = wdm._build_swim_display_rows([interval])
        assert rows[0]["stroke"] == "Butterfly"

    def test_kickboard_is_translated(self) -> None:
        """'Kickboard' stroke label must pass through t()."""
        interval = self._make_interval("Kickboard")
        rows = wdm._build_swim_display_rows([interval])
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
        interval = self._make_interval("Unknown")
        rows = wdm._build_swim_display_rows([interval])
        assert rows[0]["stroke"] == "Unknown"

    def test_all_strokes_translated_in_french(self) -> None:
        """All stroke labels are wrapped in t() and appear translated in French."""
        from unittest.mock import patch

        fr_expected = {
            "Freestyle": "Nage libre",
            "Backstroke": "Dos crawlé",
            "Breaststroke": "Brasse",
            "Butterfly": "Papillon",
            "Kickboard": "Planche",
        }
        for stroke, expected_fr in fr_expected.items():
            interval = self._make_interval(stroke)
            with patch("i18n.get_language", return_value="fr"):
                rows = wdm._build_swim_display_rows([interval])
            assert rows[0]["stroke"] == expected_fr, (
                f"Expected French translation for '{stroke}' to be '{expected_fr}'"
            )

    def test_empty_intervals_returns_empty_list(self) -> None:
        """No intervals → empty rows list."""
        rows = wdm._build_swim_display_rows([])
        assert rows == []
