"""Core WorkoutManager class composed from dedicated mixins."""

import pandas as pd

from .aggregations import WorkoutManagerAggregationsMixin
from .export import WorkoutManagerExportMixin
from .segments import WorkoutManagerSegmentsMixin

STANDARD_SEGMENT_DISTANCES: list[int] = [
    100,
    200,
    400,
    800,
    1000,
    5000,
    10000,
    15000,
    20000,
    21097,
    42195,
    50000,
    100000,
]
HALF_MARATHON_DISTANCE_M = 21097
MARATHON_DISTANCE_M = 42195


class WorkoutManager(
    WorkoutManagerAggregationsMixin,
    WorkoutManagerExportMixin,
    WorkoutManagerSegmentsMixin,
):
    """Class to manage workout data and metrics."""

    DEFAULT_EXCLUDED_COLUMNS = {"route", "route_parts"}
    DATE_FORMAT = "%Y/%m/%d"
    DEFAULT_SEGMENT_DISTANCES = STANDARD_SEGMENT_DISTANCES

    def __init__(self, pd_workouts: pd.DataFrame | None = None) -> None:
        if pd_workouts is None:
            self.workouts: pd.DataFrame = pd.DataFrame(
                columns=[
                    "activityType",
                    "startDate",
                    "endDate",
                    "duration",
                    "durationUnit",
                    "distance",
                ]
            )
        else:
            self.workouts = pd_workouts
