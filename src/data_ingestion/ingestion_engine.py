"""
Ingestion Engine

Orchestrates all three hazard data ingesters (wildfire, weather, flood)
across the entire property portfolio in a single cycle, using the
geographic-cell design described in docs/scaling-design.md:

- Properties are grouped into grid cells (src.utils.assign_grid_cell) so
  hazard data is fetched once per cell, not once per property. API call
  volume scales with geographic footprint, not portfolio size.
- Each provider's calls are paced by a dedicated RateLimiter, configured
  per-source in config/settings.json.
- A freshness check skips re-fetching a cell/source if a sufficiently
  recent hazard_data reading was already ingested this cycle window.
- Each source's failure is isolated - one provider being down does not
  prevent the others from completing.
"""

import logging
from typing import Dict, List, Tuple

from src.config import get_config, setup_logging
from src.database import get_db_connection, PropertyDAO
from src.utils import assign_grid_cell, get_utc_now, minutes_ago
from src.data_ingestion.wildfire_ingestion import WildFireIngester
from src.data_ingestion.weather_ingestion import WeatherIngester
from src.data_ingestion.flood_ingestion import FloodIngester
from src.data_ingestion.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class IngestionEngine:
    """Orchestrates hazard data ingestion across the property portfolio."""

    def __init__(self):
        config = get_config()

        self.cell_size_degrees: float = config.get("ingestion.grid_cell_size_degrees", 0.5)
        self.freshness_minutes: int = config.get("ingestion.freshness_minutes", 4)
        self.bbox_buffer_degrees: float = config.get(
            "data_sources.nasa_firms.bounding_box_buffer_degrees", 0.5
        )

        self._property_dao = PropertyDAO()
        self._wildfire = WildFireIngester()
        self._weather = WeatherIngester()
        self._flood = FloodIngester()

        self._rate_limiters = {
            "NASA_FIRMS": RateLimiter(config.get("data_sources.nasa_firms.calls_per_minute", 30)),
            "OPENWEATHER": RateLimiter(config.get("data_sources.openweather.calls_per_minute", 50)),
            "OPENWEATHER_RAIN": RateLimiter(config.get("data_sources.openweather.calls_per_minute", 50)),
            "USGS": RateLimiter(config.get("data_sources.usgs_water.calls_per_minute", 30)),
        }

    def _get_portfolio_cells(self) -> List[Tuple[float, float]]:
        """Group all properties into grid cells; return the unique cell centroids."""
        properties = self._property_dao.get_all_properties()
        cells = {
            assign_grid_cell(p["latitude"], p["longitude"], self.cell_size_degrees)
            for p in properties
        }
        return sorted(cells)

    def _is_cell_fresh(self, source: str, lat_min: float, lat_max: float,
                        lon_min: float, lon_max: float) -> bool:
        """
        Check whether a hazard_data reading for this source already exists
        within the bounding box, ingested within the freshness window.

        Known limitation: presence of any matching row is used as the
        freshness signal. This cannot distinguish "recently checked and
        genuinely found nothing" from "never checked" - an empty-result
        bbox will always be treated as not-fresh and re-queried every
        cycle. This is an acceptable simplification for the MVP: it errs
        toward re-checking rather than silently going stale.
        """
        cutoff = minutes_ago(self.freshness_minutes).isoformat()
        conn = get_db_connection()
        try:
            cursor = conn.execute(
                """
                SELECT 1 FROM hazard_data
                WHERE source = ?
                  AND latitude BETWEEN ? AND ?
                  AND longitude BETWEEN ? AND ?
                  AND ingested_timestamp > ?
                LIMIT 1
                """,
                (source, lat_min, lat_max, lon_min, lon_max, cutoff),
            )
            return cursor.fetchone() is not None
        finally:
            conn.close()

    def run_ingestion_cycle(self) -> Dict:
        """
        Run one full ingestion cycle across every grid cell covering the
        property portfolio.

        Returns:
            Summary dict: fires_ingested, weather_points, precipitation_points,
            gauge_readings, cells_processed, cells_skipped_fresh, errors
        """
        started_at = get_utc_now()
        cells = self._get_portfolio_cells()
        logger.info("Starting ingestion cycle: %d properties grouped into %d cells",
                    self._property_dao.count_properties(), len(cells))

        summary = {
            "fires_ingested": 0,
            "weather_points": 0,
            "precipitation_points": 0,
            "gauge_readings": 0,
            "cells_processed": 0,
            "cells_skipped_fresh": 0,
            "errors": [],
        }

        half = self.cell_size_degrees / 2 + self.bbox_buffer_degrees

        for cell_lat, cell_lon in cells:
            lat_min, lat_max = cell_lat - half, cell_lat + half
            lon_min, lon_max = cell_lon - half, cell_lon + half
            cell_had_work = False

            # --- Wildfire (bounding box) ---
            try:
                if self._is_cell_fresh("NASA_FIRMS", lat_min, lat_max, lon_min, lon_max):
                    summary["cells_skipped_fresh"] += 1
                else:
                    self._rate_limiters["NASA_FIRMS"].wait_if_needed()
                    fires = self._wildfire.fetch_active_fires(lat_min, lat_max, lon_min, lon_max)
                    stored = self._wildfire.store_fires(fires)
                    summary["fires_ingested"] += stored
                    cell_had_work = True
            except Exception as e:
                logger.error("Wildfire ingestion failed for cell (%s, %s): %s", cell_lat, cell_lon, e)
                summary["errors"].append(f"wildfire@({cell_lat},{cell_lon}): {e}")

            # --- River gauges (bounding box) ---
            try:
                if self._is_cell_fresh("USGS", lat_min, lat_max, lon_min, lon_max):
                    summary["cells_skipped_fresh"] += 1
                else:
                    self._rate_limiters["USGS"].wait_if_needed()
                    gauges = self._flood.fetch_river_gauges(lat_min, lat_max, lon_min, lon_max)
                    stored = self._flood.store_records(gauges)
                    summary["gauge_readings"] += stored
                    cell_had_work = True
            except Exception as e:
                logger.error("Gauge ingestion failed for cell (%s, %s): %s", cell_lat, cell_lon, e)
                summary["errors"].append(f"gauges@({cell_lat},{cell_lon}): {e}")

            # --- Weather (point, at cell centroid) ---
            try:
                if not self._is_cell_fresh("OPENWEATHER", cell_lat, cell_lat, cell_lon, cell_lon):
                    self._rate_limiters["OPENWEATHER"].wait_if_needed()
                    weather = self._weather.fetch_weather(cell_lat, cell_lon)
                    if weather and self._weather.store_weather(weather):
                        summary["weather_points"] += 1
                    cell_had_work = True
                else:
                    summary["cells_skipped_fresh"] += 1
            except Exception as e:
                logger.error("Weather ingestion failed for cell (%s, %s): %s", cell_lat, cell_lon, e)
                summary["errors"].append(f"weather@({cell_lat},{cell_lon}): {e}")

            # --- Precipitation (point, at cell centroid; reuses weather's API key) ---
            try:
                if not self._is_cell_fresh("OPENWEATHER_RAIN", cell_lat, cell_lat, cell_lon, cell_lon):
                    self._rate_limiters["OPENWEATHER_RAIN"].wait_if_needed()
                    precip = self._flood.fetch_precipitation(cell_lat, cell_lon)
                    if precip:
                        stored = self._flood.store_records([precip])
                        summary["precipitation_points"] += stored
                    cell_had_work = True
                else:
                    summary["cells_skipped_fresh"] += 1
            except Exception as e:
                logger.error("Precipitation ingestion failed for cell (%s, %s): %s", cell_lat, cell_lon, e)
                summary["errors"].append(f"precipitation@({cell_lat},{cell_lon}): {e}")

            if cell_had_work:
                summary["cells_processed"] += 1

        duration = (get_utc_now() - started_at).total_seconds()
        logger.info(
            "Ingestion cycle complete in %.1fs: %d fires, %d weather points, "
            "%d precipitation points, %d gauge readings, %d cells processed, "
            "%d cells skipped (fresh), %d errors",
            duration, summary["fires_ingested"], summary["weather_points"],
            summary["precipitation_points"], summary["gauge_readings"],
            summary["cells_processed"], summary["cells_skipped_fresh"], len(summary["errors"]),
        )
        return summary


if __name__ == "__main__":
    setup_logging()

    print("=" * 60)
    print("Ingestion Engine - Task 14")
    print("=" * 60)
    print()

    engine = IngestionEngine()
    summary = engine.run_ingestion_cycle()

    print()
    print("Cycle summary:")
    for key, value in summary.items():
        if key != "errors":
            print(f"  {key}: {value}")
    if summary["errors"]:
        print("  errors:")
        for err in summary["errors"]:
            print(f"    - {err}")

    print()
    print("=" * 60)
