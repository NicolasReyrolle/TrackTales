"""UI formatting and locale helpers."""

import json
import re
from collections.abc import Sequence
from typing import Any, Protocol

import pandas as pd
from babel.core import default_locale
from babel.numbers import format_decimal

from i18n import translate
from units import METERS_TO_MILES

SECONDS_PER_MINUTE: float = 60.0
MINUTES_PER_HOUR: float = 60.0


class _SupportsStrftime(Protocol):
    """Protocol for date-like objects exposing ``strftime``."""

    def strftime(self, fmt: str, /) -> str:
        """Return a formatted date string."""
        raise NotImplementedError


def _resolve_locale(locale_name: str | None = None) -> str:
    """Resolve the locale to use for formatting."""
    if locale_name:
        return locale_name
    detected = default_locale()
    return detected or "en_US"


def _normalize_language_code(language_code: str) -> str:
    """Normalize language identifiers to base gettext language codes.

    UI/session language values may appear as locale-like codes (e.g. ``fr_FR``),
    while gettext catalogs are keyed by short language codes (e.g. ``fr``).
    """
    if not language_code:
        return "en"
    normalized = language_code.replace("-", "_").lower()
    if "_" in normalized:
        normalized = normalized.split("_", maxsplit=1)[0]
    return normalized


def format_integer(value: int, locale_name: str | None = None) -> str:
    """Format an integer with grouping for the current locale."""
    return format_decimal(value, format="#,##0", locale=_resolve_locale(locale_name))


def format_float(value: float, decimal_places: int = 1, locale_name: str | None = None) -> str:
    """Format a float with the given number of decimal places for the current locale."""
    if decimal_places <= 0:
        fmt = "#,##0"
    else:
        fmt = f"#,##0.{'0' * decimal_places}"
    return format_decimal(value, format=fmt, locale=_resolve_locale(locale_name))


def period_code_to_label(code: str) -> str:
    """Convert a period code to a human-readable label."""
    mapping = {
        "D": "day",
        "W": "week",
        "M": "month",
        "Q": "quarter",
        "Y": "year",
    }
    return mapping.get(code, code)


def qdate_locale_json(language_code: str) -> str:
    """Return Quasar QDate locale data serialized as JSON."""

    normalized_language_code = _normalize_language_code(language_code)

    def tr(message: str) -> str:
        return translate(message, language=normalized_language_code)

    locale_by_language: dict[str, dict[str, object]] = {
        "fr": {
            "days": [
                tr("Sunday"),
                tr("Monday"),
                tr("Tuesday"),
                tr("Wednesday"),
                tr("Thursday"),
                tr("Friday"),
                tr("Saturday"),
            ],
            "daysShort": [
                tr("Sun"),
                tr("Mon"),
                tr("Tue"),
                tr("Wed"),
                tr("Thu"),
                tr("Fri"),
                tr("Sat"),
            ],
            "months": [
                tr("January"),
                tr("February"),
                tr("March"),
                tr("April"),
                tr("May"),
                tr("June"),
                tr("July"),
                tr("August"),
                tr("September"),
                tr("October"),
                tr("November"),
                tr("December"),
            ],
            "monthsShort": [
                tr("Jan"),
                tr("Feb"),
                tr("Mar"),
                tr("Apr"),
                tr("May"),
                tr("Jun"),
                tr("Jul"),
                tr("Aug"),
                tr("Sep"),
                tr("Oct"),
                tr("Nov"),
                tr("Dec"),
            ],
            "firstDayOfWeek": 1,
        },
        "en": {
            "days": [
                "Sunday",
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
                "Saturday",
            ],
            "daysShort": ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
            "months": [
                "January",
                "February",
                "March",
                "April",
                "May",
                "June",
                "July",
                "August",
                "September",
                "October",
                "November",
                "December",
            ],
            "monthsShort": [
                "Jan",
                "Feb",
                "Mar",
                "Apr",
                "May",
                "Jun",
                "Jul",
                "Aug",
                "Sep",
                "Oct",
                "Nov",
                "Dec",
            ],
            "firstDayOfWeek": 0,
        },
    }
    locale: dict[str, object] = locale_by_language.get(
        normalized_language_code, locale_by_language["en"]
    )
    return json.dumps(locale)


def format_distance_label(
    distance_m: float,
    language_code: str,
    half_marathon_distance_m: int,
    marathon_distance_m: int,
    distance_unit: str = "km",
) -> str:
    """Format a best-segment distance label with special marathon names.

    Args:
        distance_m: Distance in metres.
        language_code: Active language code used for translated names.
        half_marathon_distance_m: Half-marathon reference distance in metres.
        marathon_distance_m: Marathon reference distance in metres.
        distance_unit: Display unit – ``"km"`` (default) or ``"mi"``.
    """
    normalized_language_code = _normalize_language_code(language_code)
    rounded_distance = int(round(distance_m))
    if rounded_distance == half_marathon_distance_m:
        return translate("Half-marathon", language=normalized_language_code)
    if rounded_distance == marathon_distance_m:
        return translate("Marathon", language=normalized_language_code)
    if rounded_distance < 1000:
        return f"{rounded_distance} m"
    if distance_unit == "mi":
        return f"{distance_m * METERS_TO_MILES:.1f} mi"
    return f"{distance_m / 1000:.1f} km"


def format_duration_label(duration_s: float | None) -> str:
    """Format a duration in seconds into a human-readable label."""
    total_seconds = max(0, int(round(duration_s))) if duration_s is not None else 0
    hours, remaining = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remaining, 60)

    if total_seconds < 60:
        return f"{seconds} s"
    if total_seconds < 3600:
        return f"{minutes} min {seconds:02d} s"
    return f"{hours} h {minutes:02d} min {seconds:02d} s"


def format_hours_minutes_from_seconds(duration_s: float) -> str:
    """Format seconds as a compact hours/minutes string for overview stat cards."""
    total_minutes = int(round(duration_s / SECONDS_PER_MINUTE))
    hours, minutes = divmod(total_minutes, int(MINUTES_PER_HOUR))
    return f"{hours} h {minutes:02d} min" if hours > 0 else f"{minutes} min"


def parse_float(value: Any) -> float | None:
    """Parse a float value, returning ``None`` when conversion fails."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def format_date_label(start_date: _SupportsStrftime, language_code: str) -> str:
    """Format a date label according to the selected language."""
    normalized_language_code = _normalize_language_code(language_code)
    if normalized_language_code == "fr":
        return start_date.strftime("%d/%m/%Y")
    return start_date.strftime("%m/%d/%Y")


def translate_parser_progress_message(message: str, language_code: str) -> str:
    """Translate parser progress messages emitted by ``ExportParser``."""
    exact_messages = {
        "Starting to parse the Apple Health export file...": (
            "Starting to parse the Apple Health export file..."
        ),
        "Loading the workouts...": "Loading the workouts...",
        "Finished parsing the Apple Health export file.": (
            "Finished parsing the Apple Health export file."
        ),
    }
    exact_template = exact_messages.get(message)
    if exact_template is not None:
        return translate(exact_template, language=language_code)

    template: str | None
    params: dict[str, str]
    processed_match = re.match(r"^Processed (\d+) workouts\.\.\.$", message)
    if processed_match:
        template = "Processed {count} workouts..."
        params = {"count": processed_match.group(1)}
    else:
        loaded_match = re.match(r"^Loaded (\d+) workouts total\.$", message)
        if loaded_match:
            template = "Loaded {count} workouts total."
            params = {"count": loaded_match.group(1)}
        else:
            error_match = re.match(r"^Error during parsing: (.+)$", message)
            if error_match:
                template = "Error during parsing: {error}"
                params = {"error": error_match.group(1)}
            else:
                template = None
                params = {}

    if template is None:
        return message
    return translate(template, language=language_code, **params)


def calculate_moving_average(
    y_values: Sequence[float | int | None], window_size: int = 12
) -> list[float | None]:
    """Calculate a moving average with ``min_periods=1`` while preserving missing values."""
    series = pd.Series(list(y_values), dtype=float)
    result = series.rolling(window=window_size, min_periods=1).mean().round(2)
    return [None if pd.isna(v) else float(v) for v in result]
