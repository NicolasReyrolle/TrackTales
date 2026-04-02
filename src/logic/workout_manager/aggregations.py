"""Aggregation and filtering mixin for WorkoutManager."""

from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any, cast

import pandas as pd


class WorkoutManagerAggregationsMixin:
    """Filtering, aggregation, and metric accessors for workout data."""

    workouts: pd.DataFrame
    DEFAULT_EXCLUDED_COLUMNS: set[str]

    def get_activity_types(self) -> list[str]:
        """Return the list of unique activity types."""
        if self.workouts.empty or "activityType" not in self.workouts.columns:
            return []

        result: list[str] = self.workouts["activityType"].dropna().unique().tolist()
        return result

    def _filter_workouts(
        self,
        activity_type: str = "All",
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
    ) -> pd.DataFrame:
        """Filter workouts by activity type and/or date range."""
        workouts: pd.DataFrame = self.workouts

        if activity_type != "All":
            workouts = workouts.loc[workouts["activityType"] == activity_type]

        if "startDate" in workouts.columns:
            if start_date is not None:
                workouts = workouts.loc[workouts["startDate"] >= pd.Timestamp(start_date)]
            if end_date is not None:
                end_timestamp = pd.Timestamp(end_date)
                if self._is_date_only(end_date):
                    next_day = end_timestamp + pd.Timedelta(days=1)
                    workouts = workouts.loc[workouts["startDate"] < next_day]
                else:
                    workouts = workouts.loc[workouts["startDate"] <= end_timestamp]

        return workouts

    @staticmethod
    def _is_date_only(value: datetime | pd.Timestamp) -> bool:
        """Return True when the value represents a date without time-of-day information."""
        timestamp = pd.Timestamp(value)
        return bool(timestamp == timestamp.normalize())

    def _get_filtered_columns(self, exclude_columns: set[str] | None = None) -> list[str]:
        """Return list of columns after applying exclusion filters."""
        excluded = exclude_columns if exclude_columns is not None else self.DEFAULT_EXCLUDED_COLUMNS
        return [col for col in self.workouts.columns if col not in excluded]

    def _get_distance_divisor(self, unit: str) -> float:
        """Get the divisor for distance conversion based on unit."""
        if unit == "km":
            return 1000
        if unit == "m":
            return 1
        if unit == "mi":
            return 1609.34
        if unit == "ft":
            # 1 foot = 0.3048 metres; dividing by 0.3048 converts metres to feet
            return 0.3048
        raise ValueError(f"Unsupported unit: {unit}")

    def _get_aggregate_total(
        self,
        activity_type: str,
        column: str,
        divisor: float = 1.0,
        default: int = 0,
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
    ) -> int:
        """Generic method to calculate total for any column with optional unit conversion."""
        workouts = self._filter_workouts(activity_type, start_date, end_date)
        if column not in workouts.columns:
            return default
        total = workouts[column].sum() / divisor
        return int(round(total))

    def _aggregate_by_activity(
        self,
        column: str,
        aggregation: Callable[[Any], pd.Series],
        transformation: Callable[[pd.Series], pd.Series],
        column_check: str | None = None,
        filter_zeros: bool = True,
        combination_threshold: float = 10.0,
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
    ) -> dict[str, int]:
        """Generic method to aggregate metrics by activity type."""
        column_check = column_check or column
        if "activityType" not in self.workouts.columns or column_check not in self.workouts.columns:
            return {}

        workouts = self._filter_workouts("All", start_date, end_date)

        series_group = workouts.groupby("activityType")[column]
        grouped = aggregation(cast(Any, series_group))
        if grouped.empty:
            return {}

        transformed = transformation(grouped)
        transformed_float = transformed.astype(float)
        result_float: dict[str, float] = {
            str(k): float(v) for k, v in transformed_float.to_dict().items()
        }

        if combination_threshold > 0:
            result_float = self.group_small_values(
                result_float, threshold_percent=combination_threshold
            )

        result: dict[str, int] = {k: int(round(v)) for k, v in result_float.items()}

        if filter_zeros:
            result = {k: v for k, v in result.items() if v > 0}

        return result

    def _aggregate_by_period(
        self,
        column: str,
        period: str,
        aggregation: Callable[[Any], Any],
        transformation: Callable[[pd.Series], pd.Series],
        column_check: str | None = None,
        filter_zeros: bool = True,
        activity_type: str = "All",
        fill_missing_periods: bool = True,
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
    ) -> dict[str, int]:
        """Generic method to aggregate metrics by period."""
        column_check = column_check or column
        if (
            "activityType" not in self.workouts.columns
            or column_check not in self.workouts.columns
            or "startDate" not in self.workouts.columns
        ):
            return {}

        if not pd.api.types.is_datetime64_any_dtype(self.workouts["startDate"]):
            return {}

        workouts = self._filter_workouts(activity_type, start_date, end_date)

        if workouts.empty:
            return {}

        grouped = aggregation(workouts.groupby(workouts["startDate"].dt.to_period(period))[column])

        if grouped.empty:
            return {}

        if fill_missing_periods:
            full_range = pd.period_range(
                start=grouped.index.min(),
                end=grouped.index.max(),
                freq=period,
            )
            grouped = grouped.reindex(full_range, fill_value=0)

        transformed = transformation(grouped)
        transformed_float = transformed.astype(float)
        result_float: dict[str, float] = cast(dict[str, float], transformed_float.to_dict())

        result: dict[str, int] = {str(k): int(round(v)) for k, v in result_float.items()}

        if filter_zeros and not fill_missing_periods:
            result = {k: v for k, v in result.items() if v > 0}

        return result

    def get_count(
        self,
        activity_type: str = "All",
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
    ) -> int:
        """Return the number of workouts."""
        return len(self._filter_workouts(activity_type, start_date, end_date))

    def get_total_distance(
        self,
        activity_type: str = "All",
        unit: str = "km",
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
    ) -> int:
        """Return the total distance optionally per activity_type, and in the given unit."""
        divisor = self._get_distance_divisor(unit)
        return self._get_aggregate_total(
            activity_type, "distance", divisor=divisor, start_date=start_date, end_date=end_date
        )

    def convert_distance(self, unit: str, total_distance_meters: float) -> float:
        """Convert distance in meters to the specified unit."""
        divisor = self._get_distance_divisor(unit)
        return total_distance_meters / divisor

    def get_total_duration(
        self,
        activity_type: str = "All",
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
    ) -> int:
        """Return the total duration of workouts in hours rounded to the nearest integer."""
        return self._get_aggregate_total(
            activity_type, "duration", divisor=3600, start_date=start_date, end_date=end_date
        )

    def get_total_elevation(
        self,
        activity_type: str = "All",
        unit: str = "km",
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
    ) -> int:
        """Return the total elevation gain of workouts in the specified unit."""
        divisor = self._get_distance_divisor(unit)
        return self._get_aggregate_total(
            activity_type,
            "ElevationAscended",
            divisor=divisor,
            start_date=start_date,
            end_date=end_date,
        )

    def get_total_calories(
        self,
        activity_type: str = "All",
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
    ) -> int:
        """Return the total calories burned of workouts."""
        return self._get_aggregate_total(
            activity_type, "sumActiveEnergyBurned", start_date=start_date, end_date=end_date
        )

    def get_calories_by_activity(
        self,
        combination_threshold: float = 10.0,
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
    ) -> dict[str, int]:
        """Return a dictionary mapping activity types to total calories burned."""
        return self._aggregate_by_activity(
            "sumActiveEnergyBurned",
            lambda x: x.sum(),
            lambda x: x,
            combination_threshold=combination_threshold,
            start_date=start_date,
            end_date=end_date,
        )

    def get_calories_by_period(
        self,
        period: str,
        activity_type: str = "All",
        fill_missing_periods: bool = True,
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
    ) -> dict[str, int]:
        """Return a dictionary mapping periods to total calories burned."""
        return self._aggregate_by_period(
            "sumActiveEnergyBurned",
            period,
            lambda x: x.sum(),
            lambda x: x,
            activity_type=activity_type,
            fill_missing_periods=fill_missing_periods,
            start_date=start_date,
            end_date=end_date,
        )

    def get_distance_by_activity(
        self,
        unit: str = "km",
        combination_threshold: float = 10.0,
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
    ) -> dict[str, int]:
        """Return a dictionary mapping activity types to total distance."""
        return self._aggregate_by_activity(
            "distance",
            lambda x: x.sum(),
            lambda x: x.div(self._get_distance_divisor(unit)),
            combination_threshold=combination_threshold,
            start_date=start_date,
            end_date=end_date,
        )

    def get_distance_by_period(
        self,
        period: str,
        activity_type: str = "All",
        unit: str = "km",
        fill_missing_periods: bool = True,
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
    ) -> dict[str, int]:
        """Return a dictionary mapping periods to total distance."""
        return self._aggregate_by_period(
            "distance",
            period,
            lambda x: x.sum(),
            lambda x: x.div(self._get_distance_divisor(unit)),
            filter_zeros=False,
            activity_type=activity_type,
            fill_missing_periods=fill_missing_periods,
            start_date=start_date,
            end_date=end_date,
        )

    def get_count_by_activity(
        self,
        combination_threshold: float = 10.0,
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
    ) -> dict[str, int]:
        """Return a dictionary mapping activity types to workout counts."""
        return self._aggregate_by_activity(
            "activityType",
            lambda x: x.count(),
            lambda x: x,
            column_check="activityType",
            combination_threshold=combination_threshold,
            start_date=start_date,
            end_date=end_date,
        )

    def get_count_by_period(
        self,
        period: str,
        activity_type: str = "All",
        fill_missing_periods: bool = True,
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
    ) -> dict[str, int]:
        """Return a dictionary mapping periods to workout counts."""
        return self._aggregate_by_period(
            "activityType",
            period,
            lambda x: x.count(),
            lambda x: x,
            column_check="activityType",
            activity_type=activity_type,
            fill_missing_periods=fill_missing_periods,
            start_date=start_date,
            end_date=end_date,
        )

    def get_duration_by_activity(
        self,
        combination_threshold: float = 10.0,
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
    ) -> dict[str, int]:
        """Return a dictionary mapping activity types to total duration."""
        return self._aggregate_by_activity(
            "duration",
            lambda x: x.sum(),
            lambda x: x.div(3600),
            combination_threshold=combination_threshold,
            start_date=start_date,
            end_date=end_date,
        )

    def get_duration_by_period(
        self,
        period: str,
        activity_type: str = "All",
        fill_missing_periods: bool = True,
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
    ) -> dict[str, int]:
        """Return a dictionary mapping periods to total duration in hours."""
        return self._aggregate_by_period(
            "duration",
            period,
            lambda x: x.sum(),
            lambda x: x.div(3600),
            activity_type=activity_type,
            fill_missing_periods=fill_missing_periods,
            start_date=start_date,
            end_date=end_date,
        )

    def get_elevation_by_activity(
        self,
        combination_threshold: float = 10.0,
        unit: str = "m",
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
    ) -> dict[str, int]:
        """Return a dictionary mapping activity types to total elevation gain."""
        return self._aggregate_by_activity(
            "ElevationAscended",
            lambda x: x.sum(),
            lambda x: x.div(self._get_distance_divisor(unit)),
            filter_zeros=False,
            combination_threshold=combination_threshold,
            start_date=start_date,
            end_date=end_date,
        )

    def get_elevation_by_period(
        self,
        period: str,
        activity_type: str = "All",
        fill_missing_periods: bool = True,
        unit: str = "m",
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
    ) -> dict[str, int]:
        """Return a dictionary mapping periods to total elevation gain in the specified unit."""
        return self._aggregate_by_period(
            "ElevationAscended",
            period,
            lambda x: x.sum(),
            lambda x: x.div(self._get_distance_divisor(unit)),
            filter_zeros=False,
            activity_type=activity_type,
            fill_missing_periods=fill_missing_periods,
            start_date=start_date,
            end_date=end_date,
        )

    def group_small_values(
        self,
        data: Mapping[str, float],
        threshold_percent: float = 10.0,
        others_label: str = "Others",
    ) -> dict[str, float]:
        """Group smallest values whose cumulative sum is below threshold into a single category."""
        if not data:
            return {}

        total = sum(data.values())

        if total == 0:
            return dict(data)

        threshold_value = total * (threshold_percent / 100.0)

        sorted_items = sorted(data.items(), key=lambda x: x[1])

        result: dict[str, float] = {}
        others_sum = 0.0
        cumulative_sum = 0.0

        for key, value in sorted_items:
            if cumulative_sum + value <= threshold_value:
                others_sum += value
                cumulative_sum += value
            else:
                result[key] = value

        if others_sum > 0:
            result[others_label] = others_sum

        return result

    def get_longest_workout(
        self,
        activity_types: list[str],
        unit: str = "km",
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
    ) -> float:
        """Return the distance of the longest single workout for the given activity types."""
        if (
            self.workouts.empty
            or "distance" not in self.workouts.columns
            or "activityType" not in self.workouts.columns
        ):
            return 0.0

        all_workouts = self._filter_workouts("All", start_date, end_date)
        if all_workouts.empty:
            return 0.0

        filtered = all_workouts[all_workouts["activityType"].isin(activity_types)]
        if filtered.empty:
            return 0.0

        max_distance = filtered["distance"].max()
        if pd.isna(max_distance):
            return 0.0

        divisor = self._get_distance_divisor(unit)
        return float(max_distance) / divisor

    def get_longest_workout_details(
        self,
        activity_types: list[str],
        unit: str = "km",
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
    ) -> dict[str, Any] | None:
        """Return details of the longest single workout for the given activity types.

        Returns a dict with keys ``distance`` (float, in *unit*), ``date`` (Timestamp or ``None``),
        and ``duration`` (float in seconds or ``None``), or ``None`` when no matching workout
        exists.
        """
        if (
            self.workouts.empty
            or "distance" not in self.workouts.columns
            or "activityType" not in self.workouts.columns
        ):
            return None

        all_workouts = self._filter_workouts("All", start_date, end_date)
        if all_workouts.empty:
            return None

        filtered = all_workouts[all_workouts["activityType"].isin(activity_types)]
        if filtered.empty:
            return None

        distance_series = filtered["distance"].dropna()
        if distance_series.empty:
            return None
        idx = distance_series.idxmax()

        row = filtered.loc[[idx]].iloc[0]
        divisor = self._get_distance_divisor(unit)
        raw_distance: float = float(row["distance"])
        raw_duration_val = row["duration"] if "duration" in filtered.columns else None
        raw_duration: float | None = (
            None
            if raw_duration_val is None or pd.isna(raw_duration_val)
            else float(raw_duration_val)
        )
        result: dict[str, Any] = {
            "distance": raw_distance / divisor,
            "date": row["startDate"] if "startDate" in filtered.columns else None,
            "duration": raw_duration,
        }
        return result

    def get_distance_bounds(
        self,
        unit: str = "km",
        activity_type: str = "All",
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
    ) -> tuple[float, float]:
        """Return the minimum and maximum workout distance in the specified unit.

        Returns ``(0.0, 0.0)`` when there are no workouts or no ``distance`` column.
        Only workouts with a positive distance are considered.
        Optionally filters by activity type and date range before computing bounds.
        """
        workouts = self._filter_workouts(activity_type, start_date, end_date)
        if workouts.empty or "distance" not in workouts.columns:
            return 0.0, 0.0
        distances = workouts["distance"].dropna()
        distances = distances[distances > 0]
        if distances.empty:
            return 0.0, 0.0
        divisor = self._get_distance_divisor(unit)
        return float(distances.min()) / divisor, float(distances.max()) / divisor

    def get_duration_bounds(
        self,
        unit: str = "min",
        activity_type: str = "All",
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
    ) -> tuple[float, float]:
        """Return the minimum and maximum workout duration in the specified unit.

        Returns ``(0.0, 0.0)`` when there are no workouts or no ``duration`` column.
        Duration is stored in seconds; supported units are ``"s"``, ``"min"``, ``"h"``.
        Optionally filters by activity type and date range before computing bounds.
        """
        workouts = self._filter_workouts(activity_type, start_date, end_date)
        if workouts.empty or "duration" not in workouts.columns:
            return 0.0, 0.0
        durations = workouts["duration"].dropna()
        durations = durations[durations > 0]
        if durations.empty:
            return 0.0, 0.0
        if unit == "min":
            divisor = 60.0
        elif unit == "h":
            divisor = 3600.0
        elif unit == "s":
            divisor = 1.0
        else:
            raise ValueError(f"Unsupported duration unit: {unit}")
        return float(durations.min()) / divisor, float(durations.max()) / divisor

    def get_workouts(self) -> pd.DataFrame:
        """Return the DataFrame of workouts."""
        return self.workouts
