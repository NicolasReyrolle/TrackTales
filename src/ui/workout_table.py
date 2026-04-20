"""Workout details table and range-filter selectors for Apple Health Analyzer."""

import logging
import math
from typing import Any

import pandas as pd
from nicegui import ui

from app_state import get_distance_unit, get_elevation_unit, state
from i18n import get_language, t
from i18n.activity_types import activity_display_label
from ui.css import (
    LABEL_EMPTY_STATE_CLASSES,
    RANGE_LABEL_CLASSES,
    RANGE_SELECTOR_COLUMN_CLASSES,
    TABLE_FULL_CLASSES,
)
from ui.helpers import format_date_label, format_duration_label
from ui.workout_detail_modal import create_workout_detail_modal
from units import METERS_TO_FEET, METERS_TO_MILES

_logger = logging.getLogger(__name__)

# Sentinel used for missing optional numeric values so they sort to the bottom.
_MISSING_SORT = -1.0


def _safe_float(value: Any) -> float | None:
    """Return a float for numeric *value*, or None if it is missing/NaN."""
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(f) else f


def _build_field_pair(
    raw_value: Any,
    formatter: Any,
    missing_display: str = "–",
) -> tuple[float | str, str]:
    """Build a (sort_value, display_value) pair for a field.

    Args:
        raw_value: The raw value to process.
        formatter: A callable that takes the raw value and returns a display string,
                   or None if the value is missing/invalid.
        missing_display: String to display when value is missing.

    Returns:
        A tuple of (sort_value, display_value).
    """
    safe_val = _safe_float(raw_value)
    if safe_val is None:
        return _MISSING_SORT, missing_display
    display = formatter(safe_val)
    return safe_val, display


def _build_workout_rows() -> list[dict[str, Any]]:
    """Build table rows from the currently filtered workouts.

    Each row stores both a raw numeric value (used for column sorting) and a
    human-readable display string for every attribute.  Optional columns that
    are absent for a workout are filled with ``_MISSING_SORT`` / ``"–"``.
    """
    df = state.workouts._filter_workouts(
        state.selected_activity_type, state.start_date, state.end_date
    )

    if df.empty:
        return []

    # Apply distance range filter: state.distance_range stores values in the user's
    # preferred distance unit (km or mi); convert to metres for filtering.
    dist_range = state.distance_range
    distance_unit = get_distance_unit()
    dist_divisor = 1 / METERS_TO_MILES if distance_unit == "mi" else 1000.0
    dist_min_m = dist_range.get("min", 0.0) * dist_divisor
    dist_max_m = dist_range.get("max", 0.0) * dist_divisor
    if "distance" in df.columns and dist_min_m < dist_max_m:
        dist = df["distance"].fillna(0.0)
        df = df[(dist >= dist_min_m) & (dist <= dist_max_m)]

    # Apply duration range filter (convert minutes to seconds, the canonical storage unit).
    dur_range = state.duration_range_min
    dur_min_s = dur_range.get("min", 0.0) * 60.0
    dur_max_s = dur_range.get("max", 0.0) * 60.0
    if "duration" in df.columns and dur_min_s < dur_max_s:
        dur = df["duration"].fillna(0.0)
        df = df[(dur >= dur_min_s) & (dur <= dur_max_s)]

    if df.empty:
        return []

    if "startDate" in df.columns:
        df = df.sort_values("startDate", ascending=False)

    language_code = get_language()
    elevation_unit = get_elevation_unit()
    rows: list[dict[str, Any]] = []

    for idx, (_, row) in enumerate(df.iterrows()):
        row_data = _extract_row_data(row, idx, language_code, distance_unit, elevation_unit)
        rows.append(row_data)

    return rows


def _extract_row_data(
    row: Any,
    idx: int,
    language_code: str,
    distance_unit: str = "km",
    elevation_unit: str = "m",
) -> dict[str, Any]:
    """Extract and format a single workout row.

    Args:
        row: A pandas Series representing a workout.
        idx: The row index.
        language_code: The current language code for date formatting.
        distance_unit: The display unit for distance values (``"km"`` or ``"mi"``).
        elevation_unit: The display unit for elevation values (``"m"`` or ``"ft"``).

    Returns:
        A dictionary with sort and display values for all columns.
    """
    date_sort, date_display = _extract_date_field(row, language_code)
    raw_activity = str(row.get("activityType") or "")
    activity_type = activity_display_label(raw_activity) if raw_activity else "–"
    duration_sort, duration_display = _build_field_pair(row.get("duration"), format_duration_label)
    distance_sort, distance_display = _extract_distance_field(row, distance_unit)
    calories_sort, calories_display = _build_field_pair(
        row.get("sumActiveEnergyBurned"),
        lambda v: f"{int(round(v))} kcal",
    )
    hr_sort, hr_display = _build_field_pair(
        row.get("averageHeartRate"),
        lambda v: f"{int(round(v))} bpm",
    )
    if elevation_unit == "ft":
        elev_sort, elev_display = _build_field_pair(
            row.get("ElevationAscended"),
            lambda v: f"{int(round(v * METERS_TO_FEET))} ft",
        )
    else:
        elev_sort, elev_display = _build_field_pair(
            row.get("ElevationAscended"),
            lambda v: f"{int(round(v))} m",
        )
    power_sort, power_display = _build_field_pair(
        row.get("averageRunningPower"),
        lambda v: f"{int(round(v))} W",
    )

    return {
        "id": f"{date_sort}_{idx}",
        "date_sort": date_sort,
        "date": date_display,
        "activity_type": activity_type,
        "duration_sort": duration_sort,
        "duration": duration_display,
        "distance_sort": distance_sort,
        "distance": distance_display,
        "calories_sort": calories_sort,
        "calories": calories_display,
        "avg_hr_sort": hr_sort,
        "avg_hr": hr_display,
        "elevation_sort": elev_sort,
        "elevation": elev_display,
        "avg_power_sort": power_sort,
        "avg_power": power_display,
    }


def _extract_date_field(row: Any, language_code: str) -> tuple[float, str]:
    """Extract date sort and display values."""
    start_date_raw = row.get("startDate")
    ts: pd.Timestamp | None = start_date_raw if isinstance(start_date_raw, pd.Timestamp) else None
    date_sort = float(ts.timestamp()) if ts is not None else _MISSING_SORT
    date_display = format_date_label(ts, language_code) if ts is not None else "–"
    return date_sort, date_display


def _extract_distance_field(row: Any, distance_unit: str = "km") -> tuple[float | str, str]:
    """Extract distance sort and display values (stored in metres)."""
    distance_raw = _safe_float(row.get("distance"))
    if distance_raw is None:
        return _MISSING_SORT, "–"
    if distance_raw > 0:
        if distance_unit == "mi":
            distance_display = f"{distance_raw * METERS_TO_MILES:.1f} mi"
        else:
            distance_display = f"{distance_raw / 1000:.1f} km"
    else:
        distance_display = "–"
    return distance_raw, distance_display


def _find_row_index(row_id: str, rows: list[dict[str, Any]]) -> int | None:
    """Return the index of the row with matching *row_id*, or ``None`` if missing."""
    for i, row in enumerate(rows):
        if row.get("id") == row_id:
            return i
    return None


@ui.refreshable
def render_workout_table() -> None:
    """Render the workout details table with sortable numeric columns and pagination."""
    if not state.file_loaded:
        ui.label(t("Load a file to see workout details.")).classes(LABEL_EMPTY_STATE_CLASSES)
        return

    rows = _build_workout_rows()
    _logger.debug("Rendering workout table with %d rows", len(rows))

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
        {
            "name": "actions",
            "label": "",
            "field": "id",
            "sortable": False,
            "align": "center",
        },
    ]

    # Create the detail modal once; the returned callable opens it at a given index.
    open_detail = create_workout_detail_modal(rows)

    table = ui.table(
        columns=columns,
        rows=rows,
        row_key="id",
        pagination={"sortBy": "date_sort", "descending": True, "rowsPerPage": 15},
    ).classes(TABLE_FULL_CLASSES)

    # Render formatted display values via body-cell slots while keeping raw
    # numeric field values for sorting.
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

    # Details button: icon-only button with a tooltip. Uses $parent.$emit so the
    # event reaches NiceGUI's Python listener (registered on the q-table's wrapper).
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
        row_index = _find_row_index(row_id, rows)
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

    # No meaningful range to filter (no data or all workouts have the same distance).
    if slider_min >= slider_max:
        return

    with ui.column().classes(RANGE_SELECTOR_COLUMN_CLASSES):
        dist_range = state.distance_range
        # Pre-compute translated format string once at render time so the
        # bind_text_from backward never calls t() in a deferred binding context
        # where app.storage.user may not yet be available (causing English reversion).
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

    # No meaningful range to filter (no data or all workouts have the same duration).
    if slider_min >= slider_max:
        return

    with ui.column().classes(RANGE_SELECTOR_COLUMN_CLASSES):
        dur_range = state.duration_range_min
        # Pre-compute translated format string once at render time (same reasoning
        # as render_distance_range_selector).
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
