"""Statistics tab UI rendering."""

from __future__ import annotations

from collections import defaultdict

import pandas as pd
from nicegui import ui

from app_state import get_distance_unit, state
from i18n import t
from ui.charts import render_box_plot_graph, render_heat_map_graph
from ui.css import ROW_CENTERED_CLASSES

_DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_MAX_ACTIVITIES_IN_BOXPLOT = 6


def _filter_workouts_for_statistics() -> pd.DataFrame:
    workouts = state.workouts.get_workouts()
    if workouts.empty:
        return workouts
    if state.selected_activity_type != "All" and "activityType" in workouts.columns:
        workouts = workouts.loc[workouts["activityType"] == state.selected_activity_type]
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


def _build_day_time_heatmap_values(workouts: pd.DataFrame) -> list[tuple[int, int, int]]:
    if workouts.empty or "startDate" not in workouts.columns:
        return []
    start_dates = pd.to_datetime(workouts["startDate"], errors="coerce")
    start_dates = start_dates.dropna()
    if start_dates.empty:
        return []
    counts = start_dates.groupby([start_dates.dt.hour, start_dates.dt.dayofweek]).size()
    result: list[tuple[int, int, int]] = []
    for key, value in counts.items():
        if not isinstance(key, tuple) or len(key) != 2:
            continue
        hour, day = key
        result.append((int(hour), int(day), int(value)))
    return result


def _build_pace_boxplot_data(
    workouts: pd.DataFrame, *, distance_unit: str
) -> dict[str, list[float]]:
    if workouts.empty or "distance" not in workouts.columns or "duration" not in workouts.columns:
        return {}
    filtered = workouts[
        workouts["distance"].notna()
        & workouts["duration"].notna()
        & (workouts["distance"] > 0)
        & (workouts["duration"] > 0)
    ].copy()
    if filtered.empty:
        return {}
    filtered["distance_converted"] = (
        filtered["distance"]
        .astype(float)
        .apply(lambda value: state.workouts.convert_distance(distance_unit, value))
    )
    filtered["pace"] = filtered["duration"].astype(float).div(60.0) / filtered["distance_converted"]
    if "activityType" not in filtered.columns:
        return {t("All Activities"): filtered["pace"].astype(float).tolist()}

    pace_by_activity: defaultdict[str, list[float]] = defaultdict(list)
    for activity, pace in zip(
        filtered["activityType"].astype(str),
        filtered["pace"].astype(float),
        strict=True,
    ):
        pace_by_activity[activity].append(round(pace, 2))
    # Keep the chart readable by limiting to the most represented activities.
    return dict(
        sorted(pace_by_activity.items(), key=lambda item: (-len(item[1]), item[0]))[
            :_MAX_ACTIVITIES_IN_BOXPLOT
        ]
    )


@ui.refreshable
def render_statistics_tab() -> None:
    """Render statistics charts (heat map and box plot)."""
    workouts = _filter_workouts_for_statistics()
    heatmap_values = _build_day_time_heatmap_values(workouts)
    distance_unit = get_distance_unit()
    pace_boxplot_data = _build_pace_boxplot_data(workouts, distance_unit=distance_unit)

    with ui.row().classes(ROW_CENTERED_CLASSES):
        render_heat_map_graph(
            t("Activity heat map (day/time)"),
            [str(hour) for hour in range(24)],
            _DAY_LABELS,
            heatmap_values,
        )
        render_box_plot_graph(
            t("Pace distribution by activity"),
            pace_boxplot_data,
        )
