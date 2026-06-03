"""This script extracts heart rate records with motion context = 2 from Apple Health XML.
It writes the results directly to a CSV file to minimize memory usage."""

import argparse
import csv
import xml.etree.ElementTree as ET


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract heart rate records from Apple Health XML and save to CSV."
    )
    parser.add_argument("xml_path", type=str, help="Path to the Apple Health XML file.")
    parser.add_argument("csv_path", type=str, help="Path to the output CSV file.")
    return parser.parse_args()


def extract_active_heart_rate_to_csv(xml_path: str, csv_path: str) -> None:
    """
    Extracts heart rate records with motion context = 2 from Apple Health XML.
    Writes the results directly to a CSV file to minimize memory usage.
    """
    with open(csv_path, mode="w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file, delimiter=";")  # Semicolon is better for French Excel
        writer.writerow(["start_date", "bpm"])

        # iterparse reads the file incrementally
        context = ET.iterparse(xml_path, events=("end",))

        for event, elem in context:
            if elem.tag == "Record":
                record_type = elem.attrib.get("type")

                if record_type == "HKQuantityTypeIdentifierHeartRate":
                    is_active_motion = False

                    # Inspect child nodes for the specific motion context
                    for metadata in elem.findall("MetadataEntry"):
                        key = metadata.attrib.get("key")
                        value = metadata.attrib.get("value")

                        if key == "HKMetadataKeyHeartRateMotionContext" and value == "2":
                            is_active_motion = True
                            break

                    if is_active_motion:
                        start_date = elem.attrib.get("startDate")
                        bpm = elem.attrib.get("value")

                        if start_date and bpm:
                            writer.writerow([start_date, bpm])

                # Clear the element from memory to prevent RAM exhaustion
                elem.clear()


if __name__ == "__main__":
    args = parse_args()
    extract_active_heart_rate_to_csv(args.xml_path, args.csv_path)
