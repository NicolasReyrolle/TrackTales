"""Tests for core gettext catalog entries."""

import i18n
from i18n import translate


def test_route_tab_label_is_translated_in_french() -> None:
    """Workout modal Route tab should have a French translation."""
    i18n.compile_message_catalogs()
    assert translate("Route", language="fr") == "Parcours"


def test_route_map_tooltip_labels_are_translated_in_french() -> None:
    """Route map tooltip labels should have French translations."""
    i18n.compile_message_catalogs()
    assert translate("Route {index}", language="fr", index="2") == "Parcours 2"
    assert translate("Start", language="fr") == "Départ"
    assert translate("End", language="fr") == "Arrivée"


def test_comparisons_tab_label_is_translated_in_french() -> None:
    """Workout modal Comparisons tab should have a French translation."""
    i18n.compile_message_catalogs()
    assert translate("Comparisons", language="fr") == "Comparaisons"


def test_no_similar_routes_message_is_translated_in_french() -> None:
    """No-similar-routes empty-state message should have a French translation."""
    i18n.compile_message_catalogs()
    assert (
        translate("No similar routes found.", language="fr") == "Aucun parcours similaire trouvé."
    )


def test_your_rank_message_is_translated_in_french() -> None:
    """Rank label template should have a French translation."""
    i18n.compile_message_catalogs()
    result = translate("Rank: {rank} of {total}", language="fr", rank="3", total="15")
    assert result == "Rang : 3 sur 15"


def test_diff_column_label_is_translated_in_french() -> None:
    """Diff column header should have a French translation."""
    i18n.compile_message_catalogs()
    assert translate("Diff", language="fr") == "Écart"


def test_non_physical_w_prime_warning_strings_are_translated_in_french() -> None:
    """Running-tab non-physical W' warning strings should have French translations."""
    i18n.compile_message_catalogs()
    warning_message = (
        "W' <= 0 is non-physical in the CP model. "
        "This usually means sparse data or inconsistent "
        "pace/power estimates for those periods."
    )
    warning_translation = (
        "W' <= 0 est non physique dans le modèle de PC. "
        "Cela indique généralement des données clairsemées "
        "ou des estimations d'allure/puissance incohérentes "
        "pour ces périodes."
    )
    assert translate("Non-physical W'", language="fr") == "W' non physique"
    assert translate(warning_message, language="fr") == warning_translation
    assert translate("Periods", language="fr") == "Périodes"
