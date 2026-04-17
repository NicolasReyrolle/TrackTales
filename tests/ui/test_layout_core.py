"""Tests for ui.layout core behaviors not covered by integration tests."""

from __future__ import annotations

from types import SimpleNamespace, TracebackType
from typing import Any
from unittest.mock import ANY, MagicMock, patch

from app_state import state
from ui import layout


class _DummyRow:
    def __enter__(self):
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Exit method that does nothing."""
        pass

    def classes(self, *_args: Any, **_kwargs: Any) -> _DummyRow:
        """Mock method to allow chaining."""
        return self


class _DummyRadio:
    def __init__(self, _options: dict[str, str], on_change: Any = None):
        self.on_change = on_change
        self.target: Any | None = None
        self.key: str | None = None

    def bind_value(self, _target: Any, _key: str) -> _DummyRadio:
        """Mock bind_value to capture binding information."""
        self.target = _target
        self.key = _key
        return self

    def props(self, *_args: Any, **_kwargs: Any) -> _DummyRadio:
        """Mock props to enable chaining."""
        return self


class _DummyInput:
    """Mock input component to test method chaining in render_date_range_selector."""

    def classes(self, *_args: Any, **_kwargs: Any) -> _DummyInput:
        """Mock classes to enable chaining."""
        return self

    def bind_enabled_from(self, *_args: Any, **_kwargs: Any) -> _DummyInput:
        """Mock bind_enabled_from to enable chaining."""
        return self

    def bind_value(self, *_args: Any, **_kwargs: Any) -> _DummyInput:
        """Mock bind_value to enable chaining."""
        return self

    def props(self, *_args: Any, **_kwargs: Any) -> _DummyInput:
        """Mock props to enable chaining."""
        return self


class _DummyDate:
    """Mock date component to test method chaining in render_date_range_selector."""

    def __init__(self) -> None:
        self.props_arg = ""

    def props(self, value: str) -> _DummyDate:
        """Mock props to capture arguments and enable chaining."""
        self.props_arg = value
        return self

    def bind_value(self, *_args: Any, **_kwargs: Any) -> _DummyDate:
        """Mock bind_value to enable chaining."""
        return self

    def bind_enabled_from(self, *_args: Any, **_kwargs: Any) -> _DummyDate:
        """Mock bind_enabled_from to enable chaining."""
        return self


def test_render_activity_graphs_renders_all_charts() -> None:
    """Test that render_activity_graphs calls render_pie_rose_graph for all metrics."""
    original_workouts: Any = state.workouts

    workouts_mock = MagicMock()
    workouts_mock.get_count_by_activity.return_value = {"Running": 1}
    workouts_mock.get_distance_by_activity.return_value = {"Running": 5}
    workouts_mock.get_calories_by_activity.return_value = {"Running": 200}
    workouts_mock.get_duration_by_activity.return_value = {"Running": 1}
    workouts_mock.get_elevation_by_activity.return_value = {"Running": 1}

    try:
        state.workouts = workouts_mock
        with patch("ui.activities_tab.ui.row", return_value=_DummyRow()):
            with patch("ui.activities_tab.render_pie_rose_graph") as render_graph_mock:
                layout.render_activity_graphs.func()

        assert render_graph_mock.call_count == 5
        render_graph_mock.assert_any_call(
            "Count by activity", {"Running": 1}, fullscreen_values=ANY
        )
        render_graph_mock.assert_any_call(
            "Distance by activity",
            {"Running": 5},
            "km",
            fullscreen_values=ANY,
        )
        render_graph_mock.assert_any_call(
            "Calories by activity",
            {"Running": 200},
            "kcal",
            fullscreen_values=ANY,
        )
        render_graph_mock.assert_any_call(
            "Duration by activity",
            {"Running": 1},
            "h",
            fullscreen_values=ANY,
        )
        render_graph_mock.assert_any_call(
            "Elevation by activity",
            {"Running": 1},
            "m",
            fullscreen_values=ANY,
        )
    finally:
        state.workouts = original_workouts


def test_render_period_selector_renders_label_and_radio() -> None:
    """Test that render_period_selector renders the 'Aggregate by:' label and radio button."""

    with patch("ui.layout.ui.label") as label_mock:
        with patch("ui.layout.ui.radio", side_effect=_DummyRadio) as radio_mock:
            layout.render_period_selector()

    # Verify the label was created
    label_mock.assert_called_once_with("Aggregate by:")

    # Verify the radio button was created with correct options
    radio_mock.assert_called_once()
    radio_options, call_kwargs = radio_mock.call_args[0][0], radio_mock.call_args[1]
    assert radio_options == {"W": "Week", "M": "Month", "Q": "Quarter", "Y": "Year"}
    assert "on_change" in call_kwargs


def test_render_period_selector_radio_bound_to_state() -> None:
    """Test that render_period_selector radio button is bound to state.trends_period."""

    radio_instances: list[_DummyRadio] = []

    def _radio_factory(_options: dict[str, str], on_change: Any = None) -> _DummyRadio:
        """Create and track radio instances for assertions."""
        instance = _DummyRadio(_options, on_change)
        radio_instances.append(instance)
        return instance

    with patch("ui.layout.ui.label"):
        with patch("ui.layout.ui.radio", side_effect=_radio_factory) as radio_mock:
            layout.render_period_selector()

    # Get the radio instance that was created
    assert radio_mock.call_count == 1
    radio_instance = radio_instances[0]

    # Verify bind_value was called with correct arguments
    assert radio_instance.target == state
    assert radio_instance.key == "trends_period"


def test_render_period_selector_radio_calls_refresh_on_change() -> None:
    """Test that the period selector on_change callback triggers render_trends_graphs.refresh."""

    radio_instances: list[_DummyRadio] = []

    def _radio_factory(_options: dict[str, str], on_change: Any = None) -> _DummyRadio:
        """Create and track radio instances for assertions."""
        instance = _DummyRadio(_options, on_change)
        radio_instances.append(instance)
        return instance

    with patch("ui.layout.ui.label"):
        with patch("ui.layout.ui.radio", side_effect=_radio_factory) as radio_mock:
            with patch("ui.layout.render_trends_graphs") as render_graphs_mock:
                with patch("ui.layout.render_health_data_tab"):
                    with patch("ui.layout._reset_health_data_state"):
                        with patch("ui.layout.schedule_health_data_load"):
                            layout.render_period_selector()

                            assert radio_mock.call_count == 1
                            radio_instance = radio_instances[0]
                            assert radio_instance.on_change is not None

                            # Invoke inside patch scope so mocks are still active
                            radio_instance.on_change()

    render_graphs_mock.refresh.assert_called_once()


def test_render_trends_tab_only_renders_graphs() -> None:
    """Test that render_trends_tab no longer renders the period selector."""

    with patch("ui.trends_tab.render_trends_graphs") as render_graphs_mock:
        with patch("ui.layout.ui.label") as label_mock:
            with patch("ui.layout.ui.radio") as radio_mock:
                layout.render_trends_tab()

    # Only render_trends_graphs should be called; no label or radio
    render_graphs_mock.assert_called_once()
    label_mock.assert_not_called()
    radio_mock.assert_not_called()


def test_change_language_reloads_ui_without_triggering_file_load() -> None:
    """Language switch should reload the page so all translated text updates."""

    fake_app = SimpleNamespace(storage=SimpleNamespace(user={}))

    with patch("ui.layout.app", fake_app):
        with patch("ui.layout.ui.navigate.reload") as reload_mock:
            with patch("ui.layout.load_file") as load_file_mock:
                change_language = getattr(layout, "_change_language")
                change_language("fr")

    assert fake_app.storage.user["language"] == "fr"
    reload_mock.assert_called_once()
    load_file_mock.assert_not_called()


def test_top_level_layout_functions_are_not_refreshable() -> None:
    """Top-level NiceGUI layout functions must stay non-refreshable."""

    assert not hasattr(layout.render_header, "refresh")
    assert not hasattr(layout.render_left_drawer, "refresh")


def test_render_date_range_selector_applies_french_calendar_locale() -> None:
    """Date picker should receive FR locale data when active language is French."""

    original_workouts: Any = state.workouts
    workouts_mock = MagicMock()
    workouts_mock.get_date_bounds.return_value = ("2024/01/01", "2024/12/31")

    dummy_date = _DummyDate()

    try:
        state.workouts = workouts_mock
        with patch("ui.layout.get_language", return_value="fr"):
            with patch("ui.layout.ui.row", return_value=_DummyRow()):
                with patch("ui.layout.ui.input", return_value=_DummyInput()):
                    with patch("ui.layout.ui.date", return_value=dummy_date):
                        layout.render_date_range_selector.func()

        assert "firstDayOfWeek" in dummy_date.props_arg
        assert '"firstDayOfWeek": 1' in dummy_date.props_arg
        assert "janvier" in dummy_date.props_arg
        assert "dimanche" in dummy_date.props_arg
    finally:
        state.workouts = original_workouts


def test_render_date_range_selector_applies_english_calendar_locale() -> None:
    """Date picker should receive EN locale data when active language is English."""

    original_workouts: Any = state.workouts
    workouts_mock = MagicMock()
    workouts_mock.get_date_bounds.return_value = ("2024/01/01", "2024/12/31")

    dummy_date = _DummyDate()

    try:
        state.workouts = workouts_mock
        with patch("ui.layout.get_language", return_value="en"):
            with patch("ui.layout.ui.row", return_value=_DummyRow()):
                with patch("ui.layout.ui.input", return_value=_DummyInput()):
                    with patch("ui.layout.ui.date", return_value=dummy_date):
                        layout.render_date_range_selector.func()

        assert "firstDayOfWeek" in dummy_date.props_arg
        assert '"firstDayOfWeek": 0' in dummy_date.props_arg
        assert "January" in dummy_date.props_arg
        assert "Sunday" in dummy_date.props_arg
    finally:
        state.workouts = original_workouts


def test_render_date_range_selector_unknown_language_falls_back_to_english() -> None:
    """Unknown active language should fallback to English date locale configuration."""

    original_workouts: Any = state.workouts
    workouts_mock = MagicMock()
    workouts_mock.get_date_bounds.return_value = ("2024/01/01", "2024/12/31")

    dummy_date = _DummyDate()

    try:
        state.workouts = workouts_mock
        with patch("ui.layout.get_language", return_value="xx"):
            with patch("ui.layout.ui.row", return_value=_DummyRow()):
                with patch("ui.layout.ui.input", return_value=_DummyInput()):
                    with patch("ui.layout.ui.date", return_value=dummy_date):
                        layout.render_date_range_selector.func()

        assert '"firstDayOfWeek": 0' in dummy_date.props_arg
        assert "January" in dummy_date.props_arg
        assert "Sunday" in dummy_date.props_arg
    finally:
        state.workouts = original_workouts


def test_render_header_dark_mode_callbacks_update_state_and_refresh_graphs() -> None:
    """Header dark-mode callbacks should update state and refresh refreshable graph sections."""

    class _DummyDarkMode:
        """Minimal dark-mode stub for callback testing."""

        def __init__(self, value: bool = False) -> None:
            """Initialize dark-mode flags."""
            self.value = value
            self.enabled = False
            self.disabled = False

        def enable(self) -> None:
            """Mark dark mode as enabled."""
            self.value = True
            self.enabled = True

        def disable(self) -> None:
            """Mark dark mode as disabled."""
            self.value = False
            self.disabled = True

    class _DummyButton:
        """Minimal button/context manager stub for header rendering."""

        def __init__(self, on_click: Any = None, context: bool = False) -> None:
            """Store callback and context behavior."""
            self.on_click = on_click
            self._context = context

        def bind_visibility_from(self, *_args: Any, **_kwargs: Any) -> _DummyButton:
            """Support NiceGUI-style chaining."""
            return self

        def props(self, *_args: Any, **_kwargs: Any) -> _DummyButton:
            """Support NiceGUI-style chaining."""
            return self

        def __enter__(self) -> _DummyButton:
            """Enter context only for context-enabled buttons."""
            if not self._context:
                raise RuntimeError("not a context button")
            return self

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc: BaseException | None,
            tb: TracebackType | None,
        ) -> None:
            """Exit method that does nothing."""
            pass

    class _DummyImage:
        """Minimal image stub supporting classes() chaining."""

        def classes(self, *_args: Any, **_kwargs: Any) -> _DummyImage:
            """Support NiceGUI-style chaining."""
            return self

    class _DummyLabel:
        """Minimal label stub supporting classes() chaining."""

        def classes(self, *_args: Any, **_kwargs: Any) -> _DummyLabel:
            """Support NiceGUI-style chaining."""
            return self

    dark_mode = _DummyDarkMode(value=True)
    callbacks: dict[str, Any] = {}

    def _button_factory(*_args: Any, **kwargs: Any) -> _DummyButton:
        """Create button stubs and capture dark/light callbacks for assertions."""
        icon = kwargs.get("icon")
        on_click = kwargs.get("on_click")
        if icon in {"dark_mode", "light_mode"}:
            callbacks[icon] = on_click
            return _DummyButton(on_click=on_click)
        if icon == "tune":
            return _DummyButton(on_click=on_click, context=True)
        return _DummyButton(on_click=on_click)

    original_dark_mode_enabled = state.dark_mode_enabled
    try:
        state.dark_mode_enabled = False
        with patch("ui.layout.ui.dark_mode", return_value=dark_mode):
            with patch("ui.layout.ui.header", return_value=_DummyRow()):
                with patch("ui.layout.ui.image", return_value=_DummyImage()):
                    with patch("ui.layout.ui.label", return_value=_DummyLabel()):
                        with patch("ui.layout.ui.button", side_effect=_button_factory):
                            with patch("ui.layout.ui.menu", return_value=_DummyRow()):
                                with patch("ui.layout.ui.menu_item"):
                                    with patch("ui.layout.ui.separator"):
                                        with patch("ui.layout.LANGUAGES", {}):
                                            with patch(
                                                "ui.layout.render_activity_graphs.refresh"
                                            ) as act:
                                                with patch(
                                                    "ui.layout.render_trends_graphs.refresh"
                                                ) as trends:
                                                    with patch(
                                                        "ui.layout.render_health_data_tab.refresh"
                                                    ) as health:
                                                        layout.render_header()

                                                        assert state.dark_mode_enabled is True

                                                        callbacks["light_mode"]()
                                                        assert dark_mode.disabled is True
                                                        assert state.dark_mode_enabled is False
                                                        assert act.call_count == 1
                                                        assert trends.call_count == 1
                                                        assert health.call_count == 1

                                                        callbacks["dark_mode"]()
                                                        assert dark_mode.enabled is True
                                                        assert state.dark_mode_enabled is True
                                                        assert act.call_count == 2
                                                        assert trends.call_count == 2
                                                        assert health.call_count == 2
    finally:
        state.dark_mode_enabled = original_dark_mode_enabled
