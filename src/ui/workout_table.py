"""Workout details table and range-filter selectors for Apple Health Analyzer."""

import logging
import math
from typing import Any

import pandas as pd
from nicegui import ui

from app_state import get_distance_unit, get_elevation_unit, get_temperature_unit, state
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
from units import METERS_TO_FEET, METERS_TO_MILES, celsius_to_fahrenheit

_logger = logging.getLogger(__name__)

# Sentinel used for missing optional numeric values so they sort to the bottom.
_MISSING_SORT = -1.0

# Only these fields are needed by the visible q-table columns and row-action event.
_TABLE_ROW_FIELDS: tuple[str, ...] = (
    "id",
    "date_sort",
    "date",
    "activity_type",
    "duration_sort",
    "duration",
    "distance_sort",
    "distance",
    "calories_sort",
    "calories",
    "avg_hr_sort",
    "avg_hr",
    "elevation_sort",
    "elevation",
    "avg_power_sort",
    "avg_power",
)


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
    temperature_unit = get_temperature_unit()
    rows: list[dict[str, Any]] = []

    # Pre-parse VO2Max dates once so _nearest_vo2_max avoids repeating the
    # pd.to_datetime() call for every running workout in the batch.
    vo2_df: pd.DataFrame = state.records_by_type.get("VO2Max")
    vo2_dates: pd.Series | None = None
    if not vo2_df.empty and "startDate" in vo2_df.columns:
        vo2_dates = pd.to_datetime(vo2_df["startDate"], errors="coerce").dt.tz_localize(None)

    for idx, (_, row) in enumerate(df.iterrows()):
        row_data = _extract_row_data(
            row, idx, language_code, distance_unit, elevation_unit, vo2_dates, temperature_unit
        )
        rows.append(row_data)

    return rows


def _extract_row_data(
    row: Any,
    idx: int,
    language_code: str,
    distance_unit: str = "km",
    elevation_unit: str = "m",
    vo2_dates: pd.Series | None = None,
    temperature_unit: str = "°C",
) -> dict[str, Any]:
    """Extract and format a single workout row.

    Args:
        row: A pandas Series representing a workout.
        idx: The row index.
        language_code: The current language code for date formatting.
        distance_unit: The display unit for distance values (``"km"`` or ``"mi"``).
        elevation_unit: The display unit for elevation values (``"m"`` or ``"ft"``).
        vo2_dates: Pre-parsed tz-naive VO2Max start dates; when provided avoids
            re-parsing inside :func:`_nearest_vo2_max` for each row.
        temperature_unit: The display unit for temperature (``"°C"`` or ``"°F"``).

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

    _, temp_display = _build_field_pair(
        row.get("WeatherTemperature"),
        lambda v: (
            f"{celsius_to_fahrenheit(v):.1f} °F" if temperature_unit == "°F" else f"{v:.1f} °C"
        ),
    )
    _, humidity_display = _build_field_pair(
        row.get("WeatherHumidity"),
        lambda v: f"{int(round(v))} %",
    )

    result: dict[str, Any] = {
        "id": f"{date_sort}_{idx}",
        "date_sort": date_sort,
        "date": date_display,
        "raw_activity_type": raw_activity,
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
        "temperature": temp_display,
        "humidity": humidity_display,
        # Route and distance_unit stored for all activity types so the Splits
        # tab can be enabled for any workout that has a GPS route (e.g. Cycling).
        "route": row.get("route"),
        "distance_unit": distance_unit,
    }

    if raw_activity == "Running":
        start_date_raw = row.get("startDate")
        workout_date = start_date_raw if isinstance(start_date_raw, pd.Timestamp) else None
        result.update(_extract_running_fields(row, workout_date, distance_unit, vo2_dates))
    elif raw_activity == "Walking":
        result.update(_extract_walking_fields(row, distance_unit))
    elif raw_activity == "Hiking":
        result.update(_extract_hiking_fields(row, distance_unit))
    elif raw_activity == "Swimming":
        result.update(_extract_swimming_fields(row))
    elif raw_activity == "Cycling":
        result.update(_extract_cycling_fields(row, distance_unit))

    return result


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
            distance_display = f"{distance_raw * METERS_TO_MILES:.2f} mi"
        else:
            distance_display = f"{distance_raw / 1000:.2f} km"
    else:
        distance_display = "–"
    return distance_raw, distance_display


def _format_pace(speed_km_h: float, distance_unit: str = "km") -> str:
    """Convert speed in km/h to a pace string using the active distance unit.

    Args:
        speed_km_h: Average speed in kilometres per hour.
        distance_unit: Display unit for the pace (``"km"`` or ``"mi"``).

    Returns:
        Pace string such as ``"6:00 /km"`` or ``"9:40 /mi"``, or ``"–"``
        when speed is non-positive.
    """
    if speed_km_h <= 0:
        return "–"
    if distance_unit == "mi":
        display_speed = speed_km_h * 1000.0 * METERS_TO_MILES
        suffix = "/mi"
    else:
        display_speed = speed_km_h
        suffix = "/km"
    pace_min = 60.0 / display_speed
    minutes = int(pace_min)
    seconds = int(round((pace_min - minutes) * 60))
    if seconds == 60:
        minutes += 1
        seconds = 0
    return f"{minutes}:{seconds:02d} {suffix}"


def _nearest_vo2_max(
    workout_date: pd.Timestamp | None,
    vo2_dates: pd.Series | None = None,
) -> str:
    """Return the VO2 max value (mL/min·kg) closest in time to *workout_date*.

    Looks up ``state.records_by_type["VO2Max"]`` and finds the record whose
    ``startDate`` is nearest to *workout_date*.

    Args:
        workout_date: The workout start date as a :class:`pd.Timestamp`.
        vo2_dates: Optional pre-parsed, tz-naive Series of VO2Max start dates.
            When provided it avoids re-parsing the dates on every call, which
            is important when processing many running workouts in a single batch.
            When ``None`` the dates are parsed from state on each call (backward-
            compatible behaviour used in tests and one-off lookups).

    Returns:
        A formatted string such as ``"50.1 mL/min·kg"``, or ``"–"`` when no
        VO2 max records are available or *workout_date* is ``None``.
    """
    if workout_date is None:
        return "–"
    vo2_df: pd.DataFrame = state.records_by_type.get("VO2Max")
    if vo2_df.empty or "startDate" not in vo2_df.columns or "value" not in vo2_df.columns:
        return "–"

    if vo2_dates is None:
        vo2_dates = pd.to_datetime(vo2_df["startDate"], errors="coerce").dt.tz_localize(None)
    if not vo2_dates.notna().any():
        return "–"
    deltas = (vo2_dates - workout_date).abs()
    min_idx = deltas.idxmin()
    value = _safe_float(vo2_df.loc[min_idx, "value"])
    if value is None:
        return "–"
    return f"{value:.1f} mL/min·kg"


def _extract_running_fields(
    row: Any,
    workout_date: pd.Timestamp | None,
    distance_unit: str = "km",
    vo2_dates: pd.Series | None = None,
) -> dict[str, Any]:
    """Extract running-specific display fields from a workout DataFrame row.

    Fields are populated only when the corresponding statistics are present.
    Fields that are absent or ``NaN`` fall back to the missing-data sentinel
    ``"–"`` so the modal can hide them automatically.

    Args:
        row: A pandas Series representing a running workout.
        workout_date: The workout start date used for VO2 max look-up.
        distance_unit: ``"km"`` or ``"mi"`` (affects pace display label).
        vo2_dates: Pre-parsed, tz-naive VO2Max start dates; passed through to
            :func:`_nearest_vo2_max` to avoid repeating the parse per workout.

    Returns:
        A dict with running-specific display and sort values.
    """
    # --- Pace (derived from averageRunningSpeed) ---
    speed_raw = _safe_float(row.get("averageRunningSpeed"))
    pace_display = _format_pace(speed_raw, distance_unit) if speed_raw is not None else "–"
    pace_sort = (60.0 / speed_raw) if speed_raw is not None and speed_raw > 0 else _MISSING_SORT

    # --- Cadence ---
    cadence_sort, cadence_display = _build_field_pair(
        row.get("averageRunningCadence"),
        lambda v: f"{int(round(v))} spm",
    )

    # --- Stride length ---
    stride_sort, stride_display = _build_field_pair(
        row.get("averageRunningStrideLength"),
        lambda v: f"{v:.2f} m",
    )

    # --- Vertical oscillation ---
    _, vo_display = _build_field_pair(
        row.get("averageRunningVerticalOscillation"),
        lambda v: f"{v:.1f} cm",
    )

    # --- Ground contact time ---
    _, gct_display = _build_field_pair(
        row.get("averageRunningGroundContactTime"),
        lambda v: f"{int(round(v))} ms",
    )

    # --- Step count ---
    _, step_count_display = _build_field_pair(
        row.get("sumStepCount"),
        lambda v: f"{int(round(v))}",
    )

    return {
        "pace_sort": pace_sort,
        "pace": pace_display,
        "cadence_sort": cadence_sort,
        "cadence": cadence_display,
        "stride_length_sort": stride_sort,
        "stride_length": stride_display,
        "vertical_oscillation": vo_display,
        "ground_contact_time": gct_display,
        "step_count": step_count_display,
        "vo2_max": _nearest_vo2_max(workout_date, vo2_dates),
    }


def _extract_walking_fields(
    row: Any,
    distance_unit: str = "km",
) -> dict[str, Any]:
    """Extract walking-specific display fields from a workout DataFrame row.

    Fields are populated only when the corresponding statistics are present.
    Fields that are absent or ``NaN`` fall back to the missing-data sentinel
    ``"–"`` so the modal can hide them automatically.

    Args:
        row: A pandas Series representing a walking workout.
        distance_unit: ``"km"`` or ``"mi"`` (affects pace display).

    Returns:
        A dict with walking-specific display and sort values.
    """
    # --- Pace (derived from averageWalkingSpeed) ---
    speed_raw = _safe_float(row.get("averageWalkingSpeed"))
    pace_display = _format_pace(speed_raw, distance_unit) if speed_raw is not None else "–"
    pace_sort = (60.0 / speed_raw) if speed_raw is not None and speed_raw > 0 else _MISSING_SORT

    # --- Cadence ---
    cadence_sort, cadence_display = _build_field_pair(
        row.get("averageWalkingCadence"),
        lambda v: f"{int(round(v))} spm",
    )

    # --- Step length ---
    _, step_length_display = _build_field_pair(
        row.get("averageWalkingStepLength"),
        lambda v: f"{v:.2f} m",
    )

    # --- Step count ---
    _, step_count_display = _build_field_pair(
        row.get("sumStepCount"),
        lambda v: f"{int(round(v))}",
    )

    return {
        "pace_sort": pace_sort,
        "pace": pace_display,
        "cadence_sort": cadence_sort,
        "cadence": cadence_display,
        "step_length": step_length_display,
        "step_count": step_count_display,
    }


def _extract_hiking_fields(
    row: Any,
    distance_unit: str = "km",
) -> dict[str, Any]:
    """Extract hiking-specific display fields from a workout DataFrame row.

    Hiking workouts use the same HealthKit locomotion statistics as walking
    (``averageWalkingSpeed``, ``averageWalkingCadence``, ``averageWalkingStepLength``,
    ``sumStepCount``), so this function delegates to :func:`_extract_walking_fields`
    to avoid code duplication.

    Args:
        row: A pandas Series representing a hiking workout.
        distance_unit: ``"km"`` or ``"mi"`` (affects pace display).

    Returns:
        A dict with hiking-specific display and sort values.
    """
    return _extract_walking_fields(row, distance_unit)


def _extract_swimming_fields(row: Any) -> dict[str, Any]:
    """Extract swimming-specific fields from a workout DataFrame row.

    Passes the raw ``swimming_events`` list and lap-length metadata through
    to the row dict so the workout detail modal can build the interval table.

    Args:
        row: A pandas Series representing a swimming workout.

    Returns:
        A dict with swimming-specific fields for the modal.
    """
    events = row.get("swimming_events")
    # swimming_events is a list stored as an object in the DataFrame column;
    # guard against NaN (float) or other non-list values.
    swimming_events: list[Any] = events if isinstance(events, list) else []

    # LapLength is stored as a float (metres) after ExportParser._parse_value.
    lap_length_raw = _safe_float(row.get("LapLength"))
    lap_length_m = lap_length_raw if lap_length_raw is not None and lap_length_raw > 0 else 0.0

    # Location type (1=Pool, 2=Open Water) is stored as an int after parse_metadata_value.
    location_raw = row.get("SwimmingLocationType")
    location_display: str
    if location_raw is not None:
        from logic.workout_detail_schema import SWIMMING_LOCATION_TYPES

        try:
            label = SWIMMING_LOCATION_TYPES.get(int(location_raw), str(location_raw))
            location_display = t(label)
        except (ValueError, TypeError):
            location_display = str(location_raw)
    else:
        location_display = "–"

    _, stroke_count_display = _build_field_pair(
        row.get("sumSwimmingStrokeCount"),
        lambda v: f"{int(round(v))}",
    )

    lap_length_display = f"{int(lap_length_m)} m" if lap_length_m > 0 else "–"

    return {
        "swimming_events": swimming_events,
        "lap_length_m": lap_length_m,
        "swimming_location": location_display,
        "swimming_stroke_count": stroke_count_display,
        "swimming_lap_length": lap_length_display,
    }


def _extract_cycling_fields(
    row: Any,
    distance_unit: str = "km",
) -> dict[str, Any]:
    """Extract cycling-specific display fields from a workout DataFrame row.

    Fields are populated only when the corresponding statistics are present.
    Fields that are absent or ``NaN`` fall back to the missing-data sentinel
    ``"–"`` so the modal can hide them automatically.

    Args:
        row: A pandas Series representing a cycling workout.
        distance_unit: ``"km"`` or ``"mi"`` (affects speed display unit).

    Returns:
        A dict with cycling-specific display values.
    """
    # --- Speed ---
    speed_raw = _safe_float(row.get("averageCyclingSpeed"))
    if speed_raw is not None and speed_raw > 0:
        if distance_unit == "mi":
            # km/h → mph: multiply by 1000 (m/km) then by METERS_TO_MILES (mile/m)
            cycling_speed_display = f"{speed_raw * 1000.0 * METERS_TO_MILES:.1f} mph"
        else:
            cycling_speed_display = f"{speed_raw:.1f} km/h"
    else:
        cycling_speed_display = "–"

    # --- Cadence ---
    _, cycling_cadence_display = _build_field_pair(
        row.get("averageCyclingCadence"),
        lambda v: f"{int(round(v))} rpm",
    )

    # --- Power ---
    _, cycling_power_display = _build_field_pair(
        row.get("averageCyclingPower"),
        lambda v: f"{int(round(v))} W",
    )

    # --- Functional Threshold Power ---
    _, cycling_ftp_display = _build_field_pair(
        row.get("averageCyclingFunctionalThresholdPower"),
        lambda v: f"{int(round(v))} W",
    )

    return {
        "cycling_speed": cycling_speed_display,
        "cycling_cadence": cycling_cadence_display,
        "cycling_power": cycling_power_display,
        "cycling_ftp": cycling_ftp_display,
    }


def _find_row_index(row_id: str, rows: list[dict[str, Any]]) -> int | None:
    """Return the index of the row with matching *row_id*, or ``None`` if missing."""
    for i, row in enumerate(rows):
        if row.get("id") == row_id:
            return i
    return None


def _build_table_rows(full_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return lightweight rows for q-table transport.

    This strips modal-only payloads (e.g. route traces, swimming intervals) from
    the table JSON sent to the browser while preserving all data needed for visible
    columns and action events.
    """
    return [{field: row.get(field) for field in _TABLE_ROW_FIELDS} for row in full_rows]


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
        {
            "name": "actions",
            "label": "",
            "field": "id",
            "sortable": False,
            "align": "center",
        },
    ]

    # Create the detail modal once; the returned callable opens it at a given index.
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

    # Translate Quasar's built-in pagination labels so they respect the active language.
    # rows-per-page-label overrides the "Records per page:" string label directly.
    # :pagination-label is a JavaScript function prop (evaluated by NiceGUI's `:` prefix
    # mechanism) that replaces the default "1-10 of 10" row-range indicator; the "of"
    # word is embedded at render time from the gettext catalog.
    table.props(f'rows-per-page-label="{t("Records per page:")}"')
    of_label = t("of")
    table.props(f':pagination-label=\'(a, b, c) => a + "-" + b + " {of_label} " + c\'')

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
