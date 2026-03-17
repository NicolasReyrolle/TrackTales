"""Anonymize GPX files by shifting all coordinates so the first point is (0,0)."""

from __future__ import annotations

import argparse
import math
import sys
import xml.etree.ElementTree as _stdlib_ET
from collections.abc import Callable
from pathlib import Path
from typing import TypeAlias

from defusedxml import ElementTree as ET

GPX_NAMESPACE = "http://www.topografix.com/GPX/1/1"  # noqa: S5332
XSI_NAMESPACE = "http://www.w3.org/2001/XMLSchema-instance"  # noqa: S5332
GPX_TRKPT_XPATH = ".//gpx:trkpt"
ZERO_THRESHOLD = 1e-12
Vector3: TypeAlias = tuple[float, float, float]
LatLon: TypeAlias = tuple[float, float]
RotateFn: TypeAlias = Callable[[Vector3], Vector3]


def _lat_lon_to_vector(latitude: float, longitude: float) -> Vector3:
    """Convert latitude/longitude in degrees to a 3D unit vector on the sphere."""
    lat_rad = math.radians(latitude)
    lon_rad = math.radians(longitude)
    cos_lat = math.cos(lat_rad)
    return (
        cos_lat * math.cos(lon_rad),
        cos_lat * math.sin(lon_rad),
        math.sin(lat_rad),
    )


def _vector_to_lat_lon(vector: Vector3) -> LatLon:
    """Convert a 3D unit vector to latitude/longitude in degrees."""
    x_coord, y_coord, z_coord = vector
    latitude = math.degrees(math.atan2(z_coord, math.sqrt(x_coord * x_coord + y_coord * y_coord)))
    longitude = math.degrees(math.atan2(y_coord, x_coord))
    return latitude, longitude


def _dot(a: Vector3, b: Vector3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Vector3, b: Vector3) -> Vector3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _norm(vector: Vector3) -> float:
    return math.sqrt(_dot(vector, vector))


def _normalize(vector: Vector3) -> Vector3:
    vector_norm = _norm(vector)
    if vector_norm < ZERO_THRESHOLD:
        raise ValueError("Cannot normalize a zero vector")
    return (vector[0] / vector_norm, vector[1] / vector_norm, vector[2] / vector_norm)


def _rotate_with_axis_angle(
    vector: Vector3,
    axis: Vector3,
    angle: float,
) -> Vector3:
    """Rotate a vector around a unit axis using Rodrigues' formula."""
    axis_unit = _normalize(axis)
    cos_angle = math.cos(angle)
    sin_angle = math.sin(angle)
    axis_dot_vector = _dot(axis_unit, vector)
    axis_cross_vector = _cross(axis_unit, vector)
    return (
        vector[0] * cos_angle
        + axis_cross_vector[0] * sin_angle
        + axis_unit[0] * axis_dot_vector * (1.0 - cos_angle),
        vector[1] * cos_angle
        + axis_cross_vector[1] * sin_angle
        + axis_unit[1] * axis_dot_vector * (1.0 - cos_angle),
        vector[2] * cos_angle
        + axis_cross_vector[2] * sin_angle
        + axis_unit[2] * axis_dot_vector * (1.0 - cos_angle),
    )


def _build_rotation(
    source_vector: Vector3,
    target_vector: Vector3,
) -> RotateFn:
    """Return a rotation function mapping source_vector onto target_vector on the sphere."""
    source_unit = _normalize(source_vector)
    target_unit = _normalize(target_vector)
    cross_vec = _cross(source_unit, target_unit)
    cross_norm = _norm(cross_vec)
    dot_value = max(-1.0, min(1.0, _dot(source_unit, target_unit)))

    if cross_norm < ZERO_THRESHOLD:
        if dot_value > 0.0:
            return lambda vector: vector

        # 180-degree rotation: pick any axis orthogonal to source.
        fallback_axis = _cross(source_unit, (0.0, 0.0, 1.0))
        if _norm(fallback_axis) < ZERO_THRESHOLD:
            fallback_axis = _cross(source_unit, (0.0, 1.0, 0.0))
        return lambda vector: _rotate_with_axis_angle(vector, fallback_axis, math.pi)

    axis = (cross_vec[0] / cross_norm, cross_vec[1] / cross_norm, cross_vec[2] / cross_norm)
    angle = math.atan2(cross_norm, dot_value)
    return lambda vector: _rotate_with_axis_angle(vector, axis, angle)


def anonymize_gpx(file_path: str) -> None:
    """Rewrite a GPX file in place while preserving route geometry and distances."""
    tree = ET.parse(file_path)
    root = tree.getroot()
    if root is None:
        raise ValueError("Invalid XML structure in file")
    namespaces = {"gpx": GPX_NAMESPACE}

    first_pt = root.find(GPX_TRKPT_XPATH, namespaces)
    if first_pt is None:
        raise ValueError("No track point found in file")

    lat_value = first_pt.get("lat")
    lon_value = first_pt.get("lon")
    if lat_value is None or lon_value is None:
        raise ValueError("First track point is missing lat/lon attributes")

    first_lat = float(lat_value)
    first_lon = float(lon_value)
    if abs(first_lat) < ZERO_THRESHOLD and abs(first_lon) < ZERO_THRESHOLD:
        raise ValueError("File is already anonymized: first point is 0,0")

    source_vector = _lat_lon_to_vector(first_lat, first_lon)
    target_vector = _lat_lon_to_vector(0.0, 0.0)
    rotate = _build_rotation(source_vector, target_vector)

    for trkpt in root.findall(GPX_TRKPT_XPATH, namespaces):
        point_lat = trkpt.get("lat")
        point_lon = trkpt.get("lon")
        if point_lat is None or point_lon is None:
            continue

        point_vector = _lat_lon_to_vector(float(point_lat), float(point_lon))
        rotated_vector = rotate(point_vector)
        new_lat, new_lon = _vector_to_lat_lon(rotated_vector)
        trkpt.set("lat", f"{new_lat:.6f}")
        trkpt.set("lon", f"{new_lon:.6f}")

    # Preserve original namespace style instead of introducing ns0 prefixes.
    _stdlib_ET.register_namespace("", GPX_NAMESPACE)
    _stdlib_ET.register_namespace("xsi", XSI_NAMESPACE)
    tree.write(file_path, encoding="utf-8", xml_declaration=True)


def _transform_tree_with_rotation(
    tree: _stdlib_ET.ElementTree[_stdlib_ET.Element[str]],
    rotate: RotateFn,
    forced_first_point: LatLon | None = None,
) -> LatLon | None:
    """Apply a rotation to all track points in a tree.

    Returns the last transformed (lat, lon), or None if no points exist.
    If forced_first_point is provided, first transformed point is set exactly
    to that value (used to lock continuity across split files).
    """
    root = tree.getroot()
    namespaces = {"gpx": GPX_NAMESPACE}

    transformed_last: LatLon | None = None
    first_written = False

    for trkpt in root.findall(GPX_TRKPT_XPATH, namespaces):
        point_lat = trkpt.get("lat")
        point_lon = trkpt.get("lon")
        if point_lat is None or point_lon is None:
            continue

        point_vector = _lat_lon_to_vector(float(point_lat), float(point_lon))
        rotated_vector = rotate(point_vector)
        new_lat, new_lon = _vector_to_lat_lon(rotated_vector)
        rounded_lat = round(new_lat, 6)
        rounded_lon = round(new_lon, 6)

        if not first_written and forced_first_point is not None:
            rounded_lat, rounded_lon = forced_first_point

        trkpt.set("lat", f"{rounded_lat:.6f}")
        trkpt.set("lon", f"{rounded_lon:.6f}")

        first_written = True
        transformed_last = (rounded_lat, rounded_lon)

    return transformed_last


def anonymize_gpx_single_track(
    file_paths: list[Path],
    output_dir: Path | None = None,
) -> list[Path]:
    """Anonymize multiple split GPX files as one continuous track.

    All files are transformed with one shared rotation derived from the first
    file's first point. Continuity is enforced so the first point of file n+1
    is exactly the last point of file n.
    """
    if not file_paths:
        raise ValueError("No input files provided")

    namespaces = {"gpx": GPX_NAMESPACE}

    first_tree = ET.parse(file_paths[0])
    first_root = first_tree.getroot()
    if first_root is None:
        raise ValueError(f"Invalid XML structure in file: {file_paths[0]}")

    first_pt = first_root.find(GPX_TRKPT_XPATH, namespaces)
    if first_pt is None:
        raise ValueError(f"No track point found in file: {file_paths[0]}")

    lat_value = first_pt.get("lat")
    lon_value = first_pt.get("lon")
    if lat_value is None or lon_value is None:
        raise ValueError("First track point is missing lat/lon attributes")

    source_vector = _lat_lon_to_vector(float(lat_value), float(lon_value))
    target_vector = _lat_lon_to_vector(0.0, 0.0)
    rotate = _build_rotation(source_vector, target_vector)

    _stdlib_ET.register_namespace("", GPX_NAMESPACE)
    _stdlib_ET.register_namespace("xsi", XSI_NAMESPACE)

    written_paths: list[Path] = []
    previous_last: LatLon | None = None

    for index, file_path in enumerate(file_paths):
        tree = ET.parse(file_path)
        root = tree.getroot()
        if root is None:
            raise ValueError(f"Invalid XML structure in file: {file_path}")
        forced_first = previous_last if index > 0 else None
        previous_last = _transform_tree_with_rotation(tree, rotate, forced_first)  # type: ignore[arg-type]

        if output_dir is None:
            target_path = file_path
        else:
            output_dir.mkdir(parents=True, exist_ok=True)
            target_path = output_dir / file_path.name

        tree.write(target_path, encoding="utf-8", xml_declaration=True)
        written_paths.append(target_path)

    return written_paths


def _normalize_date_for_filename(date_value: str) -> str:
    """Convert accepted date formats to YYYY-MM-DD for route filenames."""
    value = date_value.strip()
    separator: str | None = None
    if "/" in value:
        separator = "/"
    elif "-" in value:
        separator = "-"

    if separator is None:
        raise ValueError("Unsupported date format. Use DD/MM/YYYY or YYYY-MM-DD")

    parts = value.split(separator)
    if len(parts) != 3:
        raise ValueError("Unsupported date format. Use DD/MM/YYYY or YYYY-MM-DD")

    if separator == "/":
        day, month, year = parts
    else:
        year, month, day = parts

    return f"{year.zfill(4)}-{month.zfill(2)}-{day.zfill(2)}"


def _files_from_date(routes_dir: Path, date_value: str) -> list[Path]:
    """Resolve all route files for one date, sorted by filename."""
    normalized = _normalize_date_for_filename(date_value)
    matched = sorted(routes_dir.glob(f"route_{normalized}_*.gpx"))
    if not matched:
        raise ValueError(f"No GPX files found for date {normalized} in {routes_dir}")
    return matched


def _process_output_files(
    input_files: list[Path],
    output_dir: Path | None,
) -> None:
    """Process files for non-single-track mode."""
    if output_dir is None:
        for file_path in input_files:
            anonymize_gpx(str(file_path))
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    for file_path in input_files:
        target = output_dir / file_path.name
        target.write_bytes(file_path.read_bytes())
        anonymize_gpx(str(target))


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Rewrite GPX file(s) by shifting coordinates to anonymize location"
    )
    parser.add_argument("files", nargs="*", help="Path(s) to GPX/XML file(s)")
    parser.add_argument(
        "--date",
        default=None,
        help="Date to auto-select route files (DD/MM/YYYY or YYYY-MM-DD)",
    )
    parser.add_argument(
        "--routes-dir",
        default="tests/fixtures/exports/workout-routes",
        help="Directory used with --date to discover route files",
    )
    parser.add_argument(
        "--single-track",
        action="store_true",
        help="Treat all input files as one split track and enforce continuity between files",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Optional output directory; when omitted, files are rewritten in place",
    )
    args = parser.parse_args()

    try:
        input_files: list[Path]
        if args.date:
            input_files = _files_from_date(Path(args.routes_dir), args.date)
        else:
            input_files = [Path(file_path) for file_path in args.files]

        if not input_files:
            raise ValueError("Provide files or use --date to select them automatically")

        output_dir = Path(args.output_dir) if args.output_dir else None

        if args.single_track:
            anonymize_gpx_single_track(input_files, output_dir)
        else:
            _process_output_files(input_files, output_dir)
    except (_stdlib_ET.ParseError, OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
