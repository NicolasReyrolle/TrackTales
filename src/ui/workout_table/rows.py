"""Row-building helpers for the workout table.

All functions here are pure data transformations with no NiceGUI UI calls.
"""

import logging
import math
from datetime import datetime
from typing import Any, cast

import pandas as pd

from app_state import get_distance_unit, get_elevation_unit, get_temperature_unit, state
from i18n import get_language, t
from i18n.activity_types import activity_display_label
from logic.workout_manager.workout_route import WorkoutRoute
from ui.helpers import format_date_label, format_duration_label
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
    """Build a (sort_value, display_value) pair for a field."""
    safe_val = _safe_float(raw_value)
    if safe_val is None:
        return _MISSING_SORT, missing_display
    display = formatter(safe_val)
    return safe_val, display


def _apply_range_filters(df: pd.DataFrame, distance_unit: str) -> pd.DataFrame:
    """Apply distance and duration range filters from state to *df*."""
    dist_range = state.distance_range
    dist_divisor = 1 / METERS_TO_MILES if distance_unit == "mi" else 1000.0
    dist_min_m = dist_range.get("min", 0.0) * dist_divisor
    dist_max_m = dist_range.get("max", 0.0) * dist_divisor
    if "distance" in df.columns and dist_min_m < dist_max_m:
        dist = df["distance"].fillna(0.0)
        df = df[(dist >= dist_min_m) & (dist <= dist_max_m)]

    dur_range = state.duration_range_min
    dur_min_s = dur_range.get("min", 0.0) * 60.0
    dur_max_s = dur_range.get("max", 0.0) * 60.0
    if "duration" in df.columns and dur_min_s < dur_max_s:
        dur = df["duration"].fillna(0.0)
        df = df[(dur >= dur_min_s) & (dur <= dur_max_s)]

    return df


def _normalize_datetime(value: Any) -> datetime | None:
    """Return a timezone-normalized naive datetime, or ``None`` when unavailable."""
    if value is None:
        return None
    try:
        ts = pd.Timestamp(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(ts):
        return None
    if ts.tzinfo is not None:
        ts = ts.tz_convert("UTC").tz_localize(None)
    return ts.to_pydatetime()


def _extract_workout_heart_rate_samples(
    heart_rate_samples: pd.DataFrame,
    start_date: datetime | None,
    end_date: datetime | None,
) -> list[tuple[datetime, float]]:
    """Return heart-rate samples whose timestamps fall within the workout bounds."""
    if heart_rate_samples.empty or start_date is None or end_date is None:
        return []
    samples = heart_rate_samples[
        (heart_rate_samples["startDate"] >= start_date)
        & (heart_rate_samples["startDate"] <= end_date)
    ]
    return list(
        zip(
            samples["startDate"].map(lambda ts: ts.to_pydatetime()).tolist(),
            samples["value"].astype(float).tolist(),
            strict=False,
        )
    )


def _annotate_route_with_heart_rate(
    route: Any,
    heart_rate_samples: list[tuple[datetime, float]],
) -> Any:
    """Return a copy of *route* with nearest heart-rate samples attached to each point."""
    if not heart_rate_samples:
        return route
    if not isinstance(route, WorkoutRoute):
        return route
    if route.is_empty:
        return route

    annotated_points = []
    sample_index = 0
    for point in route.points:
        point_time = _normalize_datetime(point.time)
        if point_time is None:
            annotated_points.append(point)
            continue
        while (
            sample_index + 1 < len(heart_rate_samples)
            and heart_rate_samples[sample_index + 1][0] <= point_time
        ):
            sample_index += 1
        closest_index = sample_index
        if sample_index + 1 < len(heart_rate_samples):
            previous_delta = abs((point_time - heart_rate_samples[sample_index][0]).total_seconds())
            next_delta = abs((heart_rate_samples[sample_index + 1][0] - point_time).total_seconds())
            if next_delta < previous_delta:
                closest_index = sample_index + 1
        heart_rate = heart_rate_samples[closest_index][1]
        annotated_points.append(
            point.__class__(
                time=point.time,
                latitude=point.latitude,
                longitude=point.longitude,
                altitude=point.altitude,
                speed=point.speed,
                heart_rate=heart_rate,
            )
        )
    return WorkoutRoute(points=annotated_points)


def _log_malformed_route_fragment(
    row: Any,
    route_value: Any,
    *,
    field_name: str,
    workout_index: object | None,
) -> None:
    """Log malformed route data using non-sensitive metadata only."""
    xml_fragment = row.get("xmlFragment")
    workout_ref = f" at index {workout_index}" if workout_index is not None else ""
    has_xml_fragment = isinstance(xml_fragment, str) and bool(xml_fragment)
    malformed_count = len(route_value) if isinstance(route_value, list) else 1
    _logger.debug(
        "Skipping heart-rate route enrichment for malformed %s%s "
        "(type=%s, count=%d, has_xml_fragment=%s)",
        field_name,
        workout_ref,
        type(route_value).__name__,
        malformed_count,
        has_xml_fragment,
    )


def _is_missing_route_placeholder(value: Any) -> bool:
    """Return True when *value* is an expected missing-route placeholder."""
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _build_workout_rows(
    activity_type: str | None = None,
    skip_range_filters: bool = False,
) -> list[dict[str, Any]]:
    """Build table rows from the currently filtered workouts."""
    df = state.workouts._filter_workouts(
        activity_type if activity_type is not None else state.selected_activity_type,
        state.start_date,
        state.end_date,
    )

    if df.empty:
        return []

    distance_unit = get_distance_unit()

    if not skip_range_filters:
        df = _apply_range_filters(df, distance_unit)

    if df.empty:
        return []

    if "startDate" in df.columns:
        df = df.sort_values("startDate", ascending=False)

    language_code = get_language()
    elevation_unit = get_elevation_unit()
    temperature_unit = get_temperature_unit()
    rows: list[dict[str, Any]] = []

    vo2_df: pd.DataFrame = state.records_by_type.get("VO2Max")
    vo2_dates: pd.Series | None = None
    if not vo2_df.empty and "startDate" in vo2_df.columns:
        vo2_dates = pd.to_datetime(vo2_df["startDate"], errors="coerce").dt.tz_localize(None)

    for idx, (workout_index, row) in enumerate(df.iterrows()):
        row_data = _extract_row_data(
            row,
            idx,
            language_code,
            distance_unit,
            elevation_unit,
            vo2_dates,
            temperature_unit,
            workout_index=workout_index,
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
    workout_index: object | None = None,
) -> dict[str, Any]:
    """Extract and format a single workout row."""
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
    elev_sort, elev_display = _extract_elevation_field(row, elevation_unit)
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
        "workout_index": workout_index,
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
        "route": row.get("route"),
        "route_parts": row.get("route_parts"),
        "distance_unit": distance_unit,
        "workout_start_utc": row.get("startDateUtc", row.get("startDate")),
        "workout_end_utc": row.get("endDateUtc", row.get("endDate")),
    }

    start_date_raw = row.get("startDate")
    workout_date: pd.Timestamp | None = (
        start_date_raw if isinstance(start_date_raw, pd.Timestamp) else None
    )
    result["vo2_max"] = _nearest_vo2_max(workout_date, vo2_dates)

    _apply_activity_specific_fields(result, row, raw_activity, distance_unit)

    return result


def _extract_elevation_field(row: Any, elevation_unit: str) -> tuple[float | str, str]:
    """Extract elevation sort/display values with the selected unit."""
    if elevation_unit == "ft":
        return _build_field_pair(
            row.get("ElevationAscended"),
            lambda v: f"{int(round(v * METERS_TO_FEET))} ft",
        )
    return _build_field_pair(
        row.get("ElevationAscended"),
        lambda v: f"{int(round(v))} m",
    )


def _enrich_routes_with_heart_rate(
    result: dict[str, Any],
    row: Any,
    heart_rate_samples: pd.DataFrame | None,
    workout_index: object | None,
) -> None:
    """Attach nearest heart-rate values to route and route parts when available."""
    workout_start = _normalize_datetime(row.get("startDateUtc", row.get("startDate")))
    workout_end = _normalize_datetime(row.get("endDateUtc", row.get("endDate")))
    workout_heart_rate_samples = _extract_workout_heart_rate_samples(
        heart_rate_samples if heart_rate_samples is not None else pd.DataFrame(),
        workout_start,
        workout_end,
    )
    if not workout_heart_rate_samples:
        return

    route_value = result.get("route")
    if not _is_missing_route_placeholder(route_value) and not isinstance(route_value, WorkoutRoute):
        _log_malformed_route_fragment(
            row, route_value, field_name="route", workout_index=workout_index
        )
    result["route"] = _annotate_route_with_heart_rate(
        cast(WorkoutRoute | None, route_value),
        workout_heart_rate_samples,
    )

    route_parts = result.get("route_parts")
    if not isinstance(route_parts, list):
        return

    invalid_route_parts = [
        part
        for part in route_parts
        if not _is_missing_route_placeholder(part) and not isinstance(part, WorkoutRoute)
    ]
    if invalid_route_parts:
        _log_malformed_route_fragment(
            row,
            invalid_route_parts,
            field_name="route_parts",
            workout_index=workout_index,
        )
    result["route_parts"] = [
        _annotate_route_with_heart_rate(part, workout_heart_rate_samples)
        if isinstance(part, WorkoutRoute)
        else part
        for part in route_parts
    ]


def _apply_activity_specific_fields(
    result: dict[str, Any],
    row: Any,
    raw_activity: str,
    distance_unit: str,
) -> None:
    """Populate sport-specific fields for the workout row."""
    if raw_activity == "Running":
        result.update(_extract_running_fields(row, distance_unit))
        return
    if raw_activity == "Walking":
        result.update(_extract_walking_fields(row, distance_unit))
        return
    if raw_activity == "Hiking":
        result.update(_extract_hiking_fields(row, distance_unit))
        return
    if raw_activity == "Swimming":
        result.update(_extract_swimming_fields(row))
        return
    if raw_activity == "Cycling":
        result.update(_extract_cycling_fields(row, distance_unit))


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
    """Convert speed in km/h to a pace string using the active distance unit."""
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
    """Return the VO2 max value (mL/min·kg) closest in time to *workout_date*."""
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
    distance_unit: str = "km",
) -> dict[str, Any]:
    """Extract running-specific display fields from a workout DataFrame row."""
    speed_raw = _safe_float(row.get("averageRunningSpeed"))
    pace_display = _format_pace(speed_raw, distance_unit) if speed_raw is not None else "–"
    pace_sort = (60.0 / speed_raw) if speed_raw is not None and speed_raw > 0 else _MISSING_SORT

    cadence_sort, cadence_display = _build_field_pair(
        row.get("averageRunningCadence"),
        lambda v: f"{int(round(v))} spm",
    )
    stride_sort, stride_display = _build_field_pair(
        row.get("averageRunningStrideLength"),
        lambda v: f"{v:.2f} m",
    )
    _, vo_display = _build_field_pair(
        row.get("averageRunningVerticalOscillation"),
        lambda v: f"{v:.1f} cm",
    )
    _, gct_display = _build_field_pair(
        row.get("averageRunningGroundContactTime"),
        lambda v: f"{int(round(v))} ms",
    )
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
    }


def _extract_walking_fields(
    row: Any,
    distance_unit: str = "km",
) -> dict[str, Any]:
    """Extract walking-specific display fields from a workout DataFrame row."""
    speed_raw = _safe_float(row.get("averageWalkingSpeed"))
    pace_display = _format_pace(speed_raw, distance_unit) if speed_raw is not None else "–"
    pace_sort = (60.0 / speed_raw) if speed_raw is not None and speed_raw > 0 else _MISSING_SORT

    cadence_sort, cadence_display = _build_field_pair(
        row.get("averageWalkingCadence"),
        lambda v: f"{int(round(v))} spm",
    )
    _, step_length_display = _build_field_pair(
        row.get("averageWalkingStepLength"),
        lambda v: f"{v:.2f} m",
    )
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
    """Extract hiking-specific display fields (delegates to walking helpers)."""
    return _extract_walking_fields(row, distance_unit)


def _extract_swimming_fields(row: Any) -> dict[str, Any]:
    """Extract swimming-specific fields from a workout DataFrame row."""
    events = row.get("swimming_events")
    swimming_events: list[Any] = events if isinstance(events, list) else []

    lap_length_raw = _safe_float(row.get("LapLength"))
    lap_length_m = lap_length_raw if lap_length_raw is not None and lap_length_raw > 0 else 0.0

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
    """Extract cycling-specific display fields from a workout DataFrame row."""
    speed_raw = _safe_float(row.get("averageCyclingSpeed"))
    if speed_raw is not None and speed_raw > 0:
        if distance_unit == "mi":
            cycling_speed_display = f"{speed_raw * 1000.0 * METERS_TO_MILES:.1f} mph"
        else:
            cycling_speed_display = f"{speed_raw:.1f} km/h"
    else:
        cycling_speed_display = "–"

    _, cycling_cadence_display = _build_field_pair(
        row.get("averageCyclingCadence"),
        lambda v: f"{int(round(v))} rpm",
    )
    _, cycling_power_display = _build_field_pair(
        row.get("averageCyclingPower"),
        lambda v: f"{int(round(v))} W",
    )
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
    """Return lightweight rows for q-table transport (strips modal-only payloads)."""
    return [{field: row.get(field) for field in _TABLE_ROW_FIELDS} for row in full_rows]
