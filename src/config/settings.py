"""
Configuration Manager

Loads and provides access to application settings from JSON config files.
Supports dot-notation access to nested configuration values.
"""

import json
from pathlib import Path
from typing import Any, Optional


# Project root directory (3 levels up from this file: src/config/settings.py)
PROJECT_ROOT = Path(__file__).parent.parent.parent
DEFAULT_SETTINGS_PATH = PROJECT_ROOT / "config" / "settings.json"
DEFAULT_LOGGING_CONFIG_PATH = PROJECT_ROOT / "config" / "logging_config.json"


class ConfigManager:
    """
    Manages application configuration loaded from JSON files.

    Supports dot-notation access to nested values, e.g.:
        config.get("monitoring.interval_minutes")
        config.get("alerts.wildfire_threshold")
    """

    def __init__(self, settings_path: Optional[Path] = None):
        """
        Initialize ConfigManager and load settings.

        Args:
            settings_path: Path to settings JSON file.
                          Defaults to config/settings.json
        """
        self.settings_path = settings_path or DEFAULT_SETTINGS_PATH
        self._settings: dict = {}
        self.reload()

    def reload(self) -> None:
        """Load (or reload) settings from the JSON file."""
        if not self.settings_path.exists():
            raise FileNotFoundError(
                f"Settings file not found: {self.settings_path}"
            )

        with open(self.settings_path, "r", encoding="utf-8") as f:
            self._settings = json.load(f)

    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get a configuration value using dot notation.

        Args:
            key_path: Dot-separated path to the value
                      (e.g., "monitoring.interval_minutes")
            default: Value to return if key path is not found

        Returns:
            The configuration value, or default if not found

        Example:
            >>> config.get("alerts.wildfire_threshold")
            70
            >>> config.get("nonexistent.key", "fallback")
            'fallback'
        """
        keys = key_path.split(".")
        value = self._settings

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default

        return value

    def get_required(self, key_path: str) -> Any:
        """
        Get a configuration value, raising an error if not found.

        Args:
            key_path: Dot-separated path to the value

        Returns:
            The configuration value

        Raises:
            KeyError: If the key path does not exist
        """
        sentinel = object()
        value = self.get(key_path, sentinel)
        if value is sentinel:
            raise KeyError(f"Required config key not found: {key_path}")
        return value

    def get_section(self, section: str) -> dict:
        """
        Get an entire configuration section as a dictionary.

        Args:
            section: Top-level section name (e.g., "risk_scoring")

        Returns:
            Dictionary of the section, or empty dict if not found
        """
        return self._settings.get(section, {})

    def as_dict(self) -> dict:
        """Return the full configuration as a dictionary."""
        return self._settings

    def validate(self) -> tuple:
        """
        Validate that required configuration keys are present.

        Returns:
            Tuple of (is_valid: bool, errors: list[str])
        """
        errors = []

        required_keys = [
            "monitoring.interval_minutes",
            "monitoring.enabled",
            "risk_scoring.wildfire_weights",
            "risk_scoring.flood_weights",
            "risk_scoring.overall_weights",
            "alerts.wildfire_threshold",
            "alerts.flood_threshold",
            "database.path",
        ]

        sentinel = object()
        for key in required_keys:
            if self.get(key, sentinel) is sentinel:
                errors.append(f"Missing required config key: {key}")

        # Validate weight sums (should sum to ~1.0)
        for weight_key in ["risk_scoring.wildfire_weights", "risk_scoring.flood_weights",
                           "risk_scoring.overall_weights"]:
            weights = self.get(weight_key)
            if isinstance(weights, dict):
                total = sum(weights.values())
                if not (0.99 <= total <= 1.01):
                    errors.append(
                        f"{weight_key} weights should sum to 1.0, got {total}"
                    )

        return len(errors) == 0, errors

    def __repr__(self) -> str:
        return f"ConfigManager(settings_path='{self.settings_path}')"


# Module-level singleton for convenient access
_default_config: Optional[ConfigManager] = None


def get_config() -> ConfigManager:
    """
    Get the default ConfigManager singleton instance.

    Returns:
        Shared ConfigManager instance
    """
    global _default_config
    if _default_config is None:
        _default_config = ConfigManager()
    return _default_config


if __name__ == "__main__":
    print("=" * 60)
    print("Configuration Manager Test")
    print("=" * 60)

    config = ConfigManager()

    print("\n1. Basic dot-notation access")
    print("-" * 60)
    print(f"monitoring.interval_minutes = {config.get('monitoring.interval_minutes')}")
    print(f"alerts.wildfire_threshold   = {config.get('alerts.wildfire_threshold')}")
    print(f"alerts.flood_threshold      = {config.get('alerts.flood_threshold')}")
    print(f"database.path               = {config.get('database.path')}")

    print("\n2. Default values for missing keys")
    print("-" * 60)
    print(f"nonexistent.key (default='N/A') = {config.get('nonexistent.key', 'N/A')}")

    print("\n3. Get entire section")
    print("-" * 60)
    wildfire_weights = config.get_section("risk_scoring").get("wildfire_weights")
    print(f"wildfire_weights = {wildfire_weights}")

    print("\n4. Validation")
    print("-" * 60)
    is_valid, errors = config.validate()
    print(f"Config valid: {is_valid}")
    if errors:
        for error in errors:
            print(f"  [ERROR] {error}")
    else:
        print("  No errors found!")

    print("\n" + "=" * 60)
    print("All tests complete!")
    print("=" * 60)
