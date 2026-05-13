"""Route and profile helpers for workout detail modal tabs."""

from __future__ import annotations

import asyncio
import json
from collections import deque
from collections.abc import Callable
from math import isfinite
from typing import Any, TypedDict, cast

from nicegui import background_tasks

from i18n import t
from logic.workout_manager.workout_route import WorkoutRoute
from units import M_S_TO_KM_H, METERS_PER_KM, METERS_TO_FEET, METERS_TO_MILES, SECONDS_PER_MINUTE

from .comparisons import _get_row_routes

#: Speeds below this threshold are treated as non-moving for rolling pace smoothing.
_MIN_MOVING_SPEED_M_S = 0.5
#: Distance window used to smooth pace and avoid spikes caused by brief pauses.
_PACE_SMOOTHING_WINDOW_M = 200.0
#: Keep at least this many segments in the rolling window for short-stop stability.
_MIN_ROLLING_SEGMENTS = 1


class _RoutePointData(TypedDict):
    """Normalized route point payload used by map/profile helpers."""

    lat: float
    lon: float
    altitude: float
    speed: float
    heart_rate: float | None
    time: Any


def _finite_altitude(value: Any) -> float:
    """Return a finite altitude float, falling back to 0.0."""
    return float(value) if isinstance(value, (int, float)) and isfinite(value) else 0.0


def _route_point_map_data(point: Any) -> _RoutePointData | None:
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
        "altitude": _finite_altitude(altitude),
        "speed": float(speed) if isinstance(speed, (int, float)) and isfinite(speed) else 0.0,
        "heart_rate": (
            float(heart_rate)
            if isinstance(heart_rate, (int, float)) and isfinite(heart_rate)
            else None
        ),
        "time": getattr(point, "time", None),
    }


def _route_segment_metrics(
    previous: _RoutePointData,
    current: _RoutePointData,
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
    pace_min_per_km = (METERS_PER_KM / speed_m_s) / SECONDS_PER_MINUTE
    return distance_m, speed_m_s, pace_min_per_km


def _update_rolling_pace_window(
    rolling_pace_segments: deque[tuple[float, float]],
    rolling_distance_m: float,
    rolling_time_s: float,
    segment_distance_m: float,
    speed_m_s: float,
) -> tuple[float, float, float | None]:
    """Update the rolling moving-pace window and return the smoothed pace value."""
    if speed_m_s >= _MIN_MOVING_SPEED_M_S and segment_distance_m > 0.0:
        segment_time_s = segment_distance_m / speed_m_s
        rolling_pace_segments.append((segment_distance_m, segment_time_s))
        rolling_distance_m += segment_distance_m
        rolling_time_s += segment_time_s
        while (
            rolling_distance_m > _PACE_SMOOTHING_WINDOW_M
            and len(rolling_pace_segments) > _MIN_ROLLING_SEGMENTS
        ):
            old_distance_m, old_time_s = rolling_pace_segments.popleft()
            rolling_distance_m -= old_distance_m
            rolling_time_s -= old_time_s
    pace = None
    if rolling_distance_m > 0.0 and rolling_time_s > 0.0:
        pace = (rolling_time_s / SECONDS_PER_MINUTE) / (rolling_distance_m / METERS_PER_KM)
    return rolling_distance_m, rolling_time_s, pace


def _route_altitudes(route: WorkoutRoute) -> list[float]:
    """Return finite altitude samples for one route as floats."""
    return [_finite_altitude(point.altitude) for point in route.points]


def _build_valid_route_points(route: WorkoutRoute) -> list[_RoutePointData]:
    """Return route points enriched with altitude and filtered for valid coordinates."""
    altitudes = _route_altitudes(route)
    if not altitudes:
        return []
    valid_points: list[_RoutePointData] = []
    for point, altitude in zip(route.points, altitudes):
        point_data = _route_point_map_data(point)
        if point_data is None:
            continue
        point_data["altitude"] = altitude
        valid_points.append(point_data)
    return valid_points


def _add_segment_distance(
    cumulative_distance_m: float,
    previous: _RoutePointData | None,
    current: _RoutePointData,
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
    previous: _RoutePointData | None,
    current: _RoutePointData,
    rolling_pace_segments: deque[tuple[float, float]],
    rolling_distance_m: float,
    rolling_time_s: float,
) -> tuple[float | None, float | None, float, float]:
    """Compute speed/pace series values for one profile point."""
    if previous is None:
        return None, None, rolling_distance_m, rolling_time_s
    segment_distance_m, speed_m_s, _ = _route_segment_metrics(previous, current)
    if speed_m_s is None:
        return None, None, rolling_distance_m, rolling_time_s
    speed_kmh = speed_m_s * M_S_TO_KM_H
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
    valid_points: list[_RoutePointData],
    cumulative_distance_m: float,
) -> float:
    """Append chart points for one valid route and return updated cumulative distance."""
    rolling_pace_segments: deque[tuple[float, float]] = deque()
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
        distance_km = cumulative_distance_m / METERS_PER_KM
        altitude_m = cast(float, current["altitude"])
        hr_bpm = cast(float | None, current["heart_rate"])
        profile_points.append([distance_km, altitude_m, pace, speed_kmh, hr_bpm])
    return cumulative_distance_m


def _build_route_profile_chart_config(routes: list[WorkoutRoute]) -> dict[str, Any]:
    """Build a route profile chart with altitude plus pace/speed/HR hover metrics."""
    return _build_route_profile_chart_config_with_translate(
        routes, translate=t, distance_unit="km"
    )


def _build_route_profile_chart_config_with_translate(
    routes: list[WorkoutRoute],
    *,
    translate: Callable[..., str],
    distance_unit: str = "km",
) -> dict[str, Any]:
    """Build profile chart config using an injectable translation function."""
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

    normalized_distance_unit = "mi" if distance_unit == "mi" else "km"
    if normalized_distance_unit == "mi":
        km_to_miles = METERS_TO_MILES * METERS_PER_KM
        profile_points = [
            [
                cast(float, point[0]) * km_to_miles,
                cast(float, point[1]) * METERS_TO_FEET,
                None if point[2] is None else cast(float, point[2]) / km_to_miles,
                None if point[3] is None else cast(float, point[3]) * km_to_miles,
                point[4],
            ]
            for point in profile_points
        ]
        altitude_unit = "ft"
        speed_unit = "mph"
    else:
        altitude_unit = "m"
        speed_unit = "km/h"

    pace_label = json.dumps(f"{translate('Pace')}: ")
    speed_label = json.dumps(f"{translate('Speed')}: ")
    altitude_label = json.dumps(f"{translate('Altitude')}: ")
    distance_label = json.dumps(f"{translate('Distance')}: ")
    heart_rate_label = json.dumps(f"{translate('Heart Rate')}: ")
    no_data = json.dumps("–")
    distance_unit_label = json.dumps(normalized_distance_unit)
    altitude_unit_label = json.dumps(altitude_unit)
    speed_unit_label = json.dumps(speed_unit)
    altitude_axis_name = f"{translate('Altitude')} ({altitude_unit})"
    pace_axis_name = f"{translate('Pace')} (/{normalized_distance_unit})"
    distance_axis_name = f"{translate('Distance')} ({normalized_distance_unit})"
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
                f"var text = {distance_label} + point[0].toFixed(2) + ' ' + "
                f"{distance_unit_label} + '\\n' + "
                f"{altitude_label} + point[1].toFixed(1) + ' ' + {altitude_unit_label};"
                f"text += '\\n' + {pace_label} + (point[2] == null ? {no_data} : "
                "("
                "Math.floor(Math.round(point[2] * 60) / 60) + ':' + "
                "String(Math.round(point[2] * 60) % 60).padStart(2, '0') + "
                f"' /{normalized_distance_unit}'));"
                f"text += '\\n' + {speed_label} + ("
                f"point[3] == null ? {no_data} : point[3].toFixed(1) + ' ' + {speed_unit_label});"
                "if (point[4] != null) {"
                f"  text += '\\n' + {heart_rate_label} + point[4].toFixed(0) + ' bpm';"
                "}"
                "return text;"
                "}"
            ),
        },
        "xAxis": {
            "type": "value",
            "name": distance_axis_name,
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
    *,
    fit_bounds_scheduler: Callable[[Any], Any] | None = None,
    translate: Callable[..., str] = t,
) -> None:
    """Update the Route tab map with plain route polylines."""
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
    start_label = translate("Start")
    end_label = translate("End")

    for idx, route in enumerate(routes, start=1):
        route_name = translate("Route {index}", index=str(idx))
        points_data = [_route_point_map_data(point) for point in route.points]
        valid_points = [point for point in points_data if point is not None]
        if len(valid_points) < 2:
            continue

        route_points = [
            [cast(float, point["lat"]), cast(float, point["lon"])] for point in valid_points
        ]
        polyline = route_map.generic_layer(
            name="polyline",
            args=[route_points, {"color": "#2563eb", "weight": 4, "opacity": 0.9}],
        )
        route_map.run_layer_method(polyline.id, "bindTooltip", route_name)

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
        all_points.extend(route_points)

    if all_points:
        schedule = fit_bounds_scheduler or background_tasks.create
        schedule(_fit_route_bounds_after_init(route_map, list(all_points)))
    else:
        route_map.set_center((0.0, 0.0))
        route_map.set_zoom(1)


def _do_refresh_route_profile_tab(
    no_route_label: Any,
    route_profile_chart: Any,
    row: dict[str, Any],
    *,
    translate: Callable[..., str] = t,
) -> None:
    """Update the Profile tab chart with altitude and pace series."""
    routes = _get_row_routes(row)
    has_route = bool(routes)
    no_route_label.set_visibility(not has_route)
    route_profile_chart.set_visibility(has_route)
    if not has_route:
        return

    distance_unit = str(row.get("distance_unit", "km"))
    route_profile_options = _build_route_profile_chart_config_with_translate(
        routes,
        translate=translate,
        distance_unit="mi" if distance_unit == "mi" else "km",
    )
    chart_options = getattr(route_profile_chart, "options", None)
    if isinstance(chart_options, dict):
        chart_options.clear()
        chart_options.update(route_profile_options)
    route_profile_chart.update()


async def _fit_route_bounds_after_init(route_map: Any, all_points: list[list[float]]) -> None:
    """Fit map bounds after Leaflet map initialization and tab layout completion."""
    try:
        await route_map.initialized()
        await asyncio.sleep(0)
        route_map.run_map_method("invalidateSize", False)
        route_map.run_map_method("fitBounds", all_points, {"padding": [20, 20]})
    except (TimeoutError, asyncio.CancelledError):
        return
