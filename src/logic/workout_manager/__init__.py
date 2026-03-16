"""Workout manager package and public compatibility exports."""

from datetime import datetime

from .manager import (
    HALF_MARATHON_DISTANCE_M,
    MARATHON_DISTANCE_M,
    STANDARD_SEGMENT_DISTANCES,
    WorkoutManager as _WorkoutManager,
)
from .segments import CriticalPowerResult


class WorkoutManager(_WorkoutManager):
    """Compatibility wrapper exposing package-level datetime monkeypatch point."""

    def get_date_bounds(self) -> tuple[str, str]:
        """Return the minimum and maximum start dates as strings in YYYY/MM/DD."""
        if self.workouts.empty or "startDate" not in self.workouts.columns:
            return "2000/01/01", datetime.now().strftime(self.DATE_FORMAT)

        start_dates = [w.startDate for w in self.workouts.itertuples()]

        return (
            min(start_dates).strftime(self.DATE_FORMAT),  # type: ignore[arg-type,union-attr]
            max(start_dates).strftime(self.DATE_FORMAT),  # type: ignore[arg-type,union-attr]
        )


__all__ = [
    "WorkoutManager",
    "STANDARD_SEGMENT_DISTANCES",
    "HALF_MARATHON_DISTANCE_M",
    "MARATHON_DISTANCE_M",
    "CriticalPowerResult",
    "datetime",
]
