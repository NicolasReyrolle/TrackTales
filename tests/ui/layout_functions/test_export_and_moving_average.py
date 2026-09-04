"""Tests for ui.layout export handlers and moving-average helper."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app_state import state
from ui import layout
from ui.helpers import calculate_moving_average


class TestExportHandlers:
    """Tests for export handler functions."""

    def test_handle_json_export_calls_export_and_download(self) -> None:
        """Test that handle_json_export calls the correct methods."""
        original_workouts: Any = state.workouts
        original_activity = state.selected_activity_type
        original_date_range = state.date_range_text

        workouts_mock = MagicMock()
        workouts_mock.export_to_json.return_value = '{"test": "data"}'

        try:
            state.workouts = workouts_mock
            state.selected_activity_type = "Running"
            state.date_range_text = "2024-02-01 - 2024-02-29"
            expected_start = datetime(2024, 2, 1)
            expected_end = datetime(2024, 2, 29)

            with patch("ui.layout.ui.download") as download_mock:
                layout.handle_json_export()

            workouts_mock.export_to_json.assert_called_once_with(
                activity_type="Running",
                start_date=expected_start,
                end_date=expected_end,
            )
            download_mock.assert_called_once_with(b'{"test": "data"}', "apple_health_export.json")
        finally:
            state.workouts = original_workouts
            state.selected_activity_type = original_activity
            state.date_range_text = original_date_range

    def test_handle_csv_export_calls_export_and_download(self) -> None:
        """Test that handle_csv_export calls the correct methods."""
        original_workouts: Any = state.workouts
        original_activity = state.selected_activity_type
        original_date_range = state.date_range_text

        workouts_mock = MagicMock()
        workouts_mock.export_to_csv.return_value = "header1,header2\nvalue1,value2"

        try:
            state.workouts = workouts_mock
            state.selected_activity_type = "Cycling"
            state.date_range_text = "2024-03-01 - 2024-03-31"
            expected_start = datetime(2024, 3, 1)
            expected_end = datetime(2024, 3, 31)

            with patch("ui.layout.ui.download") as download_mock:
                layout.handle_csv_export()

            workouts_mock.export_to_csv.assert_called_once_with(
                activity_type="Cycling",
                start_date=expected_start,
                end_date=expected_end,
            )
            download_mock.assert_called_once_with(
                b"header1,header2\nvalue1,value2", "apple_health_export.csv"
            )
        finally:
            state.workouts = original_workouts
            state.selected_activity_type = original_activity
            state.date_range_text = original_date_range

    def test_handle_markdown_export_calls_export_and_download(self) -> None:
        original_workouts: Any = state.workouts
        original_activity = state.selected_activity_type
        original_date_range = state.date_range_text

        workouts_mock = MagicMock()
        workouts_mock.export_to_markdown.return_value = "# report"

        try:
            state.workouts = workouts_mock
            state.selected_activity_type = "Running"
            state.date_range_text = "2024-03-01 - 2024-03-31"

            with patch("ui.layout.ui.download") as download_mock:
                layout.handle_markdown_export()

            workouts_mock.export_to_markdown.assert_called_once_with(
                activity_type="Running",
                start_date=datetime(2024, 3, 1),
                end_date=datetime(2024, 3, 31),
                distance_unit="km",
            )
            download_mock.assert_called_once_with(b"# report", "tracktales_analytics_report.md")
        finally:
            state.workouts = original_workouts
            state.selected_activity_type = original_activity
            state.date_range_text = original_date_range


class TestCalculateMovingAverage:
    """Tests for calculate_moving_average function."""

    def test_calculate_moving_average_with_small_list(self) -> None:
        """Test moving average with list smaller than window size."""
        y_values = [1, 2, 3, 4, 5]
        result = calculate_moving_average(y_values, window_size=12)

        assert result == [1.0, 1.5, 2.0, 2.5, 3.0]

    def test_calculate_moving_average_with_exact_window_size(self) -> None:
        """Test moving average with list exactly matching window size."""
        y_values = [10, 20, 30, 40, 50]
        result = calculate_moving_average(y_values, window_size=5)

        assert result[0] == pytest.approx(10.0, abs=1e-9)  # type: ignore[arg-type]
        assert result[1] == pytest.approx(15.0, abs=1e-9)  # type: ignore[arg-type]
        assert result[2] == pytest.approx(20.0, abs=1e-9)  # type: ignore[arg-type]
        assert result[3] == pytest.approx(25.0, abs=1e-9)  # type: ignore[arg-type]
        assert result[4] == pytest.approx(30.0, abs=1e-9)  # type: ignore[arg-type]

    def test_calculate_moving_average_with_larger_list(self) -> None:
        """Test moving average with list larger than window size."""
        y_values = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140]
        result = calculate_moving_average(y_values, window_size=3)

        assert result[0] == pytest.approx(10.0, abs=1e-9)  # type: ignore[arg-type]
        assert result[1] == pytest.approx(15.0, abs=1e-9)  # type: ignore[arg-type]
        assert result[2] == pytest.approx(20.0, abs=1e-9)  # type: ignore[arg-type]
        assert result[3] == pytest.approx(30.0, abs=1e-9)  # type: ignore[arg-type]
        assert result[4] == pytest.approx(40.0, abs=1e-9)  # type: ignore[arg-type]
        assert len(result) == len(y_values)

    def test_calculate_moving_average_with_default_window(self) -> None:
        """Test moving average with default window size of 12."""
        y_values = list(range(1, 25))
        result = calculate_moving_average(y_values)

        assert result[0] == pytest.approx(1.0, abs=1e-9)  # type: ignore[arg-type]
        assert result[1] == pytest.approx(1.5, abs=1e-9)  # type: ignore[arg-type]
        assert result[10] == pytest.approx(6.0, abs=1e-9)  # type: ignore[arg-type]
        expected_avg = sum(range(1, 13)) / 12
        assert result[11] == round(expected_avg, 2)

    def test_calculate_moving_average_with_constant_values(self) -> None:
        """Test moving average with all constant values."""
        y_values = [50] * 20
        result = calculate_moving_average(y_values, window_size=5)

        assert all(v == pytest.approx(50.0, abs=1e-9) for v in result)  # type: ignore[arg-type]

    def test_calculate_moving_average_with_empty_list(self) -> None:
        """Test moving average with empty list."""
        y_values: list[int] = []
        result = calculate_moving_average(y_values, window_size=12)

        assert result == []

    def test_calculate_moving_average_with_single_value(self) -> None:
        """Test moving average with single value."""
        y_values = [42]
        result = calculate_moving_average(y_values, window_size=12)

        assert result == [42.0]
