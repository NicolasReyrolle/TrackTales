"""Shared UI chart and card components for Apple Health Analyzer."""

import copy
import json
from collections.abc import Callable, Mapping, Sequence

from nicegui import ui

from app_state import state
from i18n import t
from ui.css import (
    BUTTON_DENSE_PROPS,
    BUTTON_FLAT_ROUND_PROPS,
    CHART_CARD_CLASSES,
    CHART_FULLSCREEN_CARD_CLASSES,
    CHART_HEADER_ROW_CLASSES,
    ECHART_FULLSCREEN_CLASSES,
    LABEL_MUTED_CLASSES,
    LABEL_UPPERCASE_CLASSES,
    ROW_CENTERED_CLASSES,
    STAT_CARD_CLASSES,
    STAT_CARD_CLICKABLE_CLASSES,
    STAT_CARD_CLICKABLE_PROPS,
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
    "render_box_plot_graph",
    "render_heat_map_graph",
    "render_pie_rose_graph",
    "render_scatter_graph",
    "stat_card",
]

_SAVE_AS_IMAGE = "Save as Image"
_RESTORE = "Restore"


def _toolbox_config(*, restore: bool = False) -> dict[str, object]:
    """Build an ECharts toolbox configuration dict.

    Args:
        restore: When True, adds a ``restore`` button that resets the chart zoom.
    """
    feature: dict[str, object] = {"saveAsImage": {"title": t(_SAVE_AS_IMAGE)}}
    if restore:
        feature["restore"] = {"title": t(_RESTORE)}
    return {"feature": feature}


def stat_card(
    label: str,
    value_ref: dict[str, str],
    key: str,
    unit: str = "",
    tooltip_ref: dict[str, str] | None = None,
    tooltip_key: str | None = None,
    on_click: Callable[[], None] | None = None,
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
        on_click: Optional click handler. When provided, the card gets clickable
            hover styles and opens the callback on click.
    """
    card = ui.card().classes(STAT_CARD_CLASSES)
    if on_click is not None:

        def _handle_click(_event: object) -> None:
            on_click()

        card.classes(STAT_CARD_CLICKABLE_CLASSES)
        card.props(STAT_CARD_CLICKABLE_PROPS)
        card.on("click", _handle_click)
        card.on("keydown.enter", _handle_click)
        card.on("keydown.space", _handle_click)
    with card:
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


def render_pie_rose_graph(
    label: str,
    values: Mapping[str, float | int],
    unit: str = "",
    fullscreen_values: Mapping[str, float | int] | None = None,
) -> None:
    """Render a pie/rose graph for the given values.

    Args:
        label: Chart title.
        values: Mapping of category name to numeric value (used in the card view).
        unit: Optional unit suffix appended to tooltip values and chart title.
        fullscreen_values: Alternative data mapping used exclusively in the fullscreen chart.
            When provided (e.g. ungrouped data), overrides ``values`` for the fullscreen view.
    """

    chart_data: list[dict[str, float | int | str]] = [
        {"value": v, "name": k} for k, v in values.items()
    ]

    fullscreen_chart_data: list[dict[str, float | int | str]] = (
        [{"value": v, "name": k} for k, v in fullscreen_values.items()]
        if fullscreen_values is not None
        else chart_data
    )

    # Include unit in chart title when one is provided
    title_text = f"{label} ({unit})" if unit else label
    value_suffix = f" {unit}" if unit else ""

    _shared: dict[str, object] = {
        "backgroundColor": "transparent",
        "darkMode": state.dark_mode_enabled,
        "tooltip": {
            "trigger": "item",
            "renderMode": "richText",
            "formatter": f"{{b}}\n{{c}}{value_suffix}\n({{d}}%)",
        },
        "toolbox": _toolbox_config(),
    }

    # Card chart: compact fixed-pixel radius (fits the w-100 h-80 card)
    card_chart_config: dict[str, object] = {
        **_shared,
        "series": [
            {
                "type": "pie",
                "name": label,
                "data": chart_data,
                "roseType": "rose",
                "radius": ["10%", "60%"],
                "center": ["50%", "50%"],
            },
        ],
    }

    # Fullscreen chart: larger radius fills the viewport, all slices shown (minAngle: 0).
    fullscreen_chart_config: dict[str, object] = {
        **copy.deepcopy(_shared),
        "series": [
            {
                "type": "pie",
                "name": label,
                "data": fullscreen_chart_data,
                "roseType": "rose",
                "radius": ["15%", "75%"],
                "center": ["50%", "50%"],
                "minAngle": 0,
            },
        ],
    }

    with ui.dialog().props("maximized") as dialog:
        with ui.card().classes(CHART_FULLSCREEN_CARD_CLASSES):
            with ui.row().classes(CHART_HEADER_ROW_CLASSES):
                ui.label(title_text).classes(LABEL_UPPERCASE_CLASSES)
                ui.button(icon="close", on_click=dialog.close).props(BUTTON_DENSE_PROPS)
            ui.echart(fullscreen_chart_config).classes(ECHART_FULLSCREEN_CLASSES)

    with ui.card().classes(CHART_CARD_CLASSES):
        with ui.row().classes(CHART_HEADER_ROW_CLASSES):
            ui.label(title_text).classes(LABEL_UPPERCASE_CLASSES)
            ui.button(icon="fullscreen", on_click=dialog.open).props(BUTTON_DENSE_PROPS)
        ui.echart(card_chart_config)


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
    value_suffix = f" {unit}" if unit else ""

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
        # NiceGUI evaluates dict keys prefixed with ":" as JavaScript expressions.
        # ECharts excludes series with tooltip.show:false from the formatter params array,
        # so the bridge (series[0], hidden) is not counted and the actual data is params[0].
        # When the value is null (interpolated gap), show "n/a" with no unit suffix.
        tooltip_formatter_key = ":formatter"
        tooltip_formatter: str = (
            "function(params) {"
            "var name = params[0].name;"
            "var val = params[0].value;"
            "if (val === null || val === undefined) { return name + '\\nn/a'; }"
            f"return name + '\\n' + val + '{value_suffix}';"
            "}"
        )
    else:
        series = [{"data": data_points, "type": graph_type}]
        # c0 = bar/area value
        tooltip_formatter_key = "formatter"
        tooltip_formatter = f"{{b}}\n{{c0}}{value_suffix}"

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

    base_config: dict[str, object] = {
        "backgroundColor": "transparent",
        "darkMode": state.dark_mode_enabled,
        "tooltip": {
            "trigger": "axis",
            "axisPointer": {"type": "cross"},
            "renderMode": "richText",
            tooltip_formatter_key: tooltip_formatter,
        },
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

    # Card chart: scroll/pinch zoom only (no slider, no restore button)
    card_config = copy.deepcopy(base_config)
    card_config["dataZoom"] = [{"type": "inside"}]
    card_config["toolbox"] = _toolbox_config()

    # Fullscreen chart: inside zoom + visible slider + restore button
    fullscreen_config = copy.deepcopy(base_config)
    fullscreen_config["dataZoom"] = [{"type": "inside"}, {"type": "slider"}]
    fullscreen_config["toolbox"] = _toolbox_config(restore=True)

    with ui.dialog().props("maximized") as dialog:
        with ui.card().classes(CHART_FULLSCREEN_CARD_CLASSES):
            with ui.row().classes(CHART_HEADER_ROW_CLASSES):
                ui.label(label).classes(LABEL_UPPERCASE_CLASSES)
                ui.button(icon="close", on_click=dialog.close).props(BUTTON_DENSE_PROPS)
            ui.echart(fullscreen_config).classes(ECHART_FULLSCREEN_CLASSES)

    with ui.card().classes(CHART_CARD_CLASSES):
        with ui.row().classes(CHART_HEADER_ROW_CLASSES):
            ui.label(label).classes(LABEL_UPPERCASE_CLASSES)
            ui.button(icon="fullscreen", on_click=dialog.open).props(BUTTON_DENSE_PROPS)
        ui.echart(card_config)


def render_scatter_graph(
    label: str,
    points: Sequence[tuple[float, float] | tuple[float, float, str, object | None]],
    x_axis_label: str,
    y_axis_label: str,
    x_unit: str = "",
    y_unit: str = "",
    date_label: str = "",
    fullscreen_description: str = "",
    on_point_click: Callable[[object], None] | None = None,
) -> None:
    """Render a scatter graph from (x, y) points."""
    value_suffix_x = f" {x_unit}" if x_unit else ""
    value_suffix_y = f" {y_unit}" if y_unit else ""
    title_text = label

    chart_data: list[list[float | str | object | None]] = []
    includes_metadata = False
    for point in points:
        if len(point) >= 4:
            x, y, point_date, workout_index = point[:4]
            chart_data.append([x, y, point_date, workout_index])
            includes_metadata = True
        elif len(point) >= 2:
            x, y = point[0], point[1]
            chart_data.append([x, y])

    trend_data: list[list[float]] = []
    if len(chart_data) >= 2:
        def _to_float(value: float | str | object | None) -> float:
            if isinstance(value, (int, float, str)):
                return float(value)
            return 0.0

        x_values = [_to_float(point[0]) for point in chart_data]
        y_values = [_to_float(point[1]) for point in chart_data]
        x_mean = sum(x_values) / len(x_values)
        y_mean = sum(y_values) / len(y_values)
        denominator = sum((x_value - x_mean) ** 2 for x_value in x_values)
        if denominator > 0:
            numerator = sum(
                (x_value - x_mean) * (y_value - y_mean)
                for x_value, y_value in zip(x_values, y_values, strict=True)
            )
            slope = numerator / denominator
            intercept = y_mean - slope * x_mean
            x_min = min(x_values)
            x_max = max(x_values)
            trend_data = [
                [x_min, slope * x_min + intercept],
                [x_max, slope * x_max + intercept],
            ]

    tooltip_formatter = (
        "function(params) {"
        f"var text = '{x_axis_label}: ' + params.value[0] + '{value_suffix_x}' + "
        f"'\\n{y_axis_label}: ' + params.value[1] + '{value_suffix_y}';"
        "if (params.value.length > 2 && params.value[2]) {"
        f"  return text + '\\n{date_label}: ' + params.value[2];"
        "}"
        "return text;"
        "}"
        if includes_metadata
        else (f"{x_axis_label}: {{@[0]}}{value_suffix_x}\n{y_axis_label}: {{@[1]}}{value_suffix_y}")
    )

    base_config: dict[str, object] = {
        "backgroundColor": "transparent",
        "darkMode": state.dark_mode_enabled,
        "tooltip": {
            "trigger": "item",
            "renderMode": "richText",
            ":formatter": tooltip_formatter,
        },
        "xAxis": {"type": "value", "name": x_axis_label, "scale": True},
        "yAxis": {"type": "value", "name": y_axis_label, "scale": True},
        "series": [
            {"type": "scatter", "data": chart_data, "symbolSize": 9},
            {
                "type": "line",
                "data": trend_data,
                "symbol": "none",
                "lineStyle": {"type": "dashed", "width": 2},
                "tooltip": {"show": False},
                "silent": True,
            },
        ],
    }

    card_config = copy.deepcopy(base_config)
    card_config["dataZoom"] = [{"type": "inside"}]
    card_config["toolbox"] = _toolbox_config()

    fullscreen_config = copy.deepcopy(base_config)
    fullscreen_config["dataZoom"] = [{"type": "inside"}, {"type": "slider"}]
    fullscreen_config["toolbox"] = _toolbox_config(restore=True)

    with ui.dialog().props("maximized") as dialog:
        with ui.card().classes(CHART_FULLSCREEN_CARD_CLASSES):
            with ui.row().classes(CHART_HEADER_ROW_CLASSES):
                ui.label(title_text).classes(LABEL_UPPERCASE_CLASSES)
                ui.button(icon="close", on_click=dialog.close).props(BUTTON_DENSE_PROPS)
            if fullscreen_description:
                ui.label(fullscreen_description).classes(LABEL_MUTED_CLASSES)
            fullscreen_chart = ui.echart(fullscreen_config).classes(ECHART_FULLSCREEN_CLASSES)

    with ui.card().classes(CHART_CARD_CLASSES):
        with ui.row().classes(CHART_HEADER_ROW_CLASSES):
            ui.label(title_text).classes(LABEL_UPPERCASE_CLASSES)
            ui.button(icon="fullscreen", on_click=dialog.open).props(BUTTON_DENSE_PROPS)
        card_chart = ui.echart(card_config)

    if on_point_click is not None:

        def _handle_click(event: object) -> None:
            args = getattr(event, "args", {})
            if not isinstance(args, dict):
                return
            data = args.get("data")
            value: object
            if isinstance(data, dict):
                value = data.get("value")
            else:
                value = data if data is not None else args.get("value")
            # Metadata points store workout_index at position 3 in
            # [x, y, date_label, workout_index].
            if isinstance(value, tuple):
                value = list(value)
            if isinstance(value, list) and len(value) >= 4 and value[3] is not None:
                on_point_click(value[3])
                return
            data_index = args.get("dataIndex")
            if isinstance(data_index, int) and 0 <= data_index < len(chart_data):
                point = chart_data[data_index]
                if len(point) >= 4 and point[3] is not None:
                    on_point_click(point[3])

        card_chart.on("click", _handle_click)
        fullscreen_chart.on("click", _handle_click)


def render_heat_map_graph(
    label: str,
    x_labels: Sequence[str],
    y_labels: Sequence[str],
    values: Sequence[tuple[int, int, int]],
    x_axis_name: str = "",
    y_axis_name: str = "",
    value_label: str | None = None,
    value_label_singular: str | None = None,
    value_label_plural: str | None = None,
    fullscreen_y_labels: Sequence[str] | None = None,
    fullscreen_description: str = "",
) -> None:
    """Render an ECharts heat map from indexed (x, y, value) triplets."""
    max_value = max((value for *_coords, value in values), default=1)
    value_label_text = value_label if value_label is not None else t("Workouts")
    singular_label = value_label_singular if value_label_singular is not None else t("workout")
    plural_label = value_label_plural if value_label_plural is not None else t("workouts")
    x_labels_values = list(x_labels)
    y_labels_values = list(y_labels)
    singular_label_js = json.dumps(singular_label)
    plural_label_js = json.dumps(plural_label)
    from_label_js = json.dumps(t("from"))
    to_label_js = json.dumps(t("to"))
    fullscreen_y_labels_values = (
        list(fullscreen_y_labels) if fullscreen_y_labels is not None else y_labels_values
    )

    def _build_tooltip_formatter(y_labels_source: Sequence[str]) -> str:
        y_labels_js = json.dumps(list(y_labels_source))
        return (
            "function(params) {"
            f"var yLabels = {y_labels_js};"
            f"var singularLabel = {singular_label_js};"
            f"var pluralLabel = {plural_label_js};"
            f"var fromLabel = {from_label_js};"
            f"var toLabel = {to_label_js};"
            "var point = params.value;"
            "var hour = Number(point[0]);"
            "var startHour = String(hour).padStart(2, '0') + ':00';"
            "var endHour = String((hour + 1) % 24).padStart(2, '0') + ':00';"
            "var count = Number(point[2]);"
            "var noun = count === 1 ? singularLabel : pluralLabel;"
            "return yLabels[point[1]] + ', ' + fromLabel + ' ' + startHour + "
            "' ' + toLabel + ' ' + endHour + ': ' + count + ' ' + noun;"
            "}"
        )

    base_config: dict[str, object] = {
        "backgroundColor": "transparent",
        "darkMode": state.dark_mode_enabled,
        "tooltip": {
            "position": "top",
            "renderMode": "richText",
            ":formatter": _build_tooltip_formatter(y_labels_values),
        },
        "grid": {"left": "3%", "right": "4%", "bottom": "10%", "containLabel": True},
        "xAxis": {
            "type": "category",
            "name": x_axis_name,
            "nameLocation": "middle",
            "nameGap": 28,
            "data": x_labels_values,
            "splitArea": {"show": True},
        },
        "yAxis": {
            "type": "category",
            "name": y_axis_name,
            "nameLocation": "middle",
            "nameGap": 56,
            "data": y_labels_values,
            "splitArea": {"show": True},
        },
        "series": [
            {
                "name": label,
                "type": "heatmap",
                "data": [[x, y, v] for x, y, v in values],
                "label": {"show": False},
                "emphasis": {"itemStyle": {"shadowBlur": 10, "shadowColor": "rgba(0,0,0,0.5)"}},
            }
        ],
    }
    card_config = copy.deepcopy(base_config)
    fullscreen_config = copy.deepcopy(base_config)
    fullscreen_config["tooltip"] = {
        "position": "top",
        "renderMode": "richText",
        ":formatter": _build_tooltip_formatter(fullscreen_y_labels_values),
    }
    base_y_axis = base_config["yAxis"]
    if isinstance(base_y_axis, dict):
        fullscreen_config["yAxis"] = {**base_y_axis, "data": fullscreen_y_labels_values}
    fullscreen_config["visualMap"] = {
        "min": 0,
        "max": max_value,
        "calculable": True,
        "orient": "horizontal",
        "left": "center",
        "bottom": "1%",
        "text": [t("More workouts"), t("Fewer workouts")],
        "formatter": f"{{value}} {value_label_text}",
    }
    fullscreen_config["grid"] = {"left": "3%", "right": "4%", "bottom": "16%", "containLabel": True}

    with ui.dialog().props("maximized") as dialog:
        with ui.card().classes(CHART_FULLSCREEN_CARD_CLASSES):
            with ui.row().classes(CHART_HEADER_ROW_CLASSES):
                ui.label(label).classes(LABEL_UPPERCASE_CLASSES)
                ui.button(icon="close", on_click=dialog.close).props(BUTTON_DENSE_PROPS)
            if fullscreen_description:
                ui.label(fullscreen_description).classes(LABEL_MUTED_CLASSES)
            ui.echart(fullscreen_config).classes(ECHART_FULLSCREEN_CLASSES)

    with ui.card().classes(CHART_CARD_CLASSES):
        with ui.row().classes(CHART_HEADER_ROW_CLASSES):
            ui.label(label).classes(LABEL_UPPERCASE_CLASSES)
            ui.button(icon="fullscreen", on_click=dialog.open).props(BUTTON_DENSE_PROPS)
        ui.echart(card_config)


def render_box_plot_graph(
    label: str,
    values_by_category: Mapping[str, Sequence[float]],
    fullscreen_description: str = "",
) -> None:
    """Render a box plot graph where each key is one category."""
    categories = list(values_by_category.keys())
    series_data: list[list[float]] = []

    for values in values_by_category.values():
        sorted_values = sorted(float(value) for value in values)
        if not sorted_values:
            series_data.append([0.0, 0.0, 0.0, 0.0, 0.0])
            continue
        n = len(sorted_values)
        mid = n // 2
        median = (
            sorted_values[mid]
            if n % 2 == 1
            else (sorted_values[mid - 1] + sorted_values[mid]) / 2.0
        )
        # Use an index-based quartile approximation on the sorted sample for
        # deterministic rendering without introducing extra dependencies.
        q1 = sorted_values[int((n - 1) * 0.25)]
        q3 = sorted_values[int((n - 1) * 0.75)]
        series_data.append([sorted_values[0], q1, median, q3, sorted_values[-1]])

    base_config: dict[str, object] = {
        "backgroundColor": "transparent",
        "darkMode": state.dark_mode_enabled,
        "tooltip": {"trigger": "item", "axisPointer": {"type": "shadow"}},
        "xAxis": {"type": "category", "data": categories},
        "yAxis": {"type": "value", "scale": True},
        "series": [{"type": "boxplot", "data": series_data}],
        "toolbox": _toolbox_config(),
    }

    with ui.dialog().props("maximized") as dialog:
        with ui.card().classes(CHART_FULLSCREEN_CARD_CLASSES):
            with ui.row().classes(CHART_HEADER_ROW_CLASSES):
                ui.label(label).classes(LABEL_UPPERCASE_CLASSES)
                ui.button(icon="close", on_click=dialog.close).props(BUTTON_DENSE_PROPS)
            if fullscreen_description:
                ui.label(fullscreen_description).classes(LABEL_MUTED_CLASSES)
            ui.echart(base_config).classes(ECHART_FULLSCREEN_CLASSES)

    with ui.card().classes(CHART_CARD_CLASSES):
        with ui.row().classes(CHART_HEADER_ROW_CLASSES):
            ui.label(label).classes(LABEL_UPPERCASE_CLASSES)
            ui.button(icon="fullscreen", on_click=dialog.open).props(BUTTON_DENSE_PROPS)
        ui.echart(base_config)
