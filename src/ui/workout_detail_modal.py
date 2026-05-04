"""Workout detail modal dialog for Apple Health Analyzer."""

from collections.abc import Callable
from typing import Any, TypeAlias, cast

from nicegui import ui

from i18n import t
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
    MODAL_FIELD_LABEL_CLASSES,
    MODAL_FIELD_ROW_CLASSES,
    MODAL_FIELD_VALUE_CLASSES,
    MODAL_HEADER_ROW_CLASSES,
    MODAL_NAV_COUNTER_CLASSES,
    MODAL_NAV_ROW_CLASSES,
    MODAL_SPLITS_TABLE_CLASSES,
    MODAL_SWIM_TABLE_CLASSES,
    MODAL_TAB_PANELS_CLASSES,
    TABLE_DENSE_FLAT_PROPS,
    TABS_FULL_CLASSES,
)
from units import METERS_TO_MILES

#: Callable returning a translated label string; alias for readability.
_LabelFn: TypeAlias = Callable[[], str]

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
    ("vo2_max", lambda: t("VO₂ Max")),
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


def _build_swim_display_rows(intervals: list[SwimInterval]) -> list[dict[str, Any]]:
    """Build display-ready rows for the swim interval table.

    Delegates to :func:`~logic.workout_manager.swimming.build_swim_interval_display_rows`
    which merges all laps within each interval into a single summary row.

    Args:
        intervals: Ordered list of :class:`~logic.workout_manager.swimming.SwimInterval`
            objects produced by :func:`~logic.workout_manager.swimming.build_swim_intervals`.

    Returns:
        List of row dicts ready for assignment to a ``ui.table``.
    """
    return build_swim_interval_display_rows(intervals)


def _format_split_pace(pace_min_per_km: float) -> str:
    """Format a pace value (min/km) as a ``mm:ss`` string.

    Args:
        pace_min_per_km: Pace in minutes per kilometre.

    Returns:
        Formatted string such as ``"4:32"``.
    """
    minutes = int(pace_min_per_km)
    seconds = int(round((pace_min_per_km - minutes) * 60))
    if seconds == 60:
        minutes += 1
        seconds = 0
    return f"{minutes}:{seconds:02d}"


def _format_elevation_change(elevation_change_m: float) -> str:
    """Format an elevation change in metres as a compact signed string.

    Args:
        elevation_change_m: Net elevation change in metres.

    Returns:
        Formatted string such as ``"+5 m"`` or ``"-2 m"``.
    """
    sign = "+" if elevation_change_m >= 0 else ""
    return f"{sign}{int(round(elevation_change_m))} m"


def _format_split_rows(
    splits: list[dict[str, Any]],
    distance_unit: str,
) -> list[dict[str, Any]]:
    """Format raw split dicts into display rows suitable for a ``ui.table``.

    Args:
        splits: List of split dicts from
            :meth:`~logic.workout_manager.workout_route.WorkoutRoute.compute_splits`.
        distance_unit: Active distance unit, ``"km"`` or ``"mi"``.  Controls
            the pace-scale factor applied before formatting.

    Returns:
        List of row dicts with ``"split"``, ``"pace_str"``, and ``"elev_str"``
        keys ready for direct assignment to ``ui.table.rows``.
    """
    pace_scale = 1.0 / (1000.0 * METERS_TO_MILES) if distance_unit == "mi" else 1.0
    return [
        {
            "split": int(s["split"]),
            "pace_str": _format_split_pace(float(s["pace_min_per_km"]) * pace_scale),
            "elev_str": _format_elevation_change(float(s["elevation_change_m"])),
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
        with ui.row().classes(MODAL_FIELD_ROW_CLASSES) as frow:
            ui.label(label_fn()).classes(MODAL_FIELD_LABEL_CLASSES)
            value_el = ui.label().classes(MODAL_FIELD_VALUE_CLASSES)
        field_rows[field_key] = (frow, value_el)
    return field_rows


def _row_has_route(row: dict[str, Any]) -> bool:
    """Return True when the row contains a non-empty GPS route.

    Used to decide whether to enable the Splits tab in the workout detail modal.

    Args:
        row: A workout row dict as returned by ``_build_workout_rows()``.

    Returns:
        True when a :class:`~logic.workout_manager.workout_route.WorkoutRoute`
        with at least one point is stored under the ``"route"`` key.
    """
    route = row.get("route")
    return isinstance(route, WorkoutRoute) and not route.is_empty


#: Maps each supported raw activity type to the field keys shown in the Activity tab.
#: Used by :func:`_row_has_activity_data` to determine whether at least one field
#: has a non-missing value.
_ACTIVITY_FIELD_KEYS: dict[str, list[str]] = {
    "Running": [k for k, _ in _RUNNING_FIELD_DISPLAY],
    "Walking": [k for k, _ in _WALKING_FIELD_DISPLAY],
    "Hiking": [k for k, _ in _HIKING_FIELD_DISPLAY],
    # Swimming: enable Activity tab when any summary field is present.
    "Swimming": [k for k, _ in _SWIMMING_FIELD_DISPLAY],
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
    """Return True when the row contains at least one parsed swimming event.

    Used to decide whether to enable the Intervals tab in the workout detail
    modal.

    Args:
        row: A workout row dict as returned by ``_build_workout_rows()``.

    Returns:
        True when ``swimming_events`` is a non-empty list.
    """
    events = row.get("swimming_events")
    return isinstance(events, list) and len(events) > 0


def create_workout_detail_modal(
    rows: list[dict[str, Any]],
) -> Callable[[int], None]:
    """Create a workout detail modal dialog and return a callable to open it.

    The dialog is created once in the current NiceGUI context.  Calling the
    returned ``open_at(index)`` function updates the displayed content and
    opens the dialog at the given row index.

    Navigation within the open modal is supported via left/right arrow buttons.
    The dialog closes on Esc (Quasar default) or when the close button is clicked.

    The modal is organised into four tabs:

    * **Overview** – generic workout attributes (date, distance, calories, etc.).
    * **Activity** – type-specific metrics.  Running workouts show pace, cadence,
      stride length, vertical oscillation, ground contact time, step count, and
      VO₂ max.  Walking workouts show pace, cadence, step length, and step count.
      Hiking workouts show elevation gain, pace, cadence, step length, and step count.
      Swimming workouts show location, lap length, and total stroke count.
      Other activity types show a placeholder message; the tab is disabled.
    * **Intervals** – per-interval lap table for Swimming workouts.  Each row
      represents one active set (segment), with distance, time, stroke style,
      average SWOLF, and the rest duration before the next set.  The tab is
      disabled for non-swimming workouts or when no lap events are available.
    * **Splits** – per-km GPS-based splits in a compact table.  The tab is
      disabled when no GPS route is available.

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
                intervals_tab = ui.tab("intervals", t("Intervals"))
                splits_tab = ui.tab("splits", t("Splits"))

            # ---- Tab panels ----
            with ui.tab_panels(detail_tabs, value="overview").classes(MODAL_TAB_PANELS_CLASSES):
                # Overview tab: generic workout attributes
                with ui.tab_panel("overview"):
                    field_rows = _build_field_rows(_FIELD_DISPLAY)

                # Activity tab: type-specific metrics
                with ui.tab_panel("activity"):
                    # Shown for unsupported activity types
                    no_activity_label = ui.label(t("No activity-specific data available.")).classes(
                        LABEL_MUTED_CLASSES
                    )
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

                # Intervals tab: per-interval swim lap table (Swimming workouts only)
                with ui.tab_panel("intervals"):
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

                # Splits tab: per-km GPS splits table
                with ui.tab_panel("splits"):
                    no_splits_label = ui.label(t("No GPS route available.")).classes(
                        LABEL_MUTED_CLASSES
                    )
                    splits_columns = [
                        {
                            "name": "split",
                            "label": "km",
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

    def _refresh_activity_tab(row: dict[str, Any]) -> None:
        """Update activity tab: show type-specific metrics and set tab enabled state."""
        raw_type = row.get("raw_activity_type")
        is_running = raw_type == "Running"
        is_walking = raw_type == "Walking"
        is_hiking = raw_type == "Hiking"
        is_swimming = raw_type == "Swimming"
        has_data = _row_has_activity_data(row)
        no_activity_label.set_visibility(not has_data)
        running_container.set_visibility(is_running)
        walking_container.set_visibility(is_walking)
        hiking_container.set_visibility(is_hiking)
        swimming_container.set_visibility(is_swimming)
        activity_tab.set_enabled(has_data)
        if is_running:
            _update_fields(running_field_rows, row)
        elif is_walking:
            _update_fields(walking_field_rows, row)
        elif is_hiking:
            _update_fields(hiking_field_rows, row)
        elif is_swimming:
            _update_fields(swimming_field_rows, row)

    def _refresh_intervals_tab(row: dict[str, Any]) -> None:
        """Update the Intervals tab with swim lap data.

        Builds :class:`~logic.workout_manager.swimming.SwimInterval` objects from
        ``row["swimming_events"]`` and ``row["lap_length_m"]``, merges each
        interval's laps into a single summary row, and populates ``swim_table``.
        The table is hidden when no laps are available.
        """
        events = row.get("swimming_events") or []
        lap_length = float(row.get("lap_length_m") or 0.0)
        intervals = build_swim_intervals(events, lap_length)
        table_rows = _build_swim_display_rows(intervals)
        has_laps = bool(table_rows)
        no_swim_laps_label.set_visibility(not has_laps)
        swim_table.set_visibility(has_laps)
        if has_laps:
            swim_table.rows = table_rows
            swim_table.update()

    def _refresh_splits_tab(row: dict[str, Any]) -> None:
        """Update splits tab with GPS-based per-km or per-mi splits.

        Splits are computed lazily on first open (via :func:`_compute_splits_lazy`)
        and then cached in ``row["splits"]`` for instant display on subsequent
        navigations to the same workout.
        """
        splits = _compute_splits_lazy(row)
        has_splits = bool(splits)
        no_splits_label.set_visibility(not has_splits)
        splits_table.set_visibility(has_splits)
        if has_splits:
            du = row.get("distance_unit", "km")
            # Update column header to reflect the active distance unit (km / mi).
            splits_columns[0]["label"] = du
            splits_table.rows = _format_split_rows(splits, du)
            splits_table.update()

    def _refresh() -> None:
        """Update all modal elements to reflect the current workout."""
        idx = modal_state["index"]
        row = rows[idx]
        n = len(rows)

        _refresh_header(idx, n, row)
        _update_fields(field_rows, row)
        _refresh_activity_tab(row)
        intervals_tab.set_enabled(_row_has_swim_laps(row))
        splits_tab.set_enabled(_row_has_route(row))
        # Only refresh lazy tabs when they are currently active; switching to
        # them triggers _on_tab_change which handles the initial load.
        if detail_tabs.value == "intervals":
            _refresh_intervals_tab(row)
        elif detail_tabs.value == "splits":
            _refresh_splits_tab(row)

    def _navigate(delta: int) -> None:
        """Move to the next or previous workout by *delta* steps."""
        new_idx = modal_state["index"] + delta
        if 0 <= new_idx < len(rows):
            modal_state["index"] = new_idx
            _refresh()

    def _on_tab_change(e: Any) -> None:
        """Refresh lazy tabs when the user switches to them.

        * ``"intervals"`` – loads the swim interval table (lazily, on first open).
        * ``"splits"`` – computes GPS splits (lazily via
          :func:`_compute_splits_lazy`) and caches them in ``row["splits"]``.
        Other tab changes are ignored.
        """
        row = rows[modal_state["index"]]
        if e.value == "intervals":
            _refresh_intervals_tab(row)
        elif e.value == "splits":
            _refresh_splits_tab(row)

    detail_tabs.on_value_change(_on_tab_change)

    def open_at(index: int) -> None:
        """Open the modal at the given *index*."""
        modal_state["index"] = max(0, min(index, len(rows) - 1))
        _refresh()
        dialog.open()

    return open_at
