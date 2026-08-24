"""
Pytest test suite for the logging framework (Task 6)

Run with: pytest tests/test_logging_pytest.py -v
"""

import logging
import pytest

from src.config.logging_config import (
    setup_logging,
    is_configured,
    LOGS_DIR,
    DEFAULT_LOGGING_CONFIG_PATH,
)


class TestLoggingSetup:
    """Tests for setup_logging() and its side effects."""

    def test_config_file_exists(self):
        """Test that the logging config JSON file exists."""
        assert DEFAULT_LOGGING_CONFIG_PATH.exists()

    def test_setup_logging_creates_logs_dir(self):
        """Test that logs/ directory is created on setup."""
        setup_logging()
        assert LOGS_DIR.exists()
        assert LOGS_DIR.is_dir()

    def test_setup_logging_marks_configured(self):
        """Test that is_configured() reflects setup state."""
        setup_logging()
        assert is_configured() is True

    def test_setup_logging_is_idempotent(self):
        """Test that calling setup_logging() twice doesn't error."""
        setup_logging()
        setup_logging()  # should be a no-op, not raise
        assert is_configured() is True

    def test_app_log_file_created(self):
        """Test that logs/app.log is created after setup."""
        setup_logging()
        logger = logging.getLogger("test_app_log_creation")
        logger.info("pytest test message")
        assert (LOGS_DIR / "app.log").exists()

    def test_alerts_log_file_created(self):
        """Test that logs/alerts.log is created when the alerts logger is used."""
        setup_logging()
        alerts_logger = logging.getLogger("alerts")
        alerts_logger.info("pytest alert test message")
        assert (LOGS_DIR / "alerts.log").exists()

    def test_errors_log_file_created(self):
        """Test that logs/errors.log is created when an ERROR is logged."""
        setup_logging()
        logger = logging.getLogger("test_error_log_creation")
        logger.error("pytest error test message")
        assert (LOGS_DIR / "errors.log").exists()

    def test_app_log_contains_message(self):
        """Test that a logged message actually appears in app.log."""
        setup_logging()
        marker = "UNIQUE_PYTEST_MARKER_12345"
        logger = logging.getLogger("test_marker_logger")
        logger.info(marker)

        # Flush handlers so content is written to disk before we read it
        for handler in logging.getLogger().handlers:
            handler.flush()

        content = (LOGS_DIR / "app.log").read_text(encoding="utf-8")
        assert marker in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
