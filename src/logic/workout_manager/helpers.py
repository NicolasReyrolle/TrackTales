"""Helper utilities for workout-manager aggregation logic."""

from collections.abc import Callable

SECONDS_PER_MINUTE = 60.0
SECONDS_PER_HOUR = 3600.0


def convert_record_metric_value(
    metric_column: str,
    raw_value: float,
    unit: str,
    get_length_unit_divisor: Callable[[str], float],
) -> float:
    """Convert a workout-record metric value to the requested display unit."""
    if metric_column in {"distance", "ElevationAscended"}:
        return raw_value / get_length_unit_divisor(unit)
    if metric_column == "duration":
        if unit == "h":
            return raw_value / SECONDS_PER_HOUR
        if unit == "min":
            return raw_value / SECONDS_PER_MINUTE
        if unit == "s":
            return raw_value
        raise ValueError(f"Unsupported duration unit: {unit}")
    raise ValueError(f"Unit conversion is not supported for metric: {metric_column}")
