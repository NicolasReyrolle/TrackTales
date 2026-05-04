"""Tests for render_workout_table() and utility helpers in ui.workout_table."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from app_state import state
from ui import workout_table as wt

from ._helpers import DummyComponent, DummyTable


class TestRenderWorkoutTable:
    """Tests for render_workout_table()."""

    def test_shows_empty_state_when_file_not_loaded(self) -> None:
        """Tab should display an empty-state label when no file has been loaded."""
        original_file_loaded = state.file_loaded

        try:
            state.file_loaded = False

            with patch("ui.workout_table.ui.label", return_value=DummyComponent()) as label_mock:
                wt.render_workout_table.func()

            label_mock.assert_called_once()
            assert any(
                "Load a file" in str(call.args[0])
                for call in label_mock.call_args_list
                if call.args
            )
        finally:
            state.file_loaded = original_file_loaded

    def test_renders_table_with_slots_when_loaded(self) -> None:
        """Table should be created with one body-cell slot per column when data is loaded."""
        original_file_loaded = state.file_loaded
        original_workouts: Any = state.workouts

        workouts_mock = MagicMock()
        workouts_mock._filter_workouts.return_value = pd.DataFrame(
            [
                {
                    "activityType": "Running",
                    "startDate": pd.Timestamp("2025-09-16"),
                    "duration": 3660.0,
                }
            ]
        )

        table_stub = DummyTable()

        try:
            state.file_loaded = True
            state.workouts = workouts_mock

            with (
                patch("ui.workout_table.ui.table", return_value=table_stub) as table_mock,
                patch("ui.workout_table.create_workout_detail_modal", return_value=lambda _: None),
            ):
                wt.render_workout_table.func()

            table_mock.assert_called_once()
            # One slot per data column plus the actions column:
            # date, activity_type, duration, distance, calories,
            # avg_hr, elevation, avg_power, actions
            assert len(table_stub.slots) == 9
            slot_names = [s[0] for s in table_stub.slots]
            assert "body-cell-date" in slot_names
            assert "body-cell-activity_type" in slot_names
            assert "body-cell-duration" in slot_names
            assert "body-cell-distance" in slot_names
            assert "body-cell-calories" in slot_names
            assert "body-cell-avg_hr" in slot_names
            assert "body-cell-elevation" in slot_names
            assert "body-cell-avg_power" in slot_names
            assert "body-cell-actions" in slot_names
        finally:
            state.file_loaded = original_file_loaded
            state.workouts = original_workouts

    def test_table_pagination_default_sort_date_descending(self) -> None:
        """Table should be initialised with date sort descending."""
        original_file_loaded = state.file_loaded
        original_workouts: Any = state.workouts

        workouts_mock = MagicMock()
        workouts_mock._filter_workouts.return_value = pd.DataFrame(
            [
                {
                    "activityType": "Running",
                    "startDate": pd.Timestamp("2025-09-16"),
                    "duration": 3660.0,
                }
            ]
        )

        try:
            state.file_loaded = True
            state.workouts = workouts_mock

            with (
                patch("ui.workout_table.ui.table", return_value=DummyTable()) as table_mock,
                patch("ui.workout_table.create_workout_detail_modal", return_value=lambda _: None),
            ):
                wt.render_workout_table.func()

            call_kwargs = table_mock.call_args
            pagination = call_kwargs.kwargs.get("pagination", {})
            assert pagination.get("sortBy") == "date_sort"
            assert pagination.get("descending") is True
        finally:
            state.file_loaded = original_file_loaded
            state.workouts = original_workouts

    def test_table_rows_per_page_label_prop_is_set(self) -> None:
        """Table should set rows-per-page-label prop for translation."""
        original_file_loaded = state.file_loaded
        original_workouts: Any = state.workouts

        workouts_mock = MagicMock()
        workouts_mock._filter_workouts.return_value = pd.DataFrame(
            [
                {
                    "activityType": "Running",
                    "startDate": pd.Timestamp("2025-09-16"),
                    "duration": 3660.0,
                }
            ]
        )

        table_stub = DummyTable()

        try:
            state.file_loaded = True
            state.workouts = workouts_mock

            with (
                patch("ui.workout_table.ui.table", return_value=table_stub),
                patch("ui.workout_table.create_workout_detail_modal", return_value=lambda _: None),
            ):
                wt.render_workout_table.func()

            assert any("rows-per-page-label" in p for p in table_stub.props_calls)
        finally:
            state.file_loaded = original_file_loaded
            state.workouts = original_workouts

    def test_pagination_label_prop_uses_of_translation(self) -> None:
        """The :pagination-label prop should embed the translated 'of' word."""
        original_file_loaded = state.file_loaded
        original_workouts: Any = state.workouts

        workouts_mock = MagicMock()
        workouts_mock._filter_workouts.return_value = pd.DataFrame(
            [
                {
                    "activityType": "Running",
                    "startDate": pd.Timestamp("2025-09-16"),
                    "duration": 3660.0,
                }
            ]
        )

        table_stub = DummyTable()

        try:
            state.file_loaded = True
            state.workouts = workouts_mock

            with (
                patch("ui.workout_table.ui.table", return_value=table_stub),
                patch("ui.workout_table.create_workout_detail_modal", return_value=lambda _: None),
                patch("ui.workout_table.t", side_effect=lambda msg, **_kw: f"tr:{msg}"),
            ):
                wt.render_workout_table.func()

            pagination_label_props = [p for p in table_stub.props_calls if ":pagination-label" in p]
            assert len(pagination_label_props) == 1
            prop_value = pagination_label_props[0]
            # The prop must declare a three-argument arrow function.
            assert "(a, b, c) =>" in prop_value
            # The translated "of" word must be embedded in the JS arrow function.
            assert "tr:of" in prop_value
        finally:
            state.file_loaded = original_file_loaded
            state.workouts = original_workouts

    def test_no_table_when_file_not_loaded(self) -> None:
        """ui.table should not be created when no file is loaded."""
        original_file_loaded = state.file_loaded

        try:
            state.file_loaded = False

            with (
                patch("ui.workout_table.ui.label", return_value=DummyComponent()),
                patch("ui.workout_table.ui.table") as table_mock,
            ):
                wt.render_workout_table.func()

            table_mock.assert_not_called()
        finally:
            state.file_loaded = original_file_loaded

    def test_open_detail_event_fires_for_known_row_id(self) -> None:
        """Firing 'open_detail' for a known row id should call the open_detail callable."""
        original_file_loaded = state.file_loaded
        original_workouts: Any = state.workouts

        workouts_mock = MagicMock()
        workouts_mock._filter_workouts.return_value = pd.DataFrame(
            [
                {
                    "activityType": "Running",
                    "startDate": pd.Timestamp("2025-09-16"),
                    "duration": 3660.0,
                }
            ]
        )

        table_stub = DummyTable()
        open_detail_calls: list[int] = []

        try:
            state.file_loaded = True
            state.workouts = workouts_mock

            with (
                patch("ui.workout_table.ui.table", return_value=table_stub),
                patch(
                    "ui.workout_table.create_workout_detail_modal",
                    return_value=lambda idx: open_detail_calls.append(idx),
                ),
            ):
                wt.render_workout_table.func()

            # Extract the row id that was built for this row.
            rows = wt._build_workout_rows()
            assert rows, "Expected at least one row from the mock workouts"
            row_id = rows[0]["id"]

            # Fire the event as Quasar would when the button is clicked.
            table_stub.fire("open_detail", row_id)

            assert open_detail_calls == [0]
        finally:
            state.file_loaded = original_file_loaded
            state.workouts = original_workouts

    def test_open_detail_event_ignored_for_unknown_row_id(self) -> None:
        """Firing 'open_detail' for an unknown row id should be a no-op."""
        original_file_loaded = state.file_loaded
        original_workouts: Any = state.workouts

        workouts_mock = MagicMock()
        workouts_mock._filter_workouts.return_value = pd.DataFrame(
            [
                {
                    "activityType": "Running",
                    "startDate": pd.Timestamp("2025-09-16"),
                    "duration": 3660.0,
                }
            ]
        )

        table_stub = DummyTable()
        open_detail_calls: list[int] = []

        try:
            state.file_loaded = True
            state.workouts = workouts_mock

            with (
                patch("ui.workout_table.ui.table", return_value=table_stub),
                patch(
                    "ui.workout_table.create_workout_detail_modal",
                    return_value=lambda idx: open_detail_calls.append(idx),
                ),
            ):
                wt.render_workout_table.func()

            table_stub.fire("open_detail", "nonexistent-id")

            # No calls expected when id is not found.
            assert open_detail_calls == []
        finally:
            state.file_loaded = original_file_loaded
            state.workouts = original_workouts

    def test_table_rows_exclude_modal_payload_fields(self) -> None:
        """Table transport rows should exclude heavy modal-only fields like route payloads."""
        original_file_loaded = state.file_loaded
        original_workouts: Any = state.workouts

        workouts_mock = MagicMock()
        workouts_mock._filter_workouts.return_value = pd.DataFrame(
            [
                {
                    "activityType": "Running",
                    "startDate": pd.Timestamp("2025-09-16"),
                    "duration": 3660.0,
                    "route": object(),
                }
            ]
        )

        table_stub = DummyTable()
        captured_modal_rows: list[dict[str, Any]] = []

        def _capture_modal_rows(rows: list[dict[str, Any]]) -> Any:
            captured_modal_rows.extend(rows)
            return lambda _idx: None

        try:
            state.file_loaded = True
            state.workouts = workouts_mock

            with (
                patch("ui.workout_table.ui.table", return_value=table_stub) as table_mock,
                patch(
                    "ui.workout_table.create_workout_detail_modal", side_effect=_capture_modal_rows
                ),
            ):
                wt.render_workout_table.func()

            rendered_rows = table_mock.call_args.kwargs["rows"]
            assert len(rendered_rows) == 1
            assert "route" not in rendered_rows[0]
            assert captured_modal_rows
            assert "route" in captured_modal_rows[0]
        finally:
            state.file_loaded = original_file_loaded
            state.workouts = original_workouts


class TestSafeFloat:
    """Unit tests for _safe_float() helper."""

    def test_returns_none_for_none(self) -> None:
        """None input should return None."""
        assert wt._safe_float(None) is None

    def test_returns_none_for_non_numeric_string(self) -> None:
        """Non-numeric string should return None (TypeError/ValueError branch)."""
        assert wt._safe_float("not-a-number") is None

    def test_returns_float_for_numeric_string(self) -> None:
        """A numeric string should be converted to float."""
        result = wt._safe_float("3.14")
        assert result == pytest.approx(3.14)

    def test_returns_none_for_nan(self) -> None:
        """float('nan') should return None."""
        assert wt._safe_float(float("nan")) is None


class TestExtractDistanceField:
    """Unit tests for _extract_distance_field() helper."""

    def test_zero_distance_returns_dash(self) -> None:
        """Zero-metre distance should produce '–' as the display string."""
        row = {"distance": 0.0}
        sort_val, display = wt._extract_distance_field(row)
        assert sort_val == pytest.approx(0.0)
        assert display == "–"

    def test_negative_distance_returns_dash(self) -> None:
        """Negative distance should also produce '–'."""
        row = {"distance": -100.0}
        _, display = wt._extract_distance_field(row)
        assert display == "–"

    def test_imperial_distance_uses_miles(self) -> None:
        """distance_unit='mi' should format in miles with 2 decimal places."""
        from units import METERS_TO_MILES

        row = {"distance": 1609.344}  # 1 mile
        _, display = wt._extract_distance_field(row, distance_unit="mi")
        expected = f"{1609.344 * METERS_TO_MILES:.2f} mi"
        assert display == expected


class TestFormatPace:
    """Unit tests for _format_pace()."""

    def test_positive_speed_produces_pace_string(self) -> None:
        """A positive speed should produce a 'mm:ss /km' string."""
        # 10 km/h → 6:00 /km
        result = wt._format_pace(10.0)
        assert result == "6:00 /km"

    def test_zero_speed_returns_dash(self) -> None:
        """Zero speed should return '–'."""
        assert wt._format_pace(0.0) == "–"

    def test_negative_speed_returns_dash(self) -> None:
        """Negative speed should return '–'."""
        assert wt._format_pace(-5.0) == "–"

    def test_fractional_seconds_rounded(self) -> None:
        """Fractional seconds should be rounded to the nearest integer."""
        # 9 km/h → 6.666... min/km → 6:40
        result = wt._format_pace(9.0)
        assert result == "6:40 /km"

    def test_seconds_rollover_increments_minutes(self) -> None:
        """When rounded seconds == 60, minutes should increment and seconds reset."""
        # Craft a speed so that pace_min has fractional seconds that round to 60.
        # pace_min = 60 / speed. We need (pace_min - floor(pace_min)) * 60 ≈ 59.5+
        # speed = 60 / (n + 59.5/60) for some integer n.
        # For n=6: speed = 60 / 6.9916... ≈ 8.582 km/h
        # → pace ≈ 6.9916 min/km → 6 min 59.5 s → rounds to 7:00
        result = wt._format_pace(60.0 / (6 + 59.5 / 60))
        # seconds 59.5 rounds to 60 → should produce 7:00, not 6:60
        assert "60" not in result
        assert result == "7:00 /km"

    def test_imperial_speed_produces_per_mile_pace_string(self) -> None:
        """With distance_unit='mi', pace should be formatted as '… /mi'."""
        # 10 km/h in mph ≈ 6.214 mph → pace ≈ 9:39 /mi
        result = wt._format_pace(10.0, "mi")
        assert result.endswith("/mi")
        # Sanity: pace should be in the right ballpark (between 9:00 and 10:30 /mi)
        minutes_part = int(result.split(":")[0])
        assert 9 <= minutes_part <= 10


class TestNearestVo2Max:
    """Unit tests for _nearest_vo2_max()."""

    def test_returns_dash_when_date_is_none(self) -> None:
        """Should return '–' when workout_date is None."""
        result = wt._nearest_vo2_max(None)
        assert result == "–"

    def test_returns_dash_when_no_vo2_records(self) -> None:
        """Should return '–' when VO2Max records are absent."""
        from app_state import state
        from logic.records_by_type import RecordsByType

        original = state.records_by_type
        try:
            state.records_by_type = RecordsByType(data={})
            result = wt._nearest_vo2_max(pd.Timestamp("2025-01-01"))
        finally:
            state.records_by_type = original
        assert result == "–"

    def test_returns_nearest_record_by_date(self) -> None:
        """Should return the VO2 max value from the nearest-in-time record."""
        from app_state import state
        from logic.records_by_type import RecordsByType

        vo2_df = pd.DataFrame(
            [
                {"startDate": "2025-01-01 10:00:00", "value": 50.0},
                {"startDate": "2025-06-01 10:00:00", "value": 52.0},
            ]
        )
        original = state.records_by_type
        try:
            state.records_by_type = RecordsByType(data={"VO2Max": vo2_df})
            # Workout on 2025-01-02 → nearest is 2025-01-01 record (value 50.0)
            result = wt._nearest_vo2_max(pd.Timestamp("2025-01-02"))
        finally:
            state.records_by_type = original
        assert result == "50.0 mL/min·kg"

    def test_returns_dash_when_nearest_record_has_none_value(self) -> None:
        """Should return '–' when the nearest VO2Max record has a null/NaN value."""
        from app_state import state
        from logic.records_by_type import RecordsByType

        # Record exists but value is None (e.g. exported without measurement)
        vo2_df = pd.DataFrame([{"startDate": "2025-01-01 10:00:00", "value": None}])
        original = state.records_by_type
        try:
            state.records_by_type = RecordsByType(data={"VO2Max": vo2_df})
            result = wt._nearest_vo2_max(pd.Timestamp("2025-01-01"))
        finally:
            state.records_by_type = original
        assert result == "–"

    def test_returns_dash_when_all_dates_are_unparsable(self) -> None:
        """Should return '–' when all startDate values are unparsable (all-NaT)."""
        from app_state import state
        from logic.records_by_type import RecordsByType

        # All startDate values are garbage strings → pd.to_datetime yields all NaT.
        vo2_df = pd.DataFrame(
            [
                {"startDate": "not-a-date", "value": 50.0},
                {"startDate": "also-not-a-date", "value": 52.0},
            ]
        )
        original = state.records_by_type
        try:
            state.records_by_type = RecordsByType(data={"VO2Max": vo2_df})
            result = wt._nearest_vo2_max(pd.Timestamp("2025-01-01"))
        finally:
            state.records_by_type = original
        assert result == "–"
