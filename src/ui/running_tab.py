"""Running tab UI rendering."""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd
from nicegui import ui

from app_state import get_distance_unit, get_elevation_unit, state
from i18n import get_language, t
from ui.best_segments import render_best_segments_tab
from ui.charts import render_generic_graph, render_scatter_graph
from ui.css import (
    LABEL_MUTED_CLASSES,
    ROW_CENTERED_CLASSES,
    ROW_WARNING_CLASSES,
    WARNING_BADGE_CLASSES,
    WARNING_BADGE_PROPS,
)
from ui.helpers import filter_workouts_by_date_range, format_date_label


def _filter_running_workouts() -> pd.DataFrame:
    workouts = state.workouts.get_workouts()
    if workouts.empty:
        return workouts
    if "activityType" in workouts.columns:
        activity_series = workouts["activityType"].astype(str).str.strip()
        workouts = workouts[activity_series.str.contains(r"\brunning\b", case=False, regex=True)]
    return filter_workouts_by_date_range(
        workouts,
        start_date=state.start_date,
        end_date=state.end_date,
    )


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

    def _format_start_date_label(start_date: object) -> str:
        if isinstance(start_date, (datetime, date)):
            return format_date_label(start_date, language_code)
        return str(start_date)

    date_labels = [
        _format_start_date_label(start_date)
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


@ui.refreshable
def render_running_tab() -> None:
    """Render running-specific charts and best-segment insights."""
    if state.selected_main_tab != "running":
        return
    distance_unit = get_distance_unit()
    elevation_unit = get_elevation_unit()
    pace_unit = f"min/{distance_unit}"
    distance_axis_label = f"{t('Distance')} ({distance_unit})"
    elevation_axis_label = f"{t('Elevation')} ({elevation_unit})"
    pace_axis_label = f"{t('Pace')} ({pace_unit})"
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
            distance_axis_label,
            pace_axis_label,
            distance_unit,
            pace_unit,
            date_label=t("Date"),
        )
        render_scatter_graph(
            t("Elevation vs Pace"),
            elevation_vs_pace,
            elevation_axis_label,
            pace_axis_label,
            elevation_unit,
            pace_unit,
            date_label=t("Date"),
        )

    render_running_health_graphs()

    render_best_segments_tab()


@ui.refreshable
def render_running_health_graphs() -> None:
    """Render CP/W' section for the running tab."""
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

            non_physical_map = state.health_data_graphs.get("w_prime_non_physical", {})
            if isinstance(non_physical_map, dict):
                non_physical_periods = sorted(
                    period
                    for period, marker in non_physical_map.items()
                    if isinstance(period, str) and isinstance(marker, (int, float)) and marker > 0
                )
            else:
                non_physical_periods = []

            if non_physical_periods:
                with ui.row().classes(ROW_WARNING_CLASSES):
                    warning_badge = ui.badge(t("Non-physical W'"))
                    warning_badge.props(WARNING_BADGE_PROPS)
                    warning_badge.classes(WARNING_BADGE_CLASSES)
                    with warning_badge:
                        ui.tooltip(
                            t(
                                "W' <= 0 is non-physical in the CP model. "
                                "This usually means sparse data or inconsistent "
                                "pace/power estimates "
                                "for those periods."
                            )
                        )
                    ui.label(f"{t('Periods')}: {', '.join(non_physical_periods)}").classes(
                        LABEL_MUTED_CLASSES
                    )
