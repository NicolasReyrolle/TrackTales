"""Schema definition for the workout detail modal.

This module defines the data contract for displaying workout details,
covering generic attributes (shown for all workout types) and per-type
attributes for specific activity types.

Field names correspond to the keys produced by :class:`~logic.export_parser.ExportParser`
in :class:`~logic.models.WorkoutRecord`, which become the DataFrame columns in
``ParsedHealthData.workouts``.

**Field naming convention (from ExportParser):**

- Workout element attributes: ``activityType``, ``duration``, ``startDate``,
  ``endDate``
- ``WorkoutStatistics``: ``f"{stat_attr}{stat_type}"`` where *stat_attr* is one of
  ``sum``, ``average``, ``minimum``, ``maximum``, and *stat_type* is the
  ``HKQuantityTypeIdentifier`` value with the ``HKQuantityTypeIdentifier`` prefix
  stripped.  For example, ``HKQuantityTypeIdentifierHeartRate`` with the ``average``
  aggregate becomes ``averageHeartRate``.
- ``MetadataEntry``: ``key.replace("HK", "")`` where *key* is the raw XML attribute.
  For example, ``HKElevationAscended`` becomes ``ElevationAscended``.

**Presence semantics:**

- ``ALWAYS`` — the field is populated for every workout of this type recorded by
  an Apple Watch (or equivalent Apple Health source that reports the statistic).
- ``OPTIONAL`` — the field *may* be absent, for example because the sensor was not
  worn, the source device does not report the metric, or the workout pre-dates the
  introduction of the Apple Health Kit quantity type.

**Extensibility:**

New activity types can be registered by adding an entry to :data:`PER_TYPE_FIELDS`.
New generic fields shared by all types can be appended to :data:`GENERIC_FIELDS`.
Use :func:`get_fields_for_activity` to retrieve the combined ordered list of fields
(generic first, then type-specific) for a given activity type.

For activity types that need display-value mappings for integer-coded metadata (such as
swimming location type or stroke style), add a corresponding entry to
:data:`ENUM_DISPLAY_VALUES`.

**Note on VO2 Max:**

VO2 max is recorded as a separate ``HKQuantityTypeIdentifierVO2Max`` *Record* in the
Apple Health export, not as a ``WorkoutStatistics`` child of a ``Workout`` element.
It is therefore not directly available as a column in ``ParsedHealthData.workouts``.
A future enhancement could join the nearest-in-time VO2 max record to each workout;
until then it is documented here for completeness but is not included as a
:class:`FieldDefinition` in :data:`PER_TYPE_FIELDS`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class FieldType(str, Enum):
    """Data type for rendering and processing a field value.

    Values:
        STRING:   Freeform text; render as-is.
        NUMBER:   Numeric value; apply unit formatting.
        DURATION: Integer seconds; render as HH:MM:SS.
        DATE:     ISO datetime string or ``pd.Timestamp``; render with locale formatter.
        BOOLEAN:  ``True``/``False`` value derived from a boolean metadata entry (0/1).
    """

    STRING = "string"
    NUMBER = "number"
    DURATION = "duration"
    DATE = "date"
    BOOLEAN = "boolean"


class FieldPresence(str, Enum):
    """Whether a field is guaranteed to be populated for a given workout type.

    Values:
        ALWAYS:   Present in every workout of this type from supported sources.
        OPTIONAL: May be absent; check for ``None``/``NaN`` before rendering.
    """

    ALWAYS = "always"
    OPTIONAL = "optional"


@dataclass(frozen=True)
class FieldDefinition:
    """Specification of a single attribute in the workout detail modal.

    Attributes:
        field_name:   Key in the ``WorkoutRecord`` dict and ``DataFrame`` column name.
        display_name: Human-readable label shown in the UI.
        unit:         Physical unit string (``None`` if unitless or categorical).
        field_type:   How the value should be rendered.
        presence:     Whether this field is guaranteed to be populated.
        description:  Maintainer documentation explaining the field origin and semantics.
    """

    field_name: str
    display_name: str
    unit: str | None
    field_type: FieldType
    presence: FieldPresence
    description: str = ""


# ---------------------------------------------------------------------------
# Display-value mappings for integer-coded metadata fields
# ---------------------------------------------------------------------------

#: Maps the integer codes stored in ``SwimmingLocationType`` to human-readable labels.
#: Source: ``HKWorkoutSwimmingLocationType`` enum in Apple HealthKit.
#: 1 = pool (indoors), 2 = open water (outdoors).
SWIMMING_LOCATION_TYPES: dict[int, str] = {
    1: "Pool",
    2: "Open Water",
}

#: Maps the integer codes stored in ``SwimmingStrokeStyle`` (per-lap metadata) to labels.
#: Source: ``HKSwimmingStrokeStyle`` enum in Apple HealthKit.
#: 0 = unknown, 1 = mixed, 2 = freestyle, 3 = backstroke,
#: 4 = breaststroke, 5 = butterfly, 6 = kickboard.
SWIMMING_STROKE_STYLES: dict[int, str] = {
    0: "Unknown",
    1: "Mixed",
    2: "Freestyle",
    3: "Backstroke",
    4: "Breaststroke",
    5: "Butterfly",
    6: "Kickboard",
}

#: Collects all enum display-value mappings keyed by ``field_name`` for easy lookup.
#: Consumers can call ``ENUM_DISPLAY_VALUES.get(field_name, {}).get(raw_value, str(raw_value))``
#: to convert a raw integer to a label.
ENUM_DISPLAY_VALUES: dict[str, dict[int, str]] = {
    "SwimmingLocationType": SWIMMING_LOCATION_TYPES,
    "SwimmingStrokeStyle": SWIMMING_STROKE_STYLES,
}


# ---------------------------------------------------------------------------
# Generic fields — shown for every workout type
# ---------------------------------------------------------------------------

#: Fields common to all workout types. These mirror the subset of workout-table
#: columns that apply across all workout types, plus additional Apple Health Kit
#: attributes present on every workout. Type-specific workout-table columns (for
#: example, running-only metrics such as average running power) belong in the
#: relevant per-type field definitions rather than in :data:`GENERIC_FIELDS`.
#:
#: Ordering follows the recommended display priority: identity fields first, then
#: performance, then environmental context.
GENERIC_FIELDS: list[FieldDefinition] = [
    # ---- Identity / timing ----
    FieldDefinition(
        field_name="activityType",
        display_name="Activity",
        unit=None,
        field_type=FieldType.STRING,
        presence=FieldPresence.ALWAYS,
        description=(
            "Normalized activity type string produced by stripping the "
            "'HKWorkoutActivityType' prefix from the raw XML attribute."
        ),
    ),
    FieldDefinition(
        field_name="startDate",
        display_name="Start Date",
        unit=None,
        field_type=FieldType.DATE,
        presence=FieldPresence.ALWAYS,
        description="Workout start timestamp from the 'startDate' XML attribute.",
    ),
    FieldDefinition(
        field_name="endDate",
        display_name="End Date",
        unit=None,
        field_type=FieldType.DATE,
        presence=FieldPresence.OPTIONAL,
        description="Workout end timestamp from the 'endDate' XML attribute.",
    ),
    FieldDefinition(
        field_name="duration",
        display_name="Duration",
        unit="s",
        field_type=FieldType.DURATION,
        presence=FieldPresence.ALWAYS,
        description=(
            "Total elapsed time in seconds, converted from the 'duration'/'durationUnit' "
            "XML attributes by ExportParser.duration_to_seconds()."
        ),
    ),
    # ---- Distance ----
    FieldDefinition(
        field_name="distance",
        display_name="Distance",
        unit="m",
        field_type=FieldType.NUMBER,
        presence=FieldPresence.OPTIONAL,
        description=(
            "Total distance in metres, consolidated from any 'Distance*' WorkoutStatistics "
            "sum (e.g. DistanceWalkingRunning, DistanceCycling, DistanceSwimming)."
        ),
    ),
    # ---- Energy ----
    FieldDefinition(
        field_name="sumActiveEnergyBurned",
        display_name="Active Calories",
        unit="kcal",
        field_type=FieldType.NUMBER,
        presence=FieldPresence.OPTIONAL,
        description=(
            "Sum of HKQuantityTypeIdentifierActiveEnergyBurned WorkoutStatistics. "
            "Present for most Apple Watch workouts."
        ),
    ),
    FieldDefinition(
        field_name="sumBasalEnergyBurned",
        display_name="Resting Calories",
        unit="kcal",
        field_type=FieldType.NUMBER,
        presence=FieldPresence.OPTIONAL,
        description=(
            "Sum of HKQuantityTypeIdentifierBasalEnergyBurned WorkoutStatistics. "
            "Present for most Apple Watch workouts."
        ),
    ),
    # ---- Heart rate ----
    FieldDefinition(
        field_name="averageHeartRate",
        display_name="Avg Heart Rate",
        unit="bpm",
        field_type=FieldType.NUMBER,
        presence=FieldPresence.OPTIONAL,
        description=(
            "Average of HKQuantityTypeIdentifierHeartRate WorkoutStatistics. "
            "Requires Apple Watch or compatible heart rate monitor."
        ),
    ),
    FieldDefinition(
        field_name="minimumHeartRate",
        display_name="Min Heart Rate",
        unit="bpm",
        field_type=FieldType.NUMBER,
        presence=FieldPresence.OPTIONAL,
        description="Minimum of HKQuantityTypeIdentifierHeartRate WorkoutStatistics.",
    ),
    FieldDefinition(
        field_name="maximumHeartRate",
        display_name="Max Heart Rate",
        unit="bpm",
        field_type=FieldType.NUMBER,
        presence=FieldPresence.OPTIONAL,
        description="Maximum of HKQuantityTypeIdentifierHeartRate WorkoutStatistics.",
    ),
    # ---- Elevation ----
    FieldDefinition(
        field_name="ElevationAscended",
        display_name="Elevation Gain",
        unit="m",
        field_type=FieldType.NUMBER,
        presence=FieldPresence.OPTIONAL,
        description=(
            "Elevation gain in metres from the HKElevationAscended MetadataEntry. "
            "The raw value may be in centimetres and is converted to metres by "
            "ExportParser._parse_value() via the 'cm' → 'm' unit conversion."
        ),
    ),
    # ---- Environmental context ----
    FieldDefinition(
        field_name="IndoorWorkout",
        display_name="Indoor",
        unit=None,
        field_type=FieldType.BOOLEAN,
        presence=FieldPresence.OPTIONAL,
        description=(
            "Boolean flag from HKIndoorWorkout MetadataEntry. "
            "True when the workout was performed indoors."
        ),
    ),
    FieldDefinition(
        field_name="TimeZone",
        display_name="Time Zone",
        unit=None,
        field_type=FieldType.STRING,
        presence=FieldPresence.OPTIONAL,
        description="IANA time zone name from HKTimeZone MetadataEntry.",
    ),
    FieldDefinition(
        field_name="WeatherTemperature",
        display_name="Temperature",
        unit="°C",
        field_type=FieldType.NUMBER,
        presence=FieldPresence.OPTIONAL,
        description=(
            "Ambient temperature in °C from HKWeatherTemperature MetadataEntry. "
            "Original value in °F is converted to °C by ExportParser._parse_value()."
        ),
    ),
    FieldDefinition(
        field_name="WeatherHumidity",
        display_name="Humidity",
        unit="%",
        field_type=FieldType.NUMBER,
        presence=FieldPresence.OPTIONAL,
        description=(
            "Relative humidity from HKWeatherHumidity MetadataEntry. "
            "ExportParser._parse_value() parses values such as '6400 %' to 64.0, "
            "so this field is already stored as a percent value for display."
        ),
    ),
    FieldDefinition(
        field_name="AverageMETs",
        display_name="Avg METs",
        unit="kcal/hr·kg",
        field_type=FieldType.NUMBER,
        presence=FieldPresence.OPTIONAL,
        description=(
            "Average metabolic equivalent of task from HKAverageMETs MetadataEntry. "
            "Indicates exercise intensity relative to resting metabolic rate. "
            "Apple Health exports use either 'kcal/hr·kg' (middle-dot) or 'kcal/hr-kg' "
            "(hyphen) depending on the device/iOS version; both represent the same unit. "
            "The raw unit string is stored in AverageMETsUnit by the parser. "
            "The canonical display unit defined here ('kcal/hr·kg') should be used by "
            "the UI regardless of the raw unit string in the export."
        ),
    ),
]


# ---------------------------------------------------------------------------
# Shared display-name constants reused across multiple activity types
# ---------------------------------------------------------------------------

_DN_AVG_SPEED = "Avg Speed"
_DN_AVG_CADENCE = "Avg Cadence"
_DN_AVG_POWER = "Avg Power"

# ---------------------------------------------------------------------------
# Shared field definitions reused across multiple activity types
# ---------------------------------------------------------------------------

#: Step count field, shared by Running, Hiking, and Walking.
_STEP_COUNT_FIELD: FieldDefinition = FieldDefinition(
    field_name="sumStepCount",
    display_name="Step Count",
    unit="steps",
    field_type=FieldType.NUMBER,
    presence=FieldPresence.OPTIONAL,
    description="Sum of HKQuantityTypeIdentifierStepCount WorkoutStatistics.",
)


# ---------------------------------------------------------------------------
# Per-type fields — shown only for a specific activity type
# ---------------------------------------------------------------------------

#: Type-specific fields for running workouts.
#:
#: VO2 max is tracked as a separate HKQuantityTypeIdentifierVO2Max *Record* element
#: (not a WorkoutStatistics child) and is therefore not listed here.  A future
#: enhancement could join the nearest-in-time VO2 max record when displaying running
#: workout details.
_RUNNING_FIELDS: list[FieldDefinition] = [
    FieldDefinition(
        field_name="averageRunningSpeed",
        display_name=_DN_AVG_SPEED,
        unit="km/h",
        field_type=FieldType.NUMBER,
        presence=FieldPresence.OPTIONAL,
        description=(
            "Average of HKQuantityTypeIdentifierRunningSpeed WorkoutStatistics. "
            "Can be used to compute average pace (min/km) as 60 / speed_km_h."
        ),
    ),
    FieldDefinition(
        field_name="averageRunningCadence",
        display_name=_DN_AVG_CADENCE,
        unit="steps/min",
        field_type=FieldType.NUMBER,
        presence=FieldPresence.OPTIONAL,
        description=(
            "Average of HKQuantityTypeIdentifierRunningCadence WorkoutStatistics. "
            "Reported as total steps per minute (both feet)."
        ),
    ),
    FieldDefinition(
        field_name="averageRunningStrideLength",
        display_name="Avg Stride Length",
        unit="m",
        field_type=FieldType.NUMBER,
        presence=FieldPresence.OPTIONAL,
        description=(
            "Average of HKQuantityTypeIdentifierRunningStrideLength WorkoutStatistics. "
            "One stride = two steps (left + right)."
        ),
    ),
    FieldDefinition(
        field_name="averageRunningPower",
        display_name=_DN_AVG_POWER,
        unit="W",
        field_type=FieldType.NUMBER,
        presence=FieldPresence.OPTIONAL,
        description=(
            "Average of HKQuantityTypeIdentifierRunningPower WorkoutStatistics. "
            "Requires Apple Watch Series 8+ or Ultra."
        ),
    ),
    FieldDefinition(
        field_name="averageRunningVerticalOscillation",
        display_name="Avg Vertical Oscillation",
        unit="cm",
        field_type=FieldType.NUMBER,
        presence=FieldPresence.OPTIONAL,
        description=(
            "Average of HKQuantityTypeIdentifierRunningVerticalOscillation WorkoutStatistics. "
            "Vertical movement of the centre of mass per stride in centimetres."
        ),
    ),
    FieldDefinition(
        field_name="averageRunningGroundContactTime",
        display_name="Avg Ground Contact Time",
        unit="ms",
        field_type=FieldType.NUMBER,
        presence=FieldPresence.OPTIONAL,
        description=(
            "Average of HKQuantityTypeIdentifierRunningGroundContactTime WorkoutStatistics. "
            "Time each foot spends on the ground per stride in milliseconds."
        ),
    ),
    _STEP_COUNT_FIELD,
]

#: Type-specific fields for cycling workouts.
_CYCLING_FIELDS: list[FieldDefinition] = [
    FieldDefinition(
        field_name="averageCyclingSpeed",
        display_name=_DN_AVG_SPEED,
        unit="km/h",
        field_type=FieldType.NUMBER,
        presence=FieldPresence.OPTIONAL,
        description=(
            "Average of HKQuantityTypeIdentifierCyclingSpeed WorkoutStatistics. "
            "Requires Apple Watch Series 4+ with a paired cycling sensor or "
            "Apple Watch Ultra 2+ with native cycling detection."
        ),
    ),
    FieldDefinition(
        field_name="averageCyclingCadence",
        display_name=_DN_AVG_CADENCE,
        unit="rpm",
        field_type=FieldType.NUMBER,
        presence=FieldPresence.OPTIONAL,
        description=(
            "Average of HKQuantityTypeIdentifierCyclingCadence WorkoutStatistics. "
            "Pedalling revolutions per minute."
        ),
    ),
    FieldDefinition(
        field_name="averageCyclingPower",
        display_name=_DN_AVG_POWER,
        unit="W",
        field_type=FieldType.NUMBER,
        presence=FieldPresence.OPTIONAL,
        description=(
            "Average of HKQuantityTypeIdentifierCyclingPower WorkoutStatistics. "
            "Requires a Bluetooth power meter paired with Apple Watch."
        ),
    ),
    FieldDefinition(
        field_name="averageCyclingFunctionalThresholdPower",
        display_name="Functional Threshold Power",
        unit="W",
        field_type=FieldType.NUMBER,
        presence=FieldPresence.OPTIONAL,
        description=(
            "Average of HKQuantityTypeIdentifierCyclingFunctionalThresholdPower "
            "WorkoutStatistics.  The highest average power a rider can sustain for "
            "approximately one hour; used to derive training zones."
        ),
    ),
]

#: Type-specific fields for swimming workouts.
_SWIMMING_FIELDS: list[FieldDefinition] = [
    FieldDefinition(
        field_name="sumSwimmingStrokeCount",
        display_name="Stroke Count",
        unit="strokes",
        field_type=FieldType.NUMBER,
        presence=FieldPresence.OPTIONAL,
        description=(
            "Sum of HKQuantityTypeIdentifierSwimmingStrokeCount WorkoutStatistics. "
            "Total strokes counted over the full session."
        ),
    ),
    FieldDefinition(
        field_name="LapLength",
        display_name="Lap Length",
        unit="m",
        field_type=FieldType.NUMBER,
        presence=FieldPresence.OPTIONAL,
        description=(
            "Pool lane length from HKLapLength MetadataEntry. "
            "Typically 25 m or 50 m for pool swimming; absent for open-water sessions."
        ),
    ),
    FieldDefinition(
        field_name="SwimmingLocationType",
        display_name="Location Type",
        unit=None,
        field_type=FieldType.STRING,
        presence=FieldPresence.OPTIONAL,
        description=(
            "Integer code from HKSwimmingLocationType MetadataEntry indicating whether "
            "the session was in open water (1) or a pool (2).  Use SWIMMING_LOCATION_TYPES "
            "to convert to a human-readable label."
        ),
    ),
]

#: Type-specific fields for hiking workouts.
#:
#: Elevation gain (``ElevationAscended``) is already present in :data:`GENERIC_FIELDS`
#: because it applies to all outdoor activities.  The fields below complement the generic
#: set with hiking-specific metrics.
_HIKING_FIELDS: list[FieldDefinition] = [
    _STEP_COUNT_FIELD,
]

#: Type-specific fields for walking workouts.
_WALKING_FIELDS: list[FieldDefinition] = [
    _STEP_COUNT_FIELD,
    FieldDefinition(
        field_name="averageWalkingCadence",
        display_name=_DN_AVG_CADENCE,
        unit="steps/min",
        field_type=FieldType.NUMBER,
        presence=FieldPresence.OPTIONAL,
        description=(
            "Average of HKQuantityTypeIdentifierWalkingCadence WorkoutStatistics. "
            "Recorded when walking speed and step count data are available."
        ),
    ),
    FieldDefinition(
        field_name="averageWalkingStepLength",
        display_name="Avg Step Length",
        unit="m",
        field_type=FieldType.NUMBER,
        presence=FieldPresence.OPTIONAL,
        description="Average of HKQuantityTypeIdentifierWalkingStepLength WorkoutStatistics.",
    ),
    FieldDefinition(
        field_name="averageWalkingSpeed",
        display_name=_DN_AVG_SPEED,
        unit="km/h",
        field_type=FieldType.NUMBER,
        presence=FieldPresence.OPTIONAL,
        description="Average of HKQuantityTypeIdentifierWalkingSpeed WorkoutStatistics.",
    ),
]


#: Maps activity type names (as produced by ExportParser, without the
#: ``HKWorkoutActivityType`` prefix) to their type-specific :class:`FieldDefinition` lists.
#:
#: To add support for a new activity type, insert an entry here mapping the activity
#: type string to a list of :class:`FieldDefinition` instances.  The generic fields
#: in :data:`GENERIC_FIELDS` are always included; the list here is *additional* fields.
PER_TYPE_FIELDS: dict[str, list[FieldDefinition]] = {
    "Running": _RUNNING_FIELDS,
    "Cycling": _CYCLING_FIELDS,
    "Swimming": _SWIMMING_FIELDS,
    "Hiking": _HIKING_FIELDS,
    "Walking": _WALKING_FIELDS,
}


def get_fields_for_activity(activity_type: str) -> list[FieldDefinition]:
    """Return the ordered list of fields for the given *activity_type*.

    The returned list contains :data:`GENERIC_FIELDS` first, followed by any
    type-specific fields from :data:`PER_TYPE_FIELDS`.  For activity types not
    listed in :data:`PER_TYPE_FIELDS` only the generic fields are returned.

    Args:
        activity_type: Activity type string as produced by ``ExportParser``
            (e.g. ``"Running"``, ``"Cycling"``).

    Returns:
        Combined list of :class:`FieldDefinition` instances for *activity_type*.
    """
    return GENERIC_FIELDS + PER_TYPE_FIELDS.get(activity_type, [])
