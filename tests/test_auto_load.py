"""Tests for auto-load functionality in the main() function.

These tests verify that when a dev file path is stored in app.storage.general,
the file is automatically loaded when the page is rendered. This includes testing
various scenarios like page refreshes, multiple connections, and error handling.
"""

import asyncio
import logging
from collections.abc import Callable
from unittest.mock import patch

import pytest
from nicegui import app
from nicegui.testing import User


class TestAutoLoadFunctionality:
    """Tests for automatic file loading from app.storage.general."""

    async def test_auto_load_when_dev_file_in_storage(
        self, user: User, create_health_zip: Callable[..., str], caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test that a dev file is auto-loaded when _dev_file_path is set in app storage."""
        # Create a test file
        zip_path = create_health_zip()

        # Set the dev file path in app storage before opening the page
        app.storage.general["_dev_file_path"] = zip_path

        try:
            with caplog.at_level(logging.INFO):
                # Open the page - this should trigger auto-load
                await user.open("/")

                # Wait for the auto-load to complete (ui.timer is set to 1 second)
                await asyncio.sleep(2.0)

                # Verify the file was loaded by checking logs
                log_messages = [record.message for record in caplog.records]
                assert any("Finished parsing in" in msg for msg in log_messages), (
                    "Should log completion message"
                )
                assert any("Total distance of 9" in msg for msg in log_messages), (
                    "Should log workout statistics with total distance of 9"
                )

        finally:
            # Cleanup
            app.storage.general.pop("_dev_file_path", None)
            await asyncio.sleep(0.2)

    async def test_auto_load_sets_input_file_value(
        self, user: User, create_health_zip: Callable[..., str]
    ) -> None:
        """Test that auto-load correctly sets the input_file value."""
        zip_path = create_health_zip()
        app.storage.general["_dev_file_path"] = zip_path

        try:
            await user.open("/")
            await asyncio.sleep(0.5)

            # Check that the input field was populated
            input_elements = list(user.find("Apple Health export file").elements)
            assert len(input_elements) > 0
            input_field = input_elements[0]
            assert input_field.value == zip_path  # type: ignore[attr-defined]
        finally:
            # Cleanup
            app.storage.general.pop("_dev_file_path", None)
            await asyncio.sleep(0.2)

    async def test_auto_load_on_page_refresh(
        self, user: User, create_health_zip: Callable[..., str], caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test that auto-load works correctly when the page is refreshed."""
        zip_path = create_health_zip()
        app.storage.general["_dev_file_path"] = zip_path

        try:
            # Open the page for the first time
            with caplog.at_level(logging.INFO):
                await user.open("/")
                await asyncio.sleep(2.0)

                log_messages = [record.message for record in caplog.records]
                assert any("Finished parsing in" in msg for msg in log_messages), (
                    "Should log completion message on first load"
                )

            caplog.clear()

            # Refresh the page by opening it again
            with caplog.at_level(logging.INFO):
                await user.open("/")
                await asyncio.sleep(2.0)

                # Verify the file is auto-loaded again after refresh
                log_messages = [record.message for record in caplog.records]
                assert any("Finished parsing in" in msg for msg in log_messages), (
                    "Should log completion message after refresh"
                )
                assert any("Total distance of 9" in msg for msg in log_messages), (
                    "Should log workout statistics with total distance of 9"
                )
        finally:
            # Cleanup
            app.storage.general.pop("_dev_file_path", None)
            await asyncio.sleep(0.2)

    async def test_no_auto_load_when_dev_file_not_in_storage(self, user: User) -> None:
        """Test that no auto-load occurs when _dev_file_path is not in app storage."""
        # Ensure _dev_file_path is not in storage
        if "_dev_file_path" in app.storage.general:
            del app.storage.general["_dev_file_path"]

        await user.open("/")
        await asyncio.sleep(2.0)

        # Verify no file was loaded (should still see zero values)
        await user.should_see("Apple Health Analyzer")
        # Should not see the "Finished parsing" message
        input_elements = list(user.find("Apple Health export file").elements)
        assert len(input_elements) > 0
        input_field = input_elements[0]
        assert input_field.value == ""  # type: ignore[attr-defined]

        await asyncio.sleep(0.2)

    async def test_auto_load_with_invalid_file_path(self, user: User) -> None:
        """Test that auto-load handles invalid file paths gracefully."""
        # Set an invalid file path in storage
        invalid_path = "/nonexistent/file.zip"
        app.storage.general["_dev_file_path"] = invalid_path

        try:
            await user.open("/")
            await asyncio.sleep(2.0)

            # Verify error message is shown
            await user.should_see("No such file or directory", retries=50)
        finally:
            # Cleanup
            app.storage.general.pop("_dev_file_path", None)
            await asyncio.sleep(0.2)

    async def test_auto_load_timer_called_once(
        self, user: User, create_health_zip: Callable[..., str]
    ) -> None:
        """Test that the auto-load timer is set up with correct parameters."""
        zip_path = create_health_zip()

        with patch("nicegui.ui.timer") as mock_timer:
            app.storage.general["_dev_file_path"] = zip_path

            try:
                await user.open("/")
                await asyncio.sleep(0.5)

                # Verify ui.timer was called with correct parameters
                mock_timer.assert_called_once()
                call_args = mock_timer.call_args

                # Check the interval is 1.0 second
                assert call_args[0][0] == pytest.approx(1.0)  # type: ignore[arg-type]

                # Check the 'once' parameter is True
                assert call_args[1].get("once") is True, "Timer should be set to run once"
            finally:
                # Cleanup
                app.storage.general.pop("_dev_file_path", None)
                await asyncio.sleep(0.2)

    async def test_auto_load_logging_messages(
        self, user: User, create_health_zip: Callable[..., str], caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test that auto-load logs appropriate messages."""
        zip_path = create_health_zip()
        app.storage.general["_dev_file_path"] = zip_path

        try:
            with caplog.at_level(logging.INFO):
                await user.open("/")
                await asyncio.sleep(2.5)

                # Check for expected log messages
                log_messages = [record.message for record in caplog.records]

                # Should log that dev file will be auto-loaded
                assert any(
                    "Dev file will be auto-loaded" in msg and zip_path in msg
                    for msg in log_messages
                ), "Should log dev file auto-load intention"

                # Should log the actual auto-loading
                assert any(
                    "Auto-loading file" in msg and zip_path in msg for msg in log_messages
                ), "Should log auto-loading action"
        finally:
            # Cleanup
            app.storage.general.pop("_dev_file_path", None)
            await asyncio.sleep(0.2)

    async def test_auto_load_with_multiple_page_opens(
        self, user: User, create_health_zip: Callable[..., str], caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test auto-load behavior with multiple page opens (multiple connections)."""
        zip_path = create_health_zip()
        app.storage.general["_dev_file_path"] = zip_path

        try:
            # Open the page multiple times in sequence
            for _ in range(3):
                with caplog.at_level(logging.INFO):
                    await user.open("/")
                    await asyncio.sleep(2.0)

                    # Each time should trigger auto-load
                    log_messages = [record.message for record in caplog.records]
                    assert any("Finished parsing in" in msg for msg in log_messages), (
                        "Should log completion message"
                    )
                    assert any("Total distance of 9" in msg for msg in log_messages), (
                        "Should log workout statistics with total distance of 9"
                    )

                caplog.clear()
        finally:
            # Cleanup
            app.storage.general.pop("_dev_file_path", None)
            await asyncio.sleep(0.2)

    async def test_auto_load_does_not_occur_with_none_value(self, user: User) -> None:
        """Test that auto-load does not occur when _dev_file_path is explicitly None."""
        # Set the value to None explicitly
        app.storage.general["_dev_file_path"] = None

        try:
            await user.open("/")
            await asyncio.sleep(2.0)

            # Verify no file was loaded
            input_elements = list(user.find("Apple Health export file").elements)
            assert len(input_elements) > 0
            input_field = input_elements[0]
            assert input_field.value == ""  # type: ignore[attr-defined]
        finally:
            # Cleanup
            app.storage.general.pop("_dev_file_path", None)
            await asyncio.sleep(0.2)

    async def test_auto_load_with_empty_string(self, user: User) -> None:
        """Test behavior when _dev_file_path is an empty string.

        The implementation checks 'if dev_file:' so an empty string is falsy
        and will NOT trigger the auto-load logic. The ui.timer should not be called.
        """
        app.storage.general["_dev_file_path"] = ""

        try:
            with patch("apple_health_analyzer.ui.timer") as mock_timer:
                await user.open("/")
                await asyncio.sleep(0.5)

                # Empty string is falsy, so the timer should NOT be set
                mock_timer.assert_not_called()
        finally:
            # Cleanup
            app.storage.general.pop("_dev_file_path", None)
            await asyncio.sleep(0.2)
