"""Tests for workout trend slope and semantic analysis."""

import pytest

from logic.workout_manager import WorkoutManager
from logic.workout_manager.aggregations import calculate_trend_slope


class TestCalculateTrendSlope:
    """Unit tests for OLS trend slope calculation."""

    def test_returns_none_with_insufficient_data(self) -> None:
        """Fewer than two points cannot produce a meaningful slope."""
        assert calculate_trend_slope([42.0]) is None

    def test_returns_zero_for_flat_values(self) -> None:
        """Flat values should produce a zero slope."""
        assert calculate_trend_slope([3.0, 3.0, 3.0]) == pytest.approx(0.0)

    def test_returns_positive_slope_for_rising_values(self) -> None:
        """Increasing values should produce a positive slope."""
        assert calculate_trend_slope([10.0, 20.0, 30.0]) == pytest.approx(10.0)

    def test_returns_negative_slope_for_declining_values(self) -> None:
        """Decreasing values should produce a negative slope."""
        assert calculate_trend_slope([30.0, 20.0, 10.0]) == pytest.approx(-10.0)


class TestGetTrendAnalysis:
    """Unit tests for semantic trend classification."""

    def test_returns_insufficient_data_with_single_point(self) -> None:
        """A single point should be reported as insufficient data."""
        manager = WorkoutManager()
        assert manager.get_trend_analysis([42.0]) == "Insufficient data"

    def test_returns_stable_for_noisy_values_below_threshold(self) -> None:
        """Small physiological noise should be filtered out as stable."""
        manager = WorkoutManager()
        assert manager.get_trend_analysis([10.0, 10.03, 10.01, 10.04], threshold=0.05) == "Stable"

    def test_returns_improving_when_higher_values_are_better(self) -> None:
        """Positive slope is improving for higher-is-better metrics."""
        manager = WorkoutManager()
        assert manager.get_trend_analysis([1.0, 2.0, 3.0], threshold=0.05) == "Improving"

    def test_returns_improving_when_lower_values_are_better(self) -> None:
        """Negative slope is improving for lower-is-better metrics."""
        manager = WorkoutManager()
        assert (
            manager.get_trend_analysis(
                [70.0, 68.0, 66.0],
                is_higher_better=False,
                threshold=0.05,
            )
            == "Improving"
        )
