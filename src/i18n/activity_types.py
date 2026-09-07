"""Helpers to localize Apple Health workout activity types for display.

Raw values are preserved for filtering and exports. These helpers only translate
labels shown in the UI.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping

from i18n import t

_logger = logging.getLogger(__name__)


def n_(message: str) -> str:
    """Dummy marker for Babel extraction. Returns the raw string."""
    return message


# Complete public HKWorkoutActivityType set (including deprecated legacy values)
# collected from Apple HealthKit API documentation.
HK_WORKOUT_ACTIVITY_TYPES = frozenset(
    {
        n_("AmericanFootball"),
        n_("Archery"),
        n_("AustralianFootball"),
        n_("Badminton"),
        n_("Baseball"),
        n_("Basketball"),
        n_("Barre"),
        n_("Bowling"),
        n_("Boxing"),
        n_("CardioDance"),
        n_("Climbing"),
        n_("Cooldown"),
        n_("CoreTraining"),
        n_("Cricket"),
        n_("CrossCountrySkiing"),
        n_("CrossTraining"),
        n_("Curling"),
        n_("Cycling"),
        n_("Dance"),
        n_("DanceInspiredTraining"),
        n_("DiscSports"),
        n_("DownhillSkiing"),
        n_("Elliptical"),
        n_("EquestrianSports"),
        n_("Fencing"),
        n_("Fishing"),
        n_("FitnessGaming"),
        n_("Flexibility"),
        n_("FunctionalStrengthTraining"),
        n_("Golf"),
        n_("Gymnastics"),
        n_("HandCycling"),
        n_("Handball"),
        n_("HighIntensityIntervalTraining"),
        n_("Hiking"),
        n_("Hockey"),
        n_("Hunting"),
        n_("JumpRope"),
        n_("Kickboxing"),
        n_("Lacrosse"),
        n_("MartialArts"),
        n_("MindAndBody"),
        n_("MixedCardio"),
        n_("MixedMetabolicCardioTraining"),
        n_("Other"),
        n_("PaddleSports"),
        n_("Pickleball"),
        n_("Pilates"),
        n_("Play"),
        n_("PreparationAndRecovery"),
        n_("Racquetball"),
        n_("Rowing"),
        n_("Rugby"),
        n_("Running"),
        n_("Sailing"),
        n_("SkatingSports"),
        n_("Snowboarding"),
        n_("SnowSports"),
        n_("Soccer"),
        n_("SocialDance"),
        n_("Softball"),
        n_("Squash"),
        n_("StairClimbing"),
        n_("Stairs"),
        n_("StepTraining"),
        n_("SurfingSports"),
        n_("SwimBikeRun"),
        n_("Swimming"),
        n_("TableTennis"),
        n_("TaiChi"),
        n_("Tennis"),
        n_("TrackAndField"),
        n_("TraditionalStrengthTraining"),
        n_("Transition"),
        n_("UnderwaterDiving"),
        n_("Volleyball"),
        n_("Walking"),
        n_("WaterFitness"),
        n_("WaterPolo"),
        n_("WaterSports"),
        n_("WheelchairRunPace"),
        n_("WheelchairWalkPace"),
        n_("Wrestling"),
        n_("Yoga"),
    }
)

_DISPLAY_LABEL_OVERRIDES = {
    "All": n_("All"),
    "Others": n_("Others"),
}

_logged_unknown_activity_types: set[str] = set()


def _humanize_camel_case(value: str) -> str:
    """Convert camel-cased enum names to human-readable labels."""
    return re.sub(r"(?<!^)(?=[A-Z])", " ", value).strip()


def normalize_activity_type(activity_type: str) -> str:
    """Normalize Apple Health activity type values to canonical enum names."""
    normalized = activity_type.replace("HKWorkoutActivityType", "", 1)
    return normalized or activity_type


def activity_display_label(activity_type: str) -> str:
    """Return translated label for an activity type value."""
    normalized = normalize_activity_type(activity_type)
    if normalized in _DISPLAY_LABEL_OVERRIDES:
        return t(_DISPLAY_LABEL_OVERRIDES[normalized])

    if normalized in HK_WORKOUT_ACTIVITY_TYPES:
        return t(normalized)

    if normalized not in _logged_unknown_activity_types:
        _logged_unknown_activity_types.add(normalized)
        _logger.warning(
            "Unknown workout activity type '%s'. Falling back to humanized label.", normalized
        )
    return t(_humanize_camel_case(normalized))


def build_activity_select_options(activity_options: list[str]) -> dict[str, str]:
    """Build translated dropdown options while preserving raw activity values.

    NiceGUI `ui.select` expects dictionary options in the form
    `{value: label}`. The selected value remains the raw activity type.
    """
    translated_options: dict[str, str] = {}
    used_labels: set[str] = set()
    for raw_value in activity_options:
        display_label = activity_display_label(raw_value)
        if display_label in used_labels:
            display_label = f"{display_label} ({raw_value})"
        translated_options[raw_value] = display_label
        used_labels.add(display_label)
    return translated_options


def translate_activity_value_map(values: Mapping[str, float | int]) -> dict[str, float | int]:
    """Translate activity names in metric maps and merge label collisions if needed."""
    translated: dict[str, float | int] = {}
    for raw_label, metric_value in values.items():
        translated_label = activity_display_label(raw_label)
        if translated_label in translated:
            translated[translated_label] += metric_value
        else:
            translated[translated_label] = metric_value
    return translated
