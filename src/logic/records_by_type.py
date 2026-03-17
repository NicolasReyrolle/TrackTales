"""Logic for working with HealthKit records grouped by type."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

import pandas as pd


@dataclass(frozen=True)
class RecordsByType:
    """Thin wrapper around raw record DataFrames grouped by HealthKit type."""

    data: dict[str, pd.DataFrame]

    HEART_RATE_TYPE = "HeartRate"
    BODY_MASS_TYPE = "BodyMass"
    VO2_MAX_TYPE = "VO2Max"

    class HeartRateMeasureContext(Enum):
        """Context of a heart rate measurement."""

        UNKNOWN = 0
        SEDENTARY = 1
        ACTIVE = 2

    def get(self, record_type: str) -> pd.DataFrame:
        """Return DataFrame for a HealthKit type, or empty DataFrame."""
        return self.data.get(record_type, pd.DataFrame())

    def heart_rate(self) -> pd.DataFrame:
        """Return DataFrame for heart rate records."""
        return self.get(self.HEART_RATE_TYPE)

    def weight(self) -> pd.DataFrame:
        """Return DataFrame for weight records."""
        return self.get(self.BODY_MASS_TYPE)

    def vo2_max(self) -> pd.DataFrame:
        """Return DataFrame for VO2 max records."""
        return self.get(self.VO2_MAX_TYPE)

    def stats_by_period(
        self,
        record_type: str,
        period: str = "M",
        value_col: str = "value",
        date_col: str = "startDate",
        query_filter: str | None = None,
        round_decimals: int = 2,
        fill_missing_periods: bool = True,
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
    ) -> pd.DataFrame:
        """Aggregate avg/min/max/count by period for one record type."""
        df = self.get(record_type)
        if df.empty or value_col not in df.columns or date_col not in df.columns:
            return pd.DataFrame(columns=["period", "avg", "min", "max", "count"])

        if query_filter:
            df = df.query(query_filter)

        if df.empty:
            return pd.DataFrame(columns=["period", "avg", "min", "max", "count"])

        work = df[[date_col, value_col]].copy()
        # Parse dates using the ISO8601 parser to avoid per-row inference warnings.
        work[date_col] = pd.to_datetime(work[date_col], format="ISO8601", errors="coerce")
        if isinstance(work[date_col].dtype, pd.DatetimeTZDtype):
            work[date_col] = work[date_col].dt.tz_localize(None)
        work[value_col] = pd.to_numeric(work[value_col], errors="coerce")
        work = work.dropna(subset=[date_col, value_col])

        if start_date is not None:
            work = work[work[date_col] >= pd.Timestamp(start_date)]
        if end_date is not None:
            end_ts = pd.Timestamp(end_date)
            # Distinguish between date-only and datetime-with-time bounds.
            # For date-only (e.g. from a date picker), include the full day by using an
            # exclusive next-day boundary. For datetimes with a time component, treat the
            # bound as an exact timestamp and include records up to and including end_ts.
            has_time_component = False
            if isinstance(end_date, pd.Timestamp):
                has_time_component = any(
                    getattr(end_date, attr) != 0
                    for attr in ("hour", "minute", "second", "microsecond", "nanosecond")
                )
            else:
                has_time_component = any(
                    getattr(end_date, attr) != 0
                    for attr in ("hour", "minute", "second", "microsecond")
                )
            if has_time_component:
                work = work[work[date_col] <= end_ts]
            else:
                next_day = end_ts + pd.Timedelta(days=1)
                work = work[work[date_col] < next_day]

        if work.empty:
            return pd.DataFrame(columns=["period", "avg", "min", "max", "count"])

        result: pd.DataFrame = (
            work.groupby(work[date_col].dt.to_period(period))[value_col]
            .agg(avg="mean", min="min", max="max", count="count")
            .reset_index()
            .rename(columns={date_col: "period"})
            .sort_values("period")
        )
        result[["avg", "min", "max"]] = result[["avg", "min", "max"]].round(round_decimals)

        # Add missing periods while preserving missing metric values (None)
        if fill_missing_periods:
            full_range = pd.period_range(
                start=result["period"].min(),
                end=result["period"].max(),
                freq=period,
            )
            result = (
                result.set_index("period").reindex(full_range).rename_axis("period").reset_index()
            )
            cols = ["avg", "min", "max"]
            result.loc[:, cols] = result.loc[:, cols].astype("Float64")

            result["count"] = result["count"].fillna(0)
            result["count"] = result["count"].astype(int)

        return result

    def heart_rate_stats(
        self,
        period: str = "M",
        context: HeartRateMeasureContext | None = None,
        round_decimals: int = 2,
        fill_missing_periods: bool = True,
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
    ) -> pd.DataFrame:
        """Return aggregated heart rate stats by period."""
        heart_rate_df = self.heart_rate()
        query_filter = None
        if context is not None and "HeartRateMotionContext" in heart_rate_df.columns:
            query_filter = f"HeartRateMotionContext == {context.value}"

        return self.stats_by_period(
            self.HEART_RATE_TYPE,
            period=period,
            query_filter=query_filter,
            round_decimals=round_decimals,
            fill_missing_periods=fill_missing_periods,
            start_date=start_date,
            end_date=end_date,
        )

    def weight_stats(
        self,
        period: str = "M",
        round_decimals: int = 2,
        fill_missing_periods: bool = True,
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
    ) -> pd.DataFrame:
        """Return aggregated weight stats by period."""
        return self.stats_by_period(
            self.BODY_MASS_TYPE,
            period=period,
            round_decimals=round_decimals,
            fill_missing_periods=fill_missing_periods,
            start_date=start_date,
            end_date=end_date,
        )

    def vo2_max_stats(
        self,
        period: str = "M",
        round_decimals: int = 2,
        fill_missing_periods: bool = True,
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
    ) -> pd.DataFrame:
        """Return aggregated VO2 max stats by period."""
        return self.stats_by_period(
            self.VO2_MAX_TYPE,
            period=period,
            round_decimals=round_decimals,
            fill_missing_periods=fill_missing_periods,
            start_date=start_date,
            end_date=end_date,
        )
