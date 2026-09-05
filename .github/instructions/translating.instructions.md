---
description: "Use when adding, changing, or removing translatable strings (t(...) / translate(...)) in src/, or touching src/i18n/**. Covers the gettext catalog workflow documented in src/i18n/locales/README.md."
applyTo: "src/**"
---

# Translation Workflow Policy

Full details: [src/i18n/locales/README.md](../../src/i18n/locales/README.md). Follow it exactly; this file is a summary/checklist.

- Never hardcode translated literals in `.py` files. All user-facing strings must go through `t("...")` or `translate("...", language=...)`.
- After adding/changing/removing any `t("...")` or `translate(...)` call anywhere in `src/`:
  1. Regenerate the template: `python tools/extract_pot.py`
  2. Update each existing language catalog, e.g. French: `pybabel update --ignore-obsolete -i src/i18n/locales/messages.pot -d src/i18n/locales -D messages -l fr`
  3. Translate new/changed entries in each `src/i18n/locales/<lang>/LC_MESSAGES/messages.po`. Do not leave new msgids untranslated.
  4. Do not commit compiled `.mo` files — they are gitignored and generated at runtime (`compile_message_catalogs`).
- When adding a new language, follow the "Add a New Language" steps in the README, including registering it in the `LANGUAGES` dict in `src/i18n/__init__.py`.
- Before finishing a task that touched translatable strings, run `pytest tests/i18n/test_translations.py` and ensure it passes.
- Commit `messages.pot` and all updated `.po` files alongside the code change.
