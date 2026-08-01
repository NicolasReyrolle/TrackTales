"""Recovery recommendation mixin for WorkoutManager."""

from datetime import datetime

import pandas as pd

# Acute:Chronic Workload Ratio (ACWR) thresholds based on sports science literature.
# These values define the four training-load zones.
_ACWR_REST_THRESHOLD: float = 1.5
_ACWR_ACTIVE_RECOVERY_THRESHOLD: float = 1.3
_ACWR_BUILD_THRESHOLD: float = 0.8

# Number of weeks used for the chronic (rolling-average) load window.
_CHRONIC_LOAD_WINDOW_WEEKS: int = 4

# Minimum number of weekly periods required to compute a meaningful ACWR.
_MIN_WEEKS_FOR_ACWR: int = 2


class WorkoutManagerRecoveryMixin:
    """Training load analysis and recovery recommendation helpers.

    Uses the Acute:Chronic Workload Ratio (ACWR) framework from sports science.
    The ACWR is the ratio of the most recent week's load (acute) to the
    rolling average over the past four weeks (chronic), providing a simple
    measure of how much the current training spike compares to the recent norm.
    """

    workouts: pd.DataFrame

    # --- Stubs for methods supplied by WorkoutManagerAggregationsMixin -----------

    def get_duration_by_period(
        self,
        period: str,
        activity_type: str = "All",
        fill_missing_periods: bool = True,
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
    ) -> dict[str, int]:
        """Provided by WorkoutManagerAggregationsMixin."""
        raise NotImplementedError  # pragma: no cover

    def get_distance_by_period(
        self,
        period: str,
        activity_type: str = "All",
        unit: str = "km",
        fill_missing_periods: bool = True,
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
    ) -> dict[str, int]:
        """Provided by WorkoutManagerAggregationsMixin."""
        raise NotImplementedError  # pragma: no cover

    # --- Private helpers ---------------------------------------------------------

    def _get_weekly_load(
        self,
        load_metric: str,
        activity_type: str = "All",
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
    ) -> list[float]:
        """Return chronologically ordered weekly load totals (oldest → most recent).

        Args:
            load_metric: ``"duration"`` uses total hours per week;
                ``"distance"`` uses total kilometres per week.
            activity_type: Optional activity type filter.  Defaults to ``"All"``.
            start_date: Optional lower bound on workout start date.
            end_date: Optional upper bound on workout start date.

        Returns:
            List of floats, one entry per calendar week, ordered from oldest
            to most recent.  Missing weeks are filled with ``0``.

        Raises:
            ValueError: When *load_metric* is not ``"duration"`` or ``"distance"``.
        """
        if load_metric == "duration":
            weekly_data = self.get_duration_by_period(
                period="W",
                activity_type=activity_type,
                fill_missing_periods=True,
                start_date=start_date,
                end_date=end_date,
            )
        elif load_metric == "distance":
            weekly_data = self.get_distance_by_period(
                period="W",
                activity_type=activity_type,
                fill_missing_periods=True,
                start_date=start_date,
                end_date=end_date,
            )
        else:
            raise ValueError(
                f"Unsupported load_metric {load_metric!r}. Use 'duration' or 'distance'."
            )
        return [float(v) for v in weekly_data.values()]

    # --- Public API --------------------------------------------------------------

    def get_recovery_recommendation(
        self,
        activity_type: str = "All",
        load_metric: str = "duration",
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
    ) -> str:
        """Return a recovery recommendation based on the Acute:Chronic Workload Ratio (ACWR).

        Computes weekly training load totals and derives the ACWR:

        - **Acute load** – the most recent full week's total.
        - **Chronic load** – the rolling average over the last four weeks
          (or all available weeks when fewer than four are present).
        - **ACWR** = acute / chronic

        Recommendation mapping:

        +---------------------------+-------------------+
        | ACWR                      | Recommendation    |
        +===========================+===================+
        | > 1.5                     | Rest              |
        +---------------------------+-------------------+
        | 1.3 < ACWR ≤ 1.5          | Active Recovery   |
        +---------------------------+-------------------+
        | 0.8 ≤ ACWR ≤ 1.3          | Maintain          |
        +---------------------------+-------------------+
        | < 0.8                     | Build             |
        +---------------------------+-------------------+

        Returns ``"Insufficient data"`` when fewer than two full weeks of
        data are available, or when the chronic load is zero (no workouts
        in the chronic window).

        Args:
            activity_type: Activity type filter applied before aggregating
                load.  Defaults to ``"All"``.
            load_metric: Metric used as a training-load proxy.
                ``"duration"`` uses total workout hours per week;
                ``"distance"`` uses total kilometres per week.
                Defaults to ``"duration"``.
            start_date: Optional lower bound on the workout date range.
            end_date: Optional upper bound on the workout date range.

        Returns:
            One of ``"Rest"``, ``"Active Recovery"``, ``"Maintain"``,
            ``"Build"``, or ``"Insufficient data"``.
        """
        weekly_load = self._get_weekly_load(
            load_metric=load_metric,
            activity_type=activity_type,
            start_date=start_date,
            end_date=end_date,
        )

        if len(weekly_load) < _MIN_WEEKS_FOR_ACWR:
            return "Insufficient data"

        acute_load = weekly_load[-1]
        chronic_window = weekly_load[-_CHRONIC_LOAD_WINDOW_WEEKS:]
        chronic_load = sum(chronic_window) / len(chronic_window)

        if chronic_load == 0:
            return "Insufficient data"

        acwr = acute_load / chronic_load

        if acwr > _ACWR_REST_THRESHOLD:
            return "Rest"
        if acwr > _ACWR_ACTIVE_RECOVERY_THRESHOLD:
            return "Active Recovery"
        if acwr >= _ACWR_BUILD_THRESHOLD:
            return "Maintain"
        return "Build"
