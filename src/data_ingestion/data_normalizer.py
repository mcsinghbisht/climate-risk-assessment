"""
Data Normalizer

Consolidates the per-record normalization logic that was previously
duplicated (with small variations) across WildFireIngester, WeatherIngester,
and FloodIngester (Tasks 10-12): coordinate validation, confidence handling,
timestamp parsing, and building the final hazard_data-ready record.

Each normalize_*() method takes one raw record from its respective source
API and returns either a normalized dict ready for hazard_data, or None if
the record is invalid/unusable - it never raises for malformed input.

Note on field names: the hazard_data table (Task 3) uses columns named
`observation_timestamp` and `raw_data`, so normalized records use those
names directly rather than generic `timestamp`/`metadata` labels - this
keeps every normalized record insertable into hazard_data with no
translation step.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Dict, Optional

from src.utils import is_valid_coordinate, get_utc_now, is_within_hours, parse_iso_timestamp

logger = logging.getLogger(__name__)

# NASA FIRMS VIIRS confidence is a letter code, not a number - mapped to an
# approximate 0-1 confidence score for consistency with the rest of the
# hazard_data schema.
FIRMS_CONFIDENCE_MAP = {"l": 0.3, "n": 0.6, "h": 0.9}
DEFAULT_CONFIDENCE = 0.5

# Weather and precipitation observations are treated as fully reliable
# (unlike FIRMS' letter-coded confidence).
OBSERVATION_CONFIDENCE = 1.0

# USGS parameter codes relevant to flood risk
USGS_PARAMETER_LABELS = {
    "00060": "discharge_cfs",
    "00065": "gage_height_ft",
}

# USGS "instantaneous values" sites can report broken/offline sensor data
# that is years old despite being listed as "active" (observed live during
# Task 12 testing). Readings older than this are rejected as stale.
DEFAULT_MAX_GAUGE_READING_AGE_HOURS = 48


class DataNormalizer:
    """Normalizes raw records from each hazard data source into a common format."""

    def __init__(self, max_gauge_reading_age_hours: int = DEFAULT_MAX_GAUGE_READING_AGE_HOURS):
        self.max_gauge_reading_age_hours = max_gauge_reading_age_hours

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_record(
        hazard_type: str, source: str, latitude: float, longitude: float,
        value: float, confidence: float, observation_timestamp: str, raw: dict,
    ) -> Optional[Dict]:
        """Validate coordinates and assemble the final hazard_data-ready record."""
        if not is_valid_coordinate(latitude, longitude):
            logger.warning(
                "Rejecting %s record from %s: invalid coordinates (%s, %s)",
                hazard_type, source, latitude, longitude,
            )
            return None

        return {
            "hazard_type": hazard_type,
            "source": source,
            "latitude": latitude,
            "longitude": longitude,
            "value": value,
            "confidence": confidence,
            "observation_timestamp": observation_timestamp,
            "raw_data": json.dumps(raw),
        }

    def _is_stale(self, observation_timestamp: str) -> bool:
        try:
            return not is_within_hours(
                parse_iso_timestamp(observation_timestamp), self.max_gauge_reading_age_hours
            )
        except ValueError:
            return True  # unparseable timestamp is treated as untrustworthy/stale

    @staticmethod
    def _parse_acq_datetime(acq_date: Optional[str], acq_time: Optional[str]) -> str:
        """Combine FIRMS' acq_date (YYYY-MM-DD) and acq_time (HHMM) into ISO 8601."""
        if not acq_date:
            return get_utc_now().isoformat()
        try:
            time_str = (acq_time or "0000").zfill(4)
            dt = datetime.strptime(f"{acq_date} {time_str}", "%Y-%m-%d %H%M")
            return dt.replace(tzinfo=timezone.utc).isoformat()
        except ValueError:
            return get_utc_now().isoformat()

    @staticmethod
    def _parse_unix_timestamp(dt_unix: Optional[int]) -> str:
        """Convert an OpenWeatherMap unix 'dt' field into a UTC ISO string."""
        if dt_unix is None:
            return get_utc_now().isoformat()
        try:
            return datetime.fromtimestamp(dt_unix, tz=timezone.utc).isoformat()
        except (TypeError, ValueError, OSError):
            return get_utc_now().isoformat()

    @staticmethod
    def _parse_usgs_datetime(dt_str: Optional[str]) -> str:
        """Parse a USGS ISO 8601 datetime (with offset) into a UTC ISO string."""
        if not dt_str:
            return get_utc_now().isoformat()
        try:
            dt = datetime.fromisoformat(dt_str)
            return dt.astimezone(timezone.utc).isoformat()
        except ValueError:
            return get_utc_now().isoformat()

    # ------------------------------------------------------------------
    # Per-source normalization
    # ------------------------------------------------------------------

    def normalize_fire(self, row: Dict) -> Optional[Dict]:
        """
        Normalize one NASA FIRMS CSV row (as a dict) into a hazard_data record.

        Args:
            row: A single row from csv.DictReader over a FIRMS area-API response

        Returns:
            Normalized dict, or None if the row is malformed or has invalid coordinates
        """
        try:
            lat = float(row["latitude"])
            lon = float(row["longitude"])
        except (KeyError, ValueError):
            return None

        try:
            frp = float(row.get("frp", 0.0))
        except ValueError:
            frp = 0.0

        confidence_code = (row.get("confidence") or "").strip().lower()
        confidence = FIRMS_CONFIDENCE_MAP.get(confidence_code, DEFAULT_CONFIDENCE)
        observation_timestamp = self._parse_acq_datetime(row.get("acq_date"), row.get("acq_time"))

        return self._build_record(
            "wildfire", "NASA_FIRMS", lat, lon, frp, confidence, observation_timestamp, row
        )

    def normalize_weather(self, data: Dict, latitude: float, longitude: float) -> Optional[Dict]:
        """
        Normalize an OpenWeatherMap current-weather JSON response into a
        hazard_data record.

        Args:
            data: Raw OpenWeatherMap /weather JSON response
            latitude, longitude: The queried coordinates (the response's own
                                  coord field is not used, to guarantee the
                                  record matches what was requested)

        Returns:
            Normalized dict (with convenience fields temperature/humidity/
            wind_speed/wind_direction added), or None if the response shape
            is unexpected
        """
        try:
            main = data["main"]
            wind = data.get("wind", {})
            temperature = float(main["temp"])
            humidity = float(main["humidity"])
            wind_speed = float(wind.get("speed", 0.0))
            wind_direction = float(wind.get("deg", 0.0))
        except (KeyError, TypeError, ValueError) as e:
            logger.error("Unexpected OpenWeatherMap response structure: %s", e)
            return None

        observation_timestamp = self._parse_unix_timestamp(data.get("dt"))

        record = self._build_record(
            "weather", "OPENWEATHER", latitude, longitude, temperature,
            OBSERVATION_CONFIDENCE, observation_timestamp,
            {
                "temperature": temperature,
                "humidity": humidity,
                "wind_speed": wind_speed,
                "wind_direction": wind_direction,
                "raw_response": data,
            },
        )
        if record is None:
            return None

        record.update({
            "temperature": temperature,
            "humidity": humidity,
            "wind_speed": wind_speed,
            "wind_direction": wind_direction,
        })
        return record

    def normalize_precipitation(
        self, weather_raw_response: Dict, latitude: float, longitude: float,
        observation_timestamp: str,
    ) -> Dict:
        """
        Normalize an OpenWeatherMap raw response's 'rain' field into a
        flood-type hazard_data record.

        Args:
            weather_raw_response: The raw OpenWeatherMap JSON (same shape
                                   passed to normalize_weather)
            latitude, longitude: The queried coordinates
            observation_timestamp: Already-parsed ISO timestamp (reused from
                                    the weather fetch, since it's the same
                                    observation)

        Returns:
            Normalized dict. Rainfall defaults to 0.0 (not an error) when the
            'rain' field is absent, since OpenWeatherMap omits it during dry
            conditions rather than reporting an explicit zero.
        """
        rainfall_mm = weather_raw_response.get("rain", {}).get("1h", 0.0)

        return self._build_record(
            "flood", "OPENWEATHER_RAIN", latitude, longitude, float(rainfall_mm),
            OBSERVATION_CONFIDENCE, observation_timestamp,
            {"rainfall_mm_1h": rainfall_mm, "raw_response": weather_raw_response},
        )

    def normalize_gauge(self, series: Dict) -> Optional[Dict]:
        """
        Normalize one USGS WaterML timeSeries entry into a hazard_data record.

        Args:
            series: One entry from value.timeSeries[] in a USGS IV API response

        Returns:
            Normalized dict, or None if the entry is malformed, has invalid
            coordinates, or its most recent reading is stale (see
            DEFAULT_MAX_GAUGE_READING_AGE_HOURS)
        """
        try:
            source_info = series["sourceInfo"]
            site_name = source_info.get("siteName", "Unknown site")
            geo = source_info["geoLocation"]["geogLocation"]
            lat = float(geo["latitude"])
            lon = float(geo["longitude"])

            param_code = series["variable"]["variableCode"][0]["value"]

            values = series["values"][0]["value"]
            if not values:
                return None
            latest = values[-1]
            value = float(latest["value"])
            observation_timestamp = self._parse_usgs_datetime(latest.get("dateTime"))
        except (KeyError, IndexError, TypeError, ValueError) as e:
            logger.warning("Skipping malformed USGS time series entry: %s", e)
            return None

        if not is_valid_coordinate(lat, lon):
            logger.warning("Skipping gauge with invalid coordinates: %s, %s", lat, lon)
            return None

        if self._is_stale(observation_timestamp):
            logger.warning(
                "Skipping stale gauge reading at %s (%s): observation_timestamp=%s "
                "is older than %d hours",
                site_name, param_code, observation_timestamp, self.max_gauge_reading_age_hours,
            )
            return None

        return self._build_record(
            "flood", "USGS", lat, lon, value, 1.0, observation_timestamp,
            {
                "site_name": site_name,
                "parameter_code": param_code,
                "parameter_label": USGS_PARAMETER_LABELS.get(param_code, param_code),
                "raw_value_entry": latest,
            },
        )


if __name__ == "__main__":
    print("=" * 60)
    print("Data Normalizer Test")
    print("=" * 60)

    normalizer = DataNormalizer()

    print("\n1. normalize_fire()")
    fire_row = {
        "latitude": "33.5", "longitude": "-116.2", "frp": "250.5",
        "confidence": "n", "acq_date": "2026-07-20", "acq_time": "0833",
    }
    print(normalizer.normalize_fire(fire_row))

    print("\n2. normalize_weather()")
    weather_data = {
        "main": {"temp": 28.5, "humidity": 22},
        "wind": {"speed": 5.7, "deg": 270},
        "dt": 1753180800,
    }
    print(normalizer.normalize_weather(weather_data, 33.75, -116.72))

    print("\n3. normalize_precipitation()")
    print(normalizer.normalize_precipitation(
        {"rain": {"1h": 4.2}}, 29.95, -90.07, get_utc_now().isoformat()
    ))

    print("\n4. normalize_gauge() - current reading")
    gauge_series = {
        "sourceInfo": {
            "siteName": "TEST GAUGE",
            "geoLocation": {"geogLocation": {"latitude": "29.95", "longitude": "-90.07"}},
        },
        "variable": {"variableCode": [{"value": "00065"}]},
        "values": [{"value": [{"value": "3.21", "dateTime": get_utc_now().isoformat()}]}],
    }
    print(normalizer.normalize_gauge(gauge_series))

    print("\n" + "=" * 60)
    print("All normalizers exercised successfully!")
    print("=" * 60)
