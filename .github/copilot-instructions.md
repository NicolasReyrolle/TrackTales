# TrackTales - AI Coding Agent Instructions

## Rule precedence

When instructions conflict, apply this order:
1. Safety and platform policy
2. Explicit user request for the current task
3. This repository instruction file
4. General style preferences

If two rules at the same level conflict, choose the option with fewer implementation steps or dependencies, prioritizing user-facing simplicity, and state the assumption.
If a user request is ambiguous or incomplete, apply repository instructions that best match the stated intent and document the assumption in your response.

## Project overview

**Purpose**: NiceGUI app that parses Apple Health exports (ZIP containing XML/GPX) and presents workout analytics.

**Core modules**:
- `src/tracktales.py` - app entrypoint and `@ui.page` registration
- `src/app_state.py` - shared UI/data singleton state
- `src/ui/layout.py` - UI composition (header, drawer, tabs, charts)
- `src/ui/css.py` - all CSS class/props string constants (single source of truth)
- `src/ui/charts.py` - reusable chart and stat-card components
- `src/ui/local_file_picker.py` - local file picker dialog
- `src/ui/helpers.py` - label/date/duration/distance formatters
- `src/logic/export_parser.py` - ZIP/XML/GPX parsing (`ExportParser`)
- `src/logic/workout_manager/` - workout aggregations/export/segment features
- `src/logic/workout_route.py` - `WorkoutRoute`/`RoutePoint`, route metrics, segment search
- `tests/` - unit tests for logic, UI, i18n

**Data flow**: page load → file selection → `load_workouts_from_file()` → parse with `ExportParser` → store in `AppState` → refresh tabs/views.

## Development commands

- Setup (Windows): `.\.venv\Scripts\Activate.ps1`
- Run app: `python -m nicegui src.tracktales`
- Tests: `pytest --cov=src tests/`
- Quality: `ruff format src tests`, `ruff check src tests`, `mypy src tests`

## Mandatory engineering constraints

### Parsing and security
- Keep XML parsing on `defusedxml` (never switch to stdlib `ElementTree` for untrusted XML parsing).
- Preserve streaming parsing patterns (`iterparse` + `elem.clear()`) for large files.
- `ExportParser` remains a context manager and should be used with `with ExportParser() as ep:`.
- If an Apple Health export is invalid or corrupted and cannot be parsed, display an error message and log the issue.

### CSS and styling
- All Tailwind/Quasar class strings and NiceGUI `.props()` strings live in `src/ui/css.py` as named constants (`*_CLASSES` / `*_PROPS`).  Import and use them instead of writing inline string literals.
- `resources/style.css` is the single global stylesheet.  Add new CSS classes there rather than using `.style(...)` inline styles.  Every class added must be documented with a comment explaining its purpose.
- Inline styles (`style="..."` in Vue templates or `.style(...)` in Python) are forbidden unless strictly unavoidable; document any surviving inline styles with a comment in both the template and `style.css`.
- ECharts (`ui.echart`) must include `"backgroundColor": "transparent"` in every chart config so the card background (which adapts to dark mode via CSS) shows through correctly.

### Test fixtures and mocking
- Never modify existing files under `tests/fixtures/exports`.
- For new scenarios, add new fixture files or construct data in tests.
- Prefer centralized fixtures/helpers in `tests/conftest.py` instead of ad-hoc inline mocks.
- For patching NiceGUI objects, patch module-level lookups to support runtime patching.

### Data and numeric handling
- Convert numeric XML attributes/values to `int`/`float` at parse time.
- In tests, never compare floating-point values with `==`; use `pytest.approx`.

## Coding workflow

### Before coding
- Identify impacted files and adjacent tests.
- Reuse existing patterns and naming.
- Prefer minimal, targeted changes over broad refactors.

### During coding
- Fix root cause; avoid cosmetic unrelated edits.
- Keep public APIs stable unless the task explicitly requests API changes. Do not use compatibility layers unless absolutely necessary.
- Use `# noqa: ...` or `# type: ignore` only when necessary and scoped to the smallest
  expression/line.
- Keep cognitive complexity low; break down complex functions into smaller helpers. Maximum complexity of 15 per function.
- Keep functions under 50 lines where practical. If a function exceeds this, consider refactoring into smaller functions.
- Each module must contain less than 1000 lines of code. This limit applies to both source and test files. If a module exceeds this, consider splitting it into smaller, focused modules (e.g. by feature area or tab).
- Any `__init__.py` content should be kept to a minimum, without much logic inside. Only imports and real setup would be preferable.

### After coding
- Run `ruff format src tests`

### Validation scope (default)
- Validate changed files and directly affected tests first.
- Run wider suites (`tests/`, full lint, full type-check) only when:
  - requested by the user, or
  - risk is high (cross-cutting parser/model/UI changes).

### TDD policy
- Use TDD for bug fixes and new logic where practical.
- For trivial refactors/renames/doc-only changes, add or update tests only if behavior meaningfully changes.
- Do not perform equality checks with floating point values. Use `pytest.approx` for comparisons in tests.

## Definition of done

A task is complete when all of the following are true:
1. Requested behavior is implemented.
2. Changed files are lint/type clean (or existing unrelated issues are explicitly called out).
	Use both Pylance and Ruff for type/lint checks.
3. Relevant tests pass.
4. Any new assumptions, trade-offs, or follow-ups are clearly reported.

## Key file map

| File | Responsibility |
|---|---|
| `src/tracktales.py` | App entrypoint, page registration, CLI args |
| `src/app_state.py` | Shared application state |
| `src/ui/layout.py` | Main UI rendering/composition |
| `src/ui/css.py` | All CSS class/props string constants (single source of truth) |
| `src/ui/charts.py` | Reusable chart and stat-card components |
| `src/ui/local_file_picker.py` | Local file picker dialog UI |
| `src/ui/helpers.py` | UI formatting utilities |
| `src/logic/export_parser.py` | Health export parsing, route loading |
| `src/logic/workout_manager/` | Aggregations and reporting utilities |
| `src/logic/workout_route.py` | Route models and route computations |
| `tests/conftest.py` | Shared fixtures and test helpers |
| `pyproject.toml` | Tooling configuration (pytest/mypy/ruff/formatters) |
| `resources/style.css` | Global CSS: dark-mode vars, Quasar overrides, utility classes |

## CI expectations

CI validates tests and quality checks on PRs. Keep local changes aligned with configured tooling and avoid introducing new warnings in touched code.

## Example responses

### Small fix (single file)
"Updated `src/logic/workout_route.py` to avoid float equality in the segment guard. Ran `pytest tests/logic/test_workout_route.py -q` (all passing). No API changes."

### Multi-file change
"Implemented the requested metric in `src/logic/workout_manager/` and wired it in `src/ui/layout.py`, with tests in `tests/logic/test_workout_manager_totals.py`. Validated changed tests and ran targeted lint/type checks for touched files."

### Blocked case
"I could not complete the change because the required fixture is missing and must be provided by a human (`tests/fixtures/exports/...`). I made no destructive edits. If you add the fixture, I can finish by adding parser handling and tests in one pass."
