"""Shared data-processing constants and candidates for future user settings."""

PANDAS_ISO8601_FORMAT = "ISO8601"

# Route-derived elevation gain estimation (used when a workout has no recorded elevation).
# Number of GPS altitude samples used by the moving median filter. Increasing this smooths
# more noise but can erase short climbs; decreasing it preserves detail but leaves more noise.
ELEVATION_SMOOTHING_WINDOW = 9

# Minimum climb/descent in meters to be considered real rather than GPS altitude noise.
# Increasing this filters more small climbs; decreasing it counts smaller changes but risks
# treating GPS noise as elevation gain.
ELEVATION_NOISE_THRESHOLD_M = 3.0

# Altitudes within this distance of 0 m are treated as "no altitude data". Increasing it can
# discard valid near-sea-level altitude; decreasing it can treat zero-level sensor noise as data.
ALTITUDE_ZERO_TOLERANCE_M = 1e-9

# Minimum fraction of workout time covered by GPS before route-distance scaling is applied.
# Increasing this skips scaling for more partial traces; decreasing it scales more partial traces,
# which can compensate for interruptions but may overstate distances when route data is missing.
MIN_GPS_TIME_COVERAGE_FOR_SCALING = 0.8

# Route-normalization settings candidates for a future user settings UI.
# Maximum deviation of the scale factor from 1.0 accepted when GPS distance exceeds the workout
# summary. Increasing this normalizes larger GPS over-counts; decreasing it leaves more routes
# unscaled, which can retain GPS over-count in segment distances.
MAX_REALISTIC_DISTANCE_SCALE_DEVIATION = 0.10

# Upper scale factor accepted for GPS under-counts caused by recording interruptions. Increasing
# this accepts and stretches larger GPS shortfalls (but risks scaling corrupt/mismatched routes);
# decreasing it rejects more interrupted routes and leaves their segment distances unscaled.
MAX_GPS_INTERRUPTION_SCALE_FACTOR = 2.0
