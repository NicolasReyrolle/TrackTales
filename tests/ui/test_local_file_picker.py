"""Tests for the local_file_picker class."""

import sys
from pathlib import Path
from types import TracebackType
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest

from ui.local_file_picker import LocalFilePicker as local_file_picker


class TestUpdateGrid:
    """Test the update_grid method."""

    def test_update_grid_creates_row_data(self, tmp_path: Path) -> None:
        """Test that update_grid creates row data correctly."""
        # Create test structure
        (tmp_path / "dir1").mkdir()
        (tmp_path / "file1.txt").touch()

        # Create a mock picker without full initialization
        picker = MagicMock(spec=local_file_picker)
        picker.path = tmp_path
        picker.upper_limit = None
        picker.show_hidden_files = False
        picker.file_filter = None
        picker.grid = MagicMock()
        picker.grid.options = {"rowData": []}

        # Call the actual method
        local_file_picker.update_grid(picker)

        # Verify grid was updated and has content
        assert picker.grid.update.called
        options: dict[str, list[Any]] = picker.grid.options  # type: ignore[assignment]
        assert len(options["rowData"]) > 0

    def test_update_grid_hides_hidden_files_by_default(self, tmp_path: Path) -> None:
        """Test that hidden files are excluded by default."""
        # Create hidden file
        (tmp_path / ".hidden").touch()
        (tmp_path / "visible.txt").touch()

        # Create a mock picker
        picker = MagicMock(spec=local_file_picker)
        picker.path = tmp_path
        picker.upper_limit = None
        picker.show_hidden_files = False
        picker.file_filter = None
        picker.grid = MagicMock()
        picker.grid.options = {"rowData": []}

        # Call the actual method
        local_file_picker.update_grid(picker)

        options: dict[str, list[Any]] = picker.grid.options  # type: ignore[assignment]
        row_data: list[dict[str, Any]] = options["rowData"]  # type: ignore[assignment]
        file_names: list[str] = [r["name"] for r in row_data]

        # Hidden file should not be in the list
        assert not any(".hidden" in name for name in file_names)

    def test_update_grid_shows_hidden_files_when_enabled(self, tmp_path: Path) -> None:
        """Test that hidden files are shown when enabled."""
        # Create hidden file
        (tmp_path / ".hidden").touch()
        (tmp_path / "visible.txt").touch()

        # Create a mock picker
        picker = MagicMock(spec=local_file_picker)
        picker.path = tmp_path
        picker.upper_limit = None
        picker.show_hidden_files = True
        picker.file_filter = None
        picker.grid = MagicMock()
        picker.grid.options = {"rowData": []}

        # Call the actual method
        local_file_picker.update_grid(picker)

        options: dict[str, list[Any]] = picker.grid.options  # type: ignore[assignment]
        row_data: list[dict[str, Any]] = options["rowData"]  # type: ignore[assignment]
        file_names: list[str] = [r["name"] for r in row_data]

        # Hidden file should be in the list
        assert any(".hidden" in name for name in file_names)

    def test_update_grid_sorts_directories_first(self, tmp_path: Path) -> None:
        """Test that directories appear before files in sorted order."""
        # Create structure
        (tmp_path / "z_dir").mkdir()
        (tmp_path / "a_dir").mkdir()
        (tmp_path / "z_file.txt").touch()
        (tmp_path / "a_file.txt").touch()

        # Create a mock picker
        picker = MagicMock(spec=local_file_picker)
        picker.path = tmp_path
        picker.upper_limit = None
        picker.show_hidden_files = False
        picker.file_filter = None
        picker.grid = MagicMock()
        picker.grid.options = {"rowData": []}

        # Call the actual method
        local_file_picker.update_grid(picker)

        options: dict[str, list[Any]] = picker.grid.options  # type: ignore[assignment]
        row_data: list[dict[str, Any]] = options["rowData"]  # type: ignore[assignment]
        names: list[str] = [r["name"] for r in row_data]

        # Directories should come before files
        dir_indices = [i for i, n in enumerate(names) if "📁" in n]
        file_indices = [i for i, n in enumerate(names) if "📁" not in n]

        if dir_indices and file_indices:
            assert max(dir_indices) < min(file_indices)

    def test_update_grid_adds_parent_directory_link(self, tmp_path: Path) -> None:
        """Test that parent directory (..) is added when not at upper_limit."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        # Create a mock picker
        picker = MagicMock(spec=local_file_picker)
        picker.path = subdir
        picker.upper_limit = None
        picker.show_hidden_files = False
        picker.file_filter = None
        picker.grid = MagicMock()
        picker.grid.options = {"rowData": []}

        # Call the actual method
        local_file_picker.update_grid(picker)

        options: dict[str, list[Any]] = picker.grid.options  # type: ignore[assignment]
        row_data: list[dict[str, Any]] = options["rowData"]  # type: ignore[assignment]
        names: list[str] = [r["name"] for r in row_data]

        # Parent directory should be first
        assert any(".." in name for name in names)

    def test_update_grid_no_parent_at_upper_limit(self, tmp_path: Path) -> None:
        """Test that parent directory is not shown at upper_limit."""
        # Create a mock picker
        picker = MagicMock(spec=local_file_picker)
        picker.path = tmp_path
        picker.upper_limit = tmp_path
        picker.show_hidden_files = False
        picker.file_filter = None
        picker.grid = MagicMock()
        picker.grid.options = {"rowData": []}

        # Call the actual method
        local_file_picker.update_grid(picker)

        options: dict[str, list[Any]] = picker.grid.options  # type: ignore[assignment]
        row_data: list[dict[str, Any]] = options["rowData"]  # type: ignore[assignment]
        names: list[str] = [r["name"] for r in row_data]

        # Parent directory should not be shown
        assert not any(".." in name for name in names)


class TestHandleDoubleClick:
    """Test the handle_double_click method."""

    def test_handle_double_click_on_directory(self, tmp_path: Path) -> None:
        """Test double-clicking a directory navigates into it."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        # Create a mock picker
        picker = MagicMock(spec=local_file_picker)
        picker.path = tmp_path
        picker.grid = MagicMock()
        picker.update_grid = MagicMock()

        # Create event
        event = MagicMock()
        event.args = {"data": {"path": str(subdir)}}

        # Call the actual method
        local_file_picker.handle_double_click(picker, event)

        assert picker.path == subdir
        picker.update_grid.assert_called_once()

    def test_handle_double_click_on_file_submits(self, tmp_path: Path) -> None:
        """Test double-clicking a file submits and closes the dialog."""
        file_path = tmp_path / "test_file.txt"
        file_path.touch()

        # Create a mock picker
        picker = MagicMock(spec=local_file_picker)
        picker.path = tmp_path
        picker.grid = MagicMock()
        picker.submit = MagicMock()

        # Create event
        event = MagicMock()
        event.args = {"data": {"path": str(file_path)}}

        # Call the actual method
        local_file_picker.handle_double_click(picker, event)

        picker.submit.assert_called_once_with([str(file_path)])


class TestHandleOk:
    """Test the _handle_ok method."""

    @pytest.mark.asyncio
    async def test_handle_ok_single_file_selection(self, tmp_path: Path) -> None:
        """Test OK button with single file selection."""
        file_path = tmp_path / "test_file.txt"
        file_path.touch()

        # Create a mock picker
        picker = MagicMock(spec=local_file_picker)
        picker.grid = MagicMock()

        # Mock get_selected_rows to return a coroutine
        async def async_get_selected_rows():
            return [{"path": str(file_path)}]

        picker.grid.get_selected_rows = async_get_selected_rows
        picker.submit = MagicMock()

        # Call the actual method
        await local_file_picker._handle_ok(picker)  # type: ignore[misc]  # pylint: disable=protected-access

        picker.submit.assert_called_once_with([str(file_path)])

    @pytest.mark.asyncio
    async def test_handle_ok_multiple_file_selection(self, tmp_path: Path) -> None:
        """Test OK button with multiple file selection."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.touch()
        file2.touch()

        # Create a mock picker
        picker = MagicMock(spec=local_file_picker)
        picker.grid = MagicMock()

        # Mock get_selected_rows to return a coroutine
        async def async_get_selected_rows():
            return [{"path": str(file1)}, {"path": str(file2)}]

        picker.grid.get_selected_rows = async_get_selected_rows
        picker.submit = MagicMock()

        # Call the actual method
        await local_file_picker._handle_ok(picker)  # type: ignore[misc]  # pylint: disable=protected-access

        picker.submit.assert_called_once_with([str(file1), str(file2)])


class TestPathHandling:
    """Test path handling and validation."""

    def test_path_expansion_with_tilde(self) -> None:
        """Test that paths with ~ are expanded to home directory."""
        test_path = "~"
        expanded = Path(test_path).expanduser()

        assert expanded == Path.home()
        assert "~" not in str(expanded)

    def test_path_expansion_with_relative(self) -> None:
        """Test that relative paths are handled correctly."""
        test_path = "."
        expanded = Path(test_path).expanduser().resolve()

        assert expanded.is_absolute()

    def test_path_expansion_nested_home(self) -> None:
        """Test that nested paths under home are expanded correctly."""
        test_path = "~/test/path"
        expanded = Path(test_path).expanduser()

        assert expanded == Path.home() / "test" / "path"
        assert "~" not in str(expanded)


class TestUpdateDrive:
    """Test the update_drive method."""

    def test_update_drive_changes_path(self) -> None:
        """Test that update_drive changes the current path."""
        # Create a mock picker
        picker = MagicMock(spec=local_file_picker)
        picker.drives_toggle = MagicMock()
        picker.drives_toggle.value = "C:\\"
        picker.update_grid = MagicMock()

        # Call the actual method
        local_file_picker.update_drive(picker)

        assert picker.path == Path("C:\\")
        picker.update_grid.assert_called_once()

    def test_update_drive_without_drives_toggle(self) -> None:
        """Test that update_drive handles missing drives_toggle gracefully."""
        # Create a mock picker without drives_toggle
        picker = MagicMock(spec=local_file_picker)
        del picker.drives_toggle

        # Should not raise an exception
        local_file_picker.update_drive(picker)

        # update_grid should not be called since drives_toggle is missing
        assert not picker.update_grid.called


class TestAddDrivesToggle:
    """Test the add_drives_toggle method."""

    def test_add_drives_toggle_attributes(self) -> None:
        """Test that add_drives_toggle is callable on the class."""
        # Verify the method exists
        assert hasattr(local_file_picker, "add_drives_toggle")
        assert callable(getattr(local_file_picker, "add_drives_toggle"))

    def test_add_drives_toggle_mocked(self) -> None:
        """Test that add_drives_toggle adds the drives_toggle attribute
        by mocking Windows and the module."""
        # Create a mock for the picker instance (acts as 'self')
        picker = MagicMock()

        # 1. Setup the win32api mock
        mock_win32 = MagicMock()
        mock_win32.GetLogicalDriveStrings.return_value = "C:\\\000"

        # 2. Use patch.dict to inject the mock into sys.modules
        # This prevents the 'ImportError' inside the method
        with (
            patch.dict(sys.modules, {"win32api": mock_win32}),
            patch("ui.local_file_picker.platform.system", return_value="Windows"),
            patch("ui.local_file_picker.ui.toggle") as mock_toggle,
        ):
            # 3. Call the method
            # We call it as a static method passing our mock picker
            local_file_picker.add_drives_toggle(picker)

            # Now ui.toggle should be called because:
            # - platform.system() == "Windows"
            # - import win32api succeeded (returned our mock)
            assert mock_toggle.called

            # Verify it created the attribute on our mock picker
            assert hasattr(picker, "drives_toggle")

    def test_add_drives_toggle_handles_import_error_on_windows(self) -> None:
        """Windows systems without win32api should skip drive toggle creation."""

        class _Picker:
            pass

        picker = _Picker()
        real_import = __import__

        def _import_side_effect(name: str, *args: Any, **kwargs: Any) -> Any:
            if name == "win32api":
                raise ImportError("win32api not installed")
            return real_import(name, *args, **kwargs)

        with (
            patch("ui.local_file_picker.platform.system", return_value="Windows"),
            patch("builtins.__import__", side_effect=_import_side_effect),
        ):
            local_file_picker.add_drives_toggle(cast(Any, picker))

        assert not hasattr(picker, "drives_toggle")


class TestLocalFilePickerInit:
    """Tests for constructor path handling branches."""

    def test_init_expands_upper_limit_when_provided(self) -> None:
        """Constructor should expand upper_limit path when a value is provided."""

        class _DummyChain:
            """Dummy class to allow method chaining in patched UI components."""

            def __enter__(self):
                return self

            def __exit__(
                self,
                exc_type: type[BaseException] | None,
                exc: BaseException | None,
                tb: TracebackType | None,
            ) -> bool:
                return False

            def classes(self, *_args: Any, **_kwargs: Any):
                """Dummy method to allow chaining."""
                return self

            def on(self, *_args: Any, **_kwargs: Any):
                """Dummy method to allow chaining."""
                return self

            def props(self, *_args: Any, **_kwargs: Any):
                """Dummy method to allow chaining."""
                return self

        def _dialog_enter(self: Any) -> Any:
            return self

        def _dialog_exit(
            self: Any,
            exc_type: type[BaseException] | None,
            exc: BaseException | None,
            tb: TracebackType | None,
        ) -> bool:
            del self, exc_type, exc, tb
            return False

        with (
            patch("ui.local_file_picker.ui.dialog.__init__", return_value=None),
            patch.object(local_file_picker, "__enter__", _dialog_enter, create=True),
            patch.object(local_file_picker, "__exit__", _dialog_exit, create=True),
            patch("ui.local_file_picker.ui.card", return_value=_DummyChain()),
            patch("ui.local_file_picker.ui.aggrid", return_value=_DummyChain()),
            patch("ui.local_file_picker.ui.row", return_value=_DummyChain()),
            patch("ui.local_file_picker.ui.button", return_value=_DummyChain()),
            patch.object(local_file_picker, "add_drives_toggle"),
            patch.object(local_file_picker, "update_grid"),
        ):
            picker = local_file_picker("~", upper_limit="~/upper")

        assert picker.upper_limit == Path("~/upper").expanduser()


class TestFileFilter:
    """Test the file_filter feature for filtering files by extension."""

    def test_update_grid_with_file_filter(self, tmp_path: Path) -> None:
        """Test that file_filter correctly filters files by extension."""
        # Create test structure
        (tmp_path / "file1.xml").touch()
        (tmp_path / "file2.xml").touch()
        (tmp_path / "file3.txt").touch()
        (tmp_path / "file4.csv").touch()
        (tmp_path / "subdir").mkdir()

        # Create a mock picker with file_filter
        picker = MagicMock(spec=local_file_picker)
        picker.path = tmp_path
        picker.upper_limit = None
        picker.show_hidden_files = False
        picker.file_filter = ".xml"
        picker.grid = MagicMock()
        picker.grid.options = {"rowData": []}

        # Call the actual method
        local_file_picker.update_grid(picker)

        options: dict[str, list[Any]] = picker.grid.options  # type: ignore[assignment]
        row_data: list[dict[str, Any]] = options["rowData"]  # type: ignore[assignment]
        file_names: list[str] = [r["name"] for r in row_data]

        # Should only show .xml files and directories
        assert any("file1.xml" in name for name in file_names)
        assert any("file2.xml" in name for name in file_names)
        assert not any("file3.txt" in name for name in file_names)
        assert not any("file4.csv" in name for name in file_names)
        # Directories should always be shown
        assert any("subdir" in name for name in file_names)

    def test_update_grid_with_file_filter_case_insensitive(self, tmp_path: Path) -> None:
        """Test that file_filter is case-insensitive."""
        # Create test structure with mixed case
        (tmp_path / "file1.XML").touch()
        (tmp_path / "file2.Xml").touch()
        (tmp_path / "file3.txt").touch()

        # Create a mock picker with lowercase filter
        picker = MagicMock(spec=local_file_picker)
        picker.path = tmp_path
        picker.upper_limit = None
        picker.show_hidden_files = False
        picker.file_filter = ".xml"
        picker.grid = MagicMock()
        picker.grid.options = {"rowData": []}

        # Call the actual method
        local_file_picker.update_grid(picker)

        options: dict[str, list[Any]] = picker.grid.options  # type: ignore[assignment]
        row_data: list[dict[str, Any]] = options["rowData"]  # type: ignore[assignment]
        file_names: list[str] = [r["name"] for r in row_data]

        # Should match both uppercase and mixed case extensions
        assert any("file1.XML" in name for name in file_names)
        assert any("file2.Xml" in name for name in file_names)
        assert not any("file3.txt" in name for name in file_names)

    def test_update_grid_without_file_filter(self, tmp_path: Path) -> None:
        """Test that without file_filter, all files are shown."""
        # Create test structure
        (tmp_path / "file1.xml").touch()
        (tmp_path / "file2.txt").touch()
        (tmp_path / "file3.csv").touch()

        # Create a mock picker without file_filter
        picker = MagicMock(spec=local_file_picker)
        picker.path = tmp_path
        picker.upper_limit = None
        picker.show_hidden_files = False
        picker.file_filter = None
        picker.grid = MagicMock()
        picker.grid.options = {"rowData": []}

        # Call the actual method
        local_file_picker.update_grid(picker)

        options: dict[str, list[Any]] = picker.grid.options  # type: ignore[assignment]
        row_data: list[dict[str, Any]] = options["rowData"]  # type: ignore[assignment]
        file_names: list[str] = [r["name"] for r in row_data]

        # All files should be shown
        assert any("file1.xml" in name for name in file_names)
        assert any("file2.txt" in name for name in file_names)
        assert any("file3.csv" in name for name in file_names)

    def test_file_filter_always_shows_directories(self, tmp_path: Path) -> None:
        """Test that file_filter doesn't filter out directories."""
        # Create test structure
        (tmp_path / "docs").mkdir()
        (tmp_path / "data").mkdir()
        (tmp_path / "file1.xml").touch()
        (tmp_path / "file2.txt").touch()

        # Create a mock picker with file_filter
        picker = MagicMock(spec=local_file_picker)
        picker.path = tmp_path
        picker.upper_limit = None
        picker.show_hidden_files = False
        picker.file_filter = ".xml"
        picker.grid = MagicMock()
        picker.grid.options = {"rowData": []}

        # Call the actual method
        local_file_picker.update_grid(picker)

        options: dict[str, list[Any]] = picker.grid.options  # type: ignore[assignment]
        row_data: list[dict[str, Any]] = options["rowData"]  # type: ignore[assignment]
        file_names: list[str] = [r["name"] for r in row_data]

        # Both directories should be shown regardless of filter
        assert any("docs" in name for name in file_names)
        assert any("data" in name for name in file_names)
        # Only matching files should be shown
        assert any("file1.xml" in name for name in file_names)
        assert not any("file2.txt" in name for name in file_names)
