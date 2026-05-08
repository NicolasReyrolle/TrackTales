"""Tests for running/statistics tab rendering."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pandas as pd

from app_state import state
from logic.workout_manager import WorkoutManager
from ui import running_tab, statistics_tab

from ._helpers import DummyRow


def _sample_workouts_manager() -> WorkoutManager:
    return WorkoutManager(
        pd.DataFrame(
            [
                {
                    "activityType": "Running",
                    "startDate": pd.Timestamp("2025-01-06 08:15:00"),
                    "distance": 5000.0,
                    "duration": 1500.0,
                    "ElevationAscended": 120.0,
                },
                {
                    "activityType": "Running",
                    "startDate": pd.Timestamp("2025-01-07 18:30:00"),
                    "distance": 10000.0,
                    "duration": 3300.0,
                    "ElevationAscended": 80.0,
                },
                {
                    "activityType": "Walking",
                    "startDate": pd.Timestamp("2025-01-08 12:00:00"),
                    "distance": 3000.0,
                    "duration": 2100.0,
                    "ElevationAscended": 30.0,
                },
            ]
        )
    )


def test_render_running_tab_builds_scatter_data_from_workouts() -> None:
    """Running tab should compute scatter points from running workout data."""
    original_workouts: Any = state.workouts
    original_graphs = state.health_data_graphs
    original_cp_loading = state.health_data_cp_loading
    original_date_text = state.date_range_text
    original_selected_tab = state.selected_main_tab

    try:
        state.workouts = _sample_workouts_manager()
        state.health_data_graphs = {"critical_power": {"2025-01": 300}, "w_prime": {"2025-01": 20}}
        state.health_data_cp_loading = False
        state.date_range_text = ""
        state.selected_main_tab = "running"

        with (
            patch("ui.running_tab.ui.row", return_value=DummyRow()),
            patch("ui.running_tab.render_scatter_graph") as scatter_mock,
            patch("ui.running_tab.render_running_health_graphs"),
            patch("ui.running_tab.render_best_segments_tab"),
        ):
            running_tab.render_running_tab.func()

        assert scatter_mock.call_count == 2
        distance_points = scatter_mock.call_args_list[0].args[1]
        elevation_points = scatter_mock.call_args_list[1].args[1]
        assert len(distance_points) == 2
        assert distance_points[0][:2] == (5.0, 5.0)
        assert elevation_points[0][:2] == (120.0, 5.0)
        assert distance_points[0][2] == "01/06/2025"
        assert distance_points[0][3] == 0
    finally:
        state.workouts = original_workouts
        state.health_data_graphs = original_graphs
        state.health_data_cp_loading = original_cp_loading
        state.date_range_text = original_date_text
        state.selected_main_tab = original_selected_tab


def test_render_statistics_tab_builds_heatmap_and_boxplot_from_workouts() -> None:
    """Statistics tab should derive heat map and pace distribution from workout rows."""
    original_workouts: Any = state.workouts
    original_activity = state.selected_activity_type
    original_date_text = state.date_range_text
    original_selected_tab = state.selected_main_tab

    try:
        state.workouts = _sample_workouts_manager()
        state.selected_activity_type = "All"
        state.date_range_text = ""
        state.selected_main_tab = "statistics"

        with (
            patch("ui.statistics_tab.ui.row", return_value=DummyRow()),
            patch("ui.statistics_tab.render_heat_map_graph") as heatmap_mock,
            patch("ui.statistics_tab.render_box_plot_graph") as box_mock,
        ):
            statistics_tab.render_statistics_tab.func()

        heatmap_values = heatmap_mock.call_args.args[3]
        boxplot_values = box_mock.call_args.args[1]
        assert heatmap_values
        assert "Running" in boxplot_values
        assert len(boxplot_values["Running"]) == 2
        assert heatmap_mock.call_args.kwargs["x_axis_name"] == "Hour of day"
        assert heatmap_mock.call_args.kwargs["y_axis_name"] == "Day of week"
        assert heatmap_mock.call_args.args[2] == ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        assert heatmap_mock.call_args.kwargs["fullscreen_y_labels"] == [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]
    finally:
        state.workouts = original_workouts
        state.selected_activity_type = original_activity
        state.date_range_text = original_date_text
        state.selected_main_tab = original_selected_tab


def test_render_running_tab_shows_health_loading_before_cp_graphs() -> None:
    """Running tab should show loading state while health data is still loading."""
    original_loading = state.health_data_loading
    original_loaded = state.health_data_loaded
    original_cp_loading = state.health_data_cp_loading
    original_workouts: Any = state.workouts
    original_date_text = state.date_range_text
    original_selected_tab = state.selected_main_tab

    try:
        state.health_data_loading = True
        state.health_data_loaded = False
        state.health_data_cp_loading = False
        state.workouts = _sample_workouts_manager()
        state.date_range_text = ""
        state.selected_main_tab = "running"

        with (
            patch("ui.running_tab.ui.row", return_value=DummyRow()),
            patch("ui.running_tab.ui.spinner") as spinner_mock,
            patch("ui.running_tab.ui.label") as label_mock,
            patch("ui.running_tab.render_scatter_graph"),
            patch("ui.running_tab.render_running_health_graphs"),
            patch("ui.running_tab.render_best_segments_tab"),
        ):
            running_tab.render_running_tab.func()

        spinner_mock.assert_not_called()
        label_mock.assert_not_called()
    finally:
        state.health_data_loading = original_loading
        state.health_data_loaded = original_loaded
        state.health_data_cp_loading = original_cp_loading
        state.workouts = original_workouts
        state.date_range_text = original_date_text
        state.selected_main_tab = original_selected_tab


def test_running_tab_defers_workout_detail_until_click() -> None:
    """Workout rows/modal should be built only when clicking a scatter point."""
    original_workouts: Any = state.workouts
    original_selected_tab = state.selected_main_tab
    original_date_text = state.date_range_text

    captured_on_click: Any = None

    def _capture_scatter(*_args: Any, **kwargs: Any) -> None:
        nonlocal captured_on_click
        captured_on_click = kwargs["on_point_click"]

    try:
        state.workouts = _sample_workouts_manager()
        state.selected_main_tab = "running"
        state.date_range_text = ""

        with (
            patch("ui.running_tab.ui.row", return_value=DummyRow()),
            patch("ui.running_tab.render_scatter_graph", side_effect=_capture_scatter),
            patch("ui.running_tab.render_running_health_graphs"),
            patch("ui.running_tab.render_best_segments_tab"),
            patch(
                "ui.running_tab._build_workout_rows", return_value=[{"workout_index": 0}]
            ) as build_rows_mock,
            patch("ui.running_tab.create_workout_detail_modal") as create_modal_mock,
        ):
            open_detail_mock = MagicMock()
            create_modal_mock.return_value = open_detail_mock
            running_tab.render_running_tab.func()
            build_rows_mock.assert_not_called()
            assert callable(captured_on_click)
            captured_on_click(0)
            build_rows_mock.assert_called_once()
            captured_on_click("0")
            assert build_rows_mock.call_count == 1
            create_modal_mock.assert_called_once()
            assert open_detail_mock.call_count == 2
    finally:
        state.workouts = original_workouts
        state.selected_main_tab = original_selected_tab
        state.date_range_text = original_date_text


def test_render_running_health_graphs_shows_loading_state() -> None:
    """Running health section should show loading spinner while health data loads."""
    original_loading = state.health_data_loading
    original_loaded = state.health_data_loaded
    original_cp_loading = state.health_data_cp_loading

    try:
        state.health_data_loading = True
        state.health_data_loaded = False
        state.health_data_cp_loading = False

        with (
            patch("ui.running_tab.ui.row", return_value=DummyRow()),
            patch("ui.running_tab.ui.spinner") as spinner_mock,
            patch("ui.running_tab.ui.label") as label_mock,
            patch("ui.running_tab.render_generic_graph") as generic_mock,
        ):
            running_tab.render_running_health_graphs.func()

        spinner_mock.assert_called_once()
        generic_mock.assert_not_called()
        assert any(
            "Loading health data" in str(call.args[0])
            for call in label_mock.call_args_list
            if call.args
        )
    finally:
        state.health_data_loading = original_loading
        state.health_data_loaded = original_loaded
        state.health_data_cp_loading = original_cp_loading
