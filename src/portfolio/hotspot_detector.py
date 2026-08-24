"""
Hotspot Detection (Geographic Risk Clustering)

Identifies geographic clusters of assessed properties whose combined
average risk exceeds a threshold - the "risk clustering" half of the
project's accumulation-tracking goal (PortfolioAggregator, Task 25, covers
the portfolio-wide numbers; this covers *where* risk is concentrated
geographically, which a portfolio-wide average alone can't reveal).

Algorithm: for every assessed property, treat it as a candidate cluster
center and gather every other assessed property within radius_km (real
great-circle distance, Task 9's calculate_distance). A candidate becomes a
hotspot if it has at least hotspot_min_properties members and their average
risk score exceeds hotspot_risk_threshold. Candidates are then de-duplicated
via non-max suppression: sorted by avg_risk (then size) descending, a
candidate is kept only if its center isn't already within radius_km of a
previously-kept hotspot - otherwise nearly every property in a dense
high-risk area would each spawn its own near-identical "hotspot."

Known MVP simplification: O(n^2) distance comparisons across the whole
assessed portfolio per call, same category of "correct and simple at
today's scale, revisit if the portfolio grows substantially" flagged
elsewhere (e.g. RiskScoringEngine's full-table hazard_data fetch, Task 19).
"""

import logging
from typing import Dict, List, Optional

from src.config import get_config
from src.database import PropertyDAO, RiskDAO
from src.utils import calculate_distance

logger = logging.getLogger(__name__)

DEFAULT_RADIUS_KM = 50
DEFAULT_MIN_PROPERTIES = 3
DEFAULT_RISK_THRESHOLD = 50


class HotspotDetector:
    """Detects geographic clusters of elevated portfolio risk."""

    def __init__(self):
        config = get_config()
        portfolio_cfg = config.get_section("portfolio")
        self.default_radius_km: float = portfolio_cfg.get("hotspot_radius_km", DEFAULT_RADIUS_KM)
        self.min_properties: int = portfolio_cfg.get("hotspot_min_properties", DEFAULT_MIN_PROPERTIES)
        self.risk_threshold: float = portfolio_cfg.get("hotspot_risk_threshold", DEFAULT_RISK_THRESHOLD)

        self.property_dao = PropertyDAO()
        self.risk_dao = RiskDAO()

    def detect_hotspots(self, radius_km: Optional[float] = None) -> List[Dict]:
        """
        Find geographic clusters of assessed properties with elevated
        combined average risk.

        Args:
            radius_km: Cluster radius in kilometers. Defaults to the
                       configured portfolio.hotspot_radius_km.

        Returns:
            List of hotspots, sorted by avg_risk descending:
            [{
                "center_lat": float, "center_lon": float,
                "property_count": int, "avg_risk": float,
                "properties": [{"property_id": int, "risk_score": float}, ...],
            }, ...]
        """
        radius_km = radius_km if radius_km is not None else self.default_radius_km

        assessed = self._get_assessed_properties()
        if len(assessed) < self.min_properties:
            return []

        candidates = self._build_candidates(assessed, radius_km)
        hotspots = self._suppress_overlapping(candidates, radius_km)

        logger.info(
            "Hotspot detection: %d assessed properties, %d hotspot(s) found (radius=%skm, threshold=%s)",
            len(assessed), len(hotspots), radius_km, self.risk_threshold,
        )
        return hotspots

    def _get_assessed_properties(self) -> List[Dict]:
        """Join properties with their latest assessment's overall_risk_score."""
        properties_by_id = {p["property_id"]: p for p in self.property_dao.get_all_properties()}
        assessments = self.risk_dao.get_all_latest_assessments()

        assessed = []
        for a in assessments:
            prop = properties_by_id.get(a["property_id"])
            if prop is None or a.get("overall_risk_score") is None:
                continue
            assessed.append({
                "property_id": a["property_id"],
                "lat": prop["latitude"],
                "lon": prop["longitude"],
                "risk_score": a["overall_risk_score"],
            })
        return assessed

    def _build_candidates(self, assessed: List[Dict], radius_km: float) -> List[Dict]:
        """For every assessed property as a candidate center, gather its cluster."""
        candidates = []
        for center in assessed:
            members = [
                p for p in assessed
                if calculate_distance(center["lat"], center["lon"], p["lat"], p["lon"]) <= radius_km
            ]
            if len(members) < self.min_properties:
                continue

            avg_risk = sum(p["risk_score"] for p in members) / len(members)
            if avg_risk <= self.risk_threshold:
                continue

            candidates.append({
                "center_lat": center["lat"],
                "center_lon": center["lon"],
                "property_count": len(members),
                "avg_risk": round(avg_risk, 2),
                "properties": [
                    {"property_id": p["property_id"], "risk_score": p["risk_score"]} for p in members
                ],
            })
        return candidates

    def _suppress_overlapping(self, candidates: List[Dict], radius_km: float) -> List[Dict]:
        """Non-max suppression: keep the strongest candidate in each area, drop near-duplicates."""
        candidates = sorted(candidates, key=lambda c: (-c["avg_risk"], -c["property_count"]))

        hotspots: List[Dict] = []
        for candidate in candidates:
            overlaps_existing = any(
                calculate_distance(
                    candidate["center_lat"], candidate["center_lon"],
                    h["center_lat"], h["center_lon"],
                ) <= radius_km
                for h in hotspots
            )
            if not overlaps_existing:
                hotspots.append(candidate)

        return hotspots


if __name__ == "__main__":
    print("=" * 60)
    print("Hotspot Detector Test")
    print("=" * 60)
    print()

    detector = HotspotDetector()
    print(f"radius_km={detector.default_radius_km}, min_properties={detector.min_properties}, "
          f"risk_threshold={detector.risk_threshold}")
    print()

    hotspots = detector.detect_hotspots()
    print(f"Found {len(hotspots)} hotspot(s)")
    for hs in hotspots:
        print(
            f"  ({hs['center_lat']:.2f}, {hs['center_lon']:.2f}): "
            f"{hs['property_count']} properties, avg risk {hs['avg_risk']:.1f}"
        )

    print()
    print("=" * 60)
