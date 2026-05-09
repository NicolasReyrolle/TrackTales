"""Statistics section rendering for the Health Data tab."""

from __future__ import annotations

import pandas as pd
from nicegui import ui

from app_state import state
from i18n import t
from ui.charts import render_heat_map_graph
from ui.css import ROW_CENTERED_CLASSES
from ui.helpers import filter_workouts_by_date_range


def _filter_workouts_for_statistics() -> pd.DataFrame:
    workouts = state.workouts.get_workouts()
    if workouts.empty:
        return workouts
    if state.selected_activity_type != "All" and "activityType" in workouts.columns:
        workouts = workouts.loc[workouts["activityType"] == state.selected_activity_type]
    return filter_workouts_by_date_range(
        workouts,
        start_date=state.start_date,
        end_date=state.end_date,
    )


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


@ui.refreshable
def render_statistics_tab() -> None:
    """Render statistics charts in the Health Data tab."""
    if state.selected_main_tab != "health_data":
        return
    workouts = _filter_workouts_for_statistics()
    heatmap_values = _build_day_time_heatmap_values(workouts)
    day_labels_short = [
        t("Mon"),
        t("Tue"),
        t("Wed"),
        t("Thu"),
        t("Fri"),
        t("Sat"),
        t("Sun"),
    ]
    day_labels_long = [
        t("Monday"),
        t("Tuesday"),
        t("Wednesday"),
        t("Thursday"),
        t("Friday"),
        t("Saturday"),
        t("Sunday"),
    ]

    with ui.row().classes(ROW_CENTERED_CLASSES):
        render_heat_map_graph(
            t("Activity heat map (day/time)"),
            [str(hour) for hour in range(24)],
            day_labels_short,
            heatmap_values,
            x_axis_name=t("Hour of day"),
            y_axis_name=t("Day of week"),
            value_label=t("Workouts"),
            value_label_singular=t("workout"),
            value_label_plural=t("workouts"),
            fullscreen_y_labels=day_labels_long,
            fullscreen_description=t(
                "This heat map shows when workouts happen. "
                "X axis is hour of day, Y axis is day of week, "
                "and color intensity represents workout count."
            ),
        )
