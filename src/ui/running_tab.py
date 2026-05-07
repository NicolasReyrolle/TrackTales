"""Running tab UI rendering."""

from __future__ import annotations

import pandas as pd
from nicegui import ui

from app_state import get_distance_unit, get_elevation_unit, state
from i18n import t
from ui.best_segments import render_best_segments_tab
from ui.charts import render_generic_graph, render_scatter_graph
from ui.css import ROW_CENTERED_CLASSES


def _filter_running_workouts() -> pd.DataFrame:
    workouts = state.workouts.get_workouts()
    if workouts.empty:
        return workouts
    if "activityType" in workouts.columns:
        workouts = workouts[
            workouts["activityType"].astype(str).str.contains("running", case=False)
        ]
    if "startDate" in workouts.columns:
        if state.start_date is not None:
            workouts = workouts.loc[workouts["startDate"] >= pd.Timestamp(state.start_date)]
        if state.end_date is not None:
            end_timestamp = pd.Timestamp(state.end_date)
            if end_timestamp == end_timestamp.normalize():
                workouts = workouts.loc[
                    workouts["startDate"] < end_timestamp + pd.Timedelta(days=1)
                ]
            else:
                workouts = workouts.loc[workouts["startDate"] <= end_timestamp]
    return workouts


def _build_scatter_points(
    workouts: pd.DataFrame,
    *,
    distance_unit: str,
    elevation_unit: str,
) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
    if workouts.empty or "distance" not in workouts.columns or "duration" not in workouts.columns:
        return [], []

    filtered = workouts[
        workouts["distance"].notna()
        & workouts["duration"].notna()
        & (workouts["distance"] > 0)
        & (workouts["duration"] > 0)
    ].copy()
    if filtered.empty:
        return [], []

    filtered["distance_converted"] = (
        filtered["distance"]
        .astype(float)
        .apply(lambda value: state.workouts.convert_distance(distance_unit, value))
    )
    filtered["pace"] = filtered["duration"].astype(float).div(60.0) / filtered["distance_converted"]
    filtered["elevation_converted"] = (
        filtered["ElevationAscended"]
        .astype(float)
        .apply(lambda value: state.workouts.convert_distance(elevation_unit, value))
        if "ElevationAscended" in filtered.columns
        else 0.0
    )

    distance_vs_pace = [
        (round(distance, 2), round(pace, 2))
        for distance, pace in zip(
            filtered["distance_converted"].astype(float),
            filtered["pace"].astype(float),
            strict=True,
        )
    ]
    elevation_vs_pace = [
        (round(elevation, 2), round(pace, 2))
        for elevation, pace in zip(
            filtered["elevation_converted"].astype(float),
            filtered["pace"].astype(float),
            strict=True,
        )
    ]
    return distance_vs_pace, elevation_vs_pace


@ui.refreshable
def render_running_tab() -> None:
    """Render running-specific charts and best-segment insights."""
    distance_unit = get_distance_unit()
    elevation_unit = get_elevation_unit()
    pace_unit = f"min/{distance_unit}"
    running_workouts = _filter_running_workouts()
    distance_vs_pace, elevation_vs_pace = _build_scatter_points(
        running_workouts,
        distance_unit=distance_unit,
        elevation_unit=elevation_unit,
    )

    with ui.row().classes(ROW_CENTERED_CLASSES):
        render_scatter_graph(
            t("Distance vs Pace"),
            distance_vs_pace,
            t("Distance"),
            t("Pace"),
            distance_unit,
            pace_unit,
        )
        render_scatter_graph(
            t("Elevation vs Pace"),
            elevation_vs_pace,
            t("Elevation"),
            t("Pace"),
            elevation_unit,
            pace_unit,
        )

    with ui.row().classes(ROW_CENTERED_CLASSES):
        if state.health_data_cp_loading:
            ui.spinner(size="lg")
            ui.label(t("Loading Critical Power data..."))
        else:
            render_generic_graph(
                t("Critical Power (CP) over time"),
                state.health_data_graphs.get("critical_power", {}),
                "W",
                graph_type="line",
                show_trend=False,
            )
            render_generic_graph(
                t("W' over time"),
                state.health_data_graphs.get("w_prime", {}),
                "kJ",
                graph_type="line",
                show_trend=False,
            )

    render_best_segments_tab()
