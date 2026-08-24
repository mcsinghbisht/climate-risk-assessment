"""
Logging Configuration

Sets up application-wide logging from config/logging_config.json.
Creates the logs/ directory automatically and wires console + rotating
file handlers so every module can use logging.getLogger(__name__).
"""

import json
import logging
import logging.config
from pathlib import Path
from typing import Optional

# Project root directory (3 levels up from this file: src/config/logging_config.py)
PROJECT_ROOT = Path(__file__).parent.parent.parent
DEFAULT_LOGGING_CONFIG_PATH = PROJECT_ROOT / "config" / "logging_config.json"
LOGS_DIR = PROJECT_ROOT / "logs"

_logging_configured = False


def setup_logging(config_path: Optional[Path] = None, force: bool = False) -> None:
    """
    Configure application-wide logging from a JSON dictConfig file.

    Idempotent by default: subsequent calls are no-ops unless force=True,
    so any module can safely call this at import/startup time.

    Args:
        config_path: Path to logging config JSON.
                     Defaults to config/logging_config.json
        force: If True, reconfigure even if already configured.
    """
    global _logging_configured

    if _logging_configured and not force:
        return

    config_path = config_path or DEFAULT_LOGGING_CONFIG_PATH

    if not config_path.exists():
        raise FileNotFoundError(f"Logging config file not found: {config_path}")

    # Ensure logs/ directory exists before handlers try to open files in it
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    with open(config_path, "r", encoding="utf-8") as f:
        logging_config = json.load(f)

    logging.config.dictConfig(logging_config)
    _logging_configured = True

    logger = logging.getLogger(__name__)
    logger.debug("Logging configured from %s", config_path)


def is_configured() -> bool:
    """Return True if setup_logging() has already run in this process."""
    return _logging_configured


if __name__ == "__main__":
    print("=" * 60)
    print("Logging Framework Test")
    print("=" * 60)
    print()

    setup_logging()

    logger = logging.getLogger("test_logger")
    alerts_logger = logging.getLogger("alerts")

    print("Emitting test log messages...")
    print("-" * 60)
    logger.debug("This is a DEBUG message (file only)")
    logger.info("This is an INFO message (console + file)")
    logger.warning("This is a WARNING message")
    logger.error("This is an ERROR message (also goes to errors.log)")
    alerts_logger.info("This is a test alert message (goes to alerts.log)")

    print()
    print(f"Logs directory: {LOGS_DIR}")
    print(f"  - app.log:    {(LOGS_DIR / 'app.log').exists()}")
    print(f"  - alerts.log: {(LOGS_DIR / 'alerts.log').exists()}")
    print(f"  - errors.log: {(LOGS_DIR / 'errors.log').exists()}")

    print()
    print("=" * 60)
    print("Check logs/app.log, logs/alerts.log, logs/errors.log for output")
    print("=" * 60)
