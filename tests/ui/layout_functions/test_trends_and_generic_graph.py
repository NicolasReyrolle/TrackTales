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


class TestParseDateStr:
    """Tests for the private _parse_date_str helper."""

    def test_parse_date_slash_format(self) -> None:
        """YYYY/MM/DD is accepted."""
        from datetime import datetime

        result = charts._parse_date_str("2024/06/15")  # type: ignore[attr-defined]
        assert result == datetime(2024, 6, 15)

    def test_parse_date_dash_format(self) -> None:
        """YYYY-MM-DD is accepted."""
        from datetime import datetime

        result = charts._parse_date_str("2024-06-15")  # type: ignore[attr-defined]
        assert result == datetime(2024, 6, 15)

    def test_parse_date_invalid_returns_none(self) -> None:
        """Unrecognised date strings return None."""
        result = charts._parse_date_str("not-a-date")  # type: ignore[attr-defined]
        assert result is None

    def test_parse_date_empty_returns_none(self) -> None:
        """Empty strings return None."""
        result = charts._parse_date_str("")  # type: ignore[attr-defined]
        assert result is None


class TestPieRoseFullscreenDataFn:
    """Tests for render_pie_rose_graph fullscreen_data_fn date-range callback."""

    def test_fullscreen_data_fn_date_row_rendered(self) -> None:
        """When fullscreen_data_fn is provided, an extra row is rendered in the dialog."""
        row_calls: list[Any] = []

        def counting_row(*args: Any, **kwargs: Any) -> DummyRow:
            row_calls.append((args, kwargs))
            return DummyRow()

        with (
            patch("ui.charts.ui.dialog", return_value=MagicMock()),
            patch("ui.charts.ui.card", return_value=DummyRow()),
            patch("ui.charts.ui.row", side_effect=counting_row),
            patch("ui.charts.ui.label"),
            patch("ui.charts.ui.button", return_value=DummyComponent()),
            patch("ui.charts.ui.input", return_value=DummyComponent()),
            patch("ui.charts.ui.date", return_value=DummyComponent()),
            patch("ui.charts.ui.echart", return_value=DummyComponent()),
        ):
            charts.render_pie_rose_graph(
                "Elevation",
                {"Running": 500},
                "m",
                fullscreen_data_fn=lambda s, e: {"Running": 400},
            )

        # At least 2 rows created: the header row + the date range row
        assert len(row_calls) >= 2

    def test_fullscreen_data_fn_updates_echart_on_date_change(self) -> None:
        """_on_date_change should call fullscreen_data_fn and update the echart."""
        date_on_change_cb: list[Any] = []
        echart_elements: list[DummyComponent] = []

        def capture_date(*args: Any, on_change: Any = None, **kwargs: Any) -> DummyComponent:
            if on_change is not None:
                date_on_change_cb.append(on_change)
            return DummyComponent()

        def capture_echart(config: dict, *args: Any, **kwargs: Any) -> DummyComponent:
            elem = DummyComponent()
            elem.options = config  # type: ignore[attr-defined]
            echart_elements.append(elem)
            return elem

        new_data: dict[str, int] = {"Hiking": 999}

        with (
            patch("ui.charts.ui.dialog", return_value=MagicMock()),
            patch("ui.charts.ui.card", return_value=DummyRow()),
            patch("ui.charts.ui.row", return_value=DummyRow()),
            patch("ui.charts.ui.label"),
            patch("ui.charts.ui.button", return_value=DummyComponent()),
            patch("ui.charts.ui.input", return_value=DummyComponent()),
            patch("ui.charts.ui.date", side_effect=capture_date),
            patch("ui.charts.ui.echart", side_effect=capture_echart),
        ):
            charts.render_pie_rose_graph(
                "Elevation",
                {"Running": 500},
                "m",
                fullscreen_data_fn=lambda s, e: new_data,
            )

        assert len(date_on_change_cb) == 1, "Expected exactly one on_change callback registered"

        # Simulate user selecting a date range
        fake_event = MagicMock()
        fake_event.value = {"from": "2024/01/01", "to": "2024/12/31"}
        date_on_change_cb[0](fake_event)

        # The fullscreen echart (first echart created) should now have updated data
        fs_echart = echart_elements[0]
        assert fs_echart.options["series"][0]["data"] == [  # type: ignore[index]
            {"value": 999, "name": "Hiking"}
        ]
