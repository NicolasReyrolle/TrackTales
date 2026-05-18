"""Tests for WorkoutManager.get_critical_power and get_critical_power_evolution."""

from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd
import pytest

from logic.workout_manager import WorkoutManager
from logic.workout_manager.workout_route import RoutePoint, WorkoutRoute


class TestGetCriticalPower:
    """Test suite for WorkoutManager.get_critical_power."""

    @staticmethod
    def _make_route(
        start_time: datetime, distance_m: float, duration_s: float, end_lon: float
    ) -> WorkoutRoute:
        speed = distance_m / duration_s
        return WorkoutRoute(
            points=[
                RoutePoint(time=start_time, latitude=0.0, longitude=0.0, altitude=0.0, speed=speed),
                RoutePoint(
                    time=start_time + timedelta(seconds=duration_s),
                    latitude=0.0,
                    longitude=end_lon,
                    altitude=0.0,
                    speed=speed,
                ),
            ]
        )

    @staticmethod
    def _rp_df(start_time: datetime, duration_s: float, power_w: float) -> pd.DataFrame:
        """RunningPower record placed in the middle of the segment window."""
        mid = start_time + timedelta(seconds=duration_s / 2)
        return pd.DataFrame(
            {"startDate": [mid.strftime("%Y-%m-%dT%H:%M:%S+00:00")], "value": [power_w]}
        )

    def test_returns_none_for_empty_manager(self) -> None:
        """No workouts should return None."""
        assert WorkoutManager().get_critical_power() is None

    def test_returns_none_when_no_power_data(self) -> None:
        """Return None when neither individual records nor workout stats are available."""
        t800 = datetime(2025, 1, 1, tzinfo=timezone.utc)
        t5000 = datetime(2025, 2, 1, tzinfo=timezone.utc)
        manager = WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running"],
                    "startDate": [pd.Timestamp("2025-01-01"), pd.Timestamp("2025-02-01")],
                    "distance": [800.0, 5000.0],
                    "route": [
                        self._make_route(t800, 800.0, 160.0, 0.007),
                        self._make_route(t5000, 5000.0, 1250.0, 0.045),
                    ],
                }
            )
        )

        assert manager.get_critical_power() is None

    def test_returns_none_when_short_distance_missing(self) -> None:
        """Return None when no best segment exists for the short distance."""
        t = datetime(2025, 1, 1, tzinfo=timezone.utc)
        route = self._make_route(t, 5000.0, 1500.0, 0.045)
        rp_df = self._rp_df(t, 1500.0, 250.0)
        manager = WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "startDate": [pd.Timestamp("2025-01-01")],
                    "distance": [5000.0],
                    "route": [route],
                }
            )
        )

        assert (
            manager.get_critical_power(
                running_power_df=rp_df, short_distance=10000, long_distance=50000
            )
            is None
        )

    def test_returns_none_when_short_ge_long(self) -> None:
        """Return None for degenerate distance inputs."""
        manager = WorkoutManager()
        assert manager.get_critical_power(short_distance=800, long_distance=800) is None
        assert manager.get_critical_power(short_distance=5000, long_distance=800) is None

    def test_critical_power_formula_with_individual_records(self) -> None:
        """CP and W' computed from individual RunningPower records within segment windows."""
        time_800 = 160
        power_800 = 350.0
        time_5000 = 1250
        power_5000 = 250.0
        t800 = datetime(2025, 1, 1, tzinfo=timezone.utc)
        t5000 = datetime(2025, 2, 1, tzinfo=timezone.utc)

        manager = WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running"],
                    "startDate": [pd.Timestamp("2025-01-01"), pd.Timestamp("2025-02-01")],
                    "distance": [800.0, 5000.0],
                    "route": [
                        self._make_route(t800, 800.0, float(time_800), 0.007),
                        self._make_route(t5000, 5000.0, float(time_5000), 0.045),
                    ],
                }
            )
        )

        # Build a combined RunningPower records DataFrame with one record per segment
        rp_df = pd.concat(
            [
                self._rp_df(t800, float(time_800), power_800),
                self._rp_df(t5000, float(time_5000), power_5000),
            ],
            ignore_index=True,
        )

        result = manager.get_critical_power(
            running_power_df=rp_df, topn=1, short_distance=800, long_distance=5000
        )

        assert result is not None
        assert result["short_distance"] == 800
        assert result["long_distance"] == 5000
        assert result["avg_time_short_s"] == pytest.approx(time_800)  # type: ignore[misc]
        assert result["avg_time_long_s"] == pytest.approx(time_5000)  # type: ignore[misc]
        assert result["avg_power_short_w"] == pytest.approx(power_800)  # type: ignore[misc]
        assert result["avg_power_long_w"] == pytest.approx(power_5000)  # type: ignore[misc]
        work_short = power_800 * time_800
        work_long = power_5000 * time_5000
        expected_cp = (work_long - work_short) / (time_5000 - time_800)
        expected_w_prime = work_short - expected_cp * time_800
        assert result["critical_power_w"] == pytest.approx(expected_cp)  # type: ignore[misc]
        assert result["w_prime_j"] == pytest.approx(expected_w_prime)  # type: ignore[misc]
        assert result["count_short"] == 1
        assert result["count_long"] == 1

    def test_fallback_to_workout_stats_when_workout_is_the_segment(self) -> None:
        """Workout-level avg power is used when workout duration ≈ segment duration."""
        time_800 = 160
        time_5000 = 1250
        t800 = datetime(2025, 1, 1, tzinfo=timezone.utc)
        t5000 = datetime(2025, 2, 1, tzinfo=timezone.utc)

        manager = WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running"],
                    "startDate": [pd.Timestamp("2025-01-01"), pd.Timestamp("2025-02-01")],
                    "distance": [800.0, 5000.0],
                    # duration ≈ segment duration (within 10%)
                    "duration": [float(time_800), float(time_5000)],
                    "averageRunningPower": [350.0, 250.0],
                    "route": [
                        self._make_route(t800, 800.0, float(time_800), 0.007),
                        self._make_route(t5000, 5000.0, float(time_5000), 0.045),
                    ],
                }
            )
        )

        # No individual records, but workout duration ≈ segment → fallback applies
        result = manager.get_critical_power(
            running_power_df=None, topn=1, short_distance=800, long_distance=5000
        )

        assert result is not None
        assert result["avg_power_short_w"] == pytest.approx(350.0, rel=0.01)  # type: ignore[misc]
        assert result["avg_power_long_w"] == pytest.approx(250.0, rel=0.01)  # type: ignore[misc]

    def test_critical_power_uses_average_work_not_product_of_means(self) -> None:
        """Average work should be computed from per-segment work to avoid false invalid W'."""
        month = datetime(2026, 4, 1, tzinfo=timezone.utc)
        short_data = [
            (198.3270856480831, 370.7915258375548),
            (161.7296540939797, 278.27940586367725),
            (170.57335750270062, 255.26954656462945),
            (178.77726829668626, 334.006848846674),
            (157.12712767559637, 271.50544091913963),
        ]
        long_data = [
            (1770.2654643940498, 307.38580179348514),
            (1304.4328938134136, 300.8841198524406),
            (1438.573924535698, 281.9585778958942),
            (1579.2464357580236, 308.68479554994934),
            (1630.0284825070953, 313.000637214952),
        ]

        rows: list[dict[str, Any]] = []
        rp_dfs: list[pd.DataFrame] = []
        for idx, (duration_s, power_w) in enumerate(short_data):
            start = month + timedelta(days=idx)
            rows.append(
                {
                    "activityType": "Running",
                    "startDate": pd.Timestamp(start),
                    "distance": 800.0,
                    "route": self._make_route(start, 800.0, duration_s, 0.007),
                }
            )
            rp_dfs.append(self._rp_df(start, duration_s, power_w))
        for idx, (duration_s, power_w) in enumerate(long_data):
            start = month + timedelta(days=10 + idx)
            rows.append(
                {
                    "activityType": "Running",
                    "startDate": pd.Timestamp(start),
                    "distance": 5000.0,
                    "route": self._make_route(start, 5000.0, duration_s, 0.045),
                }
            )
            rp_dfs.append(self._rp_df(start, duration_s, power_w))

        manager = WorkoutManager(pd.DataFrame(rows))
        rp_df = pd.concat(rp_dfs, ignore_index=True)

        result = manager.get_critical_power(
            running_power_df=rp_df, topn=5, short_distance=800, long_distance=5000
        )

        assert result is not None
        avg_time_short = sum(duration for duration, _ in short_data) / len(short_data)
        avg_time_long = sum(duration for duration, _ in long_data) / len(long_data)
        avg_work_short = sum(duration * power for duration, power in short_data) / len(short_data)
        avg_work_long = sum(duration * power for duration, power in long_data) / len(long_data)
        expected_cp = (avg_work_long - avg_work_short) / (avg_time_long - avg_time_short)
        expected_w_prime = avg_work_short - expected_cp * avg_time_short

        assert result["critical_power_w"] == pytest.approx(expected_cp)  # type: ignore[misc]
        assert result["w_prime_j"] == pytest.approx(expected_w_prime)  # type: ignore[misc]
        assert result["w_prime_j"] > 0  # type: ignore[operator]

    def test_critical_power_uses_1500_and_3000_when_available(self) -> None:
        """Robust fit should include intermediate distances when they exist."""
        specs = [
            (800.0, 160.0, 345.0, 0.007),
            (1500.0, 300.0, 320.0, 0.014),
            (3000.0, 700.0, 280.0, 0.027),
            (5000.0, 1300.0, 255.0, 0.045),
        ]
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)

        rows: list[dict[str, Any]] = []
        rp_dfs: list[pd.DataFrame] = []
        for index, (distance_m, duration_s, power_w, lon) in enumerate(specs):
            workout_start = start + timedelta(days=index)
            rows.append(
                {
                    "activityType": "Running",
                    "startDate": pd.Timestamp(workout_start),
                    "distance": distance_m,
                    "route": self._make_route(workout_start, distance_m, duration_s, lon),
                }
            )
            rp_dfs.append(self._rp_df(workout_start, duration_s, power_w))

        manager = WorkoutManager(pd.DataFrame(rows))
        rp_df = pd.concat(rp_dfs, ignore_index=True)

        result = manager.get_critical_power(running_power_df=rp_df, topn=1)

        assert result is not None
        work_800 = 160.0 * 345.0
        work_5000 = 1300.0 * 255.0
        cp_two_point = (work_5000 - work_800) / (1300.0 - 160.0)
        # Robust fitting with intermediate distances should not collapse to the
        # strict two-point estimate.
        assert abs(float(result["critical_power_w"]) - cp_two_point) > 1.0

    def test_critical_power_robust_fit_rejects_single_outlier_distance(self) -> None:
        """RANSAC-like fit should down-weight a rogue distance point."""
        specs = [
            (800.0, 160.0, 342.0, 0.007),
            (1500.0, 300.0, 320.0, 0.014),
            # Intentional outlier: unrealistically low power for this duration.
            (3000.0, 700.0, 120.0, 0.027),
            (5000.0, 1300.0, 255.0, 0.045),
        ]
        start = datetime(2025, 2, 1, tzinfo=timezone.utc)

        rows: list[dict[str, Any]] = []
        rp_dfs: list[pd.DataFrame] = []
        for index, (distance_m, duration_s, power_w, lon) in enumerate(specs):
            workout_start = start + timedelta(days=index)
            rows.append(
                {
                    "activityType": "Running",
                    "startDate": pd.Timestamp(workout_start),
                    "distance": distance_m,
                    "route": self._make_route(workout_start, distance_m, duration_s, lon),
                }
            )
            rp_dfs.append(self._rp_df(workout_start, duration_s, power_w))

        manager = WorkoutManager(pd.DataFrame(rows))
        rp_df = pd.concat(rp_dfs, ignore_index=True)

        result = manager.get_critical_power(running_power_df=rp_df, topn=1)

        assert result is not None
        # Without robust rejection this setup collapses CP toward ~170W. The
        # inlier set (800/1500/5000) keeps CP in a realistic range.
        assert result["critical_power_w"] > 220.0  # type: ignore[operator]

    def test_critical_power_skips_missing_intermediate_distances(self) -> None:
        """Missing 1500/3000 rows should be skipped while keeping a valid CP from anchors."""
        t800 = datetime(2025, 3, 1, tzinfo=timezone.utc)
        t5000 = datetime(2025, 3, 2, tzinfo=timezone.utc)
        manager = WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running"],
                    "startDate": [pd.Timestamp(t800), pd.Timestamp(t5000)],
                    "distance": [800.0, 5000.0],
                    "route": [
                        self._make_route(t800, 800.0, 160.0, 0.007),
                        self._make_route(t5000, 5000.0, 1200.0, 0.045),
                    ],
                }
            )
        )
        rp_df = pd.concat(
            [
                self._rp_df(t800, 160.0, 350.0),
                self._rp_df(t5000, 1200.0, 260.0),
            ],
            ignore_index=True,
        )

        result = manager.get_critical_power(running_power_df=rp_df, topn=1)

        assert result is not None
        assert result["short_distance"] == 800
        assert result["long_distance"] == 5000

    def test_critical_power_logs_warning_for_non_physical_w_prime(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Non-physical W' should be rejected and logged as a warning."""
        t800 = datetime(2025, 4, 1, tzinfo=timezone.utc)
        t5000 = datetime(2025, 4, 2, tzinfo=timezone.utc)
        manager = WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Running"],
                    "startDate": [pd.Timestamp(t800), pd.Timestamp(t5000)],
                    "distance": [800.0, 5000.0],
                    "route": [
                        self._make_route(t800, 800.0, 200.0, 0.007),
                        self._make_route(t5000, 5000.0, 1000.0, 0.045),
                    ],
                }
            )
        )
        rp_df = pd.concat(
            [
                self._rp_df(t800, 200.0, 200.0),
                self._rp_df(t5000, 1000.0, 300.0),
            ],
            ignore_index=True,
        )

        with caplog.at_level("WARNING"):
            result = manager.get_critical_power(running_power_df=rp_df, topn=1)

        assert result is None
        assert "Non-physical W' detected" in caplog.text

    def test_critical_power_continues_when_additional_distances_have_no_segments(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Distances requested only as additional inputs can be absent and must be skipped."""
        manager = WorkoutManager(pd.DataFrame())
        stub_segments = pd.DataFrame(
            {
                "distance": [100, 200],
                "duration_s": [30.0, 60.0],
                "segment_avg_power": [320.0, 320.0],
            }
        )

        monkeypatch.setattr(manager, "get_best_segments", lambda **_kwargs: stub_segments.copy())
        monkeypatch.setattr(
            manager,
            "annotate_segments_with_power",
            lambda segments, _running_power_df: segments,
        )

        result = manager.get_critical_power(
            running_power_df=None,
            topn=1,
            short_distance=100,
            long_distance=200,
        )

        assert result is not None
        assert result["short_distance"] == 100
        assert result["long_distance"] == 200

    def test_critical_power_returns_none_when_distance_points_drop_below_two(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Defensive path: return None if distance points collapse below two."""

        class StatefulSegmentsFrame(pd.DataFrame):
            _mask_calls = 0

            @property
            def _constructor(self):  # type: ignore[override]
                return StatefulSegmentsFrame

            def __getitem__(self, key):  # type: ignore[override]
                if isinstance(key, pd.Series) and key.dtype == bool:
                    StatefulSegmentsFrame._mask_calls += 1
                    if StatefulSegmentsFrame._mask_calls <= 2:
                        return super().__getitem__(key)
                    return self.iloc[0:0].copy()
                return super().__getitem__(key)

        manager = WorkoutManager(pd.DataFrame())
        base = pd.DataFrame(
            {
                "distance": [100, 200],
                "duration_s": [30.0, 60.0],
                "segment_avg_power": [320.0, 320.0],
            }
        )
        stateful_segments = StatefulSegmentsFrame(base)

        monkeypatch.setattr(
            manager,
            "get_best_segments",
            lambda **_kwargs: StatefulSegmentsFrame(stateful_segments.copy()),
        )
        monkeypatch.setattr(
            manager,
            "annotate_segments_with_power",
            lambda segments, _running_power_df: segments,
        )

        result = manager.get_critical_power(
            running_power_df=None,
            topn=1,
            short_distance=100,
            long_distance=200,
        )

        assert result is None


class TestSegmentsHelperCoverage:
    """Branch-level coverage tests for segments helper methods."""

    @staticmethod
    def _make_route(start_time: datetime, distance_m: float, duration_s: float) -> WorkoutRoute:
        speed = distance_m / duration_s
        return WorkoutRoute(
            points=[
                RoutePoint(time=start_time, latitude=0.0, longitude=0.0, altitude=0.0, speed=speed),
                RoutePoint(
                    time=start_time + timedelta(seconds=duration_s),
                    latitude=0.0,
                    longitude=0.01,
                    altitude=0.0,
                    speed=speed,
                ),
            ]
        )

    def test_evaluate_ransac_candidate_returns_none_when_threshold_excludes_all(self) -> None:
        result = WorkoutManager._evaluate_ransac_candidate(
            times_s=[100.0, 200.0, 300.0],
            works_j=[20000.0, 40000.0, 60000.0],
            index_a=0,
            index_b=1,
            residual_threshold_j=-1.0,
        )
        assert result is None

    def test_log_dropped_outlier_points_uses_fallback_labels_when_mismatch(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level("INFO"):
            WorkoutManager._log_dropped_outlier_points(
                total_points=4,
                inlier_indexes=[0, 2],
                point_labels=["only_one_label"],
            )
        assert "point_1" in caplog.text
        assert "point_3" in caplog.text

    def test_fit_work_time_line_returns_none_for_invalid_lengths(self) -> None:
        assert WorkoutManager._fit_work_time_line([100.0], [20000.0]) is None
        assert WorkoutManager._fit_work_time_line([100.0, 200.0], [20000.0]) is None

    def test_fit_work_time_line_ransac_like_handles_edge_input_shapes(self) -> None:
        assert WorkoutManager._fit_work_time_line_ransac_like([100.0], [20000.0]) is None

        two_point = WorkoutManager._fit_work_time_line_ransac_like(
            [100.0, 200.0],
            [20000.0, 45000.0],
        )
        direct_two_point = WorkoutManager._fit_work_time_line(
            [100.0, 200.0],
            [20000.0, 45000.0],
        )
        assert two_point == direct_two_point

    def test_fit_work_time_line_ransac_like_falls_back_when_no_candidate_survives(self) -> None:
        # All time points identical => any two-point OLS fit is undefined.
        result = WorkoutManager._fit_work_time_line_ransac_like(
            [100.0, 100.0, 100.0],
            [20000.0, 25000.0, 30000.0],
        )
        assert result is None

    def test_build_best_segments_frame_returns_empty_schema_for_no_results(self) -> None:
        frame = WorkoutManager._build_best_segments_frame([], topn=5)
        assert frame.empty
        assert list(frame.columns) == [
            "startDate",
            "distance",
            "duration_s",
            "segment_start",
            "segment_end",
            "elevation_change_m",
        ]

    def test_get_run_distance_m_returns_none_for_missing_or_nan(self) -> None:
        row_none = type("RunRecord", (), {"distance": None})()
        row_nan = type("RunRecord", (), {"distance": float("nan")})()

        assert WorkoutManager._get_run_distance_m(row_none) is None
        assert WorkoutManager._get_run_distance_m(row_nan) is None

    def test_extract_route_traces_prefers_valid_route_parts(self) -> None:
        route = self._make_route(datetime(2025, 1, 1, tzinfo=timezone.utc), 800.0, 160.0)
        run_record = type(
            "RunRecord",
            (),
            {"route_parts": ["invalid", route], "route": None},
        )()

        traces = WorkoutManager._extract_route_traces(run_record)
        assert len(traces) == 1
        assert traces[0].points == route.points

    def test_fallback_filter_running_workouts_filters_running_and_end_timestamp(self) -> None:
        manager = WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running", "Cycling", "Running"],
                    "startDate": [
                        pd.Timestamp("2025-01-01T10:00:00"),
                        pd.Timestamp("2025-01-01T12:00:00"),
                        pd.Timestamp("2025-01-02T10:00:00"),
                    ],
                }
            )
        )
        filtered = manager._fallback_filter_running_workouts(
            start_date=pd.Timestamp("2025-01-01T00:00:00"),
            end_date=pd.Timestamp("2025-01-01T23:59:59"),
        )

        assert len(filtered) == 1
        assert filtered.iloc[0]["activityType"] == "Running"

    def test_get_best_segments_uses_default_distances_when_none(self) -> None:
        manager = WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Cycling"],
                    "startDate": [pd.Timestamp("2025-01-01")],
                }
            )
        )

        result = manager.get_best_segments(topn=5)
        assert result.empty


class TestGetCriticalPowerEvolution:
    """Test suite for WorkoutManager.get_critical_power_evolution."""

    @staticmethod
    def _make_route(
        start_time: datetime, distance_m: float, duration_s: float, end_lon: float
    ) -> WorkoutRoute:
        speed = distance_m / duration_s
        return WorkoutRoute(
            points=[
                RoutePoint(time=start_time, latitude=0.0, longitude=0.0, altitude=0.0, speed=speed),
                RoutePoint(
                    time=start_time + timedelta(seconds=duration_s),
                    latitude=0.0,
                    longitude=end_lon,
                    altitude=0.0,
                    speed=speed,
                ),
            ]
        )

    @staticmethod
    def _rp_record(start_time: datetime, duration_s: float, power_w: float) -> dict[str, Any]:
        mid = start_time + timedelta(seconds=duration_s / 2)
        return {"startDate": mid.strftime("%Y-%m-%dT%H:%M:%S+00:00"), "value": power_w}

    def test_returns_empty_for_empty_manager(self) -> None:
        """No workouts returns an empty DataFrame with expected columns."""
        result = WorkoutManager().get_critical_power_evolution()
        assert result.empty
        assert list(result.columns) == ["period", "critical_power_w", "w_prime_kj"]

    def test_returns_empty_when_no_power_data(self) -> None:
        """Periods with insufficient data to compute CP produce no output rows."""
        t = datetime(2025, 1, 1, tzinfo=timezone.utc)
        route = self._make_route(t, 800.0, 160.0, 0.007)
        manager = WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "startDate": [pd.Timestamp("2025-01-01")],
                    "distance": [800.0],
                    "route": [route],
                }
            )
        )

        result = manager.get_critical_power_evolution()
        assert result.empty
        assert list(result.columns) == ["period", "critical_power_w", "w_prime_kj"]

    def test_evolution_groups_by_period(self) -> None:
        """Each calendar period with both distances produces one CP/W' row."""
        data = [
            (datetime(2025, 1, 5, tzinfo=timezone.utc), 800.0, 160.0, 0.007, 350.0),
            (datetime(2025, 1, 20, tzinfo=timezone.utc), 5000.0, 1250.0, 0.045, 250.0),
            (datetime(2025, 2, 5, tzinfo=timezone.utc), 800.0, 155.0, 0.007, 360.0),
            (datetime(2025, 2, 20, tzinfo=timezone.utc), 5000.0, 1200.0, 0.045, 260.0),
        ]
        manager = WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"] * 4,
                    "startDate": [pd.Timestamp(dt) for dt, *_ in data],
                    "distance": [d for _, d, *_ in data],
                    "route": [
                        self._make_route(dt, dist, dur, lon) for dt, dist, dur, lon, _ in data
                    ],
                }
            )
        )
        rp_df = pd.DataFrame([self._rp_record(dt, dur, pwr) for dt, _, dur, _, pwr in data])

        result = manager.get_critical_power_evolution(running_power_df=rp_df, period="M")

        assert len(result) == 2
        assert list(result.columns) == ["period", "critical_power_w", "w_prime_kj"]
        assert all(result["critical_power_w"] > 0)
        assert all(result["w_prime_kj"] > 0)

    def test_period_with_only_one_distance_is_skipped(self) -> None:
        """A period with only one distance produces no output row (CP requires both distances)."""
        t = datetime(2025, 1, 1, tzinfo=timezone.utc)
        manager = WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"],
                    "startDate": [pd.Timestamp("2025-01-01")],
                    "distance": [800.0],
                    "route": [self._make_route(t, 800.0, 160.0, 0.007)],
                }
            )
        )
        rp_df = pd.DataFrame([self._rp_record(t, 160.0, 350.0)])

        result = manager.get_critical_power_evolution(running_power_df=rp_df, period="M")
        assert result.empty
        assert list(result.columns) == ["period", "critical_power_w", "w_prime_kj"]

    def test_evolution_uses_topn_within_each_period(self) -> None:
        """topn should be applied independently per period, not globally before grouping."""
        data = [
            # January
            (datetime(2025, 1, 5, tzinfo=timezone.utc), 800.0, 170.0, 0.007, 300.0),
            (datetime(2025, 1, 20, tzinfo=timezone.utc), 5000.0, 1300.0, 0.045, 220.0),
            # February (globally faster for both distances)
            (datetime(2025, 2, 5, tzinfo=timezone.utc), 800.0, 160.0, 0.007, 350.0),
            (datetime(2025, 2, 20, tzinfo=timezone.utc), 5000.0, 1200.0, 0.045, 260.0),
        ]
        manager = WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"] * 4,
                    "startDate": [pd.Timestamp(dt) for dt, *_ in data],
                    "distance": [distance for _, distance, *_ in data],
                    "route": [
                        self._make_route(dt, distance, duration, lon)
                        for dt, distance, duration, lon, _ in data
                    ],
                }
            )
        )
        rp_df = pd.DataFrame(
            [self._rp_record(dt, duration, power) for dt, _, duration, _, power in data]
        )

        result = manager.get_critical_power_evolution(running_power_df=rp_df, period="M", topn=1)

        assert len(result) == 2
        assert list(result["period"]) == ["2025-01", "2025-02"]
        assert all(result["critical_power_w"] > 0)
        assert all(result["w_prime_kj"] > 0)

    def test_interior_gap_period_kept_as_none(self) -> None:
        """A month between two valid CP months appears as None (chart gap), not dropped.

        September and November have both 800m and 5000m segments with power → valid CP.
        October has NO workouts at all. The result must still include all three months,
        with October as a None gap so the chart x-axis is contiguous.
        """
        data = [
            # September: 800m and 5000m → valid CP
            (datetime(2025, 9, 5, tzinfo=timezone.utc), 800.0, 160.0, 0.007, 350.0),
            (datetime(2025, 9, 20, tzinfo=timezone.utc), 5000.0, 1250.0, 0.045, 250.0),
            # October: intentionally absent — simulates a month with zero workouts
            # November: 800m and 5000m → valid CP
            (datetime(2025, 11, 5, tzinfo=timezone.utc), 800.0, 158.0, 0.007, 355.0),
            (datetime(2025, 11, 25, tzinfo=timezone.utc), 5000.0, 1200.0, 0.045, 255.0),
        ]
        manager = WorkoutManager(
            pd.DataFrame(
                {
                    "activityType": ["Running"] * 4,
                    "startDate": [pd.Timestamp(dt) for dt, *_ in data],
                    "distance": [d for _, d, *_ in data],
                    "route": [
                        self._make_route(dt, dist, dur, lon) for dt, dist, dur, lon, _ in data
                    ],
                }
            )
        )
        rp_df = pd.DataFrame([self._rp_record(dt, dur, pwr) for dt, _, dur, _, pwr in data])

        result = manager.get_critical_power_evolution(running_power_df=rp_df, period="M")

        assert len(result) == 3
        assert list(result["period"]) == ["2025-09", "2025-10", "2025-11"]
        # September: valid CP
        assert result.iloc[0]["critical_power_w"] is not None
        assert result.iloc[0]["w_prime_kj"] is not None
        # October: gap — no workouts at all in this month
        assert pd.isna(result.iloc[1]["critical_power_w"])
        assert pd.isna(result.iloc[1]["w_prime_kj"])
        # November: valid CP
        assert result.iloc[2]["critical_power_w"] is not None
        assert result.iloc[2]["w_prime_kj"] is not None

    def test_month_with_valid_segments_is_not_dropped_due_to_work_averaging(self) -> None:
        """A month with valid 800m/5000m power data should produce CP/W' values."""
        month = datetime(2026, 4, 1, tzinfo=timezone.utc)
        short_data = [
            (198.3270856480831, 370.7915258375548),
            (161.7296540939797, 278.27940586367725),
            (170.57335750270062, 255.26954656462945),
            (178.77726829668626, 334.006848846674),
            (157.12712767559637, 271.50544091913963),
        ]
        long_data = [
            (1770.2654643940498, 307.38580179348514),
            (1304.4328938134136, 300.8841198524406),
            (1438.573924535698, 281.9585778958942),
            (1579.2464357580236, 308.68479554994934),
            (1630.0284825070953, 313.000637214952),
        ]

        rows: list[dict[str, Any]] = []
        rp_records: list[dict[str, Any]] = []
        for idx, (duration_s, power_w) in enumerate(short_data):
            start = month + timedelta(days=idx)
            rows.append(
                {
                    "activityType": "Running",
                    "startDate": pd.Timestamp(start),
                    "distance": 800.0,
                    "route": self._make_route(start, 800.0, duration_s, 0.007),
                }
            )
            rp_records.append(self._rp_record(start, duration_s, power_w))
        for idx, (duration_s, power_w) in enumerate(long_data):
            start = month + timedelta(days=10 + idx)
            rows.append(
                {
                    "activityType": "Running",
                    "startDate": pd.Timestamp(start),
                    "distance": 5000.0,
                    "route": self._make_route(start, 5000.0, duration_s, 0.045),
                }
            )
            rp_records.append(self._rp_record(start, duration_s, power_w))

        manager = WorkoutManager(pd.DataFrame(rows))
        rp_df = pd.DataFrame(rp_records)

        result = manager.get_critical_power_evolution(running_power_df=rp_df, period="M", topn=5)

        assert list(result["period"]) == ["2026-04"]
        assert result.iloc[0]["critical_power_w"] is not None
        assert result.iloc[0]["w_prime_kj"] is not None
