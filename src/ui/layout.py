"""UI layout components for Apple Health Analyzer application."""

import asyncio
import logging
import math
import time
from collections.abc import Callable
from typing import Any, cast

import pandas as pd
from nicegui import app, ui

from app_state import (
    UNIT_SYSTEMS,
    get_distance_unit,
    get_elevation_unit,
    get_unit_system,
    get_weight_unit,
    state,
)
from assets import APP_ICON_BASE64
from i18n import LANGUAGES, get_language, t
from i18n.activity_types import build_activity_select_options
from logic.export_parser import ExportParser
from logic.records_by_type import RecordsByType
from logic.workout_manager import WorkoutManager
from ui.activities_tab import render_activity_graphs
from ui.best_segments import load_best_segments_data, render_best_segments_tab
from ui.charts import (
    stat_card,
)
from ui.css import (
    APP_LOGO_CLASSES,
    APP_TITLE_CLASSES,
    BUTTON_FLAT_ROUND_PROPS,
    DATE_ROW_CLASSES,
    HEADER_CLASSES,
    INPUT_GROW_CLASSES,
    INPUT_MEDIUM_CLASSES,
    INPUT_SMALL_CLASSES,
    LABEL_MUTED_CLASSES,
    LABEL_SECTION_CLASSES,
    PREF_MENU_ITEM_CLASSES,
    PREF_SECTION_LABEL_CLASSES,
    RANGE_SELECTORS_ROW_CLASSES,
    ROW_CENTERED_CLASSES,
    ROW_FULL_ITEMS_CLASSES,
    TABS_FULL_CLASSES,
)
from ui.health_data_tab import render_health_data_tab
from ui.helpers import (
    format_date_label,
    format_duration_label,
    format_float,
    format_hours_minutes_from_seconds,
    format_integer,
    parse_float,
    qdate_locale_json,
    translate_parser_progress_message,
)
from ui.local_file_picker import LocalFilePicker
from ui.running_tab import render_running_tab
from ui.statistics_tab import render_statistics_tab
from ui.trends_tab import render_trends_graphs, render_trends_tab
from ui.workout_detail_modal import create_workout_detail_modal
from ui.workout_table import (
    _build_workout_rows,
    render_distance_range_selector,
    render_duration_range_selector,
    render_workout_table,
)
from units import KG_TO_LBS

# Get logger for this module
_logger = logging.getLogger(__name__)


def schedule_best_segments_load(force: bool = False) -> None:
    """Schedule best-segments loading and keep a reference to the task."""

    def _clear_completed_task(task: asyncio.Task[None]) -> None:
        if state.best_segments_task is task:
            state.best_segments_task = None

    task: Any = asyncio.create_task(load_best_segments_data(force=force))
    state.best_segments_task = task if hasattr(task, "add_done_callback") else None
    if state.best_segments_task is not None:
        state.best_segments_task.add_done_callback(_clear_completed_task)


def schedule_health_data_load(force: bool = False) -> None:
    """Schedule health-data loading and keep a reference to the task."""

    def _clear_completed_task(task: asyncio.Task[None]) -> None:
        if state.health_data_task is task:
            state.health_data_task = None

    task: Any = asyncio.create_task(load_health_data(force=force))
    state.health_data_task = task if hasattr(task, "add_done_callback") else None
    if state.health_data_task is not None:
        state.health_data_task.add_done_callback(_clear_completed_task)


def _migrate_legacy_tab_name(tab_name: str) -> str:
    """Map persisted legacy tab identifiers to the current tab names."""
    return "running" if tab_name == "best_segments" else tab_name


def _to_json_safe(d: dict[Any, Any]) -> dict[str, float | int | None]:
    """Replace pd.NA/NaN with None for JSON-safe chart data."""
    result: dict[str, float | int | None] = {}
    for key, value in d.items():
        normalized_key = str(key)
        if value is None:
            result[normalized_key] = None
        elif isinstance(value, float) and pd.isna(value):
            result[normalized_key] = None
        elif isinstance(value, (int, float)):
            result[normalized_key] = value
        else:
            result[normalized_key] = None
    return result


def _build_fast_health_graphs() -> dict[str, dict[str, float | int | None]]:
    """Build chart series for fast health graphs (resting HR, body mass, VO2 max)."""
    resting_heart_rate_stats = state.records_by_type.resting_heart_rate_stats(
        period=state.trends_period,
        start_date=state.start_date,
        end_date=state.end_date,
    )
    body_mass_stats = state.records_by_type.weight_stats(
        period=state.trends_period,
        start_date=state.start_date,
        end_date=state.end_date,
    )
    vo2_max_stats = state.records_by_type.vo2_max_stats(
        period=state.trends_period,
        start_date=state.start_date,
        end_date=state.end_date,
    )

    # Apple Health stores body mass in kg; convert to lbs when the user prefers imperial weight.
    weight_factor = KG_TO_LBS if get_weight_unit() == "lbs" else 1.0
    body_mass_series = body_mass_stats.assign(
        period=body_mass_stats["period"].astype(str),
        avg=body_mass_stats["avg"] * weight_factor,
    )

    return {
        "heart_rate": _to_json_safe(
            resting_heart_rate_stats.assign(period=resting_heart_rate_stats["period"].astype(str))
            .set_index("period")["avg"]
            .to_dict()
        ),
        "body_mass": _to_json_safe(body_mass_series.set_index("period")["avg"].to_dict()),
        "vo2_max": _to_json_safe(
            vo2_max_stats.assign(period=vo2_max_stats["period"].astype(str))
            .set_index("period")["avg"]
            .to_dict()
        ),
    }


def _build_cp_graphs() -> dict[str, dict[str, float | int | None]]:
    """Build chart series for the slow CP/W' graphs (critical power evolution)."""
    cp_evolution = state.workouts.get_critical_power_evolution(
        running_power_df=state.records_by_type.get("RunningPower"),
        period=state.trends_period,
        start_date=state.start_date,
        end_date=state.end_date,
    )
    return {
        "critical_power": _to_json_safe(
            {}
            if cp_evolution.empty
            else cp_evolution.set_index("period")["critical_power_w"].to_dict()
        ),
        "w_prime": _to_json_safe(
            {} if cp_evolution.empty else cp_evolution.set_index("period")["w_prime_kj"].to_dict()
        ),
    }


async def load_health_data(force: bool = False) -> None:
    """Load health data asynchronously for the tab, with concurrency guard.

    Uses two phases so fast graphs (HR, body mass, VO2 max) are displayed
    immediately while the slower CP/W' computation runs in the background.
    """
    if state.health_data_loading:
        return
    if state.health_data_loaded and not force:
        return
    if not state.file_loaded:
        return

    state.health_data_loading = True
    render_health_data_tab.refresh()

    try:
        # Phase 1 — fast graphs: HR, body mass, VO2 max
        fast_graphs = await asyncio.to_thread(_build_fast_health_graphs)
        state.health_data_graphs.update(fast_graphs)
        state.health_data_loaded = True
        state.health_data_loading = False
        state.health_data_cp_loading = True
        render_health_data_tab.refresh()

        # Phase 2 — slow graphs: critical power and W'
        try:
            cp_graphs = await asyncio.to_thread(_build_cp_graphs)
            state.health_data_graphs.update(cp_graphs)
        except Exception:
            _logger.exception("Failed to load critical power graphs")
        finally:
            state.health_data_cp_loading = False
            render_health_data_tab.refresh()
    except Exception:
        _logger.exception("Failed to load health data tab")
        state.health_data_loading = False
        state.health_data_cp_loading = False
        render_health_data_tab.refresh()


def handle_json_export() -> None:
    """Handle exporting data to JSON format."""
    json_data = state.workouts.export_to_json(
        activity_type=state.selected_activity_type,
        start_date=state.start_date,
        end_date=state.end_date,
    )
    ui.download(json_data.encode("utf-8"), "apple_health_export.json")


def handle_csv_export() -> None:
    """Handle exporting data to CSV format."""
    csv_data = state.workouts.export_to_csv(
        activity_type=state.selected_activity_type,
        start_date=state.start_date,
        end_date=state.end_date,
    )
    ui.download(csv_data.encode("utf-8"), "apple_health_export.csv")


def _refresh_summary_metrics() -> None:
    """Refresh global summary metrics and their display values."""
    dist_unit = get_distance_unit()
    elev_unit = get_elevation_unit()
    metrics: dict[str, int | float] = state.metrics
    metrics_display: dict[str, str] = state.metrics_display
    metrics["count"] = state.workouts.get_count(
        state.selected_activity_type, state.start_date, state.end_date
    )
    metrics["distance"] = state.workouts.get_total_distance(
        state.selected_activity_type,
        unit=dist_unit,
        start_date=state.start_date,
        end_date=state.end_date,
    )
    metrics["duration"] = state.workouts.get_total_duration(
        state.selected_activity_type, start_date=state.start_date, end_date=state.end_date
    )
    metrics["elevation"] = state.workouts.get_total_elevation(
        state.selected_activity_type,
        unit=elev_unit,
        start_date=state.start_date,
        end_date=state.end_date,
    )
    metrics["calories"] = state.workouts.get_total_calories(
        state.selected_activity_type, start_date=state.start_date, end_date=state.end_date
    )

    metrics_display["count"] = format_integer(cast(int, metrics["count"]))
    metrics_display["distance"] = format_integer(cast(int, metrics["distance"]))
    metrics_display["duration"] = format_integer(cast(int, metrics["duration"]))
    metrics_display["elevation"] = format_integer(cast(int, metrics["elevation"]))
    metrics_display["calories"] = format_integer(cast(int, metrics["calories"]))


def _set_longest_metric_from_details(
    metric_key: str,
    details: dict[str, Any] | None,
    language_code: str,
    details_value_key: str = "distance",
    value_divisor: float = 1.0,
    decimal_places: int = 1,
    round_to_int: bool = False,
    display_as_hours_minutes: bool = False,
) -> None:
    """Set one personal-record metric display/tooltip from details."""
    metrics: dict[str, int | float] = state.metrics  # type: ignore[assignment]
    metrics_display: dict[str, str] = state.metrics_display  # type: ignore[assignment]
    metrics_tooltip: dict[str, str] = state.metrics_tooltip  # type: ignore[assignment]
    metrics_workout_index: dict[str, object | None] = state.metrics_workout_index
    metrics[metric_key] = 0.0
    metrics_display[metric_key] = format_float(0.0)
    metrics_workout_index[metric_key] = None

    if details is None:
        metrics_tooltip[metric_key] = t("No data")
        return

    if value_divisor == 0:
        raise ValueError(f"value_divisor must not be zero for metric '{metric_key}'")

    value_float = parse_float(details.get(details_value_key)) or 0.0
    value_for_display = value_float / value_divisor
    metrics_workout_index[metric_key] = details.get("workout_index")

    if display_as_hours_minutes:
        metrics[metric_key] = value_float
        metrics_display[metric_key] = format_hours_minutes_from_seconds(value_float)
    elif round_to_int:
        rounded_value = int(round(value_for_display))
        metrics[metric_key] = rounded_value
        metrics_display[metric_key] = format_integer(rounded_value)
    else:
        metrics[metric_key] = value_for_display
        metrics_display[metric_key] = format_float(value_for_display, decimal_places=decimal_places)

    date_value = details.get("date")
    date_str = format_date_label(date_value, language_code) if date_value is not None else None
    duration_float = parse_float(details.get("duration"))
    duration_str = format_duration_label(duration_float) if duration_float is not None else None

    if date_str:
        metrics_tooltip[metric_key] = date_str
    elif duration_str:
        metrics_tooltip[metric_key] = duration_str
    else:
        metrics_tooltip[metric_key] = t("No data")


def _refresh_longest_workout_metrics() -> None:
    """Refresh overview personal-record metrics and tooltips."""
    language_code = get_language()
    dist_unit = get_distance_unit()
    elev_unit = get_elevation_unit()
    metric_configs: list[dict[str, Any]] = [
        {"key": "longest_run", "activities": ["Running"], "column": "distance", "unit": dist_unit},
        {
            "key": "longest_walk",
            "activities": ["Walking", "Hiking"],
            "column": "distance",
            "unit": dist_unit,
        },
        {
            "key": "longest_cycling",
            "activities": ["Cycling"],
            "column": "distance",
            "unit": dist_unit,
        },
        {
            "key": "longest_swim",
            "activities": ["Swimming"],
            "column": "distance",
            "unit": dist_unit,
            "decimal_places": 2,
        },
        {
            "key": "most_elevation_run",
            "activities": ["Running"],
            "column": "ElevationAscended",
            "unit": elev_unit,
        },
        {
            "key": "most_elevation_walk",
            "activities": ["Walking", "Hiking"],
            "column": "ElevationAscended",
            "unit": elev_unit,
        },
        {
            "key": "longest_duration_workout",
            "activities": None,
            "column": "duration",
            "display_as_hours_minutes": True,
        },
        {
            "key": "most_calories_workout",
            "activities": None,
            "column": "sumActiveEnergyBurned",
            "round_to_int": True,
        },
    ]

    for config in metric_configs:
        details = state.workouts.get_workout_record_details(
            metric_column=config["column"],
            activity_types=config["activities"],
            unit=config.get("unit"),
            start_date=state.start_date,
            end_date=state.end_date,
        )
        _set_longest_metric_from_details(
            config["key"],
            details,
            language_code,
            details_value_key="value",
            value_divisor=config.get("value_divisor", 1.0),
            decimal_places=config.get("decimal_places", 1),
            round_to_int=config.get("round_to_int", False),
            display_as_hours_minutes=config.get("display_as_hours_minutes", False),
        )


def _reset_best_segments_state() -> None:
    """Invalidate cached best-segments data and cancel stale in-flight loads."""
    best_segments_task: Any = getattr(state, "best_segments_task", None)
    if isinstance(best_segments_task, asyncio.Task) and not best_segments_task.done():
        best_segments_task.cancel()

    state.best_segments_task = None
    if hasattr(state, "best_segments_loading"):
        state.best_segments_loading = False
    state.best_segments_rows = []
    state.best_segments_loaded = False


def _reset_health_data_state() -> None:
    """Invalidate cached health-data graphs and cancel stale in-flight loads."""
    health_data_task: Any = getattr(state, "health_data_task", None)
    if isinstance(health_data_task, asyncio.Task) and not health_data_task.done():
        health_data_task.cancel()

    state.health_data_task = None
    state.health_data_loading = False
    state.health_data_loaded = False
    state.health_data_cp_loading = False
    state.health_data_graphs = {
        "heart_rate": {},
        "body_mass": {},
        "vo2_max": {},
        "critical_power": {},
        "w_prime": {},
    }


def refresh_data() -> None:
    """Refresh the displayed data."""
    _logger.info(
        "Refreshing data: activity_type=%s, start_date=%s, end_date=%s",
        state.selected_activity_type,
        state.start_date,
        state.end_date,
    )

    _refresh_summary_metrics()
    _refresh_longest_workout_metrics()
    _reset_best_segments_state()
    _reset_health_data_state()

    # Reset range filter bounds to match the current activity/date filtered dataset so
    # sliders always show a meaningful range and start fully open after a filter change.
    # Values are stored in the user's preferred distance unit.
    dist_unit = get_distance_unit()
    dist_min, dist_max = state.workouts.get_distance_bounds(
        unit=dist_unit,
        activity_type=state.selected_activity_type,
        start_date=state.start_date,
        end_date=state.end_date,
    )
    state.distance_range = {"min": math.floor(dist_min), "max": math.ceil(dist_max)}
    dur_min, dur_max = state.workouts.get_duration_bounds(
        activity_type=state.selected_activity_type,
        start_date=state.start_date,
        end_date=state.end_date,
    )
    state.duration_range_min = {"min": math.floor(dur_min), "max": math.ceil(dur_max)}

    render_activity_graphs.refresh()
    render_trends_graphs.refresh()
    render_health_data_tab.refresh()
    render_running_tab.refresh()
    render_statistics_tab.refresh()
    render_best_segments_tab.refresh()
    render_distance_range_selector.refresh()
    render_duration_range_selector.refresh()
    render_workout_table.refresh()

    # If user is already on the tab, load asynchronously after invalidation.
    if state.selected_main_tab == "running":
        schedule_best_segments_load()
        schedule_health_data_load()
    if state.selected_main_tab == "health_data":
        schedule_health_data_load()


@ui.refreshable
def render_activity_select() -> None:
    """Render the activity type selection dropdown."""

    ui.select(
        options=build_activity_select_options(state.activity_options),
        on_change=refresh_data,
        value=state.selected_activity_type,
        label=t("Activity Type"),
    ).classes(INPUT_SMALL_CLASSES).bind_enabled_from(state, "file_loaded").bind_value(
        state, "selected_activity_type"
    )


def render_period_selector() -> None:
    """Render the aggregate-by-period radio button selector."""

    def _on_period_change() -> None:
        _reset_health_data_state()
        render_trends_graphs.refresh()
        render_health_data_tab.refresh()
        render_running_tab.refresh()
        if state.selected_main_tab in {"health_data", "running"}:
            schedule_health_data_load()

    ui.label(t("Aggregate by:")).classes(LABEL_SECTION_CLASSES)
    ui.radio(
        {
            "W": t("Week"),
            "M": t("Month"),
            "Q": t("Quarter"),
            "Y": t("Year"),
        },
        on_change=_on_period_change,
    ).bind_value(state, "trends_period").props("inline")


def render_left_drawer() -> None:
    """Generate the left drawer with filters."""

    with ui.left_drawer().props("width=330"):
        ui.label(t("Activities"))
        render_activity_select()

        ui.separator()

        render_date_range_selector()

        ui.separator()

        render_period_selector()

        ui.separator()
        with ui.dropdown_button(t("Export data"), icon="download").bind_enabled_from(
            state, "file_loaded"
        ):
            ui.button(t("to JSON"), on_click=handle_json_export).props("flat").classes("w-full")
            ui.button(t("to CSV"), on_click=handle_csv_export).props("flat").classes("w-full")


@ui.refreshable
def render_date_range_selector() -> None:
    """Render the date range selector with linked input and date picker."""
    with ui.row().classes(DATE_ROW_CLASSES):
        min_date, max_date = state.workouts.get_date_bounds()
        date_locale = qdate_locale_json(get_language())

        date_input = (
            ui.input(t("Date range"))
            .classes(INPUT_MEDIUM_CLASSES)
            .bind_enabled_from(state, "file_loaded")
            .bind_value(state, "date_range_text")
            .props("clearable")
        )
        ui.date(
            on_change=refresh_data,
        ).props(
            f'range default-year-month="{max_date[:7]}" '
            f":locale='{date_locale}' "
            f''':options="date => date >= '{min_date}' && date <= '{max_date}'"'''
        ).bind_value(
            date_input,
            forward=lambda x: (
                f"{x['from']} - {x['to']}" if isinstance(x, dict) and "from" in x else str(x or "")  # type: ignore[arg-type]
            ),
            backward=lambda x: (
                {
                    "from": x.split(" - ")[0],
                    "to": x.split(" - ")[1],
                }
                if " - " in (x or "")
                else None
            ),
        ).bind_enabled_from(state, "file_loaded")


def _change_language(language_code: str) -> None:
    """Store the selected language and refresh translated UI in place."""
    app.storage.user["language"] = language_code
    _logger.info("Language changed to '%s', reloading page.", language_code)
    # NiceGUI top-level layout elements (header/drawer/body containers) cannot be
    # nested in refreshable containers. Reloading ensures all translated UI text updates.
    ui.navigate.reload()


def _refresh_loaded_data_for_unit_change() -> None:
    """Recompute cached derived data so unit labels and values stay in sync."""
    if not state.file_loaded:
        return

    refresh_data()


def _change_unit_system(system: str) -> None:
    """Store the selected unit system and reload the page."""
    app.storage.user["unit_system"] = system
    _refresh_loaded_data_for_unit_change()
    _logger.info("Unit system changed to '%s', reloading page.", system)
    ui.navigate.reload()


def render_header() -> None:
    """Generate the application header with a dark mode toggle and preferences menu."""
    dark = ui.dark_mode()

    # Sync initial dark-mode state (browser may have remembered the preference).
    state.dark_mode_enabled = bool(dark.value)

    def _enable_dark() -> None:
        dark.enable()
        state.dark_mode_enabled = True
        render_activity_graphs.refresh()
        render_trends_graphs.refresh()
        render_health_data_tab.refresh()

    def _disable_dark() -> None:
        dark.disable()
        state.dark_mode_enabled = False
        render_activity_graphs.refresh()
        render_trends_graphs.refresh()
        render_health_data_tab.refresh()

    with ui.header().classes(HEADER_CLASSES):
        ui.image(APP_ICON_BASE64).classes(APP_LOGO_CLASSES)
        ui.label(t("Apple Health Analyzer")).classes(APP_TITLE_CLASSES)

        # Toggle button with dynamic icon
        ui.button(icon="dark_mode", on_click=_enable_dark).bind_visibility_from(
            dark, "value", backward=lambda v: not v
        ).props(BUTTON_FLAT_ROUND_PROPS)
        ui.button(icon="light_mode", on_click=_disable_dark).bind_visibility_from(
            dark, "value"
        ).props(BUTTON_FLAT_ROUND_PROPS)

        # Preferences menu (language + unit system)
        current_language = get_language()
        current_system = get_unit_system()
        with ui.button(icon="tune").props(BUTTON_FLAT_ROUND_PROPS):
            with ui.menu():
                ui.label(t("Language")).classes(PREF_SECTION_LABEL_CLASSES)
                for code, name in LANGUAGES.items():
                    ui.menu_item(
                        f"{'✓ ' if code == current_language else ''}{name}",
                        on_click=lambda _event, c=code: _change_language(c),
                    ).classes(PREF_MENU_ITEM_CLASSES)
                ui.separator()
                ui.label(t("Units")).classes(PREF_SECTION_LABEL_CLASSES)
                for system_code, system_label in UNIT_SYSTEMS.items():
                    ui.menu_item(
                        f"{'✓ ' if system_code == current_system else ''}{t(system_label)}",
                        on_click=lambda _event, s=system_code: _change_unit_system(s),
                    ).classes(PREF_MENU_ITEM_CLASSES)


async def pick_file() -> None:
    """Open a file picker dialog to select the Apple Health export file."""
    result: list[str] = await LocalFilePicker("~", multiple=False, file_filter=".zip")

    if not result:
        ui.notify(t("No file selected"))
        return

    state.input_file.value = result[0]


def load_workouts_from_file(
    file_path: str,
    progress_callback: Callable[[int, str], None] | None = None,
) -> tuple[WorkoutManager, list[str], RecordsByType]:
    """Load and parse the Apple Health export file.

    Returns a tuple of (WorkoutManager, activity_options, records_by_type) so that all UI
    state mutations and refresh calls can be performed on the event-loop
    thread by the caller (load_file), avoiding thread-safety issues.
    """

    def report(progress: int, message: str) -> None:
        localized_message = translate_parser_progress_message(message, get_language())
        _logger.info(localized_message)
        if progress_callback:
            progress_callback(progress, localized_message)

    parser_progress = 20

    def parser_message_handler(message: str) -> None:
        nonlocal parser_progress

        if message.startswith("Starting to parse"):
            parser_progress = max(parser_progress, 20)
        elif message.startswith("Loading the workouts"):
            parser_progress = max(parser_progress, 35)
        elif message.startswith("Processed "):
            parser_progress = min(parser_progress + 2, 80)
        elif message.startswith("Loaded "):
            parser_progress = max(parser_progress, 85)
        elif message.startswith("Finished parsing"):
            parser_progress = max(parser_progress, 90)

        report(parser_progress, message)

    report(5, t("Preparing file load..."))
    start_time = time.perf_counter()
    _logger.info("Starting to load file: %s", file_path)

    with ExportParser(progress_callback=parser_message_handler) as ep:
        phd = ep.parse(file_path)
        workouts_df = phd.workouts
        records_by_type = RecordsByType(data=phd.records_by_type)

    report(93, t("Building workout index..."))
    workouts = WorkoutManager(workouts_df)
    elapsed = time.perf_counter() - start_time
    _logger.info(workouts.get_statistics())
    _logger.info("Finished parsing in %s seconds.", elapsed)

    activity_types = workouts.get_activity_types()
    activity_types.sort()
    activity_options = ["All"] + activity_types

    report(97, t("Preparing dashboard update..."))
    return workouts, activity_options, records_by_type


async def load_file() -> None:
    """Load and parse the selected Apple Health export file."""
    if state.input_file.value == "":
        ui.notify(t("Please select an Apple Health export file first."))
        return

    # Guard against concurrent invocations (e.g., from auto-load timer + manual click)
    if state.loading:
        _logger.debug("File loading already in progress, skipping concurrent invocation")
        return

    state.loading = True
    state.loading_status = f"0% - {t('Initializing...')}"

    loop = asyncio.get_running_loop()

    def progress_callback(progress: int, message: str) -> None:
        """Schedule a UI-safe update of the loading status from a worker thread."""

        def _update() -> None:
            if state.loading:
                state.loading_status = f"{progress}% - {message}"

        loop.call_soon_threadsafe(_update)

    try:
        workouts, activity_options, records_by_type = await asyncio.to_thread(
            load_workouts_from_file,
            state.input_file.value,
            progress_callback,
        )
        state.workouts = workouts
        state.records_by_type = records_by_type
        state.file_loaded = True
        state.activity_options = activity_options
        render_activity_select.refresh()
        render_date_range_selector.refresh()
        refresh_data()
        ui.notify(t("File parsed successfully."))
    except Exception as e:
        ui.notify(t("Error parsing file: {error}", error=str(e)))
    finally:
        state.loading_status = ""
        state.loading = False


def render_body() -> None:
    """Generate the main body of the application."""
    with ui.row().classes(ROW_FULL_ITEMS_CLASSES):
        state.input_file = (
            ui.input(
                t("Apple Health export file"),
                placeholder=t("Select an Apple Health export file..."),
            )
            .classes(INPUT_GROW_CLASSES)
            .bind_value(app.storage.user, "input_file_path")
        )
        ui.button(t("Browse"), on_click=pick_file, icon="folder_open")

    with ui.row().classes(ROW_FULL_ITEMS_CLASSES):
        ui.button(t("Load"), on_click=load_file, icon="play_arrow").classes(
            INPUT_GROW_CLASSES
        ).bind_enabled_from(state, "loading", backward=lambda loading: not loading)
        ui.spinner(size="lg").bind_visibility_from(state, "loading")

    ui.label().classes(LABEL_MUTED_CLASSES).bind_text_from(
        state, "loading_status"
    ).bind_visibility_from(state, "loading")

    def _on_tab_change(event: Any) -> None:
        value = getattr(event, "value", None)
        tab_name = (
            _migrate_legacy_tab_name(str(getattr(value, "name", value)))
            if value is not None
            else ""
        )
        state.selected_main_tab = tab_name
        if tab_name == "running":
            schedule_best_segments_load()
            schedule_health_data_load()
        elif tab_name == "health_data":
            schedule_health_data_load()

    with ui.tabs(on_change=_on_tab_change).classes(TABS_FULL_CLASSES) as tabs:
        ui.tab("summary", t("Overview"))
        ui.tab("activities", t("Activities")).bind_enabled_from(state, "file_loaded")
        ui.tab("trends", t("Trends")).bind_enabled_from(state, "file_loaded")
        ui.tab("statistics", t("Statistics")).bind_enabled_from(state, "file_loaded")
        ui.tab("running", t("Running")).bind_enabled_from(state, "file_loaded")
        ui.tab("workouts", t("Workouts")).bind_enabled_from(state, "file_loaded")
        ui.tab("health_data", t("Health Data")).bind_enabled_from(state, "file_loaded")
    selected_tab = _migrate_legacy_tab_name(state.selected_main_tab or "summary")
    state.selected_main_tab = selected_tab

    # Restore the previously selected tab (defaults to "summary" on first render).
    tabs.value = selected_tab

    with ui.tab_panels(tabs, value=selected_tab).classes(TABS_FULL_CLASSES):
        with ui.tab_panel("summary"):
            dist_unit = get_distance_unit()
            elev_unit = get_elevation_unit()

            def _open_record_metric(metric_key: str) -> None:
                workout_index = state.metrics_workout_index.get(metric_key)
                if workout_index is None:
                    return
                full_rows = _build_workout_rows(
                    activity_type="All",
                    skip_range_filters=True,
                )
                row_index_by_workout_index: dict[object, int] = {}
                for idx, row_workout_index in enumerate(
                    row.get("workout_index") for row in full_rows
                ):
                    if (
                        row_workout_index is not None
                        and row_workout_index not in row_index_by_workout_index
                    ):
                        row_index_by_workout_index[row_workout_index] = idx
                row_index = row_index_by_workout_index.get(workout_index)
                if row_index is None:
                    return
                open_detail = create_workout_detail_modal(full_rows)
                open_detail(row_index)

            with ui.row().classes(ROW_CENTERED_CLASSES):
                stat_card(t("Count"), state.metrics_display, "count")
                stat_card(t("Distance"), state.metrics_display, "distance", dist_unit)
                stat_card(t("Duration"), state.metrics_display, "duration", "h")
                stat_card(t("Elevation"), state.metrics_display, "elevation", elev_unit)
                stat_card(t("Calories"), state.metrics_display, "calories", "kcal")
            with ui.row().classes(ROW_CENTERED_CLASSES):
                stat_card(
                    t("Longest Run"),
                    state.metrics_display,
                    "longest_run",
                    dist_unit,
                    tooltip_ref=state.metrics_tooltip,
                    tooltip_key="longest_run",
                    on_click=lambda: _open_record_metric("longest_run"),
                )
                stat_card(
                    t("Longest Walk/Hike"),
                    state.metrics_display,
                    "longest_walk",
                    dist_unit,
                    tooltip_ref=state.metrics_tooltip,
                    tooltip_key="longest_walk",
                    on_click=lambda: _open_record_metric("longest_walk"),
                )
                stat_card(
                    t("Most Elevation (Run)"),
                    state.metrics_display,
                    "most_elevation_run",
                    elev_unit,
                    tooltip_ref=state.metrics_tooltip,
                    tooltip_key="most_elevation_run",
                    on_click=lambda: _open_record_metric("most_elevation_run"),
                )
                stat_card(
                    t("Most Elevation (Walk/Hike)"),
                    state.metrics_display,
                    "most_elevation_walk",
                    elev_unit,
                    tooltip_ref=state.metrics_tooltip,
                    tooltip_key="most_elevation_walk",
                    on_click=lambda: _open_record_metric("most_elevation_walk"),
                )
            with ui.row().classes(ROW_CENTERED_CLASSES):
                stat_card(
                    t("Longest Cycling"),
                    state.metrics_display,
                    "longest_cycling",
                    dist_unit,
                    tooltip_ref=state.metrics_tooltip,
                    tooltip_key="longest_cycling",
                    on_click=lambda: _open_record_metric("longest_cycling"),
                )
                stat_card(
                    t("Longest Swim"),
                    state.metrics_display,
                    "longest_swim",
                    dist_unit,
                    tooltip_ref=state.metrics_tooltip,
                    tooltip_key="longest_swim",
                    on_click=lambda: _open_record_metric("longest_swim"),
                )
                stat_card(
                    t("Longest Duration Workout"),
                    state.metrics_display,
                    "longest_duration_workout",
                    "",
                    tooltip_ref=state.metrics_tooltip,
                    tooltip_key="longest_duration_workout",
                    on_click=lambda: _open_record_metric("longest_duration_workout"),
                )
                stat_card(
                    t("Most Calories Workout"),
                    state.metrics_display,
                    "most_calories_workout",
                    "kcal",
                    tooltip_ref=state.metrics_tooltip,
                    tooltip_key="most_calories_workout",
                    on_click=lambda: _open_record_metric("most_calories_workout"),
                )

        with ui.tab_panel("activities"):
            render_activity_graphs()

        with ui.tab_panel("trends"):
            render_trends_tab()

        with ui.tab_panel("statistics"):
            render_statistics_tab()

        with ui.tab_panel("running"):
            render_running_tab()

        with ui.tab_panel("workouts"):
            with ui.row().classes(RANGE_SELECTORS_ROW_CLASSES):
                render_distance_range_selector()
                render_duration_range_selector()
            render_workout_table()

        with ui.tab_panel("health_data"):
            render_health_data_tab()
