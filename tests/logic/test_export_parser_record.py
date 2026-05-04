"""Test parsing of complex real-world records from Apple Health export."""

from __future__ import annotations

from collections.abc import Callable
from xml.etree.ElementTree import Element

import pandas as pd
import pytest

from logic.export_parser import ExportParser, ParsedHealthData
from logic.records_by_type import RecordsByType


class TestParsedHealthData:
    """Test cases for ParsedHealthData dataclass."""

    def test_parsed_health_data_creation(self) -> None:
        """Test creating ParsedHealthData with workouts and records."""
        workouts_df = pd.DataFrame({"activityType": ["Running"]})
        records_df = pd.DataFrame({"type": ["HeartRate"], "value": [67]})
        records_by_type = {"HeartRate": records_df}

        health_data = ParsedHealthData(workouts=workouts_df, records_by_type=records_by_type)

        assert len(health_data.workouts) == 1
        assert "HeartRate" in health_data.records_by_type
        assert len(health_data.records_by_type["HeartRate"]) == 1

    def test_all_records_property_single_type(self) -> None:
        """Test all_records property with single record type."""
        records_df = pd.DataFrame({"type": ["HeartRate"], "value": [67]})
        records_by_type = {"HeartRate": records_df}
        health_data = ParsedHealthData(workouts=pd.DataFrame(), records_by_type=records_by_type)

        all_records = health_data.all_records
        assert len(all_records) == 1
        assert all_records.iloc[0]["value"] == 67

    def test_all_records_property_multiple_types(self) -> None:
        """Test all_records property combining multiple record types."""
        hr_df = pd.DataFrame({"type": ["HeartRate"], "value": [67]})
        weight_df = pd.DataFrame({"type": ["BodyMass"], "value": [70.5]})
        records_by_type = {"HeartRate": hr_df, "BodyMass": weight_df}
        health_data = ParsedHealthData(workouts=pd.DataFrame(), records_by_type=records_by_type)

        all_records = health_data.all_records
        assert len(all_records) == 2
        assert set(all_records["type"]) == {"HeartRate", "BodyMass"}

    def test_all_records_property_empty(self) -> None:
        """Test all_records property with no records."""
        health_data = ParsedHealthData(workouts=pd.DataFrame(), records_by_type={})

        all_records = health_data.all_records
        assert len(all_records) == 0
        assert isinstance(all_records, pd.DataFrame)

    def test_parsed_health_data_is_frozen(self) -> None:
        """Test that ParsedHealthData is immutable (frozen)."""
        health_data = ParsedHealthData(workouts=pd.DataFrame(), records_by_type={})

        with pytest.raises(AttributeError):
            health_data.workouts = pd.DataFrame()  # type: ignore


class TestComplexRealWorldRecords:
    """Test parsing of complex real-world records."""

    def test_parse_complex_records(
        self,
        create_health_zip: Callable[..., str],
        load_export_fragment: Callable[[str], str],
        build_health_export_xml: Callable[[list[str]], str],
    ) -> None:
        """Test parsing complex real-world heart rate Record entries from an export fragment."""

        xml_content = build_health_export_xml([load_export_fragment("record_heart_rate.xml")])
        zip_path = create_health_zip(xml_content=xml_content)

        parser = ExportParser()
        with parser:
            health_data = parser.parse(str(zip_path)).records_by_type["HeartRate"]

        # Verify the heart rate records were parsed
        assert len(health_data) == 14

        sample_record = health_data.iloc[0]
        assert sample_record["value"] == pytest.approx(67, abs=1e-9)  # type: ignore[arg-type]
        assert sample_record["startDate"] == "2022-01-17 16:34:57 +0100"
        assert sample_record["HeartRateMotionContext"] == 1

    def test_parse_returns_parsed_health_data(
        self,
        create_health_zip: Callable[..., str],
        load_export_fragment: Callable[[str], str],
        build_health_export_xml: Callable[[list[str]], str],
    ) -> None:
        """Test that parse() returns ParsedHealthData instance."""
        xml_content = build_health_export_xml([load_export_fragment("record_heart_rate.xml")])
        zip_path = create_health_zip(xml_content=xml_content)

        parser = ExportParser()
        with parser:
            result = parser.parse(str(zip_path))

        assert isinstance(result, ParsedHealthData)
        assert isinstance(result.workouts, pd.DataFrame)
        assert isinstance(result.records_by_type, dict)

    def test_parse_records_by_type_structure(
        self,
        create_health_zip: Callable[..., str],
        load_export_fragment: Callable[[str], str],
        build_health_export_xml: Callable[[list[str]], str],
    ) -> None:
        """Test that records are properly grouped by type."""
        xml_content = build_health_export_xml([load_export_fragment("record_heart_rate.xml")])
        zip_path = create_health_zip(xml_content=xml_content)

        parser = ExportParser()
        with parser:
            result = parser.parse(str(zip_path))

        # Should have HeartRate records
        assert "HeartRate" in result.records_by_type
        assert isinstance(result.records_by_type["HeartRate"], pd.DataFrame)
        assert len(result.records_by_type["HeartRate"]) == 14

        # Test the statistics aggregation for heart rate records
        stats = result.records.heart_rate_stats(
            "M", context=RecordsByType.HeartRateMeasureContext.UNKNOWN
        )

        assert len(stats) == 1
        assert stats.iloc[0]["count"] == 2
        assert stats.iloc[0]["avg"] == pytest.approx(68.5, abs=1e-9)  # type: ignore[arg-type]

    def test_parse_running_power_records(
        self,
        create_health_zip: Callable[..., str],
        load_export_fragment: Callable[[str], str],
        build_health_export_xml: Callable[[list[str]], str],
    ) -> None:
        """RunningPower records should be parsed into records_by_type."""
        xml_content = build_health_export_xml([load_export_fragment("record_running_power.xml")])
        zip_path = create_health_zip(xml_content=xml_content)

        parser = ExportParser()
        with parser:
            result = parser.parse(str(zip_path))

        assert "RunningPower" in result.records_by_type
        rp_df = result.records_by_type["RunningPower"]
        assert isinstance(rp_df, pd.DataFrame)
        assert len(rp_df) > 0
        assert "startDate" in rp_df.columns
        assert "endDate" in rp_df.columns
        assert "value" in rp_df.columns
        assert rp_df["endDate"].notna().all()
        # Values should be numeric for at least some rows.
        values = pd.to_numeric(rp_df["value"], errors="coerce").dropna().tolist()
        assert len(values) > 0


class TestToNumber:
    """Test suite for ExportParser.to_number static method."""

    def test_to_number_with_none(self) -> None:
        """Test that None input returns None."""
        assert ExportParser.to_number(None) is None

    def test_to_number_with_integer_string(self) -> None:
        """Test that integer string returns int."""
        assert ExportParser.to_number("42") == 42
        assert isinstance(ExportParser.to_number("42"), int)

    def test_to_number_with_float_string(self) -> None:
        """Test that float string returns float."""
        assert ExportParser.to_number("3.14") == pytest.approx(3.14)  # type: ignore[arg-type]
        assert isinstance(ExportParser.to_number("3.14"), float)

    def test_to_number_with_float_that_is_integer(self) -> None:
        """Test that float string like '5.0' returns int."""
        assert ExportParser.to_number("5.0") == 5
        assert isinstance(ExportParser.to_number("5.0"), int)

    def test_to_number_with_negative_integer(self) -> None:
        """Test that negative integer string returns int."""
        assert ExportParser.to_number("-10") == -10
        assert isinstance(ExportParser.to_number("-10"), int)

    def test_to_number_with_negative_float(self) -> None:
        """Test that negative float string returns float."""
        assert ExportParser.to_number("-2.5") == pytest.approx(-2.5)  # type: ignore[arg-type]
        assert isinstance(ExportParser.to_number("-2.5"), float)

    def test_to_number_with_zero(self) -> None:
        """Test that '0' returns int 0."""
        assert ExportParser.to_number("0") == 0
        assert isinstance(ExportParser.to_number("0"), int)

    def test_to_number_with_zero_float(self) -> None:
        """Test that '0.0' returns int 0."""
        assert ExportParser.to_number("0.0") == pytest.approx(0, abs=1e-9)  # type: ignore[arg-type]
        assert isinstance(ExportParser.to_number("0.0"), int)

    def test_to_number_with_scientific_notation(self) -> None:
        """Test that scientific notation string is parsed correctly."""
        assert ExportParser.to_number("1e3") == 1000
        assert isinstance(ExportParser.to_number("1e3"), int)

    def test_to_number_with_invalid_string(self) -> None:
        """Test that non-numeric string returns None."""
        assert ExportParser.to_number("abc") is None
        assert ExportParser.to_number("123abc") is None
        assert ExportParser.to_number("") is None

    def test_to_number_with_whitespace(self) -> None:
        """Test that string with only whitespace returns None."""
        assert ExportParser.to_number("   ") is None

    def test_to_number_with_leading_trailing_whitespace(self) -> None:
        """Test that numeric string with whitespace is parsed correctly."""
        assert ExportParser.to_number("  42  ") == 42
        assert ExportParser.to_number("  3.14  ") == pytest.approx(3.14)  # type: ignore[arg-type]

    def test_to_number_with_very_large_number(self) -> None:
        """Test that very large numbers are handled correctly."""
        result = ExportParser.to_number("999999999999999")
        assert result == 999999999999999
        assert isinstance(result, int)

    def test_to_number_with_very_small_float(self) -> None:
        """Test that very small floats are handled correctly."""
        result = ExportParser.to_number("0.0000001")
        assert result == pytest.approx(0.0000001, abs=1e-9)  # type: ignore[arg-type]
        assert isinstance(result, float)


class TestParseMetadataValue:
    """Test suite for ExportParser.parse_metadata_value static method."""

    def test_parse_metadata_value_keeps_numeric_flags_as_ints(self) -> None:
        """Return integers for bare numeric metadata values (no bool coercion)."""
        value, unit = ExportParser.parse_metadata_value("1")

        assert value == 1
        assert isinstance(value, int)
        assert unit is None

    def test_parse_metadata_value_with_number_and_unit(self) -> None:
        """Parse a numeric metadata value that includes a unit."""
        value, unit = ExportParser.parse_metadata_value("100 m")

        assert value == pytest.approx(100.0, abs=1e-9)  # type: ignore[arg-type]
        assert isinstance(value, float)
        assert unit == "m"

    def test_parse_metadata_value_with_text(self) -> None:
        """Return raw text for non-numeric metadata values."""
        value, unit = ExportParser.parse_metadata_value("Europe/Luxembourg")

        assert value == "Europe/Luxembourg"
        assert unit is None

    def test_parse_metadata_value_with_leading_trailing_whitespace(self) -> None:
        """Strip leading/trailing whitespace from the raw value before parsing."""
        value, unit = ExportParser.parse_metadata_value("  42  ")

        assert value == 42
        assert isinstance(value, int)
        assert unit is None

    def test_parse_metadata_value_with_multiple_spaces(self) -> None:
        """Handle multiple spaces between number and unit correctly."""
        value, unit = ExportParser.parse_metadata_value("100  m")

        assert value == pytest.approx(100.0, abs=1e-9)  # type: ignore[arg-type]
        assert isinstance(value, float)
        assert unit == "m"

    def test_parse_metadata_value_with_trailing_space_and_no_unit(self) -> None:
        """Treat trailing whitespace after number (no unit) as unit=None."""
        value, unit = ExportParser.parse_metadata_value("55 ")

        assert value == 55
        assert isinstance(value, int)
        assert unit is None

    def test_parse_metadata_value_with_empty_input_returns_none_tuple(self) -> None:
        """Empty metadata values should return (None, None)."""
        assert ExportParser.parse_metadata_value("") == (None, None)


class TestExportParserInternalBranches:
    """Target branch coverage for parser internals via public parse()."""

    def test_parse_with_broken_progress_callback_logs_debug_and_continues(
        self,
        create_health_zip: Callable[..., str],
        caplog: pytest.LogCaptureFixture,
        build_health_export_xml: Callable[[list[str]], str],
    ) -> None:
        """Progress callback errors should be swallowed and parser should continue."""
        workout_xml = (
            "<Workout "
            "workoutActivityType='HKWorkoutActivityTypeRunning' "
            "startDate='2024-01-01 10:00:00 +0000' "
            "endDate='2024-01-01 10:30:00 +0000' "
            "duration='30' "
            "durationUnit='min' "
            "/>"
        )
        xml_content = build_health_export_xml([workout_xml])
        zip_path = create_health_zip(xml_content=xml_content)

        def broken_callback(_message: str) -> None:
            raise RuntimeError("boom")

        parser = ExportParser(progress_callback=broken_callback)
        with caplog.at_level("DEBUG"):
            with parser:
                result = parser.parse(str(zip_path))

        assert len(result.workouts) == 1
        assert any("Loading the workouts" in record.message for record in caplog.records)

    def test_parse_emits_processed_progress_message_at_interval(
        self,
        create_health_zip: Callable[..., str],
        monkeypatch: pytest.MonkeyPatch,
        build_health_export_xml: Callable[[list[str]], str],
    ) -> None:
        """When workout count reaches interval, parser should emit processed progress message."""
        monkeypatch.setattr("logic.export_parser.WORKOUT_PROGRESS_INTERVAL", 1)

        workout_xml = (
            "<Workout "
            "workoutActivityType='HKWorkoutActivityTypeRunning' "
            "startDate='2024-01-01 10:00:00 +0000' "
            "endDate='2024-01-01 10:30:00 +0000' "
            "duration='30' "
            "durationUnit='min' "
            "/>"
        )
        xml_content = build_health_export_xml([workout_xml])
        zip_path = create_health_zip(xml_content=xml_content)
        messages: list[str] = []

        parser = ExportParser(progress_callback=messages.append)
        with parser:
            parser.parse(str(zip_path))

        assert any(message.startswith("Processed 1 workouts") for message in messages)

    def test_parse_ignores_record_without_type(
        self,
        create_health_zip: Callable[..., str],
        build_health_export_xml: Callable[[list[str]], str],
    ) -> None:
        """Record entries missing a type should be ignored without failing parsing."""
        xml_content = build_health_export_xml(
            ["<Record startDate='2024-01-01 10:00:00 +0000' value='72' />"]
        )
        zip_path = create_health_zip(xml_content=xml_content)

        parser = ExportParser()
        with parser:
            result = parser.parse(str(zip_path))

        assert not result.records_by_type

    def test_parse_preserves_non_hk_metadata_keys(
        self,
        create_health_zip: Callable[..., str],
        build_health_export_xml: Callable[[list[str]], str],
    ) -> None:
        """Metadata keys without HK prefix should be preserved as-is."""
        record_xml = (
            "<Record "
            "type='HKQuantityTypeIdentifierHeartRate' "
            "startDate='2024-01-01 10:00:00 +0000' "
            "value='72'"
            ">"
            "<MetadataEntry key='CustomKey' value='100 m' />"
            "</Record>"
        )
        xml_content = build_health_export_xml([record_xml])
        zip_path = create_health_zip(xml_content=xml_content)

        parser = ExportParser()
        with parser:
            result = parser.parse(str(zip_path))

        heart_rate_df = result.records_by_type["HeartRate"]
        sample = heart_rate_df.iloc[0]
        assert sample["CustomKey"] == pytest.approx(100.0, abs=1e-9)  # type: ignore[arg-type]
        assert sample["CustomKeyUnit"] == "m"


# ---------------------------------------------------------------------------
# _parse_swim_event_metadata
# ---------------------------------------------------------------------------


class TestParseSwimEventMetadata:
    """Unit tests for ExportParser._parse_swim_event_metadata()."""

    @staticmethod
    def _make_event_element(metadata: dict[str, str]) -> Element:
        """Build a fake WorkoutEvent XML element with the given metadata entries."""
        from xml.etree.ElementTree import Element, SubElement

        elem = Element(
            "WorkoutEvent",
            attrib={
                "type": "HKWorkoutEventTypeLap",
                "date": "2025-01-01 10:00:00 +0000",
                "duration": "1.0",
                "durationUnit": "min",
            },
        )
        for key, value in metadata.items():
            SubElement(elem, "MetadataEntry", attrib={"key": key, "value": value})
        return elem

    def test_returns_empty_dict_when_no_metadata(self) -> None:
        """No MetadataEntry children → empty dict."""
        elem = self._make_event_element({})
        result = ExportParser._parse_swim_event_metadata(elem)  # type: ignore[misc]
        assert result == {}

    def test_extracts_swolf_as_float(self) -> None:
        """HKSWOLFScore → ``"swolf"`` key as float."""
        elem = self._make_event_element({"HKSWOLFScore": "96.78"})
        result = ExportParser._parse_swim_event_metadata(elem)  # type: ignore[misc]
        assert result["swolf"] == pytest.approx(96.78)  # type: ignore[arg-type]

    def test_extracts_stroke_style_as_int(self) -> None:
        """HKSwimmingStrokeStyle → ``"stroke_style"`` key as int."""
        elem = self._make_event_element({"HKSwimmingStrokeStyle": "4"})
        result = ExportParser._parse_swim_event_metadata(elem)  # type: ignore[misc]
        assert result["stroke_style"] == 4
        assert isinstance(result["stroke_style"], int)

    def test_extracts_both_swolf_and_stroke_style(self) -> None:
        """When both keys are present, both should be returned."""
        elem = self._make_event_element({"HKSWOLFScore": "113.5", "HKSwimmingStrokeStyle": "2"})
        result = ExportParser._parse_swim_event_metadata(elem)  # type: ignore[misc]
        assert result["swolf"] == pytest.approx(113.5)  # type: ignore[arg-type]
        assert result["stroke_style"] == 2

    def test_ignores_non_metadata_entry_tags(self) -> None:
        """Child elements with tags other than MetadataEntry should be silently skipped."""
        from xml.etree.ElementTree import Element, SubElement

        elem = Element("WorkoutEvent")
        SubElement(elem, "OtherTag", attrib={"key": "HKSWOLFScore", "value": "99.0"})
        result = ExportParser._parse_swim_event_metadata(elem)  # type: ignore[misc]
        assert result == {}

    def test_invalid_swolf_value_is_skipped(self) -> None:
        """A non-numeric HKSWOLFScore should not raise and should be excluded."""
        elem = self._make_event_element({"HKSWOLFScore": "not-a-number"})
        result = ExportParser._parse_swim_event_metadata(elem)  # type: ignore[misc]
        assert "swolf" not in result

    def test_stroke_style_zero_maps_to_int_zero(self) -> None:
        """HKSwimmingStrokeStyle value '0' should be stored as int 0 (Unknown)."""
        elem = self._make_event_element({"HKSwimmingStrokeStyle": "0"})
        result = ExportParser._parse_swim_event_metadata(elem)  # type: ignore[misc]
        assert result["stroke_style"] == 0
        assert isinstance(result["stroke_style"], int)

    def test_unknown_metadata_keys_are_ignored(self) -> None:
        """Metadata keys other than SWOLF and StrokeStyle should not appear in result."""
        elem = self._make_event_element({"HKOtherKey": "123", "HKSWOLFScore": "50.0"})
        result = ExportParser._parse_swim_event_metadata(elem)  # type: ignore[misc]
        assert "HKOtherKey" not in result
        assert "OtherKey" not in result
        assert result["swolf"] == pytest.approx(50.0)  # type: ignore[arg-type]
