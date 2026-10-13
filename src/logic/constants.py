"""Shared constants for data processing."""

PANDAS_ISO8601_FORMAT = "ISO8601"

# Route-derived elevation gain estimation (used when a workout has no recorded elevation).
# Number of consecutive GPS altitude samples used by the moving median filter.
ELEVATION_SMOOTHING_WINDOW = 9
# Minimum climb/descent in meters to be considered real rather than GPS altitude noise.
ELEVATION_NOISE_THRESHOLD_M = 3.0
# Altitudes within this distance of 0 m are treated as "no altitude data".
ALTITUDE_ZERO_TOLERANCE_M = 1e-9
