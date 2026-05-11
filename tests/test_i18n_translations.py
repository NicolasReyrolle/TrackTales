"""Tests for core gettext catalog entries."""

from i18n import translate


def test_route_tab_label_is_translated_in_french() -> None:
    """Workout modal Route tab should have a French translation."""
    assert translate("Route", language="fr") == "Parcours"
