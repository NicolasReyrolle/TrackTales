"""Export/statistics mixin for WorkoutManager."""

import json
from datetime import datetime
from typing import Any

import pandas as pd


class WorkoutManagerExportMixin:
    """Statistics and export methods for workout data."""

    workouts: pd.DataFrame
    DATE_FORMAT: str
    DEFAULT_EXCLUDED_COLUMNS: set[str]

    def _filter_workouts(
        self,
        activity_type: str = "All",
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
    ) -> pd.DataFrame:
        raise NotImplementedError

    def _get_filtered_columns(self, exclude_columns: set[str] | None = None) -> list[str]:
        raise NotImplementedError

    def get_total_distance(
        self,
        activity_type: str = "All",
        unit: str = "km",
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
    ) -> int:
        """Return the total distance in the specified unit."""
        raise NotImplementedError

    def get_statistics(self) -> str:
        """Return global statistics of the loaded data as a formatted string."""
        if not self.workouts.empty:
            result = f"Total workouts: {len(self.workouts)}\n"
            if "distance" in self.workouts.columns:
                result += f"Total distance of {self.get_total_distance()} km.\n"
            if "duration" in self.workouts.columns:
                total_duration_sec = self.workouts["duration"].sum()
                hours, remainder = divmod(total_duration_sec, 3600)
                minutes, seconds = divmod(remainder, 60)
                result += f"Total duration of {int(hours)}h {int(minutes)}m {int(seconds)}s.\n"
        else:
            result = "No workout loaded."

        return result

    def export_to_json(
        self,
        activity_type: str = "All",
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
        exclude_columns: set[str] | None = None,
    ) -> str:
        """Export to JSON: Schema first, specific column order, no nulls. Return JSON string."""
        cols_to_keep = self._get_filtered_columns(exclude_columns)
        filtered_workouts = self._filter_workouts(activity_type, start_date, end_date)
        df_filtered = filtered_workouts[cols_to_keep]

        json_str = df_filtered.to_json(orient="table")  # type: ignore[misc]
        raw_obj = json.loads(json_str)

        column_priority = {"index": 0, "startDate": 1, "endDate": 2}

        cleaned_data: list[dict[str, Any]] = []
        for row in raw_obj.get("data", []):
            valid_items = {k: v for k, v in row.items() if v is not None}
            sorted_keys = sorted(
                valid_items.keys(), key=lambda k: (column_priority.get(k, 3), k.lower())
            )
            cleaned_data.append({k: valid_items[k] for k in sorted_keys})

        cleaned_data.sort(key=lambda x: x.get("startDate", ""))

        final_obj: dict[str, Any] = {
            "schema": raw_obj.get("schema"),
            "data": cleaned_data,
        }

        return json.dumps(final_obj, indent=2)

    def export_to_csv(
        self,
        activity_type: str = "All",
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
        exclude_columns: set[str] | None = None,
    ) -> str:
        """Export workouts to a CSV format, returns the CSV string."""
        cols_to_keep = self._get_filtered_columns(exclude_columns)
        filtered_workouts = self._filter_workouts(activity_type, start_date, end_date)

        if filtered_workouts.empty:
            expected_columns = [
                "activityType",
                "duration",
                "durationUnit",
                "startDate",
                "endDate",
                "source",
            ]
            excluded = (
                exclude_columns if exclude_columns is not None else self.DEFAULT_EXCLUDED_COLUMNS
            )
            cols_to_keep = [col for col in expected_columns if col not in excluded]
            empty_df = pd.DataFrame(columns=cols_to_keep)
            return empty_df.to_csv(index=False)

        return filtered_workouts[cols_to_keep].to_csv(index=False)

    def get_date_bounds(self) -> tuple[str, str]:
        """Return the minimum and maximum start dates as strings in YYYY/MM/DD."""
        if self.workouts.empty or "startDate" not in self.workouts.columns:
            return "2000/01/01", datetime.now().strftime(self.DATE_FORMAT)

        start_dates = [w.startDate for w in self.workouts.itertuples()]

        return (
            min(start_dates).strftime(self.DATE_FORMAT),  # type: ignore[arg-type,union-attr]
            max(start_dates).strftime(self.DATE_FORMAT),  # type: ignore[arg-type,union-attr]
        )
