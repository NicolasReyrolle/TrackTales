"""Models representing the structured data extracted from the Apple Health export."""

from typing import Any, TypedDict

from logic.workout_manager.workout_route import WorkoutRoute


class WorkoutRecordRequired(TypedDict):
    """Required fields for workout record."""

    activityType: str


class WorkoutRecord(WorkoutRecordRequired, total=False):
    """Type definition for workout record structure."""

    duration: float | None
    durationUnit: str | None
    startDate: str | None
    endDate: str | None
    source: str | None
    xmlFragment: str | None
    route: WorkoutRoute | None
    route_parts: list[WorkoutRoute]
    distance: int | None  # Total distance in meters
    swimming_events: list[dict[str, Any]]  # Parsed WorkoutEvent list for swimming
