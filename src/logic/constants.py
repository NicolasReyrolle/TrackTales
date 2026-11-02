"""Shared data-processing constants and candidates for future user settings."""

PANDAS_ISO8601_FORMAT = "ISO8601"

# Route-derived elevation gain estimation (used when a workout has no recorded elevation).
# Number of consecutive GPS altitude samples used by the moving median filter.
ELEVATION_SMOOTHING_WINDOW = 9

# Minimum climb/descent in meters to be considered real rather than GPS altitude noise.
ELEVATION_NOISE_THRESHOLD_M = 3.0

# Altitudes within this distance of 0 m are treated as "no altitude data".
ALTITUDE_ZERO_TOLERANCE_M = 1e-9

# Minimum fraction of GPS time coverage required for scaling.
MIN_GPS_TIME_COVERAGE_FOR_SCALING = 0.8

# Route-normalization settings candidates for a future user settings UI.
# Maximum relative deviation accepted when GPS distance exceeds the workout summary.
MAX_REALISTIC_DISTANCE_SCALE_DEVIATION = 0.10

# Upper scale factor accepted for GPS under-counts caused by recording interruptions.
MAX_GPS_INTERRUPTION_SCALE_FACTOR = 2.0
