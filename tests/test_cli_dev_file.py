"""Tests for command-line dev file parameter.

These tests invoke the actual application script (src/tracktales.py) as a subprocess
to validate the CLI argument parsing and application startup behavior. This approach tests the
real application code path that users would experience when running the application, rather than
testing argument parsing in isolation with mock implementations.

The tests verify:
1. Help output includes all expected CLI options
2. Invalid file paths cause immediate failure with non-zero exit codes
3. Valid file paths allow the application to start successfully
"""

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest


def _terminate_process_tree(process: subprocess.Popen[str], timeout: float = 5.0) -> None:
    """Terminate a subprocess and its children, with Windows-specific tree cleanup."""
    if process.poll() is not None:
        return

    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            text=True,
            check=False,
        )
    else:
        process.terminate()
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()

    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        pass


def test_dev_file_help() -> None:
    """Test that --help shows the --dev-file option on the real CLI.

    This test invokes the actual application module (src/tracktales.py)
    as a subprocess, ensuring we test the real CLI argument parser, not a mock.
    This guarantees that --dev-file will be detected here if and only if it exists
    in the actual argparse setup in cli_main().
    """
    result = subprocess.run(
        [
            sys.executable,
            "src/tracktales.py",
            "--help",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    # Help should succeed and mention the --dev-file option
    assert result.returncode == 0, "Help command should succeed on real CLI"
    combined_output = (result.stdout or "") + (result.stderr or "")
    assert "--dev-file" in combined_output, "Help output should mention --dev-file option"


def test_dev_file_invalid_path() -> None:
    """Test that an invalid --dev-file path causes a non-zero exit on startup.

    This test validates the actual application's file validation logic at
    src/tracktales.py (cli_main function) by running the real
    application and verifying both exit code and error message.
    """
    invalid_path = "/nonexistent/file.zip"

    result = subprocess.run(
        [
            sys.executable,
            "src/tracktales.py",
            "--dev-file",
            invalid_path,
            "--no-browser",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    # The application should fail fast when given a clearly invalid dev file path
    assert result.returncode != 0, "Invalid --dev-file path should cause non-zero exit"
    # Verify the actual validation logic detected the missing file
    combined_output = (result.stdout or "") + (result.stderr or "")
    assert "File not found" in combined_output or "not found" in combined_output.lower(), (
        "Error message should indicate file was not found"
    )


def test_dev_file_valid_path() -> None:
    """Test that a valid --dev-file path does not cause immediate startup failure."""
    fixture_path = Path("tests/fixtures/export_sample.zip")

    if not fixture_path.exists():
        pytest.skip(f"Test fixture not found: {fixture_path}")

    # Clean the environment to prevent NiceGUI from detecting a test context
    env = os.environ.copy()
    env.pop("PYTEST_CURRENT_TEST", None)
    env.pop("NICEGUI_SCREEN_TEST_PORT", None)
    env["BROWSER"] = "none"

    # Start the real application with a valid dev file. We don't wait indefinitely;
    # instead, allow a short startup window, then terminate if still running.
    # Use --no-browser to prevent opening a browser window in CI/headless environments.
    process = subprocess.Popen(
        [
            sys.executable,
            "src/tracktales.py",
            "--dev-file",
            str(fixture_path),
            "--no-browser",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )

    try:
        # Poll for early process exit within a bounded startup window instead of
        # relying on a fixed sleep, which can be flaky on slower CI machines.
        startup_timeout = 30.0
        poll_interval = 0.5
        start_time = time.monotonic()
        exit_code = None
        while True:
            exit_code = process.poll()
            if exit_code is not None:
                # Process has already exited, which indicates a startup failure
                _, stderr = process.communicate()
                assert exit_code == 0, f"Startup failed with error: {stderr}"
                break

            if time.monotonic() - start_time >= startup_timeout:
                # The process is still running after the startup timeout window;
                # treat this as a successful startup (no fast failure detected).
                break

            time.sleep(poll_interval)

        _terminate_process_tree(process)

    finally:
        _terminate_process_tree(process)


def test_dev_file_directory_instead_of_file() -> None:
    """Test that providing a directory path instead of a file causes validation failure.

    This test verifies the is_file() validation logic in the actual application
    by providing a directory path and confirming proper error handling.
    """
    # Use the tests directory as a known directory
    directory_path = "tests"

    result = subprocess.run(
        [
            sys.executable,
            "src/tracktales.py",
            "--dev-file",
            directory_path,
            "--no-browser",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    # Should fail because a directory is not a file
    assert result.returncode != 0, "Directory path should cause non-zero exit"
    combined_output = (result.stdout or "") + (result.stderr or "")
    assert "File not found" in combined_output or "not found" in combined_output.lower(), (
        "Error message should indicate file was not found"
    )


def test_dev_file_combined_with_log_level() -> None:
    """Test that --dev-file works correctly when combined with --log-level.

    This validates that multiple CLI arguments are properly handled together
    and that the actual validation logic runs correctly with combined arguments.
    """
    fixture_path = Path("tests/fixtures/export_sample.zip")

    if not fixture_path.exists():
        pytest.skip(f"Test fixture not found: {fixture_path}")

    # Clean the environment to prevent NiceGUI from detecting a test context
    env = os.environ.copy()
    env.pop("PYTEST_CURRENT_TEST", None)
    env.pop("NICEGUI_SCREEN_TEST_PORT", None)
    env["BROWSER"] = "none"

    process = subprocess.Popen(
        [
            sys.executable,
            "src/tracktales.py",
            "--dev-file",
            str(fixture_path),
            "--log-level",
            "DEBUG",
            "--no-browser",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )

    try:
        # Poll for early process exit within a bounded startup window instead of
        # relying on a fixed sleep, which can be flaky on slower CI machines.
        startup_timeout = 30.0
        poll_interval = 0.5
        start_time = time.monotonic()
        exit_code = None
        while True:
            exit_code = process.poll()
            if exit_code is not None:
                # Process has already exited, which indicates a startup failure
                _, stderr = process.communicate()
                assert exit_code == 0, f"Startup failed with error: {stderr}"
                break

            if time.monotonic() - start_time >= startup_timeout:
                # The process is still running after the startup timeout window;
                # treat this as a successful startup (no fast failure detected).
                break

            time.sleep(poll_interval)

        _terminate_process_tree(process)

    finally:
        _terminate_process_tree(process)
