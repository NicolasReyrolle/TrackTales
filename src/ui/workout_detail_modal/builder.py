"""Workout detail modal dialog for TrackTales."""

from collections.abc import Callable
from typing import Any, TypeAlias, cast

import pandas as pd
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
from ui.workout_detail_modal.routes import (
    _build_route_profile_chart_config_with_translate as _build_route_profile_chart_config_impl,
)
from ui.workout_detail_modal.routes import (
    _do_refresh_route_profile_tab as _do_refresh_route_profile_tab_impl,
)
from ui.workout_detail_modal.routes import (
    _do_refresh_route_tab as _do_refresh_route_tab_impl,
)
from units import METERS_TO_MILES

#: Callable returning a translated label string; alias for readability.
_LabelFn: TypeAlias = Callable[[], str]

#: i18n key reused across GPS-dependent modal sections.
_NO_GPS_ROUTE_MSG = "No GPS route available."
_HEART_RATE_SAMPLES_CACHE: tuple[int, pd.DataFrame] | None = None

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
        ``"avg_hr_str"``, and ``"elev_str"`` keys ready for direct assignment to
        ``ui.table.rows``.
    """
    return [
        {
            "split": int(s["split"]),
            "pace_str": _format_split_pace(float(s["pace_min_per_km"]), distance_unit),
            "speed_str": _format_split_speed(float(s["pace_min_per_km"]), distance_unit),
            "avg_hr_str": (
                "–"
                if s.get("avg_heart_rate") is None
                else f"{int(round(float(cast(float, s['avg_heart_rate']))))} bpm"
            ),
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
    _ensure_row_heart_rate_enriched(row)
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


def _get_cached_heart_rate_samples() -> pd.DataFrame:
    """Return cached normalized heart-rate samples for the active file load."""
    from app_state import state

    global _HEART_RATE_SAMPLES_CACHE

    cache_key = id(state.records_by_type)
    if _HEART_RATE_SAMPLES_CACHE is not None and _HEART_RATE_SAMPLES_CACHE[0] == cache_key:
        return _HEART_RATE_SAMPLES_CACHE[1]

    heart_rate_df = state.records_by_type.heart_rate()
    heart_rate_samples = pd.DataFrame(columns=["startDate", "value"])
    if not heart_rate_df.empty and {"startDate", "value"}.issubset(heart_rate_df.columns):
        heart_rate_samples = heart_rate_df[["startDate", "value"]].copy()
        heart_rate_samples["startDate"] = pd.to_datetime(
            heart_rate_samples["startDate"], utc=True, errors="coerce"
        ).dt.tz_localize(None)
        heart_rate_samples["value"] = pd.to_numeric(heart_rate_samples["value"], errors="coerce")
        heart_rate_samples = heart_rate_samples.dropna(subset=["startDate", "value"]).sort_values(
            "startDate"
        )

    _HEART_RATE_SAMPLES_CACHE = (cache_key, heart_rate_samples)
    return heart_rate_samples


def _ensure_row_heart_rate_enriched(row: dict[str, Any]) -> None:
    """Attach nearest heart-rate samples to the row's routes once, on demand."""
    if row.get("_heart_rate_routes_enriched"):
        return

    from ui import workout_table as wt

    workout_start = row.get("workout_start_utc")
    workout_end = row.get("workout_end_utc")
    if workout_start is None or workout_end is None:
        row["_heart_rate_routes_enriched"] = True
        return

    wt._enrich_routes_with_heart_rate(
        row,
        {
            "startDateUtc": workout_start,
            "endDateUtc": workout_end,
            "xmlFragment": row.get("xmlFragment"),
        },
        _get_cached_heart_rate_samples(),
        row.get("workout_index"),
    )
    row["_heart_rate_routes_enriched"] = True


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

    Creates a ``ui.element("div")`` row for each entry in *field_display* and
    returns a dict mapping each field key to its ``(row_element, value_label)`` pair so that
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


def _build_route_profile_chart_config(routes: list[WorkoutRoute]) -> dict[str, Any]:
    """Build route profile chart config using the modal's translation context."""
    return _build_route_profile_chart_config_impl(routes, translate=t)


def _do_refresh_route_tab(
    no_route_label: Any,
    route_map: Any,
    row: dict[str, Any],
) -> None:
    """Update the Route tab map with plain route polylines."""
    _do_refresh_route_tab_impl(
        no_route_label,
        route_map,
        row,
        fit_bounds_scheduler=background_tasks.create,
        translate=t,
    )


def _do_refresh_route_profile_tab(
    no_route_label: Any,
    route_profile_chart: Any,
    row: dict[str, Any],
) -> None:
    """Update the Charts tab chart with altitude, pace, and heart-rate series."""
    _ensure_row_heart_rate_enriched(row)
    _do_refresh_route_profile_tab_impl(
        no_route_label,
        route_profile_chart,
        row,
        translate=t,
    )


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
      with start/end markers.
    * **Charts** – elevation, pace, and heart-rate charts for the workout route.
      Includes distance-based tooltip metrics (pace, speed, altitude, optional heart rate).
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
                profile_tab = ui.tab("profile", t("Charts"))
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
                            "name": "avg_hr",
                            "label": t("Avg HR"),
                            "field": "avg_hr_str",
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

                # Charts tab: altitude + pace + heart-rate chart for route readability
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
        """Delegate to module-level helper; updates Charts tab chart and visibility."""
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
        refresh_fn = (
            _lazy_tab_refresh.get(detail_tabs.value) if isinstance(detail_tabs.value, str) else None
        )
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
        The Charts tab renders an elevation + pace + heart-rate chart from the route points.
        The Comparisons tab searches for similar routes and caches the result
        in ``row["similar_routes"]``.
        """
        tab_value = e.value if isinstance(e.value, str) else None
        refresh_fn = _lazy_tab_refresh.get(tab_value) if tab_value is not None else None
        if refresh_fn:
            refresh_fn(rows[modal_state["index"]])

    detail_tabs.on_value_change(_on_tab_change)

    def open_at(index: int) -> None:
        """Open the modal at the given *index*."""
        modal_state["index"] = max(0, min(index, len(rows) - 1))
        _refresh()
        dialog.open()

    return open_at
