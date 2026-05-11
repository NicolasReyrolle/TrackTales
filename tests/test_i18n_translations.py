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
    assert translate("No similar routes found.", language="fr") == "Aucun parcours similaire trouvé."


def test_your_rank_message_is_translated_in_french() -> None:
    """Your-rank label template should have a French translation."""
    i18n.compile_message_catalogs()
    result = translate("Your rank: {rank} of {total}", language="fr", rank="3", total="15")
    assert result == "Votre rang : 3 sur 15"
