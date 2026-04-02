"""Best-segments loading and rendering for Apple Health Analyzer."""

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

_logger = logging.getLogger(__name__)


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

    # Annotate with per-segment average power from individual RunningPower records,
    # falling back to workout-level statistics when segment power cannot be derived
    # from those records.
    running_power_df = state.records_by_type.get("RunningPower")
    annotated = state.workouts.annotate_segments_with_power(best_segments, running_power_df)

    language_code = get_language()
    distance_unit = get_distance_unit()
    elevation_unit = get_elevation_unit()
    confidence_meta = {
        "measured": {
            "icon": "sensors",
            "tooltip": t("Measured from segment samples"),
        },
        "overlap_estimated": {
            "icon": "insights",
            "tooltip": t("Estimated from overlapping power intervals"),
        },
        "workout_fallback": {
            "icon": "directions_run",
            "tooltip": t("Using workout average power fallback"),
        },
        "missing": {
            "icon": "help_outline",
            "tooltip": t("No matching power data"),
        },
    }

    def _format_entry(
        distance_m: float,
        duration_s: float,
        elevation_change_m: float,
        start_date: Any,
        power_w: Any,
        power_confidence: Any,
    ) -> dict[str, str]:
        if distance_unit == "mi":
            average_speed = (distance_m / 1609.34) / (duration_s / 3600) if duration_s > 0 else 0.0
            speed_str = f"{average_speed:.2f} mi/h"
        else:
            average_speed = (distance_m / 1000) / (duration_s / 3600) if duration_s > 0 else 0.0
            speed_str = f"{average_speed:.2f} km/h"
        avg_power_str = (
            f"{float(power_w):.0f} W" if power_w is not None and not pd.isna(power_w) else "–"
        )
        if power_confidence in confidence_meta:
            confidence_key = str(power_confidence)
        elif power_w is not None and not pd.isna(power_w):
            confidence_key = "measured"
        else:
            confidence_key = "missing"
        confidence_cfg = confidence_meta[confidence_key]
        if elevation_unit == "ft":
            elevation_display = f"{elevation_change_m / 0.3048:.1f} ft"
        else:
            elevation_display = f"{elevation_change_m:.1f} m"
        return {
            "distance": format_distance_label(
                distance_m,
                language_code,
                HALF_MARATHON_DISTANCE_M,
                MARATHON_DISTANCE_M,
                distance_unit,
            ),
            "duration": format_duration_label(duration_s),
            "elevation_change": elevation_display,
            "average_speed": speed_str,
            "avg_power": avg_power_str,
            "avg_power_confidence_icon": str(confidence_cfg["icon"]),
            "avg_power_confidence_tooltip": str(confidence_cfg["tooltip"]),
            "start_date": format_date_label(start_date, language_code),
        }

    rows: list[dict[str, Any]] = []
    for _, group_df in annotated.groupby("distance", sort=True):
        records = list(group_df.sort_values("duration_s").itertuples(index=False))
        if not records:
            continue

        distance_m = float(getattr(records[0], "distance", 0.0))
        elevation_change_m = float(getattr(records[0], "elevation_change_m", 0.0))
        start_date = getattr(records[0], "startDate", None)
        if start_date is None:
            continue

        power_w = getattr(records[0], "segment_avg_power", None)
        power_confidence = getattr(records[0], "segment_power_confidence", None)
        parent: dict[str, Any] = {
            **_format_entry(
                distance_m,
                float(getattr(records[0], "duration_s", 0.0)),
                elevation_change_m,
                start_date,
                power_w,
                power_confidence,
            ),
            "id": str(int(distance_m)),
            "children": [
                _format_entry(
                    distance_m,
                    float(getattr(record, "duration_s", 0.0)),
                    float(getattr(record, "elevation_change_m", 0.0)),
                    getattr(record, "startDate"),
                    getattr(record, "segment_avg_power", None),
                    getattr(record, "segment_power_confidence", None),
                )
                for record in records[1:]
                if getattr(record, "startDate", None) is not None
            ],
        }
        rows.append(parent)

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
                                </span>
                            </q-item-section>
                        </q-item>
                    </q-list>
                </q-td>
            </q-tr>
            """,
        )
