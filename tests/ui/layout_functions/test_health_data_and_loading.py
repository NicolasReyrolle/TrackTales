"""Tests for ui.layout health-data rendering and workout-file loading helpers."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock, patch
from zipfile import ZipFile

import pandas as pd
import pytest

from app_state import state
from ui import layout

from ._helpers import DummyRow, translated_message


class TestRenderHealthDataTab:
    """Tests for render_health_data_tab behavior."""

    def test_render_health_data_tab_shows_placeholder_when_not_loaded(self) -> None:
        """Tab should show a lightweight placeholder before lazy loading runs."""
        original_loading = state.health_data_loading
        original_loaded = state.health_data_loaded

        try:
            state.health_data_loading = False
            state.health_data_loaded = False

            with (
                patch("ui.layout.ui.label") as label_mock,
                patch("ui.layout.render_generic_graph") as render_generic_graph_mock,
            ):
                layout.render_health_data_tab.func()

            render_generic_graph_mock.assert_not_called()
            assert any(
                "Open this tab to load health data" in str(call.args[0])
                for call in label_mock.call_args_list
                if call.args
            )
        finally:
            state.health_data_loading = original_loading
            state.health_data_loaded = original_loaded

    def test_render_health_data_tab_shows_loading_state(self) -> None:
        """Tab should render spinner while lazy loading is in progress."""
        original_loading = state.health_data_loading
        original_loaded = state.health_data_loaded

        try:
            state.health_data_loading = True
            state.health_data_loaded = False

            with (
                patch("ui.layout.ui.row", return_value=DummyRow()),
                patch("ui.layout.ui.spinner") as spinner_mock,
                patch("ui.layout.ui.label") as label_mock,
                patch("ui.layout.render_generic_graph") as render_generic_graph_mock,
            ):
                layout.render_health_data_tab.func()

            spinner_mock.assert_called_once()
            render_generic_graph_mock.assert_not_called()
            assert any(
                "Loading health data" in str(call.args[0])
                for call in label_mock.call_args_list
                if call.args
            )
        finally:
            state.health_data_loading = original_loading
            state.health_data_loaded = original_loaded

    def test_render_health_data_tab_uses_cached_graphs(self) -> None:
        """Loaded tab should render graphs from cached series without recomputation."""
        original_loading = state.health_data_loading
        original_loaded = state.health_data_loaded
        original_graphs = state.health_data_graphs

        try:
            state.health_data_loading = False
            state.health_data_loaded = True
            state.health_data_graphs = {
                "heart_rate": {"2025-01": 67.0},
                "body_mass": {"2025-01": 70.5},
                "vo2_max": {"2025-01": 51.2},
                "critical_power": {"2025-01": None},
                "w_prime": {"2025-01": None},
            }

            with (
                patch("ui.layout.ui.row", return_value=DummyRow()),
                patch("ui.layout.render_generic_graph") as render_generic_graph_mock,
            ):
                layout.render_health_data_tab.func()

            cp_call = next(
                call
                for call in render_generic_graph_mock.call_args_list
                if call.args and call.args[0] == "Critical Power (CP) over time"
            )
            assert cp_call.args[1] == {"2025-01": None}
        finally:
            state.health_data_loading = original_loading
            state.health_data_loaded = original_loaded
            state.health_data_graphs = original_graphs


class TestLoadWorkoutsFromFile:
    """Tests for load_workouts_from_file function."""

    def test_load_workouts_from_file_with_valid_zip(self, tmp_path: Path) -> None:
        """Test loading workouts from a valid ZIP file."""
        zip_path = tmp_path / "test_export.zip"
        xml_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<HealthData>
    <Workout workoutActivityType="HKWorkoutActivityTypeRunning"
             startDate="2024-01-01 10:00:00 +0000"
             endDate="2024-01-01 11:00:00 +0000"
             duration="60"
             totalDistance="5.0"
             totalEnergyBurned="300"/>
</HealthData>
"""
        with ZipFile(zip_path, "w") as zf:
            zf.writestr("apple_health_export/export.xml", xml_content)

        workouts, activity_options, _ = layout.load_workouts_from_file(str(zip_path))

        assert workouts is not None
        assert workouts.get_count() > 0
        assert isinstance(activity_options, list)
        assert "All" in activity_options

    def test_load_workouts_from_file_uses_context_manager(self, tmp_path: Path) -> None:
        """Test that load_workouts_from_file uses ExportParser as context manager."""
        zip_path = tmp_path / "test_export.zip"
        xml_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<HealthData>
    <Workout workoutActivityType="HKWorkoutActivityTypeRunning"
             startDate="2024-01-01 10:00:00 +0000"
             endDate="2024-01-01 11:00:00 +0000"
             duration="60"/>
</HealthData>
"""
        with ZipFile(zip_path, "w") as zf:
            zf.writestr("apple_health_export/export.xml", xml_content)

        with patch("ui.layout.ExportParser") as parser_class_mock:
            parser_instance_mock = MagicMock()
            parser_instance_mock.parse.return_value.workouts = pd.DataFrame()
            parser_instance_mock.parse.return_value.records_by_type = {}
            parser_class_mock.return_value.__enter__.return_value = parser_instance_mock
            parser_class_mock.return_value.__exit__.return_value = None

            layout.load_workouts_from_file(str(zip_path))

            parser_class_mock.return_value.__enter__.assert_called_once()
            parser_class_mock.return_value.__exit__.assert_called_once()
            parser_instance_mock.parse.assert_called_once_with(str(zip_path))

    def test_load_workouts_from_file_creates_workout_manager(self, tmp_path: Path) -> None:
        """Test that load_workouts_from_file creates a WorkoutManager instance."""
        zip_path = tmp_path / "test_export.zip"
        xml_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<HealthData>
    <Workout workoutActivityType="HKWorkoutActivityTypeRunning"
             startDate="2024-01-01 10:00:00 +0000"
             endDate="2024-01-01 11:00:00 +0000"
             duration="60"/>
</HealthData>
"""
        with ZipFile(zip_path, "w") as zf:
            zf.writestr("apple_health_export/export.xml", xml_content)

        with patch("ui.layout.WorkoutManager") as wm_class_mock:
            wm_instance_mock = MagicMock()
            wm_instance_mock.get_activity_types.return_value = []
            wm_class_mock.return_value = wm_instance_mock

            workouts, activity_options, _ = layout.load_workouts_from_file(str(zip_path))

            wm_class_mock.assert_called_once()
            assert workouts == wm_instance_mock
            assert activity_options == ["All"]

    def test_load_workouts_from_file_reports_processed_progress_messages(self) -> None:
        """Progress callback should receive updates when parser reports processed workouts."""

        events: list[tuple[int, str]] = []

        with patch("ui.layout.ExportParser") as parser_class_mock:
            parser_instance_mock = MagicMock()

            def _parse_side_effect(_file_path: str) -> Any:
                parser_cb = parser_class_mock.call_args.kwargs["progress_callback"]
                parser_cb("Processed 100 workouts...")
                return SimpleNamespace(workouts=pd.DataFrame(), records_by_type={})

            parser_instance_mock.parse.side_effect = _parse_side_effect
            parser_class_mock.return_value.__enter__.return_value = parser_instance_mock
            parser_class_mock.return_value.__exit__.return_value = None

            with patch("ui.layout.WorkoutManager") as wm_class_mock:
                wm_instance_mock = MagicMock()
                wm_instance_mock.get_activity_types.return_value = []
                wm_class_mock.return_value = wm_instance_mock

                layout.load_workouts_from_file(
                    "dummy.zip",
                    progress_callback=lambda progress, message: events.append((progress, message)),
                )

        assert any(msg.startswith("Processed 100 workouts") for _progress, msg in events)
        assert any(progress == 22 for progress, msg in events if msg.startswith("Processed "))

    def test_load_workouts_from_file_translates_parser_progress_messages(self) -> None:
        """Parser progress text should be translated before reaching UI callback."""

        events: list[tuple[int, str]] = []

        with patch("ui.layout.t", side_effect=translated_message):
            with patch("ui.helpers.translate", side_effect=translated_message):
                with patch("ui.layout.ExportParser") as parser_class_mock:
                    parser_instance_mock = MagicMock()

                    def _parse_side_effect(_file_path: str) -> Any:
                        parser_cb = parser_class_mock.call_args.kwargs["progress_callback"]
                        parser_cb("Processed 3 workouts...")
                        return SimpleNamespace(workouts=pd.DataFrame(), records_by_type={})

                    parser_instance_mock.parse.side_effect = _parse_side_effect
                    parser_class_mock.return_value.__enter__.return_value = parser_instance_mock
                    parser_class_mock.return_value.__exit__.return_value = None

                    with patch("ui.layout.WorkoutManager") as wm_class_mock:
                        wm_instance_mock = MagicMock()
                        wm_instance_mock.get_activity_types.return_value = []
                        wm_class_mock.return_value = wm_instance_mock

                        layout.load_workouts_from_file(
                            "dummy.zip",
                            progress_callback=lambda progress, message: events.append(
                                (progress, message)
                            ),
                        )

        assert any(msg == "tr:Processed 3 workouts..." for _progress, msg in events)


class TestToJsonSafe:
    """Tests for the _to_json_safe helper (Period-key normalisation and value coercion)."""

    def test_string_keys_are_preserved(self) -> None:
        """String keys should pass through unchanged."""
        result = layout._to_json_safe({"2025-01": 60.0, "2025-02": 70})
        assert list(result.keys()) == ["2025-01", "2025-02"]

    def test_period_keys_are_converted_to_str(self) -> None:
        """pandas Period keys must be converted to strings so output is JSON-safe."""
        period_key = pd.Period("2025-01", freq="M")
        result = layout._to_json_safe({period_key: 55.0})  # type: ignore[dict-item]
        assert "2025-01" in result
        json.dumps(result)  # must not raise

    def test_none_values_are_preserved(self) -> None:
        """None values must remain None (chart gap markers)."""
        result = layout._to_json_safe({"2025-01": None})
        assert result["2025-01"] is None

    def test_float_nan_is_coerced_to_none(self) -> None:
        """float NaN must be replaced with None for JSON safety."""
        result = layout._to_json_safe({"2025-01": float("nan")})
        assert result["2025-01"] is None
        json.dumps(result)  # must not raise

    def test_pandas_na_is_coerced_to_none(self) -> None:
        """pd.NA must be replaced with None (isinstance check uses pd.isna)."""
        result = layout._to_json_safe({"2025-01": pd.NA})
        assert result["2025-01"] is None
        json.dumps(result)  # must not raise

    def test_non_numeric_string_value_is_coerced_to_none(self) -> None:
        """Non-numeric, non-None values must be coerced to None."""
        result = layout._to_json_safe({"2025-01": "unexpected"})
        assert result["2025-01"] is None

    def test_valid_numeric_values_are_retained(self) -> None:
        """int and float values must be retained as-is."""
        result = layout._to_json_safe({"a": 42, "b": 3.14})
        assert result["a"] == 42
        assert result["b"] == pytest.approx(3.14)
        json.dumps(result)  # must not raise

    def test_output_is_always_json_serialisable(self) -> None:
        """Mixed input with Period keys, NaN, None, valid numbers must be JSON-safe."""
        p1 = pd.Period("2025-Q1", freq="Q")
        p2 = pd.Period("2025-Q2", freq="Q")
        mixed = cast(dict[Any, Any], {p1: 300.0, p2: float("nan"), "2025-Q3": None, "2025-Q4": 250})  # type: ignore[dict-item]
        result = layout._to_json_safe(mixed)
        serialised = json.dumps(result)
        parsed = json.loads(serialised)
        assert parsed[str(p1)] == pytest.approx(300.0)
        assert parsed[str(p2)] is None
        assert parsed["2025-Q3"] is None
        assert parsed["2025-Q4"] == 250
