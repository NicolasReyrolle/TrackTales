"""Tests for i18n catalog compilation helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

import i18n as i18n

_MINIMAL_PO = """msgid ""
msgstr ""
"Language: fr\\n"
"Content-Type: text/plain; charset=UTF-8\\n"

msgid "Hello"
msgstr "Bonjour"
"""


def _make_po_file(locales_root: Path) -> Path:
    po_path = locales_root / "fr" / "LC_MESSAGES" / "messages.po"
    po_path.parent.mkdir(parents=True, exist_ok=True)
    po_path.write_text(_MINIMAL_PO, encoding="utf-8")
    return po_path


def test_compile_message_catalogs_creates_missing_mo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Compilation should generate .mo files when missing."""
    locales_root = tmp_path / "locales"
    po_path = _make_po_file(locales_root)
    monkeypatch.setattr(i18n, "_LOCALE_DIR", locales_root)

    compiled_count = i18n.compile_message_catalogs()

    assert compiled_count == 1
    assert po_path.with_suffix(".mo").exists()


def test_compile_message_catalogs_skips_up_to_date_mo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Compilation should skip catalogs when .mo is already up to date."""
    locales_root = tmp_path / "locales"
    _make_po_file(locales_root)
    monkeypatch.setattr(i18n, "_LOCALE_DIR", locales_root)

    first_count = i18n.compile_message_catalogs()
    second_count = i18n.compile_message_catalogs()

    assert first_count == 1
    assert second_count == 0
