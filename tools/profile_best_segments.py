#!/usr/bin/env python3
"""Profile the get_best_segments method using pyinstrument.

Uses the export_sample.zip from tests/fixtures and profiles the get_best_segments
method to identify performance bottlenecks.

Usage:
    python -m tools.profile_best_segments
    or
    cd tools && python profile_best_segments.py
"""

import sys
from pathlib import Path

try:
    from pyinstrument import Profiler
except ImportError:
    print("Error: pyinstrument is not installed.")
    print("Install it with: pip install pyinstrument")
    sys.exit(1)


def main() -> None:
    """Load export_sample.zip and profile get_best_segments."""
    # Add src to path for imports
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root / "src"))

    from logic.export_parser import ExportParser  # noqa: E402
    from logic.workout_manager import WorkoutManager  # noqa: E402

    sample_file = project_root / "tests" / "fixtures" / "export_sample.zip"

    if not sample_file.exists():
        print(f"Error: Sample file not found at {sample_file}")
        sys.exit(1)

    print(f"Loading export from: {sample_file.resolve()}")
    print()

    # Parse the export file
    parser = ExportParser()
    with parser:
        parsed = parser.parse(str(sample_file))

    manager = WorkoutManager(parsed.workouts)

    # Count workouts and routes for context
    total_workouts = len(manager.workouts)
    running_workouts = len(manager.workouts[manager.workouts["activityType"] == "Running"])
    routes_with_data = sum(
        1 for row in manager.workouts.itertuples() if getattr(row, "route", None) is not None
    )

    print(f"Total workouts: {total_workouts}")
    print(f"Running workouts: {running_workouts}")
    print(f"Routes with GPS data: {routes_with_data}")
    print()

    # Profile get_best_segments
    print("Profiling get_best_segments()...")
    print("=" * 70)

    profiler = Profiler()
    profiler.start()

    result = manager.get_best_segments()

    profiler.stop()

    print(profiler.output_text(unicode=True, color=True))
    print("=" * 70)
    print()

    # Show result summary
    print(f"Result: {len(result)} best segments found")
    if not result.empty:
        print(result.to_string())


if __name__ == "__main__":
    main()
