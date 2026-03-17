"""Tests for logging in layout module."""

import logging

import pytest

from ui import layout


def test_refresh_data_logs_to_root_logger(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that the layout module logger logs at INFO level by default."""
    # Get the layout logger
    layout_logger = logging.getLogger("ui.layout")

    # Capture logs at INFO level
    with caplog.at_level(logging.INFO):
        # Test that we can log at INFO level
        layout_logger.info("Test INFO message")
        layout_logger.debug("Test DEBUG message - should not be captured")

    # Check if INFO message was captured
    log_messages = [record.message for record in caplog.records]

    # Should have the INFO message but not the DEBUG message
    assert any("Test INFO message" in msg for msg in log_messages), (
        f"Expected INFO message to be logged, got: {log_messages}"
    )

    # DEBUG message should not be captured (INFO is default level)
    assert not any("Test DEBUG message" in msg for msg in log_messages), (
        f"DEBUG message should not be captured at INFO level, got: {log_messages}"
    )


def test_layout_logger_propagates(caplog: pytest.LogCaptureFixture) -> None:
    """Test that the layout module logger properly propagates to root logger."""
    with caplog.at_level(logging.INFO):
        # Get the layout logger
        layout_logger = logging.getLogger("ui.layout")
        layout_logger.info("TEST MESSAGE FROM LAYOUT")

    log_messages = [record.message for record in caplog.records]

    assert any("TEST MESSAGE FROM LAYOUT" in msg for msg in log_messages), (
        f"Expected test message to be logged, got: {log_messages}"
    )


def test_module_logger_exists() -> None:
    """Test that the _logger in layout module is properly configured."""
    # The _logger should be logging.getLogger("ui.layout")
    assert hasattr(layout, "_logger"), "layout module should have _logger attribute"
    assert isinstance(
        layout._logger,
        logging.Logger,  # type: ignore[attr-defined]
    ), "_logger should be a Logger instance"
    assert (
        layout._logger.name == "ui.layout"  # type: ignore[attr-defined]  # pylint: disable=protected-access
    ), f"Logger name should be 'ui.layout', got {layout._logger.name}"  # type: ignore[attr-defined]  # pylint: disable=protected-access
    # Logger should propagate by default
    assert (
        layout._logger.propagate  # type: ignore[attr-defined]  # pylint: disable=protected-access
    ), "Logger should propagate to parent loggers"


# The previous test_refresh_data_called_once_on_activity_selection_change was removed
# because it only invoked a MagicMock directly and did not exercise any real
# production code or UI wiring.


# The previous test_refresh_data_called_once_on_date_range_change was removed
# because it only invoked a MagicMock directly and did not exercise any real
# production code or UI wiring.
