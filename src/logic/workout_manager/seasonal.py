"""Seasonal pattern aggregation mixin for WorkoutManager."""

from collections.abc import Callable
from datetime import datetime
from typing import Any

import pandas as pd

# Seasonal pattern constants: positions are the integer values returned by the
# corresponding ``pd.Series.dt`` attribute; labels are the human-readable keys
# used in the returned dictionaries.
_DAY_OF_WEEK_POSITIONS: list[int] = list(range(7))  # 0=Monday … 6=Sunday
_DAY_OF_WEEK_LABELS: list[str] = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]
_MONTH_OF_YEAR_POSITIONS: list[int] = list(range(1, 13))  # 1=January … 12=December
_MONTH_OF_YEAR_LABELS: list[str] = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]
_QUARTER_OF_YEAR_POSITIONS: list[int] = [1, 2, 3, 4]  # 1=Q1 … 4=Q4
_QUARTER_OF_YEAR_LABELS: list[str] = ["Q1", "Q2", "Q3", "Q4"]


class WorkoutManagerSeasonalMixin:
    """Seasonal pattern aggregation methods (day-of-week, month, quarter)."""

    workouts: pd.DataFrame

    def _filter_workouts(
        self,
        activity_type: str = "All",
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
    ) -> pd.DataFrame:
        raise NotImplementedError

    def _get_length_unit_divisor(self, unit: str) -> float:
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Generic helper
    # ------------------------------------------------------------------

    def _aggregate_by_seasonal_unit(
        self,
        column: str,
        date_attr: str,
        positions: list[int],
        labels: list[str],
        aggregation: Callable[[Any], pd.Series],
        transformation: Callable[[pd.Series], pd.Series],
        column_check: str | None = None,
        activity_type: str = "All",
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
    ) -> dict[str, float]:
        """Aggregate a metric by a repeating calendar unit for seasonal pattern detection.

        Groups workouts by a cyclical date attribute (day of week, month of year, or
        quarter of year) and returns the total metric value for each position in the
        cycle across all available data.

        Args:
            column: DataFrame column to aggregate.
            date_attr: pandas ``dt`` attribute name (``"dayofweek"``, ``"month"``,
                or ``"quarter"``).
            positions: All expected integer positions for the date attribute
                (e.g. ``[0, 1, …, 6]`` for ``"dayofweek"``).
            labels: Human-readable label for each position in the same order as
                *positions* (e.g. ``["Monday", …, "Sunday"]``).
            aggregation: Callable accepting a SeriesGroupBy and returning an
                aggregated :class:`pandas.Series`.
            transformation: Callable that applies unit conversion to the aggregated
                Series (e.g. meters → km).
            column_check: Column whose presence is verified; defaults to *column*.
            activity_type: Filter to a specific activity type or ``"All"``.
            start_date: Optional lower bound for ``startDate``.
            end_date: Optional upper bound for ``startDate``.
        """
        column_check = column_check or column
        if column_check not in self.workouts.columns or "startDate" not in self.workouts.columns:
            return {}

        if not pd.api.types.is_datetime64_any_dtype(self.workouts["startDate"]):
            return {}

        workouts = self._filter_workouts(activity_type, start_date, end_date)
        if workouts.empty:
            return {}

        position_series = getattr(workouts["startDate"].dt, date_attr)
        grouped: pd.Series = aggregation(workouts.groupby(position_series)[column])

        # Ensure every canonical position appears in the result (fill absent ones with 0).
        full_index = pd.Index(positions)
        grouped = grouped.reindex(full_index, fill_value=0)

        transformed = transformation(grouped)
        return {label: float(v) for label, v in zip(labels, transformed.tolist())}

    # ------------------------------------------------------------------
    # Seasonal count
    # ------------------------------------------------------------------

    def get_count_by_day_of_week(
        self,
        activity_type: str = "All",
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
    ) -> dict[str, float]:
        """Return total workout count for each day of the week (Monday … Sunday)."""
        return self._aggregate_by_seasonal_unit(
            "activityType",
            "dayofweek",
            _DAY_OF_WEEK_POSITIONS,
            _DAY_OF_WEEK_LABELS,
            lambda x: x.count().astype(float),
            lambda x: x,
            column_check="activityType",
            activity_type=activity_type,
            start_date=start_date,
            end_date=end_date,
        )

    def get_count_by_month_of_year(
        self,
        activity_type: str = "All",
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
    ) -> dict[str, float]:
        """Return total workout count for each month of the year (January … December)."""
        return self._aggregate_by_seasonal_unit(
            "activityType",
            "month",
            _MONTH_OF_YEAR_POSITIONS,
            _MONTH_OF_YEAR_LABELS,
            lambda x: x.count().astype(float),
            lambda x: x,
            column_check="activityType",
            activity_type=activity_type,
            start_date=start_date,
            end_date=end_date,
        )

    def get_count_by_quarter_of_year(
        self,
        activity_type: str = "All",
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
    ) -> dict[str, float]:
        """Return total workout count for each quarter of the year (Q1 … Q4)."""
        return self._aggregate_by_seasonal_unit(
            "activityType",
            "quarter",
            _QUARTER_OF_YEAR_POSITIONS,
            _QUARTER_OF_YEAR_LABELS,
            lambda x: x.count().astype(float),
            lambda x: x,
            column_check="activityType",
            activity_type=activity_type,
            start_date=start_date,
            end_date=end_date,
        )

    # ------------------------------------------------------------------
    # Seasonal distance
    # ------------------------------------------------------------------

    def get_distance_by_day_of_week(
        self,
        activity_type: str = "All",
        unit: str = "km",
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
    ) -> dict[str, float]:
        """Return total distance for each day of the week in the specified unit."""
        return self._aggregate_by_seasonal_unit(
            "distance",
            "dayofweek",
            _DAY_OF_WEEK_POSITIONS,
            _DAY_OF_WEEK_LABELS,
            lambda x: x.sum(),
            lambda x: x.div(self._get_length_unit_divisor(unit)),
            activity_type=activity_type,
            start_date=start_date,
            end_date=end_date,
        )

    def get_distance_by_month_of_year(
        self,
        activity_type: str = "All",
        unit: str = "km",
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
    ) -> dict[str, float]:
        """Return total distance for each month of the year in the specified unit."""
        return self._aggregate_by_seasonal_unit(
            "distance",
            "month",
            _MONTH_OF_YEAR_POSITIONS,
            _MONTH_OF_YEAR_LABELS,
            lambda x: x.sum(),
            lambda x: x.div(self._get_length_unit_divisor(unit)),
            activity_type=activity_type,
            start_date=start_date,
            end_date=end_date,
        )

    def get_distance_by_quarter_of_year(
        self,
        activity_type: str = "All",
        unit: str = "km",
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
    ) -> dict[str, float]:
        """Return total distance for each quarter of the year in the specified unit."""
        return self._aggregate_by_seasonal_unit(
            "distance",
            "quarter",
            _QUARTER_OF_YEAR_POSITIONS,
            _QUARTER_OF_YEAR_LABELS,
            lambda x: x.sum(),
            lambda x: x.div(self._get_length_unit_divisor(unit)),
            activity_type=activity_type,
            start_date=start_date,
            end_date=end_date,
        )

    # ------------------------------------------------------------------
    # Seasonal duration
    # ------------------------------------------------------------------

    def get_duration_by_day_of_week(
        self,
        activity_type: str = "All",
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
    ) -> dict[str, float]:
        """Return total duration in hours for each day of the week."""
        return self._aggregate_by_seasonal_unit(
            "duration",
            "dayofweek",
            _DAY_OF_WEEK_POSITIONS,
            _DAY_OF_WEEK_LABELS,
            lambda x: x.sum(),
            lambda x: x.div(3600),
            activity_type=activity_type,
            start_date=start_date,
            end_date=end_date,
        )

    def get_duration_by_month_of_year(
        self,
        activity_type: str = "All",
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
    ) -> dict[str, float]:
        """Return total duration in hours for each month of the year."""
        return self._aggregate_by_seasonal_unit(
            "duration",
            "month",
            _MONTH_OF_YEAR_POSITIONS,
            _MONTH_OF_YEAR_LABELS,
            lambda x: x.sum(),
            lambda x: x.div(3600),
            activity_type=activity_type,
            start_date=start_date,
            end_date=end_date,
        )

    def get_duration_by_quarter_of_year(
        self,
        activity_type: str = "All",
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
    ) -> dict[str, float]:
        """Return total duration in hours for each quarter of the year."""
        return self._aggregate_by_seasonal_unit(
            "duration",
            "quarter",
            _QUARTER_OF_YEAR_POSITIONS,
            _QUARTER_OF_YEAR_LABELS,
            lambda x: x.sum(),
            lambda x: x.div(3600),
            activity_type=activity_type,
            start_date=start_date,
            end_date=end_date,
        )

    # ------------------------------------------------------------------
    # Seasonal calories
    # ------------------------------------------------------------------

    def get_calories_by_day_of_week(
        self,
        activity_type: str = "All",
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
    ) -> dict[str, float]:
        """Return total calories burned for each day of the week."""
        return self._aggregate_by_seasonal_unit(
            "sumActiveEnergyBurned",
            "dayofweek",
            _DAY_OF_WEEK_POSITIONS,
            _DAY_OF_WEEK_LABELS,
            lambda x: x.sum(),
            lambda x: x,
            activity_type=activity_type,
            start_date=start_date,
            end_date=end_date,
        )

    def get_calories_by_month_of_year(
        self,
        activity_type: str = "All",
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
    ) -> dict[str, float]:
        """Return total calories burned for each month of the year."""
        return self._aggregate_by_seasonal_unit(
            "sumActiveEnergyBurned",
            "month",
            _MONTH_OF_YEAR_POSITIONS,
            _MONTH_OF_YEAR_LABELS,
            lambda x: x.sum(),
            lambda x: x,
            activity_type=activity_type,
            start_date=start_date,
            end_date=end_date,
        )

    def get_calories_by_quarter_of_year(
        self,
        activity_type: str = "All",
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
    ) -> dict[str, float]:
        """Return total calories burned for each quarter of the year."""
        return self._aggregate_by_seasonal_unit(
            "sumActiveEnergyBurned",
            "quarter",
            _QUARTER_OF_YEAR_POSITIONS,
            _QUARTER_OF_YEAR_LABELS,
            lambda x: x.sum(),
            lambda x: x,
            activity_type=activity_type,
            start_date=start_date,
            end_date=end_date,
        )
