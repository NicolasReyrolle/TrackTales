"""Unit conversion constants for Apple Health Analyzer.

All values represent multiplication factors applied to a value stored in its
canonical SI base unit (metres for distance/elevation, kilograms for mass) to
obtain the user-facing value in the target unit.
"""

#: Multiply metres by this value to obtain miles.
METERS_TO_MILES: float = 1 / 1609.344

#: Multiply metres by this value to obtain feet.
METERS_TO_FEET: float = 1 / 0.3048

#: Multiply kilograms by this value to obtain pounds.
KG_TO_LBS: float = 2.20462


def celsius_to_fahrenheit(celsius: float) -> float:
    """Convert a temperature value from Celsius to Fahrenheit."""
    return celsius * 9 / 5 + 32
