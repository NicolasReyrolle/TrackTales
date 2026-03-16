"""Tests for WorkoutManager.get_critical_power and get_critical_power_evolution."""

from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd
import pytest

from logic.workout_manager import WorkoutManager
from logic.workout_route import RoutePoint, WorkoutRoute


class TestGetCriticalPower:
    """Test suite for WorkoutManager.get_critical_power."""

    @staticmethod
    def _make_route(
        start_time: datetime, distance_m: float, duration_s: float, end_lon: float
    ) -> WorkoutRoute:
        speed = distance_m / duration_s
        return WorkoutRoute(
            points=[
                RoutePoint(time=start_time, latitude=0.0, longitude=0.0, altitude=0.0, speed=speed),
                RoutePoint(
                    time=start_time + timedelta(seconds=duration_s),
                    latitude=0.0,
                    longitude=end_lon,
                    altitude=0.0,
                    speed=speed,
                ),
            ]
        )

    @staticmethod
    def _rp_df(start_time: datetime, duration_s: float, power_w: float) -> pd.DataFrame:
        """RunningPower record placed in the middle of the segment window."""
        mid = start_time + timedelta(seconds=duration_s / 2)
        return pd.DataFrame(
            {"startDate": [mid.strftime("%Y-%m-%dT%H:%M:%S+00:00")], "value": [power_w]}
        )

    def test_returns_none_for_empty_manager(self) -> None:
        """No workouts should return None."""
        assert WorkoutManager().get_critical_power() is None

    def test_returns_none_when_no_power_data(self) -> None:
        """Return None when neither individual records nor workout stats are available."""
        t800 = datetime(2025, 1, 1, tzinfo=timezone.utc)
        t5000 = datetime(2025, 2, 1, tzinfo=timezone.utc)
        manager = WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running"],
                    "startDate": [pd.Timestamp("2025-01-01"), pd.Timestamp("2025-02-01")],
                    "distance": [800.0, 5000.0],
                    "route": [
                        self._make_route(t800, 800.0, 160.0, 0.007),
                        self._make_route(t5000, 5000.0, 1250.0, 0.045),
                    ],
                }
            )
        )

        assert manager.get_critical_power() is None

    def test_returns_none_when_short_distance_missing(self) -> None:
        """Return None when no best segment exists for the short distance."""
        t = datetime(2025, 1, 1, tzinfo=timezone.utc)
        route = self._make_route(t, 5000.0, 1500.0, 0.045)
        rp_df = self._rp_df(t, 1500.0, 250.0)
        manager = WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "startDate": [pd.Timestamp("2025-01-01")],
                    "distance": [5000.0],
                    "route": [route],
                }
            )
        )

        assert (
            manager.get_critical_power(
                running_power_df=rp_df, short_distance=10000, long_distance=50000
            )
            is None
        )

    def test_returns_none_when_short_ge_long(self) -> None:
        """Return None for degenerate distance inputs."""
        manager = WorkoutManager()
        assert manager.get_critical_power(short_distance=800, long_distance=800) is None
        assert manager.get_critical_power(short_distance=5000, long_distance=800) is None

    def test_critical_power_formula_with_individual_records(self) -> None:
        """CP and W' computed from individual RunningPower records within segment windows."""
        time_800 = 160
        power_800 = 350.0
        time_5000 = 1250
        power_5000 = 250.0
        t800 = datetime(2025, 1, 1, tzinfo=timezone.utc)
        t5000 = datetime(2025, 2, 1, tzinfo=timezone.utc)

        manager = WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running"],
                    "startDate": [pd.Timestamp("2025-01-01"), pd.Timestamp("2025-02-01")],
                    "distance": [800.0, 5000.0],
                    "route": [
                        self._make_route(t800, 800.0, float(time_800), 0.007),
                        self._make_route(t5000, 5000.0, float(time_5000), 0.045),
                    ],
                }
            )
        )

        # Build a combined RunningPower records DataFrame with one record per segment
        rp_df = pd.concat(
            [
                self._rp_df(t800, float(time_800), power_800),
                self._rp_df(t5000, float(time_5000), power_5000),
            ],
            ignore_index=True,
        )

        result = manager.get_critical_power(
            running_power_df=rp_df, topn=1, short_distance=800, long_distance=5000
        )

        assert result is not None
        assert result["short_distance"] == 800
        assert result["long_distance"] == 5000
        assert result["avg_time_short_s"] == pytest.approx(time_800)  # type: ignore[misc]
        assert result["avg_time_long_s"] == pytest.approx(time_5000)  # type: ignore[misc]
        assert result["avg_power_short_w"] == pytest.approx(power_800)  # type: ignore[misc]
        assert result["avg_power_long_w"] == pytest.approx(power_5000)  # type: ignore[misc]
        work_short = power_800 * time_800
        work_long = power_5000 * time_5000
        expected_cp = (work_long - work_short) / (time_5000 - time_800)
        expected_w_prime = work_short - expected_cp * time_800
        assert result["critical_power_w"] == pytest.approx(expected_cp)  # type: ignore[misc]
        assert result["w_prime_j"] == pytest.approx(expected_w_prime)  # type: ignore[misc]
        assert result["count_short"] == 1
        assert result["count_long"] == 1

    def test_fallback_to_workout_stats_when_workout_is_the_segment(self) -> None:
        """Workout-level avg power is used when workout duration ≈ segment duration."""
        time_800 = 160
        time_5000 = 1250
        t800 = datetime(2025, 1, 1, tzinfo=timezone.utc)
        t5000 = datetime(2025, 2, 1, tzinfo=timezone.utc)

        manager = WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running"],
                    "startDate": [pd.Timestamp("2025-01-01"), pd.Timestamp("2025-02-01")],
                    "distance": [800.0, 5000.0],
                    # duration ≈ segment duration (within 10%)
                    "duration": [float(time_800), float(time_5000)],
                    "averageRunningPower": [350.0, 250.0],
                    "route": [
                        self._make_route(t800, 800.0, float(time_800), 0.007),
                        self._make_route(t5000, 5000.0, float(time_5000), 0.045),
                    ],
                }
            )
        )

        # No individual records, but workout duration ≈ segment → fallback applies
        result = manager.get_critical_power(
            running_power_df=None, topn=1, short_distance=800, long_distance=5000
        )

        assert result is not None
        assert result["avg_power_short_w"] == pytest.approx(350.0, rel=0.01)  # type: ignore[misc]
        assert result["avg_power_long_w"] == pytest.approx(250.0, rel=0.01)  # type: ignore[misc]


class TestGetCriticalPowerEvolution:
    """Test suite for WorkoutManager.get_critical_power_evolution."""

    @staticmethod
    def _make_route(
        start_time: datetime, distance_m: float, duration_s: float, end_lon: float
    ) -> WorkoutRoute:
        speed = distance_m / duration_s
        return WorkoutRoute(
            points=[
                RoutePoint(time=start_time, latitude=0.0, longitude=0.0, altitude=0.0, speed=speed),
                RoutePoint(
                    time=start_time + timedelta(seconds=duration_s),
                    latitude=0.0,
                    longitude=end_lon,
                    altitude=0.0,
                    speed=speed,
                ),
            ]
        )

    @staticmethod
    def _rp_record(start_time: datetime, duration_s: float, power_w: float) -> dict[str, Any]:
        mid = start_time + timedelta(seconds=duration_s / 2)
        return {"startDate": mid.strftime("%Y-%m-%dT%H:%M:%S+00:00"), "value": power_w}

    def test_returns_empty_for_empty_manager(self) -> None:
        """No workouts returns an empty DataFrame with expected columns."""
        result = WorkoutManager().get_critical_power_evolution()
        assert result.empty
        assert list(result.columns) == ["period", "critical_power_w", "w_prime_kj"]

    def test_returns_empty_when_no_power_data(self) -> None:
        """Periods with insufficient data to compute CP produce no output rows."""
        t = datetime(2025, 1, 1, tzinfo=timezone.utc)
        route = self._make_route(t, 800.0, 160.0, 0.007)
        manager = WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "startDate": [pd.Timestamp("2025-01-01")],
                    "distance": [800.0],
                    "route": [route],
                }
            )
        )

        result = manager.get_critical_power_evolution()
        assert result.empty
        assert list(result.columns) == ["period", "critical_power_w", "w_prime_kj"]

    def test_evolution_groups_by_period(self) -> None:
        """Each calendar period with both distances produces one CP/W' row."""
        data = [
            (datetime(2025, 1, 5, tzinfo=timezone.utc), 800.0, 160.0, 0.007, 350.0),
            (datetime(2025, 1, 20, tzinfo=timezone.utc), 5000.0, 1250.0, 0.045, 250.0),
            (datetime(2025, 2, 5, tzinfo=timezone.utc), 800.0, 155.0, 0.007, 360.0),
            (datetime(2025, 2, 20, tzinfo=timezone.utc), 5000.0, 1200.0, 0.045, 260.0),
        ]
        manager = WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"] * 4,
                    "startDate": [pd.Timestamp(dt) for dt, *_ in data],
                    "distance": [d for _, d, *_ in data],
                    "route": [
                        self._make_route(dt, dist, dur, lon) for dt, dist, dur, lon, _ in data
                    ],
                }
            )
        )
        rp_df = pd.DataFrame([self._rp_record(dt, dur, pwr) for dt, _, dur, _, pwr in data])

        result = manager.get_critical_power_evolution(running_power_df=rp_df, period="M")

        assert len(result) == 2
        assert list(result.columns) == ["period", "critical_power_w", "w_prime_kj"]
        assert all(result["critical_power_w"] > 0)
        assert all(result["w_prime_kj"] > 0)

    def test_period_with_only_one_distance_is_skipped(self) -> None:
        """A period with only one distance produces no output row (CP requires both distances)."""
        t = datetime(2025, 1, 1, tzinfo=timezone.utc)
        manager = WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "startDate": [pd.Timestamp("2025-01-01")],
                    "distance": [800.0],
                    "route": [self._make_route(t, 800.0, 160.0, 0.007)],
                }
            )
        )
        rp_df = pd.DataFrame([self._rp_record(t, 160.0, 350.0)])

        result = manager.get_critical_power_evolution(running_power_df=rp_df, period="M")
        assert result.empty
        assert list(result.columns) == ["period", "critical_power_w", "w_prime_kj"]

    def test_evolution_uses_topn_within_each_period(self) -> None:
        """topn should be applied independently per period, not globally before grouping."""
        data = [
            # January
            (datetime(2025, 1, 5, tzinfo=timezone.utc), 800.0, 170.0, 0.007, 300.0),
            (datetime(2025, 1, 20, tzinfo=timezone.utc), 5000.0, 1300.0, 0.045, 220.0),
            # February (globally faster for both distances)
            (datetime(2025, 2, 5, tzinfo=timezone.utc), 800.0, 160.0, 0.007, 350.0),
            (datetime(2025, 2, 20, tzinfo=timezone.utc), 5000.0, 1200.0, 0.045, 260.0),
        ]
        manager = WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"] * 4,
                    "startDate": [pd.Timestamp(dt) for dt, *_ in data],
                    "distance": [distance for _, distance, *_ in data],
                    "route": [
                        self._make_route(dt, distance, duration, lon)
                        for dt, distance, duration, lon, _ in data
                    ],
                }
            )
        )
        rp_df = pd.DataFrame(
            [self._rp_record(dt, duration, power) for dt, _, duration, _, power in data]
        )

        result = manager.get_critical_power_evolution(running_power_df=rp_df, period="M", topn=1)

        assert len(result) == 2
        assert list(result["period"]) == ["2025-01", "2025-02"]
        assert all(result["critical_power_w"] > 0)
        assert all(result["w_prime_kj"] > 0)

    def test_interior_gap_period_kept_as_none(self) -> None:
        """A month between two valid CP months appears as None (chart gap), not dropped.

        September and November have both 800m and 5000m segments with power → valid CP.
        October has NO workouts at all. The result must still include all three months,
        with October as a None gap so the chart x-axis is contiguous.
        """
        data = [
            # September: 800m and 5000m → valid CP
            (datetime(2025, 9, 5, tzinfo=timezone.utc), 800.0, 160.0, 0.007, 350.0),
            (datetime(2025, 9, 20, tzinfo=timezone.utc), 5000.0, 1250.0, 0.045, 250.0),
            # October: intentionally absent — simulates a month with zero workouts
            # November: 800m and 5000m → valid CP
            (datetime(2025, 11, 5, tzinfo=timezone.utc), 800.0, 158.0, 0.007, 355.0),
            (datetime(2025, 11, 25, tzinfo=timezone.utc), 5000.0, 1200.0, 0.045, 255.0),
        ]
        manager = WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"] * 4,
                    "startDate": [pd.Timestamp(dt) for dt, *_ in data],
                    "distance": [d for _, d, *_ in data],
                    "route": [
                        self._make_route(dt, dist, dur, lon) for dt, dist, dur, lon, _ in data
                    ],
                }
            )
        )
        rp_df = pd.DataFrame([self._rp_record(dt, dur, pwr) for dt, _, dur, _, pwr in data])

        result = manager.get_critical_power_evolution(running_power_df=rp_df, period="M")

        assert len(result) == 3
        assert list(result["period"]) == ["2025-09", "2025-10", "2025-11"]
        # September: valid CP
        assert result.iloc[0]["critical_power_w"] is not None
        assert result.iloc[0]["w_prime_kj"] is not None
        # October: gap — no workouts at all in this month
        assert pd.isna(result.iloc[1]["critical_power_w"])
        assert pd.isna(result.iloc[1]["w_prime_kj"])
        # November: valid CP
        assert result.iloc[2]["critical_power_w"] is not None
        assert result.iloc[2]["w_prime_kj"] is not None
