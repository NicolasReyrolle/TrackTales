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
- **Workout Detail Modal**: Open per-workout details from the Activities table. The wider modal now includes six tabs: **Overview**, **Activity**, **Route** (Leaflet map with start/end markers for each route part), **Charts** (elevation + pace charting plus a heart-rate trace when workout HR samples are available), **Intervals** (including per-split average heart rate when available), and **Comparisons** (historical same-route ranking with rank and time gap). The Charts tab uses non-zero-based axes, centered axis titles, and top legend placement for readability. Type-specific Activity metrics vary by sport — Running: pace, cadence, stride length, vertical oscillation, ground contact time, step count; Walking: pace, cadence, step length, step count; Hiking: elevation gain, pace, cadence, step length, step count; Cycling: speed, cadence, power, functional threshold power; Swimming: pool/open-water location, lap length, total stroke count. Activity/route-dependent tabs are disabled when required data is unavailable.
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
1. In the **Activities** table, click the **Details** action to open the workout modal (Overview, Activity, Route map, Charts, Intervals, and Comparisons).
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

Maintainer and contributor documentation is centralized in [MAINTAINERS.md](MAINTAINERS.md).

For development setup, quality checks, release workflow, packaging validation, and architecture notes, use [MAINTAINERS.md](MAINTAINERS.md) as the single source of truth.

## 🔒 Security

This application uses **streaming XML parsing** (`iterparse`) to remain memory-efficient even with large exports (GBs of data) and `defusedxml.ElementTree` to mitigate risks associated with untrusted XML data.

## 📄 License

This project is licensed under the **GPL-3.0 License**. See the [LICENSE](LICENSE) file for details.
