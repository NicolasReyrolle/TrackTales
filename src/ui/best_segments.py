"""Best-segments loading and rendering for TrackTales."""

import asyncio
import logging
from typing import Any

import pandas as pd
from nicegui import ui

from app_state import get_distance_unit, get_elevation_unit, state
from i18n import get_language, t
from logic.workout_manager import (
    HALF_MARATHON_DISTANCE_M,
    MARATHON_DISTANCE_M,
    STANDARD_SEGMENT_DISTANCES,
)
from ui.charts import LABEL_UPPERCASE_CLASSES, ROW_CENTERED_CLASSES
from ui.css import (
    LABEL_EMPTY_STATE_CLASSES,
    ROW_LOADING_CLASSES,
    TABLE_FULL_CLASSES,
)
from ui.helpers import format_date_label, format_distance_label, format_duration_label
from ui.workout_detail_modal import create_workout_detail_modal
from ui.workout_table import _build_workout_rows
from units import METERS_TO_FEET, METERS_TO_MILES

_logger = logging.getLogger(__name__)


#: Power confidence metadata used to choose an icon and tooltip for each row.
_CONFIDENCE_META: dict[str, dict[str, str]] = {
    "measured": {
        "icon": "sensors",
        "tooltip_key": "Measured from segment samples",
    },
    "overlap_estimated": {
        "icon": "insights",
        "tooltip_key": "Estimated from overlapping power intervals",
    },
    "workout_fallback": {
        "icon": "directions_run",
        "tooltip_key": "Using workout average power fallback",
    },
    "missing": {
        "icon": "help_outline",
        "tooltip_key": "No matching power data",
    },
}


def _register_confidence_translations() -> None:
    """Register confidence tooltip strings for Babel extraction.

    These msgids are referenced via ``_CONFIDENCE_META[...]["tooltip_key"]``
    and would otherwise be missed by ``pybabel extract``.
    """
    t("Measured from segment samples")
    t("Estimated from overlapping power intervals")
    t("Using workout average power fallback")
    t("No matching power data")


_register_confidence_translations()


def _resolve_confidence_key(power_w: Any, power_confidence: Any) -> str:
    """Return the confidence metadata key for *power_confidence* / *power_w*."""
    if power_confidence in _CONFIDENCE_META:
        return str(power_confidence)
    if power_w is not None and not pd.isna(power_w):
        return "measured"
    return "missing"


def _format_speed(distance_m: float, duration_s: float, distance_unit: str) -> str:
    """Return a formatted average speed string for the segment."""
    if duration_s <= 0:
        speed = 0.0
    elif distance_unit == "mi":
        speed = (distance_m * METERS_TO_MILES) / (duration_s / 3600)
    else:
        speed = (distance_m / 1000) / (duration_s / 3600)
    unit_label = "mi/h" if distance_unit == "mi" else "km/h"
    return f"{speed:.2f} {unit_label}"


def _format_elevation(elevation_change_m: float, elevation_unit: str) -> str:
    """Return a formatted elevation change string."""
    if elevation_unit == "ft":
        return f"{elevation_change_m * METERS_TO_FEET:.1f} ft"
    return f"{elevation_change_m:.1f} m"


def _format_segment_entry(
    distance_m: float,
    duration_s: float,
    elevation_change_m: float,
    start_date: Any,
    power_w: Any,
    power_confidence: Any,
    language_code: str,
    distance_unit: str,
    elevation_unit: str,
) -> dict[str, str | float | None]:
    """Format a single segment record into a display dictionary."""
    avg_power_str = (
        f"{float(power_w):.0f} W" if power_w is not None and not pd.isna(power_w) else "–"
    )
    confidence_key = _resolve_confidence_key(power_w, power_confidence)
    confidence_cfg = _CONFIDENCE_META[confidence_key]
    workout_ts: float | None = (
        float(start_date.timestamp()) if isinstance(start_date, pd.Timestamp) else None
    )
    return {
        "distance": format_distance_label(
            distance_m,
            language_code,
            HALF_MARATHON_DISTANCE_M,
            MARATHON_DISTANCE_M,
            distance_unit,
        ),
        "duration": format_duration_label(duration_s),
        "elevation_change": _format_elevation(elevation_change_m, elevation_unit),
        "average_speed": _format_speed(distance_m, duration_s, distance_unit),
        "avg_power": avg_power_str,
        "avg_power_confidence_icon": str(confidence_cfg["icon"]),
        "avg_power_confidence_tooltip": t(confidence_cfg["tooltip_key"]),
        "start_date": format_date_label(start_date, language_code),
        "workout_ts": workout_ts,
    }


def _build_distance_group_row(
    records: list[Any],
    language_code: str,
    distance_unit: str,
    elevation_unit: str,
) -> dict[str, Any] | None:
    """Build a parent row with children for one distance group."""
    if not records:
        return None

    start_date = getattr(records[0], "startDate", None)
    if start_date is None:
        return None

    distance_m = float(getattr(records[0], "distance", 0.0))
    kwargs = {
        "language_code": language_code,
        "distance_unit": distance_unit,
        "elevation_unit": elevation_unit,
    }

    children = [
        _format_segment_entry(
            distance_m,
            float(getattr(rec, "duration_s", 0.0)),
            float(getattr(rec, "elevation_change_m", 0.0)),
            getattr(rec, "startDate"),
            getattr(rec, "segment_avg_power", None),
            getattr(rec, "segment_power_confidence", None),
            **kwargs,
        )
        for rec in records[1:]
        if getattr(rec, "startDate", None) is not None
    ]

    return {
        **_format_segment_entry(
            distance_m,
            float(getattr(records[0], "duration_s", 0.0)),
            float(getattr(records[0], "elevation_change_m", 0.0)),
            start_date,
            getattr(records[0], "segment_avg_power", None),
            getattr(records[0], "segment_power_confidence", None),
            **kwargs,
        ),
        "id": str(int(distance_m)),
        "children": children,
    }


def _build_best_segments_rows() -> list[dict[str, Any]]:
    """Compute and format best segments rows for tab rendering.

    Returns one row per distance (the #1 record). Runner-up records are stored
    in a ``children`` list so the table can expand them on demand.
    """
    _logger.debug("Calculating best segments for distances: %s", STANDARD_SEGMENT_DISTANCES)
    best_segments = state.workouts.get_best_segments(
        distances=STANDARD_SEGMENT_DISTANCES,
        start_date=state.start_date,
        end_date=state.end_date,
    )
    _logger.debug("Best segments data:\n%s", best_segments)

    running_power_df = state.records_by_type.get("RunningPower")
    annotated = state.workouts.annotate_segments_with_power(best_segments, running_power_df)

    language_code = get_language()
    distance_unit = get_distance_unit()
    elevation_unit = get_elevation_unit()

    rows: list[dict[str, Any]] = []
    for _, group_df in annotated.groupby("distance", sort=True):
        records = list(group_df.sort_values("duration_s").itertuples(index=False))
        row = _build_distance_group_row(records, language_code, distance_unit, elevation_unit)
        if row is not None:
            rows.append(row)

    return rows


async def load_best_segments_data(force: bool = False) -> None:
    """Load best segments asynchronously for the tab, with concurrency guard."""
    if state.best_segments_loading:
        return
    if state.best_segments_loaded and not force:
        return
    if not state.file_loaded:
        return

    state.best_segments_loading = True
    render_best_segments_tab.refresh()

    try:
        rows = await asyncio.to_thread(_build_best_segments_rows)
        state.best_segments_rows = rows
        state.best_segments_loaded = True
    except Exception:
        _logger.exception("Failed to load best segments data")
    finally:
        state.best_segments_loading = False
        render_best_segments_tab.refresh()


@ui.refreshable
def render_best_segments_tab() -> None:
    """Render the best segments for standard running distances in a table format."""
    with ui.card().classes(ROW_CENTERED_CLASSES):
        ui.label(t("Best segments for standard running distances")).classes(LABEL_UPPERCASE_CLASSES)
        columns = [
            {"name": "distance", "label": t("Distance"), "field": "distance"},
            {"name": "duration", "label": t("Duration"), "field": "duration"},
            {
                "name": "elevation_change",
                "label": t("Elevation Change"),
                "field": "elevation_change",
            },
            {
                "name": "average_speed",
                "label": t("Average Speed"),
                "field": "average_speed",
            },
            {"name": "avg_power", "label": t("Avg Power"), "field": "avg_power"},
            {"name": "start_date", "label": t("Date"), "field": "start_date"},
            {"name": "actions", "label": "", "field": "workout_ts"},
        ]

        if state.best_segments_loading:
            with ui.row().classes(ROW_LOADING_CLASSES):
                ui.spinner(size="lg")
                ui.label(t("Loading best segments..."))
            return

        if not state.best_segments_loaded:
            ui.label(t("Open this tab to load best segments.")).classes(LABEL_EMPTY_STATE_CLASSES)
            return

        _logger.debug("Table rendered with %d rows", len(state.best_segments_rows))
        details_tooltip = t("Details")
        # Lazy cache: populated on the first open_segment_detail event so that
        # _build_workout_rows and create_workout_detail_modal are not executed on
        # every tab refresh (they iterate all workouts, which is expensive).
        _lazy: dict[str, Any] = {}
        table = ui.table(
            columns=columns,
            rows=state.best_segments_rows,
            row_key="id",
        ).classes(TABLE_FULL_CLASSES)
        table.add_slot(
            "header",
            r"""
            <q-tr :props="props">
                <q-th auto-width />
                <q-th v-for="col in props.cols" :key="col.name" :props="props">
                    {{ col.label }}
                </q-th>
            </q-tr>
            """,
        )
        table.add_slot(
            "body",
            r"""
            <q-tr :props="props">
                <q-td auto-width>
                    <q-btn
                        v-if="props.row.children && props.row.children.length"
                        size="sm" flat round dense
                        @click="props.expand = !props.expand"
                        :icon="props.expand ? 'expand_less' : 'expand_more'" />
                    <span v-else class="expand-placeholder" />
                </q-td>
                <q-td v-for="col in props.cols" :key="col.name" :props="props">
                    <template v-if="col.name === 'avg_power'">
                        {{ col.value }}
                        <q-icon
                            v-if="props.row.avg_power_confidence_icon"
                            :name="props.row.avg_power_confidence_icon"
                            size="14px"
                            class="q-ml-xs"
                        >
                            <q-tooltip>{{ props.row.avg_power_confidence_tooltip }}</q-tooltip>
                        </q-icon>
                    </template>
                    <template v-else-if="col.name === 'actions'">
                        <q-btn
                            v-if="props.row.workout_ts != null"
"""
            + f'            flat round dense icon="info" aria-label="{details_tooltip}"'
            + r"""
                            @click="$parent.$emit('open_segment_detail', props.row.workout_ts)">
"""
            + f"            <q-tooltip>{details_tooltip}</q-tooltip>"
            + r"""
                        </q-btn>
                    </template>
                    <template v-else>
                        {{ col.value }}
                    </template>
                </q-td>
            </q-tr>
            <q-tr v-show="props.expand" :props="props">
                <q-td colspan="100%" class="segment-child-row">
                    <q-list dense>
                        <q-item v-for="(child, i) in props.row.children" :key="i">
                            <q-item-section>
                                <span class="text-caption text-white-9">
                                    #{{ i + 2 }}&nbsp;&nbsp;
                                    {{ child.duration }}&nbsp;&nbsp;
                                    {{ child.elevation_change }}&nbsp;&nbsp;
                                    {{ child.average_speed }}&nbsp;&nbsp;
                                    {{ child.avg_power }}&nbsp;&nbsp;
                                    <q-icon
                                        v-if="child.avg_power_confidence_icon"
                                        :name="child.avg_power_confidence_icon"
                                        size="12px"
                                    >
                                            <q-tooltip>
                                                {{ child.avg_power_confidence_tooltip }}
                                            </q-tooltip>
                                    </q-icon>
                                    &nbsp;&nbsp;
                                    {{ child.start_date }}
"""
            + r"""
                                    <q-btn
                                        v-if="child.workout_ts != null"
"""
            + f' flat round dense size="sm" icon="info" aria-label="{details_tooltip}"'
            + r"""
@click="$parent.$emit('open_segment_detail', child.workout_ts)">
"""
            + f"<q-tooltip>{details_tooltip}</q-tooltip>"
            + r"""
                                    </q-btn>
                                </span>
                            </q-item-section>
                        </q-item>
                    </q-list>
                </q-td>
            </q-tr>
            """,
        )

        def _handle_open_segment_detail(event: Any) -> None:
            if "open_detail" not in _lazy:
                full_rows = _build_workout_rows(activity_type="Running", skip_range_filters=True)
                _lazy["open_detail"] = create_workout_detail_modal(full_rows)
                _lazy["row_index"] = {
                    row["date_sort"]: idx
                    for idx, row in enumerate(full_rows)
                    if isinstance(row.get("date_sort"), float)
                }
            ts = float(event.args)
            row_index = _lazy["row_index"].get(ts)
            if row_index is not None:
                _lazy["open_detail"](row_index)

        table.on("open_segment_detail", _handle_open_segment_detail)

