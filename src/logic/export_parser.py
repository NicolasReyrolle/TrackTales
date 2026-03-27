"""Export processor for Apple Health data."""

import logging
from bisect import bisect_left, bisect_right
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime
from types import TracebackType
from typing import Any
from xml.etree.ElementTree import Element
from zipfile import ZipFile

import pandas as pd
from defusedxml.ElementTree import iterparse

from logic.models import WorkoutRecord
from logic.parsed_health_data import ParsedHealthData
from logic.workout_route import RoutePoint, WorkoutRoute

_logger = logging.getLogger(__name__)

# Configuration constants
WORKOUT_PROGRESS_INTERVAL = 100  # Report progress every N workouts

# Only parse record types that the application currently supports to limit memory usage.
SUPPORTED_RECORD_TYPES = frozenset({"HeartRate", "BodyMass", "VO2Max", "RunningPower"})


class ExportParser:
    """Reads and parses Apple Health export files."""

    def __init__(self, progress_callback: Callable[[str], None] | None = None) -> None:
        self.progress_callback = progress_callback
        self._route_cache: dict[str, WorkoutRoute | None] = {}

    def __enter__(self) -> "ExportParser":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        # Nothing to do for now
        pass

    @staticmethod
    def to_number(raw: str | None) -> float | int | None:
        """Convert a string to a number (int or float), or return None if conversion fails."""
        if raw is None:
            return None
        try:
            value = float(raw)
            return int(value) if value.is_integer() else value
        except ValueError:
            return None

    @staticmethod
    def parse_metadata_value(raw_value: str | None) -> tuple[Any, str | None]:
        """
        Parse a metadata entry value without boolean coercion.

        Unlike _parse_value, numeric values "0" and "1" are returned as integers,
        not booleans. This is needed for enumerated metadata fields such as
        HeartRateMotionContext (0/1/2).

        Returns: (value, unit) where unit is None when no unit is present.
        """
        if not raw_value:
            return None, None

        raw_value = raw_value.strip()

        parts = raw_value.split(maxsplit=1)
        if len(parts) == 1:
            num = ExportParser.to_number(parts[0])
            if num is not None:
                return num, None
            return parts[0], None

        num = ExportParser.to_number(parts[0])
        if num is not None:
            unit = parts[1].strip() or None
            return float(num), unit
        return raw_value, None

    @staticmethod
    def _parse_value(raw_value: str | None) -> tuple[Any, str | None]:
        """
        Internal helper: Separates value and unit, converts to standard metric system.

        Specific rules:
        - Number without unit (0 or 1) -> Boolean (False/True)
        - Number without unit (other) -> Float
        - String (not a number) -> String
        - "Value Unit" -> Converted Float + Unit

        Returns: (value, unit) or (None, None)
        """
        # Check if value is empty or None
        if not raw_value:
            return None, None

        # CASE A: No unit detected (No space)
        if " " not in raw_value:
            try:
                val = float(raw_value)

                # Logic for Booleans (0 or 1 without unit)
                # We compare with 0 and 1. Note that 0.0 == 0 is True in Python.
                if val == 0:
                    return False, None
                if val == 1:
                    return True, None

                # Other numbers (e.g. "10", "42.5")
                return val, None

            except ValueError:
                # It is not a number, so it is a string (e.g. "Europe/Luxembourg")
                return raw_value, None

        # CASE B: Value with Unit (contains space)
        parts = raw_value.split(" ")

        # Handle cases like "String with spaces" that are not numbers
        # We try to parse the first part as a number. If it fails, treat whole string as text.
        try:
            val = float(parts[0])
        except ValueError:
            return raw_value, None

        unit = parts[1]

        # --- Unit Conversion Logic ---
        if unit == "cm":
            val = val / 100.0
            unit = "m"

        elif unit == "%":
            val = val / 100.0
            unit = "%"

        elif unit == "degF":
            val = (val - 32) * 5.0 / 9.0
            unit = "degC"

        return val, unit

    @staticmethod
    def duration_to_seconds(value: float, unit: str = "min") -> int:
        """Convert duration to seconds based on the unit."""
        if unit == "min" or unit == "":
            return int(value * 60)
        elif unit == "h":
            return int(value * 3600)
        elif unit == "s":
            return int(value)
        else:
            raise ValueError(f"Unknown duration unit: {unit}")

    def _log(self, message: str) -> None:
        """Emit progress message if callback is enabled."""
        if self.progress_callback:
            try:
                self.progress_callback(message)
            except Exception:
                _logger.debug(message)

    def _process_workout_event(
        self,
        elem: Element,
        zipfile: ZipFile,
        workout_rows: list[WorkoutRecord],
    ) -> None:
        """Process a workout element and append the normalized workout record."""
        activity_type = self._extract_activity_type(elem)
        record = self._create_workout_record(elem, activity_type)
        self._process_workout_children(elem, record, zipfile)
        workout_rows.append(record)

        if len(workout_rows) % WORKOUT_PROGRESS_INTERVAL == 0:
            self._log(f"Processed {len(workout_rows)} workouts...")

    def _process_record_event(
        self,
        elem: Element,
        record_rows_by_type: dict[str, list[dict[str, Any]]],
    ) -> None:
        """Process a health record element and store supported record types."""
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
        """Build ParsedHealthData from parsed row collections."""
        workouts_df = pd.DataFrame(workout_rows)
        records_by_type_df = {
            record_type: pd.DataFrame(rows) for record_type, rows in record_rows_by_type.items()
        }

        if len(workouts_df) > 0:
            workouts_df["startDate"] = pd.to_datetime(workouts_df["startDate"]).dt.tz_localize(None)

        self._log(f"Loaded {len(workouts_df)} workouts total.")
        return ParsedHealthData(workouts=workouts_df, records_by_type=records_by_type_df)

    def _load_data(self, zipfile: ZipFile) -> ParsedHealthData:
        """Load workouts and HealthKit records from the export file into ParsedHealthData."""
        self._log("Loading the workouts...")

        with zipfile.open("apple_health_export/export.xml") as export_file:
            workout_rows: list[WorkoutRecord] = []
            record_rows_by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)

            for _, elem in iterparse(export_file, events=("end",)):
                if elem.tag == "Workout":
                    self._process_workout_event(elem, zipfile, workout_rows)
                    elem.clear()
                elif elem.tag == "Record":
                    self._process_record_event(elem, record_rows_by_type)
                    elem.clear()

            return self._build_parsed_health_data(workout_rows, record_rows_by_type)

    def _extract_health_data_record(self, elem: Element) -> tuple[str, dict[str, Any]] | None:
        """Extract and clean health data record from element attributes and metadata."""
        raw_type = elem.get("type")
        if not raw_type:
            return None
        record_type = raw_type.replace("HKQuantityTypeIdentifier", "")
        record_data: dict[str, Any] = {
            "type": record_type,
            "startDate": elem.get("startDate"),
            "endDate": elem.get("endDate"),
            "value": self.to_number(elem.get("value")),
        }
        # Include metadata entries as additional fields
        for child in elem:
            if child.tag == "MetadataEntry":
                raw_key = child.get("key", "")
                if raw_key.startswith("HKMetadataKey"):
                    key = raw_key[len("HKMetadataKey") :]
                elif raw_key.startswith("HK"):
                    key = raw_key[2:]
                else:
                    key = raw_key
                value, unit = self.parse_metadata_value(child.get("value", ""))
                record_data[key] = value
                if unit:
                    record_data[f"{key}Unit"] = unit
        return record_type, record_data

    def _extract_activity_type(self, elem: Element) -> str:
        """Extract and clean activity type from workout element."""
        activity_type_raw = elem.get("workoutActivityType", "")
        return activity_type_raw.replace("HKWorkoutActivityType", "")

    def _create_workout_record(self, elem: Element, activity_type: str) -> WorkoutRecord:
        """Create base workout record from element attributes."""
        duration_str = elem.get("duration")
        duration_unit_str: str = elem.get("durationUnit") or ""
        return {
            "activityType": activity_type,
            "duration": (
                self.duration_to_seconds(float(duration_str), duration_unit_str)
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
        """Update motion timestamps based on event type."""
        if event_type == "HKWorkoutEventTypeMotionPaused":
            if last_paused is None or event_date > last_paused:
                last_paused = event_date
        elif event_type == "HKWorkoutEventTypeMotionResumed":
            if last_resumed is None or event_date > last_resumed:
                last_resumed = event_date
        return last_paused, last_resumed

    @staticmethod
    def _compute_active_end(elem: Element) -> datetime | None:
        """Return the last MotionPaused time if it is not followed by a MotionResumed.

        When the user forgets to stop the watch before getting into a vehicle, the GPS
        keeps recording at vehicle speed after the final pause.  Trimming route points
        beyond this timestamp prevents impossible best-segment values.
        """
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
        """Process child elements of workout (statistics and metadata)."""
        active_end = self._compute_active_end(elem)
        for child in elem:
            if child.tag == "WorkoutStatistics":
                self._process_workout_statistics(child, record)
            elif child.tag == "MetadataEntry":
                self._process_metadata_entry(child, record)
            elif child.tag == "WorkoutRoute":
                self._process_workout_route(child, record, zipfile, active_end=active_end)
            elif child.tag == "WorkoutActivity":
                self._process_workout_activity_children(
                    child, record, zipfile, active_end=active_end
                )

    def _process_workout_activity_children(
        self, elem: Element, record: WorkoutRecord, zipfile: ZipFile, *, active_end: datetime | None
    ) -> None:
        """Process children of a WorkoutActivity element.

        Only fills keys not already present in the record so that top-level Workout
        statistics/metadata take precedence over WorkoutActivity values when both exist.
        The active_end computed from the parent Workout is reused to avoid an extra pass.
        """
        for child in elem:
            if child.tag == "WorkoutStatistics":
                self._process_workout_statistics(child, record, fill_missing_only=True)
            elif child.tag == "MetadataEntry":
                self._process_metadata_entry(child, record)  # already skips duplicates
            elif child.tag == "WorkoutRoute":
                self._process_workout_route(child, record, zipfile, active_end=active_end)

    @staticmethod
    def str_distance_to_meters(value: str, unit: str | None) -> int:
        """Convert distance to meters."""
        if unit is None:
            raise ValueError("Distance unit is missing (None). Cannot convert to meters.")
        if unit == "km":
            return int(float(value) * 1000)
        if unit == "m":
            return int(float(value))
        if unit == "mi":
            return int(float(value) * 1609.34)
        raise ValueError(f"Unknown distance unit: {unit}")

    @staticmethod
    def _process_distance_stat(
        record: WorkoutRecord,
        stat_attr_str: str,
        unit: str | None,
        fill_missing_only: bool,
    ) -> None:
        """Process distance statistic (consolidates all distance types into the `distance`
        field)."""
        if not fill_missing_only or "distance" not in record:
            record["distance"] = ExportParser.str_distance_to_meters(stat_attr_str, unit)

    @staticmethod
    def _process_non_distance_stat(
        record: WorkoutRecord,
        stat_attr: str,
        stat_type: str,
        stat_attr_str: str,
        unit: str | None,
        fill_missing_only: bool,
    ) -> None:
        """Process non-distance statistic."""
        key = f"{stat_attr}{stat_type}"
        if not fill_missing_only or key not in record:
            record[key] = float(stat_attr_str)  # type: ignore[literal-required]
            record[f"{key}Unit"] = unit  # type: ignore[literal-required]

    def _process_workout_statistics(
        self, child: Element, record: WorkoutRecord, *, fill_missing_only: bool = False
    ) -> None:
        """Process workout statistics child element.

        When fill_missing_only is True, only populate keys that are not already present
        in the record so that top-level Workout values take precedence.
        """
        stat_type = child.get("type", "").replace("HKQuantityTypeIdentifier", "")
        unit = child.get("unit")

        for stat_attr in ["sum", "average", "minimum", "maximum"]:
            if child.get(stat_attr):
                stat_attr_str = child.get(stat_attr) or "0"
                # Consolidate all distance types into a single Distance field
                if stat_attr == "sum" and "Distance" in stat_type:
                    self._process_distance_stat(record, stat_attr_str, unit, fill_missing_only)
                else:
                    self._process_non_distance_stat(
                        record, stat_attr, stat_type, stat_attr_str, unit, fill_missing_only
                    )

    @staticmethod
    def _parse_gpx_speed(ext_elem: Element | None) -> float:
        """Extract speed value from GPX extensions element."""
        if ext_elem is None:
            return 0.0
        speed_elem = ext_elem.find("{http://www.topografix.com/GPX/1/1}speed")
        if speed_elem is None or not speed_elem.text:
            return 0.0
        try:
            return float(speed_elem.text)
        except ValueError:
            return 0.0

    @staticmethod
    def _extract_gpx_point_data(elem: Element) -> tuple[str, str, str, str, float]:
        """Extract coordinate and metadata from a GPX trackpoint element."""
        latitude = elem.get("lat") or ""
        longitude = elem.get("lon") or ""
        if not latitude or not longitude:
            _logger.debug(
                "Skipping GPX trackpoint with missing latitude/longitude: %s", elem.attrib
            )

        ele_elem = elem.find("{http://www.topografix.com/GPX/1/1}ele")
        time_elem = elem.find("{http://www.topografix.com/GPX/1/1}time")

        altitude = (ele_elem.text or "0.0") if ele_elem is not None else "0.0"
        time_str = (time_elem.text or "") if time_elem is not None else ""

        ext_elem = elem.find("{http://www.topografix.com/GPX/1/1}extensions")
        speed_val = ExportParser._parse_gpx_speed(ext_elem)

        return latitude, longitude, altitude, time_str, speed_val

    @staticmethod
    def _create_route_point(
        latitude: str, longitude: str, altitude: str, time_str: str, speed_val: float
    ) -> RoutePoint:
        """Create a RoutePoint from extracted GPX data."""
        return RoutePoint(
            time=datetime.fromisoformat(time_str.replace("Z", "+00:00")),
            latitude=float(latitude),
            longitude=float(longitude),
            altitude=float(altitude),
            speed=speed_val,
        )

    def _load_route(self, zipfile: ZipFile, route_path: str) -> WorkoutRoute | None:
        """Load GPX route file from the export zip."""
        try:
            with zipfile.open(f"apple_health_export{route_path}") as route_file:
                points: list[RoutePoint] = []
                for _, elem in iterparse(route_file, events=("end",)):
                    if elem.tag == "{http://www.topografix.com/GPX/1/1}trkpt":
                        point_data = self._extract_gpx_point_data(elem)
                        points.append(self._create_route_point(*point_data))
                        elem.clear()
                return WorkoutRoute(points=points)
        except KeyError:
            self._log(f"Route file not found in export: {route_path}")
            return None

    @staticmethod
    def _parse_health_datetime(raw: str | None) -> datetime | None:
        """Parse Apple Health datetime values like "YYYY-MM-DD HH:MM:SS +0100"."""
        if raw is None:
            return None
        try:
            return datetime.strptime(raw, "%Y-%m-%d %H:%M:%S %z")
        except ValueError:
            return None

    def _load_route_cached(self, zipfile: ZipFile, route_path: str) -> WorkoutRoute | None:
        """Load GPX route once per file path for the current export parsing session."""
        if route_path not in self._route_cache:
            self._route_cache[route_path] = self._load_route(zipfile, route_path)
        return self._route_cache[route_path]

    @staticmethod
    def clip_route_to_window(
        route: WorkoutRoute,
        window_start: datetime | None,
        window_end: datetime | None,
    ) -> WorkoutRoute:
        """Return route points clipped to WorkoutRoute time window.

        Apple Health exports can reference the same GPX file from multiple adjacent
        WorkoutRoute entries. We must keep only points that belong to the current
        window to avoid creating artificial cross-window traces.

        Uses binary search on the cached sorted-times list for O(log n) clipping instead
        of an O(n) linear scan, which matters when the same cached GPX route is clipped
        many times across a large export. Falls back to a linear scan if route times
        are not monotonic.
        """
        if window_start is None or window_end is None:
            return WorkoutRoute(points=list(route.points))

        times = route.sorted_times()
        if not times:
            return WorkoutRoute(points=[])

        try:
            is_monotonic = all(t1 <= t2 for t1, t2 in zip(times, times[1:]))
        except TypeError:
            _logger.debug("Non-comparable route times encountered; falling back to linear clipping")
            is_monotonic = False

        if is_monotonic:
            left = bisect_left(times, window_start)
            right = bisect_right(times, window_end)
            return WorkoutRoute(points=route.points[left:right])

        # Fallback: linear scan for routes with non-monotonic or invalid times.
        clipped_points: list[RoutePoint] = [
            point
            for point in route.points
            if point.time is not None  # type: ignore[redundant-expr]
            and window_start <= point.time <= window_end
        ]
        return WorkoutRoute(points=clipped_points)

    @staticmethod
    def _merge_route_parts(route_parts: list[WorkoutRoute]) -> WorkoutRoute | None:
        """Merge route parts as a compatibility route while preserving part boundaries.

        Use ``route_parts`` for analytics. The merged ``route`` field remains available
        for legacy consumers that expect a single route object.
        """
        if not route_parts:
            return None

        merged_points: list[RoutePoint] = []
        for route_part in route_parts:
            if not route_part.points:
                continue

            if merged_points and merged_points[-1] == route_part.points[0]:
                merged_points.extend(route_part.points[1:])
            else:
                merged_points.extend(route_part.points)

        return WorkoutRoute(points=merged_points) if merged_points else None

    def _process_workout_route(
        self,
        elem: Element,
        record: WorkoutRecord,
        zipfile: ZipFile,
        active_end: datetime | None = None,
    ) -> None:
        """Process one WorkoutRoute XML block as an independent time window.

        Behavior is intentionally window-based to prevent unrealistic best-segment
        calculations when adjacent windows reuse GPX files or when a window has no
        matching GPX points.

        ``active_end`` clips the window end to the last unpaired MotionPaused event,
        which prevents vehicle-speed GPS points recorded after forgetting to stop the
        watch from influencing best-segment calculations.
        """
        route_path: str | None = None
        for child in elem:
            if child.tag == "FileReference":
                route_path = child.get("path")

        if not route_path:
            return

        route_source = self._load_route_cached(zipfile, route_path)
        if route_source is None:
            return

        window_start = self._parse_health_datetime(elem.get("startDate"))
        window_end = self._parse_health_datetime(elem.get("endDate"))
        if active_end is not None and window_end is not None:  # type: ignore[redundant-expr]
            window_end = min(window_end, active_end)
        route_part = self.clip_route_to_window(route_source, window_start, window_end)

        if not route_part.points:
            self._log(
                "Skipping WorkoutRoute window without GPX points: "
                f"{elem.get('startDate')} -> {elem.get('endDate')} ({route_path})"
            )
            return

        existing_parts = record.get("route_parts")
        if isinstance(existing_parts, list):
            existing_parts.append(route_part)
            route_parts = existing_parts
        else:
            route_parts = [route_part]
            record["route_parts"] = route_parts

        merged_route = self._merge_route_parts(route_parts)
        if merged_route is not None:
            record["route"] = merged_route

    def _process_metadata_entry(self, child: Element, record: WorkoutRecord) -> None:
        """Process metadata entry child element."""
        key = child.get("key", "").replace("HK", "")

        # Skip keys that have no meaning for analysis
        if key == "WOIntervalStepKeyPath":
            return

        value, unit = self._parse_value(child.get("value", ""))

        # If the key already exists, do not consider it as there can be duplicate in the real file
        if key in record:
            logging.debug("Duplicate key '%s' found, bypassing the second one", key)
        else:
            record[key] = value  # type: ignore[literal-required]
            if unit:
                record[f"{key}Unit"] = unit  # type: ignore[literal-required]

    def parse(self, export_file: str) -> ParsedHealthData:
        """Parse the export file."""

        try:
            self._route_cache.clear()
            self._log("Starting to parse the Apple Health export file...")
            with ZipFile(export_file, "r") as zipfile:
                result = self._load_data(zipfile)
            self._log("Finished parsing the Apple Health export file.")
            return result
        except Exception as e:
            self._log(f"Error during parsing: {e}")
            raise
