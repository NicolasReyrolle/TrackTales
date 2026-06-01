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


class _POTranslations(gettext.NullTranslations):
    def __init__(self, messages: dict[str, str]) -> None:
        super().__init__()
        self._messages = messages

    def gettext(self, message: str) -> str:
        return self._messages.get(message) or message


def _load_po_translation(lang: str) -> gettext.NullTranslations:
    po_path = _LOCALE_DIR / lang / "LC_MESSAGES" / f"{_DOMAIN}.po"
    if not po_path.exists():
        return gettext.NullTranslations()
    with po_path.open("r", encoding="utf-8") as f:
        catalog = pofile.read_po(f)
    messages = {
        m.id: m.string
        for m in catalog
        if isinstance(m.id, str) and isinstance(m.string, str) and m.id and m.string
    }
    return _POTranslations(messages)


def _compile_po_catalog(po_path: Path) -> bool:
    mo_path = po_path.with_suffix(".mo")
    if mo_path.exists() and mo_path.stat().st_mtime >= po_path.stat().st_mtime:
        return False
    with po_path.open("r", encoding="utf-8") as f:
        catalog = pofile.read_po(f)
    with mo_path.open("wb") as f:
        mofile.write_mo(f, catalog)
    return True


def compile_message_catalogs() -> int:
    compiled = 0
    for po_path in _LOCALE_DIR.glob("*/LC_MESSAGES/*.po"):
        try:
            if _compile_po_catalog(po_path):
                compiled += 1
        except PermissionError:
            _logger.debug(
                "Cannot write compiled catalog for '%s': directory is not writable.", po_path
            )
        except Exception as exc:
            _logger.warning("Failed to compile translation catalog '%s': %s", po_path, exc)
    _get_translation.cache_clear()
    return compiled


@cache
def _get_translation(lang: str) -> gettext.NullTranslations:
    try:
        return gettext.translation(_DOMAIN, localedir=str(_LOCALE_DIR), languages=[lang])
    except FileNotFoundError:
        _logger.debug("No compiled .mo catalog for '%s'; trying .po fallback", lang)
        return _load_po_translation(lang)


def get_language() -> str:
    try:
        from nicegui import app

        return str(cast(dict[str, object], app.storage.user).get("language", DEFAULT_LANGUAGE))
    except Exception:
        return DEFAULT_LANGUAGE


def translate(message: str, language: str, **kwargs: str) -> str:
    result = _get_translation(language).gettext(message)
    if kwargs:
        try:
            return result.format(**kwargs)
        except (KeyError, ValueError) as exc:
            _logger.warning(
                "Failed to format translation '%s' in language '%s': %r", message, language, exc
            )
    return result


def t(message: str, **kwargs: str) -> str:
    lang = get_language()
    result = translate(message, language=lang)
    if kwargs:
        try:
            return result.format(**kwargs)
        except (KeyError, ValueError) as exc:
            _logger.warning(
                "Failed to format translation '%s' in language '%s': %r", message, lang, exc
            )
            return result
    return result
