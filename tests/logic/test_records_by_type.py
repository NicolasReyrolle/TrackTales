"""Test suite for RecordsByType wrapper around HealthKit record DataFrames."""

from collections.abc import Callable
from datetime import datetime

import pandas as pd
import pytest

from logic.export_parser import ExportParser
from logic.records_by_type import RecordsByType


class TestRecordsByTypeGetters:
    """Test basic accessors and convenience getters."""

    def test_get_returns_dataframe_for_existing_type(self) -> None:
        """Return the stored DataFrame when the record type exists."""
        heart_rate_df = pd.DataFrame({"value": [60, 65]})
        records = RecordsByType({"HeartRate": heart_rate_df})

        result = records.get("HeartRate")

        assert result is heart_rate_df
        assert len(result) == 2

    def test_get_returns_empty_dataframe_for_missing_type(self) -> None:
        """Return an empty DataFrame when the record type does not exist."""
        records = RecordsByType({})

        result = records.get("MissingType")

        assert isinstance(result, pd.DataFrame)
        assert result.empty

    def test_heart_rate_weight_and_vo2_helpers_return_expected_types(self) -> None:
        """Expose heart-rate, body-mass and VO2 max data via helper methods."""
        heart_rate_df = pd.DataFrame({"value": [58, 62]})
        body_mass_df = pd.DataFrame({"value": [70.5, 70.2]})
        vo2_max_df = pd.DataFrame({"value": [49.8, 50.1]})
        records = RecordsByType(
            {"HeartRate": heart_rate_df, "BodyMass": body_mass_df, "VO2Max": vo2_max_df}
        )

        heart_rate_result = records.heart_rate()
        body_mass_result = records.weight()
        vo2_max_result = records.vo2_max()

        assert heart_rate_result is heart_rate_df
        assert body_mass_result is body_mass_df
        assert vo2_max_result is vo2_max_df


class TestRecordsByTypeStatsByPeriod:
    """Test period-based aggregation logic."""

    def test_stats_by_period_returns_empty_when_required_columns_missing(self) -> None:
        """Return an empty shaped DataFrame when date/value columns are missing."""
        records = RecordsByType({"HeartRate": pd.DataFrame({"not_value": [1]})})

        result = records.stats_by_period("HeartRate")

        assert list(result.columns) == ["period", "avg", "min", "max", "count"]
        assert result.empty

    def test_stats_by_period_drops_invalid_dates_and_values(self) -> None:
        """Ignore rows with invalid dates or non-numeric values before aggregation."""
        heart_rate_df = pd.DataFrame(
            {
                "startDate": ["2024-01-01", "not-a-date", "2024-01-15"],
                "value": [60, 75, "invalid"],
            }
        )
        records = RecordsByType({"HeartRate": heart_rate_df})

        result = records.stats_by_period("HeartRate", period="M")

        assert len(result) == 1
        assert result.iloc[0]["period"].strftime("%Y-%m") == "2024-01"
        assert result.iloc[0]["avg"] == 60
        assert result.iloc[0]["min"] == 60
        assert result.iloc[0]["max"] == 60
        assert result.iloc[0]["count"] == 1

    def test_stats_by_period_groups_by_month(self) -> None:
        """Aggregate avg/min/max/count correctly for monthly periods."""
        heart_rate_df = pd.DataFrame(
            {
                "startDate": ["2024-01-01", "2024-01-20", "2024-02-10"],
                "value": [60, 80, 70],
            }
        )
        records = RecordsByType({"HeartRate": heart_rate_df})

        result = records.stats_by_period("HeartRate", period="M")

        assert list(result["period"].astype(str)) == ["2024-01", "2024-02"]
        assert list(result["avg"]) == [70.0, 70.0]
        assert list(result["min"]) == [60, 70]
        assert list(result["max"]) == [80, 70]
        assert list(result["count"]) == [2, 1]

    def test_stats_by_period_groups_by_quarter(self) -> None:
        """Aggregate values into quarter buckets when period='Q'."""
        heart_rate_df = pd.DataFrame(
            {
                "startDate": ["2024-01-01", "2024-03-15", "2024-04-10"],
                "value": [60, 90, 75],
            }
        )
        records = RecordsByType({"HeartRate": heart_rate_df})

        result = records.stats_by_period("HeartRate", period="Q")

        assert list(result["period"].astype(str)) == ["2024Q1", "2024Q2"]
        assert list(result["avg"]) == [75.0, 75.0]
        assert list(result["min"]) == [60, 75]
        assert list(result["max"]) == [90, 75]
        assert list(result["count"]) == [2, 1]

    def test_stats_by_period_rounds_to_two_decimals_by_default(self) -> None:
        """Round avg/min/max to 2 decimals when round_decimals is not specified."""
        heart_rate_df = pd.DataFrame(
            {
                "startDate": ["2024-01-01", "2024-01-20"],
                "value": [1.111, 1.239],
            }
        )
        records = RecordsByType({"HeartRate": heart_rate_df})

        result = records.stats_by_period("HeartRate", period="M")

        assert list(result["avg"]) == [1.18]
        assert list(result["min"]) == [1.11]
        assert list(result["max"]) == [1.24]

    def test_stats_by_period_respects_custom_round_decimals(self) -> None:
        """Use caller-provided rounding precision for avg/min/max."""
        heart_rate_df = pd.DataFrame(
            {
                "startDate": ["2024-01-01", "2024-01-20"],
                "value": [1.111, 1.239],
            }
        )
        records = RecordsByType({"HeartRate": heart_rate_df})

        result = records.stats_by_period("HeartRate", period="M", round_decimals=3)

        assert list(result["avg"]) == [1.175]
        assert list(result["min"]) == [1.111]
        assert list(result["max"]) == [1.239]

    def test_stats_by_period_returns_empty_when_query_filter_removes_all_rows(self) -> None:
        """Applying a filter that removes all rows should return an empty shaped frame."""
        heart_rate_df = pd.DataFrame(
            {
                "startDate": ["2024-01-01", "2024-01-02"],
                "value": [60, 70],
                "HeartRateMotionContext": [1, 1],
            }
        )
        records = RecordsByType({"HeartRate": heart_rate_df})

        result = records.stats_by_period(
            "HeartRate", period="M", query_filter="HeartRateMotionContext == 99"
        )

        assert list(result.columns) == ["period", "avg", "min", "max", "count"]
        assert result.empty

    def test_stats_by_period_returns_empty_when_dropna_removes_all_rows(self) -> None:
        """Rows that become NaT/NaN should be dropped; empty result should be returned."""
        heart_rate_df = pd.DataFrame(
            {
                "startDate": ["invalid-date", "also-invalid"],
                "value": ["not-a-number", "still-not-a-number"],
            }
        )
        records = RecordsByType({"HeartRate": heart_rate_df})

        result = records.stats_by_period("HeartRate", period="M")

        assert list(result.columns) == ["period", "avg", "min", "max", "count"]
        assert result.empty


class TestRecordsByTypeConvenienceStats:
    """Test convenience wrappers around stats_by_period."""

    def test_heart_rate_stats_uses_heart_rate_type(self) -> None:
        """Use the HeartRate type constant in heart_rate_stats."""
        heart_rate_df = pd.DataFrame(
            {
                "startDate": ["2024-01-01", "2024-01-02"],
                "value": [60, 70],
            }
        )
        records = RecordsByType({"HeartRate": heart_rate_df})

        result = records.heart_rate_stats("M")

        assert len(result) == 1
        assert result.iloc[0]["avg"] == pytest.approx(65.0, abs=1e-9)  # type: ignore[arg-type]

    def test_heart_rate_stats_filters_unknown_context(self) -> None:
        """Filter heart rate stats by UNKNOWN context."""
        heart_rate_df = pd.DataFrame(
            {
                "startDate": ["2024-01-01", "2024-01-02", "2024-01-03"],
                "value": [68, 69, 75],
                "HeartRateMotionContext": [0, 0, 2],
            }
        )
        records = RecordsByType({"HeartRate": heart_rate_df})

        result = records.heart_rate_stats(
            "M", context=RecordsByType.HeartRateMeasureContext.UNKNOWN
        )

        assert len(result) == 1
        assert result.iloc[0]["count"] == 2
        assert result.iloc[0]["avg"] == pytest.approx(68.5, abs=1e-9)  # type: ignore[arg-type]

    def test_weight_stats_uses_body_mass_type(self) -> None:
        """Use the BodyMass type constant in weight_stats."""
        body_mass_df = pd.DataFrame(
            {
                "startDate": ["2024-01-01", "2024-01-10", "2024-02-10"],
                "value": [70.5, 69.5, 70.0],
            }
        )
        records = RecordsByType({"BodyMass": body_mass_df})

        result = records.weight_stats("M")

        assert list(result["period"].astype(str)) == ["2024-01", "2024-02"]
        assert list(result["avg"]) == [70.0, 70.0]

    def test_vo2_max_stats_uses_vo2_max_type(self) -> None:
        """Use the VO2Max type constant in vo2_max_stats."""
        vo2_max_df = pd.DataFrame(
            {
                "startDate": ["2024-01-01", "2024-01-10", "2024-02-10"],
                "value": [49.5, 50.5, 51.0],
            }
        )
        records = RecordsByType({"VO2Max": vo2_max_df})

        result = records.vo2_max_stats("M")

        assert list(result["period"].astype(str)) == ["2024-01", "2024-02"]
        assert list(result["avg"]) == [50.0, 51.0]

    def test_vo2_max_stats_respects_custom_round_decimals(self) -> None:
        """Apply custom rounding precision through vo2_max_stats."""
        vo2_max_df = pd.DataFrame(
            {
                "startDate": ["2024-01-01", "2024-01-10"],
                "value": [49.54, 50.05],
            }
        )
        records = RecordsByType({"VO2Max": vo2_max_df})

        result = records.vo2_max_stats("M", round_decimals=1)

        assert list(result["avg"]) == [49.8]
        assert list(result["min"]) == [49.5]
        assert list(result["max"]) == [50.0]

    def test_vo2_max_stats_fill_missing_periods_parameter(self) -> None:
        """Fill or keep gaps depending on fill_missing_periods parameter."""
        vo2_max_df = pd.DataFrame(
            {
                "startDate": ["2024-01-05", "2024-03-10"],
                "value": [49.5, 51.0],
            }
        )
        records = RecordsByType({"VO2Max": vo2_max_df})

        result_with_fill = records.vo2_max_stats("M", fill_missing_periods=True)
        result_without_fill = records.vo2_max_stats("M", fill_missing_periods=False)

        assert list(result_with_fill["period"].astype(str)) == ["2024-01", "2024-02", "2024-03"]
        feb = result_with_fill[result_with_fill["period"].astype(str) == "2024-02"].iloc[0]
        assert pd.isna(feb["avg"])
        assert pd.isna(feb["min"])
        assert pd.isna(feb["max"])
        assert feb["count"] == 0

        assert list(result_without_fill["period"].astype(str)) == ["2024-01", "2024-03"]

    def test_heart_rate_stats_from_export_sample_zip(
        self,
        create_health_zip: Callable[..., str],
        load_export_fragment: Callable[[str], str],
        build_health_export_xml: Callable[[list[str]], str],
    ) -> None:
        """Aggregate heart rate stats from the export_sample.zip fixture."""
        xml_content = build_health_export_xml([load_export_fragment("record_heart_rate.xml")])
        zip_path = create_health_zip(xml_content=xml_content)

        with ExportParser() as parser:
            parsed = parser.parse(str(zip_path))

        records = RecordsByType(data=parsed.records_by_type)
        heart_rate_df = records.heart_rate()
        result = records.heart_rate_stats("M")

        assert not heart_rate_df.empty
        assert list(result.columns) == ["period", "avg", "min", "max", "count"]
        assert not result.empty
        assert int(result["count"].sum()) == len(heart_rate_df)
        assert (result["min"] <= result["avg"]).all()
        assert (result["avg"] <= result["max"]).all()

    def test_vo2_max_stats_from_export_sample_zip(
        self,
        create_health_zip: Callable[..., str],
        load_export_fragment: Callable[[str], str],
        build_health_export_xml: Callable[[list[str]], str],
    ) -> None:
        """Aggregate VO2 max stats from the export_sample.zip fixture."""
        xml_content = build_health_export_xml([load_export_fragment("record_vo2_max.xml")])
        zip_path = create_health_zip(xml_content=xml_content)

        with ExportParser() as parser:
            parsed = parser.parse(str(zip_path))

        records = RecordsByType(data=parsed.records_by_type)
        vo2_max_df = records.get(RecordsByType.VO2_MAX_TYPE)
        result = records.vo2_max_stats("M")

        assert not vo2_max_df.empty
        assert list(result.columns) == ["period", "avg", "min", "max", "count"]
        assert not result.empty
        assert int(result["count"].sum()) == len(vo2_max_df)
        assert (result["min"] <= result["avg"]).all()
        assert (result["avg"] <= result["max"]).all()


class TestRecordsByTypeDateRangeFiltering:
    """Test date-range filtering in stats_by_period and convenience wrappers."""

    def test_stats_by_period_filters_by_start_date(self) -> None:
        """Records before start_date should be excluded from aggregation."""
        heart_rate_df = pd.DataFrame(
            {
                "startDate": ["2024-01-01", "2024-02-01", "2024-03-01"],
                "value": [60, 70, 80],
            }
        )
        records = RecordsByType({"HeartRate": heart_rate_df})

        result = records.stats_by_period("HeartRate", period="M", start_date=datetime(2024, 2, 1))

        periods = list(result["period"].astype(str))
        assert "2024-01" not in periods
        assert "2024-02" in periods
        assert "2024-03" in periods

    def test_stats_by_period_filters_by_end_date(self) -> None:
        """Records after end_date should be excluded from aggregation."""
        heart_rate_df = pd.DataFrame(
            {
                "startDate": ["2024-01-01", "2024-02-01", "2024-03-01"],
                "value": [60, 70, 80],
            }
        )
        records = RecordsByType({"HeartRate": heart_rate_df})

        result = records.stats_by_period("HeartRate", period="M", end_date=datetime(2024, 2, 28))

        periods = list(result["period"].astype(str))
        assert "2024-01" in periods
        assert "2024-02" in periods
        assert "2024-03" not in periods

    def test_stats_by_period_filters_by_both_dates(self) -> None:
        """Only records within [start_date, end_date] should be included."""
        heart_rate_df = pd.DataFrame(
            {
                "startDate": ["2024-01-01", "2024-02-01", "2024-03-01", "2024-04-01"],
                "value": [60, 70, 80, 90],
            }
        )
        records = RecordsByType({"HeartRate": heart_rate_df})

        result = records.stats_by_period(
            "HeartRate", period="M", start_date=datetime(2024, 2, 1), end_date=datetime(2024, 3, 31)
        )

        periods = list(result["period"].astype(str))
        assert "2024-01" not in periods
        assert "2024-02" in periods
        assert "2024-03" in periods
        assert "2024-04" not in periods

    def test_stats_by_period_end_date_is_inclusive(self) -> None:
        """Records on the end_date itself should be included."""
        heart_rate_df = pd.DataFrame(
            {
                "startDate": ["2024-02-29", "2024-03-01"],
                "value": [70, 80],
            }
        )
        records = RecordsByType({"HeartRate": heart_rate_df})

        result = records.stats_by_period("HeartRate", period="M", end_date=datetime(2024, 2, 29))

        periods = list(result["period"].astype(str))
        assert "2024-02" in periods
        assert "2024-03" not in periods

    def test_heart_rate_stats_respects_date_range(self) -> None:
        """heart_rate_stats should pass date filters to stats_by_period."""
        heart_rate_df = pd.DataFrame(
            {
                "startDate": ["2024-01-01", "2024-02-01", "2024-03-01"],
                "value": [60, 70, 80],
            }
        )
        records = RecordsByType({"HeartRate": heart_rate_df})

        result = records.heart_rate_stats(
            "M", start_date=datetime(2024, 2, 1), end_date=datetime(2024, 2, 28)
        )

        periods = list(result["period"].astype(str))
        assert periods == ["2024-02"]
        assert result.iloc[0]["avg"] == pytest.approx(70.0, abs=1e-9)  # type: ignore[arg-type]

    def test_weight_stats_respects_date_range(self) -> None:
        """weight_stats should pass date filters to stats_by_period."""
        body_mass_df = pd.DataFrame(
            {
                "startDate": ["2024-01-01", "2024-02-01", "2024-03-01"],
                "value": [70.0, 71.0, 72.0],
            }
        )
        records = RecordsByType({"BodyMass": body_mass_df})

        result = records.weight_stats("M", start_date=datetime(2024, 2, 1))

        periods = list(result["period"].astype(str))
        assert "2024-01" not in periods
        assert "2024-02" in periods
        assert "2024-03" in periods

    def test_vo2_max_stats_respects_date_range(self) -> None:
        """vo2_max_stats should pass date filters to stats_by_period."""
        vo2_max_df = pd.DataFrame(
            {
                "startDate": ["2024-01-01", "2024-02-01", "2024-03-01"],
                "value": [48.0, 49.0, 50.0],
            }
        )
        records = RecordsByType({"VO2Max": vo2_max_df})

        result = records.vo2_max_stats("M", end_date=datetime(2024, 2, 28))

        periods = list(result["period"].astype(str))
        assert "2024-01" in periods
        assert "2024-02" in periods
        assert "2024-03" not in periods
