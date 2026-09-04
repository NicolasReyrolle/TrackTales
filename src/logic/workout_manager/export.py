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

        result: str = filtered_workouts[cols_to_keep].to_csv(index=False)
        return result

    def export_to_markdown(
        self,
        activity_type: str = "All",
        start_date: datetime | pd.Timestamp | None = None,
        end_date: datetime | pd.Timestamp | None = None,
        distance_unit: str = "km",
    ) -> str:
        """Export a human-readable analytics summary as Markdown."""
        filtered_workouts = self._filter_workouts(activity_type, start_date, end_date)
        count = len(filtered_workouts)
        distance = self.get_total_distance(
            activity_type=activity_type,
            unit=distance_unit,
            start_date=start_date,
            end_date=end_date,
        )
        duration = self.get_total_duration(
            activity_type=activity_type,
            start_date=start_date,
            end_date=end_date,
        )
        calories = self.get_total_calories(
            activity_type=activity_type,
            start_date=start_date,
            end_date=end_date,
        )
        monthly_distance = self.get_distance_by_period(
            "M",
            activity_type=activity_type,
            unit=distance_unit,
            start_date=start_date,
            end_date=end_date,
            fill_missing_periods=False,
        )
        trend = self.get_trend_analysis(list(monthly_distance.values()), label_mode="directional")
        seasonal_counts = self.get_count_by_day_of_week(
            activity_type=activity_type,
            start_date=start_date,
            end_date=end_date,
        )
        busiest_day = max(seasonal_counts, key=seasonal_counts.get) if seasonal_counts else "N/A"
        activity_label = activity_type.replace("|", "\\|")
        date_label = (
            f"{start_date:%Y-%m-%d} to {end_date:%Y-%m-%d}"
            if start_date is not None and end_date is not None
            else "All available dates"
        )
        training_load = self.get_training_load(activity_type, start_date, end_date)
        recovery = self.get_recovery_recommendation(
            activity_type,
            start_date=start_date,
            end_date=end_date,
        )

        return "\n".join(
            [
                "# TrackTales Analytics Report",
                "",
                f"- **Activity:** {activity_label}",
                f"- **Date range:** {date_label}",
                "",
                "## Summary",
                "",
                "| Metric | Value |",
                "| --- | ---: |",
                f"| Workouts | {count} |",
                f"| Distance | {distance} {distance_unit} |",
                f"| Duration | {duration}h |",
                f"| Calories | {calories} kcal |",
                "",
                "## Insights",
                "",
                f"- **Distance trend:** {trend}",
                f"- **Busiest workout day:** {busiest_day}",
                f"- **Training load:** {training_load} bpm·min",
                f"- **Recovery recommendation:** {recovery}",
                "",
            ]
        )

    def get_date_bounds(self) -> tuple[str, str]:
        """Return the minimum and maximum start dates as strings in YYYY/MM/DD."""
        if self.workouts.empty or "startDate" not in self.workouts.columns:
            return "2000/01/01", datetime.now().strftime(self.DATE_FORMAT)

        start_dates: list[datetime] = [ts.to_pydatetime() for ts in self.workouts["startDate"]]

        return (
            min(start_dates).strftime(self.DATE_FORMAT),
            max(start_dates).strftime(self.DATE_FORMAT),
        )
