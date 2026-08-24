"""
Pytest test suite for AlertDAO (Task 21b)

Run with: pytest tests/test_alert_dao_pytest.py -v

Uses a temporary SQLite database (properties + alerts + alert_history
schema) so these tests never touch or depend on data/climate_risk.db.
"""

from datetime import timedelta

import pytest

import src.database.db as db_module
from src.database.alert_dao import AlertDAO
from src.utils import get_utc_now


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Temporary SQLite database with properties, alerts, alert_history schema."""
    db_path = tmp_path / "test_climate_risk.db"
    monkeypatch.setattr(db_module, "DB_PATH", db_path)

    conn = db_module.get_db_connection()
    schema = db_module.get_schema()
    conn.execute(schema["properties"])
    conn.execute(schema["alerts"])
    conn.execute(schema["alert_history"])
    conn.execute(
        "INSERT INTO properties (property_id, address, latitude, longitude) "
        "VALUES (1, 'Test Property', 33.75, -116.72)"
    )
    conn.commit()
    conn.close()

    return db_path


def make_alert(property_id=1, risk_type="wildfire", risk_score=80,
               threshold_exceeded=70, alert_level="critical", message="Test alert"):
    return {
        "property_id": property_id,
        "risk_type": risk_type,
        "risk_score": risk_score,
        "threshold_exceeded": threshold_exceeded,
        "alert_level": alert_level,
        "message": message,
        "triggered_at": get_utc_now().isoformat(),
    }


@pytest.fixture
def dao(temp_db):
    return AlertDAO()


class TestSchemaMigration:
    def test_ensure_schema_is_idempotent(self, temp_db):
        """Instantiating AlertDAO twice (schema already has the columns the
        second time) must not raise."""
        AlertDAO()
        AlertDAO()  # should not error

    def test_lifecycle_columns_exist_after_init(self, temp_db):
        AlertDAO()
        conn = db_module.get_db_connection()
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(alerts)").fetchall()}
        conn.close()
        assert {"status", "resolved_at", "last_notified_at"}.issubset(cols)

    def test_migration_on_pre_existing_old_schema_table(self, tmp_path, monkeypatch):
        """Simulates a database created before Task 21b: an `alerts` table
        with the original (pre-lifecycle) columns only."""
        db_path = tmp_path / "old_schema.db"
        monkeypatch.setattr(db_module, "DB_PATH", db_path)

        conn = db_module.get_db_connection()
        conn.execute("""
            CREATE TABLE alerts (
                alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
                property_id INTEGER NOT NULL,
                risk_type TEXT NOT NULL,
                risk_score REAL,
                threshold_exceeded REAL,
                alert_level TEXT,
                message TEXT,
                triggered_at TIMESTAMP NOT NULL,
                acknowledged_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("CREATE TABLE alert_history (history_id INTEGER PRIMARY KEY, alert_id INTEGER, "
                     "old_status TEXT, new_status TEXT, timestamp TIMESTAMP)")
        conn.commit()
        conn.close()

        AlertDAO()  # should migrate without error

        conn = db_module.get_db_connection()
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(alerts)").fetchall()}
        conn.close()
        assert {"status", "resolved_at", "last_notified_at"}.issubset(cols)


class TestSaveNewAlerts:
    def test_returns_new_alert_id(self, dao):
        ids = dao.save_new_alerts([make_alert()])
        assert len(ids) == 1

    def test_repeated_save_of_same_condition_does_not_duplicate(self, dao):
        alert = make_alert()
        first_ids = dao.save_new_alerts([alert])
        second_ids = dao.save_new_alerts([alert])

        assert len(first_ids) == 1
        assert len(second_ids) == 0  # deduped, not a new row

        active = dao.get_active_alerts()
        assert len(active) == 1

    def test_critical_and_warning_for_same_hazard_are_independent(self, dao):
        """AlertEngine (Task 20) can produce two alerts for the same
        property+risk_type (one critical, one warning) - these must be
        tracked as separate lifecycle entities, not merged."""
        critical_alert = make_alert(alert_level="critical", risk_score=80)
        warning_alert = make_alert(alert_level="warning", risk_score=80)

        ids = dao.save_new_alerts([critical_alert, warning_alert])

        assert len(ids) == 2
        active = dao.get_active_alerts()
        assert len(active) == 2

    def test_different_property_does_not_dedupe(self, dao):
        conn = db_module.get_db_connection()
        conn.execute(
            "INSERT INTO properties (property_id, address, latitude, longitude) "
            "VALUES (2, 'Second Property', 30.0, -90.0)"
        )
        conn.commit()
        conn.close()

        ids = dao.save_new_alerts([make_alert(property_id=1), make_alert(property_id=2)])
        assert len(ids) == 2

    def test_updates_score_on_ongoing_alert(self, dao):
        dao.save_new_alerts([make_alert(risk_score=80)])
        dao.save_new_alerts([make_alert(risk_score=95)])  # same condition, worse score

        active = dao.get_active_alerts()
        assert len(active) == 1
        assert active[0]["risk_score"] == 95


class TestEvaluateLifecycle:
    def test_returns_empty_list_when_no_active_alert_exists(self, dao):
        results = dao.evaluate_lifecycle(1, "wildfire", current_score=50, latest_assessment_timestamp=get_utc_now().isoformat())
        assert results == []

    def test_score_still_above_resolution_point_stays_active(self, dao):
        dao.save_new_alerts([make_alert(risk_score=80)])  # threshold=70, hysteresis=10 -> resolution point 60
        results = dao.evaluate_lifecycle(1, "wildfire", current_score=65, latest_assessment_timestamp=get_utc_now().isoformat())
        assert results[0]["status"] == "active"

    def test_score_below_resolution_point_resolves(self, dao):
        dao.save_new_alerts([make_alert(risk_score=80)])
        results = dao.evaluate_lifecycle(1, "wildfire", current_score=55, latest_assessment_timestamp=get_utc_now().isoformat())
        assert results[0]["status"] == "resolved"
        assert results[0]["resolved_at"] is not None

    def test_score_just_at_hysteresis_boundary_does_not_resolve(self, dao):
        """resolution_point = 70 - 10 = 60; a score of exactly 60 should
        NOT resolve (strict '<' comparison, matching the pattern used
        elsewhere in this codebase)."""
        dao.save_new_alerts([make_alert(risk_score=80)])
        results = dao.evaluate_lifecycle(1, "wildfire", current_score=60, latest_assessment_timestamp=get_utc_now().isoformat())
        assert results[0]["status"] == "active"

    def test_stale_when_no_recent_assessment(self, dao):
        dao.save_new_alerts([make_alert(risk_score=80)])
        old_timestamp = (get_utc_now() - timedelta(hours=10)).isoformat()  # stale_after_hours=6
        results = dao.evaluate_lifecycle(1, "wildfire", current_score=80, latest_assessment_timestamp=old_timestamp)
        assert results[0]["status"] == "stale"

    def test_no_assessment_timestamp_is_treated_as_stale(self, dao):
        dao.save_new_alerts([make_alert(risk_score=80)])
        results = dao.evaluate_lifecycle(1, "wildfire", current_score=80, latest_assessment_timestamp=None)
        assert results[0]["status"] == "stale"

    def test_transition_recorded_in_alert_history(self, dao):
        dao.save_new_alerts([make_alert(risk_score=80)])
        dao.evaluate_lifecycle(1, "wildfire", current_score=55, latest_assessment_timestamp=get_utc_now().isoformat())

        conn = db_module.get_db_connection()
        history = conn.execute("SELECT * FROM alert_history").fetchall()
        conn.close()

        assert len(history) == 1
        assert history[0]["old_status"] == "active"
        assert history[0]["new_status"] == "resolved"

    def test_acknowledged_alert_does_not_revert_to_active_while_ongoing(self, dao):
        ids = dao.save_new_alerts([make_alert(risk_score=80)])
        dao.acknowledge_alert(ids[0])

        results = dao.evaluate_lifecycle(1, "wildfire", current_score=85, latest_assessment_timestamp=get_utc_now().isoformat())
        assert results[0]["status"] == "acknowledged"  # stays acknowledged, not reset to active

    def test_two_concurrent_alert_levels_both_resolve_independently(self, dao):
        """Regression test for the bug found during Task 23's integration
        testing: a critical (absolute-threshold) and a warning
        (sudden-increase) alert can coexist for the same property+risk_type.
        Both must be evaluated and resolved, not just the most recently
        inserted row."""
        dao.save_new_alerts([
            make_alert(risk_score=85, alert_level="critical", threshold_exceeded=70),
            make_alert(risk_score=85, alert_level="warning", threshold_exceeded=40),
        ])
        active = dao.get_active_alerts()
        assert len(active) == 2

        results = dao.evaluate_lifecycle(1, "wildfire", current_score=10, latest_assessment_timestamp=get_utc_now().isoformat())
        assert len(results) == 2
        assert all(r["status"] == "resolved" for r in results)
        assert dao.get_active_alerts() == []

    def test_two_concurrent_alert_levels_both_go_stale(self, dao):
        dao.save_new_alerts([
            make_alert(risk_score=85, alert_level="critical", threshold_exceeded=70),
            make_alert(risk_score=85, alert_level="warning", threshold_exceeded=40),
        ])
        old_timestamp = (get_utc_now() - timedelta(hours=10)).isoformat()
        results = dao.evaluate_lifecycle(1, "wildfire", current_score=85, latest_assessment_timestamp=old_timestamp)
        assert len(results) == 2
        assert all(r["status"] == "stale" for r in results)


class TestRenotificationCooldown:
    def test_should_notify_true_before_first_notification(self, dao):
        ids = dao.save_new_alerts([make_alert()])
        assert dao.should_notify(ids[0]) is True

    def test_should_notify_false_immediately_after_marking(self, dao):
        ids = dao.save_new_alerts([make_alert()])
        dao.mark_notified(ids[0])
        assert dao.should_notify(ids[0]) is False

    def test_should_notify_true_after_cooldown_elapses(self, dao):
        ids = dao.save_new_alerts([make_alert()])
        conn = db_module.get_db_connection()
        old_time = (get_utc_now() - timedelta(minutes=120)).isoformat()  # renotify_interval=60
        conn.execute("UPDATE alerts SET last_notified_at = ? WHERE alert_id = ?", (old_time, ids[0]))
        conn.commit()
        conn.close()

        assert dao.should_notify(ids[0]) is True


class TestGetActiveAlerts:
    def test_empty_when_none_exist(self, dao):
        assert dao.get_active_alerts() == []

    def test_excludes_resolved_alerts(self, dao):
        dao.save_new_alerts([make_alert(risk_score=80)])
        dao.evaluate_lifecycle(1, "wildfire", current_score=50, latest_assessment_timestamp=get_utc_now().isoformat())
        assert dao.get_active_alerts() == []

    def test_includes_stale_alerts(self, dao):
        dao.save_new_alerts([make_alert(risk_score=80)])
        dao.evaluate_lifecycle(1, "wildfire", current_score=80, latest_assessment_timestamp=None)
        active = dao.get_active_alerts()
        assert len(active) == 1
        assert active[0]["status"] == "stale"


class TestGetAlertsForProperty:
    def test_excludes_resolved_by_default(self, dao):
        dao.save_new_alerts([make_alert(risk_score=80)])
        dao.evaluate_lifecycle(1, "wildfire", current_score=50, latest_assessment_timestamp=get_utc_now().isoformat())
        assert dao.get_alerts_for_property(1) == []

    def test_includes_resolved_when_requested(self, dao):
        dao.save_new_alerts([make_alert(risk_score=80)])
        dao.evaluate_lifecycle(1, "wildfire", current_score=50, latest_assessment_timestamp=get_utc_now().isoformat())
        alerts = dao.get_alerts_for_property(1, include_resolved=True)
        assert len(alerts) == 1
        assert alerts[0]["status"] == "resolved"

    def test_only_returns_requested_property(self, dao):
        conn = db_module.get_db_connection()
        conn.execute(
            "INSERT INTO properties (property_id, address, latitude, longitude) "
            "VALUES (2, 'Second Property', 30.0, -90.0)"
        )
        conn.commit()
        conn.close()

        dao.save_new_alerts([make_alert(property_id=1), make_alert(property_id=2)])
        assert len(dao.get_alerts_for_property(1)) == 1


class TestAcknowledgeAlert:
    def test_sets_status_and_acknowledged_at(self, dao):
        ids = dao.save_new_alerts([make_alert()])
        success = dao.acknowledge_alert(ids[0])

        assert success is True
        alerts = dao.get_alerts_for_property(1)
        assert alerts[0]["status"] == "acknowledged"
        assert alerts[0]["acknowledged_at"] is not None

    def test_returns_false_for_unknown_alert_id(self, dao):
        assert dao.acknowledge_alert(9999) is False

    def test_records_transition_in_history(self, dao):
        ids = dao.save_new_alerts([make_alert()])
        dao.acknowledge_alert(ids[0])

        conn = db_module.get_db_connection()
        history = conn.execute("SELECT * FROM alert_history WHERE alert_id = ?", (ids[0],)).fetchall()
        conn.close()

        assert len(history) == 1
        assert history[0]["new_status"] == "acknowledged"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
