"""UI layout components for Apple Health Analyzer application."""

import asyncio
import logging
import time
from collections.abc import Callable
from typing import Any, cast

import pandas as pd
from nicegui import app, ui

from app_state import state
from assets import APP_ICON_BASE64
from i18n import LANGUAGES, get_language, t
from i18n.activity_types import build_activity_select_options, translate_activity_value_map
from logic.export_parser import ExportParser
from logic.records_by_type import RecordsByType
from logic.workout_manager import WorkoutManager
from ui.best_segments import load_best_segments_data, render_best_segments_tab
from ui.charts import (
    render_generic_graph,
    render_pie_rose_graph,
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
    ROW_CENTERED_CLASSES,
    ROW_FULL_ITEMS_CLASSES,
    TABS_FULL_CLASSES,
)
from ui.helpers import (
    format_date_label,
    format_duration_label,
    format_float,
    format_integer,
    period_code_to_label,
    qdate_locale_json,
    translate_parser_progress_message,
)
from ui.local_file_picker import LocalFilePicker
from ui.workout_table import render_workout_table

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
    """Build chart series for fast health graphs (HR, body mass, VO2 max)."""
    heart_rate_stats = state.records_by_type.heart_rate_stats(
        period=state.trends_period,
        context=RecordsByType.HeartRateMeasureContext.SEDENTARY,
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
    return {
        "heart_rate": _to_json_safe(
            heart_rate_stats.assign(period=heart_rate_stats["period"].astype(str))
            .set_index("period")["avg"]
            .to_dict()
        ),
        "body_mass": _to_json_safe(
            body_mass_stats.assign(period=body_mass_stats["period"].astype(str))
            .set_index("period")["avg"]
            .to_dict()
        ),
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
    metrics: dict[str, int | float] = state.metrics
    metrics_display: dict[str, str] = state.metrics_display
    metrics["count"] = state.workouts.get_count(
        state.selected_activity_type, state.start_date, state.end_date
    )
    metrics["distance"] = state.workouts.get_total_distance(
        state.selected_activity_type, start_date=state.start_date, end_date=state.end_date
    )
    metrics["duration"] = state.workouts.get_total_duration(
        state.selected_activity_type, start_date=state.start_date, end_date=state.end_date
    )
    metrics["elevation"] = state.workouts.get_total_elevation(
        state.selected_activity_type, start_date=state.start_date, end_date=state.end_date
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
) -> None:
    """Set one longest-workout metric display/tooltip from details."""
    metrics: dict[str, int | float] = state.metrics  # type: ignore[assignment]
    metrics_display: dict[str, str] = state.metrics_display  # type: ignore[assignment]
    metrics_tooltip: dict[str, str] = state.metrics_tooltip  # type: ignore[assignment]
    metrics[metric_key] = 0.0
    metrics_display[metric_key] = format_float(0.0)

    if details is None:
        metrics_tooltip[metric_key] = t("No data")
        return

    distance_value = details.get("distance")
    distance_float = 0.0
    if distance_value is not None:
        try:
            distance_float = float(distance_value)
        except (TypeError, ValueError):
            distance_float = 0.0

    metrics[metric_key] = distance_float
    metrics_display[metric_key] = format_float(distance_float)

    date_value = details.get("date")
    duration_value = details.get("duration")

    date_str: str | None = None
    if date_value is not None:
        date_str = format_date_label(date_value, language_code)

    duration_str: str | None = None
    if duration_value is not None:
        try:
            duration_float = float(duration_value)
        except (TypeError, ValueError):
            duration_float = None
        else:
            duration_str = format_duration_label(duration_float)

    if date_str and duration_str:
        metrics_tooltip[metric_key] = f"{date_str} — {duration_str}"
    elif date_str:
        metrics_tooltip[metric_key] = date_str
    elif duration_str:
        metrics_tooltip[metric_key] = duration_str
    else:
        metrics_tooltip[metric_key] = t("No data")


def _refresh_longest_workout_metrics() -> None:
    """Refresh longest run/walk/cycling metrics and tooltips."""
    language_code = get_language()
    metric_configs = [
        ("longest_run", ["Running"]),
        ("longest_walk", ["Walking", "Hiking"]),
        ("longest_cycling", ["Cycling"]),
    ]

    for metric_key, activity_types in metric_configs:
        details = state.workouts.get_longest_workout_details(
            activity_types,
            start_date=state.start_date,
            end_date=state.end_date,
        )
        _set_longest_metric_from_details(metric_key, details, language_code)


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

    render_activity_graphs.refresh()
    render_trends_graphs.refresh()
    render_health_data_tab.refresh()
    render_best_segments_tab.refresh()
    render_workout_table.refresh()

    # If user is already on the tab, load asynchronously after invalidation.
    if state.selected_main_tab == "best_segments":
        schedule_best_segments_load()
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


def render_left_drawer() -> None:
    """Generate the left drawer with filters."""

    with ui.left_drawer().props("width=330"):
        ui.label(t("Activities"))
        render_activity_select()

        ui.separator()

        render_date_range_selector()

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


def render_header() -> None:
    """Generate the application header with a dark mode toggle and language selector."""
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

        # Language selector (globe icon)
        with ui.button(icon="language").props(BUTTON_FLAT_ROUND_PROPS):
            with ui.menu():
                for code, name in LANGUAGES.items():
                    ui.menu_item(name, on_click=lambda _event, c=code: _change_language(c))


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
        tab_name = str(getattr(value, "name", value)) if value is not None else ""
        state.selected_main_tab = tab_name
        if tab_name == "best_segments":
            schedule_best_segments_load()
        elif tab_name == "health_data":
            schedule_health_data_load()

    with ui.tabs(on_change=_on_tab_change).classes(TABS_FULL_CLASSES) as tabs:
        ui.tab("summary", t("Overview"))
        ui.tab("activities", t("Activities")).bind_enabled_from(state, "file_loaded")
        ui.tab("trends", t("Trends")).bind_enabled_from(state, "file_loaded")
        ui.tab("workouts", t("Workouts")).bind_enabled_from(state, "file_loaded")
        ui.tab("health_data", t("Health Data")).bind_enabled_from(state, "file_loaded")
        ui.tab("best_segments", t("Best Segments")).bind_enabled_from(state, "file_loaded")

    # Restore the previously selected tab (defaults to "summary" on first render).
    tabs.value = state.selected_main_tab or "summary"

    with ui.tab_panels(tabs, value=state.selected_main_tab or "summary").classes(TABS_FULL_CLASSES):
        with ui.tab_panel("summary"):
            with ui.row().classes(ROW_CENTERED_CLASSES):
                stat_card(t("Count"), state.metrics_display, "count")
                stat_card(t("Distance"), state.metrics_display, "distance", "km")
                stat_card(t("Duration"), state.metrics_display, "duration", "h")
                stat_card(t("Elevation"), state.metrics_display, "elevation", "km")
            with ui.row().classes(ROW_CENTERED_CLASSES):
                stat_card(t("Calories"), state.metrics_display, "calories", "kcal")
            with ui.row().classes(ROW_CENTERED_CLASSES):
                stat_card(
                    t("Longest Run"),
                    state.metrics_display,
                    "longest_run",
                    "km",
                    tooltip_ref=state.metrics_tooltip,
                    tooltip_key="longest_run",
                )
                stat_card(
                    t("Longest Walk/Hike"),
                    state.metrics_display,
                    "longest_walk",
                    "km",
                    tooltip_ref=state.metrics_tooltip,
                    tooltip_key="longest_walk",
                )
                stat_card(
                    t("Longest Cycling"),
                    state.metrics_display,
                    "longest_cycling",
                    "km",
                    tooltip_ref=state.metrics_tooltip,
                    tooltip_key="longest_cycling",
                )

        with ui.tab_panel("activities"):
            render_activity_graphs()

        with ui.tab_panel("trends"):
            render_trends_tab()

        with ui.tab_panel("workouts"):
            render_workout_table()

        with ui.tab_panel("health_data"):
            render_health_data_tab()

        with ui.tab_panel("best_segments"):
            render_best_segments_tab()


@ui.refreshable
def render_activity_graphs() -> None:
    """Render graphs by activity type."""
    with ui.row().classes(ROW_CENTERED_CLASSES):
        render_pie_rose_graph(
            t("Count by activity"),
            translate_activity_value_map(
                state.workouts.get_count_by_activity(
                    start_date=state.start_date, end_date=state.end_date
                )
            ),
        )
        render_pie_rose_graph(
            t("Distance by activity"),
            translate_activity_value_map(
                state.workouts.get_distance_by_activity(
                    start_date=state.start_date, end_date=state.end_date
                )
            ),
            "km",
        )
    with ui.row().classes(ROW_CENTERED_CLASSES):
        render_pie_rose_graph(
            t("Calories by activity"),
            translate_activity_value_map(
                state.workouts.get_calories_by_activity(
                    start_date=state.start_date, end_date=state.end_date
                )
            ),
            "kcal",
        )
        render_pie_rose_graph(
            t("Duration by activity"),
            translate_activity_value_map(
                state.workouts.get_duration_by_activity(
                    start_date=state.start_date, end_date=state.end_date
                )
            ),
            "h",
        )
    with ui.row().classes(ROW_CENTERED_CLASSES):
        # Display elevation in meters (not km like the stat card) because per-activity
        # values can be small and would show as 0.0X km, making the chart less readable
        render_pie_rose_graph(
            t("Elevation by activity"),
            translate_activity_value_map(
                state.workouts.get_elevation_by_activity(
                    start_date=state.start_date, end_date=state.end_date
                )
            ),
            "m",
        )


def render_trends_tab() -> None:
    """Render the trends tab with period selection and graphs."""

    def _on_trends_period_change() -> None:
        _reset_health_data_state()
        render_trends_graphs.refresh()
        render_health_data_tab.refresh()
        if state.selected_main_tab == "health_data":
            schedule_health_data_load()

    with ui.row().classes(ROW_CENTERED_CLASSES):
        ui.label(t("Aggregate by:")).classes(LABEL_SECTION_CLASSES)
        ui.radio(
            {
                "W": t("Week"),
                "M": t("Month"),
                "Q": t("Quarter"),
                "Y": t("Year"),
            },
            on_change=_on_trends_period_change,
        ).bind_value(state, "trends_period").props("inline")

    render_trends_graphs()


@ui.refreshable
def render_trends_graphs() -> None:
    """Render trend graphs."""
    period_label = t(period_code_to_label(state.trends_period))
    with ui.row().classes(ROW_CENTERED_CLASSES):
        render_generic_graph(
            t("Count by {period}", period=period_label),
            state.workouts.get_count_by_period(
                state.trends_period,
                activity_type=state.selected_activity_type,
                start_date=state.start_date,
                end_date=state.end_date,
            ),
        )
        render_generic_graph(
            t("Distance by {period}", period=period_label),
            state.workouts.get_distance_by_period(
                state.trends_period,
                activity_type=state.selected_activity_type,
                start_date=state.start_date,
                end_date=state.end_date,
            ),
            "km",
        )
    with ui.row().classes(ROW_CENTERED_CLASSES):
        render_generic_graph(
            t("Calories by {period}", period=period_label),
            state.workouts.get_calories_by_period(
                state.trends_period,
                activity_type=state.selected_activity_type,
                start_date=state.start_date,
                end_date=state.end_date,
            ),
            "kcal",
        )
        render_generic_graph(
            t("Duration by {period}", period=period_label),
            state.workouts.get_duration_by_period(
                state.trends_period,
                activity_type=state.selected_activity_type,
                start_date=state.start_date,
                end_date=state.end_date,
            ),
            "h",
        )
    with ui.row().classes(ROW_CENTERED_CLASSES):
        # Display elevation in meters (not km like the stat card) because values for the
        # selected period can be small and would show as 0.0X km, making the chart less readable
        render_generic_graph(
            t("Elevation by {period}", period=period_label),
            state.workouts.get_elevation_by_period(
                state.trends_period,
                activity_type=state.selected_activity_type,
                unit="m",
                start_date=state.start_date,
                end_date=state.end_date,
            ),
            "m",
        )


@ui.refreshable
def render_health_data_tab() -> None:
    """Render the health data tab with filters and graphs."""

    if state.health_data_loading:
        with ui.row().classes(ROW_CENTERED_CLASSES):
            ui.spinner(size="lg")
            ui.label(t("Loading health data..."))
        return

    if not state.health_data_loaded:
        ui.label(t("Open this tab to load health data.")).classes(LABEL_MUTED_CLASSES)
        return

    with ui.row().classes(ROW_CENTERED_CLASSES):
        render_generic_graph(
            t("Resting HR frequency over time"),
            state.health_data_graphs.get("heart_rate", {}),
            "bpm",
            graph_type="line",
        )
        render_generic_graph(
            t("Body Mass over time"),
            state.health_data_graphs.get("body_mass", {}),
            "kg",
            graph_type="line",
        )

    with ui.row().classes(ROW_CENTERED_CLASSES):
        render_generic_graph(
            t("VO2 Max over time"),
            state.health_data_graphs.get("vo2_max", {}),
            "ml/kg/min",
            graph_type="line",
        )

    with ui.row().classes(ROW_CENTERED_CLASSES):
        if state.health_data_cp_loading:
            ui.spinner(size="lg")
            ui.label(t("Loading Critical Power data..."))
        else:
            render_generic_graph(
                t("Critical Power (CP) over time"),
                state.health_data_graphs.get("critical_power", {}),
                "W",
                graph_type="line",
                show_trend=False,
            )
            render_generic_graph(
                t("W' over time"),
                state.health_data_graphs.get("w_prime", {}),
                "kJ",
                graph_type="line",
                show_trend=False,
            )
