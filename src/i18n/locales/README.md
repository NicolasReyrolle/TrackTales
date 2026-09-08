# Translation Maintenance Guide

This folder contains gettext catalogs used by the app:

- `messages.pot`: source template (all translatable msgids extracted from Python source)
- `<lang>/LC_MESSAGES/messages.po`: editable translations for each language
- `<lang>/LC_MESSAGES/messages.mo`: compiled binary catalogs used at runtime (generated automatically at startup)

Current supported languages:

- `en/LC_MESSAGES/messages.po` (English)
- `fr/LC_MESSAGES/messages.po` (French)

> [!NOTE]
> `.mo` files are intentionally gitignored. The application compiles them on startup when missing or outdated.

## Prerequisites

Activate your virtual environment and ensure dependencies are installed:

```bash
pip install -r requirements.txt
```

`Babel` is required and pinned in `requirements.txt`.

## Translation Functions in Python Code

- `t("...")`: Active-language translation (used for almost all UI text).
- `translate("...", language=...)`: Explicit-language translation (used where the language is parameterized, e.g. calendar locale generation).
- `n_("...")`: Translation marker for module-level constants, dictionaries, or classes. Does not translate at import time, allowing `t()` to evaluate it dynamically later.

## Update Translations After UI/Text Changes

When you add or modify `t(...)`, `translate(...)`, or `n_(...)` calls in Python code:

1. **Rebuild the POT template** from source:

   ```bash
   python tools/extract_pot.py
   ```

2. **Update all language catalogs** from the new template:

   ```bash
   pybabel update --ignore-obsolete -N -i src/i18n/locales/messages.pot -d src/i18n/locales -D messages
   ```

   - `-N / --no-fuzzy-matching`: Prevents Babel from inserting fuzzy guesses that fail the test suite.
   - `--ignore-obsolete`: Automatically removes strings that no longer exist in the code.

3. **Translate new or changed entries** in each `messages.po` file:
   - `src/i18n/locales/en/LC_MESSAGES/messages.po`
   - `src/i18n/locales/fr/LC_MESSAGES/messages.po`

4. _(Optional)_ **Compile `.po` into `.mo` manually** (the app does this automatically on start):

   ```bash
   pybabel compile -d src/i18n/locales -D messages
   ```

## Add a New Language

Example: Spanish (`es`).

1. **Initialize the new language** from the template:

   ```bash
   pybabel init -i src/i18n/locales/messages.pot -d src/i18n/locales -D messages -l es
   ```

2. **Translate entries** in `src/i18n/locales/es/LC_MESSAGES/messages.po`.

3. **Register the new language** in `src/i18n/core.py`:
   - Add it to the `LANGUAGES` dictionary:

````python
     LANGUAGES: dict[str, str] = {
         "en": "English",
         "fr": "Français",
         "es": "Español",
     }
     ```

4. _(Optional)_ **Compile the new catalog**:

   ```bash
   pybabel compile -d src/i18n/locales -D messages -l es
````

## Verify Before Commit

Run translation consistency and quality tests:

```bash
pytest tests/i18n/test_translations.py tests/test_i18n_translations.py
```

Ensure the following files are staged and committed:

- `src/i18n/locales/messages.pot`
- `src/i18n/locales/<lang>/LC_MESSAGES/messages.po`

Do not commit `.mo` files.
