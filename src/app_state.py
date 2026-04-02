"""Application state management for Apple Health Analyzer."""

import asyncio
from datetime import datetime
from typing import Any, cast

from nicegui import app, ui

from logic.records_by_type import RecordsByType
from logic.workout_manager import WorkoutManager

# ---------------------------------------------------------------------------
# Unit preference constants
# ---------------------------------------------------------------------------

DEFAULT_DISTANCE_UNIT: str = "km"
DEFAULT_WEIGHT_UNIT: str = "kg"

#: Available distance units: mapping from unit code to display label.
DISTANCE_UNITS: dict[str, str] = {"km": "km", "mi": "mi"}

#: Available weight units: mapping from unit code to display label.
WEIGHT_UNITS: dict[str, str] = {"kg": "kg", "lbs": "lbs"}


def get_distance_unit() -> str:
    """Return the active distance unit from NiceGUI user storage.

    Falls back to ``DEFAULT_DISTANCE_UNIT`` when storage is not available
    (e.g., during unit tests that do not set up a NiceGUI session).
    """
    try:
        user_storage = cast(dict[str, object], app.storage.user)
        unit = str(user_storage.get("distance_unit", DEFAULT_DISTANCE_UNIT))
        return unit if unit in DISTANCE_UNITS else DEFAULT_DISTANCE_UNIT
    except Exception:
        return DEFAULT_DISTANCE_UNIT


def get_weight_unit() -> str:
    """Return the active weight unit from NiceGUI user storage.

    Falls back to ``DEFAULT_WEIGHT_UNIT`` when storage is not available
    (e.g., during unit tests that do not set up a NiceGUI session).
    """
    try:
        user_storage = cast(dict[str, object], app.storage.user)
        unit = str(user_storage.get("weight_unit", DEFAULT_WEIGHT_UNIT))
        return unit if unit in WEIGHT_UNITS else DEFAULT_WEIGHT_UNIT
    except Exception:
        return DEFAULT_WEIGHT_UNIT


class AppState:
    """Application state."""

    def __init__(self) -> None:
        self.reset()
        self.input_file: ui.input  # Assigned in layout.py
        # Dark mode preference — persists across data reloads so it lives outside reset().
        self.dark_mode_enabled: bool = False

    def reset(self) -> None:
        """Reset the application state."""
        self.workouts: WorkoutManager = WorkoutManager()
        self.records_by_type: RecordsByType = RecordsByType(data={})
        self.file_loaded: bool = False
        self.loading: bool = False
        self.loading_status: str = ""
        self.metrics: dict[str, int | float] = {
            "count": 0,
            "distance": 0,
            "duration": 0,
            "elevation": 0,
            "calories": 0,
            "longest_run": 0.0,
            "longest_walk": 0.0,
            "longest_cycling": 0.0,
        }
        self.metrics_display: dict[str, str] = {
            "count": "0",
            "distance": "0",
            "duration": "0",
            "elevation": "0",
            "calories": "0",
            "longest_run": "0.0",
            "longest_walk": "0.0",
            "longest_cycling": "0.0",
        }
        self.metrics_tooltip: dict[str, str] = {
            "longest_run": "",
            "longest_walk": "",
            "longest_cycling": "",
        }
        self.best_segments_rows: list[dict[str, Any]] = []
        self.best_segments_loading: bool = False
        self.best_segments_loaded: bool = False
        self.best_segments_task: asyncio.Task[None] | None = None
        self.health_data_graphs: dict[str, dict[str, float | int | None]] = {
            "heart_rate": {},
            "body_mass": {},
            "vo2_max": {},
            "critical_power": {},
            "w_prime": {},
        }
        self.health_data_loading: bool = False
        self.health_data_loaded: bool = False
        self.health_data_cp_loading: bool = False
        self.health_data_task: asyncio.Task[None] | None = None
        self.selected_main_tab: str = "summary"

        self.selected_activity_type: str = "All"
        self.activity_options: list[str] = ["All"]
        self.date_range_text: str = ""
        self.trends_period: str = "M"
        # Distance range filter for the workout table (values in km).
        # Initialised to {"min": 0.0, "max": 0.0}; reset to full dataset bounds on file load.
        self.distance_range_km: dict[str, float] = {"min": 0.0, "max": 0.0}
        # Duration range filter for the workout table (values in minutes).
        # Initialised to {"min": 0.0, "max": 0.0}; reset to full dataset bounds on file load.
        self.duration_range_min: dict[str, float] = {"min": 0.0, "max": 0.0}

    def _parse_date(self, date_str: str) -> datetime | None:
        """Parse a date string in one of the supported formats.

        Accepts both dash- and slash-separated dates (e.g. 2024-01-02 or 2024/01/02).
        Returns None if parsing fails instead of raising ValueError.
        """
        cleaned = date_str.strip()
        if not cleaned:
            return None

        for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
            try:
                return datetime.strptime(cleaned, fmt)
            except ValueError:
                continue

        return None

    @property
    def start_date(self) -> datetime | None:
        """Get the start date from the date range text."""
        if " - " in self.date_range_text:
            date_str = self.date_range_text.split(" - ", maxsplit=1)[0]
            return self._parse_date(date_str)
        return None

    @property
    def end_date(self) -> datetime | None:
        """Get the end date from the date range text."""
        if " - " in self.date_range_text:
            date_str = self.date_range_text.split(" - ", maxsplit=1)[1]
            return self._parse_date(date_str)
        return None


state = AppState()
