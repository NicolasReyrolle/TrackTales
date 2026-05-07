"""Tests for workout_manager helper utilities."""

import pytest

from logic.workout_manager.helpers import convert_record_metric_value


def test_convert_record_metric_value_converts_distance_and_elevation() -> None:
    """Distance and elevation should use the provided length-unit divisor callback."""

    def get_divisor(unit: str) -> float:
        return 1000.0 if unit == "km" else 1.0

    assert convert_record_metric_value("distance", 5000.0, "km", get_divisor) == pytest.approx(5.0)
    assert convert_record_metric_value(
        "ElevationAscended", 1200.0, "km", get_divisor
    ) == pytest.approx(1.2)


def test_convert_record_metric_value_converts_duration_units() -> None:
    """Duration conversion should support seconds, minutes, and hours."""

    def get_divisor(_unit: str) -> float:
        return 1.0

    assert convert_record_metric_value("duration", 7200.0, "h", get_divisor) == pytest.approx(2.0)
    assert convert_record_metric_value("duration", 180.0, "min", get_divisor) == pytest.approx(3.0)
    assert convert_record_metric_value("duration", 45.0, "s", get_divisor) == pytest.approx(45.0)


def test_convert_record_metric_value_rejects_unsupported_inputs() -> None:
    """Unsupported metric columns or units should raise ValueError."""

    def get_divisor(_unit: str) -> float:
        return 1.0

    with pytest.raises(ValueError, match="Unsupported duration unit"):
        convert_record_metric_value("duration", 45.0, "day", get_divisor)
    with pytest.raises(ValueError, match="Unit conversion is not supported"):
        convert_record_metric_value("sumActiveEnergyBurned", 45.0, "kcal", get_divisor)
