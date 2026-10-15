"""Value and unit parsing utilities for Apple Health export data."""

from typing import Any

from units import METERS_TO_MILES


def to_number(raw: str | None) -> float | int | None:
    """Convert a string to a number (int or float), or return None if conversion fails."""
    if raw is None:
        return None
    try:
        value = float(raw)
        return int(value) if value.is_integer() else value
    except ValueError:
        return None


def parse_metadata_value(raw_value: str | None) -> tuple[Any, str | None]:
    """Parse a metadata entry value without boolean coercion.

    Unlike _parse_value, numeric values "0" and "1" are returned as integers,
    not booleans. This is needed for enumerated metadata fields such as
    HeartRateMotionContext (0/1/2).

    Returns: (value, unit) where unit is None when no unit is present.
    """
    if not raw_value:
        return None, None

    raw_value = raw_value.strip()
    if not raw_value:
        return None, None

    parts = raw_value.split(maxsplit=1)
    if len(parts) == 1:
        num = to_number(parts[0])
        if num is not None:
            return num, None
        return parts[0], None

    num = to_number(parts[0])
    if num is not None:
        unit = parts[1].strip() or None
        return float(num), unit
    return raw_value, None


def parse_value(raw_value: str | None) -> tuple[Any, str | None]:
    """Separate value and unit, converting to standard metric system.

    Rules:
    - Number without unit (0 or 1) -> Boolean (False/True)
    - Number without unit (other) -> Float
    - String (not a number) -> String
    - "Value Unit" -> Converted Float + Unit

    Returns: (value, unit) or (None, None)
    """
    if not raw_value:
        return None, None

    raw_value = raw_value.strip()
    if not raw_value:
        return None, None

    parts = raw_value.split(maxsplit=1)
    if len(parts) == 1:
        try:
            val = float(parts[0])
            if val == 0:
                return False, None
            if val == 1:
                return True, None
            return val, None
        except ValueError:
            return raw_value, None
    try:
        val = float(parts[0])
    except ValueError:
        return raw_value, None

    unit = parts[1]

    if unit == "cm":
        val = val / 100.0
        unit = "m"
    elif unit == "%":
        val = val / 100.0
    elif unit == "degF":
        val = (val - 32) * 5.0 / 9.0
        unit = "degC"

    return val, unit


def duration_to_seconds(value: float, unit: str = "min") -> int:
    """Convert duration to seconds based on the unit."""
    if unit in ("min", ""):
        return int(value * 60)
    if unit == "h":
        return int(value * 3600)
    if unit == "s":
        return int(value)
    raise ValueError(f"Unknown duration unit: {unit}")


def str_distance_to_meters(value: str, unit: str | None) -> int:
    """Convert distance to meters."""
    if unit is None:
        raise ValueError("Distance unit is missing (None). Cannot convert to meters.")
    if unit == "km":
        return int(float(value) * 1000)
    if unit == "m":
        return int(float(value))
    if unit == "mi":
        return int(float(value) / METERS_TO_MILES)
    raise ValueError(f"Unknown distance unit: {unit}")
