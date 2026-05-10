"""Health data tab UI rendering."""

from nicegui import ui

from app_state import get_weight_unit, state
from i18n import t
from ui.charts import render_generic_graph
from ui.css import LABEL_MUTED_CLASSES, ROW_CENTERED_CLASSES
from ui.statistics_tab import render_statistics_tab


@ui.refreshable
def render_health_data_tab() -> None:
    """Render the health data tab with filters and graphs."""
    with ui.row().classes(ROW_CENTERED_CLASSES):
        render_statistics_tab()
        if state.health_data_loading:
            ui.spinner(size="lg")
            ui.label(t("Loading health data..."))
            return
        if not state.health_data_loaded:
            ui.label(t("Open this tab to load health data.")).classes(LABEL_MUTED_CLASSES)
            return
        weight_unit = get_weight_unit()
        render_generic_graph(
            t("Resting HR frequency over time"),
            state.health_data_graphs.get("heart_rate", {}),
            "bpm",
            graph_type="line",
        )

    with ui.row().classes(ROW_CENTERED_CLASSES):
        render_generic_graph(
            t("Body Mass over time"),
            state.health_data_graphs.get("body_mass", {}),
            weight_unit,
            graph_type="line",
        )
        render_generic_graph(
            t("VO2 Max over time"),
            state.health_data_graphs.get("vo2_max", {}),
            "ml/kg/min",
            graph_type="line",
        )
