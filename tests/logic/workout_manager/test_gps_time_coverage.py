"""GPS time-coverage and distance-scaling regressions."""

import logging
from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from logic.workout_manager import WorkoutManager
from logic.workout_manager.workout_route import RoutePoint, WorkoutRoute


def _manager_with_route(
    route: WorkoutRoute, duration_s: float, distance_m: float
) -> WorkoutManager:
    return WorkoutManager(
        pd.DataFrame(
            {
                "activityType": ["Running"],
                "startDate": [pd.Timestamp("2025-01-01")],
                "duration": [duration_s],
                "distance": [distance_m],
                "route": [route],
            }
        )
    )


class TestGpsTimeCoverage:
    def test_internal_dropout_does_not_discount_included_route_distance(self) -> None:
        """A long interval's counted distance must not be discounted by its elapsed time."""
        start = datetime(2025, 1, 1, tzinfo=UTC)
        timestamps = [*range(901), *range(1100, 2001)]
        route = WorkoutRoute(
            points=[
                RoutePoint(
                    time=start + timedelta(seconds=timestamp_s),
                    latitude=0.0,
                    longitude=0.0,
                    speed=1.0,
                )
                for timestamp_s in timestamps
            ]
        )
        manager = _manager_with_route(route, duration_s=2000.0, distance_m=2400.0)

        result = manager.get_best_segments(topn=1, distances=[1000])

        assert route.distance_meters == pytest.approx(2000.0)
        coverage = WorkoutRoute.calculate_time_coverage([route], 2000.0)
        assert coverage == pytest.approx(1.0)
        assert float(result.iloc[0]["duration_s"]) == pytest.approx(1000 / 1.2, rel=0.02)
        scale = WorkoutRoute.calculate_distance_scale_factor(
            route.distance_meters, 2400.0, time_coverage=coverage
        )
        splits = route.compute_splits(distance_scale_factor=scale)
        assert splits[0]["duration_s"] == pytest.approx(1000 / 1.2, rel=0.02)

    def test_stationary_uncovered_tail_does_not_scale_an_accurate_trace(self) -> None:
        """A 50-second stationary tail does not make an accurate 1.9 km route shorter."""
        start = datetime(2025, 4, 17, 16, 57, 20, tzinfo=UTC)
        route = WorkoutRoute(
            points=[
                RoutePoint(
                    time=start + timedelta(seconds=i),
                    latitude=0.0,
                    longitude=i * 2 / 111_319.49,
                    altitude=0.0,
                    speed=2.0,
                )
                for i in range(951)
            ]
        )
        manager = _manager_with_route(route, duration_s=1000.0, distance_m=1900.0)

        result = manager.get_best_segments(topn=1, distances=[1000])

        assert float(result.iloc[0]["duration_s"]) == pytest.approx(500.0, rel=0.02)

    def test_rejection_warning_uses_coverage_adjusted_scale(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A raw ratio above 2.0 is accepted when coverage adjustment brings it below 2.0."""
        start = datetime(2025, 1, 1, tzinfo=UTC)
        gps_distance_m = WorkoutRoute.haversine_m(0.0, 0.0, 0.0, 0.01)
        route = WorkoutRoute(
            points=[
                RoutePoint(
                    time=start + timedelta(seconds=i),
                    latitude=0.0,
                    longitude=0.01 * i / 540,
                )
                for i in range(541)
            ]
        )
        manager = _manager_with_route(
            route,
            duration_s=600.0,
            distance_m=gps_distance_m * 2.1,
        )

        with caplog.at_level(logging.WARNING, logger="logic.workout_manager.segments"):
            manager.get_best_segments(topn=1, distances=[100])

        warning_messages = [record.message for record in caplog.records]
        assert any("GPS interruption correction applied" in msg for msg in warning_messages)
        assert not any("GPS distance scale factor rejected" in msg for msg in warning_messages)
