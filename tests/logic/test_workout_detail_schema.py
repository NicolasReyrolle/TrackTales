"""Tests for the workout detail schema module."""

from __future__ import annotations

import pytest

from logic.workout_detail_schema import (
    ENUM_DISPLAY_VALUES,
    GENERIC_FIELDS,
    PER_TYPE_FIELDS,
    SWIMMING_LOCATION_TYPES,
    SWIMMING_STROKE_STYLES,
    FieldDefinition,
    FieldPresence,
    FieldType,
    get_fields_for_activity,
)

# ---------------------------------------------------------------------------
# FieldType and FieldPresence enum sanity checks
# ---------------------------------------------------------------------------


class TestEnums:
    """Verify that the enum members are present and have the expected string values."""

    def test_field_type_values(self) -> None:
        """FieldType members must match the string values consumed by the UI renderer."""
        assert FieldType.STRING == "string"
        assert FieldType.NUMBER == "number"
        assert FieldType.DURATION == "duration"
        assert FieldType.DATE == "date"
        assert FieldType.BOOLEAN == "boolean"

    def test_field_presence_values(self) -> None:
        """FieldPresence members must match their documented string values."""
        assert FieldPresence.ALWAYS == "always"
        assert FieldPresence.OPTIONAL == "optional"


# ---------------------------------------------------------------------------
# FieldDefinition dataclass
# ---------------------------------------------------------------------------


class TestFieldDefinition:
    """Unit tests for the FieldDefinition dataclass."""

    def test_frozen_immutable(self) -> None:
        """FieldDefinition instances must be immutable (frozen dataclass)."""
        fd = FieldDefinition(
            field_name="duration",
            display_name="Duration",
            unit="s",
            field_type=FieldType.DURATION,
            presence=FieldPresence.ALWAYS,
        )
        with pytest.raises((AttributeError, TypeError)):
            fd.field_name = "other"  # type: ignore[misc]

    def test_default_description_is_empty(self) -> None:
        """The description field defaults to an empty string."""
        fd = FieldDefinition(
            field_name="x",
            display_name="X",
            unit=None,
            field_type=FieldType.STRING,
            presence=FieldPresence.OPTIONAL,
        )
        assert fd.description == ""

    def test_unit_can_be_none(self) -> None:
        """Unit may be None for unitless or categorical fields."""
        fd = FieldDefinition(
            field_name="activityType",
            display_name="Activity",
            unit=None,
            field_type=FieldType.STRING,
            presence=FieldPresence.ALWAYS,
        )
        assert fd.unit is None


# ---------------------------------------------------------------------------
# GENERIC_FIELDS
# ---------------------------------------------------------------------------


class TestGenericFields:
    """Validate the generic fields list."""

    def test_non_empty(self) -> None:
        """GENERIC_FIELDS must contain at least one field."""
        assert len(GENERIC_FIELDS) > 0

    def test_all_entries_are_field_definitions(self) -> None:
        """Every entry in GENERIC_FIELDS must be a FieldDefinition instance."""
        for field in GENERIC_FIELDS:
            assert isinstance(field, FieldDefinition), f"Not a FieldDefinition: {field!r}"

    def test_field_names_are_non_empty_strings(self) -> None:
        """Every field_name must be a non-empty string."""
        for field in GENERIC_FIELDS:
            assert isinstance(field.field_name, str) and field.field_name, (
                f"Empty field_name in {field!r}"
            )

    def test_display_names_are_non_empty_strings(self) -> None:
        """Every display_name must be a non-empty string."""
        for field in GENERIC_FIELDS:
            assert isinstance(field.display_name, str) and field.display_name, (
                f"Empty display_name in {field!r}"
            )

    def test_no_duplicate_field_names(self) -> None:
        """GENERIC_FIELDS must not contain duplicate field_name values."""
        names = [f.field_name for f in GENERIC_FIELDS]
        assert len(names) == len(set(names)), "Duplicate field_names in GENERIC_FIELDS"

    # --- Required generic fields -----------------------------------------------

    def test_contains_activity_type(self) -> None:
        """activityType must be in GENERIC_FIELDS and marked ALWAYS."""
        field = _find_field(GENERIC_FIELDS, "activityType")
        assert field is not None, "activityType not found in GENERIC_FIELDS"
        assert field.presence == FieldPresence.ALWAYS
        assert field.field_type == FieldType.STRING

    def test_contains_start_date(self) -> None:
        """startDate must be in GENERIC_FIELDS and marked ALWAYS."""
        field = _find_field(GENERIC_FIELDS, "startDate")
        assert field is not None, "startDate not found in GENERIC_FIELDS"
        assert field.presence == FieldPresence.ALWAYS
        assert field.field_type == FieldType.DATE

    def test_contains_duration(self) -> None:
        """duration must be in GENERIC_FIELDS, marked ALWAYS and typed DURATION."""
        field = _find_field(GENERIC_FIELDS, "duration")
        assert field is not None, "duration not found in GENERIC_FIELDS"
        assert field.presence == FieldPresence.ALWAYS
        assert field.field_type == FieldType.DURATION

    # --- Fields that mirror the workout table columns ---------------------------

    def test_contains_distance(self) -> None:
        """distance (workout table column) must be present."""
        assert _find_field(GENERIC_FIELDS, "distance") is not None

    def test_contains_active_calories(self) -> None:
        """sumActiveEnergyBurned (workout table 'Calories' column) must be present."""
        assert _find_field(GENERIC_FIELDS, "sumActiveEnergyBurned") is not None

    def test_contains_average_heart_rate(self) -> None:
        """averageHeartRate (workout table 'Avg HR' column) must be present."""
        assert _find_field(GENERIC_FIELDS, "averageHeartRate") is not None

    def test_contains_elevation_ascended(self) -> None:
        """ElevationAscended (workout table 'Elevation' column) must be present."""
        assert _find_field(GENERIC_FIELDS, "ElevationAscended") is not None

    def test_avg_power_covered_by_running_schema(self) -> None:
        """averageRunningPower (workout table 'Avg Power' column) must be in the Running schema.

        This field is Running-specific (requires Apple Watch Series 8+ or Ultra) and
        therefore lives in PER_TYPE_FIELDS rather than GENERIC_FIELDS, but the combined
        schema for Running workouts must include it to mirror the workout table.
        """
        assert _find_field(PER_TYPE_FIELDS["Running"], "averageRunningPower") is not None

    # --- Optional generic fields ------------------------------------------------

    def test_optional_fields_have_optional_presence(self) -> None:
        """Sensor-dependent fields like weather and heart rate must be OPTIONAL."""
        optional_field_names = {
            "averageHeartRate",
            "minimumHeartRate",
            "maximumHeartRate",
            "WeatherTemperature",
            "WeatherHumidity",
            "ElevationAscended",
        }
        for name in optional_field_names:
            field = _find_field(GENERIC_FIELDS, name)
            assert field is not None, f"Expected optional field '{name}' not found"
            assert field.presence == FieldPresence.OPTIONAL, (
                f"Field '{name}' should be OPTIONAL, got {field.presence}"
            )


# ---------------------------------------------------------------------------
# PER_TYPE_FIELDS
# ---------------------------------------------------------------------------


class TestPerTypeFields:
    """Validate the per-type field registry."""

    _EXPECTED_TYPES = {"Running", "Cycling", "Swimming", "Hiking", "Walking"}

    def test_required_activity_types_present(self) -> None:
        """PER_TYPE_FIELDS must contain entries for the five specified activity types."""
        for activity in self._EXPECTED_TYPES:
            assert activity in PER_TYPE_FIELDS, f"'{activity}' not in PER_TYPE_FIELDS"

    def test_each_entry_is_list_of_field_definitions(self) -> None:
        """Each per-type entry must be a list of FieldDefinition instances."""
        for activity, fields in PER_TYPE_FIELDS.items():
            assert isinstance(fields, list), f"'{activity}' entry is not a list"
            for field in fields:
                assert isinstance(field, FieldDefinition), (
                    f"'{activity}' entry contains non-FieldDefinition: {field!r}"
                )

    def test_no_per_type_field_duplicates_generic_names(self) -> None:
        """Per-type fields must not redefine a field_name already in GENERIC_FIELDS.

        This prevents ambiguity and duplicate display in the detail modal.
        Exception: fields intentionally shared across specific types (e.g. sumStepCount
        for Hiking and Walking) are allowed across *different* per-type lists.
        """
        generic_names = {f.field_name for f in GENERIC_FIELDS}
        for activity, fields in PER_TYPE_FIELDS.items():
            for field in fields:
                assert field.field_name not in generic_names, (
                    f"'{activity}' field '{field.field_name}' duplicates a generic field"
                )

    # --- Running ----------------------------------------------------------------

    def test_running_has_speed(self) -> None:
        """Running fields must include average running speed."""
        assert _find_field(PER_TYPE_FIELDS["Running"], "averageRunningSpeed") is not None

    def test_running_has_cadence(self) -> None:
        """Running fields must include average running cadence."""
        assert _find_field(PER_TYPE_FIELDS["Running"], "averageRunningCadence") is not None

    def test_running_has_stride_length(self) -> None:
        """Running fields must include average stride length."""
        assert _find_field(PER_TYPE_FIELDS["Running"], "averageRunningStrideLength") is not None

    def test_running_has_power(self) -> None:
        """Running fields must include average running power."""
        assert _find_field(PER_TYPE_FIELDS["Running"], "averageRunningPower") is not None

    def test_running_has_ground_contact_time(self) -> None:
        """Running fields must include average ground contact time."""
        assert (
            _find_field(PER_TYPE_FIELDS["Running"], "averageRunningGroundContactTime") is not None
        )

    def test_running_has_vertical_oscillation(self) -> None:
        """Running fields must include average vertical oscillation."""
        assert (
            _find_field(PER_TYPE_FIELDS["Running"], "averageRunningVerticalOscillation") is not None
        )

    # --- Cycling ----------------------------------------------------------------

    def test_cycling_has_speed(self) -> None:
        """Cycling fields must include average cycling speed."""
        assert _find_field(PER_TYPE_FIELDS["Cycling"], "averageCyclingSpeed") is not None

    def test_cycling_has_cadence(self) -> None:
        """Cycling fields must include average cycling cadence."""
        assert _find_field(PER_TYPE_FIELDS["Cycling"], "averageCyclingCadence") is not None

    def test_cycling_has_power(self) -> None:
        """Cycling fields must include average cycling power."""
        assert _find_field(PER_TYPE_FIELDS["Cycling"], "averageCyclingPower") is not None

    # --- Swimming ---------------------------------------------------------------

    def test_swimming_has_stroke_count(self) -> None:
        """Swimming fields must include total stroke count."""
        assert _find_field(PER_TYPE_FIELDS["Swimming"], "sumSwimmingStrokeCount") is not None

    def test_swimming_has_lap_length(self) -> None:
        """Swimming fields must include lap length."""
        assert _find_field(PER_TYPE_FIELDS["Swimming"], "LapLength") is not None

    def test_swimming_has_location_type(self) -> None:
        """Swimming fields must include location type (pool vs open water)."""
        assert _find_field(PER_TYPE_FIELDS["Swimming"], "SwimmingLocationType") is not None

    # --- Hiking / Walking -------------------------------------------------------

    def test_hiking_has_step_count(self) -> None:
        """Hiking fields must include step count."""
        assert _find_field(PER_TYPE_FIELDS["Hiking"], "sumStepCount") is not None

    def test_walking_has_step_count(self) -> None:
        """Walking fields must include step count."""
        assert _find_field(PER_TYPE_FIELDS["Walking"], "sumStepCount") is not None

    def test_walking_has_cadence(self) -> None:
        """Walking fields must include walking cadence."""
        assert _find_field(PER_TYPE_FIELDS["Walking"], "averageWalkingCadence") is not None


# ---------------------------------------------------------------------------
# get_fields_for_activity
# ---------------------------------------------------------------------------


class TestGetFieldsForActivity:
    """Tests for the get_fields_for_activity helper function."""

    def test_known_type_returns_generic_plus_per_type(self) -> None:
        """For a known type, result must be generic fields followed by per-type fields."""
        combined = get_fields_for_activity("Running")
        generic_names = [f.field_name for f in GENERIC_FIELDS]
        running_names = [f.field_name for f in PER_TYPE_FIELDS["Running"]]
        expected_names = generic_names + running_names
        actual_names = [f.field_name for f in combined]
        assert actual_names == expected_names

    def test_unknown_type_returns_only_generic_fields(self) -> None:
        """For an unregistered activity type, only generic fields are returned."""
        combined = get_fields_for_activity("UnknownActivityType")
        assert combined == GENERIC_FIELDS

    def test_empty_string_returns_only_generic_fields(self) -> None:
        """Empty string activity type must fall back to generic fields only."""
        combined = get_fields_for_activity("")
        assert combined == GENERIC_FIELDS

    def test_returns_list_of_field_definitions(self) -> None:
        """All entries in the returned list must be FieldDefinition instances."""
        for activity in ("Running", "Cycling", "Swimming", "Hiking", "Walking", "Other"):
            combined = get_fields_for_activity(activity)
            for field in combined:
                assert isinstance(field, FieldDefinition)

    def test_no_duplicates_within_combined_list(self) -> None:
        """Combined list for any known type must not contain duplicate field_names."""
        for activity in PER_TYPE_FIELDS:
            names = [f.field_name for f in get_fields_for_activity(activity)]
            assert len(names) == len(set(names)), (
                f"Duplicate field_names in combined list for '{activity}'"
            )


# ---------------------------------------------------------------------------
# Enum display value mappings
# ---------------------------------------------------------------------------


class TestEnumDisplayValues:
    """Validate the display-value lookup tables."""

    def test_swimming_location_types_contains_pool_and_open_water(self) -> None:
        """SWIMMING_LOCATION_TYPES must map 1 → open water and 2 → pool."""
        assert SWIMMING_LOCATION_TYPES[1] == "Open Water"
        assert SWIMMING_LOCATION_TYPES[2] == "Pool"

    def test_swimming_stroke_styles_contains_known_strokes(self) -> None:
        """SWIMMING_STROKE_STYLES must include standard competitive strokes."""
        expected_strokes = {"Freestyle", "Backstroke", "Breaststroke", "Butterfly"}
        actual_strokes = set(SWIMMING_STROKE_STYLES.values())
        assert expected_strokes.issubset(actual_strokes)

    def test_enum_display_values_contains_swimming_location(self) -> None:
        """ENUM_DISPLAY_VALUES must contain a mapping for SwimmingLocationType."""
        assert "SwimmingLocationType" in ENUM_DISPLAY_VALUES
        assert ENUM_DISPLAY_VALUES["SwimmingLocationType"] is SWIMMING_LOCATION_TYPES

    def test_enum_display_values_lookup_pattern(self) -> None:
        """Consumers can safely call .get() on ENUM_DISPLAY_VALUES for unknown fields."""
        result = ENUM_DISPLAY_VALUES.get("NonExistentField", {}).get(99, "Unknown")
        assert result == "Unknown"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_field(fields: list[FieldDefinition], field_name: str) -> FieldDefinition | None:
    """Return the first FieldDefinition with the given field_name, or None."""
    return next((f for f in fields if f.field_name == field_name), None)
