"""WorkoutRoute represents a sequence of GPS points recorded during a workout,
allowing for calculations of distance, elevation gain/loss, and duration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from math import atan2, cos, isclose, radians, sin, sqrt
from statistics import median

import pandas as pd

from logic.constants import (
    ALTITUDE_ZERO_TOLERANCE_M,
    ELEVATION_NOISE_THRESHOLD_M,
    ELEVATION_SMOOTHING_WINDOW,
)


@dataclass(frozen=True)
class RoutePoint:
    """Represents a single GPS point in a workout route."""

    time: datetime
    latitude: float
    longitude: float
    altitude: float = 0.0
    speed: float = 0.0  # GPS-measured speed in m/s; 0.0 means unknown/unavailable
    heart_rate: float | None = None
    altitude_available: bool = True


@dataclass
class WorkoutRoute:
    """Represents a workout route as a sequence of GPS points."""

    # Maximum allowed relative deviation between route-derived distance and workout
    # summary distance for normalization to be considered realistic.
    #
    # Example with default 0.10 (10%):
    # - route=20.8km vs workout=21.1km -> scaling applied
    # - route=15.0km vs workout=21.1km -> scaling rejected
    MAX_REALISTIC_DISTANCE_SCALE_DEVIATION = 0.10

    points: list[RoutePoint]
    _cumulative_distance_cache: list[float] | None = field(default=None, init=False, repr=False)
    _sorted_times_cache: list[datetime] | None = field(default=None, init=False, repr=False)

    @property
    def is_empty(self) -> bool:
        """Check if the workout route has no points."""
        return len(self.points) == 0

    @property
    def duration_seconds(self) -> float:
        """Calculate the total duration of the workout route in seconds."""
        if len(self.points) < 2:
            return 0.0
        return (self.points[-1].time - self.points[0].time).total_seconds()

    @property
    def distance_meters(self) -> float:
        """Calculate the total distance of the workout route in meters."""
        cumulative_distances = self._cumulative_distances()

        return cumulative_distances[-1] if cumulative_distances else 0.0

    @property
    def elevation_gain_m(self) -> float:
        """Calculate the total elevation gain of the workout route in meters."""
        return sum(max(0.0, b.altitude - a.altitude) for a, b in zip(self.points, self.points[1:]))

    @property
    def elevation_loss_m(self) -> float:
        """Calculate the total elevation loss of the workout route in meters."""
        return sum(max(0.0, a.altitude - b.altitude) for a, b in zip(self.points, self.points[1:]))

    def estimated_elevation_gain_m(
        self,
        smoothing_window: int = ELEVATION_SMOOTHING_WINDOW,
        threshold_m: float = ELEVATION_NOISE_THRESHOLD_M,
    ) -> float | None:
        """Estimate the elevation gain while filtering out GPS altitude noise.

        Summing raw point-to-point altitude increases (see ``elevation_gain_m``) badly
        overestimates the gain because GPS altitude jitters by several meters. The
        algorithm works in two steps:

        1. Smoothing: each altitude is replaced by the median of the ``smoothing_window``
           samples centred on it (shorter near the route ends), which removes spikes.
        2. Hysteresis: the smoothed profile is walked while tracking ``base`` (the lowest
           altitude of the current climb) and ``peak`` (the highest altitude reached since).
           A new maximum raises ``peak``. A drop of at least ``threshold_m`` below ``peak``
           confirms the climb: ``peak - base`` is added to the gain if it is itself at least
           ``threshold_m``, then both restart from the current altitude. A fall below
           ``base`` before any confirmation restarts the climb lower. The pending climb is
           added at the end of the route if it reaches the threshold.

        Variations smaller than ``threshold_m`` are therefore never counted.

        Returns:
            The estimated gain in meters, or ``None`` when the route carries no
            altitude information (fewer than two available samples or all are zero).
        """
        valid_altitudes = [p.altitude for p in self.points if p.altitude_available]
        if len(valid_altitudes) < 2 or all(
            isclose(altitude, 0.0, abs_tol=ALTITUDE_ZERO_TOLERANCE_M)
            for altitude in valid_altitudes
        ):
            return None

        gain = 0.0
        continuous_altitudes: list[float] = []
        for point in self.points:
            if point.altitude_available:
                continuous_altitudes.append(point.altitude)
            else:
                gain += self._estimate_continuous_elevation_gain(
                    continuous_altitudes, smoothing_window, threshold_m
                )
                continuous_altitudes = []
        gain += self._estimate_continuous_elevation_gain(
            continuous_altitudes, smoothing_window, threshold_m
        )
        return gain

    @staticmethod
    def _estimate_continuous_elevation_gain(
        altitudes: list[float], smoothing_window: int, threshold_m: float
    ) -> float:
        """Estimate elevation gain for one uninterrupted sequence of altitude samples."""
        if len(altitudes) < 2:
            return 0.0

        half = max(smoothing_window, 1) // 2
        smoothed = [
            median(altitudes[max(0, i - half) : i + half + 1]) for i in range(len(altitudes))
        ]
        gain = 0.0
        base = peak = smoothed[0]
        for value in smoothed[1:]:
            if value > peak:
                peak = value
            elif peak - value >= threshold_m:
                if peak - base >= threshold_m:
                    gain += peak - base
                base = peak = value
            elif value < base:
                base = peak = value
        if peak - base >= threshold_m:
            gain += peak - base
        return gain

    def to_dataframe(self) -> pd.DataFrame:
        """Convert the workout route to a pandas DataFrame."""
        return pd.DataFrame(
            {
                "time": [p.time for p in self.points],
                "latitude": [p.latitude for p in self.points],
                "longitude": [p.longitude for p in self.points],
                "altitude": [p.altitude for p in self.points],
            }
        )

    def add_point(self, point: RoutePoint) -> None:
        """Add a new point to the workout route."""
        self.points.append(point)
        self._cumulative_distance_cache = None
        self._sorted_times_cache = None

    def sorted_times(self) -> list[datetime]:
        """Return a cached list of point timestamps in order, for binary-search clipping."""
        if self._sorted_times_cache is None:
            self._sorted_times_cache = [p.time for p in self.points]
        return self._sorted_times_cache

    @staticmethod
    def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate the Haversine distance between two GPS points in meters."""
        r = 6_371_000.0
        p1, p2 = radians(lat1), radians(lat2)
        dp = radians(lat2 - lat1)
        dl = radians(lon2 - lon1)
        a = sin(dp / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
        return 2 * r * atan2(sqrt(a), sqrt(1 - a))

    def _cumulative_distances(self) -> list[float]:
        """Return cumulative route distances for each point.

        The value at index ``i`` is the total traveled distance from the
        first point up to point ``i``.
        """
        if self._cumulative_distance_cache is not None:
            return self._cumulative_distance_cache

        if len(self.points) < 2:
            self._cumulative_distance_cache = [0.0] * len(self.points)
            return self._cumulative_distance_cache

        distances = [0.0]
        for previous, current in zip(self.points, self.points[1:]):
            avg_speed = (previous.speed + current.speed) / 2.0
            delta_t = (current.time - previous.time).total_seconds()
            if avg_speed > 0.0 and delta_t > 0.0:
                segment_distance = avg_speed * delta_t
            else:
                segment_distance = self.haversine_m(
                    previous.latitude,
                    previous.longitude,
                    current.latitude,
                    current.longitude,
                )
            distances.append(distances[-1] + segment_distance)

        self._cumulative_distance_cache = distances
        return self._cumulative_distance_cache

    def sample_point_at_fraction(self, fraction: float) -> tuple[float, float] | None:
        """Return the ``(latitude, longitude)`` of the point nearest to *fraction* of total dist.

        Uses binary search over the cached cumulative-distance list, so repeated
        calls at different fractions are cheap (O(log n) after the first call).

        Args:
            fraction: A value in ``[0, 1]`` representing the fraction of the total
                route distance at which to sample.  Values outside ``[0, 1]`` are
                clamped silently.

        Returns:
            ``(lat, lon)`` at the nearest sampled point, or ``None`` when the route
            has fewer than two points or its total distance is zero.
        """
        cum = self._cumulative_distances()
        if not cum or cum[-1] <= 0:
            return None
        fraction = max(0.0, min(1.0, fraction))
        target = fraction * cum[-1]
        lo, hi = 0, len(cum) - 1
        while lo < hi:
            mid = (lo + hi) // 2
            if cum[mid] < target:
                lo = mid + 1
            else:
                hi = mid
        pt = self.points[lo]
        return pt.latitude, pt.longitude

    @classmethod
    def calculate_distance_scale_factor(
        cls, route_distance_m: float, reference_distance_m: float | None
    ) -> float:
        """Return a route-distance normalization factor when the mismatch is realistic.

        The reference distance comes from the workout summary. A modest adjustment helps
        when GPX-derived distance slightly under/over-counts due to sampling, pauses, or
        Apple Health export quirks. Large mismatches are treated as data quality issues and
        therefore do not trigger scaling.

        This factor is computed once per workout route and reused for all queried
        segment distances (100m, 200m, 1km, 5km, half-marathon, etc.).
        """
        if reference_distance_m is None or route_distance_m <= 0 or reference_distance_m <= 0:
            return 1.0

        scale_factor = reference_distance_m / route_distance_m
        deviation = abs(scale_factor - 1.0)
        if deviation <= cls.MAX_REALISTIC_DISTANCE_SCALE_DEVIATION:
            return scale_factor

        return 1.0

    def _find_segment_end_index(
        self,
        start_idx: int,
        end_idx: int,
        segment_length_m: float,
        cumulative_distances: list[float],
        distance_scale_factor: float,
    ) -> int:
        """Find the end index for a segment of the given length."""
        current_end = max(end_idx, start_idx + 1)
        while current_end < len(self.points):
            route_distance = (
                cumulative_distances[current_end] - cumulative_distances[start_idx]
            ) * distance_scale_factor
            if route_distance >= segment_length_m:
                break
            current_end += 1
        return current_end

    def _interpolate_at_distance(
        self, end_idx: int, target_unscaled: float, cum: list[float]
    ) -> tuple[float, float]:
        """Return ``(seconds since first point, altitude)`` where *cum* reaches the target.

        The crossing lies in the segment ending at ``end_idx``. Interpolating avoids
        attributing a whole distance jump (e.g. across a gap without GPS points) to the
        split that happens to contain the next recorded point.
        """
        previous = self.points[end_idx - 1]
        current = self.points[end_idx]
        origin = self.points[0].time
        span = cum[end_idx] - cum[end_idx - 1]
        ratio = (target_unscaled - cum[end_idx - 1]) / span if span > 0 else 1.0
        ratio = min(max(ratio, 0.0), 1.0)
        elapsed = (previous.time - origin).total_seconds() + ratio * (
            current.time - previous.time
        ).total_seconds()
        altitude = previous.altitude + ratio * (current.altitude - previous.altitude)
        return elapsed, altitude

    def _build_split_data(
        self,
        split_num: int,
        split_start_idx: int,
        split_end_idx: int,
        split_distance_m: float,
        split_start_distance: float,
        split_end_distance: float,
        start: tuple[float, float],
        end: tuple[float, float],
    ) -> dict[str, float | int] | None:
        """Build one split result when the segment has a positive duration.

        ``start`` and ``end`` are ``(elapsed seconds, altitude)`` boundaries.
        """
        duration_s = end[0] - start[0]
        if duration_s <= 0:
            return None

        split_data: dict[str, float | int] = {
            "split": split_num,
            "duration_s": duration_s,
            "pace_min_per_km": (duration_s / 60.0) * (1000.0 / split_distance_m),
            "elevation_change_m": end[1] - start[1],
        }
        cumulative_distances = self._cumulative_distances()
        heart_rates = [
            point.heart_rate
            for point_idx, point in enumerate(
                self.points[split_start_idx : split_end_idx + 1], start=split_start_idx
            )
            if split_start_distance <= cumulative_distances[point_idx] <= split_end_distance
            and point.heart_rate is not None
        ]
        if heart_rates:
            split_data["avg_heart_rate"] = sum(heart_rates) / len(heart_rates)

        return split_data

    def find_fastest_segment(
        self, segment_length_m: float, distance_scale_factor: float = 1.0
    ) -> float | None:
        """Find the fastest segment of the given length in meters.

        Uses traveled route distance rather than straight-line displacement.
        This matches how running segments are typically defined and allows a
        sliding-window search with linear complexity.

        Args:
            segment_length_m: Requested segment length in meters.
            distance_scale_factor: Multiplicative correction applied to route-distance
                progression when route and workout summary distances differ by a
                realistic margin. Set to ``1.0`` to disable scaling.

        Returns:
            The duration in seconds of the fastest qualifying segment,
            or None if no valid segment exists.
        """
        if self.is_empty or segment_length_m <= 0 or len(self.points) < 2:
            return None

        cumulative_distances = self._cumulative_distances()
        best_duration_s: float | None = None
        end_idx = 1

        for start_idx in range(len(self.points) - 1):
            end_idx = self._find_segment_end_index(
                start_idx, end_idx, segment_length_m, cumulative_distances, distance_scale_factor
            )

            if end_idx == len(self.points):
                break

            duration_s = (self.points[end_idx].time - self.points[start_idx].time).total_seconds()
            if duration_s > 0 and (best_duration_s is None or duration_s < best_duration_s):
                best_duration_s = duration_s

        return best_duration_s

    def find_fastest_segment_window(
        self, segment_length_m: float, distance_scale_factor: float = 1.0
    ) -> tuple[float, datetime, datetime, float] | None:
        """Find the fastest segment

        The elevation change is computed as the net gain (positive) or loss (negative) in altitude
        from the start to the end of the segment

        Identical sliding-window search to :meth:`find_fastest_segment` but also
        returns the GPS timestamps that bound the best window so callers can look
        up health records (e.g. running power) that fall within it.

        Args:
            segment_length_m: Requested segment length in meters.
            distance_scale_factor: Same scaling applied in :meth:`find_fastest_segment`.

        Returns:
            ``(duration_s, start_time, end_time, elevation_change_m)`` for the fastest window, or
            ``None`` if no valid segment exists.
        """
        if self.is_empty or segment_length_m <= 0 or len(self.points) < 2:
            return None

        cumulative_distances = self._cumulative_distances()
        best: tuple[float, datetime, datetime, float] | None = None
        end_idx = 1

        for start_idx in range(len(self.points) - 1):
            end_idx = self._find_segment_end_index(
                start_idx, end_idx, segment_length_m, cumulative_distances, distance_scale_factor
            )

            if end_idx == len(self.points):
                break

            duration_s = (self.points[end_idx].time - self.points[start_idx].time).total_seconds()
            elevation_change_m = self.points[end_idx].altitude - self.points[start_idx].altitude
            if duration_s > 0 and (best is None or duration_s < best[0]):
                best = (
                    duration_s,
                    self.points[start_idx].time,
                    self.points[end_idx].time,
                    elevation_change_m,
                )

        return best

    def compute_splits(
        self,
        split_distance_m: float = 1000.0,
        distance_scale_factor: float = 1.0,
    ) -> list[dict[str, float | int]]:
        """Compute per-split pace data from GPS route.

        Each split covers *split_distance_m* of traveled distance.  Only
        complete splits are returned; any partial final split is omitted.

        Args:
            split_distance_m: Length of each split in meters (default 1000 m = 1 km).
            distance_scale_factor: Multiplicative correction applied to cumulative
                route distances.  Use :meth:`calculate_distance_scale_factor` to
                derive this value from the workout summary distance.

        Returns:
            A list of dicts, one per complete split, each containing:

            - ``"split"``:                int   – 1-indexed split number.
            - ``"duration_s"``:           float – elapsed time for this split (seconds).
            - ``"pace_min_per_km"``:      float – pace in min/km for this split.
            - ``"elevation_change_m"``:   float – net altitude change from split
              start to split end (positive = uphill, negative = downhill).
            - ``"avg_heart_rate"``:       float – average heart rate in bpm for the
              split when route points carry heart-rate samples.
        """
        if len(self.points) < 2 or split_distance_m <= 0:
            return []

        cum = self._cumulative_distances()
        total_scaled = cum[-1] * distance_scale_factor if cum else 0.0

        if total_scaled < split_distance_m:
            return []

        splits: list[dict[str, float | int]] = []
        split_num = 1
        split_start_idx = 0
        start: tuple[float, float] = (0.0, self.points[0].altitude)

        while True:
            target_scaled = split_num * split_distance_m
            if target_scaled > total_scaled:
                break

            # Find the route point where the scaled cumulative distance reaches the target.
            target_unscaled = target_scaled / distance_scale_factor
            split_end_idx = split_start_idx + 1
            while split_end_idx < len(cum) and cum[split_end_idx] < target_unscaled:
                split_end_idx += 1

            if split_end_idx >= len(self.points):
                break

            end = self._interpolate_at_distance(split_end_idx, target_unscaled, cum)
            split_data = self._build_split_data(
                split_num=split_num,
                split_start_idx=split_start_idx,
                split_end_idx=split_end_idx,
                split_distance_m=split_distance_m,
                split_start_distance=(split_num - 1) * split_distance_m / distance_scale_factor,
                split_end_distance=target_unscaled,
                start=start,
                end=end,
            )
            if split_data is not None:
                splits.append(split_data)

            split_num += 1
            split_start_idx = split_end_idx - 1
            start = end

        return splits
