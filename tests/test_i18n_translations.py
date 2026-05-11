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
