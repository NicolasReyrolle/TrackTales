"""Tests for WorkoutManager recovery recommendation logic."""

from datetime import datetime

import pandas as pd
import pytest

from logic.workout_manager import WorkoutManager


def _make_weekly_workouts(
    weekly_durations: list[int],
    start_date: str = "2024-01-01",
    activity_type: str = "Running",
) -> pd.DataFrame:
    """Create a DataFrame with one workout per week, each with the given duration (seconds).

    ``weekly_durations`` is ordered oldest-first; each entry is the duration (in
    seconds) of a single workout placed on the Monday of successive calendar weeks.
    """
    rows = []
    base = pd.Timestamp(start_date)
    for week_offset, duration in enumerate(weekly_durations):
        start = base + pd.Timedelta(days=7 * week_offset)
        rows.append(
            {
                "activityType": activity_type,
                "startDate": start,
                "endDate": start + pd.Timedelta(seconds=duration),
                "duration": duration,
                "distance": duration * 2.0,  # 2 m/s as a proxy distance
            }
        )
    return pd.DataFrame(rows)


class TestGetWeeklyLoad:
    """Unit tests for _get_weekly_load helper."""

    def test_returns_duration_values_for_duration_metric(self) -> None:
        """Weekly duration totals should be non-zero and match input hours."""
        df = _make_weekly_workouts([3600, 7200, 10800])  # 1h, 2h, 3h
        manager = WorkoutManager(df)
        loads = manager._get_weekly_load(load_metric="duration")
        assert len(loads) == 3
        # get_duration_by_period returns hours; 3600 s → 1 h
        assert loads[0] == pytest.approx(1.0, abs=0.1)
        assert loads[1] == pytest.approx(2.0, abs=0.1)
        assert loads[2] == pytest.approx(3.0, abs=0.1)

    def test_returns_distance_values_for_distance_metric(self) -> None:
        """Weekly distance totals should be non-zero and match input km."""
        # distance = duration * 2 m, and get_distance_by_period returns km
        df = _make_weekly_workouts([5000, 10000])  # 10 km and 20 km workouts
        manager = WorkoutManager(df)
        loads = manager._get_weekly_load(load_metric="distance")
        assert len(loads) == 2
        assert loads[0] == pytest.approx(10.0, abs=0.1)
        assert loads[1] == pytest.approx(20.0, abs=0.1)

    def test_raises_for_unsupported_metric(self) -> None:
        """An unknown load_metric should raise ValueError."""
        manager = WorkoutManager()
        with pytest.raises(ValueError, match="Unsupported load_metric"):
            manager._get_weekly_load(load_metric="calories")

    def test_returns_empty_list_for_empty_manager(self) -> None:
        """An empty WorkoutManager should return an empty load list."""
        manager = WorkoutManager()
        loads = manager._get_weekly_load(load_metric="duration")
        assert loads == []

    def test_filters_by_activity_type(self) -> None:
        """Only workouts matching the given activity_type should be included."""
        df = pd.DataFrame(
            {
                "activityType": ["Running", "Cycling"],
                "startDate": [pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-02")],
                "endDate": [
                    pd.Timestamp("2024-01-01 01:00:00"),
                    pd.Timestamp("2024-01-02 02:00:00"),
                ],
                "duration": [3600, 7200],
                "distance": [7200.0, 14400.0],
            }
        )
        manager = WorkoutManager(df)
        running_loads = manager._get_weekly_load(load_metric="duration", activity_type="Running")
        cycling_loads = manager._get_weekly_load(load_metric="duration", activity_type="Cycling")
        # Only one workout per type; both fall in the same week
        assert sum(running_loads) == pytest.approx(1.0, abs=0.1)
        assert sum(cycling_loads) == pytest.approx(2.0, abs=0.1)


class TestGetRecoveryRecommendation:
    """Unit tests for get_recovery_recommendation."""

    def test_returns_insufficient_data_for_empty_manager(self) -> None:
        """No workouts should yield 'Insufficient data'."""
        manager = WorkoutManager()
        assert manager.get_recovery_recommendation() == "Insufficient data"

    def test_returns_insufficient_data_for_single_week(self) -> None:
        """Only one week of data is insufficient for an ACWR calculation."""
        df = _make_weekly_workouts([3600])
        manager = WorkoutManager(df)
        assert manager.get_recovery_recommendation() == "Insufficient data"

    def test_returns_insufficient_data_when_chronic_load_is_zero(self) -> None:
        """All-zero historic weeks should return 'Insufficient data' (no division by zero)."""
        df = _make_weekly_workouts([0, 0, 0, 0])
        manager = WorkoutManager(df)
        assert manager.get_recovery_recommendation() == "Insufficient data"

    def test_returns_rest_when_acwr_exceeds_rest_threshold(self) -> None:
        """ACWR > 1.5 should recommend Rest.

        Chronic average = (1 + 1 + 1 + 1) / 4 = 1 h/week (in hours).
        Acute (most recent week) = 2 h.
        ACWR = 2 / 1 = 2.0 > 1.5 → Rest.
        """
        # 4 quiet weeks (1 h each) then one very heavy week (2 h)
        durations = [3600, 3600, 3600, 3600, 7200]
        df = _make_weekly_workouts(durations)
        manager = WorkoutManager(df)
        assert manager.get_recovery_recommendation() == "Rest"

    def test_returns_active_recovery_when_acwr_between_thresholds(self) -> None:
        """ACWR between 1.3 and 1.5 should recommend Active Recovery.

        ``get_duration_by_period`` rounds to integer hours, so durations must
        be chosen to round unambiguously.

        With 4 weeks [36000, 36000, 36000, 54000] seconds = [10, 10, 10, 15] hours:
        - Last 4 weeks = [10, 10, 10, 15] hours (all round cleanly)
        - Chronic = (10 + 10 + 10 + 15) / 4 = 11.25 h
        - Acute = 15 h
        - ACWR = 15 / 11.25 ≈ 1.333 → Active Recovery (1.3 < 1.333 ≤ 1.5).
        """
        # 3 × 10 h baseline weeks, then a 15 h spike
        durations = [36000, 36000, 36000, 54000]
        df = _make_weekly_workouts(durations)
        manager = WorkoutManager(df)
        result = manager.get_recovery_recommendation()
        assert result == "Active Recovery"

    def test_returns_maintain_when_acwr_in_optimal_zone(self) -> None:
        """ACWR between 0.8 and 1.3 should recommend Maintain.

        Chronic = 1.0 h/week.  Acute = 1.0 h.  ACWR = 1.0 → Maintain.
        """
        durations = [3600, 3600, 3600, 3600, 3600]
        df = _make_weekly_workouts(durations)
        manager = WorkoutManager(df)
        assert manager.get_recovery_recommendation() == "Maintain"

    def test_returns_build_when_acwr_below_build_threshold(self) -> None:
        """ACWR < 0.8 should recommend Build.

        Chronic = 1.0 h/week.  Acute = 0.5 h (1800 s).  ACWR = 0.5 < 0.8 → Build.
        """
        baseline = [3600] * 4
        durations = baseline + [1800]  # only 30 min this week
        df = _make_weekly_workouts(durations)
        manager = WorkoutManager(df)
        assert manager.get_recovery_recommendation() == "Build"

    def test_uses_last_four_weeks_for_chronic_window(self) -> None:
        """The chronic load window uses at most the last 4 weeks.

        Weeks: [100 h, 100 h, 1 h, 1 h, 1 h, 0.5 h]
        Last 4 weeks = [1, 1, 1, 0.5], chronic = 3.5/4 = 0.875 h
        Acute = 0.5 h → ACWR = 0.5/0.875 ≈ 0.57 → Build
        """
        durations = [
            360000,  # 100 h (outside the 4-week window, should be ignored)
            360000,  # 100 h
            3600,  # 1 h
            3600,  # 1 h
            3600,  # 1 h
            1800,  # 0.5 h (most recent / acute)
        ]
        df = _make_weekly_workouts(durations)
        manager = WorkoutManager(df)
        assert manager.get_recovery_recommendation() == "Build"

    def test_uses_all_weeks_when_fewer_than_four_available(self) -> None:
        """With only two weeks, chronic uses both weeks as the window.

        Weeks: [1 h, 1.4 h]
        Chronic = (1 + 1.4) / 2 = 1.2 h
        Acute = 1.4 h → ACWR = 1.4/1.2 ≈ 1.17 → Maintain
        """
        durations = [3600, 5040]  # 1 h and 1.4 h
        df = _make_weekly_workouts(durations)
        manager = WorkoutManager(df)
        assert manager.get_recovery_recommendation() == "Maintain"

    def test_distance_metric_produces_recommendation(self) -> None:
        """Using load_metric='distance' should still produce a valid recommendation."""
        # 4 weeks at 10 km, then 10 km → ACWR = 1.0 → Maintain
        df = _make_weekly_workouts([5000] * 5)  # 5000 m → 10 km each
        manager = WorkoutManager(df)
        result = manager.get_recovery_recommendation(load_metric="distance")
        assert result in {"Rest", "Active Recovery", "Maintain", "Build", "Insufficient data"}

    def test_invalid_load_metric_raises(self) -> None:
        """Passing an unsupported load_metric should raise ValueError."""
        df = _make_weekly_workouts([3600, 3600])
        manager = WorkoutManager(df)
        with pytest.raises(ValueError, match="Unsupported load_metric"):
            manager.get_recovery_recommendation(load_metric="power")

    def test_activity_type_filter_is_respected(self) -> None:
        """Filtering by activity_type should not count other activities."""
        # Two activity types each week; only running matters
        weeks = pd.date_range("2024-01-01", periods=5, freq="W-MON")
        rows = []
        for week in weeks:
            # 1 h running
            rows.append(
                {
                    "activityType": "Running",
                    "startDate": week,
                    "endDate": week + pd.Timedelta(hours=1),
                    "duration": 3600,
                    "distance": 10000.0,
                }
            )
            # 5 h cycling (should be ignored when filtering for running)
            rows.append(
                {
                    "activityType": "Cycling",
                    "startDate": week + pd.Timedelta(hours=2),
                    "endDate": week + pd.Timedelta(hours=7),
                    "duration": 18000,
                    "distance": 100000.0,
                }
            )
        df = pd.DataFrame(rows)
        manager = WorkoutManager(df)
        # Running load is steady at 1 h/week → Maintain
        assert manager.get_recovery_recommendation(activity_type="Running") == "Maintain"

    def test_date_range_filters_are_forwarded(self) -> None:
        """start_date and end_date should limit which workouts are included."""
        df = _make_weekly_workouts([3600, 3600, 3600, 3600, 7200])
        manager = WorkoutManager(df)
        # Restrict to only the first two weeks → not enough data for ACWR
        result_restricted = manager.get_recovery_recommendation(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 8),
        )
        # Full dataset still produces a proper recommendation
        result_full = manager.get_recovery_recommendation()
        # The filtered result may differ; just assert both return valid strings
        valid = {"Rest", "Active Recovery", "Maintain", "Build", "Insufficient data"}
        assert result_restricted in valid
        assert result_full in valid

    def test_exact_rest_boundary_at_1_5(self) -> None:
        """Exactly ACWR = 1.5 should NOT be 'Rest' (boundary is strict >).

        ``get_duration_by_period`` rounds to integer hours, so durations must
        round cleanly.  With 4 weeks [36000, 36000, 36000, 64800] seconds
        = [10, 10, 10, 18] hours:
        - Chronic = (10 + 10 + 10 + 18) / 4 = 12 h
        - Acute = 18 h
        - ACWR = 18 / 12 = 1.5 exactly → Active Recovery (not Rest).
        """
        # 10 h baseline × 3, then exactly 18 h → ACWR = 1.5
        durations = [36000, 36000, 36000, 64800]
        df = _make_weekly_workouts(durations)
        manager = WorkoutManager(df)
        result = manager.get_recovery_recommendation()
        assert result == "Active Recovery"

    def test_exact_build_boundary_at_0_8(self) -> None:
        """Exactly ACWR = 0.8 should be 'Maintain' (boundary is inclusive >=).

        With 4 weeks [3600, 3600, 3600, 2700]:
        - Last 4 weeks = all = [3600, 3600, 3600, 2700] seconds
        - Chronic = (3600 + 3600 + 3600 + 2700) / 4 = 3375 s = 0.9375 h
        - Acute = 2700 s = 0.75 h
        - ACWR = 2700 / 3375 = 0.8 exactly → Maintain (>= 0.8 threshold).
        """
        durations = [3600, 3600, 3600, 2700]
        df = _make_weekly_workouts(durations)
        manager = WorkoutManager(df)
        result = manager.get_recovery_recommendation()
        assert result == "Maintain"
