"""This script extracts heart rate records with motion context = 2 from Apple Health XML.
It writes the results directly to a CSV file to minimize memory usage."""

import argparse
import csv
import sys
import defusedxml.ElementTree as ET
from pathlib import Path


def get_element_text_value(elem) -> str | None:
    """
    Helper to extract text value from an element, handling nested <real>, <integer>, etc.
    Apple Health XML often nests values inside elements like <value><real>...</real></value>.
    """
    if elem is None:
        return None

    # Check attributes first (e.g., for MetadataEntry key/value pairs)
    if elem.attrib:
        val: str | None = elem.attrib.get("value") or elem.attrib.get("key")
        if val:
            return val

    # Look for child elements like <real>, <integer>, etc.
    child = elem.find("*")
    if child is not None and child.text:
        return str(child.text)

    # Fallback to direct text content
    return str(elem.text) if elem.text is not None else None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract heart rate records from Apple Health XML and save to CSV."
    )
    parser.add_argument("xml_path", type=str, help="Path to the Apple Health XML file.")
    parser.add_argument("csv_path", type=str, help="Path to the output CSV file.")
    return parser.parse_args()


def is_active_motion_record(metadata_elem) -> bool:
    """Return True when a MetadataEntry indicates ACTIVE motion context (value == 2).

    Apple Health exports typically encode this as attributes:
        <MetadataEntry key="HKMetadataKeyHeartRateMotionContext" value="2"/>

    Some exports may nest values as child tags; those are handled as a fallback.
    """
    key = metadata_elem.get("key") or metadata_elem.findtext("key")
    if key != "HKMetadataKeyHeartRateMotionContext":
        return False

    raw_val = metadata_elem.get("value")
    if raw_val is None:
        raw_val = metadata_elem.findtext("integer") or metadata_elem.findtext("real")

    return (raw_val or "").strip() == "2"


def check_record_for_active_motion(elem) -> bool:
    """Iterates through a Record element's metadata to find active motion."""
    for metadata in elem.findall("MetadataEntry"):
        if is_active_motion_record(metadata):
            return True
    return False


def extract_bpm_from_record(elem) -> str | None:
    """Extracts the BPM value from a HeartRate Record element."""
    # Extract BPM value, which is usually inside <value><real>...</real></value>
    value_elem = elem.find("value")
    if value_elem is not None:
        child_val = value_elem.find("*")
        if child_val is not None and child_val.text:
            return str(child_val.text)
    return None


def _process_heart_rate_elem(elem, writer) -> None:
    """Writes an active heart rate Record element to writer, if applicable."""
    if elem.attrib.get("type") != "HKQuantityTypeIdentifierHeartRate":
        return
    if not check_record_for_active_motion(elem):
        return
    start_date = elem.attrib.get("startDate")
    bpm_str = extract_bpm_from_record(elem)
    if start_date and bpm_str:
        writer.writerow([start_date, elem.attrib.get("endDate") or "", bpm_str])


def extract_active_heart_rate_to_csv(xml_path: str, csv_path: str) -> None:
    """
    Extracts heart rate records with motion context = 2 from Apple Health XML.
    Writes the results directly to a CSV file to minimize memory usage.
    """
    if not Path(xml_path).exists():
        print(f"Error: XML file not found at {xml_path}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(csv_path, mode="w", newline="", encoding="utf-8") as csv_file:
            writer = csv.writer(csv_file, delimiter=";")
            writer.writerow(["start_date", "end_date", "bpm"])

            for _event, elem in ET.iterparse(xml_path, events=("end",)):
                if elem.tag == "Record":
                    _process_heart_rate_elem(elem, writer)
                elem.clear()

    except ET.ParseError as e:
        print(f"Error parsing XML file: {e}", file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        print(f"Error reading/writing files: {e}", file=sys.stderr)
        sys.exit(1)

    print("Extraction complete.", file=sys.stderr)


if __name__ == "__main__":
    args = parse_args()
    extract_active_heart_rate_to_csv(args.xml_path, args.csv_path)
