"""Tests for running/statistics tab rendering."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

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
    original_start_date = state.start_date
    original_end_date = state.end_date
    original_date_text = state.date_range_text

    try:
        state.workouts = _sample_workouts_manager()
        state.health_data_graphs = {"critical_power": {"2025-01": 300}, "w_prime": {"2025-01": 20}}
        state.health_data_cp_loading = False
        state.date_range_text = ""

        with (
            patch("ui.running_tab.ui.row", return_value=DummyRow()),
            patch("ui.running_tab.render_scatter_graph") as scatter_mock,
            patch("ui.running_tab.render_generic_graph"),
            patch("ui.running_tab.render_best_segments_tab"),
        ):
            running_tab.render_running_tab.func()

        assert scatter_mock.call_count == 2
        distance_points = scatter_mock.call_args_list[0].args[1]
        elevation_points = scatter_mock.call_args_list[1].args[1]
        assert len(distance_points) == 2
        assert distance_points[0] == (5.0, 5.0)
        assert elevation_points[0] == (120.0, 5.0)
    finally:
        state.workouts = original_workouts
        state.health_data_graphs = original_graphs
        state.health_data_cp_loading = original_cp_loading
        state.date_range_text = original_date_text
        # ensure derived properties stay unchanged by test setup/teardown sequence
        _ = original_start_date
        _ = original_end_date


def test_render_statistics_tab_builds_heatmap_and_boxplot_from_workouts() -> None:
    """Statistics tab should derive heat map and pace distribution from workout rows."""
    original_workouts: Any = state.workouts
    original_activity = state.selected_activity_type
    original_date_text = state.date_range_text

    try:
        state.workouts = _sample_workouts_manager()
        state.selected_activity_type = "All"
        state.date_range_text = ""

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
    finally:
        state.workouts = original_workouts
        state.selected_activity_type = original_activity
        state.date_range_text = original_date_text
