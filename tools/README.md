# TrackTales - Tools

Utility scripts and tools for development, profiling, and testing.

## Profile Best Segments

Performance profiling tool for the `get_best_segments()` method using [pyinstrument](https://github.com/jorenham/pyinstrument).

### Usage

**From project root:**

```bash
python -m tools.profile_best_segments
```

**From tools directory:**

```bash
python profile_best_segments.py
```

### Requirements

```bash
pip install pyinstrument
```

### Purpose

Identifies performance bottlenecks in the best-segments feature by profiling the `get_best_segments()` method against the real export sample (`tests/fixtures/export_sample.zip`).

### Output

The tool displays:

- Execution time and CPU time
- Call tree with time spent in each function
- Summary statistics for the top segments found

### Example Output

```text
Loading export from: .../tests/fixtures/export_sample.zip

Total workouts: 4
Running workouts: 1
Routes with GPS data: 4

Profiling get_best_segments()...
[pyinstrument flame graph output]

Result: 1 best segments found
            startDate  distance  duration_s
0 2025-09-16 16:14:50      1000       404.0
```

### Integration

Use this tool to:

- Monitor performance after algorithm changes
- Identify optimization targets
- Verify regression testing on performance

