"""Fixtures for testing TrackTales."""

import asyncio
import contextlib
import logging
import os
import shutil
import tempfile
import uuid
import zipfile
from collections.abc import Callable, Generator, Iterator
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any
from unittest.mock import patch

import nicegui.storage
import pytest
from nicegui.testing import UserInteraction

from app_state import state as app_state

from .types_helper import StateAssertion

EXPORT_FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "exports"
DEFAULT_EXPORT_FIXTURE = "workout_running.xml"


@pytest.fixture
def load_export_fragment() -> Callable[[str], str]:
    """Load a workout fragment from the export fixtures directory."""

    def _loader(file_name: str) -> str:
        fixture_path = EXPORT_FIXTURES_DIR / file_name
        return fixture_path.read_text(encoding="utf-8")

    return _loader


@pytest.fixture
def build_health_export_xml() -> Callable[[list[str]], str]:
    """Wrap workout fragments in a minimal HealthData document."""

    def _builder(workout_fragments: list[str]) -> str:
        workouts_xml = "\n".join(workout_fragments)
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<HealthData version="11">
    <ExportDate value="2026-01-20 22:00:00 +0100"/>
{workouts_xml}
</HealthData>
"""

    return _builder


@pytest.fixture
def create_health_zip(
    tmp_path: Path,
    load_export_fragment: Callable[[str], str],
    build_health_export_xml: Callable[[list[str]], str],
) -> Callable[..., str]:
    """
    Factory fixture to generate a temporary Apple Health export ZIP file.
    Uses tmp_path, which pytest cleans up automatically after each test.
    """

    def _generate(xml_content: str | None = None, fixture_name: str | None = None) -> str:
        # If no explicit XML content is provided, load it from a fixture file
        if xml_content is None:
            if fixture_name is None:
                fixture_name = DEFAULT_EXPORT_FIXTURE

            fragment = load_export_fragment(fixture_name)
            xml_content = build_health_export_xml([fragment])

        # Generate a short unique ID for the filename to avoid collisions
        unique_id = uuid.uuid4().hex[:8]
        zip_path = tmp_path / f"export_{unique_id}.zip"
        internal_path = "apple_health_export/export.xml"

        # Ensure we have content to write
        assert xml_content is not None, "XML content must be provided or resolvable"

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            zipf.writestr(internal_path, xml_content)

        return str(zip_path)

    return _generate


@pytest.fixture
def mock_file_picker_context() -> Callable[[str | None], AbstractContextManager[None]]:
    """
    Fixture providing a Context Manager to mock-up LocalFilePicker.
    """

    @contextlib.contextmanager
    def _mocker(return_path: str | None = None) -> Iterator[None]:
        target = "ui.layout.LocalFilePicker"
        result_value: list[str] = [return_path] if return_path else []

        # Create an awaitable object that returns the result
        class AwaitableMock:
            """Mock class to simulate an awaitable LocalFilePicker."""

            def __await__(self) -> Generator[Any, None, list[str]]:
                future: asyncio.Future[list[str]] = asyncio.Future()
                future.set_result(result_value)
                return future.__await__()

        with patch(target) as mock_class:
            mock_class.return_value = AwaitableMock()
            yield

    return _mocker


@pytest.fixture(autouse=True, scope="session")
def setup_test_environment() -> Generator[Any, Any, Any]:
    """Fixture to set up a temporary NiceGUI storage path for tests."""
    test_dir = tempfile.mkdtemp()
    os.environ["NICEGUI_STORAGE_PATH"] = test_dir

    yield

    shutil.rmtree(test_dir, ignore_errors=True)


@pytest.fixture
def assert_ui_state() -> StateAssertion:
    """
    Helper fixture to verify the state of a NiceGUI element.
    Using a Protocol instead of Callable to support optional arguments
    without triggering 'Expected more positional arguments' errors.
    """

    def _assert(
        interaction: UserInteraction[Any],
        enabled: bool | None = None,
        visible: bool | None = None,
    ) -> None:
        # Check if any elements were found
        assert interaction.elements, f"No elements found for: {interaction}"

        # Get the underlying element
        element = next(iter(interaction.elements))

        # 1. Check Visibility
        if visible is not None:
            actual_visible = element.visible
            state_str = "visible" if visible else "hidden"
            assert actual_visible == visible, f"Element should be {state_str}."

        # 2. Check Enabled state
        if enabled is not None:
            # Cast to Any to access protected member _props
            element_any: Any = element
            is_disabled = element_any._props.get("disable", False)
            actual_enabled = not is_disabled
            state_str = "enabled" if enabled else "disabled"
            assert actual_enabled == enabled, f"Element should be {state_str}."

    return _assert


# --- Global Patch to prevent WinError 32 during teardown ---
PersistentDict = getattr(nicegui.storage, "PersistentDict")
original_clear = PersistentDict.clear


def _remove_storage_file(filepath: Path) -> None:
    """Remove a storage file, ignoring Windows file lock errors."""
    try:
        os.remove(str(filepath))
    except OSError as exc:
        logging.debug("Ignoring storage file removal error for %s: %s", filepath, exc)


def _clear_storage_directory(path: Path) -> None:
    """Clear all storage files from a directory."""
    for filepath in path.glob("storage-*.json"):
        _remove_storage_file(filepath)


def _resolve_storage_path(obj: Any) -> Path | None:
    """Resolve the storage path from an object's attributes."""
    path = getattr(obj, "path", getattr(obj, "_path", None))
    return path


def patched_clear(self: Any) -> None:
    """
    Safely clear NiceGUI storage by ignoring Windows file locks.
    Calls the original dictionary clear directly to avoid recursion.
    """
    path = _resolve_storage_path(self)

    if path is not None:
        path_str = str(path)
        if os.path.exists(path_str):
            if os.path.isdir(path_str):
                _clear_storage_directory(path)
            elif os.path.isfile(path_str):
                _remove_storage_file(path)

    dict.clear(self)  # type: ignore


# 3. Apply the patch
PersistentDict.clear = patched_clear


@pytest.fixture(autouse=True)
def reset_app_state():
    """Fixture to reset the application state before each test."""
    app_state.reset()


Storage = nicegui.storage.Storage


class NiceGUIErrorFilter(logging.Filter):
    """
    Filter to intercept and block specific known error messages from NiceGUI
    that are harmless during test teardown but cause pytest failures.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        # Convert message and exception info to string for searching
        # record.getMessage() gets the main message
        log_message = record.getMessage()

        # 1. Block the "Client deleted" error (Race condition on refresh)
        if "The client this element belongs to has been deleted" in log_message:
            return False  # Return False to DROP this log record

        # 2. Block the "binding_refresh_interval" error (Config corruption on exit)
        if "binding_refresh_interval" in log_message:
            return False

        # Allow all other logs
        return True


@pytest.fixture(autouse=True)
def filter_nicegui_errors() -> Generator[None, None, None]:
    """
    Automatically attach the custom error filter to the NiceGUI logger
    for every test.
    """
    # Get the main NiceGUI logger
    logger = logging.getLogger("nicegui")

    # Create and add our firewall
    error_filter = NiceGUIErrorFilter()
    logger.addFilter(error_filter)

    yield

    # Clean up: remove the filter to avoid side effects if we run other things later
    logger.removeFilter(error_filter)


@pytest.fixture
def clean_logger() -> Generator[logging.Logger, None, None]:
    """
    Fixture to provide a clean logger with all handlers properly closed and removed.

    This fixture ensures file descriptors are not left open (especially critical on Windows
    where RotatingFileHandler can prevent temp directory cleanup).

    Yields:
        logging.Logger: The root logger, cleaned of all handlers and ready for testing

    Cleanup:
        Automatically closes all handlers and removes them from the logger after the test
    """
    logger = logging.getLogger()

    # Pre-cleanup: close and remove any existing handlers from previous tests
    for handler in list(logger.handlers):  # noqa: S7504
        try:
            handler.close()
        except (OSError, ValueError):
            pass
        finally:
            try:
                logger.removeHandler(handler)
            except ValueError:
                pass

    # Also reset logger level to ensure it's not affected by previous tests
    original_level = logger.level
    logger.setLevel(logging.NOTSET)

    yield logger

    # Post-cleanup: close and remove all handlers added during the test
    for handler in list(logger.handlers):  # noqa: S7504
        try:
            handler.close()
        except (OSError, ValueError):
            pass
        finally:
            try:
                logger.removeHandler(handler)
            except ValueError:
                pass

    # Restore original logger level
    logger.setLevel(original_level)
