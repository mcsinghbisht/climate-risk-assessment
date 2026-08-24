"""
Risk Assessment Data Access Object (DAO)

Persists and retrieves risk assessment snapshots from the risk_assessments
table (Task 3 schema). Mirrors PropertyDAO's design (Task 9), with one key
difference: assessments are never upserted - each save is a new time-series
snapshot, since the whole point of this table is to preserve risk history,
not just the latest value.

Input shape: save_assessment() accepts the dict produced by
RiskAggregator.build_overall_assessment() (Task 17) directly - property_id,
wildfire_risk_score, wildfire_factors, flood_risk_score, flood_factors,
overall_risk_score, risk_level, wildfire_explanation, flood_explanation.

Schema note: risk_assessments has no dedicated column for the explanation
strings - only wildfire_factors/flood_factors JSON columns exist (Task 3).
Rather than a schema migration for two extra text columns, the explanation
is folded into each factors JSON blob under an "explanation" key before
storage - the same pattern already used for raw_data in hazard_data (Task
10-12), and avoids a migration for what is really just more detail within
an already-JSON column.
"""

import json
import logging
from typing import Dict, List, Optional

from src.database.db import get_db_connection
from src.utils import get_utc_now, days_ago

logger = logging.getLogger(__name__)


def _row_to_dict(row) -> Dict:
    """Convert a sqlite3.Row into a plain dict, parsing JSON columns back
    into Python objects."""
    d = dict(row)
    for json_field in ("wildfire_factors", "flood_factors", "alerts_triggered"):
        if d.get(json_field):
            try:
                d[json_field] = json.loads(d[json_field])
            except (json.JSONDecodeError, TypeError):
                pass  # leave as raw string if somehow malformed
    return d


class RiskDAO:
    """Data access layer for the `risk_assessments` table."""

    def save_assessment(self, assessment: Dict, alerts_triggered: Optional[List] = None) -> int:
        """
        Save a new risk assessment snapshot. Always inserts a new row -
        never updates an existing one, so risk history is preserved.

        Args:
            assessment: Dict shaped like RiskAggregator.build_overall_assessment()'s
                        output - property_id, wildfire_risk_score, wildfire_factors,
                        flood_risk_score, flood_factors, overall_risk_score,
                        risk_level, and optionally wildfire_explanation/flood_explanation
            alerts_triggered: Optional list of alert dicts/strings triggered by this
                              assessment (Task 20 will populate this; safe to omit
                              until then - stored as NULL if not provided)

        Returns:
            The new assessment_id
        """
        wildfire_factors = dict(assessment.get("wildfire_factors") or {})
        if assessment.get("wildfire_explanation"):
            wildfire_factors["explanation"] = assessment["wildfire_explanation"]

        flood_factors = dict(assessment.get("flood_factors") or {})
        if assessment.get("flood_explanation"):
            flood_factors["explanation"] = assessment["flood_explanation"]

        conn = get_db_connection()
        try:
            cursor = conn.execute(
                """
                INSERT INTO risk_assessments (
                    property_id, assessment_timestamp, wildfire_risk_score,
                    wildfire_factors, flood_risk_score, flood_factors,
                    overall_risk_score, risk_level, alerts_triggered
                ) VALUES (
                    :property_id, :assessment_timestamp, :wildfire_risk_score,
                    :wildfire_factors, :flood_risk_score, :flood_factors,
                    :overall_risk_score, :risk_level, :alerts_triggered
                )
                """,
                {
                    "property_id": assessment["property_id"],
                    "assessment_timestamp": get_utc_now().isoformat(),
                    "wildfire_risk_score": assessment.get("wildfire_risk_score"),
                    "wildfire_factors": json.dumps(wildfire_factors),
                    "flood_risk_score": assessment.get("flood_risk_score"),
                    "flood_factors": json.dumps(flood_factors),
                    "overall_risk_score": assessment.get("overall_risk_score"),
                    "risk_level": assessment.get("risk_level"),
                    "alerts_triggered": json.dumps(alerts_triggered) if alerts_triggered else None,
                },
            )
            conn.commit()
            assessment_id = cursor.lastrowid
        finally:
            conn.close()

        logger.info(
            "Saved risk assessment %d for property %s: overall=%s (%s)",
            assessment_id, assessment.get("property_id"),
            assessment.get("overall_risk_score"), assessment.get("risk_level"),
        )
        return assessment_id

    def get_latest_assessment(self, property_id: int) -> Optional[Dict]:
        """
        Get the most recent risk assessment for a property.

        "Most recent" is determined by assessment_id (strictly increasing on
        insert), not assessment_timestamp, to avoid ambiguity when two
        assessments land in the same second.

        Args:
            property_id: The property's ID

        Returns:
            Assessment dict, or None if the property has no assessments yet
        """
        conn = get_db_connection()
        try:
            cursor = conn.execute(
                """
                SELECT * FROM risk_assessments
                WHERE property_id = ?
                ORDER BY assessment_id DESC
                LIMIT 1
                """,
                (property_id,),
            )
            row = cursor.fetchone()
            return _row_to_dict(row) if row else None
        finally:
            conn.close()

    def get_assessment_history(self, property_id: int, days: int = 30) -> List[Dict]:
        """
        Get all risk assessments for a property within the last N days,
        most recent first.

        Args:
            property_id: The property's ID
            days: Number of days of history to return (default 30)

        Returns:
            List of assessment dicts, ordered newest to oldest
        """
        cutoff = days_ago(days).isoformat()
        conn = get_db_connection()
        try:
            cursor = conn.execute(
                """
                SELECT * FROM risk_assessments
                WHERE property_id = ? AND assessment_timestamp > ?
                ORDER BY assessment_id DESC
                """,
                (property_id, cutoff),
            )
            return [_row_to_dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_all_latest_assessments(self) -> List[Dict]:
        """
        Get the single latest assessment for every property that has at
        least one, ordered by property_id.

        Returns:
            List of assessment dicts, one per property
        """
        conn = get_db_connection()
        try:
            cursor = conn.execute(
                """
                SELECT ra.* FROM risk_assessments ra
                INNER JOIN (
                    SELECT property_id, MAX(assessment_id) AS max_id
                    FROM risk_assessments
                    GROUP BY property_id
                ) latest
                ON ra.property_id = latest.property_id AND ra.assessment_id = latest.max_id
                ORDER BY ra.property_id
                """
            )
            return [_row_to_dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("Risk DAO Test")
    print("=" * 60)
    print()

    dao = RiskDAO()

    sample_assessment = {
        "property_id": 1,
        "wildfire_risk_score": 77.09,
        "wildfire_factors": {"proximity_score": 88.28, "distance_km": 5.86},
        "flood_risk_score": 12.0,
        "flood_factors": {"rainfall_score": 0.0},
        "overall_risk_score": 44.5,
        "risk_level": "medium",
        "wildfire_explanation": "Nearest active fire is 5.86 km away.",
        "flood_explanation": "No significant recent rainfall detected.",
    }

    assessment_id = dao.save_assessment(sample_assessment)
    print(f"Saved assessment_id: {assessment_id}")

    latest = dao.get_latest_assessment(1)
    print(f"Latest assessment: overall={latest['overall_risk_score']}, level={latest['risk_level']}")
    print(f"Wildfire factors (with explanation folded in): {latest['wildfire_factors']}")

    history = dao.get_assessment_history(1, days=30)
    print(f"History (last 30 days): {len(history)} record(s)")

    all_latest = dao.get_all_latest_assessments()
    print(f"All latest assessments across portfolio: {len(all_latest)} record(s)")

    print()
    print("=" * 60)
    print("All tests complete!")
    print("=" * 60)
