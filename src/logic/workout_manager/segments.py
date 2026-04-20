"""Best-segment mixin for WorkoutManager."""

import logging
from datetime import datetime
from typing import Any, TypedDict

import pandas as pd

from logic.workout_route import WorkoutRoute

_logger = logging.getLogger(__name__)


class CriticalPowerResult(TypedDict):
    """Result of a critical power calculation for two segment distances."""

    short_distance: int
    long_distance: int
    avg_time_short_s: float
    avg_time_long_s: float
    avg_power_short_w: float
    avg_power_long_w: float
    critical_power_w: float
    w_prime_j: float
    count_short: int
    count_long: int


class WorkoutManagerSegmentsMixin:
    """Best-segment computation methods for running workouts."""

    workouts: pd.DataFrame
    DEFAULT_SEGMENT_DISTANCES: list[int]

    def _filter_workouts(
        self,
        activity_type: str = "All",
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
    ) -> pd.DataFrame:
        """Stub for type checking; implemented in WorkoutManagerAggregationsMixin."""
        raise NotImplementedError

    @staticmethod
    def _split_route_into_traces(route: WorkoutRoute) -> list[WorkoutRoute]:
        """Split a route into monotonic-time traces.

        Segment analysis must not cross timestamp reversals because they indicate
        disjoint windows or malformed ordering.
        """
        if len(route.points) < 2:
            return []

        traces: list[WorkoutRoute] = []
        current_points = [route.points[0]]
        for point in route.points[1:]:
            if point.time < current_points[-1].time:
                if len(current_points) >= 2:
                    traces.append(WorkoutRoute(points=current_points))
                current_points = [point]
                continue
            current_points.append(point)

        if len(current_points) >= 2:
            traces.append(WorkoutRoute(points=current_points))

        return traces

    @classmethod
    def _extract_route_traces(cls, run_record: Any) -> list[WorkoutRoute]:
        """Extract analysis traces from route parts first, then fallback to route."""
        route_parts_obj: Any = (
            run_record.route_parts if hasattr(run_record, "route_parts") else None
        )
        if isinstance(route_parts_obj, list):
            traces: list[WorkoutRoute] = []
            for route_part in route_parts_obj:  # type: ignore[misc]
                if isinstance(route_part, WorkoutRoute):
                    traces.extend(cls._split_route_into_traces(route_part))
            if traces:
                return traces

        route_obj: Any = run_record.route if hasattr(run_record, "route") else None
        if isinstance(route_obj, WorkoutRoute):
            return cls._split_route_into_traces(route_obj)

        return []

    @staticmethod
    def _empty_best_segments_frame() -> pd.DataFrame:
        """Return an empty DataFrame with the stable best-segment schema."""
        return pd.DataFrame(
            columns=[
                "startDate",
                "distance",
                "duration_s",
                "segment_start",
                "segment_end",
                "elevation_change_m",
            ]
        )

    @staticmethod
    def _get_run_distance_m(run_record: Any) -> float | None:
        """Return the run distance in meters when present and finite."""
        raw_run_distance: Any = getattr(run_record, "distance", None)
        if raw_run_distance is None or pd.isna(raw_run_distance):
            return None
        return float(raw_run_distance)

    @staticmethod
    def _build_best_segments_frame(results: list[list[Any]], topn: int) -> pd.DataFrame:
        """Sort and keep the fastest Top-N segments per requested distance."""
        df = pd.DataFrame(
            results,
            columns=[
                "startDate",
                "distance",
                "duration_s",
                "segment_start",
                "segment_end",
                "elevation_change_m",
            ],
        )
        df = df.sort_values(["distance", "duration_s"], ascending=[True, True])
        result: pd.DataFrame = df.groupby("distance").head(topn).reset_index(drop=True)
        return result

    @staticmethod
    def _get_fastest_segment_window(
        route_traces: list[WorkoutRoute],
        distance_m: float,
        distance_scale_factor: float,
    ) -> tuple[float, datetime, datetime, float] | None:
        """Return (duration_s, start_time, end_time, elevation_change_m)
        for the fastest segment across traces."""
        best: tuple[float, datetime, datetime, float] | None = None
        for route_trace in route_traces:
            result = route_trace.find_fastest_segment_window(
                distance_m,
                distance_scale_factor=distance_scale_factor,
            )
            if result is not None and (best is None or result[0] < best[0]):
                best = result
        return best

    def _get_run_best_segment_rows(
        self,
        run_record: Any,
        distances: list[int],
    ) -> list[list[Any]]:
        """Collect best-segment result rows for one running workout."""
        route_traces = self._extract_route_traces(run_record)
        if not route_traces:
            return []

        run_distance_m = self._get_run_distance_m(run_record)
        total_trace_distance_m = sum(route_trace.distance_meters for route_trace in route_traces)
        distance_scale_factor = WorkoutRoute.calculate_distance_scale_factor(
            total_trace_distance_m,
            run_distance_m,
        )

        rows: list[list[Any]] = []
        for distance in distances:
            if run_distance_m is not None and float(distance) > run_distance_m:
                continue

            window = self._get_fastest_segment_window(
                route_traces,
                float(distance),
                distance_scale_factor,
            )
            if window is None:
                continue

            duration_s, seg_start, seg_end, elevation_change_m = window
            rows.append(
                [run_record.startDate, distance, duration_s, seg_start, seg_end, elevation_change_m]
            )

        return rows

    def _fallback_filter_running_workouts(
        self,
        start_date: datetime | pd.Timestamp | None,
        end_date: datetime | pd.Timestamp | None,
    ) -> pd.DataFrame:
        """Fallback: filter running workouts with local logic and end-date handling."""
        runs: pd.DataFrame = self.workouts[self.workouts["activityType"] == "Running"]
        if start_date is not None:
            runs = runs.loc[runs["startDate"] >= pd.Timestamp(start_date)]
        if end_date is not None:
            end_ts = pd.Timestamp(end_date)
            is_date_only = end_ts.normalize() == end_ts
            if is_date_only:
                runs = runs.loc[runs["startDate"] < end_ts + pd.Timedelta(days=1)]
            else:
                runs = runs.loc[runs["startDate"] <= end_ts]
        return runs

    def get_best_segments(
        self,
        topn: int = 5,
        distances: list[int] | None = None,
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
    ) -> pd.DataFrame:
        """Return a DataFrame of best segments across all running workouts for a defined list of
        distances for the Top-N values of each segment distance.
        The segments are defined as the fastest time for a given distance
        Args:
            topn: Number of top segments to return for each distance
            distances: List of distances (in meters) to consider for segment analysis
                (defaults to DEFAULT_SEGMENT_DISTANCES)
            start_date: Optional start date to filter workouts
            end_date: Optional end date to filter workouts (inclusive)

        Returns:
            DataFrame with columns:
                - startDate
                - distance
                - duration_s
                - segment_start
                - segment_end
                - elevation_change_m
                Empty when no valid segments are found or workouts are missing
        """
        if distances is None:
            distances = self.DEFAULT_SEGMENT_DISTANCES

        if topn <= 0:
            return self._empty_best_segments_frame()

        required_columns = {"activityType", "startDate"}
        if not required_columns.issubset(self.workouts.columns):
            return self._empty_best_segments_frame()

        # Prefer shared filtering logic from WorkoutManagerAggregationsMixin to keep
        # date-handling semantics consistent across APIs.
        if hasattr(self, "_filter_workouts"):
            runs = self._filter_workouts("Running", start_date, end_date)
        else:
            runs = self._fallback_filter_running_workouts(start_date, end_date)

        if runs.empty:
            return self._empty_best_segments_frame()

        results: list[list[Any]] = []

        for run in runs.itertuples():
            results.extend(self._get_run_best_segment_rows(run, distances))

        if not results:
            return self._empty_best_segments_frame()

        return self._build_best_segments_frame(results, topn)

    @staticmethod
    def _compute_measured_segment_power(
        rp_times: pd.Series,
        rp_values: pd.Series,
        seg_start_ts: pd.Timestamp,
        seg_end_ts: pd.Timestamp,
    ) -> float | None:
        """Compute mean power from records whose startDate falls within segment bounds."""
        mask = (rp_times >= seg_start_ts) & (rp_times <= seg_end_ts) & rp_values.notna()
        vals = rp_values[mask]
        if vals.empty:
            return None
        return float(vals.mean())

    @staticmethod
    def _compute_overlap_estimated_power(
        rp_times: pd.Series,
        rp_end_times: pd.Series,
        rp_values: pd.Series,
        seg_start_ts: pd.Timestamp,
        seg_end_ts: pd.Timestamp,
    ) -> tuple[float, int, float] | None:
        """Estimate power from overlap duration between power intervals and segment window."""
        overlap_mask = (rp_times <= seg_end_ts) & (rp_end_times >= seg_start_ts) & rp_values.notna()
        if not overlap_mask.any():
            return None

        overlap_start_raw = rp_times[overlap_mask]
        overlap_end_raw = rp_end_times[overlap_mask]
        overlap_start = overlap_start_raw.where(overlap_start_raw >= seg_start_ts, seg_start_ts)
        overlap_end = overlap_end_raw.where(overlap_end_raw <= seg_end_ts, seg_end_ts)
        overlap_seconds = (overlap_end - overlap_start).dt.total_seconds()
        positive_overlap = overlap_seconds > 0
        if not positive_overlap.any():
            return None

        overlap_values = rp_values[overlap_mask][positive_overlap]
        overlap_weights = overlap_seconds[positive_overlap]
        total_weight = float(overlap_weights.sum())
        if total_weight <= 0:
            return None

        weighted_sum = float((overlap_values * overlap_weights).sum())
        return (weighted_sum / total_weight, int(positive_overlap.sum()), total_weight)

    @staticmethod
    def _prepare_running_power_series(
        running_power_df: pd.DataFrame | None,
    ) -> tuple[pd.Series | None, pd.Series | None, pd.Series | None]:
        """Parse running power records into typed series for segment matching."""
        if (
            running_power_df is None
            or running_power_df.empty
            or "startDate" not in running_power_df.columns
            or "value" not in running_power_df.columns
        ):
            return None, None, None

        rp_times = pd.to_datetime(running_power_df["startDate"], format="ISO8601", errors="coerce")
        rp_end_times: pd.Series | None = None
        if "endDate" in running_power_df.columns:
            rp_end_times = pd.to_datetime(
                running_power_df["endDate"], format="ISO8601", errors="coerce"
            )
        rp_values = pd.to_numeric(running_power_df["value"], errors="coerce")
        return rp_times, rp_end_times, rp_values

    def _build_workout_fallback_power(self) -> dict[Any, float | None]:
        """Build workout-level fallback lookup: startDate -> averageRunningPower."""
        fallback: dict[Any, float | None] = {}
        avg_power_col = "averageRunningPower"
        for workout in self.workouts.itertuples():
            workout_start = getattr(workout, "startDate", None)
            raw_power = (
                getattr(workout, avg_power_col, None)
                if avg_power_col in self.workouts.columns
                else None
            )
            fallback[workout_start] = (
                float(raw_power) if raw_power is not None and not pd.isna(raw_power) else None
            )
        return fallback

    def _compute_segment_power_and_confidence(
        self,
        row: Any,
        power_series: tuple[pd.Series | None, pd.Series | None, pd.Series | None],
        workout_fallback: dict[Any, float | None],
    ) -> tuple[float | None, str]:
        """Compute power value and confidence for one segment row."""
        rp_times, rp_end_times, rp_values = power_series
        seg_start = getattr(row, "segment_start", None)
        seg_end = getattr(row, "segment_end", None)
        workout_start = getattr(row, "startDate", None)

        power, confidence = self._compute_power_from_records(
            row,
            workout_start,
            seg_start,
            seg_end,
            rp_times,
            rp_end_times,
            rp_values,
        )

        if power is None:
            workout_avg_power = workout_fallback.get(workout_start)
            if workout_avg_power is not None:
                power = workout_avg_power
                confidence = "workout_fallback"

        _logger.debug(
            "Segment power computed "
            "(workout_start=%s distance=%sm duration_s=%.2f power=%s confidence=%s)",
            workout_start,
            getattr(row, "distance", None),
            float(getattr(row, "duration_s", 0.0)),
            power,
            confidence,
        )
        return power, confidence

    def _compute_power_from_records(
        self,
        row: Any,
        workout_start: Any,
        seg_start: Any,
        seg_end: Any,
        rp_times: pd.Series | None,
        rp_end_times: pd.Series | None,
        rp_values: pd.Series | None,
    ) -> tuple[float | None, str]:
        """Compute power from running-power records only (measured or overlap-estimated)."""
        if rp_times is None or rp_values is None or seg_start is None or seg_end is None:
            return None, "missing"

        seg_start_ts = pd.Timestamp(seg_start)
        seg_end_ts = pd.Timestamp(seg_end)
        measured_power = self._compute_measured_segment_power(
            rp_times,
            rp_values,
            seg_start_ts,
            seg_end_ts,
        )
        if measured_power is not None:
            return measured_power, "measured"

        _logger.debug(
            "No measured RunningPower samples matched segment window "
            "(workout_start=%s distance=%sm segment_start=%s segment_end=%s)",
            workout_start,
            getattr(row, "distance", None),
            seg_start_ts,
            seg_end_ts,
        )

        if rp_end_times is None:
            return None, "missing"

        lengths_match = len(rp_end_times) == len(rp_times) and len(rp_values) == len(rp_times)
        if not lengths_match:
            return None, "missing"

        overlap_estimate = self._compute_overlap_estimated_power(
            rp_times,
            rp_end_times,
            rp_values,
            seg_start_ts,
            seg_end_ts,
        )
        if overlap_estimate is None:
            return None, "missing"

        overlap_power, overlap_count, overlap_total_s = overlap_estimate
        _logger.debug(
            "Using overlap-estimated RunningPower "
            "(workout_start=%s distance=%sm records=%s overlap_s=%.2f)",
            workout_start,
            getattr(row, "distance", None),
            overlap_count,
            overlap_total_s,
        )
        return overlap_power, "overlap_estimated"

    def annotate_segments_with_power(
        self,
        segments: pd.DataFrame,
        running_power_df: pd.DataFrame | None,
    ) -> pd.DataFrame:
        """Add ``segment_avg_power`` column to a best-segments DataFrame.

        Power for each segment is determined with the following priority:

        1. **Individual records**: mean value of ``HKQuantityTypeIdentifierRunningPower``
           records whose ``startDate`` falls within ``[segment_start, segment_end]``.
          2. **Overlap-estimated**: weighted estimate from overlapping
              ``RunningPower`` interval records (requires both ``startDate`` and ``endDate``).
          3. **Workout-level fallback**: ``averageRunningPower`` from workout statistics.
        4. ``None`` when neither source provides usable data.

        Args:
            segments: DataFrame returned by :meth:`get_best_segments` (must have
                ``startDate``, ``duration_s``, ``segment_start``, ``segment_end``).
            running_power_df: Optional DataFrame of individual ``RunningPower`` records
                with columns ``startDate`` (raw ISO-8601 string) and ``value`` (float W).

        Returns:
            Copy of *segments* with an additional ``segment_avg_power`` column
            (float Watts, or ``None``) and ``segment_power_confidence`` with one of:
            ``measured``, ``overlap_estimated``, ``workout_fallback``, ``missing``.
        """
        result: pd.DataFrame = segments.copy()
        if segments.empty or "segment_start" not in segments.columns:
            result["segment_avg_power"] = None
            result["segment_power_confidence"] = "missing"
            return result

        power_series = self._prepare_running_power_series(running_power_df)
        workout_fallback = self._build_workout_fallback_power()

        avg_powers: list[float | None] = []
        confidences: list[str] = []
        for row in segments.itertuples():
            power, confidence = self._compute_segment_power_and_confidence(
                row,
                power_series,
                workout_fallback,
            )
            avg_powers.append(power)
            confidences.append(confidence)

        result["segment_avg_power"] = avg_powers
        result["segment_power_confidence"] = confidences
        return result

    def get_critical_power(
        self,
        running_power_df: pd.DataFrame | None = None,
        topn: int = 5,
        short_distance: int = 800,
        long_distance: int = 5000,
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
    ) -> CriticalPowerResult | None:
        """Compute Critical Power (CP) and W' using the 2-parameter power-duration model.

        The model fits a linear work-time relationship:
            W = CP * t + W'
        where W = P_avg * t is the total work done (Joules), CP is the maximum sustainable
        power (Watts), and W' is the anaerobic work capacity (Joules).

        Per-segment average power is derived from individual ``RunningPower`` health
        records within the segment GPS time window (see :meth:`annotate_segments_with_power`).

        Args:
            running_power_df: DataFrame of individual ``HKQuantityTypeIdentifierRunningPower``
                records (columns ``startDate``, ``value``). Pass
                ``records_by_type.get("RunningPower")`` from the app state.
            topn: Number of best segments to average per distance (default 5).
            short_distance: Shorter target distance in metres (default 800).
            long_distance: Longer target distance in metres (default 5000).
            start_date: Optional start date filter applied to workouts.
            end_date: Optional end date filter applied to workouts (inclusive).

        Returns:
            A :class:`CriticalPowerResult` dict, or ``None`` when either distance
            has no matching segments with power data, or the model yields non-physical
            values (CP ≤ 0 or W' ≤ 0), or the two distances are equal.
        """
        if short_distance >= long_distance:
            return None

        segments = self.get_best_segments(
            topn=topn,
            distances=[short_distance, long_distance],
            start_date=start_date,
            end_date=end_date,
        )

        if segments.empty:
            return None

        segments = self.annotate_segments_with_power(segments, running_power_df)

        short_rows = segments[
            (segments["distance"] == short_distance) & segments["segment_avg_power"].notna()
        ]
        long_rows = segments[
            (segments["distance"] == long_distance) & segments["segment_avg_power"].notna()
        ]

        if short_rows.empty or long_rows.empty:
            return None

        avg_time_short = float(short_rows["duration_s"].mean())
        avg_time_long = float(long_rows["duration_s"].mean())
        avg_power_short = float(short_rows["segment_avg_power"].mean())
        avg_power_long = float(long_rows["segment_avg_power"].mean())

        time_diff = avg_time_long - avg_time_short
        if time_diff <= 0:
            return None

        work_short = avg_power_short * avg_time_short  # Joules
        work_long = avg_power_long * avg_time_long  # Joules

        critical_power_w = (work_long - work_short) / time_diff
        w_prime_j = work_short - critical_power_w * avg_time_short

        if critical_power_w <= 0 or w_prime_j <= 0:
            return None

        return CriticalPowerResult(
            short_distance=short_distance,
            long_distance=long_distance,
            avg_time_short_s=avg_time_short,
            avg_time_long_s=avg_time_long,
            avg_power_short_w=avg_power_short,
            avg_power_long_w=avg_power_long,
            critical_power_w=critical_power_w,
            w_prime_j=w_prime_j,
            count_short=len(short_rows),
            count_long=len(long_rows),
        )

    def get_critical_power_evolution(
        self,
        running_power_df: pd.DataFrame | None = None,
        period: str = "M",
        short_distance: int = 800,
        long_distance: int = 5000,
        topn: int = 5,
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
    ) -> pd.DataFrame:
        """Compute Critical Power (CP) and W' for each time period.

        For each period (e.g. month), the top-N best segments for both distances
        that fall within that period are averaged to derive one (CP, W') data point.
        Periods with insufficient segment data for either distance are retained in
        the result with ``NaN``/``None`` metric values to create gaps in charts.
        Periods between the first and last period with any valid data are also
        included (and will have ``NaN``/``None`` values if they lack sufficient
        segment data).

        Args:
            running_power_df: DataFrame of individual ``HKQuantityTypeIdentifierRunningPower``
                records (columns ``startDate``, ``value``). Pass
                ``records_by_type.get("RunningPower")`` from the app state.
            period: Pandas period alias (e.g. ``"M"`` monthly, ``"Q"`` quarterly,
                ``"Y"`` yearly).  Must match the ``trends_period`` codes used
                elsewhere in the app.
            short_distance: Shorter target distance in metres (default 800).
            long_distance: Longer target distance in metres (default 5000).
            topn: Number of best segments to include per distance per period.
            start_date: Optional start date filter.
            end_date: Optional end date filter (inclusive).

        Returns:
            DataFrame with columns ``period`` (str), ``critical_power_w`` (float),
            ``w_prime_kj`` (float).  Periods without sufficient data will still be
            present but have ``NaN``/``None`` for these metrics. Empty if there is
            no data in any period.
        """
        _empty = pd.DataFrame(columns=["period", "critical_power_w", "w_prime_kj"])

        if short_distance >= long_distance:
            return _empty

        # Build available periods from filtered running workouts.
        if hasattr(self, "_filter_workouts"):
            runs = self._filter_workouts("Running", start_date, end_date)
        else:
            runs = self._fallback_filter_running_workouts(start_date, end_date)

        if runs.empty:
            return _empty

        runs_tz = (
            runs["startDate"].dt.tz
            if isinstance(runs["startDate"].dtype, pd.DatetimeTZDtype)
            else None
        )
        run_dates = (
            runs["startDate"].dt.tz_localize(None)
            if isinstance(runs["startDate"].dtype, pd.DatetimeTZDtype)
            else runs["startDate"]
        )
        period_keys = run_dates.dt.to_period(period).dropna().sort_values().unique()

        results: list[dict[str, object]] = []
        for period_key in period_keys:
            period_start = period_key.start_time
            period_end = period_key.end_time
            if runs_tz is not None:
                period_start = period_start.tz_localize(runs_tz)
                period_end = period_end.tz_localize(runs_tz)
            cp_result = self.get_critical_power(
                running_power_df=running_power_df,
                topn=topn,
                short_distance=short_distance,
                long_distance=long_distance,
                start_date=period_start,
                end_date=period_end,
            )
            if cp_result is None:
                results.append(
                    {
                        "period": str(period_key),
                        "critical_power_w": None,
                        "w_prime_kj": None,
                    }
                )
                continue

            results.append(
                {
                    "period": str(period_key),
                    "critical_power_w": round(float(cp_result["critical_power_w"]), 1),
                    "w_prime_kj": round(float(cp_result["w_prime_j"]) / 1000, 2),
                }
            )

        if not results:
            return _empty

        # Keep interior None periods as chart gaps, but drop leading/trailing ones.
        # Also fill months with zero workouts that fall between the first and last valid month.
        valid_periods = sorted(
            str(result["period"]) for result in results if result["critical_power_w"] is not None
        )
        if not valid_periods:
            return _empty

        results_by_period: dict[str, dict[str, object]] = {
            str(result["period"]): result for result in results
        }
        full_range = pd.period_range(valid_periods[0], valid_periods[-1], freq=period)
        filled: list[dict[str, object]] = [
            results_by_period.get(
                str(pk),
                {"period": str(pk), "critical_power_w": None, "w_prime_kj": None},
            )
            for pk in full_range
        ]
        return pd.DataFrame(filled)
