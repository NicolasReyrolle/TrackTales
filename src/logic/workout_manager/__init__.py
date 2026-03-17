"""Workout manager package and public compatibility exports."""

from .manager import (
    HALF_MARATHON_DISTANCE_M,
    MARATHON_DISTANCE_M,
    STANDARD_SEGMENT_DISTANCES,
)
from .manager import (
    WorkoutManager as _WorkoutManager,
)
from .segments import CriticalPowerResult


class WorkoutManager(_WorkoutManager):
    """Compatibility wrapper for package-level imports."""

    pass


__all__ = [
    "WorkoutManager",
    "STANDARD_SEGMENT_DISTANCES",
    "HALF_MARATHON_DISTANCE_M",
    "MARATHON_DISTANCE_M",
    "CriticalPowerResult",
]
