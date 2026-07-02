"""Tests for workout trend slope and semantic analysis."""

from unittest.mock import patch

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

    def test_returns_none_when_denominator_is_zero(self) -> None:
        """A zero x-variance fallback should return None instead of dividing by zero."""
        with patch("logic.workout_manager.aggregations.sum", side_effect=[6.0, 0.0, 0.0]):
            assert calculate_trend_slope([1.0, 2.0, 3.0]) is None


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

    def test_returns_increasing_for_directional_labels(self) -> None:
        """Directional labels should ignore desirability and follow slope sign."""
        manager = WorkoutManager()
        assert (
            manager.get_trend_analysis(
                [70.0, 71.0, 72.0],
                is_higher_better=False,
                threshold=0.05,
                label_mode="directional",
            )
            == "Increasing"
        )


class TestCalculateTrendSlopeWithXValues:
    """Tests for gap-aware OLS slope calculation with explicit x-positions."""

    def test_slope_with_dense_x_values_matches_default(self) -> None:
        """Passing x_values=[0, 1, 2] should yield the same slope as the default."""
        assert calculate_trend_slope([10.0, 20.0, 30.0], x_values=[0, 1, 2]) == pytest.approx(10.0)

    def test_slope_preserves_gap_spacing(self) -> None:
        """A gap at index 1 should be reflected in the computed slope."""
        # Values at periods 0 and 2 (period 1 is missing); slope from 10 to 30 over 2 steps
        slope = calculate_trend_slope([10.0, 30.0], x_values=[0, 2])
        assert slope == pytest.approx(10.0)

    def test_slope_without_gap_is_steeper_when_gap_exists(self) -> None:
        """Collapsing a gap overstates the slope compared to preserving spacing."""
        # Dense: [10, 30] → slope = 20 per step (indices 0,1)
        dense_slope = calculate_trend_slope([10.0, 30.0])
        # Sparse: same values but indices 0 and 2 → slope = 10 per step
        sparse_slope = calculate_trend_slope([10.0, 30.0], x_values=[0, 2])
        assert dense_slope != pytest.approx(sparse_slope)
        assert dense_slope == pytest.approx(20.0)
        assert sparse_slope == pytest.approx(10.0)

    def test_get_trend_analysis_with_x_values_uses_correct_spacing(self) -> None:
        """get_trend_analysis should forward x_values to slope calculation."""
        manager = WorkoutManager()
        # [10, 10.02, 10.04] over indices [0, 5, 10]: slope ≈ 0.004 → below 0.05 threshold
        result = manager.get_trend_analysis(
            [10.0, 10.02, 10.04],
            threshold=0.05,
            x_values=[0, 5, 10],
        )
        assert result == "Stable"
