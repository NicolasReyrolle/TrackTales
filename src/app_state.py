"""Application state management for Apple Health Analyzer."""

import asyncio
from datetime import datetime
from typing import Any

from nicegui import ui

from logic.records_by_type import RecordsByType
from logic.workout_manager import WorkoutManager


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
