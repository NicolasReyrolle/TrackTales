"""Internationalization (i18n) support for TrackTales.

Translations are stored in GNU gettext ``.po``/``.mo`` files under
``src/i18n/locales/`` and can be edited with any PO-file editor such as
`Poedit <https://poedit.net/>`_.

Provides a ``t()`` translation function that reads the current language from
NiceGUI user storage and returns the appropriate translated string.
"""

import gettext
import logging
from functools import cache
from pathlib import Path
from typing import cast

from babel.messages import mofile, pofile

DEFAULT_LANGUAGE: str = "en"

LANGUAGES: dict[str, str] = {
    "en": "English",
    "fr": "Français",
}

_DOMAIN = "messages"
_LOCALE_DIR = Path(__file__).parent / "locales"
_logger = logging.getLogger(__name__)

__all__ = [
    "DEFAULT_LANGUAGE",
    "LANGUAGES",
    "compile_message_catalogs",
    "get_language",
    "t",
    "translate",
]


class _POTranslations(gettext.NullTranslations):
    """Translation object backed by gettext ``.po`` files.

    This is used as a development fallback when compiled ``.mo`` files are
    not available yet.
    """

    def __init__(self, messages: dict[str, str]) -> None:
        super().__init__()
        self._messages = messages

    def gettext(self, message: str) -> str:
        translated = self._messages.get(message)
        if translated:
            return translated
        return message


def _load_po_translation(lang: str) -> gettext.NullTranslations:
    """Load translations from a ``.po`` file for *lang* if present."""
    po_path = _LOCALE_DIR / lang / "LC_MESSAGES" / f"{_DOMAIN}.po"
    if not po_path.exists():
        return gettext.NullTranslations()

    with po_path.open("r", encoding="utf-8") as po_file:
        catalog = pofile.read_po(po_file)

    messages = {
        message.id: message.string
        for message in catalog
        if isinstance(message.id, str)
        and isinstance(message.string, str)
        and message.id
        and message.string
    }
    return _POTranslations(messages)


def _compile_po_catalog(po_path: Path) -> bool:
    """Compile one ``.po`` file to its sibling ``.mo`` file.

    Returns ``True`` if the catalog was compiled, ``False`` if no compilation was needed.
    """
    mo_path = po_path.with_suffix(".mo")

    if mo_path.exists() and mo_path.stat().st_mtime >= po_path.stat().st_mtime:
        return False

    with po_path.open("r", encoding="utf-8") as po_file:
        catalog = pofile.read_po(po_file)
    with mo_path.open("wb") as mo_file:
        mofile.write_mo(mo_file, catalog)
    return True


def compile_message_catalogs() -> int:
    """Compile all gettext ``.po`` catalogs under ``locales`` into ``.mo`` files.

    Returns the number of catalogs that were (re)compiled.  Permission errors
    (e.g. read-only installed environments) are logged at DEBUG level so that
    startup is not noisy in production deployments.
    """
    compiled_count = 0
    for po_path in _LOCALE_DIR.glob("*/LC_MESSAGES/*.po"):
        try:
            if _compile_po_catalog(po_path):
                compiled_count += 1
        except PermissionError:
            _logger.debug(
                "Cannot write compiled catalog for '%s': directory is not writable.", po_path
            )
        except Exception as exc:
            _logger.warning("Failed to compile translation catalog '%s': %s", po_path, exc)

    # Ensure subsequent translation lookups reload catalogs after recompilation.
    _get_translation.cache_clear()
    return compiled_count


@cache
def _get_translation(lang: str) -> gettext.NullTranslations:
    """Load and cache the compiled ``.mo`` translation for *lang*.

    Returns a :class:`~gettext.NullTranslations` instance (which passes
    strings through unchanged) when no compiled catalog is found for *lang*.
    This means English strings are always returned as-is without needing an
    English ``.mo`` file.
    """
    try:
        return gettext.translation(_DOMAIN, localedir=str(_LOCALE_DIR), languages=[lang])
    except FileNotFoundError:
        _logger.debug("No compiled .mo catalog for '%s'; trying .po fallback", lang)
        return _load_po_translation(lang)


def get_language() -> str:
    """Return the active language code from NiceGUI user storage.

    Falls back to ``DEFAULT_LANGUAGE`` when storage is not available
    (e.g., during unit tests that do not set up a NiceGUI session).
    """
    try:
        from nicegui import app

        user_storage = cast(dict[str, object], app.storage.user)
        return str(user_storage.get("language", DEFAULT_LANGUAGE))
    except Exception:
        return DEFAULT_LANGUAGE


def t(message: str, **kwargs: str) -> str:
    """Translate *message* into the currently selected language.

    Uses standard GNU gettext look-up: *message* is the English source string
    (the ``msgid`` in the ``.po`` file).  When no translation is available the
    original *message* is returned unchanged so the UI always shows readable
    text.

    Extra keyword arguments are forwarded to :meth:`str.format` so that
    dynamic values can be injected into the translated string::

        t("Count by {period}", period=t("month"))
        # → "Count by month"   (English)
        # → "Nombre par mois"  (French)
    """
    lang = get_language()
    result = translate(message, language=lang)
    if kwargs:
        try:
            return result.format(**kwargs)
        except (KeyError, ValueError) as exc:
            _logger.warning(
                "Failed to format translation for message '%s' in language '%s': %s",
                message,
                lang,
                exc,
            )
            return result
    return result


def translate(message: str, language: str, **kwargs: str) -> str:
    """Translate *message* into the provided *language* code."""
    translation = _get_translation(language)
    result = translation.gettext(message)
    if kwargs:
        try:
            return result.format(**kwargs)
        except (KeyError, ValueError) as exc:
            _logger.warning(
                "Failed to format translation for message '%s' in language '%s': %s",
                message,
                language,
                exc,
            )
            return result
    return result
