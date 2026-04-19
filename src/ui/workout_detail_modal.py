"""Workout detail modal dialog for Apple Health Analyzer."""

from collections.abc import Callable
from typing import Any

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
)

#: Ordered list of ``(row_key, i18n_label)`` for the generic detail view.
#: Fields whose value is ``"–"`` (missing) are hidden automatically.
_FIELD_DISPLAY: list[tuple[str, str]] = [
    ("date", "Date"),
    ("activity_type", "Activity"),
    ("duration", "Duration"),
    ("distance", "Distance"),
    ("calories", "Calories"),
    ("avg_hr", "Avg HR"),
    ("elevation", "Elevation Gain"),
    ("avg_power", "Avg Power"),
]


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
            for field_key, label_text in _FIELD_DISPLAY:
                with ui.row().classes(MODAL_FIELD_ROW_CLASSES) as frow:
                    ui.label(t(label_text)).classes(MODAL_FIELD_LABEL_CLASSES)
                    value_el = ui.label().classes(MODAL_FIELD_VALUE_CLASSES)
                field_rows[field_key] = (frow, value_el)

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

        if idx <= 0:
            prev_btn.props("disabled")
        else:
            prev_btn.props(remove="disabled")

        if idx >= n - 1:
            next_btn.props("disabled")
        else:
            next_btn.props(remove="disabled")

        for field_key, (frow, value_el) in field_rows.items():
            value = str(row.get(field_key, "–"))
            has_value = bool(value) and value != "–"
            frow.set_visibility(has_value)
            if has_value:
                value_el.set_text(value)

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
