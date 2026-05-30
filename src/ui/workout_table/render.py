"""NiceGUI render functions for the workout table and range-filter selectors."""

import logging
import math
from typing import Any

from nicegui import ui

from app_state import get_distance_unit, state
from i18n import t
from ui.css import (
    LABEL_EMPTY_STATE_CLASSES,
    RANGE_LABEL_CLASSES,
    RANGE_SELECTOR_COLUMN_CLASSES,
    TABLE_FULL_CLASSES,
)
from ui.workout_detail_modal import create_workout_detail_modal
from ui.workout_table.rows import _build_table_rows, _build_workout_rows

_logger = logging.getLogger(__name__)


@ui.refreshable
def render_workout_table() -> None:
    """Render the workout details table with sortable numeric columns and pagination."""
    if not state.file_loaded:
        ui.label(t("Load a file to see workout details.")).classes(LABEL_EMPTY_STATE_CLASSES)
        return

    full_rows = _build_workout_rows()
    _logger.debug("Rendering workout table with %d rows", len(full_rows))
    table_rows = _build_table_rows(full_rows)

    columns = [
        {
            "name": "date",
            "label": t("Date"),
            "field": "date_sort",
            "sortable": True,
            "align": "left",
        },
        {
            "name": "activity_type",
            "label": t("Activity"),
            "field": "activity_type",
            "sortable": True,
            "align": "left",
        },
        {
            "name": "duration",
            "label": t("Duration"),
            "field": "duration_sort",
            "sortable": True,
            "align": "right",
        },
        {
            "name": "distance",
            "label": t("Distance"),
            "field": "distance_sort",
            "sortable": True,
            "align": "right",
        },
        {
            "name": "calories",
            "label": t("Calories"),
            "field": "calories_sort",
            "sortable": True,
            "align": "right",
        },
        {
            "name": "avg_hr",
            "label": t("Avg HR"),
            "field": "avg_hr_sort",
            "sortable": True,
            "align": "right",
        },
        {
            "name": "elevation",
            "label": t("Elevation"),
            "field": "elevation_sort",
            "sortable": True,
            "align": "right",
        },
        {
            "name": "avg_power",
            "label": t("Avg Power"),
            "field": "avg_power_sort",
            "sortable": True,
            "align": "right",
        },
        {"name": "actions", "label": "", "field": "id", "sortable": False, "align": "center"},
    ]

    open_detail = create_workout_detail_modal(full_rows)
    row_index_by_id: dict[str, int] = {
        str(row_id): idx
        for idx, row_id in enumerate(row.get("id") for row in full_rows)
        if row_id is not None
    }

    table = ui.table(
        columns=columns,
        rows=table_rows,
        row_key="id",
        pagination={"sortBy": "date_sort", "descending": True, "rowsPerPage": 15},
    ).classes(TABLE_FULL_CLASSES)

    table.props(f'rows-per-page-label="{t("Records per page:")}"')
    of_label = t("of")
    table.props(f':pagination-label=\'(a, b, c) => a + "-" + b + " {of_label} " + c\'')

    for col_name, display_field in [
        ("date", "date"),
        ("activity_type", "activity_type"),
        ("duration", "duration"),
        ("distance", "distance"),
        ("calories", "calories"),
        ("avg_hr", "avg_hr"),
        ("elevation", "elevation"),
        ("avg_power", "avg_power"),
    ]:
        table.add_slot(
            f"body-cell-{col_name}",
            f'<q-td :props="props">{{{{ props.row.{display_field} }}}}</q-td>',
        )

    details_tooltip = t("Details")
    table.add_slot(
        "body-cell-actions",
        '<q-td :props="props">'
        f'<q-btn flat round dense icon="info" aria-label="{details_tooltip}" '
        f'title="{details_tooltip}"'
        " @click=\"$parent.$emit('open_detail', props.row.id)\">"
        f"<q-tooltip>{details_tooltip}</q-tooltip>"
        "</q-btn></q-td>",
    )

    def _handle_open_detail(e: Any) -> None:
        row_id = str(e.args)
        row_index = row_index_by_id.get(row_id)
        if row_index is not None:
            open_detail(row_index)

    table.on("open_detail", _handle_open_detail)


@ui.refreshable
def render_distance_range_selector() -> None:
    """Render the distance range slider for the workout table filter."""
    distance_unit = get_distance_unit()
    min_dist, max_dist = state.workouts.get_distance_bounds(
        unit=distance_unit,
        activity_type=state.selected_activity_type,
        start_date=state.start_date,
        end_date=state.end_date,
    )
    slider_min = math.floor(min_dist)
    slider_max = math.ceil(max_dist)

    if slider_min >= slider_max:
        return

    with ui.column().classes(RANGE_SELECTOR_COLUMN_CLASSES):
        dist_range = state.distance_range
        dist_label_fmt = t("Distance: {lo} – {hi} {unit}").format(
            lo="{lo}", hi="{hi}", unit=distance_unit
        )
        ui.label(
            dist_label_fmt.format(
                lo=str(int(dist_range.get("min", slider_min))),
                hi=str(int(dist_range.get("max", slider_max))),
            )
        ).classes(RANGE_LABEL_CLASSES).bind_text_from(
            state,
            "distance_range",
            backward=lambda r: dist_label_fmt.format(
                lo=str(int(r.get("min", slider_min))),
                hi=str(int(r.get("max", slider_max))),
            ),
        )
        ui.range(
            min=slider_min, max=slider_max, step=1, on_change=render_workout_table.refresh
        ).bind_value(state, "distance_range").bind_enabled_from(state, "file_loaded").classes(
            TABLE_FULL_CLASSES
        )


@ui.refreshable
def render_duration_range_selector() -> None:
    """Render the duration range slider for the workout table filter."""
    min_min, max_min = state.workouts.get_duration_bounds(
        activity_type=state.selected_activity_type,
        start_date=state.start_date,
        end_date=state.end_date,
    )
    slider_min = math.floor(min_min)
    slider_max = math.ceil(max_min)

    if slider_min >= slider_max:
        return

    with ui.column().classes(RANGE_SELECTOR_COLUMN_CLASSES):
        dur_range = state.duration_range_min
        dur_label_fmt = t("Duration: {lo} – {hi} min")
        ui.label(
            dur_label_fmt.format(
                lo=str(int(dur_range.get("min", slider_min))),
                hi=str(int(dur_range.get("max", slider_max))),
            )
        ).classes(RANGE_LABEL_CLASSES).bind_text_from(
            state,
            "duration_range_min",
            backward=lambda r: dur_label_fmt.format(
                lo=str(int(r.get("min", slider_min))),
                hi=str(int(r.get("max", slider_max))),
            ),
        )
        ui.range(
            min=slider_min, max=slider_max, step=1, on_change=render_workout_table.refresh
        ).bind_value(state, "duration_range_min").bind_enabled_from(state, "file_loaded").classes(
            TABLE_FULL_CLASSES
        )
