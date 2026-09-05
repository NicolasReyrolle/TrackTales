# Translation Maintenance Guide

This folder contains gettext catalogs used by the app:

- `messages.pot`: source template (all translatable English msgids)
- `<lang>/LC_MESSAGES/messages.po`: editable translations for each language
- `<lang>/LC_MESSAGES/messages.mo`: compiled binary catalogs used at runtime (generated automatically at startup)

Current language example:

- `fr/LC_MESSAGES/messages.po`

Note: `.mo` files are intentionally gitignored in this repository. The app compiles them on startup when missing or outdated.

## Prerequisites

Activate your virtual environment, then ensure dependencies are installed:

```bash
pip install -r requirements.txt
```

`Babel` is required and already pinned in `requirements.txt`.

## Update Translations After UI/Text Changes

When you add or change calls like `t("...")` or `translate("...", language=...)` in Python code:

1. Rebuild the POT template from source using the helper script:

```bash
python tools/extract_pot.py
```

Notes:

- Keep translatable user-facing strings in gettext catalogs (`.po`/`.mo`), not hardcoded translated literals in `.py` files.
- `translate(...)` is used in a few places that require an explicit language code (for example locale payload generation), so `-k translate` must be included during extraction.

1. Update existing language files from the new template (example for French):

```bash
pybabel update --ignore-obsolete -i src/i18n/locales/messages.pot -d src/i18n/locales -D messages -l fr
```

1. Open `src/i18n/locales/fr/LC_MESSAGES/messages.po` and translate any new/changed entries.

1. (Optional) Compile the `.po` into `.mo` manually:

```bash
pybabel compile -d src/i18n/locales -D messages -l fr
```

## Add a New Language

Example: Spanish (`es`).

1. Initialize the new language from the template:

```bash
pybabel init -i src/i18n/locales/messages.pot -d src/i18n/locales -D messages -l es
```

1. Translate entries in:

- `src/i18n/locales/es/LC_MESSAGES/messages.po`

1. Compile the catalog:

```bash
pybabel compile -d src/i18n/locales -D messages -l es
```

1. Register the new language in `src/i18n/__init__.py`:

- Add it to the `LANGUAGES` dict, for example: `"es": "Espanol"`

## Compile All Languages

```bash
pybabel compile -d src/i18n/locales -D messages
```

## Verify Before Commit

Run translation consistency tests:

```bash
pytest tests/i18n/test_translations.py
```

Make sure these files are committed:

- `src/i18n/locales/messages.pot`
- `src/i18n/locales/<lang>/LC_MESSAGES/messages.po`

Do not commit compiled `.mo` files; they are generated at runtime.
