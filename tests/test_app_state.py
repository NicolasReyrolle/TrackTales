"""Tests for AppState class."""

from datetime import datetime

from app_state import AppState


class TestAppStateDateProperties:
    """Tests for start_date and end_date properties of AppState."""

    def test_start_date_with_empty_date_range(self) -> None:
        """Test that start_date returns None when date_range_text is empty."""
        app_state = AppState()
        app_state.date_range_text = ""
        assert app_state.start_date is None

    def test_end_date_with_empty_date_range(self) -> None:
        """Test that end_date returns None when date_range_text is empty."""
        app_state = AppState()
        app_state.date_range_text = ""
        assert app_state.end_date is None

    def test_start_date_with_valid_date_range(self) -> None:
        """Test that start_date correctly parses the start date from date_range_text."""
        app_state = AppState()
        app_state.date_range_text = "2024-01-15 - 2024-12-31"
        expected_date = datetime(2024, 1, 15)
        assert app_state.start_date == expected_date

    def test_end_date_with_valid_date_range(self) -> None:
        """Test that end_date correctly parses the end date from date_range_text."""
        app_state = AppState()
        app_state.date_range_text = "2024-01-15 - 2024-12-31"
        expected_date = datetime(2024, 12, 31)
        assert app_state.end_date == expected_date

    def test_start_date_with_single_digit_month_and_day(self) -> None:
        """Test that start_date handles dates with single-digit months and days."""
        app_state = AppState()
        app_state.date_range_text = "2024-03-05 - 2024-09-25"
        expected_date = datetime(2024, 3, 5)
        assert app_state.start_date == expected_date

    def test_end_date_with_single_digit_month_and_day(self) -> None:
        """Test that end_date handles dates with single-digit months and days."""
        app_state = AppState()
        app_state.date_range_text = "2024-03-05 - 2024-09-25"
        expected_date = datetime(2024, 9, 25)
        assert app_state.end_date == expected_date

    def test_start_date_without_separator(self) -> None:
        """Test that start_date returns None when separator is missing."""
        app_state = AppState()
        app_state.date_range_text = "2024-01-15"
        assert app_state.start_date is None

    def test_end_date_without_separator(self) -> None:
        """Test that end_date returns None when separator is missing."""
        app_state = AppState()
        app_state.date_range_text = "2024-01-15"
        assert app_state.end_date is None

    def test_start_date_with_invalid_format_raises_error(self) -> None:
        """Test that start_date returns None when date format is invalid."""
        app_state = AppState()
        app_state.date_range_text = "01-15-2024 - 12-31-2024"  # Wrong format
        assert app_state.start_date is None

    def test_end_date_with_invalid_format_raises_error(self) -> None:
        """Test that end_date returns None when date format is invalid."""
        app_state = AppState()
        app_state.date_range_text = "2024-01-15 - 12-31-2024"  # End date wrong format
        assert app_state.end_date is None

    def test_start_date_with_leap_year(self) -> None:
        """Test that start_date correctly handles leap year dates."""
        app_state = AppState()
        app_state.date_range_text = "2024-02-29 - 2024-12-31"  # 2024 is a leap year
        expected_date = datetime(2024, 2, 29)
        assert app_state.start_date == expected_date

    def test_end_date_with_leap_year(self) -> None:
        """Test that end_date correctly handles leap year dates."""
        app_state = AppState()
        app_state.date_range_text = "2024-01-01 - 2024-02-29"  # 2024 is a leap year
        expected_date = datetime(2024, 2, 29)
        assert app_state.end_date == expected_date

    def test_date_range_with_same_start_and_end(self) -> None:
        """Test that start_date and end_date work when they are the same."""
        app_state = AppState()
        app_state.date_range_text = "2024-06-15 - 2024-06-15"
        assert app_state.start_date == datetime(2024, 6, 15)
        assert app_state.end_date == datetime(2024, 6, 15)

    def test_date_range_persists_across_multiple_accesses(self) -> None:
        """Test that date properties can be accessed multiple times consistently."""
        app_state = AppState()
        app_state.date_range_text = "2024-01-01 - 2024-12-31"

        # Access multiple times
        start1 = app_state.start_date
        end1 = app_state.end_date
        start2 = app_state.start_date
        end2 = app_state.end_date

        assert start1 == start2
        assert end1 == end2

    def test_start_date_with_slash_separator(self) -> None:
        """Test that start_date accepts slash-separated dates (YYYY/MM/DD)."""
        app_state = AppState()
        app_state.date_range_text = "2024/01/15 - 2024/12/31"
        expected_date = datetime(2024, 1, 15)
        assert app_state.start_date == expected_date

    def test_end_date_with_slash_separator(self) -> None:
        """Test that end_date accepts slash-separated dates (YYYY/MM/DD)."""
        app_state = AppState()
        app_state.date_range_text = "2024/01/15 - 2024/12/31"
        expected_date = datetime(2024, 12, 31)
        assert app_state.end_date == expected_date

    def test_reset_clears_date_range_text(self) -> None:
        """Test that reset() clears the date_range_text."""
        app_state = AppState()
        app_state.date_range_text = "2024-01-01 - 2024-12-31"

        app_state.reset()

        assert app_state.date_range_text == ""
        assert app_state.start_date is None
        assert app_state.end_date is None

    def test_start_date_with_whitespace_only_date(self) -> None:
        """Test that start_date returns None when date part is only whitespace."""
        app_state = AppState()
        app_state.date_range_text = "   - 2024-12-31"
        assert app_state.start_date is None

    def test_end_date_with_whitespace_only_date(self) -> None:
        """Test that end_date returns None when date part is only whitespace."""
        app_state = AppState()
        app_state.date_range_text = "2024-01-01 -    "
        assert app_state.end_date is None


class TestAppStateBestSegmentsState:
    """Tests for AppState defaults related to best-segment UI state."""

    def test_defaults_include_best_segments_fields(self) -> None:
        """A new AppState should initialize best-segments and tab state fields."""
        app_state = AppState()

        assert not app_state.best_segments_rows
        assert app_state.best_segments_loading is False
        assert app_state.best_segments_loaded is False
        assert app_state.best_segments_task is None
        assert app_state.selected_main_tab == "summary"

    def test_reset_restores_best_segments_fields(self) -> None:
        """reset should restore best-segments cache flags and selected tab."""
        app_state = AppState()
        app_state.best_segments_rows = [{"distance": "1.0 km"}]
        app_state.best_segments_loading = True
        app_state.best_segments_loaded = True
        app_state.best_segments_task = object()  # type: ignore[assignment]
        app_state.selected_main_tab = "best_segments"

        app_state.reset()

        assert not app_state.best_segments_rows
        assert app_state.best_segments_loading is False
        assert app_state.best_segments_loaded is False
        assert app_state.best_segments_task is None
        assert app_state.selected_main_tab == "summary"
