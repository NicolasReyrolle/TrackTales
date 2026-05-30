"""Tests for ui.workout_detail_modal — route tab localization and profile chart."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import patch

import pandas as pd
import pytest

from ui import workout_detail_modal as wdm

from ._stubs import _DummyElement


class TestRouteTabLocalizationAndCoverage:
    """Focused tests for route tab localization and route-parts behavior."""

    @staticmethod
    def _build_route(points: list[tuple[float, float]]) -> Any:
        from logic.workout_manager.workout_route import RoutePoint, WorkoutRoute

        base_time = pd.Timestamp("2024-01-01 10:00:00").to_pydatetime()
        return WorkoutRoute(
            points=[
                RoutePoint(
                    time=base_time + timedelta(seconds=i),
                    latitude=lat,
                    longitude=lon,
                    altitude=100.0,
                    speed=3.0,
                )
                for i, (lat, lon) in enumerate(points)
            ]
        )

    def test_get_row_routes_prefers_non_empty_route_parts(self) -> None:
        """Route parts should be preferred over the merged fallback route."""
        part = self._build_route([(48.85, 2.35), (48.851, 2.351)])
        fallback = self._build_route([(47.0, 2.0), (47.001, 2.001)])
        row = {"route_parts": [part], "route": fallback}

        assert wdm._get_row_routes(row) == [part]

    def test_do_refresh_route_tab_uses_translated_route_and_marker_labels(self) -> None:
        """Route refresh should pass translated route index/start/end labels to tooltips."""
        row = {"route_parts": [self._build_route([(48.85, 2.35), (48.851, 2.351)])]}
        no_route_label = _DummyElement()
        route_map = _DummyElement()

        t_calls: list[tuple[str, dict[str, str]]] = []
        tooltip_texts: list[str] = []

        def fake_t(message: str, **kwargs: str) -> str:
            t_calls.append((message, kwargs))
            if message == "Route {index}":
                return f"Parcours {kwargs['index']}"
            if message == "Start":
                return "Départ"
            if message == "End":
                return "Arrivée"
            return message

        def capture_run_layer_method(_layer_id: str, method: str, text: str) -> _DummyElement:
            if method == "bindTooltip":
                tooltip_texts.append(text)
            return route_map

        def run_coroutine_sync(coro: Any) -> Any:
            return asyncio.run(coro)

        with (
            patch.object(route_map, "run_layer_method", side_effect=capture_run_layer_method),
            patch(
                "ui.workout_detail_modal.routes.background_tasks.create",
                side_effect=run_coroutine_sync,
            ),
        ):
            wdm._do_refresh_route_tab(no_route_label, route_map, row, translate=fake_t)

        assert ("Route {index}", {"index": "1"}) in t_calls
        assert ("Start", {}) in t_calls
        assert ("End", {}) in t_calls
        assert "Parcours 1" in tooltip_texts
        assert "Départ - Parcours 1" in tooltip_texts
        assert "Arrivée - Parcours 1" in tooltip_texts

    def test_do_refresh_route_tab_falls_back_when_points_are_invalid(self) -> None:
        """Route tab should fall back to world view when every route point is invalid."""
        from logic.workout_manager.workout_route import RoutePoint, WorkoutRoute

        invalid_route = WorkoutRoute(
            points=[
                RoutePoint(
                    time=datetime(2024, 1, 1, 10, 0, 0),
                    latitude=float("nan"),
                    longitude=2.35,
                    altitude=100.0,
                    speed=3.0,
                )
            ]
        )
        row = {"route": invalid_route}
        no_route_label = _DummyElement()
        route_map = _DummyElement()

        with (
            patch.object(route_map, "set_center") as set_center,
            patch.object(route_map, "set_zoom") as set_zoom,
        ):
            wdm._do_refresh_route_tab(no_route_label, route_map, row)

        assert not no_route_label._visible
        assert route_map._visible
        set_center.assert_called_once_with((0.0, 0.0))
        set_zoom.assert_called_once_with(1)

    def test_build_route_profile_chart_config_includes_altitude_and_metric_columns(self) -> None:
        """Route profile config should include altitude and sampled pace/speed metadata."""
        from logic.workout_manager.workout_route import RoutePoint, WorkoutRoute

        base_time = pd.Timestamp("2024-01-01").to_pydatetime()
        route = WorkoutRoute(
            points=[
                RoutePoint(
                    time=base_time + timedelta(seconds=i * 10),
                    latitude=48.85 + (i * 0.0001),
                    longitude=2.35 + (i * 0.0001),
                    altitude=100.0 + i,
                    speed=3.0 + i,
                )
                for i in range(3)
            ]
        )

        config = wdm._build_route_profile_chart_config([route])
        altitude_series = config["series"][0]
        pace_series = config["series"][1]
        altitude_data = altitude_series["data"]
        pace_data = pace_series["data"]

        assert config["backgroundColor"] == "transparent"
        assert config["legend"]["top"] == 8
        assert config["xAxis"]["nameLocation"] == "middle"
        assert config["xAxis"]["nameGap"] == 42
        assert isinstance(config["yAxis"], list)
        assert config["yAxis"][0]["scale"] is True
        assert config["yAxis"][0]["nameLocation"] == "middle"
        assert config["yAxis"][0]["nameGap"] == 52
        assert config["yAxis"][1]["scale"] is True
        assert config["yAxis"][1]["nameLocation"] == "middle"
        assert config["yAxis"][1]["nameGap"] == 56
        assert altitude_data[0][1] == pytest.approx(100.0)
        assert pace_data[1][2] is not None  # pace min/km
        assert pace_data[1][3] is not None  # speed km/h

    def test_build_route_profile_chart_config_excludes_heart_rate_series(self) -> None:
        """Route profile chart should not include HR axis/series after chart split."""
        from logic.workout_manager.workout_route import RoutePoint, WorkoutRoute

        base_time = pd.Timestamp("2024-01-01").to_pydatetime()
        p1 = RoutePoint(
            time=base_time,
            latitude=48.85,
            longitude=2.35,
            altitude=100.0,
            speed=3.0,
        )
        p2 = RoutePoint(
            time=base_time + timedelta(seconds=10),
            latitude=48.8501,
            longitude=2.3501,
            altitude=101.0,
            speed=3.2,
            heart_rate=142.0,
        )
        route = WorkoutRoute(points=[p1, p2])

        config = wdm._build_route_profile_chart_config([route])
        profile_data = config["series"][0]["data"]

        assert profile_data[0][4] is None
        assert profile_data[1][4] == pytest.approx(142.0)
        assert len(config["series"]) == 2
        assert len(config["yAxis"]) == 2
        assert all("Heart Rate" not in legend for legend in config["legend"]["data"])
        assert "Heart Rate" not in config["tooltip"][":formatter"]

    def test_build_route_profile_chart_config_smooths_pause_spikes(self) -> None:
        """Pause-like segments should not inject extreme pace spikes into profile samples."""
        from logic.workout_manager.workout_route import RoutePoint, WorkoutRoute

        base_time = pd.Timestamp("2024-01-01").to_pydatetime()
        route = WorkoutRoute(
            points=[
                RoutePoint(
                    time=base_time,
                    latitude=48.8500,
                    longitude=2.3500,
                    altitude=100.0,
                    speed=0.0,
                ),
                RoutePoint(
                    time=base_time + timedelta(seconds=60),
                    latitude=48.8509,
                    longitude=2.3500,
                    altitude=101.0,
                    speed=0.0,
                ),
                RoutePoint(
                    time=base_time + timedelta(seconds=240),
                    latitude=48.8510,
                    longitude=2.3500,
                    altitude=102.0,
                    speed=0.0,
                ),
                RoutePoint(
                    time=base_time + timedelta(seconds=300),
                    latitude=48.8519,
                    longitude=2.3500,
                    altitude=103.0,
                    speed=0.0,
                ),
            ]
        )

        config = wdm._build_route_profile_chart_config([route])
        data = config["series"][0]["data"]
        segment_time_s = 60.0
        expected_distance_m = WorkoutRoute.haversine_m(48.8500, 2.3500, 48.8509, 2.3500)
        expected_pace_min_per_km = (segment_time_s / 60.0) / (expected_distance_m / 1000.0)

        assert data[2][2] is not None
        assert data[2][2] == pytest.approx(expected_pace_min_per_km, rel=0.05)

    def test_build_route_profile_chart_config_uses_route_points_directly(self) -> None:
        """Route profile chart should compute altitudes directly from route points."""
        from logic.workout_manager.workout_route import RoutePoint, WorkoutRoute

        base_time = pd.Timestamp("2024-01-01").to_pydatetime()
        route = WorkoutRoute(
            points=[
                RoutePoint(
                    time=base_time + timedelta(seconds=i * 10),
                    latitude=48.85 + (i * 0.0001),
                    longitude=2.35 + (i * 0.0001),
                    altitude=100.0 + i,
                    speed=3.0 + i,
                )
                for i in range(2)
            ]
        )
        with patch.object(
            route, "to_dataframe", side_effect=AssertionError("should not be called")
        ):
            config = wdm._build_route_profile_chart_config([route])

        assert len(config["series"][0]["data"]) == 2

    def test_build_route_profile_chart_config_skips_invalid_route_points(self) -> None:
        """Routes with fewer than two valid map points should not emit profile points."""
        from logic.workout_manager.workout_route import RoutePoint, WorkoutRoute

        base_time = pd.Timestamp("2024-01-01").to_pydatetime()
        route = WorkoutRoute(
            points=[
                RoutePoint(
                    time=base_time,
                    latitude=48.85,
                    longitude=2.35,
                    altitude=100.0,
                    speed=3.0,
                ),
                RoutePoint(
                    time=base_time + timedelta(seconds=10),
                    latitude=float("nan"),
                    longitude=2.3501,
                    altitude=101.0,
                    speed=3.2,
                ),
            ]
        )

        config = wdm._build_route_profile_chart_config([route])

        assert config["series"][0]["data"] == []

    def test_do_refresh_route_tab_uses_plain_route_polyline(self) -> None:
        """Route refresh should use a single plain polyline per route."""
        from logic.workout_manager.workout_route import RoutePoint, WorkoutRoute

        base_time = pd.Timestamp("2024-01-01").to_pydatetime()
        route = WorkoutRoute(
            points=[
                RoutePoint(
                    time=base_time + timedelta(seconds=i * 10),
                    latitude=48.85 + (i * 0.0001),
                    longitude=2.35 + (i * 0.0001),
                    altitude=35.0 + i,
                    speed=2.0 + (i * 2.0),
                )
                for i in range(3)
            ]
        )
        row = {"route": route}
        no_route_label = _DummyElement()
        route_map = _DummyElement()
        polyline_colors: list[str] = []
        tooltip_texts: list[str] = []

        def capture_layer(name: str, args: list[Any]) -> _DummyElement:
            if name == "polyline":
                polyline_colors.append(args[1]["color"])
            return _DummyElement()

        def capture_tooltip(_layer_id: str, method: str, text: str) -> _DummyElement:
            if method == "bindTooltip":
                tooltip_texts.append(text)
            return route_map

        def run_coroutine_sync(coro: Any) -> Any:
            return asyncio.run(coro)

        with (
            patch.object(route_map, "generic_layer", side_effect=capture_layer),
            patch.object(route_map, "run_layer_method", side_effect=capture_tooltip),
            patch(
                "ui.workout_detail_modal.background_tasks.create", side_effect=run_coroutine_sync
            ),
        ):
            wdm._do_refresh_route_tab(no_route_label, route_map, row)

        assert polyline_colors == ["#2563eb"]
        assert "Route 1" in tooltip_texts
