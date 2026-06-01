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
- Route-capable workouts expose dedicated **Route** (Leaflet map with one polyline per route part plus start/end markers), **Charts** (ECharts route-profile chart with altitude+pace and speed hover metrics, plus a separate heart-rate chart displayed below when heart-rate samples are available), and **Comparisons** (same-route historical ranking) tabs. Keep chart readability settings (`legend.top`, centered x/y axis names, and larger grid margins) when editing chart config.

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

## Release Process

TrackTales uses **Calendar Versioning (CalVer)** with the format `YYYY.MM.PATCH` (e.g., `2026.05.1`, `2026.05.2`).

### Versioning Scheme

- **YYYY**: Current year (4 digits)
- **MM**: Current month (2 digits, zero-padded)
- **PATCH**: Sequential patch number within the month, auto-incremented (starts at 1)

Examples:

- First release in May 2026: `v2026.05.1`
- Second release in May 2026: `v2026.05.2`
- First release in June 2026: `v2026.06.1`

### How to Release

1. **Make commits** with descriptive commit messages (e.g., `fix: handle corrupted ZIP files`, `feat: add French language support`)
2. **Ensure tests pass** locally:

   ```bash
   pytest -o addopts='' --cov=src tests/
   ruff format src tests
   ruff check src tests
   mypy src tests
   ```

3. **Push commits** to `main` branch
4. **Trigger release workflow**:
   - Go to GitHub repository → **Actions** tab
   - Click **Release** workflow on the left
   - Set **Dry run** if you want to build and validate without publishing
   - Click **Run workflow** button
5. **Workflow automatically**:
   - Calculates next version (YYYY.MM.PATCH with auto-incremented PATCH)
   - Updates and commits `pyproject.toml` with the new version before creating the release tag
   - Builds Windows executable (.exe) via PyInstaller
   - Builds macOS app bundle (.dmg) via PyInstaller
   - Builds Python distributions (.whl and .tar.gz) via setuptools
   - Runs full test suite
   - Creates git tag (e.g., `v2026.05.2`)
   - Creates GitHub Release with:
     - Installation instructions for each platform
     - Auto-generated changelog from commits since last release
     - All built artifacts (.exe, .dmg, .whl, .tar.gz)
   - Publishes to PyPI

### GitHub Dry Run

Use the workflow-dispatch **Dry run** input when you want CI to build and validate everything without publishing.

- Builds and tests still run
- A `release-dry-run-<version>` artifact is uploaded with release notes and built artifacts
- No git tag is pushed
- No GitHub release is created
- Nothing is published to PyPI

### Local Dry Run

You can dry-run the release flow locally without GitHub Actions:

```bash
python tools/release_dry_run.py
```

Useful options:

```bash
python tools/release_dry_run.py --skip-tests
python tools/release_dry_run.py --skip-pyinstaller
python tools/release_dry_run.py --keep-temp
```

The script:

- Computes the next `YYYY.MM.PATCH` version from local git tags
- Copies the repo to a temporary workspace
- Rewrites `pyproject.toml` there with the computed release version
- Optionally builds Python distributions, runs tests, and builds PyInstaller artifacts
- Does not generate release notes
- Copies the generated outputs to `output/release-dry-run/`

### Distribution Channels

After release, end-users can install TrackTales:

- **Windows**: Download `.exe` from GitHub Releases, double-click to run (no installation needed)
- **macOS**: Download `.dmg` from GitHub Releases, double-click and drag app to Applications folder
- **Python/pip**: `pip install tracktales==YYYY.MM.PATCH` (from PyPI)

### Building Standalone Executables Locally

For testing or local builds, you can use PyInstaller:

1. **Install PyInstaller**:

   ```bash
   pip install pyinstaller
   ```

2. **Build executable**:

   ```bash
   pyinstaller tracktales.spec
   ```

3. **Test the built executable**:
   - **Windows**: `dist/tracktales.exe` (run directly, no Python required)
   - **macOS**: `dist/tracktales.app` (open via Finder or `open dist/tracktales.app`)

### Windows executable smoke test

Use this startup smoke test after building the Windows executable to catch early runtime crashes.

```powershell
# from repository root
Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue
pyinstaller tracktales.spec

$exe = "dist/tracktales.exe"
if (-not (Test-Path $exe)) {
   throw "Executable not found: $exe"
}

$process = Start-Process -FilePath $exe -ArgumentList @("--no-browser") -PassThru
try {
   $exited = $process.WaitForExit(15000)
   if ($exited) {
      throw "Executable exited during startup smoke test with code $($process.ExitCode)"
   }
}
finally {
   if (-not $process.HasExited) {
      Stop-Process -Id $process.Id -Force
   }
}
```

If this smoke test fails with a traceback, include the full stack trace in the issue.

1. **Create macOS .dmg installer** (optional):

   ```bash
   pip install create-dmg
   create-dmg --volname "TrackTales" --app-drop-link 450 250 "dist/tracktales-YYYY.MM.PATCH.dmg" "dist/tracktales.app"
   ```

### PyInstaller Configuration

The `tracktales.spec` file configures PyInstaller to:

- Bundle all Python dependencies (nicegui, pandas, babel, defusedxml, etc.)
- Include i18n locale files and resources
- Create a Windows .exe with no console window
- Create a macOS .app bundle with appropriate metadata

Edit `tracktales.spec` if you need to:

- Add new hidden imports (if PyInstaller doesn't auto-detect a module)
- Include additional data files
- Change bundle settings

### Setting Up PyPI Trusted Publisher (One-Time)

For the release workflow to publish to PyPI, you must configure GitHub as a trusted publisher:

1. Go to [PyPI project settings](https://pypi.org/project/tracktales/settings/)
2. Under **Publishing**, add a trusted publisher:
   - **GitHub Owner**: `NicolasReyrolle`
   - **Repository**: `TrackTales`
   - **Workflow name**: `release.yml`
3. Click **Add trusted publisher**

No API tokens need to be stored in GitHub secrets; the workflow uses OpenID Connect (OIDC) for secure authentication.

### Troubleshooting Releases

**Release workflow fails**: Check the Actions tab for error details. Common issues:

- Python dependencies not installed: Ensure `requirements.txt` is up-to-date
- PyInstaller build failed: Run `pyinstaller tracktales.spec` locally to debug
- Test failures: Fix failing tests before retrying workflow
- Local runner cannot resolve `actions/checkout@v4`: this is usually a problem with the local GitHub Actions runner tooling, network access, or GitHub credential setup, not the workflow itself

**`Unable to resolve action actions/checkout@v4`**:

- On GitHub-hosted runners, `actions/checkout@v4` is valid and should resolve normally
- If you see this locally, it usually means your local Actions emulator cannot fetch GitHub-hosted actions
- Common causes: offline environment, corporate proxy/firewall, outdated `act`, or missing GitHub authentication for action downloads
- Use `python tools/release_dry_run.py` when you want a local release rehearsal without depending on remote action resolution

**Need to release a hotfix immediately**:

- No manual version management needed; just push commits and trigger the workflow again
- The workflow auto-increments PATCH (2026.05.1 → 2026.05.2 → etc.)

**Rollback strategy**:

- If a released version is broken, publish a new version with the fix (no rollback)
- Older releases remain available on GitHub Releases for users who need to downgrade
