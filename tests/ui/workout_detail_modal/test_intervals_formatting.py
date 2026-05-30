"""Tests for ui.workout_detail_modal — Intervals tab formatting helpers."""

from __future__ import annotations

from ui import workout_detail_modal as wdm


class TestFormatSplitPace:
    """Unit tests for _format_split_pace()."""

    def test_integer_minutes_km(self) -> None:
        """An exact integer minute pace should format as 'mm:00 min/km'."""
        assert wdm._format_split_pace(5.0, "km") == "5:00 min/km"

    def test_fractional_pace_rounded_km(self) -> None:
        """Fractional seconds should be rounded correctly."""
        # 4.5 min/km → 4 min 30 sec
        assert wdm._format_split_pace(4.5, "km") == "4:30 min/km"

    def test_seconds_rollover(self) -> None:
        """When rounded seconds == 60, minutes should increment and seconds reset."""
        # pace where fractional part rounds to 60 → 4.999... ≈ 5:00
        result = wdm._format_split_pace(4.9999, "km")
        # should show 5:00 (rollover) rather than 4:60
        assert "60" not in result

    def test_mi_unit_label(self) -> None:
        """In imperial mode the unit label should be 'min/mi'."""
        result = wdm._format_split_pace(6.0, "mi")
        assert result.endswith("min/mi")

    def test_mi_pace_greater_than_km(self) -> None:
        """min/mi pace value should be larger than min/km for the same speed."""
        minutes_km = int(wdm._format_split_pace(6.0, "km").split(":")[0])
        minutes_mi = int(wdm._format_split_pace(6.0, "mi").split(":")[0])
        assert minutes_mi > minutes_km


class TestFormatSplitSpeed:
    """Unit tests for _format_split_speed()."""

    def test_km_speed_derived_from_pace(self) -> None:
        """6 min/km pace → 10 km/h speed in metric mode."""
        assert wdm._format_split_speed(6.0, "km") == "10.0 km/h"

    def test_faster_pace_gives_higher_speed(self) -> None:
        """5 min/km pace → 12 km/h speed."""
        assert wdm._format_split_speed(5.0, "km") == "12.0 km/h"

    def test_mph_speed_for_imperial(self) -> None:
        """Speed should be formatted as mph in imperial mode."""
        result = wdm._format_split_speed(6.0, "mi")
        assert result.endswith("mph")
        assert "km/h" not in result

    def test_imperial_speed_lower_than_metric(self) -> None:
        """mph value should be lower than the km/h value for the same pace."""
        result_km = wdm._format_split_speed(6.0, "km")
        result_mi = wdm._format_split_speed(6.0, "mi")
        speed_km = float(result_km.split()[0])
        speed_mi = float(result_mi.split()[0])
        assert speed_mi < speed_km


class TestFormatElevationChange:
    """Unit tests for _format_elevation_change()."""

    def test_positive_elevation_shows_plus(self) -> None:
        """Positive elevation change should show a '+' prefix."""
        assert wdm._format_elevation_change(5.3) == "+5 m"

    def test_negative_elevation_shows_minus(self) -> None:
        """Negative elevation change should show a '-' prefix."""
        assert wdm._format_elevation_change(-2.7) == "-3 m"

    def test_zero_elevation_shows_plus_zero(self) -> None:
        """Zero elevation change should show '+0 m'."""
        assert wdm._format_elevation_change(0.0) == "+0 m"

    def test_imperial_shows_feet(self) -> None:
        """In imperial mode the result should use feet."""
        result = wdm._format_elevation_change(10.0, "mi")
        assert result.endswith("ft")
        assert not result.endswith(" m")

    def test_imperial_feet_larger_than_metres(self) -> None:
        """Feet value should be greater than the metre value for the same elevation."""
        m_str = wdm._format_elevation_change(100.0, "km")
        ft_str = wdm._format_elevation_change(100.0, "mi")
        # Format is e.g. "+100 m" / "+328 ft"; parse the numeric part.
        m_val = int(m_str.split()[0].lstrip("+"))
        ft_val = int(ft_str.split()[0].lstrip("+"))
        assert ft_val > m_val


class TestFormatSplitRows:
    """Unit tests for _format_split_rows()."""

    def test_km_pace_includes_unit_label(self) -> None:
        """In km mode the pace string should include 'min/km'."""
        splits = [{"split": 1, "pace_min_per_km": 6.0, "elevation_change_m": 10.0}]
        rows = wdm._format_split_rows(splits, "km")
        assert rows[0]["split"] == 1
        assert rows[0]["pace_str"] == "6:00 min/km"
        assert rows[0]["elev_str"] == "+10 m"

    def test_km_speed_included(self) -> None:
        """In km mode, speed_str should be present with km/h unit."""
        splits = [{"split": 1, "pace_min_per_km": 6.0, "elevation_change_m": 0.0}]
        rows = wdm._format_split_rows(splits, "km")
        assert "speed_str" in rows[0]
        assert rows[0]["speed_str"] == "10.0 km/h"
        assert rows[0]["avg_hr_str"] == "–"

    def test_mi_pace_includes_unit_label_and_is_scaled(self) -> None:
        """In mi mode the pace should be converted to min/mi and labelled 'min/mi'."""
        splits = [{"split": 1, "pace_min_per_km": 6.0, "elevation_change_m": 0.0}]
        rows_km = wdm._format_split_rows(splits, "km")
        rows_mi = wdm._format_split_rows(splits, "mi")
        # unit labels
        assert rows_km[0]["pace_str"].endswith("min/km")
        assert rows_mi[0]["pace_str"].endswith("min/mi")
        # min/mi pace should be larger than min/km for the same speed
        km_minutes = int(rows_km[0]["pace_str"].split(":")[0])
        mi_minutes = int(rows_mi[0]["pace_str"].split(":")[0])
        assert mi_minutes > km_minutes

    def test_mi_speed_in_mph(self) -> None:
        """In mi mode, speed_str should be in mph."""
        splits = [{"split": 1, "pace_min_per_km": 6.0, "elevation_change_m": 0.0}]
        rows = wdm._format_split_rows(splits, "mi")
        assert "speed_str" in rows[0]
        assert rows[0]["speed_str"].endswith("mph")

    def test_mi_elevation_in_feet(self) -> None:
        """In mi mode, elevation should be shown in feet."""
        splits = [{"split": 1, "pace_min_per_km": 6.0, "elevation_change_m": 10.0}]
        rows = wdm._format_split_rows(splits, "mi")
        assert rows[0]["elev_str"].endswith("ft")
        assert not rows[0]["elev_str"].endswith(" m")

    def test_multiple_splits_returned(self) -> None:
        """All splits in the input should be present in the output."""
        splits = [
            {"split": 1, "pace_min_per_km": 5.0, "elevation_change_m": 2.0},
            {"split": 2, "pace_min_per_km": 5.5, "elevation_change_m": -1.0},
        ]
        rows = wdm._format_split_rows(splits, "km")
        assert len(rows) == 2
        assert rows[1]["split"] == 2
        assert rows[1]["elev_str"] == "-1 m"

    def test_avg_heart_rate_is_formatted_when_present(self) -> None:
        """Split rows should show average heart rate when the split includes HR samples."""
        splits = [
            {
                "split": 1,
                "pace_min_per_km": 5.0,
                "elevation_change_m": 2.0,
                "avg_heart_rate": 146.4,
            }
        ]
        rows = wdm._format_split_rows(splits, "km")

        assert rows[0]["avg_hr_str"] == "146 bpm"
