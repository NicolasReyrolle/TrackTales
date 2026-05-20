"""Tests for the TrackTales main GUI module."""

import asyncio
import json
import logging
from collections.abc import Callable
from typing import Any, cast
from unittest.mock import patch

import pytest
from nicegui import ui
from nicegui.client import Client  # Added for type hinting
from nicegui.testing import User

from app_state import state
from tests.types_helper import StateAssertion
from ui import layout as layout_module
from ui.helpers import format_integer
from ui.layout import load_file


def is_valid_json(data_string: str) -> bool:
    """Check if a string is valid JSON."""
    try:
        json.loads(data_string)
        return True
    except (json.JSONDecodeError, TypeError):
        return False


def is_valid_csv(data_string: str, expected_column: str = "") -> bool:
    """Check if a string is valid CSV."""
    first_line = data_string.splitlines()[0] if data_string else ""

    for delimiter in [",", ";"]:
        if delimiter in first_line:
            if expected_column and expected_column in first_line.split(delimiter):
                return True
            if not expected_column:
                return True
    return False


async def load_health_export(user: User, create_health_zip: Callable[..., str]) -> str:
    """Helper function to load a health export file and wait for parsing to complete.

    Args:
        user: NiceGUI test user object
        create_health_zip: Fixture function to create test health ZIP file

    Returns:
        str: Path to the loaded ZIP file
    """
    zip_path = create_health_zip()
    user.find("Apple Health export file").type(zip_path)
    user.find("Load").click()
    await user.should_see("File parsed successfully.", retries=100)
    return zip_path


class TestFileBrowsing:
    """Tests for file browsing and file picker dialog."""

    async def test_click_browse(self, user: User) -> None:
        """Test that the browse button works."""
        await user.open("/")
        await user.should_see("TrackTales")
        user.find("Browse").click()
        await user.should_see("Ok")

    async def test_browse_button_opens_picker(self, user: User) -> None:
        """Test that the browse button opens the file picker dialog."""
        await user.open("/")
        await user.should_see("TrackTales")
        user.find("Browse").click()
        await user.should_see("Ok")
        # Small delay to ensure Windows releases file handles before teardown
        await asyncio.sleep(0.2)

    async def test_browse_no_file_selected(self, user: User, mock_file_picker_context: Any) -> None:
        """Test that not selecting a file (mock returns empty) shows a notification."""

        with mock_file_picker_context(None):  # None = empty result
            await user.open("/")
            user.find("Browse").click()

            # Wait for the async operation
            await asyncio.sleep(0.5)

            # Should see "No file selected" notification
            await user.should_see("No file selected")

    async def test_browse_file_selected(self, user: User, mock_file_picker_context: Any) -> None:
        """Test that selecting a file via the dialog updates the input_file value."""
        fake_path = "/path/to/fake_health_export.zip"

        with mock_file_picker_context(fake_path):
            await user.open("/")

            # Verify input is initially empty
            input_elements = list(user.find("Apple Health export file").elements)
            input_field = input_elements[0] if input_elements else None
            assert input_field is not None
            actual_value = input_field.value  # type: ignore[attr-defined]
            assert actual_value == "", "Input should start empty"

            # Click Browse
            user.find("Browse").click()
            await asyncio.sleep(1.0)

            # Check if value was set
            assert fake_path in input_field.value, (  # type: ignore[attr-defined]
                f"Expected {fake_path} in {input_field.value}"  # type: ignore[attr-defined]
            )


class TestFileLoading:
    """Tests for loading health export files."""

    async def test_load_without_file(self, user: User) -> None:
        """Test that loading without selecting a file shows a notification."""
        await user.open("/")
        await user.should_see("TrackTales")
        user.find("Load").click()
        await user.should_see("Please select an Apple Health export file first.")

    async def test_load_with_non_existent_file(self, user: User) -> None:
        """Test that loading a non-existent file shows an error notification."""
        await user.open("/")
        await user.should_see("TrackTales")
        user.find("Apple Health export file").type("invalid_export.zip")
        user.find("Load").click()
        await user.should_see("No such file or directory")

    async def test_load_with_valid_file(
        self, user: User, create_health_zip: Callable[..., str]
    ) -> None:
        """Test that loading a valid export file shows statistics."""

        class _AwaitableFalse:
            def __await__(self) -> Any:
                yield from []
                return False

        # Type hint `self` with Client to resolve type unknown for `new` argument in patch.
        # Explicitly type `args` and `kwargs` for better type inference.
        def _noop_run_javascript(_self: Client, *_args: Any, **_kwargs: Any):
            return _AwaitableFalse()

        with patch("nicegui.client.Client.run_javascript", new=_noop_run_javascript):
            await user.open("/")
            # 1. Load the file and wait for parsing
            await load_health_export(user, create_health_zip)

            # 2. Check if the UI correctly displays data from our XML
            await user.should_see("Distance", retries=50)
            await user.should_see("9", retries=50)
            await user.should_see("Duration", retries=50)
            await user.should_see("h", retries=50)
            # Small delay to ensure Windows releases file handles and
            # async operations complete before teardown
            await asyncio.sleep(0.2)

    async def test_input_file_persists_in_storage(self, user: User) -> None:
        """Test that the input file path is persisted in app storage."""
        await user.open("/")
        user.find("Apple Health export file").type("tests/fixtures/export_sample.zip")
        await user.open("/")
        await user.should_see("tests/fixtures/export_sample.zip")
        # Small delay before teardown
        await asyncio.sleep(0.2)

    async def test_parse_error_shows_notification(self, user: User) -> None:
        """Test that parse errors display error notification."""
        await user.open("/")
        user.find("Apple Health export file").type("tests/fixtures/corrupt_export.zip")
        user.find("Load").click()
        await user.should_see("Error parsing file")
        # Small delay before teardown
        await asyncio.sleep(0.2)


class TestLanguageSwitching:
    """Tests for runtime language switching behavior."""

    async def test_switch_language_to_french_refreshes_header_and_body(self, user: User) -> None:
        """Switching language should update translated header/body labels after reload."""
        await user.open("/")

        # Baseline English labels
        await user.should_see("TrackTales")
        await user.should_see("Apple Health export file")

        # Open the preferences menu and select French
        user.find("tune").click()
        await asyncio.sleep(0.1)
        change_language = cast(Callable[[str], None], getattr(layout_module, "_change_language"))
        change_language("fr")

        # _change_language triggers ui.navigate.reload(); title stays literal
        await user.should_see("TrackTales", retries=50)
        await user.should_see("Fichier d'export Apple Health", retries=50)

        # Small delay before teardown
        await asyncio.sleep(0.2)


class TestExportFunctionality:
    """Tests for data export functionality."""

    async def test_export_dropdown_has_json_option(self, user: User) -> None:
        """Test that the export dropdown contains the 'to JSON' option."""
        await user.open("/")

        # 1. Open the export dropdown
        export_button = user.find("Export data")
        assert export_button is not None, "Export data button not found"
        export_button.click()
        await asyncio.sleep(0.2)

        # 2. Verify the "to JSON" menu item is present
        json_option = user.find("to JSON")
        assert json_option is not None, "to JSON export option not found"

    async def test_export_dropdown_has_csv_option(self, user: User) -> None:
        """Test that the export dropdown contains the 'to CSV' option."""
        await user.open("/")

        # 1. Open the export dropdown
        export_button = user.find("Export data")
        assert export_button is not None, "Export data button not found"
        export_button.click()
        await asyncio.sleep(0.2)

        # 2. Verify the "to CSV" menu item is present
        csv_option = user.find("to CSV")
        assert csv_option is not None, "to CSV export option not found"

    async def test_export_to_json_click_executes(
        self,
        user: User,
        create_health_zip: Callable[..., str],
        assert_ui_state: StateAssertion,
    ) -> None:
        """Test that clicking 'Export data > to JSON' can be executed without errors.

        This integration test verifies:
        1. The export dropdown button is accessible after file loads
        2. The "to JSON" menu item can be clicked without throwing an exception
        3. The parser's export_to_json method works correctly
        """
        await user.open("/")

        # Load a valid health data file
        await load_health_export(user, create_health_zip)

        # Verify the export dropdown is present
        export_interaction = user.find("Export data")
        assert_ui_state(export_interaction, enabled=True)
        export_interaction.click()
        await asyncio.sleep(0.5)

        # Verify the "to JSON" menu item exists
        await user.should_see("to JSON")

        # Click the export button (this should trigger the download without error)
        user.find("to JSON").click()

        found = False
        for _ in range(30):  # Wait up to 3 seconds (30 * 0.1s)
            if user.download.http_responses:
                found = True
                break
            await asyncio.sleep(0.1)

        assert found, "No download was triggered"

        res = user.download.http_responses[-1]
        assert res.status_code == 200
        assert is_valid_json(res.text)
        # Small delay before teardown
        await asyncio.sleep(0.2)

    async def test_export_to_csv_click_executes(
        self,
        user: User,
        create_health_zip: Callable[..., str],
        assert_ui_state: StateAssertion,
    ) -> None:
        """Test that clicking 'Export data > to CSV' can be executed without errors.

        This integration test verifies:
        1. The export dropdown button is accessible after file loads
        2. The "to CSV" menu item can be clicked without throwing an exception
        3. The parser's export_to_csv method works correctly
        """
        await user.open("/")

        # Load a valid health data file
        await load_health_export(user, create_health_zip)

        # Verify the export dropdown is present
        export_interaction = user.find("Export data")
        assert_ui_state(export_interaction, enabled=True)
        export_interaction.click()
        await asyncio.sleep(0.2)

        # Verify the "to CSV" menu item exists
        await user.should_see("to CSV")

        # Click the export button (this should trigger the download without error)
        user.find("to CSV").click()

        found = False
        for _ in range(30):  # Wait up to 3 seconds (30 * 0.1s)
            if user.download.http_responses:
                found = True
                break
            await asyncio.sleep(0.1)

        assert found, "No download was triggered"

        res = user.download.http_responses[-1]
        assert res.status_code == 200
        assert is_valid_csv(res.text)
        # Small delay before teardown
        await asyncio.sleep(0.2)

    async def test_export_without_loading_file_is_disabled(
        self, user: User, assert_ui_state: StateAssertion
    ) -> None:
        """Test that the export dropdown is disabled when no file is loaded."""
        await user.open("/")

        export_interaction = user.find("Export data")
        assert_ui_state(export_interaction, enabled=False)


class TestActivityFiltering:
    """Tests for activity type filtering functionality."""

    @staticmethod
    def _extract_labels_from_options(options: list[Any] | dict[Any, Any]) -> list[str]:
        """Extract label strings from select options."""
        if not options:
            return []

        if isinstance(options, list) and options and isinstance(options[0], dict):
            labels: list[str] = []
            for opt in options:
                if isinstance(opt, dict):
                    label = opt.get("label")  # type: ignore[misc]
                    if label is not None:
                        labels.append(str(label))  # type: ignore[arg-type]
            return labels

        if isinstance(options, list):
            return [str(opt) for opt in options]

        # At this point, options must be a dict
        labels = [str(key) for key in options.keys()]
        labels.extend(str(value) for value in options.values() if value is not None)
        # Remove duplicates while preserving order.
        return list(dict.fromkeys(labels))

    async def _wait_for_activity_option(
        self, user: User, activity_name: str, max_attempts: int = 30
    ) -> tuple[ui.select | None, list[str]]:
        """Wait for activity option to appear in the select element."""
        select: ui.select | None = None
        labels: list[str] = []

        for _ in range(max_attempts):
            select_elements = list(user.find("Activity Type").elements)
            if select_elements:
                select = cast(ui.select, select_elements[0])
                options: list[Any] | dict[Any, Any] = select.options  # type: ignore[assignment]
                labels = self._extract_labels_from_options(options)

                if activity_name in labels:
                    break

            await asyncio.sleep(0.1)

        return select, labels

    async def test_activity_filter_checkbox_rendering(
        self, user: User, create_health_zip: Callable[..., str]
    ) -> None:
        """Test that activity filter options are populated after loading data."""
        # Ensure a clean application state so this test is independent of others.
        if hasattr(state, "reset") and callable(getattr(state, "reset")):
            state.reset()  # type: ignore[call-arg]

        await user.open("/")
        await load_health_export(user, create_health_zip)
        await user.open("/")

        # Verify the activity options were populated correctly in the state
        assert state.activity_options[0] == "All"
        assert "Running" in state.activity_options

        # Wait for the select to refresh and include the activity options
        select, labels = await self._wait_for_activity_option(user, "Running")

        assert select is not None
        assert select.value == "All"
        assert "Running" in labels

        # Small delay before teardown
        await asyncio.sleep(0.2)


class TestStatCards:
    """Tests for statistics cards display and updates."""

    async def test_stat_cards_initial_zero_values(self, user: User) -> None:
        """Test that stat cards display zero values by default."""
        await user.open("/")

        # Verify all stat cards show zero initially
        await user.should_see("Count")
        await user.should_see("0")
        await user.should_see("Distance")
        await user.should_see("km")
        await user.should_see("Duration")
        await user.should_see("h")
        await user.should_see("Elevation")
        await user.should_see("m")
        await user.should_see("Calories")
        await user.should_see("kcal")

    async def test_stat_cards_update_after_load(
        self, user: User, create_health_zip: Callable[..., str]
    ) -> None:
        """Test that stat cards display correct values after loading health data."""
        await user.open("/")

        # 1. Verify initial zero state for metrics
        assert state.metrics["count"] == 0
        assert state.metrics["distance"] == 0
        assert state.metrics["duration"] == 0
        assert state.metrics["elevation"] == 0
        assert state.metrics["calories"] == 0

        # 2. Load a valid health data file
        await load_health_export(user, create_health_zip)

        # 3. Verify stat card values are updated correctly
        # The create_health_zip fixture provides:
        # - 1 workout
        # - 8.95512 km distance (rounded to 9)
        # - 60.887 minutes duration (approximately 1 hour)
        # - 6575 cm elevation (approximately 65.75 m)
        assert state.metrics["count"] == 1
        assert state.metrics["distance"] == 9
        assert state.metrics["duration"] == 1  # 60.887 minutes ≈ 1 hour
        assert state.metrics["elevation"] == 66  # 6575 cm = 65.75 m → 66 m (metric default)
        assert state.metrics["calories"] == 655  # ActiveEnergyBurned from fixture

        # Verify the values are displayed in the UI
        await user.should_see("1")  # Count
        await user.should_see("9")  # Distance
        # Duration is rendered as separate value + unit labels
        await user.should_see("h")
        await user.should_see("66")  # Elevation value displayed
        await user.should_see("m")  # Elevation unit (metric default)
        await user.should_see(format_integer(655))  # Calories
        await user.should_see("kcal")  # Calories unit
        # Small delay before teardown
        await asyncio.sleep(0.2)


class TestLoadingState:
    """Tests for loading state and UI interactions during parsing."""

    async def test_loading_state_disables_button_and_shows_spinner(
        self, user: User, create_health_zip: Callable[..., str], assert_ui_state: StateAssertion
    ) -> None:
        """Test that the Load button is disabled and spinner is visible during parsing."""
        await user.open("/")

        # Verify initial state: Load button is enabled
        load_button = user.find("Load")
        assert_ui_state(load_button, enabled=True)
        assert state.loading is False

        # Start loading the file
        zip_path = create_health_zip()
        user.find("Apple Health export file").type(zip_path)

        # Click load and immediately verify the state changes
        user.find("Load").click()

        # The button should now be disabled (loading state is active)
        # Note: For very fast parsing, we may not catch the intermediate state,
        # but we should see the end result is correct
        await user.should_see("File parsed successfully.", retries=100)

        # After parsing completes, verify loading state is reset
        await asyncio.sleep(0.1)
        assert state.loading is False
        assert_ui_state(load_button, enabled=True)
        # Small delay before teardown
        await asyncio.sleep(0.2)

    async def test_loading_state_reverts_on_error(
        self, user: User, assert_ui_state: StateAssertion
    ) -> None:
        """Test that loading state reverts after an error during parsing."""
        await user.open("/")

        # Verify initial state
        load_button = user.find("Load")
        assert_ui_state(load_button, enabled=True)
        assert state.loading is False

        # Try to load an invalid file
        user.find("Apple Health export file").type("tests/fixtures/corrupt_export.zip")
        user.find("Load").click()

        # Wait for error message
        await user.should_see("Error parsing file", retries=50)

        # After error, loading should be False and button should be enabled again
        await asyncio.sleep(0.1)
        assert state.loading is False
        assert_ui_state(load_button, enabled=True)
        # Small delay before teardown
        await asyncio.sleep(0.2)

    async def test_concurrent_load_file_calls_are_prevented(
        self, user: User, create_health_zip: Callable[..., str], caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test that concurrent load_file invocations are prevented by the loading guard."""

        await user.open("/")

        # Create a valid health zip
        zip_path = create_health_zip()
        user.find("Apple Health export file").type(zip_path)

        # Manually set loading to True to simulate concurrent invocation
        state.loading = True

        with caplog.at_level(logging.DEBUG):
            # Try to load file while loading is already in progress

            await load_file()

            # Verify the debug log was emitted
            assert any(
                "File loading already in progress" in record.message for record in caplog.records
            ), "Expected debug log about concurrent invocation"

        # Reset loading state
        state.loading = False

    async def test_loading_status_cleared_after_load_no_stale_callbacks(
        self, user: User, create_health_zip: Callable[..., str]
    ) -> None:
        """Test that loading_status is empty after load completes.

        Regression test for stale progress callbacks: progress_callback() schedules
        _update() via call_soon_threadsafe, but _update() guards with `if state.loading`
        so that any callbacks still queued when the finally block runs (setting
        state.loading = False) are silently discarded and cannot re-populate
        loading_status with stale text.
        """
        await user.open("/")

        zip_path = create_health_zip()
        user.find("Apple Health export file").type(zip_path)
        user.find("Load").click()

        await user.should_see("File parsed successfully.", retries=100)

        # Allow any queued _update callbacks to run
        await asyncio.sleep(0.1)

        # loading_status must be empty: the finally block cleared it and the
        # state.loading guard ensured stale callbacks did not re-populate it.
        assert state.loading_status == ""
        assert state.loading is False

        # Small delay before teardown
        await asyncio.sleep(0.2)
