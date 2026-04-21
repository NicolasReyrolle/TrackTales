"""Workout detail modal dialog for Apple Health Analyzer."""

from collections.abc import Callable
from typing import Any, TypeAlias

from nicegui import ui

from i18n import t
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
    TABLE_DENSE_FLAT_PROPS,
    TABS_FULL_CLASSES,
)
from units import METERS_TO_MILES

#: Callable returning a translated label string; alias for readability.
_LabelFn: TypeAlias = Callable[[], str]

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
]

#: Running-specific fields shown in the Activity tab when the workout is Running.
#: All values are ``"–"`` for non-running workouts and are hidden automatically.
_RUNNING_FIELD_DISPLAY: list[tuple[str, _LabelFn]] = [
    ("pace", lambda: t("Avg Pace")),
    ("cadence", lambda: t("Avg Cadence")),
    ("stride_length", lambda: t("Avg Stride Length")),
    ("vertical_oscillation", lambda: t("Avg Vertical Oscillation")),
    ("ground_contact_time", lambda: t("Avg Ground Contact Time")),
    ("step_count", lambda: t("Step Count")),
    ("vo2_max", lambda: t("VO₂ Max")),
]


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
    """
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


def create_workout_detail_modal(
    rows: list[dict[str, Any]],
) -> Callable[[int], None]:
    """Create a workout detail modal dialog and return a callable to open it.

    The dialog is created once in the current NiceGUI context.  Calling the
    returned ``open_at(index)`` function updates the displayed content and
    opens the dialog at the given row index.

    Navigation within the open modal is supported via left/right arrow buttons.
    The dialog closes on Esc (Quasar default) or when the close button is clicked.

    The modal is organised into three tabs:

    * **Overview** – generic workout attributes (date, distance, calories, etc.).
    * **Activity** – type-specific metrics.  Running workouts show pace, cadence,
      stride length, vertical oscillation, ground contact time, step count, and
      VO₂ max.  Other activity types show a placeholder message.
    * **Splits** – per-km GPS-based splits in a compact table.  Hidden when no
      GPS route is available.

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
                ui.tab("activity", t("Activity"))
                ui.tab("splits", t("Splits"))

            # ---- Tab panels ----
            with ui.tab_panels(detail_tabs, value="overview").classes(TABS_FULL_CLASSES):
                # Overview tab: generic workout attributes
                with ui.tab_panel("overview"):
                    field_rows: dict[str, tuple[Any, Any]] = {}
                    for field_key, label_fn in _FIELD_DISPLAY:
                        with ui.row().classes(MODAL_FIELD_ROW_CLASSES) as frow:
                            ui.label(label_fn()).classes(MODAL_FIELD_LABEL_CLASSES)
                            value_el = ui.label().classes(MODAL_FIELD_VALUE_CLASSES)
                        field_rows[field_key] = (frow, value_el)

                # Activity tab: type-specific metrics
                with ui.tab_panel("activity"):
                    # Shown for non-running (or future unsupported) activity types
                    no_activity_label = ui.label(t("No activity-specific data available.")).classes(
                        LABEL_MUTED_CLASSES
                    )
                    # Running-specific metrics; shown only when activity is Running
                    running_container = ui.column().classes(TABS_FULL_CLASSES)
                    with running_container:
                        running_field_rows: dict[str, tuple[Any, Any]] = {}
                        for field_key, label_fn in _RUNNING_FIELD_DISPLAY:
                            with ui.row().classes(MODAL_FIELD_ROW_CLASSES) as frow:
                                ui.label(label_fn()).classes(MODAL_FIELD_LABEL_CLASSES)
                                value_el = ui.label().classes(MODAL_FIELD_VALUE_CLASSES)
                            running_field_rows[field_key] = (frow, value_el)

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
        """Update activity tab: show running metrics only for Running workouts."""
        is_running = row.get("raw_activity_type") == "Running"
        no_activity_label.set_visibility(not is_running)
        running_container.set_visibility(is_running)
        if is_running:
            _update_fields(running_field_rows, row)

    def _refresh_splits_tab(row: dict[str, Any]) -> None:
        """Update splits tab with GPS-based per-km or per-mi splits.

        Splits are computed lazily on first open (via :func:`_compute_splits_lazy`)
        and then cached in ``row["splits"]`` for instant display on subsequent
        navigations to the same workout.
        """
        # Lazy-compute splits on first open; cached result is reused on revisit.
        if "splits" not in row:
            _compute_splits_lazy(row)
        splits = row.get("splits") or []
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
        # Only refresh the Splits tab when it is currently active; switching to
        # the Splits tab triggers _on_tab_change which handles the initial load.
        if detail_tabs.value == "splits":
            _refresh_splits_tab(row)

    def _navigate(delta: int) -> None:
        """Move to the next or previous workout by *delta* steps."""
        new_idx = modal_state["index"] + delta
        if 0 <= new_idx < len(rows):
            modal_state["index"] = new_idx
            _refresh()

    def _on_tab_change(e: Any) -> None:
        """Refresh the Splits tab the first time the user switches to it.

        For rows whose splits have not yet been computed, this triggers
        :func:`_compute_splits_lazy` (via :func:`_refresh_splits_tab`) which
        caches the result in ``row["splits"]`` so subsequent visits are instant.
        The handler is only active when ``e.value == "splits"``; other tab
        changes are ignored.
        """
        if e.value == "splits":
            _refresh_splits_tab(rows[modal_state["index"]])

    detail_tabs.on_value_change(_on_tab_change)

    def open_at(index: int) -> None:
        """Open the modal at the given *index*."""
        modal_state["index"] = max(0, min(index, len(rows) - 1))
        _refresh()
        dialog.open()

    return open_at
