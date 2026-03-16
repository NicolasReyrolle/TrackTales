"""Tests for i18n activity type translation helpers."""

from i18n.activity_types import (
    HK_WORKOUT_ACTIVITY_TYPES,
    activity_display_label,
    build_activity_select_options,
    normalize_activity_type,
    translate_activity_value_map,
)


def test_hk_workout_activity_types_has_complete_known_set() -> None:
    """Ensure the known enum list includes all currently documented values."""
    assert "Running" in HK_WORKOUT_ACTIVITY_TYPES
    assert "SwimBikeRun" in HK_WORKOUT_ACTIVITY_TYPES
    assert "UnderwaterDiving" in HK_WORKOUT_ACTIVITY_TYPES
    assert "Other" in HK_WORKOUT_ACTIVITY_TYPES
    assert len(HK_WORKOUT_ACTIVITY_TYPES) >= 84


def test_normalize_activity_type_strips_healthkit_prefix() -> None:
    """HealthKit-prefixed values should normalize to enum names."""
    assert normalize_activity_type("HKWorkoutActivityTypeRunning") == "Running"


def test_activity_display_label_translates_well_known_values() -> None:
    """Known activity labels should be humanized and translatable."""
    assert activity_display_label("TaiChi") == "Tai Chi"
    assert activity_display_label("HighIntensityIntervalTraining") == (
        "High Intensity Interval Training"
    )


def test_activity_display_label_falls_back_for_unknown_values() -> None:
    """Unknown activity names should still display cleanly for users."""
    assert activity_display_label("UltraTrailRun") == "Ultra Trail Run"


def test_build_activity_select_options_preserves_raw_values() -> None:
    """Select options must keep raw values used by filtering logic."""
    options = build_activity_select_options(["All", "Running", "TaiChi"])

    assert options["All"] == "All"
    assert options["Running"] == "Running"
    assert options["TaiChi"] == "Tai Chi"


def test_translate_activity_value_map_translates_keys_only() -> None:
    """Chart data should keep values while translating activity labels."""
    translated = translate_activity_value_map({"TaiChi": 2, "Others": 1})

    assert translated == {"Tai Chi": 2, "Others": 1}


def test_build_activity_select_options_disambiguates_duplicate_labels() -> None:
    """Duplicate display labels should be disambiguated using the raw value."""
    options = build_activity_select_options(["Running", "HKWorkoutActivityTypeRunning"])

    assert options["Running"] == "Running"
    assert options["HKWorkoutActivityTypeRunning"] == "Running (HKWorkoutActivityTypeRunning)"


def test_translate_activity_value_map_merges_label_collisions() -> None:
    """When two raw labels map to same display label, their values should be summed."""
    translated = translate_activity_value_map({"Running": 2, "HKWorkoutActivityTypeRunning": 3})

    assert translated == {"Running": 5}
