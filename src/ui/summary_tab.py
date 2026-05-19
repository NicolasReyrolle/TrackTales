"""Summary tab rendering helpers."""

from collections.abc import Callable
from typing import Any

from nicegui import ui

from app_state import state
from i18n import t


def render_summary_tab(
    *,
    dist_unit: str,
    elev_unit: str,
    stat_card_fn: Callable[..., Any],
    build_workout_rows_fn: Callable[..., list[dict[str, Any]]],
    create_workout_detail_modal_fn: Callable[[list[dict[str, Any]]], Callable[[int], None]],
    row_centered_classes: str,
) -> None:
    """Render the overview summary tab content."""

    def _open_record_metric(metric_key: str) -> None:
        workout_index = state.metrics_workout_index.get(metric_key)
        if workout_index is None:
            return
        full_rows = build_workout_rows_fn(
            activity_type="All",
            skip_range_filters=True,
        )
        row_index_by_workout_index: dict[object, int] = {}
        for idx, row_workout_index in enumerate(row.get("workout_index") for row in full_rows):
            if (
                row_workout_index is not None
                and row_workout_index not in row_index_by_workout_index
            ):
                row_index_by_workout_index[row_workout_index] = idx
        row_index = row_index_by_workout_index.get(workout_index)
        if row_index is None:
            return
        open_detail = create_workout_detail_modal_fn(full_rows)
        open_detail(row_index)

    with ui.row().classes(row_centered_classes):
        stat_card_fn(t("Count"), state.metrics_display, "count")
        stat_card_fn(t("Distance"), state.metrics_display, "distance", dist_unit)
        stat_card_fn(t("Duration"), state.metrics_display, "duration", "h")
        stat_card_fn(t("Elevation"), state.metrics_display, "elevation", elev_unit)
        stat_card_fn(t("Calories"), state.metrics_display, "calories", "kcal")
    with ui.row().classes(row_centered_classes):
        stat_card_fn(
            t("Longest Run"),
            state.metrics_display,
            "longest_run",
            dist_unit,
            tooltip_ref=state.metrics_tooltip,
            tooltip_key="longest_run",
            on_click=lambda: _open_record_metric("longest_run"),
        )
        stat_card_fn(
            t("Longest Walk/Hike"),
            state.metrics_display,
            "longest_walk",
            dist_unit,
            tooltip_ref=state.metrics_tooltip,
            tooltip_key="longest_walk",
            on_click=lambda: _open_record_metric("longest_walk"),
        )
        stat_card_fn(
            t("Most Elevation (Run)"),
            state.metrics_display,
            "most_elevation_run",
            elev_unit,
            tooltip_ref=state.metrics_tooltip,
            tooltip_key="most_elevation_run",
            on_click=lambda: _open_record_metric("most_elevation_run"),
        )
        stat_card_fn(
            t("Most Elevation (Walk/Hike)"),
            state.metrics_display,
            "most_elevation_walk",
            elev_unit,
            tooltip_ref=state.metrics_tooltip,
            tooltip_key="most_elevation_walk",
            on_click=lambda: _open_record_metric("most_elevation_walk"),
        )
    with ui.row().classes(row_centered_classes):
        stat_card_fn(
            t("Longest Cycling"),
            state.metrics_display,
            "longest_cycling",
            dist_unit,
            tooltip_ref=state.metrics_tooltip,
            tooltip_key="longest_cycling",
            on_click=lambda: _open_record_metric("longest_cycling"),
        )
        stat_card_fn(
            t("Longest Swim"),
            state.metrics_display,
            "longest_swim",
            dist_unit,
            tooltip_ref=state.metrics_tooltip,
            tooltip_key="longest_swim",
            on_click=lambda: _open_record_metric("longest_swim"),
        )
        stat_card_fn(
            t("Longest Duration Workout"),
            state.metrics_display,
            "longest_duration_workout",
            "",
            tooltip_ref=state.metrics_tooltip,
            tooltip_key="longest_duration_workout",
            on_click=lambda: _open_record_metric("longest_duration_workout"),
        )
        stat_card_fn(
            t("Most Calories Workout"),
            state.metrics_display,
            "most_calories_workout",
            "kcal",
            tooltip_ref=state.metrics_tooltip,
            tooltip_key="most_calories_workout",
            on_click=lambda: _open_record_metric("most_calories_workout"),
        )
