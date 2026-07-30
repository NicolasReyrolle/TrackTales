"""Core WorkoutManager class composed from dedicated mixins."""

import pandas as pd

from .aggregations import WorkoutManagerAggregationsMixin, calculate_trend_slope
from .export import WorkoutManagerExportMixin
from .seasonal import WorkoutManagerSeasonalMixin
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
    WorkoutManagerSeasonalMixin,
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

    def get_trend_analysis(
        self,
        data_points: list[float],
        is_higher_better: bool = True,
        threshold: float = 0.05,
        label_mode: str = "semantic",
        x_values: list[int | float] | None = None,
    ) -> str:
        """Classify a numeric trend as semantic or directional labels.

        Args:
            data_points: Ordered metric values for consecutive periods.
            is_higher_better: Whether rising values represent improvement for the
                metric being analysed. Ignored when ``label_mode`` is
                ``"directional"``.
            threshold: Minimum absolute slope required before the series is
                classified as changing instead of stable.
            label_mode: ``"semantic"`` to return improvement-oriented labels
                (for example ``"Improving"``), or ``"directional"`` to return
                slope-only labels (for example ``"Increasing"``).
            x_values: Optional x-positions corresponding to each entry in
                *data_points*.  When ``None``, equally-spaced integer indices
                are assumed.  Pass explicit positions to preserve original period
                spacing when some periods contain gaps (``None`` values) that
                were removed by the caller before invoking this method.
        """
        slope = calculate_trend_slope(data_points, x_values=x_values)
        if slope is None:
            return "Insufficient data"

        significance_threshold = abs(threshold)
        if abs(slope) < significance_threshold:
            return "Stable"

        if label_mode == "directional":
            return "Increasing" if slope > 0 else "Decreasing"

        is_improving = slope > 0 if is_higher_better else slope < 0
        return "Improving" if is_improving else "Declining"
