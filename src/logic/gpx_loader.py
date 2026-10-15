"""GPX route loading and windowing utilities for Apple Health export data."""

import logging
from bisect import bisect_left, bisect_right
from datetime import datetime
from typing import Any
from zipfile import ZipFile

from lxml.etree import (  # type: ignore[attr-defined]  # pylint: disable=no-name-in-module
    iterparse,
)

from logic.models import WorkoutRecord
from logic.workout_manager.workout_route import RoutePoint, WorkoutRoute

_logger = logging.getLogger(__name__)

_GPX_NAMESPACE = "http://www.topografix.com/GPX/1/1"  # noqa: S5332
_SAFE_ITERPARSE_OPTIONS: dict[str, Any] = {"resolve_entities": False, "no_network": True}


def _purge_element(elem: Any) -> None:
    """Release a processed element and its already-seen siblings to keep memory low."""
    elem.clear()
    parent = elem.getparent()
    if parent is None:
        return
    while elem.getprevious() is not None:
        del parent[0]


def _parse_gpx_speed(ext_elem: Any | None) -> float:
    """Extract speed value from GPX extensions element."""
    if ext_elem is None:
        return 0.0
    speed_elem = ext_elem.find(f"{{{_GPX_NAMESPACE}}}speed")
    if speed_elem is None or not speed_elem.text:
        return 0.0
    try:
        return float(speed_elem.text)
    except ValueError:
        return 0.0


def _extract_gpx_point_data(elem: Any) -> tuple[str, str, str | None, str, float]:
    """Extract coordinate and metadata from a GPX trackpoint element."""
    latitude = elem.get("lat") or ""
    longitude = elem.get("lon") or ""
    if not latitude or not longitude:
        _logger.debug("Skipping GPX trackpoint with missing latitude/longitude: %s", elem.attrib)

    ele_elem = elem.find(f"{{{_GPX_NAMESPACE}}}ele")
    time_elem = elem.find(f"{{{_GPX_NAMESPACE}}}time")

    altitude = ele_elem.text if ele_elem is not None else None
    time_str = (time_elem.text or "") if time_elem is not None else ""

    ext_elem = elem.find(f"{{{_GPX_NAMESPACE}}}extensions")
    speed_val = _parse_gpx_speed(ext_elem)

    return latitude, longitude, altitude, time_str, speed_val


def _create_route_point(
    latitude: str, longitude: str, altitude: str | None, time_str: str, speed_val: float
) -> RoutePoint:
    """Create a RoutePoint from extracted GPX data."""
    return RoutePoint(
        time=datetime.fromisoformat(time_str.replace("Z", "+00:00")),
        latitude=float(latitude),
        longitude=float(longitude),
        altitude=float(altitude) if altitude is not None else 0.0,
        altitude_available=altitude is not None,
        speed=speed_val,
    )


def clip_route_to_window(
    route: WorkoutRoute,
    window_start: datetime | None,
    window_end: datetime | None,
) -> WorkoutRoute:
    """Return route points clipped to WorkoutRoute time window.

    Uses binary search on the cached sorted-times list for O(log n) clipping instead
    of an O(n) linear scan. Falls back to a linear scan if route times are not monotonic.
    """
    if window_start is None or window_end is None:
        return WorkoutRoute(points=list(route.points))

    times = route.sorted_times()
    if not times:
        return WorkoutRoute(points=[])

    try:
        is_monotonic = all(t1 <= t2 for t1, t2 in zip(times, times[1:]))
    except TypeError:
        _logger.debug("Non-comparable route times encountered; falling back to linear clipping")
        is_monotonic = False

    if is_monotonic:
        left = bisect_left(times, window_start)
        right = bisect_right(times, window_end)
        return WorkoutRoute(points=route.points[left:right])

    clipped_points: list[RoutePoint] = [
        point
        for point in route.points
        if point.time is not None  # type: ignore[redundant-expr]
        and window_start <= point.time <= window_end
    ]
    return WorkoutRoute(points=clipped_points)


def _should_skip_merged_point(last_point: RoutePoint | None, point: RoutePoint) -> bool:
    """Return whether a point should be skipped while merging route parts."""
    if last_point is None:
        return False
    if point.time < last_point.time:
        _logger.debug(
            "Skipping overlapping GPX point during route merge: %s < %s",
            point.time,
            last_point.time,
        )
        return True
    return point == last_point


def merge_route_parts(route_parts: list[WorkoutRoute]) -> WorkoutRoute | None:
    """Merge route parts as a compatibility route while preserving part boundaries."""
    if not route_parts:
        return None

    merged_points: list[RoutePoint] = []
    for route_part in route_parts:
        for point in route_part.points:
            last_point = merged_points[-1] if merged_points else None
            if _should_skip_merged_point(last_point, point):
                continue
            merged_points.append(point)

    return WorkoutRoute(points=merged_points) if merged_points else None


def trim_overlapping_route_part(
    existing_parts: list[WorkoutRoute],
    route_part: WorkoutRoute,
) -> WorkoutRoute | None:
    """Deduplicate and trim overlapping points from a route part before appending.

    Returns None if the entire route part overlaps with existing parts.
    """
    if not existing_parts:
        return route_part
    if not route_part.points:
        return None

    existing_points: set[RoutePoint] = set()
    existing_timestamps: set[datetime] = set()
    for existing in existing_parts:
        existing_points.update(existing.points)
        existing_timestamps.update(p.time for p in existing.points)

    first_unique_idx = 0
    while first_unique_idx < len(route_part.points):
        pt = route_part.points[first_unique_idx]
        if pt not in existing_points and pt.time not in existing_timestamps:
            break
        first_unique_idx += 1

    if first_unique_idx == len(route_part.points):
        return None

    suffix_points = [
        pt
        for pt in route_part.points[first_unique_idx:]
        if pt not in existing_points and pt.time not in existing_timestamps
    ]
    if not suffix_points:
        return None

    if first_unique_idx == 0 and len(suffix_points) == len(route_part.points):
        return route_part

    return WorkoutRoute(points=suffix_points)


def get_or_init_route_parts(record: WorkoutRecord) -> list[WorkoutRoute]:
    """Retrieve or initialize the list of WorkoutRoute parts in a workout record."""
    existing_parts = record.get("route_parts")
    if isinstance(existing_parts, list) and all(
        isinstance(p, WorkoutRoute) for p in existing_parts
    ):
        return existing_parts

    route_parts: list[WorkoutRoute] = []
    if isinstance(existing_parts, list):
        route_parts = [p for p in existing_parts if isinstance(p, WorkoutRoute)]
    record["route_parts"] = route_parts
    return route_parts


class GpxLoader:
    """Loads and caches GPX route files from an Apple Health export ZIP."""

    def __init__(self) -> None:
        self._route_cache: dict[str, WorkoutRoute | None] = {}

    def clear_cache(self) -> None:
        self._route_cache.clear()

    def load_route_cached(self, zipfile: ZipFile, route_path: str) -> WorkoutRoute | None:
        """Load GPX route once per file path for the current export parsing session."""
        if route_path not in self._route_cache:
            self._route_cache[route_path] = self._load_route(zipfile, route_path)
        return self._route_cache[route_path]

    def _load_route(self, zipfile: ZipFile, route_path: str) -> WorkoutRoute | None:
        """Load GPX route file from the export zip."""
        try:
            with zipfile.open(f"apple_health_export{route_path}") as route_file:
                points: list[RoutePoint] = []
                for _, elem in iterparse(
                    route_file,
                    events=("end",),
                    tag=f"{{{_GPX_NAMESPACE}}}trkpt",
                    **_SAFE_ITERPARSE_OPTIONS,
                ):
                    point_data = _extract_gpx_point_data(elem)
                    try:
                        points.append(_create_route_point(*point_data))
                    except (TypeError, ValueError) as exc:
                        if point_data[0] and point_data[1]:
                            _logger.debug(
                                "Skipping malformed GPX trackpoint for %s (error: %s): %s",
                                route_path,
                                exc,
                                elem.attrib,
                            )
                    _purge_element(elem)
                return WorkoutRoute(points=points)
        except KeyError:
            return None
