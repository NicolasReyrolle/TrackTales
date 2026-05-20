#!/usr/bin/env python3
"""
TrackTales GUI

A graphical user interface for analyzing Apple Health data.
"""

import argparse
import logging
import os
import sys
import uuid
from pathlib import Path
from typing import cast

from nicegui import app, ui

from app_state import state
from assets import APP_ICON_BASE64
from i18n import compile_message_catalogs
from logging_config import setup_logging
from ui.layout import load_file, render_body, render_header, render_left_drawer

# Module-level logger; avoid configuring global logging at import time.
# A NullHandler prevents "No handler found" warnings if the application
# importing this module has not configured logging yet.
_logger = logging.getLogger(__name__)
if not _logger.handlers:
    _logger.addHandler(logging.NullHandler())


@app.on_startup  # type: ignore[arg-type]
def _compile_catalogs() -> None:  # pyright: ignore[reportUnusedFunction]
    """Compile translation catalogs at startup.

    Registered as an app-startup callback so that catalogs are compiled
    regardless of whether the app is launched via the CLI entry point
    (``cli_main``) or directly via ``python -m nicegui src.tracktales``.
    """
    compiled_catalogs = compile_message_catalogs()
    if compiled_catalogs:
        _logger.info("Compiled %d translation catalog(s)", compiled_catalogs)
    else:
        _logger.debug("Translation catalogs are up to date")


def main() -> None:
    """Main NiceGUI page setup function.

    This function is called by NiceGUI for each page render.
    It should not contain CLI argument parsing or app initialization logic.
    """

    render_header()
    render_left_drawer()
    render_body()

    app.add_static_files("/resources", "resources")
    # Inject style.css inline rather than via an external link so that browsers
    # always receive the latest styles.  External links are cached by
    # NiceGUI/Starlette with a 1-hour max-age, meaning users would keep seeing
    # stale CSS after a server update until the cache expires.
    ui.add_css(Path(__file__).parent.parent / "resources" / "style.css", shared=True)

    # Check if dev file was passed through app storage
    # Note: This auto-load mechanism intentionally triggers on every page render
    # (e.g., browser refresh or new tab). This is useful for development as it
    # allows quickly testing changes by simply refreshing the browser.
    dev_file = cast(
        str | None,
        app.storage.general.get("_dev_file_path"),  # type: ignore[no-untyped-call]
    )
    if dev_file:
        _logger.info("Dev file will be auto-loaded: %s", dev_file)
        state.input_file.value = dev_file

        async def _auto_load() -> None:
            """Auto-load the dev file after UI is ready."""
            _logger.info("Auto-loading file: %s", dev_file)
            await load_file()

        # Use ui.timer with the async callback
        _logger.debug("Scheduling file load via ui.timer after 1 second")
        ui.timer(1.0, _auto_load, once=True)


def cli_main() -> None:
    """CLI entry point that handles argument parsing and starts the application.

    This function should be called from the command line or the entry point.
    It parses CLI arguments, sets up logging, and starts the NiceGUI server.
    """
    # Parse command-line arguments for developer mode
    parser = argparse.ArgumentParser(
        description="TrackTales - Analyze your Apple Health data",
        prog="tracktales",
    )
    parser.add_argument(
        "--dev-file",
        type=str,
        help="(Developer mode) Path to an Apple Health export ZIP file"
        " to load automatically on startup",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set the logging level",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Prevent browser from automatically opening on startup",
    )
    args, _ = parser.parse_known_args()

    # Validate dev file if provided (before setting up logging)
    resolved_path: Path | None = None
    dev_file_error: str | None = None

    if args.dev_file is not None:
        try:
            resolved_path = Path(args.dev_file).expanduser().resolve()
        except OSError as exc:
            dev_file_error = f"Invalid dev file path '{args.dev_file}': {exc}"

        if not dev_file_error and resolved_path is not None and not resolved_path.is_file():
            dev_file_error = f"File not found: {resolved_path}"

    # Set up logging (after dev file validation)
    # File logging is disabled in dev mode (when dev file is specified) to avoid
    # Uvicorn reload issues, but enabled in production mode for debugging
    enable_file_logging = resolved_path is None
    setup_logging(args.log_level, enable_file_logging=enable_file_logging)

    # Exit early if dev file validation failed
    if dev_file_error:
        _logger.error(dev_file_error)
        sys.exit(1)

    # Log dev mode information if applicable
    if resolved_path is not None:
        _logger.info("Dev mode enabled with auto-load")
        _logger.info(
            "File logging is disabled in dev mode; debug logs are available in console output"
        )
        _logger.info("Dev file specified: %s", resolved_path)

    _logger.info("Starting TrackTales with log level: %s", args.log_level)

    secret = uuid.uuid4().hex if "pytest" in sys.modules else os.getenv("STORAGE_SECRET", "secret")

    # Pass dev file path through app storage so it's accessible in main()
    if resolved_path is not None:
        app.storage.general["_dev_file_path"] = str(resolved_path)
        _logger.debug("Stored dev file path in app storage: %s", resolved_path)
    else:
        app.storage.general["_dev_file_path"] = None

    _logger.debug("Initializing NiceGUI app")
    ui.run(  # type: ignore[misc]
        main,
        title="TrackTales",
        favicon=APP_ICON_BASE64,
        storage_secret=secret,
        uvicorn_reload_dirs="src,resources",  # Only include needed dirs for the reload
        show=not args.no_browser,
    )


if __name__ in {"__main__", "__mp_main__"}:
    cli_main()

