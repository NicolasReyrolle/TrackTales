"""Heart-rate sample helpers for the workout detail modal."""

from __future__ import annotations

from typing import Any, cast

import pandas as pd

_HEART_RATE_SAMPLES_CACHE: tuple[Any, pd.DataFrame] | None = None


def _get_cached_heart_rate_samples() -> pd.DataFrame:
    """Return cached normalized heart-rate samples for the active file load."""
    from app_state import state

    global _HEART_RATE_SAMPLES_CACHE

    cache_key = state.records_by_type
    if _HEART_RATE_SAMPLES_CACHE is not None and _HEART_RATE_SAMPLES_CACHE[0] is cache_key:
        return _HEART_RATE_SAMPLES_CACHE[1]

    heart_rate_df = state.records_by_type.heart_rate()
    heart_rate_samples = pd.DataFrame(columns=["startDate", "value"])
    if not heart_rate_df.empty and {"startDate", "value"}.issubset(heart_rate_df.columns):
        heart_rate_samples = heart_rate_df[["startDate", "value"]].copy()
        heart_rate_samples["startDate"] = pd.to_datetime(
            heart_rate_samples["startDate"], utc=True, errors="coerce"
        ).dt.tz_localize(None)
        heart_rate_samples["value"] = pd.to_numeric(heart_rate_samples["value"], errors="coerce")
        heart_rate_samples = heart_rate_samples.dropna(subset=["startDate", "value"]).sort_values(
            "startDate"
        )

    _HEART_RATE_SAMPLES_CACHE = (cache_key, heart_rate_samples)
    return heart_rate_samples


def _ensure_row_heart_rate_enriched(row: dict[str, Any]) -> None:
    """Attach nearest heart-rate samples to the row's routes once, on demand."""
    if row.get("_heart_rate_routes_enriched"):
        return

    from ui import workout_table as wt

    workout_start = row.get("workout_start_utc")
    workout_end = row.get("workout_end_utc")
    if workout_start is None or workout_end is None:
        row["_heart_rate_routes_enriched"] = True
        return

    wt._enrich_routes_with_heart_rate(
        row,
        {
            "startDateUtc": workout_start,
            "endDateUtc": workout_end,
            "xmlFragment": row.get("xmlFragment"),
        },
        _get_cached_heart_rate_samples(),
        row.get("workout_index"),
    )
    row["_heart_rate_routes_enriched"] = True


def _get_row_workout_heart_rate_samples(row: dict[str, Any]) -> list[tuple[Any, float]]:
    """Return workout-window heart-rate samples for the current row, cached on first use."""
    cached_samples = row.get("_workout_heart_rate_samples")
    if isinstance(cached_samples, list):
        return cast(list[tuple[Any, float]], cached_samples)

    from ui import workout_table as wt

    workout_start = wt._normalize_datetime(row.get("workout_start_utc"))
    workout_end = wt._normalize_datetime(row.get("workout_end_utc"))
    samples = wt._extract_workout_heart_rate_samples(
        _get_cached_heart_rate_samples(),
        workout_start,
        workout_end,
    )
    row["_workout_heart_rate_samples"] = samples
    return samples


def _row_has_workout_heart_rate(row: dict[str, Any]) -> bool:
    """Return whether the row has any workout-window heart-rate samples."""
    return bool(_get_row_workout_heart_rate_samples(row))
