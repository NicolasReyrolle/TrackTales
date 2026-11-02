---
description: "Use when writing or editing tests under tests/. Covers fixture rules, mocking conventions, and floating-point comparisons."
applyTo: "tests/**"
excludeAgent: "code-review"
---

# Test Fixtures and Mocking

- Never modify existing files under `tests/fixtures/exports`.
- If an existing export fixture contains incorrect data that a bug fix depends on, do not edit it. Add a new fixture file with a descriptive name (e.g., `tests/fixtures/exports/<scenario>_v2.<ext>`) and point the new test at it, then note the superseded fixture in the test docstring.
- For new scenarios, add new fixture files or construct data in tests.
- Prefer centralized fixtures/helpers in `tests/conftest.py` instead of ad-hoc inline mocks.
- When patching NiceGUI objects, patch the name where the code under test looks it up (e.g., `patch('myapp.pages.ui.button')`), not where NiceGUI defines it (e.g., `patch('nicegui.ui.button')`).
- Never compare floating-point values with `==`; use `pytest.approx`.

## TDD policy
- Write a failing test before the fix or implementation for every bug fix and new logic function. Skip test-first only when the code cannot be exercised in isolation, and note the reason in the commit message.
- For trivial refactors/renames/doc-only changes, add or update tests only if the change alters a return value, raised exception, side effect, or public API signature.
