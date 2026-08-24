"""
Weather Data Ingestion (OpenWeatherMap)

Fetches current weather conditions (wind speed/direction, temperature,
humidity) per property location from the OpenWeatherMap Current Weather
API, normalizes them into the project's common hazard format, and stores
them in the `hazard_data` table.

API reference: https://openweathermap.org/current
"""

import logging
import os
from typing import Dict, Optional

import requests
from dotenv import load_dotenv

from src.config import get_config, setup_logging
from src.database import get_db_connection
from src.utils import is_valid_coordinate, get_utc_now
from src.data_ingestion.data_normalizer import DataNormalizer

load_dotenv()

logger = logging.getLogger(__name__)


class WeatherIngester:
    """Fetches and stores current weather data from OpenWeatherMap."""

    def __init__(self):
        cfg = get_config().get_section("data_sources").get("openweather", {})
        self.enabled: bool = cfg.get("enabled", False)
        self.base_url: str = cfg.get(
            "base_url", "https://api.openweathermap.org/data/2.5"
        )
        self.units: str = cfg.get("units", "metric")

        api_key_env = cfg.get("api_key_env", "OPENWEATHER_API_KEY")
        self.api_key: Optional[str] = os.getenv(api_key_env)

        self._normalizer = DataNormalizer()

        if self.enabled and not self.api_key:
            logger.warning(
                "OpenWeatherMap is enabled but no API key found in environment "
                "variable '%s'. Set it in .env. Fetches will return no data "
                "until a key is configured.",
                api_key_env,
            )

    def fetch_weather(self, latitude: float, longitude: float) -> Optional[Dict]:
        """
        Fetch current weather conditions for a single coordinate.

        Args:
            latitude: Latitude in degrees
            longitude: Longitude in degrees

        Returns:
            Normalized weather dict, or None if disabled, missing API key,
            invalid coordinates, or the request fails. Never raises for
            expected operational failures.
        """
        if not self.enabled:
            logger.info("OpenWeatherMap ingestion is disabled in config; skipping fetch")
            return None

        if not self.api_key:
            logger.error("No OpenWeatherMap API key configured; cannot fetch weather")
            return None

        if not is_valid_coordinate(latitude, longitude):
            logger.warning("Skipping weather fetch for invalid coordinates: %s, %s",
                            latitude, longitude)
            return None

        url = (
            f"{self.base_url}/weather"
            f"?lat={latitude}&lon={longitude}&appid={self.api_key}&units={self.units}"
        )

        logger.debug(
            "Fetching OpenWeatherMap data for (%s, %s)", latitude, longitude
        )

        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            # Redact the API key from the exception text before logging -
            # requests includes the full request URL (with key) in its
            # error messages, which must never reach logs/output.
            safe_error = str(e).replace(self.api_key, "***")
            logger.error("OpenWeatherMap request failed: %s", safe_error)
            return None

        try:
            data = response.json()
        except ValueError:
            logger.error("OpenWeatherMap returned non-JSON response: %s", response.text[:200])
            return None

        return self._parse_weather_response(data, latitude, longitude)

    def _parse_weather_response(self, data: Dict, latitude: float, longitude: float) -> Optional[Dict]:
        """Normalize an OpenWeatherMap JSON response into the hazard format."""
        return self._normalizer.normalize_weather(data, latitude, longitude)

    def store_weather(self, weather: Dict) -> bool:
        """
        Store a normalized weather record in the hazard_data table.

        Args:
            weather: Normalized weather dict from fetch_weather()

        Returns:
            True if stored successfully, False otherwise
        """
        if not weather:
            return False

        conn = get_db_connection()
        try:
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
                {
                    "hazard_type": weather["hazard_type"],
                    "source": weather["source"],
                    "latitude": weather["latitude"],
                    "longitude": weather["longitude"],
                    "value": weather["value"],
                    "confidence": weather["confidence"],
                    "observation_timestamp": weather["observation_timestamp"],
                    "ingested_timestamp": get_utc_now().isoformat(),
                    "raw_data": weather["raw_data"],
                },
            )
            conn.commit()
        finally:
            conn.close()

        logger.info(
            "Stored weather record for (%s, %s): temp=%.1f, wind=%.1f",
            weather["latitude"], weather["longitude"],
            weather["temperature"], weather["wind_speed"],
        )
        return True


if __name__ == "__main__":
    setup_logging()

    print("=" * 60)
    print("Weather Ingestion (OpenWeatherMap) - Task 11")
    print("=" * 60)
    print()

    ingester = WeatherIngester()

    if not ingester.api_key:
        print("[ERROR] No OPENWEATHER_API_KEY found in .env - cannot fetch live data.")
        print("Register at https://openweathermap.org/appid")
    else:
        # Idyllwild, CA - same location used in our geo_utils demo (Task 4)
        lat, lon = 33.7521, -116.7277
        print(f"Fetching current weather for ({lat}, {lon})...")
        weather = ingester.fetch_weather(lat, lon)

        if weather:
            print()
            print(f"Temperature:    {weather['temperature']}°C")
            print(f"Humidity:       {weather['humidity']}%")
            print(f"Wind speed:     {weather['wind_speed']} m/s")
            print(f"Wind direction: {weather['wind_direction']}°")

            stored = ingester.store_weather(weather)
            print()
            print(f"[OK] Stored in hazard_data table: {stored}")
        else:
            print("[ERROR] Failed to fetch weather data (see logs above)")

    print()
    print("=" * 60)
