"""Tests for WorkoutManager.annotate_segments_with_power."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zipfile import ZipFile

import pandas as pd
import pytest

from logic.export_parser import ExportParser
from logic.workout_manager import WorkoutManager
from logic.workout_route import RoutePoint, WorkoutRoute
from tests.conftest import build_health_export_xml, load_export_fragment


class TestAnnotateSegmentsWithPower:
    """Test suite for WorkoutManager.annotate_segments_with_power."""

    @staticmethod
    def _make_route(start_time: datetime, duration_s: float) -> WorkoutRoute:
        # Use speed=0.0 so distance is computed via haversine (0.0→0.01 lon ≈ 1113 m)
        return WorkoutRoute(
            points=[
                RoutePoint(time=start_time, latitude=0.0, longitude=0.0, altitude=0.0, speed=0.0),
                RoutePoint(
                    time=start_time + timedelta(seconds=duration_s),
                    latitude=0.0,
                    longitude=0.01,
                    altitude=0.0,
                    speed=0.0,
                ),
            ]
        )

    @staticmethod
    def _record_df(timestamp: str, value: float) -> pd.DataFrame:
        return pd.DataFrame({"startDate": [timestamp], "value": [value]})

    @staticmethod
    def _record_interval_df(start_ts: str, end_ts: str, value: float) -> pd.DataFrame:
        return pd.DataFrame({"startDate": [start_ts], "endDate": [end_ts], "value": [value]})

    def _make_manager(
        self, duration_s: float, workout_duration_s: float, avg_power: float | None = None
    ) -> WorkoutManager:
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        cols: dict[str, Any] = {
            "activityType": ["Running"],
            "startDate": [pd.Timestamp("2025-01-01")],
            "distance": [5000.0],
            "duration": [workout_duration_s],
            "route": [self._make_route(start, duration_s)],
        }
        if avg_power is not None:
            cols["averageRunningPower"] = [avg_power]
        return WorkoutManager(pd.DataFrame(cols))

    def test_individual_records_used_when_within_window(self) -> None:
        """Power record inside the segment window should be used as avg_power."""
        manager = self._make_manager(duration_s=160.0, workout_duration_s=3600.0)
        # Record at +80 s (middle of 0–160 s window)
        rp_df = self._record_df("2025-01-01T00:01:20+00:00", 320.0)
        segments = manager.get_best_segments(topn=1, distances=[1000])

        result = manager.annotate_segments_with_power(segments, rp_df)

        assert "segment_avg_power" in result.columns
        assert "segment_power_confidence" in result.columns
        assert result["segment_avg_power"].iloc[0] == pytest.approx(320.0)  # type: ignore[misc]
        assert result["segment_power_confidence"].iloc[0] == "measured"

    def test_record_outside_window_yields_none(self) -> None:
        """Power record entirely outside the segment window should not be used."""
        manager = self._make_manager(duration_s=160.0, workout_duration_s=3600.0)
        # Record 10 minutes after the window ends
        rp_df = self._record_df("2025-01-01T00:30:00+00:00", 320.0)
        segments = manager.get_best_segments(topn=1, distances=[1000])

        result = manager.annotate_segments_with_power(segments, rp_df)

        assert result["segment_avg_power"].iloc[0] is None
        assert result["segment_power_confidence"].iloc[0] == "missing"

    def test_uses_overlap_estimate_when_no_startdate_match(self) -> None:
        """Interval overlap should estimate segment power when no startDate lies inside window."""
        manager = self._make_manager(duration_s=160.0, workout_duration_s=3600.0)
        segments = manager.get_best_segments(topn=1, distances=[1000])

        seg_start = pd.Timestamp(segments["segment_start"].iloc[0])
        # Starts just before segment start, ends inside segment: no measured match,
        # but should be captured by overlap estimation.
        rp_df = self._record_interval_df(
            (seg_start - pd.Timedelta(seconds=5)).isoformat(),
            (seg_start + pd.Timedelta(seconds=20)).isoformat(),
            300.0,
        )

        result = manager.annotate_segments_with_power(segments, rp_df)

        assert result["segment_avg_power"].iloc[0] == pytest.approx(300.0)  # type: ignore[misc]
        assert result["segment_power_confidence"].iloc[0] == "overlap_estimated"

    def test_falls_back_to_workout_stats_when_durations_close(self) -> None:
        """Workout avg power should be used when workout duration ≈ segment duration."""
        # Segment ≈ 160 s, workout = 162 s (within 10 %)
        manager = self._make_manager(duration_s=160.0, workout_duration_s=162.0, avg_power=280.0)
        segments = manager.get_best_segments(topn=1, distances=[1000])

        result = manager.annotate_segments_with_power(segments, None)

        assert result["segment_avg_power"].iloc[0] == pytest.approx(280.0)  # type: ignore[misc]
        assert result["segment_power_confidence"].iloc[0] == "workout_fallback"

    def test_falls_back_to_workout_stats_when_no_segment_match(self) -> None:
        """Workout avg power should be used as third-priority fallback."""
        # Segment ≈ 160 s, workout = 3600 s (still fallback when no better source)
        manager = self._make_manager(duration_s=160.0, workout_duration_s=3600.0, avg_power=280.0)
        segments = manager.get_best_segments(topn=1, distances=[1000])

        result = manager.annotate_segments_with_power(segments, None)

        assert result["segment_avg_power"].iloc[0] == pytest.approx(280.0)  # type: ignore[misc]
        assert result["segment_power_confidence"].iloc[0] == "workout_fallback"

    def test_individual_records_take_priority_over_workout_stats(self) -> None:
        """Individual records should override workout-level avg power."""
        # Workout duration close to segment (would allow fallback), but individual record exists
        manager = self._make_manager(duration_s=160.0, workout_duration_s=162.0, avg_power=200.0)
        rp_df = self._record_df("2025-01-01T00:01:20+00:00", 350.0)
        segments = manager.get_best_segments(topn=1, distances=[1000])

        result = manager.annotate_segments_with_power(segments, rp_df)

        assert result["segment_avg_power"].iloc[0] == pytest.approx(350.0)  # type: ignore[misc]
        assert result["segment_power_confidence"].iloc[0] == "measured"

    def test_empty_segments_returns_empty_with_column(self) -> None:
        """Empty segments DataFrame should return empty with segment_avg_power column."""
        manager = WorkoutManager()
        segments = manager.get_best_segments(topn=1, distances=[1000])

        result = manager.annotate_segments_with_power(segments, None)

        assert result.empty
        assert "segment_avg_power" in result.columns
        assert "segment_power_confidence" in result.columns

    def test_real_fixture_2024_12_26_uses_overlap_estimated_power(self, tmp_path: Path) -> None:
        """Real 2024-12-26 run should compute segment power from overlapping intervals."""
        workout_xml = load_export_fragment("workout_running_too_fast.xml")
        power_xml = load_export_fragment("record_running_power.xml")
        route_dir = Path(__file__).resolve().parents[1] / "fixtures" / "exports" / "workout-routes"
        route_files = sorted(route_dir.glob("route_2024-12-26_*.gpx"))

        zip_path = tmp_path / "running_too_fast_with_power.zip"
        with ZipFile(zip_path, "w") as zf:
            zf.writestr(
                "apple_health_export/export.xml",
                build_health_export_xml([workout_xml, power_xml]),
            )
            for route_file in route_files:
                zf.writestr(
                    f"apple_health_export/workout-routes/{route_file.name}",
                    route_file.read_bytes(),
                )

        parser = ExportParser()
        with parser:
            parsed = parser.parse(str(zip_path))

        manager = WorkoutManager(parsed.workouts)
        segments = manager.get_best_segments(topn=1, distances=[100])
        rp_df = parsed.records_by_type.get("RunningPower")
        annotated = manager.annotate_segments_with_power(segments, rp_df)

        assert len(annotated) == 1
        assert annotated["segment_avg_power"].notna().iloc[0]
        assert annotated["segment_power_confidence"].iloc[0] == "overlap_estimated"
