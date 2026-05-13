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

#: Number of meters in one kilometer.
METERS_PER_KM: float = 1000.0

#: Multiply m/s by this value to obtain km/h.
M_S_TO_KM_H: float = 3.6

#: Number of seconds in one minute.
SECONDS_PER_MINUTE: float = 60.0

#: Number of minutes in one hour.
MINUTES_PER_HOUR: float = 60.0


def celsius_to_fahrenheit(celsius: float) -> float:
    """Convert a temperature value from Celsius to Fahrenheit."""
    return celsius * 9 / 5 + 32
