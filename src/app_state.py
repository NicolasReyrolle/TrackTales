"""Application state management for Apple Health Analyzer."""

import asyncio
from datetime import datetime
from typing import Any, cast

from nicegui import app, ui

from i18n import DEFAULT_LANGUAGE as DEFAULT_LANGUAGE  # re-export alongside unit-system defaults
from logic.records_by_type import RecordsByType
from logic.workout_manager import WorkoutManager

# ---------------------------------------------------------------------------
# Unit system preference constants
# ---------------------------------------------------------------------------

#: Available unit systems: mapping from system code to display label.
UNIT_SYSTEMS: dict[str, str] = {"metric": "Metric", "imperial": "Imperial"}

DEFAULT_UNIT_SYSTEM: str = "metric"


def _register_unit_system_translations() -> None:
    """Register unit-system labels for Babel extraction.

    These literals are translated dynamically elsewhere, so Babel needs literal
    ``t("...")`` calls in scanned code to keep them in ``messages.pot``.
    """
    from i18n import t  # noqa: PLC0415

    t("Metric")
    t("Imperial")


_register_unit_system_translations()


def get_unit_system() -> str:
    """Return the active unit system from NiceGUI user storage.

    Returns ``"metric"`` or ``"imperial"``. Falls back to ``DEFAULT_UNIT_SYSTEM``
    when storage is not available (e.g., during unit tests).
    """
    try:
        user_storage = cast(dict[str, object], app.storage.user)
        system = str(user_storage.get("unit_system", DEFAULT_UNIT_SYSTEM))
        return system if system in UNIT_SYSTEMS else DEFAULT_UNIT_SYSTEM
    except Exception:
        return DEFAULT_UNIT_SYSTEM


def get_distance_unit() -> str:
    """Return the active distance unit derived from the current unit system.

    Returns ``"km"`` for metric, ``"mi"`` for imperial.
    """
    return "mi" if get_unit_system() == "imperial" else "km"


def get_elevation_unit() -> str:
    """Return the active elevation unit derived from the current unit system.

    Returns ``"m"`` for metric, ``"ft"`` for imperial.
    """
    return "ft" if get_unit_system() == "imperial" else "m"


def get_weight_unit() -> str:
    """Return the active weight unit derived from the current unit system.

    Returns ``"lbs"`` for imperial, ``"kg"`` for metric.
    """
    return "lbs" if get_unit_system() == "imperial" else "kg"


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
        # Distance range filter for the workout table (values in the user's preferred unit).
        # Initialised to {"min": 0.0, "max": 0.0}; reset to full dataset bounds on file load.
        self.distance_range: dict[str, float] = {"min": 0.0, "max": 0.0}
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
