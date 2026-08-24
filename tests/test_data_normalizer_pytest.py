"""
Pytest test suite for DataNormalizer (Task 13)

Run with: pytest tests/test_data_normalizer_pytest.py -v

These tests exercise DataNormalizer directly, independent of any ingester -
the ingester-level tests (test_wildfire_ingestion_pytest.py etc.) already
cover the integration path (ingester -> normalizer -> hazard_data record),
so these focus on the normalizer's own contract in isolation.
"""

from datetime import datetime, timedelta, timezone

import pytest

from src.data_ingestion.data_normalizer import (
    DataNormalizer,
    FIRMS_CONFIDENCE_MAP,
    DEFAULT_CONFIDENCE,
    OBSERVATION_CONFIDENCE,
    USGS_PARAMETER_LABELS,
)

COMMON_FIELDS = ["hazard_type", "source", "latitude", "longitude", "value",
                 "confidence", "observation_timestamp", "raw_data"]


@pytest.fixture
def normalizer():
    return DataNormalizer()


class TestNormalizeFire:
    def test_valid_row_produces_all_common_fields(self, normalizer):
        row = {"latitude": "33.5", "longitude": "-116.2", "frp": "250.5",
               "confidence": "n", "acq_date": "2026-07-20", "acq_time": "0833"}
        record = normalizer.normalize_fire(row)
        for field in COMMON_FIELDS:
            assert field in record

    def test_hazard_type_and_source(self, normalizer):
        row = {"latitude": "33.5", "longitude": "-116.2", "frp": "1.0",
               "confidence": "h", "acq_date": "2026-07-20", "acq_time": "0000"}
        record = normalizer.normalize_fire(row)
        assert record["hazard_type"] == "wildfire"
        assert record["source"] == "NASA_FIRMS"

    def test_missing_coordinates_returns_none(self, normalizer):
        assert normalizer.normalize_fire({"frp": "1.0"}) is None

    def test_invalid_coordinates_returns_none(self, normalizer):
        row = {"latitude": "999", "longitude": "-116.2", "frp": "1.0"}
        assert normalizer.normalize_fire(row) is None

    def test_confidence_codes_use_shared_map(self, normalizer):
        for code, expected in FIRMS_CONFIDENCE_MAP.items():
            row = {"latitude": "33.5", "longitude": "-116.2", "frp": "1.0",
                   "confidence": code, "acq_date": "2026-07-20", "acq_time": "0000"}
            assert normalizer.normalize_fire(row)["confidence"] == expected

    def test_unmapped_confidence_uses_default(self, normalizer):
        row = {"latitude": "33.5", "longitude": "-116.2", "frp": "1.0", "confidence": "?"}
        assert normalizer.normalize_fire(row)["confidence"] == DEFAULT_CONFIDENCE


class TestNormalizeWeather:
    SAMPLE = {
        "main": {"temp": 28.5, "humidity": 22},
        "wind": {"speed": 5.7, "deg": 270},
        "dt": 1753180800,
    }

    def test_valid_response_produces_all_common_fields(self, normalizer):
        record = normalizer.normalize_weather(self.SAMPLE, 33.75, -116.72)
        for field in COMMON_FIELDS:
            assert field in record

    def test_convenience_fields_present(self, normalizer):
        record = normalizer.normalize_weather(self.SAMPLE, 33.75, -116.72)
        assert record["temperature"] == 28.5
        assert record["humidity"] == 22
        assert record["wind_speed"] == 5.7
        assert record["wind_direction"] == 270

    def test_value_mirrors_temperature(self, normalizer):
        record = normalizer.normalize_weather(self.SAMPLE, 33.75, -116.72)
        assert record["value"] == record["temperature"]

    def test_confidence_is_full(self, normalizer):
        record = normalizer.normalize_weather(self.SAMPLE, 33.75, -116.72)
        assert record["confidence"] == OBSERVATION_CONFIDENCE

    def test_malformed_response_returns_none(self, normalizer):
        assert normalizer.normalize_weather({"unexpected": "shape"}, 33.75, -116.72) is None

    def test_uses_passed_coordinates_not_response_coord(self, normalizer):
        record = normalizer.normalize_weather(self.SAMPLE, 10.0, 20.0)
        assert record["latitude"] == 10.0
        assert record["longitude"] == 20.0


class TestNormalizePrecipitation:
    def test_extracts_rain_1h(self, normalizer):
        ts = datetime.now(timezone.utc).isoformat()
        record = normalizer.normalize_precipitation({"rain": {"1h": 4.2}}, 29.95, -90.07, ts)
        assert record["value"] == 4.2

    def test_defaults_to_zero_when_absent(self, normalizer):
        ts = datetime.now(timezone.utc).isoformat()
        record = normalizer.normalize_precipitation({}, 29.95, -90.07, ts)
        assert record["value"] == 0.0

    def test_hazard_type_and_source(self, normalizer):
        ts = datetime.now(timezone.utc).isoformat()
        record = normalizer.normalize_precipitation({}, 29.95, -90.07, ts)
        assert record["hazard_type"] == "flood"
        assert record["source"] == "OPENWEATHER_RAIN"


class TestNormalizeGauge:
    @staticmethod
    def _series(dt: datetime, param_code="00065", value="3.21", lat="29.95", lon="-90.07"):
        return {
            "sourceInfo": {
                "siteName": "TEST GAUGE",
                "geoLocation": {"geogLocation": {"latitude": lat, "longitude": lon}},
            },
            "variable": {"variableCode": [{"value": param_code}]},
            "values": [{"value": [{"value": value, "dateTime": dt.isoformat()}]}],
        }

    def test_current_reading_produces_all_common_fields(self, normalizer):
        record = normalizer.normalize_gauge(self._series(datetime.now(timezone.utc)))
        for field in COMMON_FIELDS:
            assert field in record

    def test_stale_reading_returns_none(self, normalizer):
        old = datetime.now(timezone.utc) - timedelta(days=1000)
        assert normalizer.normalize_gauge(self._series(old)) is None

    def test_hazard_type_and_source(self, normalizer):
        record = normalizer.normalize_gauge(self._series(datetime.now(timezone.utc)))
        assert record["hazard_type"] == "flood"
        assert record["source"] == "USGS"

    def test_parameter_label_included_in_raw_data(self, normalizer):
        record = normalizer.normalize_gauge(
            self._series(datetime.now(timezone.utc), param_code="00060")
        )
        assert USGS_PARAMETER_LABELS["00060"] in record["raw_data"]

    def test_invalid_coordinates_returns_none(self, normalizer):
        record = normalizer.normalize_gauge(
            self._series(datetime.now(timezone.utc), lat="999")
        )
        assert record is None

    def test_malformed_series_returns_none(self, normalizer):
        assert normalizer.normalize_gauge({"unexpected": "shape"}) is None

    def test_custom_staleness_threshold_is_respected(self):
        strict_normalizer = DataNormalizer(max_gauge_reading_age_hours=1)
        two_hours_old = datetime.now(timezone.utc) - timedelta(hours=2)
        assert strict_normalizer.normalize_gauge(self._series(two_hours_old)) is None


class TestConsistencyAcrossSources:
    """All four normalizers must agree on the same output contract."""

    def test_all_sources_produce_identical_field_set(self, normalizer):
        fire = normalizer.normalize_fire({
            "latitude": "33.5", "longitude": "-116.2", "frp": "1.0",
            "confidence": "n", "acq_date": "2026-07-20", "acq_time": "0000",
        })
        weather = normalizer.normalize_weather(
            {"main": {"temp": 20, "humidity": 50}, "wind": {}, "dt": 1753180800},
            33.5, -116.2,
        )
        precip = normalizer.normalize_precipitation(
            {}, 33.5, -116.2, datetime.now(timezone.utc).isoformat()
        )
        gauge = normalizer.normalize_gauge(TestNormalizeGauge._series(datetime.now(timezone.utc)))

        for record in (fire, weather, precip, gauge):
            assert set(COMMON_FIELDS).issubset(record.keys())


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
