"""Workout detail modal dialog for Apple Health Analyzer."""

from collections.abc import Callable
from typing import Any, TypeAlias

from nicegui import ui

from i18n import t
from ui.css import (
    BUTTON_DENSE_PROPS,
    LABEL_UPPERCASE_CLASSES,
    MODAL_CARD_CLASSES,
    MODAL_FIELD_LABEL_CLASSES,
    MODAL_FIELD_ROW_CLASSES,
    MODAL_FIELD_VALUE_CLASSES,
    MODAL_HEADER_ROW_CLASSES,
    MODAL_NAV_COUNTER_CLASSES,
    MODAL_NAV_ROW_CLASSES,
    MODAL_SECTION_DIVIDER_CLASSES,
    MODAL_SECTION_HEADING_CLASSES,
    MODAL_SPLITS_CELL_CLASSES,
    MODAL_SPLITS_HEADER_CLASSES,
    MODAL_SPLITS_ROW_CLASSES,
)

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

#: Running-specific fields shown only when the workout is a Running activity.
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

#: Header columns for the splits table: (row_key, header_label).
_SPLITS_COLUMNS: list[tuple[str, str]] = [
    ("split", "km"),
    ("pace", "/km"),
    ("elev", "elev"),
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


def _render_splits_rows(
    splits_body: Any,
    splits: list[dict[str, float | int]],
) -> None:
    """Clear *splits_body* and populate it with one row per split.

    Args:
        splits_body: A NiceGUI container element (e.g. ``ui.column()``) to
            render into.
        splits: List of split dicts as returned by
            :meth:`~logic.workout_route.WorkoutRoute.compute_splits`.
    """
    splits_body.clear()
    with splits_body:
        for split in splits:
            pace_str = _format_split_pace(float(split["pace_min_per_km"]))
            elev_str = _format_elevation_change(float(split["elevation_change_m"]))
            with ui.row().classes(MODAL_SPLITS_ROW_CLASSES):
                ui.label(str(int(split["split"]))).classes(MODAL_SPLITS_CELL_CLASSES)
                ui.label(pace_str).classes(MODAL_SPLITS_CELL_CLASSES)
                ui.label(elev_str).classes(MODAL_SPLITS_CELL_CLASSES)


def create_workout_detail_modal(
    rows: list[dict[str, Any]],
) -> Callable[[int], None]:
    """Create a workout detail modal dialog and return a callable to open it.

    The dialog is created once in the current NiceGUI context.  Calling the
    returned ``open_at(index)`` function updates the displayed content and
    opens the dialog at the given row index.

    Navigation within the open modal is supported via left/right arrow buttons.
    The dialog closes on Esc (Quasar default) or when the close button is clicked.

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

            # ---- Generic field rows ----
            # Each row is shown/hidden based on whether the value is missing.
            field_rows: dict[str, tuple[Any, Any]] = {}
            for field_key, label_fn in _FIELD_DISPLAY:
                with ui.row().classes(MODAL_FIELD_ROW_CLASSES) as frow:
                    ui.label(label_fn()).classes(MODAL_FIELD_LABEL_CLASSES)
                    value_el = ui.label().classes(MODAL_FIELD_VALUE_CLASSES)
                field_rows[field_key] = (frow, value_el)

            # ---- Running-specific section ----
            # Shown only when the current workout is a Running activity.
            with ui.column().classes("w-full") as running_section:
                ui.element("div").classes(MODAL_SECTION_DIVIDER_CLASSES)
                ui.label(t("Running")).classes(MODAL_SECTION_HEADING_CLASSES)
                running_field_rows: dict[str, tuple[Any, Any]] = {}
                for field_key, label_fn in _RUNNING_FIELD_DISPLAY:
                    with ui.row().classes(MODAL_FIELD_ROW_CLASSES) as frow:
                        ui.label(label_fn()).classes(MODAL_FIELD_LABEL_CLASSES)
                        value_el = ui.label().classes(MODAL_FIELD_VALUE_CLASSES)
                    running_field_rows[field_key] = (frow, value_el)

                # ---- Splits sub-section ----
                with ui.column().classes("w-full") as splits_section:
                    ui.label(t("Splits")).classes(MODAL_SECTION_HEADING_CLASSES)
                    # Header row
                    with ui.row().classes(MODAL_SPLITS_ROW_CLASSES):
                        ui.label(t("km")).classes(MODAL_SPLITS_HEADER_CLASSES)
                        ui.label(t("Pace")).classes(MODAL_SPLITS_HEADER_CLASSES)
                        ui.label(t("Elev")).classes(MODAL_SPLITS_HEADER_CLASSES)
                    # Dynamic body — rebuilt on every refresh
                    splits_body = ui.column().classes("w-full")

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

    def _refresh() -> None:
        """Update all modal elements to reflect the current workout."""
        idx = modal_state["index"]
        row = rows[idx]
        n = len(rows)

        modal_title.set_text(f"{row['activity_type']} – {row['date']}")
        nav_counter.set_text(f"{idx + 1} / {n}")

        if idx == 0:
            prev_btn.props("disabled")
        else:
            prev_btn.props(remove="disabled")

        if idx == n - 1:
            next_btn.props("disabled")
        else:
            next_btn.props(remove="disabled")

        _update_fields(field_rows, row)

        # Show/hide the running section based on activity type
        is_running = row.get("activity_type") == "Running"
        running_section.set_visibility(is_running)
        if is_running:
            _update_fields(running_field_rows, row)
            splits = row.get("splits") or []
            splits_section.set_visibility(bool(splits))
            _render_splits_rows(splits_body, splits)

    def _navigate(delta: int) -> None:
        """Move to the next or previous workout by *delta* steps."""
        new_idx = modal_state["index"] + delta
        if 0 <= new_idx < len(rows):
            modal_state["index"] = new_idx
            _refresh()

    def open_at(index: int) -> None:
        """Open the modal at the given *index*."""
        modal_state["index"] = max(0, min(index, len(rows) - 1))
        _refresh()
        dialog.open()

    return open_at
