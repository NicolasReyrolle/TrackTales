"""Shared UI chart and card components for Apple Health Analyzer."""

from collections.abc import Mapping

from nicegui import ui

from app_state import state
from ui.css import (
    BUTTON_FLAT_ROUND_PROPS,
    CHART_CARD_CLASSES,
    LABEL_UPPERCASE_CLASSES,
    ROW_CENTERED_CLASSES,
    STAT_CARD_CLASSES,
    STAT_CARD_LABEL_CLASSES,
    STAT_CARD_UNIT_CLASSES,
    STAT_CARD_VALUE_CLASSES,
    STAT_CARD_VALUE_ROW_CLASSES,
)
from ui.helpers import calculate_moving_average

# Re-export constants that other modules import from this module for compatibility.
__all__ = [
    "BUTTON_FLAT_ROUND_PROPS",
    "LABEL_UPPERCASE_CLASSES",
    "ROW_CENTERED_CLASSES",
    "render_generic_graph",
    "render_pie_rose_graph",
    "stat_card",
]


def stat_card(
    label: str,
    value_ref: dict[str, str],
    key: str,
    unit: str = "",
    tooltip_ref: dict[str, str] | None = None,
    tooltip_key: str | None = None,
) -> None:
    """Create a reactive KPI card with an optional hover tooltip.

    The card value is bound reactively to ``value_ref[key]`` so that any update
    to the dictionary is immediately reflected in the UI without a full page
    refresh.

    Args:
        label: Short display label shown above the value (e.g. ``"Distance"``).
        value_ref: Mutable dictionary whose ``key`` entry holds the formatted
            display string.  NiceGUI binds directly to this dict so mutations
            are picked up automatically.
        key: Key inside *value_ref* to read the display value from.
        unit: Optional unit suffix rendered in smaller text next to the value
            (e.g. ``"km"``, ``"kcal"``).  Omit or pass an empty string to show
            no unit.
        tooltip_ref: Optional mutable dictionary whose ``tooltip_key`` entry
            holds the tooltip text.  When provided together with *tooltip_key*,
            a NiceGUI ``ui.tooltip`` is added to the card and bound to this
            dict so it updates reactively alongside the card value.  The tooltip
            is hidden when the text is empty (i.e. before any file is loaded);
            once data is available it shows either the record details or a
            translated ``"No data"`` fallback.
        tooltip_key: Key inside *tooltip_ref* to read the tooltip text from.
            Required when *tooltip_ref* is provided; ignored otherwise.
    """
    with ui.card().classes(STAT_CARD_CLASSES):
        ui.label(label).classes(STAT_CARD_LABEL_CLASSES)
        with ui.row().classes(STAT_CARD_VALUE_ROW_CLASSES):
            # Bind the text to the dictionary key for reactive updates
            ui.label().classes(STAT_CARD_VALUE_CLASSES).bind_text_from(value_ref, key)
            if unit:
                ui.label(unit).classes(STAT_CARD_UNIT_CLASSES)
        if tooltip_ref is not None and tooltip_key is not None:
            ui.tooltip().bind_text_from(tooltip_ref, tooltip_key).bind_visibility_from(
                tooltip_ref, tooltip_key, backward=bool
            )


def render_pie_rose_graph(label: str, values: Mapping[str, float | int], unit: str = "") -> None:
    """Render a pie/rose graph for the given values."""

    chart_data: list[dict[str, float | int | str]] = [
        {"value": v, "name": k} for k, v in values.items()
    ]

    # Include unit in chart title when one is provided
    title_text = f"{label} ({unit})" if unit else label

    with ui.card().classes(CHART_CARD_CLASSES):
        ui.label(title_text).classes(LABEL_UPPERCASE_CLASSES)
        ui.echart(
            {
                "backgroundColor": "transparent",
                "darkMode": state.dark_mode_enabled,
                "tooltip": {"trigger": "item", "formatter": f"{{b}}: {{c}} {unit} ({{d}}%)"},
                "series": [
                    {
                        "type": "pie",
                        "name": label,
                        "data": chart_data,
                        "roseType": "rose",
                        "radius": ["10", "60"],
                        "center": ["50%", "50%"],
                    },
                ],
            }
        )


def render_generic_graph(
    label: str,
    values: Mapping[str, float | int | None],
    unit: str = "",
    graph_type: str = "bar",
    show_trend: bool = True,
) -> None:
    """Render generic graphs for the given values."""

    # Transform dictionary data into ECharts format: [{'value': x, 'name': y}, ...]
    chart_data: list[dict[str, float | int | None | str]] = [
        {"value": v, "name": k} for k, v in values.items()
    ]

    # Extract raw lists for the axes and series
    categories = [d["name"] for d in chart_data]
    data_points = list(values.values())

    if graph_type == "line":
        # Two-layer approach: a muted "bridge" series beneath (connectNulls=True) makes the
        # interpolated gap segments visible in a distinct colour, while the main series on
        # top (connectNulls=False) draws actual data in the normal colour and covers the
        # bridge wherever real values exist.
        series: list[dict[str, object]] = [
            {
                "data": data_points,
                "type": "line",
                "connectNulls": True,
                "symbol": "none",
                "lineStyle": {"type": "dashed", "width": 1},
                "itemStyle": {"color": "#aaaaaa"},  # Muted grey for interpolated gaps
                "tooltip": {"show": False},
                "z": 1,
            },
            {
                "data": data_points,
                "type": "line",
                "connectNulls": False,
                "symbol": "circle",
                "symbolSize": 4,
                "z": 2,
            },
        ]
    else:
        series = [{"data": data_points, "type": graph_type}]
    if show_trend:
        series.append(
            {
                "name": "Trend",
                "type": "line",
                "data": calculate_moving_average(data_points),
                "symbol": "none",  # Removes the dots on the line
                "lineStyle": {
                    "width": 2,
                    "type": "dashed",  # Dashed line for statistical trends
                },
                "itemStyle": {"color": "#e74c3c"},  # Red color to stand out
            }
        )

    with ui.card().classes(CHART_CARD_CLASSES):
        ui.label(label).classes(LABEL_UPPERCASE_CLASSES)
        ui.echart(
            {
                "backgroundColor": "transparent",
                "darkMode": state.dark_mode_enabled,
                "tooltip": {"trigger": "axis", "formatter": f"{{b}}: {{c}} {unit}"},
                "xAxis": {
                    "type": "category",
                    "data": categories,
                    "axisTick": {"alignWithLabel": True},
                },
                "yAxis": {
                    "type": "value",
                    "scale": True,
                    "name": unit,
                    "nameLocation": "end",
                },
                "series": series,
            }
        )
