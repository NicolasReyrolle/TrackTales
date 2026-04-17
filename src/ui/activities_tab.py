"""Activities tab UI rendering."""

from nicegui import ui

from app_state import get_distance_unit, get_elevation_unit, state
from i18n import t
from i18n.activity_types import translate_activity_value_map
from ui.charts import render_pie_rose_graph
from ui.css import ROW_CENTERED_CLASSES


@ui.refreshable
def render_activity_graphs() -> None:
    """Render graphs by activity type."""
    dist_unit = get_distance_unit()
    elev_unit = get_elevation_unit()
    with ui.row().classes(ROW_CENTERED_CLASSES):
        render_pie_rose_graph(
            t("Count by activity"),
            translate_activity_value_map(
                state.workouts.get_count_by_activity(
                    start_date=state.start_date, end_date=state.end_date
                )
            ),
            fullscreen_values=translate_activity_value_map(
                state.workouts.get_count_by_activity(
                    combination_threshold=0.0,
                    start_date=state.start_date,
                    end_date=state.end_date,
                )
            ),
            fullscreen_data_fn=lambda start, end: translate_activity_value_map(
                state.workouts.get_count_by_activity(
                    combination_threshold=0.0,
                    start_date=start,
                    end_date=end,
                )
            ),
        )
        render_pie_rose_graph(
            t("Distance by activity"),
            translate_activity_value_map(
                state.workouts.get_distance_by_activity(
                    unit=dist_unit,
                    start_date=state.start_date,
                    end_date=state.end_date,
                )
            ),
            dist_unit,
            fullscreen_values=translate_activity_value_map(
                state.workouts.get_distance_by_activity(
                    unit=dist_unit,
                    combination_threshold=0.0,
                    start_date=state.start_date,
                    end_date=state.end_date,
                )
            ),
            fullscreen_data_fn=lambda start, end: translate_activity_value_map(
                state.workouts.get_distance_by_activity(
                    unit=dist_unit,
                    combination_threshold=0.0,
                    start_date=start,
                    end_date=end,
                )
            ),
        )
    with ui.row().classes(ROW_CENTERED_CLASSES):
        render_pie_rose_graph(
            t("Calories by activity"),
            translate_activity_value_map(
                state.workouts.get_calories_by_activity(
                    start_date=state.start_date, end_date=state.end_date
                )
            ),
            "kcal",
            fullscreen_values=translate_activity_value_map(
                state.workouts.get_calories_by_activity(
                    combination_threshold=0.0,
                    start_date=state.start_date,
                    end_date=state.end_date,
                )
            ),
            fullscreen_data_fn=lambda start, end: translate_activity_value_map(
                state.workouts.get_calories_by_activity(
                    combination_threshold=0.0,
                    start_date=start,
                    end_date=end,
                )
            ),
        )
        render_pie_rose_graph(
            t("Duration by activity"),
            translate_activity_value_map(
                state.workouts.get_duration_by_activity(
                    start_date=state.start_date, end_date=state.end_date
                )
            ),
            "h",
            fullscreen_values=translate_activity_value_map(
                state.workouts.get_duration_by_activity(
                    combination_threshold=0.0,
                    start_date=state.start_date,
                    end_date=state.end_date,
                )
            ),
            fullscreen_data_fn=lambda start, end: translate_activity_value_map(
                state.workouts.get_duration_by_activity(
                    combination_threshold=0.0,
                    start_date=start,
                    end_date=end,
                )
            ),
        )
    with ui.row().classes(ROW_CENTERED_CLASSES):
        render_pie_rose_graph(
            t("Elevation by activity"),
            translate_activity_value_map(
                state.workouts.get_elevation_by_activity(
                    unit=elev_unit,
                    start_date=state.start_date,
                    end_date=state.end_date,
                )
            ),
            elev_unit,
            fullscreen_values=translate_activity_value_map(
                state.workouts.get_elevation_by_activity(
                    unit=elev_unit,
                    combination_threshold=0.0,
                    start_date=state.start_date,
                    end_date=state.end_date,
                )
            ),
            fullscreen_data_fn=lambda start, end: translate_activity_value_map(
                state.workouts.get_elevation_by_activity(
                    unit=elev_unit,
                    combination_threshold=0.0,
                    start_date=start,
                    end_date=end,
                )
            ),
        )
