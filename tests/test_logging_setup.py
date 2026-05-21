"""Tests for the setup_logging function in tracktales.py."""

import logging
import logging.handlers
import os
import runpy
import sys
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock, patch

import pytest

# Import the module to test
import tracktales as tracktales


class TestSetupLogging:
    """Tests for the setup_logging function."""

    @staticmethod
    def _non_pytest_handlers(logger: logging.Logger) -> list[logging.Handler]:
        """Return handlers excluding pytest log capture handlers."""
        return [
            handler
            for handler in logger.handlers
            if not handler.__class__.__module__.startswith("_pytest.")
        ]

    def test_setup_logging_with_debug_level(
        self, clean_logger: logging.Logger, tmp_path: Path
    ) -> None:
        """Test that setup_logging correctly configures DEBUG level."""
        logger = clean_logger

        # Change working directory temporarily to tmp_path
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            tracktales.setup_logging("DEBUG", enable_file_logging=True)

            # Verify logger is configured at DEBUG level
            assert logger.level == logging.DEBUG

            # Verify we have 2 handlers (console + file)
            assert len(self._non_pytest_handlers(logger)) == 2

            # Verify handlers are at DEBUG level
            for handler in self._non_pytest_handlers(logger):
                assert handler.level == logging.DEBUG

            # Verify one handler is StreamHandler (console) but not RotatingFileHandler
            console_handlers = [  # type: ignore[var-annotated]
                h
                for h in self._non_pytest_handlers(logger)
                if isinstance(h, logging.StreamHandler)
                and not isinstance(h, logging.handlers.RotatingFileHandler)
            ]
            assert len(console_handlers) == 1  # type: ignore[arg-type]
        finally:
            os.chdir(original_cwd)

    def test_setup_logging_with_info_level(
        self, clean_logger: logging.Logger, tmp_path: Path
    ) -> None:
        """Test that setup_logging correctly configures INFO level."""
        logger = clean_logger

        # Change working directory temporarily to tmp_path
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            tracktales.setup_logging("INFO", enable_file_logging=True)

            # Verify logger is configured at INFO level
            assert logger.level == logging.INFO

            # Verify handlers are at INFO level
            for handler in self._non_pytest_handlers(logger):
                assert handler.level == logging.INFO
        finally:
            os.chdir(original_cwd)

    def test_setup_logging_with_warning_level(
        self, clean_logger: logging.Logger, tmp_path: Path
    ) -> None:
        """Test that setup_logging correctly configures WARNING level."""
        logger = clean_logger

        # Change working directory temporarily to tmp_path
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            tracktales.setup_logging("WARNING", enable_file_logging=True)

            assert logger.level == logging.WARNING
            for handler in self._non_pytest_handlers(logger):
                assert handler.level == logging.WARNING
        finally:
            os.chdir(original_cwd)

    def test_setup_logging_with_error_level(
        self, clean_logger: logging.Logger, tmp_path: Path
    ) -> None:
        """Test that setup_logging correctly configures ERROR level."""
        logger = clean_logger

        # Change working directory temporarily to tmp_path
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            tracktales.setup_logging("ERROR", enable_file_logging=True)

            assert logger.level == logging.ERROR
            for handler in self._non_pytest_handlers(logger):
                assert handler.level == logging.ERROR
        finally:
            os.chdir(original_cwd)

    def test_setup_logging_disables_file_logging_in_dev_mode(
        self, clean_logger: logging.Logger
    ) -> None:
        """Test that file logging is disabled when enable_file_logging=False."""
        logger = clean_logger

        tracktales.setup_logging("INFO", enable_file_logging=False)

        # Verify we have only 1 handler (console only, no file handler)
        assert len(self._non_pytest_handlers(logger)) == 1

        # Verify the handler is a StreamHandler (console)
        assert isinstance(self._non_pytest_handlers(logger)[0], logging.StreamHandler)

        # Verify it's not a RotatingFileHandler
        assert not isinstance(
            self._non_pytest_handlers(logger)[0], logging.handlers.RotatingFileHandler
        )

    def test_setup_logging_clears_existing_handlers(
        self, clean_logger: logging.Logger, tmp_path: Path
    ) -> None:
        """Test that setup_logging clears existing handlers to prevent duplicates."""
        logger = clean_logger

        # Add some dummy handlers
        dummy_handler1 = logging.StreamHandler(sys.stdout)
        dummy_handler2 = logging.StreamHandler(sys.stdout)
        logger.addHandler(dummy_handler1)
        logger.addHandler(dummy_handler2)

        # Record the dummy handlers to verify they are removed
        dummy_handlers = {dummy_handler1, dummy_handler2}

        # Change working directory temporarily to tmp_path
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            tracktales.setup_logging("INFO", enable_file_logging=True)

            # After calling setup_logging, verify none of the dummy handlers remain
            handlers_after = set(logger.handlers)
            assert not dummy_handlers.intersection(handlers_after), (
                "Dummy handlers should have been removed by setup_logging"
            )

            # Verify we have exactly 2 new handlers (console + file)
            assert len(self._non_pytest_handlers(logger)) == 2, (
                f"Expected 2 handlers, got {len(self._non_pytest_handlers(logger))}"
            )
        finally:
            os.chdir(original_cwd)

    def test_setup_logging_creates_log_directory(
        self, clean_logger: logging.Logger, tmp_path: Path
    ) -> None:
        """Test that setup_logging creates the logs directory."""
        assert clean_logger is logging.getLogger()
        # Use a real path in tmp_path
        log_dir = tmp_path / "logs"
        assert not log_dir.exists(), "Log directory should not exist initially"

        # Change working directory temporarily to tmp_path
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            tracktales.setup_logging("INFO", enable_file_logging=True)

            # Verify log directory was created
            assert log_dir.exists(), "Log directory should be created"
        finally:
            os.chdir(original_cwd)

    def test_setup_logging_console_handler_uses_stdout(self, clean_logger: logging.Logger) -> None:
        """Test that the console handler writes to stdout."""
        logger = clean_logger

        tracktales.setup_logging("INFO", enable_file_logging=False)

        # Get the StreamHandler
        stream_handlers = [  # type: ignore[var-annotated]
            h for h in self._non_pytest_handlers(logger) if isinstance(h, logging.StreamHandler)
        ]
        assert len(stream_handlers) == 1  # type: ignore[arg-type]

        # Verify it uses stdout
        assert stream_handlers[0].stream == sys.stdout  # type: ignore[attr-defined]

    def test_setup_logging_recovers_when_std_streams_missing(
        self,
        clean_logger: logging.Logger,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """setup_logging should recreate stdout/stderr when missing."""
        assert clean_logger is logging.getLogger()
        monkeypatch.setattr(sys, "stdout", None)
        monkeypatch.setattr(sys, "stderr", None)

        tracktales.setup_logging("INFO", enable_file_logging=False)

        stream_handlers = [
            h
            for h in self._non_pytest_handlers(clean_logger)
            if isinstance(h, logging.StreamHandler)
        ]
        assert len(stream_handlers) == 1
        assert sys.stdout is not None
        assert sys.stderr is not None
        assert stream_handlers[0].stream == sys.stdout  # type: ignore[attr-defined]

    def test_setup_logging_handlers_have_formatters(
        self, clean_logger: logging.Logger, tmp_path: Path
    ) -> None:
        """Test that all handlers have formatters configured."""
        logger = clean_logger

        # Change working directory temporarily to tmp_path
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            tracktales.setup_logging("INFO", enable_file_logging=True)

            # Verify all handlers have formatters
            for handler in self._non_pytest_handlers(logger):
                assert handler.formatter is not None
                assert isinstance(handler.formatter, logging.Formatter)
        finally:
            os.chdir(original_cwd)

    def test_setup_logging_with_file_handler_configuration(
        self, clean_logger: logging.Logger, tmp_path: Path
    ) -> None:
        """Test that file handler is configured with correct settings."""
        # Create actual logs directory for this test
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            log_dir = tmp_path / "logs"
            log_dir.mkdir(exist_ok=True)

            tracktales.setup_logging("INFO", enable_file_logging=True)

            # Find the RotatingFileHandler in the handlers
            file_handlers = [
                h
                for h in self._non_pytest_handlers(clean_logger)
                if isinstance(h, logging.handlers.RotatingFileHandler)
            ]
            assert len(file_handlers) == 1, "Should have exactly one RotatingFileHandler"

            file_handler = file_handlers[0]
            # Verify the handler has the correct configuration
            assert file_handler.maxBytes == 10 * 1024 * 1024  # 10MB
            assert file_handler.backupCount == 3
        finally:
            os.chdir(original_cwd)

    def test_setup_logging_handles_file_handler_error(
        self,
        clean_logger: logging.Logger,
        caplog: pytest.LogCaptureFixture,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Test that setup_logging logs a warning when file handler fails."""
        assert clean_logger is logging.getLogger()
        monkeypatch.setenv("TRACKTALES_LOG_DIR", str(tmp_path / "logs"))

        with patch("pathlib.Path.mkdir", side_effect=OSError("no permission")):
            with caplog.at_level(logging.WARNING):
                tracktales.setup_logging("INFO", enable_file_logging=True)

        assert any("File logging disabled" in record.message for record in caplog.records), (
            "Expected a warning when file logging cannot be initialized"
        )


class TestCLIArgumentParsing:
    """Tests for CLI argument parsing logic."""

    @staticmethod
    def _extract_log_level_from_mock(mock_setup_logging: MagicMock) -> str:
        """Helper to extract log_level from setup_logging mock calls.

        Args:
            mock_setup_logging: The mock for setup_logging

        Returns:
            The log level string passed to setup_logging
        """
        # Ensure at least one call was made
        assert len(mock_setup_logging.call_args_list) > 0, "Expected setup_logging to be called"  # type: ignore[arg-type]
        # Get the most recent call
        call_args = mock_setup_logging.call_args  # type: ignore[attr-defined]
        # Extract log_level from either positional or keyword arguments
        log_level: str = call_args[0][0] if call_args[0] else call_args[1].get("log_level")  # type: ignore[index,union-attr]
        return log_level

    def test_log_level_argument_default(self) -> None:
        """Test that --log-level defaults to INFO in the real CLI."""
        with (
            patch("sys.argv", ["tracktales.py"]),
            patch.object(tracktales, "setup_logging") as mock_setup_logging,
            patch("nicegui.ui.run") as mock_ui_run,
        ):
            tracktales.cli_main()

        mock_setup_logging.assert_called()
        log_level = self._extract_log_level_from_mock(mock_setup_logging)
        assert log_level == "INFO"
        assert mock_ui_run.called

    def test_log_level_argument_accepts_debug(self) -> None:
        """Test that --log-level DEBUG is accepted by the real CLI."""
        with (
            patch(
                "sys.argv",
                ["tracktales.py", "--log-level", "DEBUG"],
            ),
            patch.object(tracktales, "setup_logging") as mock_setup_logging,
            patch("nicegui.ui.run") as mock_ui_run,
        ):
            tracktales.cli_main()

        mock_setup_logging.assert_called()
        log_level = self._extract_log_level_from_mock(mock_setup_logging)
        assert log_level == "DEBUG"
        assert mock_ui_run.called

    def test_log_level_argument_accepts_warning(self) -> None:
        """Test that --log-level WARNING is accepted by the real CLI."""
        with (
            patch(
                "sys.argv",
                ["tracktales.py", "--log-level", "WARNING"],
            ),
            patch.object(tracktales, "setup_logging") as mock_setup_logging,
            patch("nicegui.ui.run") as mock_ui_run,
        ):
            tracktales.cli_main()

        mock_setup_logging.assert_called()
        log_level = self._extract_log_level_from_mock(mock_setup_logging)
        assert log_level == "WARNING"
        assert mock_ui_run.called

    def test_log_level_argument_accepts_error(self) -> None:
        """Test that --log-level ERROR is accepted by the real CLI."""
        with (
            patch(
                "sys.argv",
                ["tracktales.py", "--log-level", "ERROR"],
            ),
            patch.object(tracktales, "setup_logging") as mock_setup_logging,
            patch("nicegui.ui.run") as mock_ui_run,
        ):
            tracktales.cli_main()

        mock_setup_logging.assert_called()
        log_level = self._extract_log_level_from_mock(mock_setup_logging)
        assert log_level == "ERROR"
        assert mock_ui_run.called

    def test_no_browser_argument_default(self) -> None:
        """Test that browser opens by default (show=True)."""
        with (
            patch("sys.argv", ["tracktales.py"]),
            patch.object(tracktales, "setup_logging"),
            patch("nicegui.ui.run") as mock_ui_run,
        ):
            tracktales.cli_main()

        # Verify ui.run was called with show=True (default)
        mock_ui_run.assert_called_once()
        call_kwargs = mock_ui_run.call_args[1]
        assert call_kwargs.get("show") is True  # type: ignore[union-attr]

    def test_no_browser_argument_prevents_browser_open(self) -> None:
        """Test that --no-browser prevents browser from opening (show=False)."""
        with (
            patch("sys.argv", ["tracktales.py", "--no-browser"]),
            patch.object(tracktales, "setup_logging"),
            patch("nicegui.ui.run") as mock_ui_run,
        ):
            tracktales.cli_main()

        # Verify ui.run was called with show=False
        mock_ui_run.assert_called_once()
        call_kwargs = mock_ui_run.call_args[1]
        assert call_kwargs.get("show") is False  # type: ignore[union-attr]

    def test_cli_main_enables_reload_dirs_when_not_frozen(self) -> None:
        """Source/dev runs should include uvicorn reload dirs."""
        with (
            patch("sys.argv", ["tracktales.py"]),
            patch.object(tracktales, "setup_logging"),
            patch("nicegui.ui.run") as mock_ui_run,
        ):
            tracktales.cli_main()

        call_kwargs = mock_ui_run.call_args[1]
        assert call_kwargs.get("uvicorn_reload_dirs") == "src,resources"  # type: ignore[union-attr]

    def test_cli_main_disables_reload_dirs_when_frozen(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Frozen/binary runs must not enable uvicorn reload dirs."""
        monkeypatch.setattr(sys, "argv", ["tracktales.py"])
        monkeypatch.setattr(sys, "frozen", True, raising=False)

        with (
            patch.object(tracktales, "setup_logging"),
            patch("nicegui.ui.run") as mock_ui_run,
        ):
            tracktales.cli_main()

        call_kwargs = mock_ui_run.call_args[1]
        assert "uvicorn_reload_dirs" not in call_kwargs

    def test_cli_main_recovers_when_std_streams_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """cli_main should recreate stdout/stderr when running without a console."""

        def _fake_run(*_args: object, **_kwargs: object) -> None:
            assert sys.stdout is not None
            assert sys.stderr is not None
            assert hasattr(sys.stdout, "isatty")
            assert hasattr(sys.stderr, "isatty")

        monkeypatch.setattr(sys, "argv", ["tracktales.py", "--no-browser"])
        monkeypatch.setattr(sys, "stdout", None)
        monkeypatch.setattr(sys, "stderr", None)

        with (
            patch.object(tracktales, "setup_logging") as mock_setup_logging,
            patch("nicegui.ui.run", side_effect=_fake_run) as mock_ui_run,
        ):
            tracktales.cli_main()

        mock_setup_logging.assert_called_once()
        mock_ui_run.assert_called_once()

    def test_cli_main_invalid_dev_file_path_exits(self) -> None:
        """Test that invalid dev file paths cause an early exit with an error."""
        with (
            patch("sys.argv", ["tracktales.py", "--dev-file", "~/bad/path.zip"]),
            patch("pathlib.Path.resolve", side_effect=OSError("bad path")),
            patch.object(tracktales, "setup_logging") as mock_setup_logging,
            patch("nicegui.ui.run") as mock_ui_run,
        ):
            with pytest.raises(SystemExit) as exc_info:
                tracktales.cli_main()

        assert exc_info.value.code == 1
        mock_setup_logging.assert_called_once()
        mock_ui_run.assert_not_called()

    def test_cli_main_stores_dev_file_and_disables_file_logging(
        self, clean_logger: logging.Logger, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that a valid dev file sets storage and disables file logging."""
        dev_file = tmp_path / "export.zip"
        dev_file.write_text("data", encoding="utf-8")

        monkeypatch.setattr(sys, "argv", ["tracktales.py", "--dev-file", str(dev_file)])

        with (
            patch.object(tracktales, "setup_logging") as mock_setup_logging,
            patch("nicegui.ui.run") as mock_ui_run,
        ):
            try:
                tracktales.cli_main()
                storage_general = cast(dict[str, str], tracktales.app.storage.general)
                assert storage_general.get("_dev_file_path") == str(dev_file)
                mock_setup_logging.assert_called_once()
                assert mock_setup_logging.call_args[1]["enable_file_logging"] is False
                mock_ui_run.assert_called_once()
            finally:
                tracktales.app.storage.general.pop("_dev_file_path", None)

    def test_cli_main_sets_dev_file_path_to_none_without_dev_file(
        self, clean_logger: logging.Logger, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that cli_main explicitly stores None when no dev file is provided."""
        assert clean_logger is logging.getLogger()
        monkeypatch.setattr(sys, "argv", ["tracktales.py"])

        with (
            patch.object(tracktales, "setup_logging") as mock_setup_logging,
            patch("nicegui.ui.run") as mock_ui_run,
        ):
            try:
                tracktales.cli_main()
                storage_general = cast(dict[str, str | None], tracktales.app.storage.general)
                assert "_dev_file_path" in storage_general
                assert storage_general["_dev_file_path"] is None
                mock_setup_logging.assert_called_once()
                assert mock_setup_logging.call_args[1]["enable_file_logging"] is True
                mock_ui_run.assert_called_once()
            finally:
                tracktales.app.storage.general.pop("_dev_file_path", None)

    def test_cli_main_dev_file_not_found_exits(
        self, clean_logger: logging.Logger, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that a non-existent dev file causes an early exit with an error."""
        dev_file = tmp_path / "nonexistent.zip"
        # File does not exist

        monkeypatch.setattr(sys, "argv", ["tracktales.py", "--dev-file", str(dev_file)])

        with (
            patch.object(tracktales, "setup_logging") as mock_setup_logging,
            patch("nicegui.ui.run") as mock_ui_run,
        ):
            with pytest.raises(SystemExit) as exc_info:
                tracktales.cli_main()

        assert exc_info.value.code == 1
        mock_setup_logging.assert_called_once()
        mock_ui_run.assert_not_called()

    def test_module_entrypoint_invokes_cli_main(
        self,
        clean_logger: logging.Logger,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Test that running the module as __main__ triggers cli_main."""
        assert clean_logger is logging.getLogger()
        called = {"run": False}

        def _fake_run(*_args: object, **_kwargs: object) -> None:
            called["run"] = True

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("TRACKTALES_LOG_DIR", str(tmp_path / "logs"))
        monkeypatch.setattr(sys, "argv", ["tracktales.py"])
        monkeypatch.setattr("nicegui.ui.run", _fake_run)

        runpy.run_module("tracktales", run_name="__main__")

        assert called["run"], "cli_main should start the NiceGUI server"
