"""Workout detail modal dialog for Apple Health Analyzer."""

import asyncio
import json
from collections.abc import Callable
from math import isfinite
from typing import Any, TypeAlias, cast

from nicegui import background_tasks, ui

from i18n import t
from logic.workout_detail_schema import PER_TYPE_FIELDS
from logic.workout_manager.swimming import (
    SwimInterval,
    build_swim_interval_display_rows,
    build_swim_intervals,
)
from logic.workout_manager.workout_route import WorkoutRoute
from ui.css import (
    BUTTON_DENSE_PROPS,
    LABEL_MUTED_CLASSES,
    LABEL_UPPERCASE_CLASSES,
    MODAL_CARD_CLASSES,
    MODAL_CENTERED_CONTENT_CLASSES,
    MODAL_CENTERED_ROW_CLASSES,
    MODAL_COMPARISON_RANK_CLASSES,
    MODAL_COMPARISON_TABLE_CLASSES,
    MODAL_FIELD_LABEL_CLASSES,
    MODAL_FIELD_ROW_CLASSES,
    MODAL_FIELD_VALUE_CLASSES,
    MODAL_HEADER_ROW_CLASSES,
    MODAL_NAV_COUNTER_CLASSES,
    MODAL_NAV_ROW_CLASSES,
    MODAL_ROUTE_MAP_CONTAINER_CLASSES,
    MODAL_ROUTE_MAP_HTML_CLASSES,
    MODAL_ROUTE_PROFILE_CLASSES,
    MODAL_ROUTE_PROFILE_CONTAINER_CLASSES,
    MODAL_SPLITS_TABLE_CLASSES,
    MODAL_SWIM_TABLE_CLASSES,
    MODAL_TAB_PANELS_CLASSES,
    TABLE_DENSE_FLAT_PROPS,
    TABS_FULL_CLASSES,
)
from ui.helpers import _format_elevation_change, _format_split_pace, _format_split_speed
from ui.workout_detail_modal.comparisons import (
    _do_refresh_comparisons_tab,
    _get_row_routes,
)
from units import METERS_TO_MILES

#: Callable returning a translated label string; alias for readability.
_LabelFn: TypeAlias = Callable[[], str]

#: i18n key reused across GPS-dependent modal sections.
_NO_GPS_ROUTE_MSG = "No GPS route available."
_M_S_TO_KM_H = 3.6
_SECONDS_PER_MINUTE = 60.0
_METERS_PER_KM = 1000.0
_MIN_MOVING_SPEED_M_S = 0.5
_PACE_SMOOTHING_WINDOW_M = 200.0
_MIN_ROLLING_SEGMENTS = 1

# ---------------------------------------------------------------------------
# Shared label-function constants reused across multiple field display lists.
# These are defined as functions so that ``t(...)`` is called at render time,
# keeping the string literals visible to pybabel for catalog extraction while
# eliminating duplication across the Running/Walking/Hiking display specs.
# ---------------------------------------------------------------------------


def _label_avg_pace() -> str:
    """Return the translated label for the average pace field."""
    return t("Avg Pace")


def _label_avg_cadence() -> str:
    """Return the translated label for the average cadence field."""
    return t("Avg Cadence")


def _label_step_count() -> str:
    """Return the translated label for the step count field."""
    return t("Step Count")


#: Ordered list of ``(row_key, label_fn)`` for the generic detail view.
#: Each ``label_fn`` is a zero-argument callable that returns the translated
#: label at render time.  Using literal ``t("…")`` calls inside the lambdas
#: lets ``pybabel extract`` discover every msgid during catalog regeneration.
#: Fields whose value is ``"–"`` (missing) are hidden automatically.
_FIELD_DISPLAY: list[tuple[str, _LabelFn]] = [
    ("date", lambda: t("Date")),
    ("activity_type", lambda: t("Activity")),
    ("duration", lambda: t("Duration")),
    ("distance", lambda: t("Distance")),
    ("calories", lambda: t("Calories")),
    ("avg_hr", lambda: t("Avg HR")),
    ("vo2_max", lambda: t("VO₂ Max")),
    ("elevation", lambda: t("Elevation Gain")),
    ("avg_power", lambda: t("Avg Power")),
    ("temperature", lambda: t("Temperature")),
    ("humidity", lambda: t("Humidity")),
]

#: Running-specific fields shown in the Activity tab when the workout is Running.
#: All values are ``"–"`` for non-running workouts and are hidden automatically.
_RUNNING_FIELD_DISPLAY: list[tuple[str, _LabelFn]] = [
    ("pace", _label_avg_pace),
    ("cadence", _label_avg_cadence),
    ("stride_length", lambda: t("Avg Stride Length")),
    ("vertical_oscillation", lambda: t("Avg Vertical Oscillation")),
    ("ground_contact_time", lambda: t("Avg Ground Contact Time")),
    ("step_count", _label_step_count),
]

#: Walking-specific fields shown in the Activity tab when the workout is Walking.
#: All values are ``"–"`` for non-walking workouts and are hidden automatically.
_WALKING_FIELD_DISPLAY: list[tuple[str, _LabelFn]] = [
    ("pace", _label_avg_pace),
    ("cadence", _label_avg_cadence),
    ("step_length", lambda: t("Avg Step Length")),
    ("step_count", _label_step_count),
]

#: Hiking-specific fields shown in the Activity tab when the workout is Hiking.
#: Elevation gain is included here because it is the primary hiking metric.
#: The remaining locomotion fields (pace, cadence, step length, step count) are
#: sourced from the same HealthKit walking statistics as :data:`_WALKING_FIELD_DISPLAY`,
#: avoiding code duplication in :func:`~ui.workout_table._extract_hiking_fields`.
_HIKING_FIELD_DISPLAY: list[tuple[str, _LabelFn]] = [
    ("elevation", lambda: t("Elevation Gain")),
    ("pace", _label_avg_pace),
    ("cadence", _label_avg_cadence),
    ("step_length", lambda: t("Avg Step Length")),
    ("step_count", _label_step_count),
]

#: Swimming-specific summary fields shown in the Activity tab when the workout is Swimming.
_SWIMMING_FIELD_DISPLAY: list[tuple[str, _LabelFn]] = [
    ("swimming_location", lambda: t("Location")),
    ("swimming_lap_length", lambda: t("Lap Length")),
    ("swimming_stroke_count", lambda: t("Total Strokes")),
]

#: Cycling-specific fields shown in the Activity tab when the workout is Cycling.
#: Speed, cadence, power, and functional threshold power are shown when available.
_CYCLING_FIELD_DISPLAY: list[tuple[str, _LabelFn]] = [
    ("cycling_speed", lambda: t("Avg Speed")),
    ("cycling_cadence", _label_avg_cadence),
    ("cycling_power", lambda: t("Avg Power")),
    ("cycling_ftp", lambda: t("Functional Threshold Power")),
]


def _build_swim_display_rows(intervals: list[SwimInterval]) -> list[dict[str, Any]]:
    """Build display-ready rows for the swim interval table.

    Delegates to :func:`~logic.workout_manager.swimming.build_swim_interval_display_rows`
    which merges all laps within each interval into a single summary row.
    All stroke labels are translated here since
    :mod:`logic.workout_manager.swimming` is i18n-agnostic.

    Args:
        intervals: Ordered list of :class:`~logic.workout_manager.swimming.SwimInterval`
            objects produced by :func:`~logic.workout_manager.swimming.build_swim_intervals`.

    Returns:
        List of row dicts ready for assignment to a ``ui.table``.
    """
    return [
        {**row, "stroke": t(row["stroke"])} if row.get("stroke") else row
        for row in build_swim_interval_display_rows(intervals)
    ]


def _format_split_rows(
    splits: list[dict[str, Any]],
    distance_unit: str,
) -> list[dict[str, Any]]:
    """Format raw split dicts into display rows suitable for a ``ui.table``.

    Args:
        splits: List of split dicts from
            :meth:`~logic.workout_manager.workout_route.WorkoutRoute.compute_splits`.
        distance_unit: Active distance unit, ``"km"`` or ``"mi"``.  Controls
            the pace scaling, speed unit, and elevation unit.

    Returns:
        List of row dicts with ``"split"``, ``"pace_str"``, ``"speed_str"``,
        and ``"elev_str"`` keys ready for direct assignment to ``ui.table.rows``.
    """
    return [
        {
            "split": int(s["split"]),
            "pace_str": _format_split_pace(float(s["pace_min_per_km"]), distance_unit),
            "speed_str": _format_split_speed(float(s["pace_min_per_km"]), distance_unit),
            "elev_str": _format_elevation_change(float(s["elevation_change_m"]), distance_unit),
        }
        for s in splits
    ]


def _compute_splits_lazy(row: dict[str, Any]) -> list[dict[str, Any]]:
    """Compute GPS splits from the route stored in *row* and cache the result.

    Called the first time the Splits tab is opened for a given workout row.
    The result is written back into ``row["splits"]`` so subsequent navigations
    to the same row skip the computation entirely.

    Args:
        row: A workout row dict as returned by ``_build_workout_rows()``.
            Must contain a ``"route"`` key with a
            :class:`~logic.workout_manager.workout_route.WorkoutRoute` object
            (or ``None``) and a ``"distance_unit"`` key.

    Returns:
        A list of split dicts, or an empty list when no GPS route is available.
        Subsequent calls with the same row return the cached result immediately.
    """
    if "splits" in row:
        return cast(list[dict[str, Any]], row["splits"])
    du = row.get("distance_unit", "km")
    split_dist = 1000.0 if du == "km" else 1.0 / METERS_TO_MILES
    route_obj = row.get("route")
    if not isinstance(route_obj, WorkoutRoute) or route_obj.is_empty:
        splits: list[dict[str, Any]] = []
        row["splits"] = splits
        return splits
    # Use the workout-summary distance for GPS-drift scale correction,
    # mirroring the logic in WorkoutRoute.find_fastest_segment.
    distance_sort = row.get("distance_sort")
    distance_sort_f = float(distance_sort) if isinstance(distance_sort, (int, float)) else None
    distance_m = distance_sort_f if distance_sort_f is not None and distance_sort_f > 0 else None
    scale = WorkoutRoute.calculate_distance_scale_factor(route_obj.distance_meters, distance_m)
    splits = route_obj.compute_splits(split_distance_m=split_dist, distance_scale_factor=scale)
    row["splits"] = splits
    return splits


def _update_fields(
    field_rows: dict[str, tuple[Any, Any]],
    row: dict[str, Any],
) -> None:
    """Update field row visibility and values to match *row*.

    Rows whose value is the missing-data sentinel ``"–"`` are hidden.
    """
    for field_key, (frow, value_el) in field_rows.items():
        value = str(row.get(field_key, "–"))
        has_value = bool(value) and value != "–"
        frow.set_visibility(has_value)
        if has_value:
            value_el.set_text(value)


def _build_field_rows(
    field_display: list[tuple[str, _LabelFn]],
) -> dict[str, tuple[Any, Any]]:
    """Build label/value field row widgets from a display spec.

    Creates a ``ui.row`` for each entry in *field_display* and returns a dict
    mapping each field key to its ``(row_element, value_label)`` pair so that
    :func:`_update_fields` can update values without rebuilding the UI tree.

    Args:
        field_display: Ordered list of ``(field_key, label_fn)`` pairs.

    Returns:
        Dict mapping each ``field_key`` to ``(frow, value_el)`` element pairs.
    """
    field_rows: dict[str, tuple[Any, Any]] = {}
    for field_key, label_fn in field_display:
        with ui.element("div").classes(MODAL_FIELD_ROW_CLASSES) as frow:
            ui.label(label_fn()).classes(MODAL_FIELD_LABEL_CLASSES)
            value_el = ui.label().classes(MODAL_FIELD_VALUE_CLASSES)
        field_rows[field_key] = (frow, value_el)
    return field_rows


def _segment_color_from_pace(pace_min_per_km: float | None) -> str:
    """Return route-segment color from pace (green=fast, red=slow)."""
    if pace_min_per_km is None:
        return "#6b7280"
    if pace_min_per_km <= 4.0:
        return "#16a34a"
    if pace_min_per_km <= 5.0:
        return "#65a30d"
    if pace_min_per_km <= 6.0:
        return "#eab308"
    if pace_min_per_km <= 7.0:
        return "#f97316"
    return "#dc2626"


def _format_pace_min_per_km(pace_min_per_km: float | None) -> str:
    """Format pace value for tooltips, or return an unavailable marker."""
    if pace_min_per_km is None or pace_min_per_km <= 0.0:
        return "–"
    minutes = int(pace_min_per_km)
    seconds = int(round((pace_min_per_km - minutes) * 60.0))
    if seconds == 60:
        minutes += 1
        seconds = 0
    return f"{minutes}:{seconds:02d} /km"


def _route_point_map_data(point: Any) -> dict[str, float | Any] | None:
    """Extract map/profile fields from a route point; return None when invalid."""
    lat = getattr(point, "latitude", None)
    lon = getattr(point, "longitude", None)
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
        return None
    lat_f, lon_f = float(lat), float(lon)
    if not (isfinite(lat_f) and isfinite(lon_f)):
        return None
    altitude = getattr(point, "altitude", None)
    speed = getattr(point, "speed", None)
    heart_rate = getattr(point, "heart_rate", None)
    return {
        "lat": lat_f,
        "lon": lon_f,
        "altitude": float(altitude)
        if isinstance(altitude, (int, float)) and isfinite(altitude)
        else 0.0,
        "speed": float(speed) if isinstance(speed, (int, float)) and isfinite(speed) else 0.0,
        "heart_rate": (
            float(heart_rate)
            if isinstance(heart_rate, (int, float)) and isfinite(heart_rate)
            else None
        ),
        "time": getattr(point, "time", None),
    }


def _route_segment_metrics(
    previous: dict[str, Any],
    current: dict[str, Any],
) -> tuple[float, float | None, float | None]:
    """Return segment distance (m), speed (m/s), and pace (min/km)."""
    distance_m = WorkoutRoute.haversine_m(
        cast(float, previous["lat"]),
        cast(float, previous["lon"]),
        cast(float, current["lat"]),
        cast(float, current["lon"]),
    )
    speed_prev = cast(float, previous["speed"])
    speed_curr = cast(float, current["speed"])
    speed_m_s = None
    if speed_prev > 0.0 and speed_curr > 0.0:
        speed_m_s = (speed_prev + speed_curr) / 2.0
    else:
        prev_time = previous["time"]
        curr_time = current["time"]
        if prev_time is not None and curr_time is not None:
            try:
                delta_seconds = (curr_time - prev_time).total_seconds()
            except (AttributeError, TypeError):
                delta_seconds = 0.0
            if delta_seconds > 0.0 and distance_m > 0.0:
                speed_m_s = distance_m / delta_seconds
    if speed_m_s is None or speed_m_s <= 0.0:
        return distance_m, None, None
    pace_min_per_km = (_METERS_PER_KM / speed_m_s) / _SECONDS_PER_MINUTE
    return distance_m, speed_m_s, pace_min_per_km


def _update_rolling_pace_window(
    rolling_pace_segments: list[tuple[float, float]],
    rolling_distance_m: float,
    rolling_time_s: float,
    segment_distance_m: float,
    speed_m_s: float,
) -> tuple[float, float, float | None]:
    """Update the rolling moving-pace window and return the smoothed pace value.

    Args:
        rolling_pace_segments: Rolling window of ``(distance_m, time_s)`` segment tuples.
        rolling_distance_m: Total distance represented by the rolling window.
        rolling_time_s: Total elapsed time represented by the rolling window.
        segment_distance_m: Distance of the latest segment in meters.
        speed_m_s: Speed estimate for the latest segment in meters per second.

    Returns:
        Tuple of ``(rolling_distance_m, rolling_time_s, pace_min_per_km)`` where
        ``pace_min_per_km`` is ``None`` when the rolling window has no valid data.
    """
    if speed_m_s >= _MIN_MOVING_SPEED_M_S and segment_distance_m > 0.0:
        segment_time_s = segment_distance_m / speed_m_s
        rolling_pace_segments.append((segment_distance_m, segment_time_s))
        rolling_distance_m += segment_distance_m
        rolling_time_s += segment_time_s
        # Keep at least one segment so pace can remain stable through short pauses.
        while (
            rolling_distance_m > _PACE_SMOOTHING_WINDOW_M
            and len(rolling_pace_segments) > _MIN_ROLLING_SEGMENTS
        ):
            old_distance_m, old_time_s = rolling_pace_segments.pop(0)
            rolling_distance_m -= old_distance_m
            rolling_time_s -= old_time_s
    pace = None
    if rolling_distance_m > 0.0 and rolling_time_s > 0.0:
        pace = (rolling_time_s / _SECONDS_PER_MINUTE) / (rolling_distance_m / _METERS_PER_KM)
    return rolling_distance_m, rolling_time_s, pace


def _route_altitudes(route: WorkoutRoute) -> list[float]:
    """Return finite altitude samples for one route as floats."""
    return [
        float(a) if isinstance(a, (int, float)) and isfinite(a) else 0.0
        for a in route.to_dataframe()["altitude"].tolist()
    ]


def _build_valid_route_points(route: WorkoutRoute) -> list[dict[str, Any]]:
    """Return route points enriched with altitude and filtered for valid coordinates."""
    altitudes = _route_altitudes(route)
    if not altitudes:
        return []
    valid_points: list[dict[str, Any]] = []
    for point, altitude in zip(route.points, altitudes):
        point_data = _route_point_map_data(point)
        if point_data is None:
            continue
        point_data["altitude"] = altitude
        valid_points.append(point_data)
    return valid_points


def _add_segment_distance(
    cumulative_distance_m: float,
    previous: dict[str, Any] | None,
    current: dict[str, Any],
) -> float:
    """Accumulate traveled distance from the previous point to current point."""
    if previous is None:
        return cumulative_distance_m
    return cumulative_distance_m + WorkoutRoute.haversine_m(
        cast(float, previous["lat"]),
        cast(float, previous["lon"]),
        cast(float, current["lat"]),
        cast(float, current["lon"]),
    )


def _profile_speed_and_pace(
    previous: dict[str, Any] | None,
    current: dict[str, Any],
    rolling_pace_segments: list[tuple[float, float]],
    rolling_distance_m: float,
    rolling_time_s: float,
) -> tuple[float | None, float | None, float, float]:
    """Compute speed/pace series values for one profile point."""
    if previous is None:
        return None, None, rolling_distance_m, rolling_time_s
    segment_distance_m, speed_m_s, _ = _route_segment_metrics(previous, current)
    if speed_m_s is None:
        return None, None, rolling_distance_m, rolling_time_s
    speed_kmh = speed_m_s * _M_S_TO_KM_H
    rolling_distance_m, rolling_time_s, pace = _update_rolling_pace_window(
        rolling_pace_segments,
        rolling_distance_m,
        rolling_time_s,
        segment_distance_m,
        speed_m_s,
    )
    return speed_kmh, pace, rolling_distance_m, rolling_time_s


def _append_route_profile_points(
    profile_points: list[list[float | None]],
    valid_points: list[dict[str, Any]],
    cumulative_distance_m: float,
) -> float:
    """Append chart points for one valid route and return updated cumulative distance."""
    rolling_pace_segments: list[tuple[float, float]] = []
    rolling_distance_m = 0.0
    rolling_time_s = 0.0
    for idx, current in enumerate(valid_points):
        previous = valid_points[idx - 1] if idx > 0 else None
        cumulative_distance_m = _add_segment_distance(cumulative_distance_m, previous, current)
        speed_kmh, pace, rolling_distance_m, rolling_time_s = _profile_speed_and_pace(
            previous,
            current,
            rolling_pace_segments,
            rolling_distance_m,
            rolling_time_s,
        )
        distance_km = cumulative_distance_m / _METERS_PER_KM
        altitude_m = cast(float, current["altitude"])
        hr_bpm = cast(float | None, current["heart_rate"])
        profile_points.append([distance_km, altitude_m, pace, speed_kmh, hr_bpm])
    return cumulative_distance_m


def _build_route_profile_chart_config(routes: list[WorkoutRoute]) -> dict[str, Any]:
    """Build a route profile chart with altitude plus pace/speed/HR hover metrics."""
    profile_points: list[list[float | None]] = []
    cumulative_distance_m = 0.0
    for route in routes:
        if not route.points:
            continue
        valid_points = _build_valid_route_points(route)
        if len(valid_points) < 2:
            continue
        cumulative_distance_m = _append_route_profile_points(
            profile_points, valid_points, cumulative_distance_m
        )

    pace_label = json.dumps(f"{t('Pace')}: ")
    speed_label = json.dumps(f"{t('Speed')}: ")
    altitude_label = json.dumps(f"{t('Altitude')}: ")
    distance_label = json.dumps(f"{t('Distance')}: ")
    heart_rate_label = json.dumps(f"{t('Heart Rate')}: ")
    no_data = json.dumps("–")
    # point payload indices for JS formatter:
    # [0]=distance_km, [1]=altitude_m, [2]=pace_min_per_km, [3]=speed_km_h, [4]=heart_rate_bpm
    # Keep this pace formatter aligned with _format_pace_min_per_km used on map tooltips.
    altitude_axis_name = f"{t('Altitude')} (m)"
    pace_axis_name = f"{t('Pace')} (/km)"
    # Keep legend and axis titles separated from tick labels on compact screens.
    chart_grid = {"left": 72, "right": 80, "top": 56, "bottom": 64}
    return {
        "backgroundColor": "transparent",
        "legend": {"data": [altitude_axis_name, pace_axis_name], "top": 8},
        "grid": chart_grid,
        "tooltip": {
            "trigger": "axis",
            "renderMode": "richText",
            ":formatter": (
                "function(params) {"
                "var point = params[0].data;"
                f"var text = {distance_label} + point[0].toFixed(2) + ' km\\n' + "
                f"{altitude_label} + point[1].toFixed(1) + ' m';"
                f"text += '\\n' + {pace_label} + (point[2] == null ? {no_data} : "
                "("
                "Math.floor(point[2]) + ':' + "
                "String(Math.round((point[2] - Math.floor(point[2])) * 60)).padStart(2, '0') + "
                "' /km'));"
                f"text += '\\n' + {speed_label} + ("
                f"point[3] == null ? {no_data} : point[3].toFixed(1) + ' km/h');"
                "if (point[4] != null) {"
                f"  text += '\\n' + {heart_rate_label} + point[4].toFixed(0) + ' bpm';"
                "}"
                "return text;"
                "}"
            ),
        },
        "xAxis": {
            "type": "value",
            "name": f"{t('Distance')} (km)",
            "nameLocation": "middle",
            "nameGap": 42,
        },
        "yAxis": [
            {
                "type": "value",
                "name": altitude_axis_name,
                "scale": True,
                "nameLocation": "middle",
                "nameGap": 52,
            },
            {
                "type": "value",
                "name": pace_axis_name,
                "scale": True,
                "inverse": True,
                "nameLocation": "middle",
                "nameGap": 56,
            },
        ],
        "series": [
            {
                "name": altitude_axis_name,
                "type": "line",
                "data": profile_points,
                "encode": {"x": 0, "y": 1},
                "showSymbol": False,
                "smooth": False,
                "lineStyle": {"width": 2},
            },
            {
                "name": pace_axis_name,
                "type": "line",
                "data": profile_points,
                "encode": {"x": 0, "y": 2},
                "yAxisIndex": 1,
                "showSymbol": False,
                "smooth": False,
                "connectNulls": True,
                "lineStyle": {"width": 2},
            },
        ],
    }


def _do_refresh_route_tab(
    no_route_label: Any,
    route_map: Any,
    row: dict[str, Any],
) -> None:
    """Update the Route tab map with pace-colored segments."""
    routes = _get_row_routes(row)
    has_route = bool(routes)
    no_route_label.set_visibility(not has_route)
    route_map.set_visibility(has_route)
    if not has_route:
        return

    route_map.clear_layers()
    route_map.tile_layer(
        url_template=r"https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        options={
            "maxZoom": 19,
            "attribution": "&copy; OpenStreetMap contributors",
        },
    )

    all_points: list[list[float]] = []
    start_label = t("Start")
    end_label = t("End")

    for idx, route in enumerate(routes, start=1):
        route_name = t("Route {index}", index=str(idx))
        points_data = [_route_point_map_data(point) for point in route.points]
        valid_points = [point for point in points_data if point is not None]
        if len(valid_points) < 2:
            continue

        for previous, current in zip(valid_points, valid_points[1:]):
            distance_m, speed_m_s, pace = _route_segment_metrics(previous, current)
            color = _segment_color_from_pace(pace)
            segment_points = [
                [cast(float, previous["lat"]), cast(float, previous["lon"])],
                [cast(float, current["lat"]), cast(float, current["lon"])],
            ]
            polyline = route_map.generic_layer(
                name="polyline",
                args=[segment_points, {"color": color, "weight": 4, "opacity": 0.9}],
            )
            speed_text = "–" if speed_m_s is None else f"{speed_m_s * _M_S_TO_KM_H:.1f} km/h"
            tooltip_lines = [
                route_name,
                f"{t('Pace')}: {_format_pace_min_per_km(pace)}",
                f"{t('Speed')}: {speed_text}",
                f"{t('Altitude')}: {cast(float, current['altitude']):.1f} m",
                f"{t('Distance')}: {distance_m:.0f} m",
            ]
            heart_rate = cast(float | None, current["heart_rate"])
            if heart_rate is not None:
                tooltip_lines.append(f"{t('Heart Rate')}: {heart_rate:.0f} bpm")
            route_map.run_layer_method(polyline.id, "bindTooltip", "<br>".join(tooltip_lines))

        start_marker = route_map.generic_layer(
            name="circleMarker",
            args=[
                [cast(float, valid_points[0]["lat"]), cast(float, valid_points[0]["lon"])],
                {"radius": 6, "color": "#16a34a", "fillOpacity": 1},
            ],
        )
        route_map.run_layer_method(start_marker.id, "bindTooltip", f"{start_label} - {route_name}")
        end_marker = route_map.generic_layer(
            name="circleMarker",
            args=[
                [cast(float, valid_points[-1]["lat"]), cast(float, valid_points[-1]["lon"])],
                {"radius": 6, "color": "#dc2626", "fillOpacity": 1},
            ],
        )
        route_map.run_layer_method(end_marker.id, "bindTooltip", f"{end_label} - {route_name}")
        all_points.extend(
            [[cast(float, point["lat"]), cast(float, point["lon"])] for point in valid_points]
        )

    if all_points:
        background_tasks.create(_fit_route_bounds_after_init(route_map, list(all_points)))
    else:
        route_map.set_center((0.0, 0.0))
        route_map.set_zoom(1)


def _do_refresh_route_profile_tab(
    no_route_label: Any,
    route_profile_chart: Any,
    row: dict[str, Any],
) -> None:
    """Update the Profile tab chart with altitude and pace series."""
    routes = _get_row_routes(row)
    has_route = bool(routes)
    no_route_label.set_visibility(not has_route)
    route_profile_chart.set_visibility(has_route)
    if not has_route:
        return

    route_profile_options = _build_route_profile_chart_config(routes)
    chart_options = getattr(route_profile_chart, "options", None)
    if isinstance(chart_options, dict):
        chart_options.clear()
        chart_options.update(route_profile_options)
    route_profile_chart.update()


async def _fit_route_bounds_after_init(route_map: Any, all_points: list[list[float]]) -> None:
    """Fit map bounds after Leaflet map initialization and tab layout completion."""
    try:
        await route_map.initialized()
        # Yield control to the event loop so the Route tab panel can complete its
        # visible layout pass before we invalidate size and fit bounds.
        await asyncio.sleep(0)
        route_map.run_map_method("invalidateSize", False)
        route_map.run_map_method("fitBounds", all_points, {"padding": [20, 20]})
    except (TimeoutError, asyncio.CancelledError):
        # The user may switch away while the map is still initializing.
        return


#: Maps each supported raw activity type to the Activity-tab field keys used by
#: :func:`_row_has_activity_data`.  Derived from
#: :data:`~logic.workout_detail_schema.PER_TYPE_FIELDS` using the ``display_row_key``
#: attribute on each :class:`~logic.workout_detail_schema.FieldDefinition`.
#: Fields whose ``display_row_key`` is ``None`` (e.g. those shown in the Overview tab,
#: such as ``averageRunningPower`` → ``avg_power``) are excluded automatically.
_ACTIVITY_FIELD_KEYS: dict[str, list[str]] = {
    activity: [f.display_row_key for f in fields if f.display_row_key is not None]
    for activity, fields in PER_TYPE_FIELDS.items()
}


def _row_has_activity_data(row: dict[str, Any]) -> bool:
    """Return True when the row has at least one non-missing activity-specific field.

    The Activity tab should only be enabled when there is something meaningful
    to display.  A row's activity-type fields all default to ``"–"`` when the
    corresponding statistics are absent from the export (e.g. a Walking workout
    recorded without cadence or step data).

    For Swimming, the tab is enabled when at least one summary field
    (location, lap length, or stroke count) is present.

    Args:
        row: A workout row dict as returned by ``_build_workout_rows()``.

    Returns:
        True when at least one field from the activity-type's display spec
        contains a value other than the missing sentinel ``"–"``.
    """
    raw_type = row.get("raw_activity_type")
    keys = _ACTIVITY_FIELD_KEYS.get(raw_type, [])  # type: ignore[arg-type]
    return any(str(row.get(k, "–")) not in ("–", "") for k in keys)


def _row_has_swim_laps(row: dict[str, Any]) -> bool:
    """Return True when the row contains at least one Lap swimming event.

    Used to decide whether to enable the Intervals tab in the workout detail
    modal.  A list that contains only Segment events does not produce any
    interval rows (``build_swim_intervals`` requires at least one Lap event),
    so the Intervals tab must remain disabled in that case.

    Args:
        row: A workout row dict as returned by ``_build_workout_rows()``.

    Returns:
        True when ``swimming_events`` contains at least one event whose
        ``type`` is ``"Lap"``.
    """
    events = row.get("swimming_events")
    if not isinstance(events, list):
        return False
    return any(e.get("type") == "Lap" for e in events)


def _do_refresh_activity_tab(
    no_activity_label: Any,
    activity_tab: Any,
    containers: dict[str, tuple[Any, Any]],
    row: dict[str, Any],
) -> None:
    """Update the Activity tab elements for the given workout row.

    Shows the appropriate type-specific container and updates its fields.
    All other containers are hidden.  The tab itself is disabled when no
    activity-specific data is available.

    Args:
        no_activity_label: Label shown when the activity type is unsupported.
        activity_tab:       The ``ui.tab`` element for the Activity tab.
        containers:         Dict mapping raw activity type name → (container, field_rows).
        row:                Workout row dict as returned by ``_build_workout_rows()``.
    """
    raw_type = row.get("raw_activity_type")
    has_data = _row_has_activity_data(row)
    no_activity_label.set_visibility(not has_data)
    activity_tab.set_enabled(has_data)
    for activity, (container, _) in containers.items():
        container.set_visibility(raw_type == activity)
    if raw_type in containers:
        _update_fields(containers[raw_type][1], row)


def _do_refresh_intervals_tab(
    no_swim_laps_label: Any,
    swim_table: Any,
    no_splits_label: Any,
    splits_table: Any,
    splits_columns: list[dict[str, Any]],
    row: dict[str, Any],
) -> None:
    """Update the Intervals tab elements for the given workout row.

    For Swimming workouts, populates the swim-interval table from
    ``row["swimming_events"]``.  For all other workout types, computes
    GPS splits lazily via :func:`_compute_splits_lazy` and populates the
    splits table.  Sections are shown or hidden based on activity type and
    data availability.

    Args:
        no_swim_laps_label: Label shown when swimming has no lap data.
        swim_table:         The ``ui.table`` for swim intervals.
        no_splits_label:    Label shown when no GPS route is available.
        splits_table:       The ``ui.table`` for GPS splits.
        splits_columns:     Column definition list for the splits table (mutated
                            to update the distance-unit header).
        row:                Workout row dict as returned by ``_build_workout_rows()``.
    """
    is_swimming = row.get("raw_activity_type") == "Swimming"

    # --- Swimming section ---
    events = row.get("swimming_events") or []
    lap_length = float(row.get("lap_length_m") or 0.0)
    intervals = build_swim_intervals(events, lap_length)
    swim_rows = _build_swim_display_rows(intervals)
    has_swim = bool(swim_rows) and is_swimming
    no_swim_laps_label.set_visibility(is_swimming and not has_swim)
    swim_table.set_visibility(has_swim)
    if has_swim:
        swim_table.rows = swim_rows
        swim_table.update()

    # --- GPS splits section ---
    splits = _compute_splits_lazy(row)
    has_splits = bool(splits) and not is_swimming
    no_splits_label.set_visibility(not is_swimming and not has_splits)
    splits_table.set_visibility(has_splits)
    if has_splits:
        du = row.get("distance_unit", "km")
        # Update column header to reflect the active distance unit (km / mi).
        splits_columns[0]["label"] = du
        splits_table.rows = _format_split_rows(splits, du)
        splits_table.update()


def create_workout_detail_modal(
    rows: list[dict[str, Any]],
) -> Callable[[int], None]:
    """Create a workout detail modal dialog and return a callable to open it.

    The dialog is created once in the current NiceGUI context.  Calling the
    returned ``open_at(index)`` function updates the displayed content and
    opens the dialog at the given row index.

    Navigation within the open modal is supported via left/right arrow buttons.
    The dialog closes on Esc (Quasar default) or when the close button is clicked.

    The modal is organised into tabs:

    * **Overview** – generic workout attributes (date, distance, calories, heart rate,
      VO₂ max, elevation, etc.) shared by all workout types.
    * **Activity** – type-specific metrics.  Running workouts show pace, cadence,
      stride length, vertical oscillation, ground contact time, and step count.
      Walking workouts show pace, cadence, step length, and step count.
      Hiking workouts show pace, cadence, step length, and step count.
      Swimming workouts show location, lap length, and total stroke count.
      Cycling workouts show speed, cadence, power, and functional threshold power.
      Other activity types show a placeholder message; the tab is disabled.
    * **Route** – interactive map for workouts with GPS points. Route geometry is
      rendered from ``route_parts`` (when available) or the merged ``route`` field,
      with start/end markers and pace-colored segments.
    * **Profile** – elevation and pace chart for the workout route. Includes
      distance-based tooltip metrics (pace, speed, altitude, optional heart rate).
    * **Intervals** – per-workout interval data.  For Swimming workouts each row
      represents one active set with distance, time, stroke style, average SWOLF,
      and rest duration.  For workouts with a GPS route the table shows per-km (or
      per-mi) splits with pace and elevation change.  The tab is disabled when
      neither lap events nor a GPS route are available.
    * **Comparisons** – route-comparison leaderboard for workouts with GPS data.
      Shows up to the top 10 performances on the same course, with the current
      workout highlighted.  The tab is disabled when no GPS route is available.

    Args:
        rows: List of workout row dicts as returned by ``_build_workout_rows()``.

    Returns:
        A callable ``open_at(index)`` that shows the modal for ``rows[index]``.
        Returns a no-op callable when *rows* is empty.
    """
    if not rows:
        return lambda _: None

    modal_state: dict[str, int] = {"index": 0}

    with ui.dialog() as dialog:
        with ui.card().classes(MODAL_CARD_CLASSES):
            # ---- Header (title + close button) ----
            with ui.row().classes(MODAL_HEADER_ROW_CLASSES):
                modal_title = ui.label().classes(LABEL_UPPERCASE_CLASSES)
                ui.button(icon="close", on_click=dialog.close).props(BUTTON_DENSE_PROPS)

            # ---- Tab bar ----
            with ui.tabs().classes(TABS_FULL_CLASSES) as detail_tabs:
                ui.tab("overview", t("Overview"))
                activity_tab = ui.tab("activity", t("Activity"))
                route_tab = ui.tab("route", t("Route"))
                profile_tab = ui.tab("profile", t("Profile"))
                intervals_tab = ui.tab("intervals", t("Intervals"))
                comparisons_tab = ui.tab("comparisons", t("Comparisons"))

            # ---- Tab panels ----
            with ui.tab_panels(detail_tabs, value="overview").classes(MODAL_TAB_PANELS_CLASSES):
                # Overview tab: generic workout attributes
                with ui.tab_panel("overview"):
                    with ui.row().classes(MODAL_CENTERED_ROW_CLASSES):
                        with ui.column().classes(MODAL_CENTERED_CONTENT_CLASSES):
                            field_rows = _build_field_rows(_FIELD_DISPLAY)

                # Activity tab: type-specific metrics
                with ui.tab_panel("activity"):
                    with ui.row().classes(MODAL_CENTERED_ROW_CLASSES):
                        with ui.column().classes(MODAL_CENTERED_CONTENT_CLASSES):
                            # Shown for unsupported activity types
                            no_activity_label = ui.label(
                                t("No activity-specific data available.")
                            ).classes(LABEL_MUTED_CLASSES)
                            # Running-specific metrics; shown only when activity is Running
                            running_container = ui.column().classes(TABS_FULL_CLASSES)
                            with running_container:
                                running_field_rows = _build_field_rows(_RUNNING_FIELD_DISPLAY)
                            # Walking-specific metrics; shown only when activity is Walking
                            walking_container = ui.column().classes(TABS_FULL_CLASSES)
                            with walking_container:
                                walking_field_rows = _build_field_rows(_WALKING_FIELD_DISPLAY)
                            # Hiking-specific metrics; shown only when activity is Hiking
                            hiking_container = ui.column().classes(TABS_FULL_CLASSES)
                            with hiking_container:
                                hiking_field_rows = _build_field_rows(_HIKING_FIELD_DISPLAY)
                            # Swimming summary metrics; shown only when activity is Swimming
                            swimming_container = ui.column().classes(TABS_FULL_CLASSES)
                            with swimming_container:
                                swimming_field_rows = _build_field_rows(_SWIMMING_FIELD_DISPLAY)
                            # Cycling-specific metrics; shown only when activity is Cycling
                            cycling_container = ui.column().classes(TABS_FULL_CLASSES)
                            with cycling_container:
                                cycling_field_rows = _build_field_rows(_CYCLING_FIELD_DISPLAY)

                # Intervals tab: swim lap table (Swimming) or GPS splits (other workouts with GPS)
                with ui.tab_panel("intervals"):
                    # Swimming section: per-interval lap table
                    no_swim_laps_label = ui.label(t("No lap data available.")).classes(
                        LABEL_MUTED_CLASSES
                    )
                    swim_columns = [
                        {
                            "name": "num",
                            "label": "#",
                            "field": "num",
                            "align": "right",
                            "sortable": False,
                        },
                        {
                            "name": "dist",
                            "label": t("Dist"),
                            "field": "dist",
                            "align": "right",
                            "sortable": False,
                        },
                        {
                            "name": "dur",
                            "label": t("Time"),
                            "field": "dur",
                            "align": "right",
                            "sortable": False,
                        },
                        {
                            "name": "stroke",
                            "label": t("Stroke"),
                            "field": "stroke",
                            "align": "left",
                            "sortable": False,
                        },
                        {
                            "name": "swolf",
                            "label": "SWOLF",
                            "field": "swolf",
                            "align": "right",
                            "sortable": False,
                        },
                        {
                            "name": "pause",
                            "label": t("Rest"),
                            "field": "pause",
                            "align": "right",
                            "sortable": False,
                        },
                    ]
                    swim_table = (
                        ui.table(columns=swim_columns, rows=[], row_key="num")
                        .classes(MODAL_SWIM_TABLE_CLASSES)
                        .props(TABLE_DENSE_FLAT_PROPS)
                    )

                    # GPS splits section: per-km or per-mi splits for workouts with a route
                    no_splits_label = ui.label(t(_NO_GPS_ROUTE_MSG)).classes(LABEL_MUTED_CLASSES)
                    # Initialise the split-number column header from the first row's unit so
                    # the correct label ("km" or "mi") is visible before the first tab-click.
                    _initial_du = rows[0].get("distance_unit", "km") if rows else "km"
                    splits_columns = [
                        {
                            "name": "split",
                            "label": _initial_du,
                            "field": "split",
                            "align": "right",
                            "sortable": False,
                        },
                        {
                            "name": "pace",
                            "label": t("Pace"),
                            "field": "pace_str",
                            "align": "right",
                            "sortable": False,
                        },
                        {
                            "name": "speed",
                            "label": t("Speed"),
                            "field": "speed_str",
                            "align": "right",
                            "sortable": False,
                        },
                        {
                            "name": "elevation",
                            "label": t("Elev"),
                            "field": "elev_str",
                            "align": "right",
                            "sortable": False,
                        },
                    ]
                    splits_table = (
                        ui.table(columns=splits_columns, rows=[], row_key="split")
                        .classes(MODAL_SPLITS_TABLE_CLASSES)
                        .props(TABLE_DENSE_FLAT_PROPS)
                    )

                # Route tab: interactive Leaflet route map with start/end markers
                with ui.tab_panel("route"):
                    no_route_label = ui.label(t(_NO_GPS_ROUTE_MSG)).classes(LABEL_MUTED_CLASSES)
                    with ui.row().classes(MODAL_ROUTE_MAP_CONTAINER_CLASSES):
                        route_map = ui.leaflet(
                            center=(0.0, 0.0),
                            zoom=13,
                            options={"zoomControl": True},
                        ).classes(MODAL_ROUTE_MAP_HTML_CLASSES)

                # Profile tab: altitude + pace chart for route readability
                with ui.tab_panel("profile"):
                    no_route_profile_label = ui.label(t(_NO_GPS_ROUTE_MSG)).classes(
                        LABEL_MUTED_CLASSES
                    )
                    with ui.row().classes(MODAL_ROUTE_PROFILE_CONTAINER_CLASSES):
                        route_profile_chart = ui.echart(
                            {
                                "backgroundColor": "transparent",
                                "xAxis": {"type": "value"},
                                "yAxis": {"type": "value"},
                                "series": [{"type": "line", "data": []}],
                            }
                        ).classes(MODAL_ROUTE_PROFILE_CLASSES)

                # Comparisons tab: route-comparison leaderboard for GPS workouts
                with ui.tab_panel("comparisons"):
                    no_route_label_comp = ui.label(t(_NO_GPS_ROUTE_MSG)).classes(
                        LABEL_MUTED_CLASSES
                    )
                    no_similar_label = ui.label(t("No similar routes found.")).classes(
                        LABEL_MUTED_CLASSES
                    )
                    comparison_rank_label = ui.label().classes(MODAL_COMPARISON_RANK_CLASSES)
                    comparison_columns = [
                        {
                            "name": "rank",
                            "label": "#",
                            "field": "rank_str",
                            "align": "right",
                            "sortable": False,
                        },
                        {
                            "name": "date",
                            "label": t("Date"),
                            "field": "date",
                            "align": "left",
                            "sortable": False,
                        },
                        {
                            "name": "duration",
                            "label": t("Duration"),
                            "field": "duration",
                            "align": "right",
                            "sortable": False,
                        },
                        {
                            "name": "diff",
                            "label": t("Diff"),
                            "field": "diff_str",
                            "align": "right",
                            "sortable": False,
                        },
                        {
                            "name": "pace",
                            "label": t("Pace"),
                            "field": "pace",
                            "align": "right",
                            "sortable": False,
                        },
                    ]
                    comparison_table = (
                        ui.table(columns=comparison_columns, rows=[], row_key="rank")
                        .classes(MODAL_COMPARISON_TABLE_CLASSES)
                        .props(TABLE_DENSE_FLAT_PROPS)
                    )

            # ---- Navigation footer ----
            with ui.row().classes(MODAL_NAV_ROW_CLASSES):
                prev_btn = ui.button(
                    icon="chevron_left",
                    on_click=lambda: _navigate(-1),
                ).props(BUTTON_DENSE_PROPS)
                nav_counter = ui.label().classes(MODAL_NAV_COUNTER_CLASSES)
                next_btn = ui.button(
                    icon="chevron_right",
                    on_click=lambda: _navigate(1),
                ).props(BUTTON_DENSE_PROPS)

    def _refresh_header(idx: int, n: int, row: dict[str, Any]) -> None:
        """Update modal title and navigation state."""
        modal_title.set_text(f"{row['activity_type']} – {row['date']}")
        nav_counter.set_text(f"{idx + 1} / {n}")
        prev_btn.set_enabled(idx != 0)
        next_btn.set_enabled(idx != n - 1)

    # Build the containers map once; reused by _refresh_activity_tab on every refresh.
    _containers: dict[str, tuple[Any, Any]] = {
        "Running": (running_container, running_field_rows),
        "Walking": (walking_container, walking_field_rows),
        "Hiking": (hiking_container, hiking_field_rows),
        "Swimming": (swimming_container, swimming_field_rows),
        "Cycling": (cycling_container, cycling_field_rows),
    }

    def _refresh_activity_tab(row: dict[str, Any]) -> None:
        """Delegate to module-level helper; updates Activity tab visibility and fields."""
        _do_refresh_activity_tab(no_activity_label, activity_tab, _containers, row)

    def _refresh_intervals_tab(row: dict[str, Any]) -> None:
        """Delegate to module-level helper; updates Intervals tab tables and labels."""
        _do_refresh_intervals_tab(
            no_swim_laps_label, swim_table, no_splits_label, splits_table, splits_columns, row
        )

    def _refresh_route_tab(row: dict[str, Any]) -> None:
        """Delegate to module-level helper; updates Route tab map and route visibility."""
        _do_refresh_route_tab(no_route_label, route_map, row)

    def _refresh_profile_tab(row: dict[str, Any]) -> None:
        """Delegate to module-level helper; updates Profile tab chart and visibility."""
        _do_refresh_route_profile_tab(no_route_profile_label, route_profile_chart, row)

    def _refresh_comparisons_tab(row: dict[str, Any]) -> None:
        """Delegate to module-level helper; updates Comparisons tab leaderboard."""
        _do_refresh_comparisons_tab(
            no_route_label_comp,
            no_similar_label,
            comparison_rank_label,
            comparison_table,
            row,
            rows,
        )

    # Dispatch table for lazily refreshing the active tab.  Defined once here
    # so both ``_refresh`` and ``_on_tab_change`` share the same mapping without
    # repeating the if/elif chain (which would raise the cognitive complexity).
    _lazy_tab_refresh: dict[str, Callable[[dict[str, Any]], None]] = {
        "intervals": _refresh_intervals_tab,
        "route": _refresh_route_tab,
        "profile": _refresh_profile_tab,
        "comparisons": _refresh_comparisons_tab,
    }

    def _refresh() -> None:
        """Update all modal elements to reflect the current workout."""
        idx = modal_state["index"]
        row = rows[idx]
        n = len(rows)

        _refresh_header(idx, n, row)
        _update_fields(field_rows, row)
        _refresh_activity_tab(row)
        has_route = bool(_get_row_routes(row))
        route_tab.set_enabled(has_route)
        profile_tab.set_enabled(has_route)
        intervals_tab.set_enabled(_row_has_swim_laps(row) or has_route)
        comparisons_tab.set_enabled(has_route)
        # Only refresh the Intervals tab when it is currently active; switching to
        # it triggers _on_tab_change which handles the initial load.
        refresh_fn = _lazy_tab_refresh.get(detail_tabs.value)
        if refresh_fn:
            refresh_fn(row)

    def _navigate(delta: int) -> None:
        """Move to the next or previous workout by *delta* steps."""
        new_idx = modal_state["index"] + delta
        if 0 <= new_idx < len(rows):
            modal_state["index"] = new_idx
            _refresh()

    def _on_tab_change(e: Any) -> None:
        """Refresh route-dependent tabs when the user switches to them.

        Swim intervals are loaded on first open and GPS splits are computed
        lazily (via :func:`_compute_splits_lazy`) and cached in
        ``row["splits"]`` for instant display on subsequent navigations.
        The Route tab renders a Leaflet map from the workout's GPS geometry.
        The Profile tab renders an elevation + pace chart from the route points.
        The Comparisons tab searches for similar routes and caches the result
        in ``row["similar_routes"]``.
        """
        refresh_fn = _lazy_tab_refresh.get(e.value)
        if refresh_fn:
            refresh_fn(rows[modal_state["index"]])

    detail_tabs.on_value_change(_on_tab_change)

    def open_at(index: int) -> None:
        """Open the modal at the given *index*."""
        modal_state["index"] = max(0, min(index, len(rows) - 1))
        _refresh()
        dialog.open()

    return open_at
