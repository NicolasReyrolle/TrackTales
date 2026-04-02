"""Tests for UI formatting in layout refresh."""

from collections.abc import Coroutine
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd

from app_state import state
from logic.workout_manager import WorkoutManager
from ui.helpers import format_integer
from ui.layout import refresh_data


class _DummyWorkouts(WorkoutManager):
    def get_count(
        self,
        activity_type: str = "All",
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
    ) -> int:
        return 12345

    def get_total_distance(
        self,
        activity_type: str = "All",
        unit: str = "km",
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
    ) -> int:
        return 67890

    def get_total_duration(
        self,
        activity_type: str = "All",
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
    ) -> int:
        return 24680

    def get_total_elevation(
        self,
        activity_type: str = "All",
        unit: str = "m",
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
    ) -> int:
        return 13579

    def get_total_calories(
        self,
        activity_type: str = "All",
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
    ) -> int:
        return 98765

    def get_longest_workout(
        self,
        activity_types: list[str],
        unit: str = "km",
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
    ) -> float:
        return 0.0

    def get_longest_workout_details(
        self,
        activity_types: list[str],
        unit: str = "km",
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
    ) -> dict[str, Any] | None:
        """Return no longest workout details in this dummy implementation."""
        return None

    def get_distance_bounds(
        self,
        unit: str = "km",
        activity_type: str = "All",
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
    ) -> tuple[float, float]:
        return 0.0, 0.0

    def get_duration_bounds(
        self,
        unit: str = "min",
        activity_type: str = "All",
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
    ) -> tuple[float, float]:
        return 0.0, 0.0


def test_refresh_data_formats_metrics_display() -> None:
    """refresh_data should populate formatted display values."""
    original_workouts: Any = state.workouts

    try:
        state.workouts = _DummyWorkouts()
        state.selected_activity_type = "All"

        # Mock the refresh calls to avoid event loop issues in testing
        mock_refresh_data()

        assert state.metrics_display["count"] == format_integer(12345)
        assert state.metrics_display["distance"] == format_integer(67890)
        assert state.metrics_display["duration"] == format_integer(24680)
        assert state.metrics_display["elevation"] == format_integer(13579)
        assert state.metrics_display["calories"] == format_integer(98765)
    finally:
        state.workouts = original_workouts


def mock_refresh_data() -> None:
    """Helper to call refresh_data with necessary UI patches."""
    with patch("ui.layout.render_activity_graphs.refresh"):
        with patch("ui.layout.render_trends_graphs.refresh"):
            with patch("ui.layout.render_health_data_tab.refresh"):
                with patch("ui.layout.render_best_segments_tab.refresh"):
                    with patch("ui.layout.render_distance_range_selector.refresh"):
                        with patch("ui.layout.render_duration_range_selector.refresh"):
                            with patch("ui.layout.render_workout_table.refresh"):
                                refresh_data()


def test_refresh_data_passes_date_range_to_workouts() -> None:
    """refresh_data should forward date range filters to workout methods."""
    original_workouts: Any = state.workouts
    original_date_range = state.date_range_text
    original_activity = state.selected_activity_type

    workouts_mock = MagicMock()
    workouts_mock.get_count.return_value = 1
    workouts_mock.get_total_distance.return_value = 2
    workouts_mock.get_total_duration.return_value = 3
    workouts_mock.get_total_elevation.return_value = 4
    workouts_mock.get_total_calories.return_value = 5
    workouts_mock.get_longest_workout.return_value = 0.0
    workouts_mock.get_longest_workout_details.return_value = None
    workouts_mock.get_distance_bounds.return_value = (0.0, 0.0)
    workouts_mock.get_duration_bounds.return_value = (0.0, 0.0)

    try:
        state.workouts = workouts_mock
        state.selected_activity_type = "Running"
        state.date_range_text = "2024/02/01 - 2024/02/01"

        expected_start = datetime(2024, 2, 1)
        expected_end = datetime(2024, 2, 1)

        mock_refresh_data()

        workouts_mock.get_count.assert_called_once_with("Running", expected_start, expected_end)
        workouts_mock.get_total_distance.assert_called_once_with(
            "Running", unit="km", start_date=expected_start, end_date=expected_end
        )
        workouts_mock.get_total_duration.assert_called_once_with(
            "Running", start_date=expected_start, end_date=expected_end
        )
        workouts_mock.get_total_elevation.assert_called_once_with(
            "Running", unit="m", start_date=expected_start, end_date=expected_end
        )
        workouts_mock.get_total_calories.assert_called_once_with(
            "Running", start_date=expected_start, end_date=expected_end
        )
    finally:
        state.workouts = original_workouts
        state.date_range_text = original_date_range
        state.selected_activity_type = original_activity


def test_refresh_data_triggers_best_segments_load_when_tab_selected() -> None:
    """refresh_data should schedule async best-segments loading from the active tab."""
    original_workouts: Any = state.workouts
    original_selected_tab = state.selected_main_tab
    original_rows = state.best_segments_rows
    original_loaded = state.best_segments_loaded

    workouts_mock = MagicMock()
    workouts_mock.get_count.return_value = 1
    workouts_mock.get_total_distance.return_value = 2
    workouts_mock.get_total_duration.return_value = 3
    workouts_mock.get_total_elevation.return_value = 4
    workouts_mock.get_total_calories.return_value = 5
    workouts_mock.get_longest_workout.return_value = 0.0
    workouts_mock.get_longest_workout_details.return_value = None
    workouts_mock.get_distance_bounds.return_value = (0.0, 0.0)
    workouts_mock.get_duration_bounds.return_value = (0.0, 0.0)

    try:
        state.workouts = workouts_mock
        state.selected_main_tab = "best_segments"
        state.best_segments_rows = [{"distance": "old"}]
        state.best_segments_loaded = True

        with patch("ui.layout.render_activity_graphs.refresh"):
            with patch("ui.layout.render_trends_graphs.refresh"):
                with patch("ui.layout.render_health_data_tab.refresh"):
                    with patch("ui.layout.render_best_segments_tab.refresh"):
                        with patch("ui.layout.render_distance_range_selector.refresh"):
                            with patch("ui.layout.render_duration_range_selector.refresh"):
                                with patch("ui.layout.render_workout_table.refresh"):
                                    with patch(
                                        "ui.layout.load_best_segments_data", new=AsyncMock()
                                    ):
                                        with patch(
                                            "ui.layout.asyncio.create_task"
                                        ) as create_task_mock:

                                            def _close_coro(
                                                coro: Coroutine[Any, Any, None],
                                            ) -> None:
                                                coro.close()

                                            create_task_mock.side_effect = _close_coro
                                            refresh_data()

        assert state.best_segments_rows == []
        assert state.best_segments_loaded is False
        create_task_mock.assert_called_once()
        assert workouts_mock.get_longest_workout_details.call_count == 3
    finally:
        state.workouts = original_workouts
        state.selected_main_tab = original_selected_tab
        state.best_segments_rows = original_rows
        state.best_segments_loaded = original_loaded
