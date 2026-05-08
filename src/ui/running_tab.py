"""Running tab UI rendering."""

from __future__ import annotations

import pandas as pd
from nicegui import ui

from app_state import get_distance_unit, get_elevation_unit, state
from i18n import get_language, t
from ui.best_segments import render_best_segments_tab
from ui.charts import render_generic_graph, render_scatter_graph
from ui.css import ROW_CENTERED_CLASSES
from ui.helpers import format_date_label
from ui.workout_detail_modal import create_workout_detail_modal
from ui.workout_table import _build_workout_rows


def _filter_running_workouts() -> pd.DataFrame:
    workouts = state.workouts.get_workouts()
    if workouts.empty:
        return workouts
    if "activityType" in workouts.columns:
        activity_series = workouts["activityType"].astype(str).str.strip()
        workouts = workouts[activity_series.str.contains(r"\brunning\b", case=False, regex=True)]
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
) -> tuple[
    list[tuple[float, float, str, object | None]],
    list[tuple[float, float, str, object | None]],
]:
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
    if "ElevationAscended" in filtered.columns:
        filtered["elevation_converted"] = (
            filtered["ElevationAscended"]
            .astype(float)
            .apply(lambda value: state.workouts.convert_distance(elevation_unit, value))
        )
    else:
        filtered["elevation_converted"] = pd.Series(0.0, index=filtered.index)

    language_code = get_language()
    date_labels = [
        format_date_label(start_date, language_code)
        if hasattr(start_date, "strftime")
        else str(start_date)
        for start_date in filtered.get("startDate", pd.Series("", index=filtered.index))
    ]
    workout_indexes = filtered.index.tolist()

    distance_vs_pace = [
        (round(distance, 2), round(pace, 2), date_label, workout_index)
        for distance, pace, date_label, workout_index in zip(
            filtered["distance_converted"].astype(float),
            filtered["pace"].astype(float),
            date_labels,
            workout_indexes,
            strict=True,
        )
    ]
    elevation_vs_pace = [
        (round(elevation, 2), round(pace, 2), date_label, workout_index)
        for elevation, pace, date_label, workout_index in zip(
            filtered["elevation_converted"].astype(float),
            filtered["pace"].astype(float),
            date_labels,
            workout_indexes,
            strict=True,
        )
    ]
    return distance_vs_pace, elevation_vs_pace


def _open_workout_detail(workout_index: object) -> None:
    full_rows = _build_workout_rows(activity_type="All", skip_range_filters=True)
    row_index_by_workout_index: dict[object, int] = {}
    for idx, row in enumerate(full_rows):
        row_workout_index = row.get("workout_index")
        if row_workout_index is not None and row_workout_index not in row_index_by_workout_index:
            row_index_by_workout_index[row_workout_index] = idx
    row_index = row_index_by_workout_index.get(workout_index)
    if row_index is None:
        return
    open_detail = create_workout_detail_modal(full_rows)
    open_detail(row_index)


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
            date_label=t("Date"),
            fullscreen_description=t(
                "Each point is a running workout. Click a point to open workout details."
            ),
            on_point_click=_open_workout_detail,
        )
        render_scatter_graph(
            t("Elevation vs Pace"),
            elevation_vs_pace,
            t("Elevation"),
            t("Pace"),
            elevation_unit,
            pace_unit,
            date_label=t("Date"),
            fullscreen_description=t(
                "Each point is a running workout. Click a point to open workout details."
            ),
            on_point_click=_open_workout_detail,
        )

    with ui.row().classes(ROW_CENTERED_CLASSES):
        if state.health_data_loading and not state.health_data_loaded:
            ui.spinner(size="lg")
            ui.label(t("Loading health data..."))
        elif state.health_data_cp_loading:
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
