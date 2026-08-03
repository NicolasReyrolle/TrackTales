"""Trends tab UI rendering."""

from nicegui import ui

from app_state import get_distance_unit, get_elevation_unit, state
from i18n import t
from ui.charts import render_generic_graph
from ui.css import (
    LABEL_MUTED_CLASSES,
    RECOVERY_CARD_CLASSES,
    RECOVERY_RECOMMENDATION_CLASSES,
    ROW_CENTERED_CLASSES,
)
from ui.helpers import period_code_to_label


def _register_recovery_translations() -> None:
    """Register dynamic recovery status strings for Babel extraction.

    These literals are returned at runtime by ``get_recovery_recommendation()``
    and passed to ``t()`` as variables, so they must appear here as literals.
    """
    t("Rest")
    t("Active Recovery")
    t("Maintain")
    t("Build")
    t("Insufficient data")


_register_recovery_translations()


def render_trends_tab() -> None:
    """Render the trends tab with recovery recommendation and trend graphs."""
    render_recovery_recommendation()
    render_trends_graphs()


@ui.refreshable
def render_recovery_recommendation() -> None:
    """Render the recovery recommendation card."""
    recommendation = state.workouts.get_recovery_recommendation(
        activity_type=state.selected_activity_type,
        start_date=state.start_date,
        end_date=state.end_date,
    )
    with ui.row().classes(ROW_CENTERED_CLASSES):
        with ui.card().classes(RECOVERY_CARD_CLASSES):
            ui.label(t("Recovery Recommendation")).classes(LABEL_MUTED_CLASSES)
            ui.label(t(recommendation)).classes(RECOVERY_RECOMMENDATION_CLASSES)


@ui.refreshable
def render_trends_graphs() -> None:
    """Render trend graphs."""
    dist_unit = get_distance_unit()
    elev_unit = get_elevation_unit()
    period_label = t(period_code_to_label(state.trends_period))
    with ui.row().classes(ROW_CENTERED_CLASSES):
        render_generic_graph(
            t("Count by {period}", period=period_label),
            state.workouts.get_count_by_period(
                state.trends_period,
                activity_type=state.selected_activity_type,
                start_date=state.start_date,
                end_date=state.end_date,
            ),
        )
        render_generic_graph(
            t("Distance by {period}", period=period_label),
            state.workouts.get_distance_by_period(
                state.trends_period,
                unit=dist_unit,
                activity_type=state.selected_activity_type,
                start_date=state.start_date,
                end_date=state.end_date,
            ),
            dist_unit,
        )
    with ui.row().classes(ROW_CENTERED_CLASSES):
        render_generic_graph(
            t("Calories by {period}", period=period_label),
            state.workouts.get_calories_by_period(
                state.trends_period,
                activity_type=state.selected_activity_type,
                start_date=state.start_date,
                end_date=state.end_date,
            ),
            "kcal",
        )
        render_generic_graph(
            t("Duration by {period}", period=period_label),
            state.workouts.get_duration_by_period(
                state.trends_period,
                activity_type=state.selected_activity_type,
                start_date=state.start_date,
                end_date=state.end_date,
            ),
            "h",
        )
    with ui.row().classes(ROW_CENTERED_CLASSES):
        render_generic_graph(
            t("Elevation by {period}", period=period_label),
            state.workouts.get_elevation_by_period(
                state.trends_period,
                activity_type=state.selected_activity_type,
                unit=elev_unit,
                start_date=state.start_date,
                end_date=state.end_date,
            ),
            elev_unit,
        )
