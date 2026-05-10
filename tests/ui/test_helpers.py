"""Tests for UI helper formatting utilities."""

from datetime import datetime

import pandas as pd
import pytest

from ui import helpers


def test_format_integer_uses_explicit_locale() -> None:
    """Explicit locale should be used for formatting."""
    assert helpers.format_integer(12345, locale_name="en_US") == "12,345"


def test_format_integer_defaults_to_fallback_locale(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fallback locale should be used when no default is detected."""

    def _no_locale() -> str | None:
        return None

    monkeypatch.setattr(helpers, "default_locale", _no_locale)

    assert helpers.format_integer(1234) == "1,234"


class TestPeriodCodeToLabel:
    """Tests for period_code_to_label conversion."""

    def test_converts_day_code(self) -> None:
        """Day code 'D' should convert to 'day'."""
        assert helpers.period_code_to_label("D") == "day"

    def test_converts_week_code(self) -> None:
        """Week code 'W' should convert to 'week'."""
        assert helpers.period_code_to_label("W") == "week"

    def test_converts_month_code(self) -> None:
        """Month code 'M' should convert to 'month'."""
        assert helpers.period_code_to_label("M") == "month"

    def test_converts_quarter_code(self) -> None:
        """Quarter code 'Q' should convert to 'quarter'."""
        assert helpers.period_code_to_label("Q") == "quarter"

    def test_converts_year_code(self) -> None:
        """Year code 'Y' should convert to 'year'."""
        assert helpers.period_code_to_label("Y") == "year"

    def test_returns_code_for_unknown_value(self) -> None:
        """Unknown code should return the code itself."""
        assert helpers.period_code_to_label("X") == "X"
        assert helpers.period_code_to_label("ABC") == "ABC"

    def test_case_sensitive(self) -> None:
        """Conversion should be case-sensitive."""
        assert helpers.period_code_to_label("w") == "w"
        assert helpers.period_code_to_label("m") == "m"


class TestBestSegmentLabelFormatters:
    """Tests for best segment label formatters."""

    def test_format_distance_label_special_distances_use_translation(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Half-marathon and marathon labels should be translated."""

        def _translate(message: str, language: str, **_kwargs: str) -> str:
            return f"{language}:{message}"

        monkeypatch.setattr(helpers, "translate", _translate)

        assert (
            helpers.format_distance_label(
                21097,
                language_code="fr",
                half_marathon_distance_m=21097,
                marathon_distance_m=42195,
            )
            == "fr:Half-marathon"
        )
        assert (
            helpers.format_distance_label(
                42195,
                language_code="fr",
                half_marathon_distance_m=21097,
                marathon_distance_m=42195,
            )
            == "fr:Marathon"
        )

    def test_format_distance_label_special_distances_normalize_locale_code(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Locale-like language codes (e.g. fr_FR) should map to gettext base code."""

        def _translate(message: str, language: str, **_kwargs: str) -> str:
            return f"{language}:{message}"

        monkeypatch.setattr(helpers, "translate", _translate)

        assert (
            helpers.format_distance_label(
                21097,
                language_code="fr_FR",
                half_marathon_distance_m=21097,
                marathon_distance_m=42195,
            )
            == "fr:Half-marathon"
        )

    def test_format_distance_label_standard_units(self) -> None:
        """Distances below and above 1km should use meter/km formatting."""
        assert (
            helpers.format_distance_label(
                100,
                language_code="en",
                half_marathon_distance_m=21097,
                marathon_distance_m=42195,
            )
            == "100 m"
        )
        assert (
            helpers.format_distance_label(
                1000,
                language_code="en",
                half_marathon_distance_m=21097,
                marathon_distance_m=42195,
            )
            == "1.0 km"
        )

    def test_format_distance_label_miles_unit(self) -> None:
        """Distances above 1 km should use miles formatting when distance_unit='mi'."""
        # 1609 metres ≈ 1.0 mile.
        # 1609 / 1609.34 = 0.9998, which rounds to "1.0".
        assert (
            helpers.format_distance_label(
                1609,
                language_code="en",
                half_marathon_distance_m=21097,
                marathon_distance_m=42195,
                distance_unit="mi",
            )
            == "1.0 mi"
        )
        assert (
            helpers.format_distance_label(
                5000,
                language_code="en",
                half_marathon_distance_m=21097,
                marathon_distance_m=42195,
                distance_unit="mi",
            )
            == "3.1 mi"
        )

    def test_format_distance_label_short_always_meters(self) -> None:
        """Distances below 1 km should always be shown in meters regardless of unit."""
        assert (
            helpers.format_distance_label(
                800,
                language_code="en",
                half_marathon_distance_m=21097,
                marathon_distance_m=42195,
                distance_unit="mi",
            )
            == "800 m"
        )

    def test_format_distance_label_special_distances_ignore_unit(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Named marathon distances should be translated regardless of unit setting."""

        def _translate(message: str, language: str, **_kwargs: str) -> str:
            return f"{language}:{message}"

        monkeypatch.setattr(helpers, "translate", _translate)

        assert (
            helpers.format_distance_label(
                21097,
                language_code="en",
                half_marathon_distance_m=21097,
                marathon_distance_m=42195,
                distance_unit="mi",
            )
            == "en:Half-marathon"
        )

    def test_format_duration_label(self) -> None:
        """Durations should be rendered as s, min/s, or h/min/s."""
        assert helpers.format_duration_label(5.0) == "5 s"
        assert helpers.format_duration_label(20.0) == "20 s"
        assert helpers.format_duration_label(404.0) == "6 min 44 s"
        assert helpers.format_duration_label(3661.0) == "1 h 01 min 01 s"
        assert helpers.format_duration_label(5000.0) == "1 h 23 min 20 s"

    def test_format_date_label(self) -> None:
        """Date labels should follow language-specific ordering."""
        value = datetime(2025, 9, 16)
        assert helpers.format_date_label(value, language_code="fr") == "16/09/2025"
        assert helpers.format_date_label(value, language_code="en") == "09/16/2025"

    def test_format_date_label_normalizes_locale_code(self) -> None:
        """Locale-like language codes should still use French date formatting."""
        value = datetime(2025, 9, 16)
        assert helpers.format_date_label(value, language_code="fr_FR") == "16/09/2025"

    def test_format_hours_minutes_from_seconds(self) -> None:
        """Overview duration formatter should output compact hours/minutes labels."""
        assert helpers.format_hours_minutes_from_seconds(3599.0) == "1 h 00 min"
        assert helpers.format_hours_minutes_from_seconds(3600.0) == "1 h 00 min"
        assert helpers.format_hours_minutes_from_seconds(7260.0) == "2 h 01 min"

    def test_parse_float(self) -> None:
        """parse_float should parse valid numbers and return None for invalid values."""
        assert helpers.parse_float("12.5") == pytest.approx(12.5)
        assert helpers.parse_float(4) == pytest.approx(4.0)
        assert helpers.parse_float(None) is None
        assert helpers.parse_float("abc") is None


def test_filter_workouts_by_date_range_no_start_date_column_returns_input() -> None:
    """Date range helper should return input when startDate column is absent."""
    workouts = pd.DataFrame({"activityType": ["Running"]})
    filtered = helpers.filter_workouts_by_date_range(
        workouts,
        start_date=datetime(2025, 1, 1),
        end_date=datetime(2025, 1, 2),
    )
    assert filtered.equals(workouts)


def test_filter_workouts_by_date_range_with_start_date_only() -> None:
    """Date range helper should apply an inclusive start date filter."""
    workouts = pd.DataFrame(
        {
            "startDate": [
                pd.Timestamp("2025-01-01 10:00:00"),
                pd.Timestamp("2025-01-02 10:00:00"),
            ]
        }
    )
    filtered = helpers.filter_workouts_by_date_range(
        workouts,
        start_date=datetime(2025, 1, 2),
        end_date=None,
    )
    assert len(filtered) == 1
    assert filtered.iloc[0]["startDate"] == pd.Timestamp("2025-01-02 10:00:00")


def test_filter_workouts_by_date_range_with_midnight_end_date_is_end_of_day_inclusive() -> None:
    """A date-only end date should include the full day."""
    workouts = pd.DataFrame(
        {
            "startDate": [
                pd.Timestamp("2025-01-02 23:59:00"),
                pd.Timestamp("2025-01-03 00:00:00"),
            ]
        }
    )
    filtered = helpers.filter_workouts_by_date_range(
        workouts,
        start_date=None,
        end_date=datetime(2025, 1, 2),
    )
    assert len(filtered) == 1
    assert filtered.iloc[0]["startDate"] == pd.Timestamp("2025-01-02 23:59:00")


def test_filter_workouts_by_date_range_with_datetime_end_date_is_timestamp_inclusive() -> None:
    """A datetime end date should filter up to the exact timestamp."""
    workouts = pd.DataFrame(
        {
            "startDate": [
                pd.Timestamp("2025-01-02 10:00:00"),
                pd.Timestamp("2025-01-02 11:00:00"),
            ]
        }
    )
    filtered = helpers.filter_workouts_by_date_range(
        workouts,
        start_date=None,
        end_date=datetime(2025, 1, 2, 10, 30),
    )
    assert len(filtered) == 1
    assert filtered.iloc[0]["startDate"] == pd.Timestamp("2025-01-02 10:00:00")
