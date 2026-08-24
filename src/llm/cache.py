"""
LLM Explanation Cache (Step 10)

Caches LLM-generated explanations and recommendations to avoid re-generating
them on every cycle when property risk hasn't changed.

Cache keys: (property_id, risk_type, overall_risk_score) → explanation
Invalidation: triggered when risk score changes or properties updated
"""

import json
import logging
from typing import Optional, Dict
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


class ExplanationCache:
    """
    Simple file-based cache for LLM explanations.

    Key insight: if a property's risk score hasn't changed since last cycle,
    the explanation shouldn't change either. Skip the LLM call and use cached text.
    """

    def __init__(self, cache_dir: str = "data/.cache"):
        """
        Initialize the cache.

        Args:
            cache_dir: directory to store cache files
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / "explanations.json"

        # Load existing cache
        self.cache = self._load_cache()

    def _load_cache(self) -> Dict:
        """Load cache from disk."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Could not load cache: {e}")
                return {}
        return {}

    def _save_cache(self) -> None:
        """Save cache to disk."""
        try:
            with open(self.cache_file, "w") as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save cache: {e}")

    def get_key(self, property_id: int, risk_type: str, score: float) -> str:
        """
        Generate cache key.

        Args:
            property_id: the property
            risk_type: "wildfire", "flood", or "overall"
            score: the risk score (rounded to nearest int to handle floats)

        Returns:
            cache key string
        """
        score_int = int(round(score))
        return f"{property_id}:{risk_type}:{score_int}"

    def get(self, property_id: int, risk_type: str, score: float) -> Optional[str]:
        """
        Get cached explanation if it exists.

        Args:
            property_id: the property
            risk_type: "wildfire", "flood", or "overall"
            score: the risk score

        Returns:
            cached explanation string, or None if not cached
        """
        key = self.get_key(property_id, risk_type, score)
        cached = self.cache.get(key)

        if cached:
            # Check if it's stale (older than 30 days)
            cached_time = datetime.fromisoformat(cached.get("timestamp", ""))
            if datetime.now() - cached_time < timedelta(days=30):
                logger.debug(f"Cache hit: {key}")
                return cached.get("text")
            else:
                # Stale, remove it
                del self.cache[key]
                self._save_cache()
                logger.debug(f"Cache expired: {key}")

        return None

    def set(self, property_id: int, risk_type: str, score: float, explanation: str) -> None:
        """
        Cache an explanation.

        Args:
            property_id: the property
            risk_type: "wildfire", "flood", or "overall"
            score: the risk score
            explanation: the LLM-generated explanation text
        """
        key = self.get_key(property_id, risk_type, score)
        self.cache[key] = {
            "text": explanation,
            "timestamp": datetime.now().isoformat(),
            "property_id": property_id,
            "risk_type": risk_type,
            "score": score,
        }
        self._save_cache()
        logger.debug(f"Cached: {key}")

    def invalidate_property(self, property_id: int) -> None:
        """
        Invalidate all cached explanations for a property (e.g., when it's updated).

        Args:
            property_id: the property to invalidate
        """
        keys_to_delete = [k for k in self.cache.keys() if k.startswith(f"{property_id}:")]
        for key in keys_to_delete:
            del self.cache[key]
        if keys_to_delete:
            self._save_cache()
            logger.debug(f"Invalidated {len(keys_to_delete)} cache entries for property {property_id}")

    def clear_all(self) -> None:
        """Clear the entire cache."""
        self.cache = {}
        self._save_cache()
        logger.info("Cache cleared")

    def get_stats(self) -> Dict:
        """
        Get cache statistics.

        Returns:
            dict with entry_count, oldest_entry_age_days, etc.
        """
        if not self.cache:
            return {"entry_count": 0}

        timestamps = [datetime.fromisoformat(v.get("timestamp", "")) for v in self.cache.values()]
        oldest = min(timestamps) if timestamps else datetime.now()
        newest = max(timestamps) if timestamps else datetime.now()

        return {
            "entry_count": len(self.cache),
            "oldest_entry_age_days": (datetime.now() - oldest).days,
            "newest_entry_age_minutes": round((datetime.now() - newest).total_seconds() / 60),
        }
