"""
Alert Data Access Object (DAO) - Persistence & Lifecycle Management

Persists alerts from AlertEngine (Task 20) durably and manages their
lifecycle over time: active -> acknowledged / stale -> resolved. Full
design rationale, state machine, and configuration in
docs/alert-lifecycle-design.md.

Key responsibilities that live here (not in AlertEngine or Notifier):

  - Deduplication: re-evaluating the same ongoing condition updates the
    existing alert row instead of inserting a duplicate.
  - Resolution with hysteresis: a score must drop meaningfully below the
    trigger threshold (not just barely under it) to count as resolved,
    preventing open/close flapping.
  - Staleness: if a property hasn't been reassessed recently, its alert
    can no longer be trusted as "still true" and is marked stale rather
    than silently continuing to claim it's active.
  - Re-notification cooldown: should_notify()/mark_notified() let a
    caller (the future monitoring loop, or Notifier) avoid re-sending
    the same ongoing alert every cycle.

This is deliberately the single place this logic lives - a future
delivery channel (email, dashboard, Slack) only ever needs to call
get_active_alerts()/get_alerts_for_property()/acknowledge_alert() and
never needs to reimplement any of the above.
"""

import logging
from typing import Dict, List, Optional

from src.config import get_config
from src.database.db import get_db_connection
from src.utils import get_utc_now, is_within_hours, parse_iso_timestamp

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = ("active", "acknowledged")


class AlertDAO:
    """Persists alerts and manages their lifecycle (Task 21b)."""

    def __init__(self):
        self._ensure_schema()

        config = get_config()
        alerts_cfg = config.get_section("alerts")
        self.wildfire_threshold: float = alerts_cfg.get("wildfire_threshold", 70)
        self.flood_threshold: float = alerts_cfg.get("flood_threshold", 65)
        self.portfolio_threshold_percent: float = alerts_cfg.get("portfolio_threshold_percent", 10)
        self.renotify_interval_minutes: float = alerts_cfg.get("renotify_interval_minutes", 60)
        self.resolution_hysteresis: float = alerts_cfg.get("resolution_hysteresis", 10)
        self.portfolio_resolution_hysteresis_percent: float = alerts_cfg.get(
            "portfolio_resolution_hysteresis_percent", 2
        )
        self.stale_after_hours: float = alerts_cfg.get("stale_after_hours", 6)

    @staticmethod
    def _ensure_schema() -> None:
        """
        Idempotent migration safety net: if this DAO runs against a database
        created before Task 21b (i.e. the `alerts` table exists but lacks
        the lifecycle columns), add them via ALTER TABLE. A no-op for any
        database created from the current schema (Task 3 + Task 21b's
        updated CREATE TABLE), since the columns already exist there.
        """
        conn = get_db_connection()
        try:
            existing_cols = {row["name"] for row in conn.execute("PRAGMA table_info(alerts)").fetchall()}
            if "status" not in existing_cols:
                conn.execute("ALTER TABLE alerts ADD COLUMN status TEXT DEFAULT 'active'")
            if "resolved_at" not in existing_cols:
                conn.execute("ALTER TABLE alerts ADD COLUMN resolved_at TIMESTAMP")
            if "last_notified_at" not in existing_cols:
                conn.execute("ALTER TABLE alerts ADD COLUMN last_notified_at TIMESTAMP")
            conn.commit()

            AlertDAO._ensure_property_id_nullable(conn)
        finally:
            conn.close()

    @staticmethod
    def _ensure_property_id_nullable(conn) -> None:
        """
        Task 27 migration: property_id must become nullable to support
        portfolio-level alerts (risk_type='portfolio_high_risk_pct',
        property_id=None - see docs/alert-lifecycle-design.md). SQLite has
        no ALTER COLUMN to drop a NOT NULL constraint, so this rebuilds the
        table when needed. A no-op for any database already created from
        the current (nullable) schema.
        """
        property_id_col = next(
            row for row in conn.execute("PRAGMA table_info(alerts)").fetchall()
            if row["name"] == "property_id"
        )
        if property_id_col["notnull"] == 0:
            return

        before_count = conn.execute("SELECT COUNT(*) AS c FROM alerts").fetchone()["c"]

        conn.execute(
            """
            CREATE TABLE alerts_new (
                alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
                property_id INTEGER,
                risk_type TEXT NOT NULL,
                risk_score REAL,
                threshold_exceeded REAL,
                alert_level TEXT CHECK (alert_level IN ('warning', 'critical')),
                message TEXT,
                triggered_at TIMESTAMP NOT NULL,
                acknowledged_at TIMESTAMP,
                status TEXT CHECK (status IN ('active', 'acknowledged', 'stale', 'resolved')) DEFAULT 'active',
                resolved_at TIMESTAMP,
                last_notified_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (property_id) REFERENCES properties(property_id),
                CHECK (risk_score >= 0 AND risk_score <= 100)
            )
            """
        )
        conn.execute(
            """
            INSERT INTO alerts_new (
                alert_id, property_id, risk_type, risk_score, threshold_exceeded,
                alert_level, message, triggered_at, acknowledged_at, status,
                resolved_at, last_notified_at, created_at
            )
            SELECT
                alert_id, property_id, risk_type, risk_score, threshold_exceeded,
                alert_level, message, triggered_at, acknowledged_at, status,
                resolved_at, last_notified_at, created_at
            FROM alerts
            """
        )

        after_count = conn.execute("SELECT COUNT(*) AS c FROM alerts_new").fetchone()["c"]
        if after_count != before_count:
            conn.execute("DROP TABLE alerts_new")
            conn.commit()
            raise RuntimeError(
                f"alerts table migration row count mismatch ({before_count} -> {after_count}) - "
                "migration aborted, original table untouched"
            )

        conn.execute("DROP TABLE alerts")
        conn.execute("ALTER TABLE alerts_new RENAME TO alerts")
        conn.commit()
        logger.info("Migrated alerts table: property_id is now nullable (%d rows preserved)", after_count)

    def _absolute_threshold_for(self, risk_type: str) -> float:
        if risk_type == "wildfire":
            return self.wildfire_threshold
        elif risk_type == "flood":
            return self.flood_threshold
        return self.portfolio_threshold_percent  # risk_type == "portfolio_high_risk_pct"

    def _resolution_hysteresis_for(self, risk_type: str) -> float:
        if risk_type == "portfolio_high_risk_pct":
            return self.portfolio_resolution_hysteresis_percent
        return self.resolution_hysteresis

    @staticmethod
    def _record_history(conn, alert_id: int, old_status: Optional[str], new_status: str) -> None:
        conn.execute(
            "INSERT INTO alert_history (alert_id, old_status, new_status, timestamp) VALUES (?, ?, ?, ?)",
            (alert_id, old_status, new_status, get_utc_now().isoformat()),
        )

    def save_new_alerts(self, alerts: List[Dict]) -> List[int]:
        """
        Persist a list of alerts from AlertEngine.evaluate_property().

        For each alert, if an active/acknowledged alert already exists for
        the same property_id + risk_type + alert_level, its score/message
        are updated in place rather than inserting a duplicate row -
        critical and warning alerts for the same hazard type are tracked as
        independent lifecycles (matching AlertEngine's own design, Task 20).

        Args:
            alerts: List of alert dicts (AlertEngine's output shape)

        Returns:
            List of alert_ids for genuinely new alerts only (excludes
            updates to existing ongoing alerts)
        """
        new_ids = []
        conn = get_db_connection()
        try:
            for alert in alerts:
                existing = conn.execute(
                    """
                    SELECT alert_id FROM alerts
                    WHERE property_id IS ? AND risk_type = ? AND alert_level = ?
                      AND status IN ('active', 'acknowledged')
                    ORDER BY alert_id DESC LIMIT 1
                    """,
                    (alert["property_id"], alert["risk_type"], alert["alert_level"]),
                ).fetchone()

                if existing:
                    conn.execute(
                        "UPDATE alerts SET risk_score = ?, message = ?, triggered_at = ? WHERE alert_id = ?",
                        (alert["risk_score"], alert["message"], alert["triggered_at"], existing["alert_id"]),
                    )
                else:
                    cursor = conn.execute(
                        """
                        INSERT INTO alerts (
                            property_id, risk_type, risk_score, threshold_exceeded,
                            alert_level, message, triggered_at, status
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'active')
                        """,
                        (
                            alert["property_id"], alert["risk_type"], alert["risk_score"],
                            alert["threshold_exceeded"], alert["alert_level"],
                            alert["message"], alert["triggered_at"],
                        ),
                    )
                    new_ids.append(cursor.lastrowid)
            conn.commit()
        finally:
            conn.close()

        if new_ids:
            logger.info("Persisted %d new alert(s)", len(new_ids))
        return new_ids

    def evaluate_lifecycle(
        self, property_id: Optional[int], risk_type: str, current_score: float,
        latest_assessment_timestamp: Optional[str],
    ) -> List[Dict]:
        """
        Re-evaluate every active/acknowledged alert for a property+risk_type
        against the current score and data freshness.

        A property+risk_type can have more than one concurrent alert row -
        e.g. AlertEngine (Task 20) can raise both a 'critical' (absolute
        threshold) and a 'warning' (sudden increase) alert independently for
        the same hazard. Each is its own lifecycle and must be evaluated
        separately; evaluating only the most-recently-inserted row would
        leave older siblings stuck 'active' forever even after the risk
        clears (found via Task 23's end-to-end integration testing).

        Applies, in order, to each matching alert:
          1. Staleness - if the latest assessment is older than
             stale_after_hours, status becomes 'stale' regardless of score.
          2. Resolution - if the score has dropped below
             (absolute_threshold - resolution_hysteresis), status becomes
             'resolved' and resolved_at is set.
          3. Otherwise stays active/acknowledged (an acknowledged alert
             does not revert to plain 'active' just because it's still
             ongoing).

        Args:
            property_id: The property's ID
            risk_type: 'wildfire' or 'flood'
            current_score: The property's current score for this risk_type
            latest_assessment_timestamp: ISO timestamp of the most recent
                risk assessment for this property (None if never assessed)

        Returns:
            List of updated alert dicts (empty if there's no active/
            acknowledged alert for this property+risk_type to evaluate)
        """
        conn = get_db_connection()
        try:
            rows = conn.execute(
                """
                SELECT * FROM alerts
                WHERE property_id IS ? AND risk_type = ? AND status IN ('active', 'acknowledged')
                ORDER BY alert_id DESC
                """,
                (property_id, risk_type),
            ).fetchall()
            if not rows:
                return []

            now = get_utc_now().isoformat()
            is_stale = self._is_stale(latest_assessment_timestamp)
            resolution_point = self._absolute_threshold_for(risk_type) - self._resolution_hysteresis_for(risk_type)

            results = []
            for row in rows:
                alert = dict(row)
                old_status = alert["status"]

                if is_stale:
                    new_status = "stale"
                elif current_score < resolution_point:
                    new_status = "resolved"
                else:
                    new_status = old_status  # stays active or acknowledged as-is

                updates = {"risk_score": current_score, "status": new_status}
                if new_status == "resolved":
                    updates["resolved_at"] = now

                set_clause = ", ".join(f"{k} = :{k}" for k in updates)
                conn.execute(
                    f"UPDATE alerts SET {set_clause} WHERE alert_id = :alert_id",
                    {**updates, "alert_id": alert["alert_id"]},
                )

                if new_status != old_status:
                    self._record_history(conn, alert["alert_id"], old_status, new_status)
                    logger.info(
                        "Alert %d (property=%s, %s) transitioned %s -> %s",
                        alert["alert_id"], property_id, risk_type, old_status, new_status,
                    )

                alert.update(updates)
                results.append(alert)

            conn.commit()
            return results
        finally:
            conn.close()

    def _is_stale(self, latest_assessment_timestamp: Optional[str]) -> bool:
        if not latest_assessment_timestamp:
            return True
        try:
            return not is_within_hours(
                parse_iso_timestamp(latest_assessment_timestamp), self.stale_after_hours
            )
        except ValueError:
            return True

    def should_notify(self, alert_id: int) -> bool:
        """
        Check whether enough time has passed since this alert was last
        notified to send another notification (the re-notification
        cooldown, renotify_interval_minutes).

        Args:
            alert_id: The alert's ID

        Returns:
            True if never notified, or if the cooldown has elapsed
        """
        conn = get_db_connection()
        try:
            row = conn.execute(
                "SELECT last_notified_at FROM alerts WHERE alert_id = ?", (alert_id,)
            ).fetchone()
            if not row or not row["last_notified_at"]:
                return True
            return not is_within_hours(
                parse_iso_timestamp(row["last_notified_at"]), self.renotify_interval_minutes / 60.0
            )
        finally:
            conn.close()

    def mark_notified(self, alert_id: int) -> None:
        """Record that this alert was just sent to a notification channel."""
        conn = get_db_connection()
        try:
            conn.execute(
                "UPDATE alerts SET last_notified_at = ? WHERE alert_id = ?",
                (get_utc_now().isoformat(), alert_id),
            )
            conn.commit()
        finally:
            conn.close()

    def get_active_alerts(self) -> List[Dict]:
        """Get all alerts currently in 'active' or 'stale' status, across the portfolio."""
        conn = get_db_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM alerts WHERE status IN ('active', 'stale') ORDER BY alert_id DESC"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_alerts_for_property(self, property_id: Optional[int], include_resolved: bool = False) -> List[Dict]:
        """
        Get alerts for a specific property, or portfolio-level alerts if
        property_id=None (risk_type='portfolio_high_risk_pct' - Task 27).

        Args:
            property_id: The property's ID, or None for portfolio-level alerts
            include_resolved: If False (default), excludes resolved alerts

        Returns:
            List of alert dicts, newest first
        """
        conn = get_db_connection()
        try:
            if include_resolved:
                rows = conn.execute(
                    "SELECT * FROM alerts WHERE property_id IS ? ORDER BY alert_id DESC", (property_id,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM alerts WHERE property_id IS ? AND status != 'resolved' ORDER BY alert_id DESC",
                    (property_id,),
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def acknowledge_alert(self, alert_id: int) -> bool:
        """
        Mark an alert as acknowledged by a human.

        Args:
            alert_id: The alert's ID

        Returns:
            True if the alert was found and acknowledged, False if no such alert exists
        """
        conn = get_db_connection()
        try:
            row = conn.execute("SELECT status FROM alerts WHERE alert_id = ?", (alert_id,)).fetchone()
            if not row:
                return False

            old_status = row["status"]
            now = get_utc_now().isoformat()
            conn.execute(
                "UPDATE alerts SET status = 'acknowledged', acknowledged_at = ? WHERE alert_id = ?",
                (now, alert_id),
            )
            self._record_history(conn, alert_id, old_status, "acknowledged")
            conn.commit()
            return True
        finally:
            conn.close()


if __name__ == "__main__":
    from src.config import setup_logging

    setup_logging()

    print("=" * 60)
    print("Alert DAO Test")
    print("=" * 60)
    print()

    dao = AlertDAO()

    sample_alert = {
        "property_id": 1, "risk_type": "wildfire", "risk_score": 80,
        "threshold_exceeded": 70, "alert_level": "critical",
        "message": "Test critical alert", "triggered_at": get_utc_now().isoformat(),
    }

    ids_first = dao.save_new_alerts([sample_alert])
    print(f"First save: {len(ids_first)} new alert(s) -> {ids_first}")

    ids_second = dao.save_new_alerts([sample_alert])
    print(f"Second save (same condition): {len(ids_second)} new alert(s) (should be 0 - deduped)")

    active = dao.get_active_alerts()
    print(f"Active alerts: {len(active)}")

    if ids_first:
        alert_id = ids_first[0]
        print(f"should_notify({alert_id}): {dao.should_notify(alert_id)} (should be True - never notified)")
        dao.mark_notified(alert_id)
        print(f"should_notify({alert_id}) after marking: {dao.should_notify(alert_id)} (should be False - cooldown active)")

        # Simulate the risk dropping well below threshold -> resolved
        results = dao.evaluate_lifecycle(1, "wildfire", current_score=50, latest_assessment_timestamp=get_utc_now().isoformat())
        print(f"After evaluate_lifecycle (score dropped to 50): status={results[0]['status']}")

    print()
    print("=" * 60)
    print("All tests complete!")
    print("=" * 60)
