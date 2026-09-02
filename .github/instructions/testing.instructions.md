---
description: "Use when writing or editing tests under tests/. Covers fixture rules, mocking conventions, and floating-point comparisons."
applyTo: "tests/**"
---

# Test Fixtures and Mocking

- Never modify existing files under `tests/fixtures/exports`.
- For new scenarios, add new fixture files or construct data in tests.
- Prefer centralized fixtures/helpers in `tests/conftest.py` instead of ad-hoc inline mocks.
- For patching NiceGUI objects, patch module-level lookups to support runtime patching.
- Never compare floating-point values with `==`; use `pytest.approx`.

## TDD policy
- Use TDD for bug fixes and new logic where practical.
- For trivial refactors/renames/doc-only changes, add or update tests only if behavior meaningfully changes.
