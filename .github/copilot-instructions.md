# TrackTales - AI Coding Agent Instructions

## Rule precedence

Order: safety and platform policy > explicit user request > this file and `.github/instructions/` > general style preferences. For same-level conflicts or ambiguous requests, choose the simplest option and state the assumption.

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
- `src/logic/export_parser.py` - ZIP/XML/GPX parsing (`ExportParser`), route loading
- `src/logic/workout_manager/` - workout aggregations/export/segment features
- `src/logic/workout_route.py` - `WorkoutRoute`/`RoutePoint`, route metrics, segment search
- `tests/` - unit tests for logic, UI, i18n; `tests/conftest.py` holds shared fixtures and helpers
- `pyproject.toml` - tooling configuration (pytest/mypy/ruff/formatters)
- `resources/style.css` - global CSS: dark-mode vars, Quasar overrides, utility classes

**Data flow**: page load → file selection → `load_workouts_from_file()` → parse with `ExportParser` → store in `AppState` → refresh tabs/views.

## Development commands

- Setup (Windows): `.\.venv\Scripts\Activate.ps1`
- Run app: `python -m nicegui src.tracktales`
- Tests: `pytest --cov=src tests/`
- Quality: `ruff format <files>`, `ruff check <files>`, `mypy <files>` (scope rules: `instructions/coding-workflow.instructions.md`)
- If a required command cannot run in the current environment (for example, the Windows venv activation on another OS, or a missing dependency), do not claim the check passed. Name the skipped command and the reason in the response, and list it as a follow-up.

## Topic-specific instructions

More detailed, path-scoped rules live under `.github/instructions/` and are auto-attached when editing matching files:
- [parsing-security.instructions.md](instructions/parsing-security.instructions.md) - `src/logic/**` (XML parsing, security, numeric handling)
- [ui-styling.instructions.md](instructions/ui-styling.instructions.md) - `src/ui/**` (CSS/Tailwind/Quasar conventions)
- [testing.instructions.md](instructions/testing.instructions.md) - `tests/**` (fixtures, mocking, TDD, float comparisons)
- [translating.instructions.md](instructions/translating.instructions.md) - `src/i18n/**` and any new/changed translatable strings (gettext catalog workflow)
- [commit-messages.instructions.md](instructions/commit-messages.instructions.md) - Conventional Commits policy
- [coding-workflow.instructions.md](instructions/coding-workflow.instructions.md) - `src/**`, `tests/**` (before/during/after coding, size and complexity limits, constants placement, validation scope)

## Definition of done

A task is complete when all of the following are true:
1. Requested behavior is implemented.
2. Changed files are `ruff check` and `mypy` clean (configured in `pyproject.toml`, and enforced by CI on PRs), or existing unrelated issues are explicitly called out. Do not introduce new warnings in touched code.
3. Relevant tests pass.
4. Any new assumptions, trade-offs, or follow-ups are clearly reported.
