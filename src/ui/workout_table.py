"""Workout details table for Apple Health Analyzer."""

import logging
from typing import Any

import pandas as pd
from nicegui import ui

from app_state import state
from i18n import get_language, t
from ui.css import LABEL_EMPTY_STATE_CLASSES, TABLE_FULL_CLASSES
from ui.helpers import format_date_label, format_duration_label

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

    if "startDate" in df.columns:
        df = df.sort_values("startDate", ascending=False)

    language_code = get_language()
    rows: list[dict[str, Any]] = []

    for idx, (_, row) in enumerate(df.iterrows()):
        # ── Date ────────────────────────────────────────────────────────────
        start_date_raw = row.get("startDate")
        ts: pd.Timestamp | None = (
            start_date_raw if isinstance(start_date_raw, pd.Timestamp) else None
        )
        date_sort = float(ts.timestamp()) if ts is not None else _MISSING_SORT
        date_display = format_date_label(ts, language_code) if ts is not None else "–"

        # ── Activity type ────────────────────────────────────────────────────
        activity_type = str(row.get("activityType") or "–")

        # ── Duration ────────────────────────────────────────────────────────
        duration_raw = _safe_float(row.get("duration"))
        duration_sort = duration_raw if duration_raw is not None else _MISSING_SORT
        duration_display = format_duration_label(duration_raw) if duration_raw is not None else "–"

        # ── Distance (optional, stored in metres) ────────────────────────────
        distance_raw = _safe_float(row.get("distance"))
        distance_sort = distance_raw if distance_raw is not None else _MISSING_SORT
        if distance_raw is not None and distance_raw > 0:
            distance_display = f"{distance_raw / 1000:.1f} km"
        else:
            distance_display = "–"

        # ── Calories (optional, kcal) ────────────────────────────────────────
        calories_raw = _safe_float(row.get("sumActiveEnergyBurned"))
        calories_sort = calories_raw if calories_raw is not None else _MISSING_SORT
        calories_display = f"{int(round(calories_raw))} kcal" if calories_raw is not None else "–"

        # ── Average heart rate (optional, bpm) ───────────────────────────────
        hr_raw = _safe_float(row.get("averageHeartRate"))
        hr_sort = hr_raw if hr_raw is not None else _MISSING_SORT
        hr_display = f"{int(round(hr_raw))} bpm" if hr_raw is not None else "–"

        # ── Elevation ascended (optional, stored in metres) ──────────────────
        elev_raw = _safe_float(row.get("ElevationAscended"))
        elev_sort = elev_raw if elev_raw is not None else _MISSING_SORT
        elev_display = f"{int(round(elev_raw))} m" if elev_raw is not None else "–"

        # ── Average running power (optional, Watts) ──────────────────────────
        power_raw = _safe_float(row.get("averageRunningPower"))
        power_sort = power_raw if power_raw is not None else _MISSING_SORT
        power_display = f"{int(round(power_raw))} W" if power_raw is not None else "–"

        rows.append(
            {
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
        )

    return rows


@ui.refreshable
def render_workout_table() -> None:
    """Render the workout details table with sortable numeric columns."""
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
    ]

    table = ui.table(
        columns=columns,
        rows=rows,
        row_key="id",
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
