# Maintainers Guide

This document contains development, testing, and maintenance notes for `apple-health-analyzer`.

## Requesting Enhancements or Reporting Issues

Use the standard GitHub workflow for all feedback:

- **Bug reports**: [Open a new issue](https://github.com/NicolasReyrolle/apple-health-analyzer/issues/new?template=bug_report.md)
- **Feature requests**: [Open a new issue](https://github.com/NicolasReyrolle/apple-health-analyzer/issues/new?template=feature_request.md)
- **Discussions**: Use [GitHub Discussions](https://github.com/NicolasReyrolle/apple-health-analyzer/discussions)

Search [existing issues](https://github.com/NicolasReyrolle/apple-health-analyzer/issues) first to avoid duplicates.

## Development Setup

### Run tests

```bash
pytest --cov=src tests/
```

### Dev mode (preloaded file)

Preferred entry point:

```bash
apple-health-analyzer --dev-file tests/fixtures/export_sample.zip
```

Alternative module run:

```bash
python src/apple_health_analyzer.py --dev-file tests/fixtures/export_sample.zip
```

### Debug logging for dev-file loading

```bash
apple-health-analyzer --dev-file tests/fixtures/export_sample.zip --log-level DEBUG
```

or:

```bash
python src/apple_health_analyzer.py --dev-file tests/fixtures/export_sample.zip --log-level DEBUG
```

In normal mode logs are written to console and `logs/apple_health_analyzer.log`.
In `--dev-file` mode logs are console-only to avoid reload loops.

Available log levels: `DEBUG`, `INFO`, `WARNING`, `ERROR` (default: `INFO`).

### Rebuild test fixture zip

```bash
python tests/fixtures/update_export_sample.py
```

This rebuilds `tests/fixtures/export_sample.zip` from `tests/fixtures/exports/`.

## Code Quality

Run before opening a PR:

```bash
ruff format src tests
ruff check src tests
mypy src tests
```

## Route Parsing and Segment Semantics

The parser and segment logic intentionally use window-bounded route behavior:

- Each XML `WorkoutRoute` block is treated as an independent time window.
- GPX points are clipped to that window (`startDate` to `endDate`).
- If a workout ends with `MotionPaused` (and no later `MotionResumed`), route points after that pause are trimmed for segment analysis.
- Windows with no matching GPX points are skipped.
- Parsed route windows are stored in `route_parts`.
- `route` is kept as a backward-compatible merged representation.
- Best-segment analysis uses `route_parts` traces so segment windows do not cross disjoint route windows.
- Trace splitting only occurs on strict timestamp reversals (`<`), not equal timestamps, so duplicate timestamps do not fragment long routes.
- Traveled distance for segment search uses GPX speed integration (`speed × Δt`, trapezoidal between points) with Haversine fallback when speed is unavailable.
- A single workout-level distance scale factor can normalize route-derived distance to workout summary distance, but only when mismatch is within `WorkoutRoute.MAX_REALISTIC_DISTANCE_SCALE_DEVIATION`.
- The same normalization factor applies to all queried segment distances for that workout (100m … 100km).

This behavior prevents unrealistic artifacts (for example impossible `100m` durations) when exports contain reused GPX file references or missing points in specific windows.

## Workout Manager Package Structure

The workout manager implementation is split into a dedicated package:

- `src/logic/workout_manager/manager.py`: core `WorkoutManager` class and exported segment distance constants.
- `src/logic/workout_manager/aggregations.py`: filtering, totals, and period/activity aggregations.
- `src/logic/workout_manager/export.py`: summary statistics and CSV/JSON export.
- `src/logic/workout_manager/segments.py`: best-segment search over running routes, segment power annotation, and CP/W' calculations.
- `src/logic/workout_manager/__init__.py`: public compatibility exports for `logic.workout_manager` imports.

Keep importing from `logic.workout_manager` in app/tests unless there is a specific reason to target internal modules.

## Translations

Translation workflows are documented in [src/i18n/locales/README.md](src/i18n/locales/README.md).

Runtime notes:

- Language and unit system (Metric/Imperial) are session-based and changeable from the header preferences menu.
- Loading/progress messages are localized in UI.
- Date picker labels are sourced from gettext catalogs.
- `.mo` files are auto-generated at startup when missing/outdated.

## Windows-specific testing note

`tests/conftest.py` includes workarounds for `WinError 32` (PermissionError) during teardown by isolating storage and patching cleanup behavior.
