"""Tests for ui.layout trend rendering and generic chart helper."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from app_state import state
from ui import charts, layout

from ._helpers import DummyComponent, DummyRow


class TestRenderTrendsGraphs:
    """Tests for render_trends_graphs function."""

    def test_render_trends_graphs_renders_all_charts(self) -> None:
        """Test that render_trends_graphs calls render_generic_graph for all metrics."""
        original_workouts: Any = state.workouts
        original_activity = state.selected_activity_type

        workouts_mock = MagicMock()
        workouts_mock.get_count_by_period.return_value = {"2024-01": 5}
        workouts_mock.get_distance_by_period.return_value = {"2024-01": 10}
        workouts_mock.get_calories_by_period.return_value = {"2024-01": 500}
        workouts_mock.get_duration_by_period.return_value = {"2024-01": 120}
        workouts_mock.get_elevation_by_period.return_value = {"2024-01": 50}

        try:
            state.workouts = workouts_mock
            state.selected_activity_type = "Running"

            with patch("ui.trends_tab.ui.row", return_value=DummyRow()):
                with patch("ui.trends_tab.render_generic_graph") as render_graph_mock:
                    layout.render_trends_graphs.func()

            assert render_graph_mock.call_count == 5
            render_graph_mock.assert_any_call("Count by month", {"2024-01": 5})
            render_graph_mock.assert_any_call("Distance by month", {"2024-01": 10}, "km")
            render_graph_mock.assert_any_call("Calories by month", {"2024-01": 500}, "kcal")
            render_graph_mock.assert_any_call("Duration by month", {"2024-01": 120}, "h")
            render_graph_mock.assert_any_call("Elevation by month", {"2024-01": 50}, "m")

            workouts_mock.get_count_by_period.assert_called_once_with(
                "M", activity_type="Running", start_date=None, end_date=None
            )
            workouts_mock.get_distance_by_period.assert_called_once_with(
                "M", unit="km", activity_type="Running", start_date=None, end_date=None
            )
            workouts_mock.get_calories_by_period.assert_called_once_with(
                "M", activity_type="Running", start_date=None, end_date=None
            )
            workouts_mock.get_duration_by_period.assert_called_once_with(
                "M", activity_type="Running", start_date=None, end_date=None
            )
            workouts_mock.get_elevation_by_period.assert_called_once_with(
                "M", activity_type="Running", unit="m", start_date=None, end_date=None
            )
        finally:
            state.workouts = original_workouts
            state.selected_activity_type = original_activity

    def test_render_trends_graphs_with_week_period(self) -> None:
        """Test that render_trends_graphs uses correct period when set to week."""
        original_workouts: Any = state.workouts
        original_activity = state.selected_activity_type
        original_period = state.trends_period

        workouts_mock = MagicMock()
        workouts_mock.get_count_by_period.return_value = {"2024-W01": 2}
        workouts_mock.get_distance_by_period.return_value = {"2024-W01": 10}
        workouts_mock.get_calories_by_period.return_value = {"2024-W01": 500}
        workouts_mock.get_duration_by_period.return_value = {"2024-W01": 120}
        workouts_mock.get_elevation_by_period.return_value = {"2024-W01": 50}

        try:
            state.workouts = workouts_mock
            state.selected_activity_type = "Running"
            state.trends_period = "W"

            with patch("ui.trends_tab.ui.row", return_value=DummyRow()):
                with patch("ui.trends_tab.render_generic_graph") as render_graph_mock:
                    layout.render_trends_graphs.func()

            workouts_mock.get_count_by_period.assert_called_once_with(
                "W", activity_type="Running", start_date=None, end_date=None
            )
            workouts_mock.get_distance_by_period.assert_called_once_with(
                "W", unit="km", activity_type="Running", start_date=None, end_date=None
            )

            called_labels = [call[0][0] for call in render_graph_mock.call_args_list]
            assert any("week" in label.lower() for label in called_labels)
        finally:
            state.workouts = original_workouts
            state.selected_activity_type = original_activity
            state.trends_period = original_period

    def test_render_trends_graphs_with_quarter_period(self) -> None:
        """Test that render_trends_graphs uses correct period when set to quarter."""
        original_workouts: Any = state.workouts
        original_activity = state.selected_activity_type
        original_period = state.trends_period

        workouts_mock = MagicMock()
        workouts_mock.get_count_by_period.return_value = {"2024-Q1": 15}
        workouts_mock.get_distance_by_period.return_value = {"2024-Q1": 50}
        workouts_mock.get_calories_by_period.return_value = {"2024-Q1": 2000}
        workouts_mock.get_duration_by_period.return_value = {"2024-Q1": 600}
        workouts_mock.get_elevation_by_period.return_value = {"2024-Q1": 250}

        try:
            state.workouts = workouts_mock
            state.selected_activity_type = "Running"
            state.trends_period = "Q"

            with patch("ui.trends_tab.ui.row", return_value=DummyRow()):
                with patch("ui.trends_tab.render_generic_graph") as render_graph_mock:
                    layout.render_trends_graphs.func()

            workouts_mock.get_count_by_period.assert_called_once_with(
                "Q", activity_type="Running", start_date=None, end_date=None
            )

            called_labels = [call[0][0] for call in render_graph_mock.call_args_list]
            assert any("quarter" in label.lower() for label in called_labels)
        finally:
            state.workouts = original_workouts
            state.selected_activity_type = original_activity
            state.trends_period = original_period

    def test_render_trends_graphs_with_year_period(self) -> None:
        """Test that render_trends_graphs uses correct period when set to year."""
        original_workouts: Any = state.workouts
        original_activity = state.selected_activity_type
        original_period = state.trends_period

        workouts_mock = MagicMock()
        workouts_mock.get_count_by_period.return_value = {"2024": 60}
        workouts_mock.get_distance_by_period.return_value = {"2024": 200}
        workouts_mock.get_calories_by_period.return_value = {"2024": 8000}
        workouts_mock.get_duration_by_period.return_value = {"2024": 2400}
        workouts_mock.get_elevation_by_period.return_value = {"2024": 1000}

        try:
            state.workouts = workouts_mock
            state.selected_activity_type = "Running"
            state.trends_period = "Y"

            with patch("ui.trends_tab.ui.row", return_value=DummyRow()):
                with patch("ui.trends_tab.render_generic_graph") as render_graph_mock:
                    layout.render_trends_graphs.func()

            workouts_mock.get_count_by_period.assert_called_once_with(
                "Y", activity_type="Running", start_date=None, end_date=None
            )

            called_labels = [call[0][0] for call in render_graph_mock.call_args_list]
            assert any("year" in label.lower() for label in called_labels)
        finally:
            state.workouts = original_workouts
            state.selected_activity_type = original_activity
            state.trends_period = original_period


class TestRenderGenericGraph:
    """Tests for render_generic_graph function."""

    def test_render_generic_graph_includes_trend_by_default(self) -> None:
        """Trend series is included when show_trend is not specified."""
        values = {"2024-01": 10, "2024-02": 20}

        with (
            patch("ui.charts.ui.dialog", return_value=MagicMock()),
            patch("ui.charts.ui.card", return_value=DummyRow()),
            patch("ui.charts.ui.row", return_value=DummyRow()),
            patch("ui.charts.ui.label"),
            patch("ui.charts.ui.button", return_value=DummyComponent()),
            patch("ui.charts.ui.echart") as echart_mock,
        ):
            charts.render_generic_graph("Distance by month", values, "km")

        chart_options = echart_mock.call_args.args[0]
        series = chart_options["series"]
        assert len(series) == 2
        assert series[0]["type"] == "bar"
        assert series[1]["name"] == "Trend"

    def test_render_generic_graph_excludes_trend_when_disabled(self) -> None:
        """Trend series is omitted when show_trend is False."""
        values = {"2024-01": 10, "2024-02": 20}

        with (
            patch("ui.charts.ui.dialog", return_value=MagicMock()),
            patch("ui.charts.ui.card", return_value=DummyRow()),
            patch("ui.charts.ui.row", return_value=DummyRow()),
            patch("ui.charts.ui.label"),
            patch("ui.charts.ui.button", return_value=DummyComponent()),
            patch("ui.charts.ui.echart") as echart_mock,
        ):
            charts.render_generic_graph("Distance by month", values, "km", show_trend=False)

        chart_options = echart_mock.call_args.args[0]
        series = chart_options["series"]
        assert len(series) == 1
        assert series[0]["type"] == "bar"

    def test_render_generic_graph_line_type_marks_gap_bridges(self) -> None:
        """Line graphs should include a bridge layer with connectNulls for inferred segments."""
        values = {"2024-01": 10, "2024-02": None, "2024-03": 20}

        with (
            patch("ui.charts.ui.dialog", return_value=MagicMock()),
            patch("ui.charts.ui.card", return_value=DummyRow()),
            patch("ui.charts.ui.row", return_value=DummyRow()),
            patch("ui.charts.ui.label"),
            patch("ui.charts.ui.button", return_value=DummyComponent()),
            patch("ui.charts.ui.echart") as echart_mock,
        ):
            charts.render_generic_graph(
                "Distance by month",
                values,
                "km",
                graph_type="line",
                show_trend=False,
            )

        chart_options = echart_mock.call_args.args[0]
        series = chart_options["series"]
        assert len(series) == 2
        assert series[0]["type"] == "line"
        assert series[0]["connectNulls"] is True
        assert series[1]["type"] == "line"
        assert series[1]["connectNulls"] is False

    def test_render_generic_graph_line_tooltip_uses_js_function(self) -> None:
        """Line chart tooltip must use a JS function formatter with null/n/a handling.

        NiceGUI evaluates dict keys prefixed with ':' as JS expressions.  The
        formatter is a function so that interpolated null points can display
        "n/a" instead of showing just the unit suffix.
        """
        values = {"2024-01": 10, "2024-02": 20}

        with (
            patch("ui.charts.ui.dialog", return_value=MagicMock()),
            patch("ui.charts.ui.card", return_value=DummyRow()),
            patch("ui.charts.ui.row", return_value=DummyRow()),
            patch("ui.charts.ui.label"),
            patch("ui.charts.ui.button", return_value=DummyComponent()),
            patch("ui.charts.ui.echart") as echart_mock,
        ):
            charts.render_generic_graph(
                "W' over time",
                values,
                "kJ",
                graph_type="line",
                show_trend=False,
            )

        chart_options = echart_mock.call_args.args[0]
        tooltip = chart_options["tooltip"]
        # Must use the ":formatter" key (NiceGUI JS eval prefix), not plain "formatter"
        assert ":formatter" in tooltip, "Line chart must use ':formatter' JS key"
        assert "formatter" not in tooltip, "Plain 'formatter' key must not be present for line"
        formatter = tooltip[":formatter"]
        assert "function(params)" in formatter, "Formatter must be a JS function"
        assert "n/a" in formatter, "Formatter must handle null values with n/a"
        assert "kJ" in formatter, "Formatter must include the unit in the non-null branch"
        assert "{c1}" not in formatter, "Formatter must not reference {c1}"

    def test_render_generic_graph_line_tooltip_null_shows_na(self) -> None:
        """Line chart tooltip JS function must return 'n/a' (no unit) for null data points."""
        values = {"2024-01": 10, "2024-02": None, "2024-03": 30}

        with (
            patch("ui.charts.ui.dialog", return_value=MagicMock()),
            patch("ui.charts.ui.card", return_value=DummyRow()),
            patch("ui.charts.ui.row", return_value=DummyRow()),
            patch("ui.charts.ui.label"),
            patch("ui.charts.ui.button", return_value=DummyComponent()),
            patch("ui.charts.ui.echart") as echart_mock,
        ):
            charts.render_generic_graph(
                "CP over time",
                values,
                "W",
                graph_type="line",
                show_trend=False,
            )

        chart_options = echart_mock.call_args.args[0]
        formatter_js = chart_options["tooltip"][":formatter"]
        # Verify the null guard returns "n/a" without any unit suffix
        assert "n/a" in formatter_js
        # Ensure the unit appears only in the non-null return branch, not next to n/a
        na_index = formatter_js.index("n/a")
        unit_index = formatter_js.index(" W")
        assert unit_index > na_index, "Unit suffix must come after the n/a guard, not inside it"

    def test_render_generic_graph_has_datazoom_and_toolbox(self) -> None:
        """Bar charts should include inside dataZoom and a toolbox for restore/save."""
        values = {"2024-01": 10, "2024-02": 20}

        with (
            patch("ui.charts.ui.dialog", return_value=MagicMock()),
            patch("ui.charts.ui.card", return_value=DummyRow()),
            patch("ui.charts.ui.row", return_value=DummyRow()),
            patch("ui.charts.ui.label"),
            patch("ui.charts.ui.button", return_value=DummyComponent()),
            patch("ui.charts.ui.echart") as echart_mock,
        ):
            charts.render_generic_graph("Distance by month", values, "km")

        chart_options = echart_mock.call_args.args[0]
        assert "dataZoom" in chart_options
        zoom_types = [z["type"] for z in chart_options["dataZoom"]]  # type: ignore[index]
        assert "inside" in zoom_types
        assert "toolbox" in chart_options


class TestChartsModuleComponents:
    """Tests for chart helpers implemented in ui.charts."""

    def test_stat_card_click_handler_is_wired_when_provided(self) -> None:
        """stat_card should register click handler and invoke callback when clicked."""

        class _CardProbe(DummyRow):
            def __init__(self) -> None:
                self.events: dict[str, Any] = {}
                self.props_calls: list[str] = []

            def on(self, event: str, handler: Any) -> _CardProbe:
                self.events[event] = handler
                return self

            def props(self, *args: Any, **_kwargs: Any) -> _CardProbe:
                self.props_calls.extend(str(arg) for arg in args)
                return self

        card_probe = _CardProbe()
        callback = MagicMock()

        with (
            patch("ui.charts.ui.card", return_value=card_probe),
            patch("ui.charts.ui.row", return_value=DummyRow()),
            patch("ui.charts.ui.label", return_value=DummyComponent()),
        ):
            charts.stat_card(
                "Distance",
                value_ref={"distance": "10.0"},
                key="distance",
                on_click=callback,
            )

        assert "tabindex=0 role=button" in card_probe.props_calls
        assert "click" in card_probe.events
        assert "keydown.enter" in card_probe.events
        assert "keydown.space" in card_probe.events
        card_probe.events["click"](object())
        callback.assert_called_once()

    def test_stat_card_binds_tooltip_when_configured(self) -> None:
        """stat_card should create and bind tooltip when tooltip refs are provided."""
        tooltip_component = DummyComponent()

        with (
            patch("ui.charts.ui.card", return_value=DummyRow()),
            patch("ui.charts.ui.row", return_value=DummyRow()),
            patch("ui.charts.ui.label", return_value=DummyComponent()),
            patch("ui.charts.ui.tooltip", return_value=tooltip_component) as tooltip_mock,
        ):
            charts.stat_card(
                "Distance",
                value_ref={"distance": "10.0"},
                key="distance",
                unit="km",
                tooltip_ref={"distance_tip": "10.0 km"},
                tooltip_key="distance_tip",
            )

        tooltip_mock.assert_called_once()

    def test_render_pie_rose_graph_builds_pie_series(self) -> None:
        """render_pie_rose_graph should emit a pie series with roseType and chart data."""
        values = {"Running": 3, "Cycling": 1}

        with (
            patch("ui.charts.ui.dialog", return_value=MagicMock()),
            patch("ui.charts.ui.card", return_value=DummyRow()),
            patch("ui.charts.ui.row", return_value=DummyRow()),
            patch("ui.charts.ui.label"),
            patch("ui.charts.ui.button", return_value=DummyComponent()),
            patch("ui.charts.ui.echart") as echart_mock,
        ):
            charts.render_pie_rose_graph("Activities", values)

        chart_options = echart_mock.call_args.args[0]
        series = chart_options["series"]
        assert len(series) == 1
        assert series[0]["type"] == "pie"
        assert series[0]["roseType"] == "rose"
        assert series[0]["data"] == [
            {"value": 3, "name": "Running"},
            {"value": 1, "name": "Cycling"},
        ]

    def test_render_pie_rose_graph_uses_fullscreen_values_in_dialog(self) -> None:
        """When fullscreen_values is given, the fullscreen echart should use that data."""
        card_values = {"Running": 3, "Others": 1}
        fullscreen_values = {"Running": 3, "Cycling": 1, "Walking": 0}

        echart_calls: list[dict] = []

        def capture_echart(config: dict, *_a, **_kw):
            echart_calls.append(config)
            return DummyComponent()

        with (
            patch("ui.charts.ui.dialog", return_value=MagicMock()),
            patch("ui.charts.ui.card", return_value=DummyRow()),
            patch("ui.charts.ui.row", return_value=DummyRow()),
            patch("ui.charts.ui.label"),
            patch("ui.charts.ui.button", return_value=DummyComponent()),
            patch("ui.charts.ui.echart", side_effect=capture_echart),
        ):
            charts.render_pie_rose_graph(
                "Activities", card_values, fullscreen_values=fullscreen_values
            )

        # First echart call is fullscreen (inside dialog), second is the card
        assert len(echart_calls) == 2
        fullscreen_config = echart_calls[0]
        card_data = echart_calls[1]["series"][0]["data"]
        fullscreen_data = fullscreen_config["series"][0]["data"]
        assert fullscreen_data == [
            {"value": 3, "name": "Running"},
            {"value": 1, "name": "Cycling"},
            {"value": 0, "name": "Walking"},
        ]
        assert card_data == [
            {"value": 3, "name": "Running"},
            {"value": 1, "name": "Others"},
        ]
        # Fullscreen uses a larger radius; card uses the compact radius
        assert fullscreen_config["series"][0]["radius"] == ["15%", "75%"]
        assert echart_calls[1]["series"][0]["radius"] == ["10%", "60%"]
        # dataZoom is not added to pie charts (it has no effect on them)
        assert "dataZoom" not in fullscreen_config
        assert "dataZoom" not in echart_calls[1]

    def test_render_scatter_graph_builds_scatter_series(self) -> None:
        """render_scatter_graph should emit an ECharts scatter series."""
        with (
            patch("ui.charts.ui.dialog", return_value=MagicMock()),
            patch("ui.charts.ui.card", return_value=DummyRow()),
            patch("ui.charts.ui.row", return_value=DummyRow()),
            patch("ui.charts.ui.label"),
            patch("ui.charts.ui.button", return_value=DummyComponent()),
            patch("ui.charts.ui.echart") as echart_mock,
        ):
            charts.render_scatter_graph(
                "Distance vs Pace",
                [(5.0, 4.5), (10.0, 5.1)],
                "Distance",
                "Pace",
                "km",
                "min/km",
            )

        chart_options = echart_mock.call_args.args[0]
        assert chart_options["backgroundColor"] == "transparent"
        assert chart_options["series"][0]["type"] == "scatter"
        assert chart_options["series"][0]["data"] == [[5.0, 4.5], [10.0, 5.1]]
        assert chart_options["series"][1]["type"] == "line"
        assert chart_options["series"][1]["data"]
        assert "<br" not in chart_options["tooltip"][":formatter"]
        assert "\n" in chart_options["tooltip"][":formatter"]

    def test_render_scatter_graph_supports_date_tooltip_and_click_handler(self) -> None:
        """Metadata points should include date in tooltip and expose click callbacks."""

        class _ChartProbe(DummyComponent):
            def __init__(self) -> None:
                self.events: dict[str, Any] = {}

            def on(self, event: str, handler: Any, **_kwargs: Any) -> _ChartProbe:
                self.events[event] = handler
                return self

        chart_probe = _ChartProbe()
        click_callback = MagicMock()

        with (
            patch("ui.charts.ui.dialog", return_value=MagicMock()),
            patch("ui.charts.ui.card", return_value=DummyRow()),
            patch("ui.charts.ui.row", return_value=DummyRow()),
            patch("ui.charts.ui.label"),
            patch("ui.charts.ui.button", return_value=DummyComponent()),
            patch("ui.charts.ui.echart", return_value=chart_probe) as echart_mock,
        ):
            charts.render_scatter_graph(
                "Distance vs Pace",
                [(5.0, 4.5, "01/06/2025", 12)],
                "Distance",
                "Pace",
                "km",
                "min/km",
                date_label="Date",
                on_point_click=click_callback,
            )

        chart_options = echart_mock.call_args.args[0]
        assert chart_options["series"][0]["data"] == [[5.0, 4.5, "01/06/2025", 12]]
        assert "Date" in chart_options["tooltip"][":formatter"]
        assert "<br" not in chart_options["tooltip"][":formatter"]
        assert "click" in chart_probe.events
        chart_probe.events["click"](MagicMock(args={"data": [5.0, 4.5, "01/06/2025", 12]}))
        click_callback.assert_called_once_with(12)
        click_callback.reset_mock()
        chart_probe.events["click"](MagicMock(args={"dataIndex": 0}))
        click_callback.assert_called_once_with(12)
        click_callback.reset_mock()
        chart_probe.events["click"](MagicMock(args={"dataIndex": "0"}))
        click_callback.assert_called_once_with(12)

    def test_render_scatter_graph_keeps_trendline_when_x_values_are_constant(self) -> None:
        """Trendline should still render as a horizontal guide for constant X values."""
        with (
            patch("ui.charts.ui.dialog", return_value=MagicMock()),
            patch("ui.charts.ui.card", return_value=DummyRow()),
            patch("ui.charts.ui.row", return_value=DummyRow()),
            patch("ui.charts.ui.label"),
            patch("ui.charts.ui.button", return_value=DummyComponent()),
            patch("ui.charts.ui.echart") as echart_mock,
        ):
            charts.render_scatter_graph(
                "Elevation vs Pace",
                [(0.0, 5.0), (0.0, 4.8), (0.0, 5.2)],
                "Elevation",
                "Pace",
            )

        chart_options = echart_mock.call_args.args[0]
        trend_data = chart_options["series"][1]["data"]
        assert len(trend_data) == 2
        assert trend_data[0][1] == trend_data[1][1]

    def test_render_heat_map_graph_builds_heatmap_series(self) -> None:
        """render_heat_map_graph should build indexed heatmap coordinates."""
        echart_calls: list[dict[str, Any]] = []

        def _capture_echart(config: dict[str, Any], *_args: Any, **_kwargs: Any) -> DummyComponent:
            echart_calls.append(config)
            return DummyComponent()

        with (
            patch("ui.charts.ui.dialog", return_value=MagicMock()),
            patch("ui.charts.ui.card", return_value=DummyRow()),
            patch("ui.charts.ui.row", return_value=DummyRow()),
            patch("ui.charts.ui.label"),
            patch("ui.charts.ui.button", return_value=DummyComponent()),
            patch("ui.charts.ui.echart", side_effect=_capture_echart),
        ):
            charts.render_heat_map_graph(
                "Activity heat map (day/time)",
                ["0", "1"],
                ["Mon", "Tue"],
                [(0, 0, 2), (1, 1, 4)],
                x_axis_name="Hour of day",
                y_axis_name="Day of week",
                value_label="Workouts",
                value_label_singular="workout",
                value_label_plural="workouts",
                fullscreen_y_labels=["Monday", "Tuesday"],
            )

        fullscreen_options = echart_calls[0]
        card_options = echart_calls[1]
        assert card_options["backgroundColor"] == "transparent"
        assert card_options["series"][0]["type"] == "heatmap"
        assert card_options["series"][0]["data"] == [[0, 0, 2], [1, 1, 4]]
        assert "visualMap" not in card_options
        assert "visualMap" in fullscreen_options
        assert fullscreen_options["xAxis"]["name"] == "Hour of day"
        assert fullscreen_options["yAxis"]["name"] == "Day of week"
        assert card_options["yAxis"]["data"] == ["Mon", "Tue"]
        assert fullscreen_options["yAxis"]["data"] == ["Monday", "Tuesday"]
        assert card_options["yAxis"]["inverse"] is True
        assert card_options["yAxis"]["axisLabel"]["interval"] == 0
        assert "from" in fullscreen_options["tooltip"][":formatter"]
        assert "to" in fullscreen_options["tooltip"][":formatter"]
        assert "<br" not in fullscreen_options["tooltip"][":formatter"]

    def test_render_box_plot_graph_builds_boxplot_series(self) -> None:
        """render_box_plot_graph should emit one boxplot row per category."""
        with (
            patch("ui.charts.ui.dialog", return_value=MagicMock()),
            patch("ui.charts.ui.card", return_value=DummyRow()),
            patch("ui.charts.ui.row", return_value=DummyRow()),
            patch("ui.charts.ui.label"),
            patch("ui.charts.ui.button", return_value=DummyComponent()),
            patch("ui.charts.ui.echart") as echart_mock,
        ):
            charts.render_box_plot_graph(
                "Pace distribution by activity",
                {"Running": [4.0, 4.5, 5.0], "Walking": [9.0, 10.0, 11.0]},
            )

        chart_options = echart_mock.call_args.args[0]
        assert chart_options["backgroundColor"] == "transparent"
        assert chart_options["series"][0]["type"] == "boxplot"
        assert chart_options["xAxis"]["data"] == ["Running", "Walking"]
