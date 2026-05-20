# Maintainers Guide

This document contains development, testing, and maintenance notes for `tracktales`.

## Requesting Enhancements or Reporting Issues

Use the standard GitHub workflow for all feedback:

- **Bug reports**: [Open a new issue](https://github.com/NicolasReyrolle/tracktales/issues/new?template=bug_report.md)
- **Feature requests**: [Open a new issue](https://github.com/NicolasReyrolle/tracktales/issues/new?template=feature_request.md)
- **Discussions**: Use [GitHub Discussions](https://github.com/NicolasReyrolle/tracktales/discussions)

Search [existing issues](https://github.com/NicolasReyrolle/tracktales/issues) first to avoid duplicates.

## Development Setup

### Run tests

```bash
pytest --cov=src tests/
```

### Dev mode (preloaded file)

Preferred entry point:

```bash
tracktales --dev-file tests/fixtures/export_sample.zip
```

Alternative module run:

```bash
python src/tracktales.py --dev-file tests/fixtures/export_sample.zip
```

### Debug logging for dev-file loading

```bash
tracktales --dev-file tests/fixtures/export_sample.zip --log-level DEBUG
```

or:

```bash
python src/tracktales.py --dev-file tests/fixtures/export_sample.zip --log-level DEBUG
```

In normal mode logs are written to console and `logs/tracktales.log`.
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

## Workout Detail Modal Architecture

The workout detail modal is organised into two layers that are **actively connected** — the UI layer imports from the schema layer, so the schema is the single source of truth for which activity types are supported and what field keys drive the Activity tab.

### Schema layer — `src/logic/workout_detail_schema.py`

Defines the data contract using pure Python (no NiceGUI dependency):

- `FieldDefinition` — frozen dataclass describing a single attribute. The `display_row_key` attribute (optional, defaults to `None`) names the key used in the modal row dict. Fields surfaced in the Overview tab (e.g. `averageRunningPower` → generic `avg_power`) leave `display_row_key=None`; Activity-tab fields always set it.
- `GENERIC_FIELDS` — ordered list of `FieldDefinition` instances shown for every workout type (activity, dates, duration, distance, calories, heart rate, VO₂ max, elevation, environment).
- `PER_TYPE_FIELDS` — dict mapping an activity-type string (e.g. `"Running"`) to a list of additional `FieldDefinition` instances specific to that type. Every field here that belongs to the Activity tab must set `display_row_key` to the row-dict key produced by `_build_workout_rows()`.
- `get_fields_for_activity(activity_type)` — returns `GENERIC_FIELDS + PER_TYPE_FIELDS.get(activity_type, [])`.

### UI layer — `src/ui/workout_detail_modal/__init__.py`

Builds the NiceGUI dialog from the field display specs:

- `_FIELD_DISPLAY` — display spec for the Overview tab (generic attributes, including VO₂ max which is generic for all workout types).
- `_RUNNING_FIELD_DISPLAY`, `_WALKING_FIELD_DISPLAY`, `_HIKING_FIELD_DISPLAY`, `_SWIMMING_FIELD_DISPLAY`, `_CYCLING_FIELD_DISPLAY` — display specs for the Activity tab, one per supported type.
- `_ACTIVITY_FIELD_KEYS` — **derived from `PER_TYPE_FIELDS`** by collecting `display_row_key` values for each activity type. This dict drives `_row_has_activity_data()` to decide whether to enable the Activity tab. It is computed at module load time so any new entry in `PER_TYPE_FIELDS` is picked up automatically.
- `create_workout_detail_modal(rows)` — creates the dialog once in the current NiceGUI context and returns an `open_at(index)` callable.
- Route-capable workouts expose dedicated **Route** (Leaflet map with one polyline per route part plus start/end markers), **Charts** (ECharts elevation+pace with a heart-rate series and speed/heart-rate hover metrics when available), and **Comparisons** (same-route historical ranking) tabs. Keep chart readability settings (`legend.top`, centered x/y axis names, and larger grid margins) when editing chart config.

**Adding Activity-tab support for a new type** requires changes in both layers:

1. **Schema layer** — add a new `FieldDefinition` list and one entry in `PER_TYPE_FIELDS`. Every field that should appear in the Activity tab (not the Overview tab) must set `display_row_key` to the row-dict key produced by `_build_workout_rows()`:

```python
_MY_SPORT_FIELDS: list[FieldDefinition] = [
    FieldDefinition(field_name="averageMyMetric", display_name="My Metric",
                    unit="unit", field_type=FieldType.NUMBER,
                    presence=FieldPresence.OPTIONAL,
                    description="Source: HKQuantityTypeIdentifier… WorkoutStatistics.",
                    display_row_key="my_metric"),
]

PER_TYPE_FIELDS["MySport"] = _MY_SPORT_FIELDS
```

1. **UI layer** — add a `_MY_SPORT_FIELD_DISPLAY` list of `(field_key, label_fn)` tuples, a `ui.column()` container inside the Activity tab panel in `create_workout_detail_modal`, and register the container in `_containers`. `_ACTIVITY_FIELD_KEYS` is updated automatically from the schema.

1. **Data layer** — add extraction logic in `src/ui/workout_table.py` (`_extract_mysport_fields`) and call it from `_extract_row_data`.

The workout table wires the modal via `create_workout_detail_modal(rows)` in `render_workout_table()` and emits an `open_detail` custom event from the Vue slot when the user clicks the info button.

## Translations

Translation workflows are documented in [src/i18n/locales/README.md](src/i18n/locales/README.md).

Runtime notes:

- Language and unit system (Metric/Imperial) are session-based and changeable from the header preferences menu.
- Loading/progress messages are localized in UI.
- Date picker labels are sourced from gettext catalogs.
- `.mo` files are auto-generated at startup when missing/outdated.

## Windows-specific testing note

`tests/conftest.py` includes workarounds for `WinError 32` (PermissionError) during teardown by isolating storage and patching cleanup behavior.
