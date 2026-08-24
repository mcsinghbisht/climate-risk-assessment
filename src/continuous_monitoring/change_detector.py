"""
Change Detection (Score Comparison)

Compares two risk assessments for a property and reports what actually
changed - the overall score delta, whether the risk level bucket changed,
and which individual factors shifted (e.g. wind picked up, a new fire
appeared closer, humidity dropped) - independent of whether the change
crosses an alert threshold. A smaller, more general-purpose sibling to
AlertEngine (Task 20): AlertEngine answers "should we notify someone?";
ChangeDetector answers "what actually changed?", useful even for moves too
small to alert on.

Input shape: current_assessment/previous_assessment are risk_assessments
dicts as produced by RiskDAO.get_latest_assessment() /
get_assessment_history() (Task 18) - overall_risk_score, risk_level,
wildfire_factors, flood_factors already parsed as dicts, not raw JSON
strings.
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# The explanation string is a natural-language rendering of the other
# factors, not itself a factor - comparing it would flag noisy wording
# differences (e.g. "5.86 km" vs "5.9 km") as a "change" even when nothing
# meaningful moved.
IGNORED_FACTOR_KEYS = {"explanation"}

# Two floats within this tolerance are treated as unchanged, avoiding
# false positives from floating-point rounding noise.
FLOAT_TOLERANCE = 0.01


def _values_differ(old, new) -> bool:
    """Compare two factor values, with float tolerance and None-safety."""
    if old is None and new is None:
        return False
    if isinstance(old, (int, float)) and isinstance(new, (int, float)):
        return abs(old - new) > FLOAT_TOLERANCE
    return old != new


class ChangeDetector:
    """Compares two risk assessments and reports what changed."""

    def detect_changes(
        self, property_id: int, current_assessment: Dict, previous_assessment: Optional[Dict] = None
    ) -> Dict:
        """
        Compare a property's current assessment against its previous one.

        Args:
            property_id: The property's ID
            current_assessment: Current risk_assessments-shaped dict
            previous_assessment: Previous risk_assessments-shaped dict, or
                                 None if this is the property's first-ever
                                 assessment (no crash - reported as a baseline)

        Returns:
            {
                "property_id": int,
                "changed": bool,
                "is_baseline": bool,
                "risk_delta": Optional[float],
                "risk_level_changed": bool,
                "trend": "worsening"/"improving"/"stable"/"baseline",
                "factors_changed": [{"factor": str, "from": Any, "to": Any}, ...],
            }
        """
        if previous_assessment is None:
            return {
                "property_id": property_id,
                "changed": False,
                "is_baseline": True,
                "risk_delta": None,
                "risk_level_changed": False,
                "trend": "baseline",
                "factors_changed": [],
            }

        current_score = current_assessment.get("overall_risk_score") or 0.0
        previous_score = previous_assessment.get("overall_risk_score") or 0.0
        risk_delta = round(current_score - previous_score, 2)

        current_level = current_assessment.get("risk_level")
        previous_level = previous_assessment.get("risk_level")
        risk_level_changed = current_level != previous_level

        if risk_delta > 0:
            trend = "worsening"
        elif risk_delta < 0:
            trend = "improving"
        else:
            trend = "stable"

        factors_changed = []
        factors_changed.extend(self._diff_factors(
            "wildfire", current_assessment.get("wildfire_factors"), previous_assessment.get("wildfire_factors")
        ))
        factors_changed.extend(self._diff_factors(
            "flood", current_assessment.get("flood_factors"), previous_assessment.get("flood_factors")
        ))

        changed = risk_delta != 0 or risk_level_changed or bool(factors_changed)

        result = {
            "property_id": property_id,
            "changed": changed,
            "is_baseline": False,
            "risk_delta": risk_delta,
            "risk_level_changed": risk_level_changed,
            "trend": trend,
            "factors_changed": factors_changed,
        }

        if changed:
            logger.info(
                "Property %s changed: delta=%s, trend=%s, %d factor(s) shifted",
                property_id, risk_delta, trend, len(factors_changed),
            )
        return result

    @staticmethod
    def _diff_factors(prefix: str, current_factors: Optional[Dict], previous_factors: Optional[Dict]) -> List[Dict]:
        """Diff two factor dicts, returning entries for every key that changed."""
        current_factors = current_factors or {}
        previous_factors = previous_factors or {}
        keys = set(current_factors.keys()) | set(previous_factors.keys())

        changes = []
        for key in sorted(keys - IGNORED_FACTOR_KEYS):
            old_val = previous_factors.get(key)
            new_val = current_factors.get(key)
            if _values_differ(old_val, new_val):
                changes.append({"factor": f"{prefix}.{key}", "from": old_val, "to": new_val})
        return changes


if __name__ == "__main__":
    print("=" * 60)
    print("Change Detector Test")
    print("=" * 60)
    print()

    detector = ChangeDetector()

    previous = {
        "overall_risk_score": 45.0,
        "risk_level": "medium",
        "wildfire_factors": {"proximity_score": 60.0, "wind_score": 0.0, "distance_km": 15.0},
        "flood_factors": {"rainfall_score": 10.0},
    }
    current = {
        "overall_risk_score": 77.09,
        "risk_level": "high",
        "wildfire_factors": {"proximity_score": 88.28, "wind_score": 75.0, "distance_km": 5.86},
        "flood_factors": {"rainfall_score": 10.0},
    }

    print("1. Worsening scenario (fire got closer, wind picked up)")
    result = detector.detect_changes(1, current, previous)
    print(f"   changed={result['changed']}, delta={result['risk_delta']}, trend={result['trend']}")
    print(f"   risk_level_changed={result['risk_level_changed']}")
    for f in result["factors_changed"]:
        print(f"   - {f['factor']}: {f['from']} -> {f['to']}")

    print()
    print("2. Improving scenario (same data, reversed)")
    result = detector.detect_changes(1, previous, current)
    print(f"   changed={result['changed']}, delta={result['risk_delta']}, trend={result['trend']}")

    print()
    print("3. No change")
    result = detector.detect_changes(1, current, current)
    print(f"   changed={result['changed']}, delta={result['risk_delta']}, trend={result['trend']}")

    print()
    print("4. First-ever assessment (no previous)")
    result = detector.detect_changes(1, current, None)
    print(f"   changed={result['changed']}, is_baseline={result['is_baseline']}, trend={result['trend']}")

    print()
    print("=" * 60)
    print("All tests complete!")
    print("=" * 60)
