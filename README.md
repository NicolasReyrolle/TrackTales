# 🏃‍♂️ TrackTales

A modern, interactive tool to parse, analyze, and visualize your Apple Health workout data. Built with **NiceGUI**, TrackTales transforms your fitness journey into rich interactive charts, segment analysis, and personalized insights. This is a personal project, but contributions are welcome!

[![codecov](https://codecov.io/gh/NicolasReyrolle/tracktales/graph/badge.svg?token=2yKEc6OOkx)](https://codecov.io/gh/NicolasReyrolle/tracktales)
[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=NicolasReyrolle_tracktales&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=NicolasReyrolle_tracktales)

## 👩‍💻 For Contributors

If you are contributing or maintaining the project, see [MAINTAINERS.md](MAINTAINERS.md).

## ✨ Features

- **ZIP Parsing**: Directly select and parse your `export.zip` file from Apple Health.
- **Workout Extraction**: Focused on running workouts with detailed metrics (distance, duration, METs, heart rate, power, etc.).
- **Visual Statistics**: Real-time summary of total activities, distance, duration, elevation, and calories with interactive charts (pie/rose charts for activity breakdown, bar charts with trend lines for time-based analysis).
- **Interactive Charts**: Every chart supports zoom and pan (mouse scroll, pinch, or trackpad gesture). Click the ⛶ fullscreen button on any chart to open it in a maximized view with a range-slider for precise zoom control. Tooltips are rich HTML with bold labels and value+unit on each axis hover.
- **Health Data Insights**: Health Data tab combines workout activity timing (day/hour heat map) with period-based trends for resting heart rate, body mass, VO2 max, **Critical Power (CP)**, and **W'**. Fast metrics load immediately and CP/W' fill in progressively in the background.
- **Best Segments Tab**: Computes and displays best running segments from 100m to 100km with expandable runner-up rows, formatted durations, localized labels, and segment power confidence.
- **Robust Segment Distance Model**: Segment search uses GPX speed integration with safeguards for export edge cases (window clipping, final unpaired pause trimming, strict reversal-only trace splits, and realistic workout-level distance normalization).
- **Activity Filtering**: Filter your workout data by activity type (Running, Cycling, Walking, etc.).
- **Workout Detail Modal**: Open per-workout details from the Activities table. The wider modal now includes six tabs: **Overview**, **Activity**, **Route** (Leaflet map with start/end markers for each route part), **Profile** (elevation + pace dual-axis chart with speed/heart-rate tooltip metrics when available), **Intervals**, and **Comparisons** (historical same-route ranking with rank and time gap). The Profile chart uses non-zero-based axes, centered axis titles, and top legend placement for readability. Type-specific Activity metrics vary by sport — Running: pace, cadence, stride length, vertical oscillation, ground contact time, step count; Walking: pace, cadence, step length, step count; Hiking: elevation gain, pace, cadence, step length, step count; Cycling: speed, cadence, power, functional threshold power; Swimming: pool/open-water location, lap length, total stroke count. Activity/route-dependent tabs are disabled when required data is unavailable.
- **Date Range Filtering**: Analyze specific time periods using the date range picker to focus on your desired date ranges.
- **Trends Period Aggregation**: Switch the Trends tab aggregation between week, month, quarter, or year.
- **Gap-Aware Time Series**: Missing periods are preserved in health-data charts, so the x-axis remains continuous and missing measurements are explicit (not coerced to zero). For line charts, inferred bridge segments are visually distinct from measured segments.
- **Route Parts Handling**: Workouts with multiple GPX route files are preserved as independent route parts for segment analysis and also exposed as a merged compatibility route.
- **Multilingual UI (EN/FR)**: gettext-based translations for labels, tabs, date picker locale labels, notifications, and loading/progress status messages.
- **Unit System Preference**: Switch between Metric (km, kg, m) and Imperial (mi, lbs, ft) from the preferences menu; all stats, charts, and tables update accordingly.
- **Data Export**: Convert your data into clean **CSV** or **JSON** formats for further analysis in Excel, Python, or other tools.
- All processing happens locally on your machine.
- **Modern UI**: Dark/Light mode support with a responsive layout.

## 🚀 Installation

### Prerequisites

- Python 3.10 or higher.
- An Apple Health export file (`export.zip`).

### Setup

#### Clone the repository

```bash
git clone https://github.com/NicolasReyrolle/tracktales.git
cd tracktales
```

#### Create a virtual environment

```bash
# Windows
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Linux/macOS
python3 -m venv .venv
source .venv/bin/activate
```

#### Install the dependencies

```bash
pip install -r requirements.txt
```

## 🖥️ Usage

Start the application using the following command:

```bash
python -m nicegui src.tracktales
```

1. Open your browser to `http://localhost:8080`.
1. Click **Browse** to select your Apple Health `export.zip`.
1. Click **Load** to parse the data.
1. View the statistics in the **Overview** tab.
1. Explore your data in the **Activities** tab (pie/rose charts grouped by activity type), **Trends** tab (weekly/monthly/quarterly/yearly bar charts with moving average trend lines), **Health Data** tab (workout heat map plus line charts for resting heart rate, body mass, VO2 max, CP, and W'), and **Running** tab (distance/elevation pace analysis with best segments).
1. In the **Activities** table, click the **Details** action to open the workout modal (Overview, Activity, Route map, Profile elevation/pace chart, Intervals, and Comparisons).
1. Use the **Activity filter** in the left drawer to focus on specific workout types.
1. Use the **Date range picker** to analyze specific time periods.
1. Use the **Aggregate by** selector in the left drawer to change the aggregation period.
1. Use the **Preferences menu** (tune icon in the header) to switch language (EN/FR) or unit system (Metric/Imperial).
1. Export your data using the **Export data** menu to download CSV or JSON files.

> **Tip**: You can set a permanent storage secret for sessions by using an environment variable:
> `set STORAGE_SECRET=your_custom_secret` (Windows)

### 📱 How to Get Your Export File

To analyze your data, you first need to export it from your iPhone:

1. Open the **Health app** on your iPhone.
1. Tap your **Profile Picture** or icon in the top-right corner.
1. Scroll to the bottom and tap **Export All Health Data**.
1. Tap **Export** to confirm. This process may take a few minutes depending on the amount of data.
1. Once the export is ready, share the `export.zip` file to your computer (via AirDrop, iCloud Drive, OneDrive, GoogleDrive or any other mean).
1. Use this file in the **TrackTales** app.

## 🛠️ Development & Testing

Maintainer and contributor documentation has moved to [MAINTAINERS.md](MAINTAINERS.md).

Quality checks (Ruff + mypy):

```bash
ruff format src tests
ruff check src tests
mypy src tests
```

If you are here to use the app, you can skip directly to the sections above.

### Best Segments algorithm (summary)

Best segments are computed with a route-aware sliding-window search on running workouts:

- GPX points are first clipped to each `WorkoutRoute` XML time window.
- If a workout ends with `MotionPaused` and no later `MotionResumed`, points after that pause are excluded.
- Route traces split only on strict timestamp reversal (`t[n+1] < t[n]`), so duplicated timestamps do not fragment long routes.
- Traveled distance progression uses GPX speed integration (`speed × Δt`, trapezoidal between points), with haversine fallback when speed is unavailable.
- A single workout-level distance normalization factor can be applied when route distance and workout summary distance differ only by a realistic margin; the same factor is reused for all queried segment distances.
- Segment distances longer than the workout's reported distance are skipped.

### Critical Power and W' (summary)

- The app computes CP and W' from best running segments using required anchor distances (800m and 5000m) plus intermediate distances when available (default: 1500m and 3000m).
- CP/W' is fit on the work-time model (`W = CP * t + W'`) with a deterministic RANSAC-like robust fit to reduce the influence of outlier distance points.
- When robust fitting excludes outlier points, the dropped points are logged at info level.
- Segment power is estimated from `RunningPower` records in priority order: direct window match, overlap-based estimate, then workout-level fallback.
- Evolution charts keep interior missing periods as gaps while trimming leading/trailing empty periods.

## 💬 Requesting Enhancements or Reporting Issues

Feedback, bug reports, and feature requests are welcome! Please use the standard GitHub workflows:

- **Bug reports**: [Open a new issue](https://github.com/NicolasReyrolle/tracktales/issues/new?template=bug_report.md) and describe the problem, steps to reproduce, and expected behaviour.
- **Feature requests**: [Open a new issue](https://github.com/NicolasReyrolle/tracktales/issues/new?template=feature_request.md) and describe the enhancement and its motivation.
- **Questions or discussions**: Use [GitHub Discussions](https://github.com/NicolasReyrolle/tracktales/discussions) for open-ended questions or design ideas.

Please search [existing issues](https://github.com/NicolasReyrolle/tracktales/issues) before opening a new one to avoid duplicates.

### Workout manager package layout

Workout management internals are organized in a dedicated package under `src/logic/workout_manager/`:

- `manager.py`: core `WorkoutManager` class and public distance constants.
- `aggregations.py`: filtering, totals, and by-activity/by-period aggregations.
- `export.py`: statistics and CSV/JSON export helpers.
- `segments.py`: best-segment computation, segment power annotation, and CP/W' calculations.
- `workout_route.py`: `RoutePoint`/`WorkoutRoute` models and route computations used by segment analysis.
- `__init__.py`: public compatibility exports.

The import path remains unchanged for consumers:

- `from logic.workout_manager import WorkoutManager`

## 🔒 Security

This application uses **streaming XML parsing** (`iterparse`) to remain memory-efficient even with large exports (GBs of data) and `defusedxml.ElementTree` to mitigate risks associated with untrusted XML data.

## 📄 License

This project is licensed under the **GPL-3.0 License**. See the [LICENSE](LICENSE) file for details.

