"""Route-comparison helpers for the workout detail modal Comparisons tab.

This module owns everything related to *finding* and *displaying* workouts that
share the same GPS route:

* :func:`_get_row_routes` / :func:`_row_has_route` – route data accessors.
* :func:`_merge_adjacent_route_parts` – merge GPS-pause-split segments.
* :func:`_route_endpoints` – extract the start/end coordinates for a row.
* :func:`_routes_shape_match` – lightweight intermediate-waypoint check.
* :func:`find_similar_route_workouts` – main similarity search.
* :func:`_pace_from_row`, :func:`_format_duration_diff` – display formatters.
* :func:`_build_comparison_display_rows` – leaderboard row builder.
* :func:`_do_refresh_comparisons_tab` – UI refresh helper.
"""

from __future__ import annotations

from typing import Any

from i18n import t
from logic.workout_manager.workout_route import RoutePoint, WorkoutRoute
from ui.helpers import _format_split_pace

# ---------------------------------------------------------------------------
# Row-route accessors
# ---------------------------------------------------------------------------


def _row_has_route(row: dict[str, Any]) -> bool:
    """Return True when the row contains a non-empty GPS route.

    Used to decide whether to enable the Route / Comparisons tabs in the
    workout detail modal.

    Args:
        row: A workout row dict as returned by ``_build_workout_rows()``.

    Returns:
        True when a :class:`~logic.workout_manager.workout_route.WorkoutRoute`
        with at least one point is stored under the ``"route"`` key.
    """
    route = row.get("route")
    return isinstance(route, WorkoutRoute) and not route.is_empty


def _get_row_routes(row: dict[str, Any]) -> list[WorkoutRoute]:
    """Return non-empty route parts for the row, falling back to the merged route."""
    route_parts = row.get("route_parts")
    if isinstance(route_parts, list):
        valid_parts = [
            part for part in route_parts if isinstance(part, WorkoutRoute) and not part.is_empty
        ]
        if valid_parts:
            return valid_parts
    route = row.get("route")
    if isinstance(route, WorkoutRoute) and not route.is_empty:
        return [route]
    return []


# ---------------------------------------------------------------------------
# Route comparison constants
# ---------------------------------------------------------------------------

#: Maximum straight-line distance (metres) between the start (or end) points of
#: two routes for them to be considered geographically similar.
_SIMILAR_ROUTE_START_END_RADIUS_M: float = 50.0

#: Maximum allowed relative deviation in total distance between two routes for
#: them to be considered the same course.  A value of 0.05 means ±5 %.
_SIMILAR_ROUTE_DISTANCE_TOLERANCE: float = 0.05

#: Maximum straight-line distance (metres) between intermediate waypoints sampled
#: at the same fractional position along two routes when checking their shape.
_SIMILAR_ROUTE_WAYPOINT_RADIUS_M: float = 100.0

#: Fractional positions along the route used for the intermediate shape check.
#: Three evenly spaced interior samples (25 %, 50 %, 75 %) give a lightweight
#: sanity-check that the two routes actually follow the same path.
_SIMILAR_ROUTE_WAYPOINT_FRACTIONS: tuple[float, ...] = (0.25, 0.50, 0.75)

#: Maximum number of ranked rows shown in the Comparisons tab leaderboard.
_COMPARISON_TOP_N: int = 10

#: Maximum distance (metres) between the last point of one route segment and the
#: first point of the next for them to be considered GPS-adjacent and eligible
#: for merging into a single continuous route.
_ADJACENT_SEGMENT_THRESHOLD_M: float = 50.0


# ---------------------------------------------------------------------------
# Multi-segment route merging
# ---------------------------------------------------------------------------


def _merge_adjacent_route_parts(
    routes: list[WorkoutRoute],
    adjacency_threshold_m: float = _ADJACENT_SEGMENT_THRESHOLD_M,
) -> WorkoutRoute:
    """Merge consecutive route segments into one when GPS-adjacent.

    Workouts recorded with GPS pauses or phone lock/unlock may be stored as
    multiple :class:`~logic.workout_manager.workout_route.WorkoutRoute`
    segments.  When every consecutive pair of segments ends/starts within
    *adjacency_threshold_m* metres of each other they represent the same
    continuous course and are merged into a single route.

    When *any* consecutive pair exceeds the threshold the first segment is
    returned unchanged; the workout is treated as a multi-course activity that
    should not be collapsed.

    Args:
        routes: Ordered, non-empty list of route parts for one workout.
        adjacency_threshold_m: Maximum end-to-start gap (metres) to accept as
            GPS noise and still merge.  Defaults to
            :data:`_ADJACENT_SEGMENT_THRESHOLD_M` (50 m).

    Returns:
        A merged :class:`~logic.workout_manager.workout_route.WorkoutRoute`
        containing the points from all segments when all consecutive pairs are
        adjacent, or just ``routes[0]`` when they are not.  Returns an empty
        :class:`~logic.workout_manager.workout_route.WorkoutRoute` when
        *routes* is empty.
    """
    if not routes:
        return WorkoutRoute(points=[])
    if len(routes) == 1:
        return routes[0]

    # Verify that every consecutive pair is GPS-adjacent.
    for prev, nxt in zip(routes, routes[1:]):
        if prev.is_empty or nxt.is_empty:
            continue
        end_pt = prev.points[-1]
        start_pt = nxt.points[0]
        gap_m = WorkoutRoute.haversine_m(
            end_pt.latitude,
            end_pt.longitude,
            start_pt.latitude,
            start_pt.longitude,
        )
        if gap_m > adjacency_threshold_m:
            # Non-adjacent segments → fall back to the first segment only.
            return routes[0]

    # All consecutive pairs are adjacent → merge all points in order.
    merged_points: list[RoutePoint] = []
    for route in routes:
        merged_points.extend(route.points)
    return WorkoutRoute(points=merged_points)


# ---------------------------------------------------------------------------
# Route endpoint extraction
# ---------------------------------------------------------------------------


def _route_endpoints(row: dict[str, Any]) -> tuple[float, float, float, float] | None:
    """Return ``(start_lat, start_lon, end_lat, end_lon)`` for *row*'s GPS route.

    Uses the first point of the first route part as the start and the last
    point of the last route part as the end so that multi-segment workouts
    are handled correctly.

    Args:
        row: A workout row dict as returned by ``_build_workout_rows()``.

    Returns:
        A 4-tuple of floats, or ``None`` when no non-empty GPS route is stored.
    """
    routes = _get_row_routes(row)
    if not routes:
        return None
    first_route = routes[0]
    last_route = routes[-1]
    if first_route.is_empty or last_route.is_empty:
        return None
    start = first_route.points[0]
    end = last_route.points[-1]
    return start.latitude, start.longitude, end.latitude, end.longitude


# ---------------------------------------------------------------------------
# Route shape comparison
# ---------------------------------------------------------------------------


def _routes_shape_match(
    route_a: WorkoutRoute,
    route_b: WorkoutRoute,
) -> bool:
    """Check whether two routes follow the same path using intermediate waypoints.

    Samples each route at :data:`_SIMILAR_ROUTE_WAYPOINT_FRACTIONS` of its total
    distance and verifies that the corresponding GPS points are within
    :data:`_SIMILAR_ROUTE_WAYPOINT_RADIUS_M` metres.  A fraction is skipped when
    either route returns ``None`` from :meth:`~WorkoutRoute.sample_point_at_fraction`
    (e.g. very short routes with too few points).

    Args:
        route_a: First GPS route to compare.
        route_b: Second GPS route to compare.

    Returns:
        ``True`` when all sampled waypoints are within the threshold, ``False``
        when any pair exceeds :data:`_SIMILAR_ROUTE_WAYPOINT_RADIUS_M`.
    """
    for fraction in _SIMILAR_ROUTE_WAYPOINT_FRACTIONS:
        pt_a = route_a.sample_point_at_fraction(fraction)
        pt_b = route_b.sample_point_at_fraction(fraction)
        if pt_a is None or pt_b is None:
            continue
        if (
            WorkoutRoute.haversine_m(pt_a[0], pt_a[1], pt_b[0], pt_b[1])
            > _SIMILAR_ROUTE_WAYPOINT_RADIUS_M
        ):
            return False
    return True


# ---------------------------------------------------------------------------
# Similarity search
# ---------------------------------------------------------------------------


def find_similar_route_workouts(
    current_row: dict[str, Any],
    all_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return all rows whose GPS route is similar to *current_row*'s route.

    Two routes are considered similar when they share the same
    ``raw_activity_type``, both have GPS data, their start points are within
    :data:`_SIMILAR_ROUTE_START_END_RADIUS_M` metres of each other, their end
    points are within the same radius, their total distances are within
    :data:`_SIMILAR_ROUTE_DISTANCE_TOLERANCE` of each other, and intermediate
    waypoints sampled at 25 %, 50 %, and 75 % of each route are within
    :data:`_SIMILAR_ROUTE_WAYPOINT_RADIUS_M` metres.

    When a workout has multiple GPS route parts (e.g. because GPS was paused
    and resumed), :func:`_merge_adjacent_route_parts` is called first to
    combine them into a single route for comparison purposes.  If the segments
    are not GPS-adjacent (large gap between them) only the first segment is
    used for the shape check.

    The returned list always includes *current_row* itself (when it has a GPS
    route) and is sorted by ``duration_sort`` ascending so that the fastest
    performance ranks first.

    Args:
        current_row: The workout row whose route is used as the reference.
        all_rows: The full list of workout rows to compare against.

    Returns:
        Rows with similar routes sorted fastest-first, or an empty list when
        *current_row* has no GPS route or no valid distance.
    """
    current_endpoints = _route_endpoints(current_row)
    if current_endpoints is None:
        return []

    current_distance = current_row.get("distance_sort")
    if not isinstance(current_distance, (int, float)) or current_distance <= 0:
        return []

    current_type = current_row.get("raw_activity_type")
    c_s_lat, c_s_lon, c_e_lat, c_e_lon = current_endpoints
    current_routes = _get_row_routes(current_row)
    current_merged = _merge_adjacent_route_parts(current_routes)

    similar: list[dict[str, Any]] = []
    for row in all_rows:
        if row.get("raw_activity_type") != current_type:
            continue
        endpoints = _route_endpoints(row)
        if endpoints is None:
            continue
        dist = row.get("distance_sort")
        if not isinstance(dist, (int, float)) or dist <= 0:
            continue
        if abs(dist / current_distance - 1.0) > _SIMILAR_ROUTE_DISTANCE_TOLERANCE:
            continue
        r_s_lat, r_s_lon, r_e_lat, r_e_lon = endpoints
        if (
            WorkoutRoute.haversine_m(c_s_lat, c_s_lon, r_s_lat, r_s_lon)
            > _SIMILAR_ROUTE_START_END_RADIUS_M
        ):
            continue
        if (
            WorkoutRoute.haversine_m(c_e_lat, c_e_lon, r_e_lat, r_e_lon)
            > _SIMILAR_ROUTE_START_END_RADIUS_M
        ):
            continue
        # Compare intermediate waypoints using the merged routes so multi-segment
        # workouts are evaluated across their full GPS path.
        candidate_routes = _get_row_routes(row)
        candidate_merged = _merge_adjacent_route_parts(candidate_routes)
        if not _routes_shape_match(current_merged, candidate_merged):
            continue
        similar.append(row)

    similar.sort(key=lambda r: r.get("duration_sort") or float("inf"))
    return similar


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------


def _pace_from_row(row: dict[str, Any], distance_unit: str) -> str:
    """Compute and format average pace for a workout row.

    Args:
        row: A workout row dict with ``duration_sort`` (seconds) and
            ``distance_sort`` (metres) keys.
        distance_unit: ``"km"`` or ``"mi"``.

    Returns:
        A formatted pace string (e.g. ``"5:12 min/km"``), or ``"–"`` when the
        required values are missing or zero.
    """
    duration_s = row.get("duration_sort")
    distance_m = row.get("distance_sort")
    if not isinstance(duration_s, (int, float)) or not isinstance(distance_m, (int, float)):
        return "–"
    if duration_s <= 0 or distance_m <= 0:
        return "–"
    pace_min_per_km = (duration_s / 60.0) / (distance_m / 1000.0)
    return _format_split_pace(pace_min_per_km, distance_unit)


def _format_duration_diff(duration_s: float, best_duration_s: float) -> str:
    """Format the time difference between a duration and the best (fastest) time.

    Args:
        duration_s: Duration of the entry to display, in seconds.
        best_duration_s: Duration of the fastest (rank-1) entry, in seconds.

    Returns:
        ``"–"`` for the rank-1 entry (or any entry faster than rank 1),
        otherwise a ``"+mm:ss"`` string representing the positive offset.
    """
    diff = duration_s - best_duration_s
    if diff <= 0:
        return "–"
    total_secs = int(round(diff))
    mins = total_secs // 60
    secs = total_secs % 60
    return f"+{mins}:{secs:02d}"


# ---------------------------------------------------------------------------
# Leaderboard row builder
# ---------------------------------------------------------------------------


def _build_comparison_display_rows(
    similar: list[dict[str, Any]],
    current_row_id: str,
    distance_unit: str,
    top_n: int = _COMPARISON_TOP_N,
) -> tuple[list[dict[str, Any]], int | None]:
    """Build display rows for the route-comparison leaderboard table.

    The leaderboard shows up to *top_n* rows ranked fastest-first.  Extra rows
    are appended in this order when they are not already present in the top-N:

    1. **Current workout** – appended when it falls outside the top *top_n*,
       so the athlete can always see their own result.
    2. **Slowest workout** – always appended when not already shown, so the
       full performance spread is visible.

    As a result the table has at most ``top_n + 2`` rows (top-N + current
    overflow + slowest), and as few as ``top_n`` rows when both the current and
    the slowest are already within the top *top_n*.

    Each row also carries a ``diff_str`` field with the duration offset from
    rank 1 formatted as ``"+mm:ss"`` (or ``"–"`` for the fastest entry).

    Args:
        similar: Sorted list of similar-route rows (fastest-first), as returned
            by :func:`find_similar_route_workouts`.
        current_row_id: The ``"id"`` value of the current workout row.
        distance_unit: ``"km"`` or ``"mi"`` – passed to :func:`_pace_from_row`.
        top_n: Maximum number of ranked rows to include before the optional
            overflow rows.

    Returns:
        A ``(display_rows, current_rank)`` tuple where *display_rows* is the
        list of dicts ready for a ``ui.table``, and *current_rank* is the
        1-indexed rank of the current workout (or ``None`` if it is absent from
        *similar*).
    """
    current_rank: int | None = None
    for i, row in enumerate(similar):
        if row.get("id") == current_row_id:
            current_rank = i + 1
            break

    # best_duration_s is only used when `similar` is non-empty (the loop below
    # always has at least one entry when called from _do_refresh_comparisons_tab
    # which guards on `len(similar) >= 2`).  The 0.0 fallback is a safe default
    # that makes _format_duration_diff return "–" for all rows in the unlikely
    # edge case of an empty list reaching this function directly.
    best_duration_s: float = float(similar[0].get("duration_sort") or 0.0) if similar else 0.0

    def _make_display_row(rank: int, row: dict[str, Any], is_current: bool) -> dict[str, Any]:
        row_duration_s = float(row.get("duration_sort") or 0.0)
        return {
            "rank": rank,
            "rank_str": f"→ {rank}" if is_current else str(rank),
            "date": row.get("date", "–"),
            "duration": row.get("duration", "–"),
            "pace": _pace_from_row(row, distance_unit),
            "diff_str": _format_duration_diff(row_duration_s, best_duration_s),
        }

    display_rows: list[dict[str, Any]] = []
    for i, row in enumerate(similar[:top_n]):
        rank = i + 1
        is_current = row.get("id") == current_row_id
        display_rows.append(_make_display_row(rank, row, is_current))

    # Track which row IDs are already shown so we avoid duplicates below.
    shown_ids: set[str | None] = {r.get("id") for r in similar[:top_n]}

    # Append current workout below the top-N cut when it is outside the top N.
    if current_rank is not None and current_rank > top_n:
        current = next((r for r in similar if r.get("id") == current_row_id), None)
        if current is not None:
            display_rows.append(_make_display_row(current_rank, current, is_current=True))
            shown_ids.add(current_row_id)

    # Append the slowest entry (last in the sorted list) when not already shown.
    # This always gives the user a sense of the full spread even with top_n < total.
    if similar:
        slowest = similar[-1]
        slowest_rank = len(similar)
        slowest_id = slowest.get("id")
        if slowest_id not in shown_ids:
            is_current = slowest_id == current_row_id
            display_rows.append(_make_display_row(slowest_rank, slowest, is_current))

    return display_rows, current_rank


# ---------------------------------------------------------------------------
# UI refresh helper
# ---------------------------------------------------------------------------


def _do_refresh_comparisons_tab(
    no_route_label: Any,
    no_similar_label: Any,
    rank_label: Any,
    comparisons_table: Any,
    row: dict[str, Any],
    all_rows: list[dict[str, Any]],
) -> None:
    """Update the Comparisons tab elements for the current workout row.

    When the workout has no GPS route the no-route placeholder is shown and all
    other elements are hidden.  When the route exists but no similar workouts
    are found the no-similar placeholder is shown.  Otherwise the leaderboard
    table is populated with up to :data:`_COMPARISON_TOP_N` ranked rows (plus
    the current workout when it falls outside the top N).

    Args:
        no_route_label:   Placeholder shown when the workout has no GPS route.
        no_similar_label: Placeholder shown when no similar routes exist.
        rank_label:       Label displaying the user's rank and total count.
        comparisons_table: ``ui.table`` element for the leaderboard.
        row:              Current workout row dict.
        all_rows:         All available workout rows used for comparison.
    """
    routes = _get_row_routes(row)
    if not routes:
        no_route_label.set_visibility(True)
        no_similar_label.set_visibility(False)
        rank_label.set_visibility(False)
        comparisons_table.set_visibility(False)
        return

    no_route_label.set_visibility(False)

    # Lazily compute similar routes and cache the result in the row dict so
    # repeated tab switches do not re-run the comparison search.
    if "similar_routes" not in row:
        row["similar_routes"] = find_similar_route_workouts(row, all_rows)
    similar: list[dict[str, Any]] = row["similar_routes"]

    # Require at least two rows (current + one other) to render the leaderboard.
    has_similar = len(similar) >= 2
    no_similar_label.set_visibility(not has_similar)
    rank_label.set_visibility(has_similar)
    comparisons_table.set_visibility(has_similar)

    if not has_similar:
        return

    du = row.get("distance_unit", "km")
    current_id = str(row.get("id", ""))
    display_rows, current_rank = _build_comparison_display_rows(similar, current_id, du)

    total = len(similar)
    rank_str = str(current_rank) if current_rank is not None else "–"
    rank_label.set_text(t("Rank: {rank} of {total}", rank=rank_str, total=str(total)))

    comparisons_table.rows = display_rows
    comparisons_table.update()
