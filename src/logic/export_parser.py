"""Export processor for Apple Health data."""

import logging
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime
from types import TracebackType
from typing import Any
from zipfile import ZipFile

import pandas as pd
from lxml.etree import (  # type: ignore[attr-defined]  # pylint: disable=no-name-in-module
    _Element as Element,
)
from lxml.etree import (
    iterparse,
    tostring,
)

from logic.constants import PANDAS_ISO8601_FORMAT
from logic.gpx_loader import (
    _SAFE_ITERPARSE_OPTIONS,
    GpxLoader,
    _create_route_point,
    _extract_gpx_point_data,
    _purge_element,
    clip_route_to_window,
    get_or_init_route_parts,
    merge_route_parts,
    trim_overlapping_route_part,
)
from logic.models import WorkoutRecord
from logic.parsed_health_data import ParsedHealthData
from logic.value_parser import (
    duration_to_seconds,
    parse_metadata_value,
    parse_value,
    str_distance_to_meters,
    to_number,
)
from logic.workout_manager.workout_route import WorkoutRoute

_logger = logging.getLogger(__name__)

WORKOUT_PROGRESS_INTERVAL = 100
DATETIME64_NS_DTYPE = "datetime64[ns]"

SUPPORTED_RECORD_TYPES = frozenset(
    {"HeartRate", "RestingHeartRate", "BodyMass", "VO2Max", "RunningPower"}
)


class ExportParser:
    """Reads and parses Apple Health export files."""

    def __init__(self, progress_callback: Callable[[str], None] | None = None) -> None:
        self.progress_callback = progress_callback
        self._gpx_loader = GpxLoader()

    # Keep _route_cache as a property for any external code that may reference it
    @property
    def _route_cache(self) -> dict[str, WorkoutRoute | None]:
        return self._gpx_loader._route_cache

    def __enter__(self) -> "ExportParser":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        pass

    # --- Delegated static helpers (kept as static methods for backward compatibility) ---

    @staticmethod
    def to_number(raw: str | None) -> float | int | None:
        return to_number(raw)

    @staticmethod
    def parse_metadata_value(raw_value: str | None) -> tuple[Any, str | None]:
        return parse_metadata_value(raw_value)

    @staticmethod
    def _parse_value(raw_value: str | None) -> tuple[Any, str | None]:
        return parse_value(raw_value)

    @staticmethod
    def duration_to_seconds(value: float, unit: str = "min") -> int:
        return duration_to_seconds(value, unit)

    @staticmethod
    def str_distance_to_meters(value: str, unit: str | None) -> int:
        return str_distance_to_meters(value, unit)

    @staticmethod
    def _extract_gpx_point_data(elem: Element) -> tuple[str, str, str | None, str, float]:
        return _extract_gpx_point_data(elem)

    @staticmethod
    def _create_route_point(
        latitude: str,
        longitude: str,
        altitude: str | None,
        time_str: str,
        speed_val: float,
    ) -> Any:
        return _create_route_point(latitude, longitude, altitude, time_str, speed_val)

    def _load_route(self, zipfile: ZipFile, route_path: str) -> WorkoutRoute | None:
        return self._gpx_loader._load_route(zipfile, route_path)

    @staticmethod
    def clip_route_to_window(
        route: WorkoutRoute,
        window_start: datetime | None,
        window_end: datetime | None,
    ) -> WorkoutRoute:
        return clip_route_to_window(route, window_start, window_end)

    # --- Progress logging ---

    def _log(self, message: str) -> None:
        if self.progress_callback:
            try:
                self.progress_callback(message)
            except Exception:
                _logger.debug(message)

    # --- Workout processing ---

    def _process_workout_event(
        self,
        elem: Element,
        zipfile: ZipFile,
        workout_rows: list[WorkoutRecord],
    ) -> None:
        activity_type = self._extract_activity_type(elem)
        record = self._create_workout_record(elem, activity_type)
        record["xmlFragment"] = tostring(elem, encoding="unicode")
        self._process_workout_children(elem, record, zipfile)
        self._apply_estimated_elevation(record)
        workout_rows.append(record)

        if len(workout_rows) % WORKOUT_PROGRESS_INTERVAL == 0:
            self._log(f"Processed {len(workout_rows)} workouts...")

    @staticmethod
    def _apply_estimated_elevation(record: WorkoutRecord) -> None:
        if "ElevationAscended" in record:
            return
        route_parts = record.get("route_parts")
        if isinstance(route_parts, list) and route_parts:
            part_gains = [
                part_gain
                for part in route_parts
                if (part_gain := part.estimated_elevation_gain_m()) is not None
            ]
            gain = sum(part_gains) if part_gains else None
        else:
            route = record.get("route")
            if route is None:
                return
            gain = route.estimated_elevation_gain_m()
        if gain is not None:
            record["ElevationAscended"] = gain  # type: ignore[typeddict-unknown-key]
            record["ElevationAscendedUnit"] = "m"  # type: ignore[typeddict-unknown-key]

    def _process_record_event(
        self,
        elem: Element,
        record_rows_by_type: dict[str, list[dict[str, Any]]],
    ) -> None:
        result = self._extract_health_data_record(elem)
        if result is None:
            return
        record_type, record_data = result
        if record_type in SUPPORTED_RECORD_TYPES:
            record_rows_by_type[record_type].append(record_data)

    def _build_parsed_health_data(
        self,
        workout_rows: list[WorkoutRecord],
        record_rows_by_type: dict[str, list[dict[str, Any]]],
    ) -> ParsedHealthData:
        workouts_df = pd.DataFrame(workout_rows)
        records_by_type_df = {
            record_type: pd.DataFrame(rows) for record_type, rows in record_rows_by_type.items()
        }

        if len(workouts_df) > 0:
            normalized_start_dates_utc = [
                self._normalize_health_datetime_to_utc_naive(raw)
                for raw in workouts_df["startDate"].tolist()
            ]
            workouts_df["startDateUtc"] = pd.Series(
                normalized_start_dates_utc, dtype=DATETIME64_NS_DTYPE
            )
            normalized_end_dates_utc = [
                self._normalize_health_datetime_to_utc_naive(raw)
                for raw in workouts_df["endDate"].tolist()
            ]
            workouts_df["endDateUtc"] = pd.Series(
                normalized_end_dates_utc, dtype=DATETIME64_NS_DTYPE
            )
            normalized_start_dates = [
                self._normalize_workout_start_date(raw) for raw in workouts_df["startDate"].tolist()
            ]
            workouts_df["startDate"] = pd.Series(normalized_start_dates, dtype=DATETIME64_NS_DTYPE)

        self._log(f"Loaded {len(workouts_df)} workouts total.")
        return ParsedHealthData(workouts=workouts_df, records_by_type=records_by_type_df)

    @staticmethod
    def _normalize_workout_start_date(raw_start_date: Any) -> datetime | pd.Timestamp | None:
        if not isinstance(raw_start_date, str):
            return None
        parsed_health_dt = ExportParser._parse_health_datetime(raw_start_date)
        if parsed_health_dt is not None:
            return parsed_health_dt.replace(tzinfo=None)
        parsed_fallback = pd.to_datetime(
            raw_start_date, format=PANDAS_ISO8601_FORMAT, errors="coerce"
        )
        return parsed_fallback if not pd.isna(parsed_fallback) else None

    @staticmethod
    def _normalize_health_datetime_to_utc_naive(
        raw_datetime: Any,
    ) -> datetime | pd.Timestamp | None:
        if not isinstance(raw_datetime, str):
            return None
        parsed_datetime = pd.to_datetime(
            raw_datetime, format=PANDAS_ISO8601_FORMAT, utc=True, errors="coerce"
        )
        if pd.isna(parsed_datetime):
            return None
        return parsed_datetime.tz_localize(None)

    def _load_data(self, zipfile: ZipFile) -> ParsedHealthData:
        self._log("Loading the workouts...")

        with zipfile.open("apple_health_export/export.xml") as export_file:
            workout_rows: list[WorkoutRecord] = []
            record_rows_by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)

            for _, elem in iterparse(
                export_file,
                events=("end",),
                tag=("Workout", "Record"),
                **_SAFE_ITERPARSE_OPTIONS,
            ):
                if elem.tag == "Workout":
                    self._process_workout_event(elem, zipfile, workout_rows)
                    _purge_element(elem)
                else:
                    self._process_record_event(elem, record_rows_by_type)
                    parent = elem.getparent()
                    if parent is not None and parent.tag == "Workout":
                        elem.clear()
                    else:
                        _purge_element(elem)

            return self._build_parsed_health_data(workout_rows, record_rows_by_type)

    def _extract_health_data_record(self, elem: Element) -> tuple[str, dict[str, Any]] | None:
        raw_type = elem.get("type")
        if not raw_type:
            return None
        record_type = raw_type.replace("HKQuantityTypeIdentifier", "")
        record_data: dict[str, Any] = {
            "type": record_type,
            "startDate": elem.get("startDate"),
            "endDate": elem.get("endDate"),
            "value": to_number(elem.get("value")),
        }
        for child in elem:
            if child.tag == "MetadataEntry":
                raw_key = child.get("key", "")
                if raw_key.startswith("HKMetadataKey"):
                    key = raw_key[len("HKMetadataKey") :]
                elif raw_key.startswith("HK"):
                    key = raw_key[2:]
                else:
                    key = raw_key
                value, unit = parse_metadata_value(child.get("value", ""))
                record_data[key] = value
                if unit:
                    record_data[f"{key}Unit"] = unit
        return record_type, record_data

    def _extract_activity_type(self, elem: Element) -> str:
        return elem.get("workoutActivityType", "").replace("HKWorkoutActivityType", "")

    def _create_workout_record(self, elem: Element, activity_type: str) -> WorkoutRecord:
        duration_str = elem.get("duration")
        duration_unit_str: str = elem.get("durationUnit") or ""
        return {
            "activityType": activity_type,
            "duration": (
                duration_to_seconds(float(duration_str), duration_unit_str)
                if duration_str
                else None
            ),
            "durationUnit": "seconds",
            "startDate": elem.get("startDate"),
            "endDate": elem.get("endDate"),
            "source": elem.get("sourceName"),
        }

    @staticmethod
    def _update_motion_timestamps(
        event_type: str,
        event_date: datetime,
        last_paused: datetime | None,
        last_resumed: datetime | None,
    ) -> tuple[datetime | None, datetime | None]:
        if event_type == "HKWorkoutEventTypeMotionPaused":
            if last_paused is None or event_date > last_paused:
                last_paused = event_date
        elif event_type == "HKWorkoutEventTypeMotionResumed":
            if last_resumed is None or event_date > last_resumed:
                last_resumed = event_date
        return last_paused, last_resumed

    @staticmethod
    def _compute_active_end(elem: Element) -> datetime | None:
        """Return the last MotionPaused time if it is not followed by a MotionResumed."""
        last_paused: datetime | None = None
        last_resumed: datetime | None = None
        for child in elem:
            if child.tag != "WorkoutEvent":
                continue
            event_type = child.get("type", "")
            event_date = ExportParser._parse_health_datetime(child.get("date"))
            if event_date is None:
                continue
            last_paused, last_resumed = ExportParser._update_motion_timestamps(
                event_type, event_date, last_paused, last_resumed
            )
        if last_paused is None:
            return None
        if last_resumed is None or last_paused > last_resumed:
            return last_paused
        return None

    def _process_workout_children(
        self, elem: Element, record: WorkoutRecord, zipfile: ZipFile
    ) -> None:
        active_end = self._compute_active_end(elem)
        nested_elevations: list[tuple[float, str | None]] = []
        deferred_interval_routes: list[Element] = []
        for child in elem:
            if child.tag == "WorkoutStatistics":
                self._process_workout_statistics(child, record)
            elif child.tag == "MetadataEntry":
                self._process_metadata_entry(child, record)
            elif child.tag == "WorkoutRoute":
                self._process_workout_route(child, record, zipfile, active_end=active_end)
            elif child.tag == "WorkoutActivity":
                if self._is_interval_activity(child):
                    self._process_interval_activity_elevation(
                        child, record, nested_elevations=nested_elevations
                    )
                    deferred_interval_routes.extend(
                        activity_child
                        for activity_child in child
                        if activity_child.tag == "WorkoutRoute"
                    )
                else:
                    self._process_workout_activity_children(
                        child,
                        record,
                        zipfile,
                        active_end=active_end,
                        nested_elevations=nested_elevations,
                    )
            elif child.tag == "WorkoutEvent" and record.get("activityType") == "Swimming":
                self._collect_workout_event(child, record)

        if record.get("route") is None:
            for route in deferred_interval_routes:
                self._process_workout_route(route, record, zipfile, active_end=active_end)

        self._apply_nested_elevation_fallback(record, nested_elevations)

    @staticmethod
    def _extract_elevation_ascended(child: Element) -> tuple[float, str | None] | None:
        if (
            child.tag == "MetadataEntry"
            and child.get("key", "").replace("HK", "") == "ElevationAscended"
        ):
            raw_val = child.get("value", "")
            value, unit = parse_value(raw_val)
            if isinstance(value, bool):
                num = to_number(raw_val)
                if num is not None:
                    return float(num), unit or "m"
            elif isinstance(value, (int, float)):
                return float(value), unit or "m"
        return None

    @staticmethod
    def _apply_nested_elevation_fallback(
        record: WorkoutRecord, nested_elevations: list[tuple[float, str | None]]
    ) -> None:
        if "ElevationAscended" in record or not nested_elevations:
            return
        total_gain = round(sum(val for val, _ in nested_elevations), 4)
        unit = next((u for _, u in nested_elevations if u), "m")
        record["ElevationAscended"] = total_gain  # type: ignore[typeddict-unknown-key]
        if unit:
            record["ElevationAscendedUnit"] = unit  # type: ignore[typeddict-unknown-key]

    def _process_interval_activity_elevation(
        self,
        elem: Element,
        record: WorkoutRecord,
        nested_elevations: list[tuple[float, str | None]] | None = None,
    ) -> None:
        for child in elem:
            if (elev := self._extract_elevation_ascended(child)) is not None:
                if nested_elevations is not None:
                    nested_elevations.append(elev)
                elif "ElevationAscended" not in record:
                    self._process_metadata_entry(child, record)

    @staticmethod
    def _is_interval_activity(elem: Element) -> bool:
        return any(
            child.tag == "MetadataEntry"
            and child.get("key", "").replace("HK", "") == "WOIntervalStepKeyPath"
            for child in elem
        )

    def _process_workout_activity_children(
        self,
        elem: Element,
        record: WorkoutRecord,
        zipfile: ZipFile,
        *,
        active_end: datetime | None,
        nested_elevations: list[tuple[float, str | None]] | None = None,
    ) -> None:
        for child in elem:
            if child.tag == "WorkoutStatistics":
                self._process_workout_statistics(child, record, fill_missing_only=True)
            elif child.tag == "MetadataEntry":
                if (elev := self._extract_elevation_ascended(child)) is not None:
                    if nested_elevations is not None:
                        nested_elevations.append(elev)
                    elif "ElevationAscended" not in record:
                        self._process_metadata_entry(child, record)
                else:
                    self._process_metadata_entry(child, record)
            elif child.tag == "WorkoutRoute":
                self._process_workout_route(child, record, zipfile, active_end=active_end)

    @staticmethod
    def _parse_swim_event_metadata(child: Element) -> dict[str, Any]:
        extra: dict[str, Any] = {}
        for meta in child:
            if meta.tag != "MetadataEntry":
                continue
            key = meta.get("key", "").replace("HK", "")
            raw_val = meta.get("value", "")
            if key == "SWOLFScore":
                try:
                    extra["swolf"] = float(raw_val)
                except ValueError:
                    pass
            elif key == "SwimmingStrokeStyle":
                num = to_number(raw_val)
                if num is not None:
                    extra["stroke_style"] = int(num)
        return extra

    def _collect_workout_event(self, child: Element, record: WorkoutRecord) -> None:
        raw_type = child.get("type", "")
        if raw_type not in ("HKWorkoutEventTypeLap", "HKWorkoutEventTypeSegment"):
            return

        date_str = child.get("date")
        duration_str = child.get("duration")
        duration_unit = child.get("durationUnit", "")

        if not date_str or not duration_str:
            return

        event: dict[str, Any] = {
            "type": raw_type.replace("HKWorkoutEventType", ""),
            "start_date": date_str,
            "duration_s": duration_to_seconds(float(duration_str), duration_unit),
            **self._parse_swim_event_metadata(child),
        }

        existing = record.get("swimming_events")
        if isinstance(existing, list):
            existing.append(event)
        else:
            record["swimming_events"] = [event]  # type: ignore[literal-required]

    @staticmethod
    def _process_distance_stat(
        record: WorkoutRecord,
        stat_attr_str: str,
        unit: str | None,
        fill_missing_only: bool,
    ) -> None:
        if not fill_missing_only or "distance" not in record:
            record["distance"] = str_distance_to_meters(stat_attr_str, unit)

    @staticmethod
    def _process_non_distance_stat(
        record: WorkoutRecord,
        stat_attr: str,
        stat_type: str,
        stat_attr_str: str,
        unit: str | None,
        fill_missing_only: bool,
    ) -> None:
        key = f"{stat_attr}{stat_type}"
        if not fill_missing_only or key not in record:
            record[key] = float(stat_attr_str)  # type: ignore[literal-required]
            record[f"{key}Unit"] = unit  # type: ignore[literal-required]

    def _process_workout_statistics(
        self, child: Element, record: WorkoutRecord, *, fill_missing_only: bool = False
    ) -> None:
        stat_type = child.get("type", "").replace("HKQuantityTypeIdentifier", "")
        unit = child.get("unit")

        for stat_attr in ["sum", "average", "minimum", "maximum"]:
            if child.get(stat_attr):
                stat_attr_str = child.get(stat_attr) or "0"
                if stat_attr == "sum" and "Distance" in stat_type:
                    self._process_distance_stat(record, stat_attr_str, unit, fill_missing_only)
                else:
                    self._process_non_distance_stat(
                        record, stat_attr, stat_type, stat_attr_str, unit, fill_missing_only
                    )

    def _process_metadata_entry(self, child: Element, record: WorkoutRecord) -> None:
        key = child.get("key", "").replace("HK", "")
        if key == "WOIntervalStepKeyPath":
            return
        value, unit = parse_value(child.get("value", ""))
        if key in record:
            logging.debug("Duplicate key '%s' found, bypassing the second one", key)
        else:
            record[key] = value  # type: ignore[literal-required]
            if unit:
                record[f"{key}Unit"] = unit  # type: ignore[literal-required]

    def _process_workout_route(
        self,
        elem: Element,
        record: WorkoutRecord,
        zipfile: ZipFile,
        active_end: datetime | None = None,
    ) -> None:
        route_path = next(
            (child.get("path") for child in elem if child.tag == "FileReference"), None
        )
        if not route_path:
            return

        route_source = self._gpx_loader.load_route_cached(zipfile, route_path)
        if route_source is None:
            return

        window_start = self._parse_health_datetime(elem.get("startDate"))
        window_end = self._parse_health_datetime(elem.get("endDate"))
        if active_end is not None and window_end is not None:  # type: ignore[redundant-expr]
            window_end = min(window_end, active_end)
        route_part = clip_route_to_window(route_source, window_start, window_end)

        if not route_part.points:
            self._log(
                "Skipping WorkoutRoute window without GPX points: "
                f"{elem.get('startDate')} -> {elem.get('endDate')} ({route_path})"
            )
            return

        route_parts = get_or_init_route_parts(record)
        trimmed_part = trim_overlapping_route_part(route_parts, route_part)
        if trimmed_part is None:
            self._log(
                "Skipping duplicate WorkoutRoute window: "
                f"{elem.get('startDate')} -> {elem.get('endDate')} ({route_path})"
            )
            return
        if len(trimmed_part.points) < len(route_part.points):
            _logger.debug(
                "Trimmed %d overlapping points from WorkoutRoute window: %s -> %s (%s)",
                len(route_part.points) - len(trimmed_part.points),
                elem.get("startDate"),
                elem.get("endDate"),
                route_path,
            )
        route_parts.append(trimmed_part)

        merged_route = merge_route_parts(route_parts)
        if merged_route is not None:
            record["route"] = merged_route

    @staticmethod
    def _parse_health_datetime(raw: str | None) -> datetime | None:
        """Parse Apple Health datetime values like "YYYY-MM-DD HH:MM:SS +0100"."""
        if raw is None:
            return None
        try:
            return datetime.strptime(raw, "%Y-%m-%d %H:%M:%S %z")
        except ValueError:
            return None

    # Keep these as static methods for backward compatibility with tests
    @staticmethod
    def _merge_route_parts(route_parts: list[WorkoutRoute]) -> WorkoutRoute | None:
        return merge_route_parts(route_parts)

    @staticmethod
    def _trim_overlapping_route_part(
        existing_parts: list[WorkoutRoute],
        route_part: WorkoutRoute,
    ) -> WorkoutRoute | None:
        return trim_overlapping_route_part(existing_parts, route_part)

    @staticmethod
    def _get_or_init_route_parts(record: WorkoutRecord) -> list[WorkoutRoute]:
        return get_or_init_route_parts(record)

    def parse(self, export_file: str) -> ParsedHealthData:
        """Parse the export file."""
        try:
            self._gpx_loader.clear_cache()
            self._log("Starting to parse the Apple Health export file...")
            with ZipFile(export_file, "r") as zipfile:
                result = self._load_data(zipfile)
            self._log("Finished parsing the Apple Health export file.")
            return result
        except Exception as e:
            self._log(f"Error during parsing: {e}")
            raise
