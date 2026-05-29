"""Internationalization (i18n) support for TrackTales."""

from i18n._core import (
    DEFAULT_LANGUAGE,
    LANGUAGES,
    compile_message_catalogs,
    get_language,
    t,
    translate,
)

__all__ = [
    "DEFAULT_LANGUAGE",
    "LANGUAGES",
    "compile_message_catalogs",
    "get_language",
    "t",
    "translate",
]
