"""Additional tests for workout detail modal tab state and activity sections."""

from __future__ import annotations

from contextlib import ExitStack
from typing import Any

import pytest

import ui.workout_detail_modal.comparisons as wdm_comparisons
from ui import workout_detail_modal as wdm

from ._stubs import _all_patches, _DummyElement, _make_row


class TestTabEnableState:
    """Tests for Activity and Splits tab enable/disable state."""

    def _make_tab_stubs(self) -> tuple[list[_DummyElement], Any]:
        """Return (tab_stubs list, tab_side_effect factory)."""
        tab_stubs: list[_DummyElement] = []

        def make_tab(*_a: Any, **_kw: Any) -> _DummyElement:
            tab = _DummyElement()
            tab._tab_value = _a[0] if _a else _kw.get("value")
            tab_stubs.append(tab)
            return tab

        return tab_stubs, make_tab

    def _tab_by_value(self, tab_stubs: list[_DummyElement], tab_value: str) -> _DummyElement:
        """Return the first tab stub with the requested ``value``."""
        return next(tab for tab in tab_stubs if getattr(tab, "_tab_value", None) == tab_value)

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
        assert not self._tab_by_value(tab_stubs, "intervals")._enabled

    def test_route_tab_disabled_when_no_route(self) -> None:
        """Route tab should be disabled when the workout has no GPS route."""
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

        import pandas as pd

        from logic.workout_manager.workout_route import RoutePoint, WorkoutRoute

        base_time = pd.Timestamp("2024-01-01 10:00:00").to_pydatetime()
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
        assert self._tab_by_value(tab_stubs, "intervals")._enabled

    def test_route_tab_enabled_when_route_present(self) -> None:
        """Route tab should be enabled when the workout has a non-empty GPS route."""
        from datetime import timedelta

        import pandas as pd

        from logic.workout_manager.workout_route import RoutePoint, WorkoutRoute

        base_time = pd.Timestamp("2024-01-01 10:00:00").to_pydatetime()
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
        assert not wdm_comparisons._row_has_route({})

    def test_returns_false_when_route_is_none(self) -> None:
        """Row with route=None should return False."""
        assert not wdm_comparisons._row_has_route({"route": None})

    def test_returns_false_for_empty_route(self) -> None:
        """Row with an empty WorkoutRoute should return False."""
        from logic.workout_manager.workout_route import WorkoutRoute

        assert not wdm_comparisons._row_has_route({"route": WorkoutRoute(points=[])})

    def test_returns_true_for_non_empty_route(self) -> None:
        """Row with a non-empty WorkoutRoute should return True."""
        from datetime import timedelta

        import pandas as pd

        from logic.workout_manager.workout_route import RoutePoint, WorkoutRoute

        base_time = pd.Timestamp("2024-01-01").to_pydatetime()
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
        assert wdm_comparisons._row_has_route({"route": WorkoutRoute(points=points)})


class TestGetRowRoutes:
    """Tests for the _get_row_routes helper."""

    def test_prefers_non_empty_route_parts_over_merged_route(self) -> None:
        """When route_parts is present, _get_row_routes returns only non-empty parts."""
        from datetime import timedelta

        import pandas as pd

        from logic.workout_manager.workout_route import RoutePoint, WorkoutRoute

        base_time = pd.Timestamp("2024-01-01").to_pydatetime()
        part = WorkoutRoute(
            points=[
                RoutePoint(
                    time=base_time + timedelta(seconds=i),
                    latitude=48.0 + (i * 0.0001),
                    longitude=2.0 + (i * 0.0001),
                    altitude=0.0,
                    speed=3.0,
                )
                for i in range(3)
            ]
        )
        merged_route = WorkoutRoute(points=[])
        routes = wdm._get_row_routes(
            {"route_parts": [WorkoutRoute(points=[]), part], "route": merged_route}
        )
        assert routes == [part]

    def test_falls_back_to_route_when_route_parts_missing(self) -> None:
        """_get_row_routes should return the merged route when route_parts is absent."""
        from datetime import timedelta

        import pandas as pd

        from logic.workout_manager.workout_route import RoutePoint, WorkoutRoute

        base_time = pd.Timestamp("2024-01-01").to_pydatetime()
        route = WorkoutRoute(
            points=[
                RoutePoint(
                    time=base_time + timedelta(seconds=i),
                    latitude=48.0 + (i * 0.0001),
                    longitude=2.0 + (i * 0.0001),
                    altitude=0.0,
                    speed=3.0,
                )
                for i in range(3)
            ]
        )
        routes = wdm._get_row_routes({"route": route})
        assert routes == [route]

    def test_falls_back_to_route_when_route_parts_is_empty_list(self) -> None:
        """_get_row_routes should return merged route when route_parts is empty."""
        from datetime import timedelta

        import pandas as pd

        from logic.workout_manager.workout_route import RoutePoint, WorkoutRoute

        base_time = pd.Timestamp("2024-01-01").to_pydatetime()
        route = WorkoutRoute(
            points=[
                RoutePoint(
                    time=base_time + timedelta(seconds=i),
                    latitude=48.0 + (i * 0.0001),
                    longitude=2.0 + (i * 0.0001),
                    altitude=0.0,
                    speed=3.0,
                )
                for i in range(3)
            ]
        )
        routes = wdm._get_row_routes({"route_parts": [], "route": route})
        assert routes == [route]


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
        """Hiking row with only elevation data and all locomotion fields missing → False."""
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

        row = {"distance": 10000.0}
        distance_value, display = wt._extract_distance_field(row, distance_unit="km")
        assert distance_value == pytest.approx(10000.0)
        assert display == "10.00 km"

    def test_metric_distance_non_round_has_two_decimals(self) -> None:
        """Non-round metric distances should show 2 decimal places."""
        from ui import workout_table as wt

        row = {"distance": 5678.0}
        distance_value, display = wt._extract_distance_field(row, distance_unit="km")
        assert distance_value == pytest.approx(5678.0)
        assert display == "5.68 km"

    def test_imperial_distance_has_two_decimals(self) -> None:
        """Imperial distances should show 2 decimal places."""
        from ui import workout_table as wt
        from units import METERS_TO_MILES

        row = {"distance": 1609.344}
        distance_value, display = wt._extract_distance_field(row, distance_unit="mi")
        expected = f"{1609.344 * METERS_TO_MILES:.2f} mi"
        assert distance_value == pytest.approx(1609.344)
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
        cycling_container = column_stubs[6]
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
        cycling_container = column_stubs[6]
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
