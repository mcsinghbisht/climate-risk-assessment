"""
Wildfire Data Ingestion (NASA FIRMS)

Fetches near-real-time active fire detections from the NASA FIRMS Area API
(VIIRS sensor), normalizes them into the project's common hazard format,
and stores them in the `hazard_data` table.

API reference: https://firms.modaps.eosdis.nasa.gov/api/area/
Bounding box order for this API is west,south,east,north (i.e. lon_min,
lat_min, lon_max, lat_max) - NOT lat_min/lat_max/lon_min/lon_max.
"""

import csv
import io
import json
import logging
import os
from typing import Dict, List, Optional

import requests
from dotenv import load_dotenv

from src.config import get_config, setup_logging
from src.database import get_db_connection
from src.utils import get_utc_now
from src.data_ingestion.data_normalizer import DataNormalizer, FIRMS_CONFIDENCE_MAP as CONFIDENCE_MAP

load_dotenv()

logger = logging.getLogger(__name__)

MAX_DAY_RANGE = 5
MIN_DAY_RANGE = 1


class WildFireIngester:
    """Fetches and stores active fire data from NASA FIRMS."""

    def __init__(self):
        cfg = get_config().get_section("data_sources").get("nasa_firms", {})
        self.enabled: bool = cfg.get("enabled", False)
        self.base_url: str = cfg.get(
            "base_url", "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
        )
        self.sensor: str = cfg.get("sensor", "VIIRS_SNPP_NRT")
        self.default_days: int = cfg.get("days_lookback", 3)
        self.buffer_degrees: float = cfg.get("bounding_box_buffer_degrees", 0.5)

        api_key_env = cfg.get("api_key_env", "NASA_FIRMS_API_KEY")
        self.api_key: Optional[str] = os.getenv(api_key_env)

        self._normalizer = DataNormalizer()

        if self.enabled and not self.api_key:
            logger.warning(
                "NASA FIRMS is enabled but no API key found in environment "
                "variable '%s'. Set it in .env. Fetches will return no data "
                "until a key is configured.",
                api_key_env,
            )

    def fetch_active_fires(
        self,
        lat_min: float,
        lat_max: float,
        lon_min: float,
        lon_max: float,
        days: Optional[int] = None,
    ) -> List[Dict]:
        """
        Fetch and normalize active fire detections within a bounding box.

        Args:
            lat_min, lat_max, lon_min, lon_max: Bounding box in degrees
                (caller passes lat/lon min/max - this method handles
                converting to FIRMS' required west,south,east,north order)
            days: Days to look back (1-5). Defaults to configured value,
                  clamped to FIRMS' allowed range.

        Returns:
            List of normalized fire dicts. Empty list if disabled, missing
            API key, or the request fails - never raises for expected
            operational failures (network errors, bad key, no fires found).
        """
        if not self.enabled:
            logger.info("NASA FIRMS ingestion is disabled in config; skipping fetch")
            return []

        if not self.api_key:
            logger.error("No NASA FIRMS API key configured; cannot fetch fires")
            return []

        days = days if days is not None else self.default_days
        if days < MIN_DAY_RANGE or days > MAX_DAY_RANGE:
            logger.warning(
                "Requested day range %d out of FIRMS allowed range (%d-%d); clamping",
                days, MIN_DAY_RANGE, MAX_DAY_RANGE,
            )
            days = max(MIN_DAY_RANGE, min(days, MAX_DAY_RANGE))

        # FIRMS bounding box order is west,south,east,north
        bbox = f"{lon_min},{lat_min},{lon_max},{lat_max}"
        url = f"{self.base_url}/{self.api_key}/{self.sensor}/{bbox}/{days}"

        logger.debug("Fetching NASA FIRMS data: %s", url.replace(self.api_key, "***"))

        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            # Redact the API key from the exception text before logging -
            # requests includes the full request URL (with key) in its
            # error messages, which must never reach logs/output.
            safe_error = str(e).replace(self.api_key, "***")
            logger.error("NASA FIRMS request failed: %s", safe_error)
            return []

        return self._parse_csv_response(response.text)

    def _parse_csv_response(self, csv_text: str) -> List[Dict]:
        """Parse and normalize a FIRMS CSV response into hazard dicts."""
        reader = csv.DictReader(io.StringIO(csv_text))

        if not reader.fieldnames or "latitude" not in reader.fieldnames:
            # FIRMS returns a plain-text error (e.g. "Invalid MAP_KEY") on
            # failure instead of CSV - detect and log rather than crash.
            logger.error(
                "Unexpected NASA FIRMS response (not valid CSV): %s",
                csv_text[:200],
            )
            return []

        fires = []
        for row in reader:
            fire = self._normalizer.normalize_fire(row)
            if fire is not None:
                fires.append(fire)

        logger.info("Parsed %d valid fire detections from NASA FIRMS response", len(fires))
        return fires

    def store_fires(self, fires: List[Dict]) -> int:
        """
        Store normalized fire records in the hazard_data table.

        Args:
            fires: List of normalized fire dicts from fetch_active_fires()

        Returns:
            Number of records successfully stored
        """
        if not fires:
            return 0

        conn = get_db_connection()
        stored = 0
        try:
            for fire in fires:
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
                    {**fire, "ingested_timestamp": get_utc_now().isoformat()},
                )
                stored += 1
            conn.commit()
        finally:
            conn.close()

        logger.info("Stored %d fire records in hazard_data", stored)
        return stored


if __name__ == "__main__":
    setup_logging()

    print("=" * 60)
    print("Wildfire Ingestion (NASA FIRMS) - Task 10")
    print("=" * 60)
    print()

    ingester = WildFireIngester()

    if not ingester.api_key:
        print("[ERROR] No NASA_FIRMS_API_KEY found in .env - cannot fetch live data.")
        print("Register at https://firms.modaps.eosdis.nasa.gov/api/map_key/")
    else:
        # California bounding box - covers our CA property cluster from Task 7
        print("Fetching active fires for California bounding box...")
        fires = ingester.fetch_active_fires(
            lat_min=32, lat_max=42, lon_min=-124, lon_max=-114, days=3
        )
        print(f"Found {len(fires)} active fire detections")

        if fires:
            print()
            print("Sample detection:")
            print(json.dumps(fires[0], indent=2))

            stored = ingester.store_fires(fires)
            print()
            print(f"[OK] Stored {stored} records in hazard_data table")
        else:
            print("No active fires detected in this bounding box (expected outside fire season).")

    print()
    print("=" * 60)
