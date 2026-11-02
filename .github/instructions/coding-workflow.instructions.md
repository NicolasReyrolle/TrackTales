---
description: "Use when writing or modifying code in src/ or tests/. Covers the before/during/after coding workflow, code size and complexity limits, constants placement, and validation scope."
applyTo: "src/**,tests/**"
excludeAgent: "code-review"
---

# Coding Workflow

## Before coding
- Identify impacted files and adjacent tests.
- Reuse existing patterns and naming.
- Prefer minimal, targeted changes over broad refactors. The function complexity and length limits may require refactoring the affected function; the module size limit may require splitting the affected module.

## During coding
- Fix root cause; avoid cosmetic unrelated edits (the formatting step in "After coding" is the only exception, and it must not reformat files you did not change).
- Put every new application setting, configurable default, or settings-candidate constant in `src/logic/constants.py` so it can serve as the source for a future user settings UI; do not define these in feature modules. Document each tunable constant's meaning, units/range where relevant, and the behavioral consequences of increasing or decreasing it in `constants.py`. Keep CSS-only constants in `src/ui/css.py`.
- Keep public APIs stable unless the task explicitly requests API changes. Do not use compatibility layers unless absolutely necessary.
- Use `# noqa: ...` or `# type: ignore` only when necessary and scoped to the smallest
  expression/line.
- Break down complex functions into smaller helpers. Maximum cyclomatic complexity of 15 per function, as measured by mccabe (ruff rule C901).
- Keep functions under 50 lines. If a function must exceed 50 lines, state the reason in the response.
- Each module must contain fewer than 1000 lines of code, for source and test files. If a change would push a module to 1000 or more lines, split it into smaller modules by feature area or tab before finishing, and report the split in the response. This rule overrides the "minimal, targeted changes" preference; limit the split to the affected module.
- In `__init__.py` files, allow only import statements and `__all__` declarations. Do not add functions, classes, variables with logic, or side effects.

## After coding
- Run `ruff format` on the files you changed (not whole directories), so untouched files are not reformatted. Run `ruff format src tests` only if the user asks.

## Validation scope (default)
- Validate changed files and directly affected tests first.
- Run wider suites (`tests/`, full lint, full type-check) only when:
  - requested by the user, or
  - the change edits more than one of `src/logic/export_parser.py`, `src/logic/workout_route.py`, `src/ui/layout.py`, or any file under `src/logic/workout_manager/`, or changes a shared model or a public function signature.
