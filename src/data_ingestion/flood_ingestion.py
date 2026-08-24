"""
Flood Data Ingestion (USGS River Gauges + OpenWeatherMap Precipitation)

Two independent flood-relevant signals, both public and requiring no new
API key beyond what Tasks 10/11 already set up:

1. River gauge data (discharge, gage height) from the USGS Water Services
   Instantaneous Values API - fully open, no key required.
   Reference: https://waterservices.usgs.gov/docs/instantaneous-values/

2. Precipitation from OpenWeatherMap's current weather response (`rain.1h`
   field) - reuses the same OPENWEATHER_API_KEY and WeatherIngester built
   in Task 11, rather than registering a separate precipitation API key.

Both are normalized into the common hazard_data format with
hazard_type='flood', distinguished by source ('USGS' vs 'OPENWEATHER_RAIN').
"""

import json
import logging
from typing import Dict, List, Optional

import requests

from src.config import get_config, setup_logging
from src.database import get_db_connection
from src.utils import get_utc_now
from src.data_ingestion.weather_ingestion import WeatherIngester
from src.data_ingestion.data_normalizer import (
    DataNormalizer,
    USGS_PARAMETER_LABELS as PARAMETER_LABELS,
    DEFAULT_MAX_GAUGE_READING_AGE_HOURS as MAX_GAUGE_READING_AGE_HOURS,
)

logger = logging.getLogger(__name__)

MAX_BBOX_DEGREES_PRODUCT = 25  # USGS constraint: lat_range * lon_range <= 25


class FloodIngester:
    """Fetches and stores flood-relevant hazard data (river gauges + precipitation)."""

    def __init__(self):
        cfg = get_config().get_section("data_sources").get("usgs_water", {})
        self.enabled: bool = cfg.get("enabled", False)
        self.base_url: str = cfg.get(
            "base_url", "https://waterservices.usgs.gov/nwis/iv"
        )
        self.parameter_codes: str = cfg.get("parameter_codes", "00060,00065")

        # Precipitation reuses Task 11's WeatherIngester (same API key, no
        # separate registration needed).
        self._weather_ingester = WeatherIngester()
        self._normalizer = DataNormalizer(max_gauge_reading_age_hours=MAX_GAUGE_READING_AGE_HOURS)

    def fetch_river_gauges(
        self, lat_min: float, lat_max: float, lon_min: float, lon_max: float
    ) -> List[Dict]:
        """
        Fetch current river gauge readings (discharge, gage height) within
        a bounding box from USGS Water Services.

        Args:
            lat_min, lat_max, lon_min, lon_max: Bounding box in degrees

        Returns:
            List of normalized flood hazard dicts. Empty list if disabled,
            the bounding box is too large, or the request fails.
        """
        if not self.enabled:
            logger.info("USGS water ingestion is disabled in config; skipping fetch")
            return []

        lat_range = lat_max - lat_min
        lon_range = lon_max - lon_min
        if lat_range * lon_range > MAX_BBOX_DEGREES_PRODUCT:
            logger.warning(
                "Bounding box too large for USGS (lat_range * lon_range = %.1f > %d); "
                "request would be rejected. Narrow the bounding box.",
                lat_range * lon_range, MAX_BBOX_DEGREES_PRODUCT,
            )
            return []

        # USGS bBox order is west,south,east,north (same convention as FIRMS)
        bbox = f"{lon_min},{lat_min},{lon_max},{lat_max}"
        url = (
            f"{self.base_url}/?format=json&bBox={bbox}"
            f"&parameterCd={self.parameter_codes}&siteStatus=active"
        )

        logger.debug("Fetching USGS gauge data: %s", url)

        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.error("USGS request failed: %s", e)
            return []

        try:
            data = response.json()
        except ValueError:
            logger.error("USGS returned non-JSON response: %s", response.text[:200])
            return []

        return self._parse_gauge_response(data)

    def _parse_gauge_response(self, data: Dict) -> List[Dict]:
        """Parse a USGS WaterML-as-JSON response into normalized flood hazard dicts."""
        try:
            time_series = data["value"]["timeSeries"]
        except (KeyError, TypeError):
            logger.warning("USGS response missing expected value.timeSeries structure")
            return []

        records = []
        for series in time_series:
            record = self._normalizer.normalize_gauge(series)
            if record is not None:
                records.append(record)

        logger.info("Parsed %d valid gauge readings from USGS response", len(records))
        return records

    def fetch_precipitation(self, latitude: float, longitude: float) -> Optional[Dict]:
        """
        Fetch current precipitation (rainfall in the last hour) for a single
        coordinate, via OpenWeatherMap's current-weather 'rain.1h' field.

        Note: unlike fetch_river_gauges(), this is point-based rather than a
        bounding-box query - OpenWeatherMap's free tier only supports
        single-coordinate current-weather lookups, not an area query.

        Args:
            latitude: Latitude in degrees
            longitude: Longitude in degrees

        Returns:
            Normalized flood hazard dict (rainfall in mm/h), or None if the
            underlying weather fetch fails.
        """
        weather = self._weather_ingester.fetch_weather(latitude, longitude)
        if not weather:
            return None

        raw_response = json.loads(weather["raw_data"]).get("raw_response", {})
        return self._normalizer.normalize_precipitation(
            raw_response, latitude, longitude, weather["observation_timestamp"]
        )

    def store_records(self, records: List[Dict]) -> int:
        """
        Store a list of normalized flood hazard records in hazard_data.

        Args:
            records: List of normalized flood dicts (from either
                     fetch_river_gauges() or wrapping fetch_precipitation()
                     results in a list)

        Returns:
            Number of records successfully stored
        """
        if not records:
            return 0

        conn = get_db_connection()
        stored = 0
        try:
            for record in records:
                conn.execute(
                    """
                    INSERT INTO hazard_data (
                        hazard_type, source, latitude, longitude, value,
                        confidence, observation_timestamp, ingested_timestamp, raw_data
                    ) VALUES (
                        :hazard_type, :source, :latitude, :longitude, :value,
                        :confidence, :observation_timestamp, :ingested_timestamp, :raw_data
                    )
                    """,
                    {**record, "ingested_timestamp": get_utc_now().isoformat()},
                )
                stored += 1
            conn.commit()
        finally:
            conn.close()

        logger.info("Stored %d flood hazard records in hazard_data", stored)
        return stored


if __name__ == "__main__":
    setup_logging()

    print("=" * 60)
    print("Flood Ingestion (USGS + OpenWeatherMap) - Task 12")
    print("=" * 60)
    print()

    ingester = FloodIngester()

    # Louisiana bounding box - covers our LA property cluster from Task 7
    print("Fetching USGS river gauge data for Louisiana bounding box...")
    gauges = ingester.fetch_river_gauges(
        lat_min=29.0, lat_max=30.8, lon_min=-91.2, lon_max=-89.4
    )
    print(f"Found {len(gauges)} gauge readings")

    if gauges:
        print()
        print("Sample gauge reading:")
        print(json.dumps(gauges[0], indent=2))
        stored = ingester.store_records(gauges)
        print(f"[OK] Stored {stored} gauge records in hazard_data table")
    else:
        print("No gauge data returned (see logs above).")

    print()
    if not ingester._weather_ingester.api_key:
        print("[SKIP] Precipitation fetch skipped - no OPENWEATHER_API_KEY configured.")
    else:
        # New Orleans, LA - within our Louisiana cluster
        lat, lon = 29.9511, -90.0715
        print(f"Fetching precipitation for ({lat}, {lon})...")
        precip = ingester.fetch_precipitation(lat, lon)

        if precip:
            print(f"Rainfall (last hour): {precip['value']} mm/h")
            stored = ingester.store_records([precip])
            print(f"[OK] Stored {stored} precipitation record in hazard_data table")
        else:
            print("[ERROR] Failed to fetch precipitation data (see logs above)")

    print()
    print("=" * 60)
