"""
Pytest test suite for the configuration system (Task 5)

Run with: pytest tests/test_config_pytest.py -v
"""

import pytest
from src.config import ConfigManager, get_config


class TestConfigManager:
    """ConfigManager loading and access tests."""

    def test_loads_settings_file(self):
        """Test that settings.json loads without error."""
        cfg = ConfigManager()
        assert cfg.as_dict() != {}

    def test_monitoring_interval(self):
        """Test dot-notation access to monitoring interval."""
        cfg = ConfigManager()
        assert cfg.get("monitoring.interval_minutes") == 5

    def test_wildfire_threshold(self):
        """Test dot-notation access to wildfire alert threshold."""
        cfg = ConfigManager()
        assert cfg.get("alerts.wildfire_threshold") == 70

    def test_flood_threshold(self):
        """Test dot-notation access to flood alert threshold."""
        cfg = ConfigManager()
        assert cfg.get("alerts.flood_threshold") == 65

    def test_default_value_for_missing_key(self):
        """Test that missing keys return the provided default."""
        cfg = ConfigManager()
        assert cfg.get("nonexistent.key", "fallback") == "fallback"

    def test_missing_key_without_default_returns_none(self):
        """Test that missing keys with no default return None."""
        cfg = ConfigManager()
        assert cfg.get("nonexistent.key") is None

    def test_get_required_raises_on_missing_key(self):
        """Test that get_required raises KeyError for missing keys."""
        cfg = ConfigManager()
        with pytest.raises(KeyError):
            cfg.get_required("nonexistent.key")

    def test_get_section_returns_dict(self):
        """Test retrieving an entire config section."""
        cfg = ConfigManager()
        section = cfg.get_section("risk_scoring")
        assert isinstance(section, dict)
        assert "wildfire_weights" in section

    def test_get_section_missing_returns_empty_dict(self):
        """Test that missing section returns empty dict."""
        cfg = ConfigManager()
        assert cfg.get_section("nonexistent_section") == {}

    def test_config_validation_passes(self):
        """Test that the default config passes validation."""
        cfg = ConfigManager()
        is_valid, errors = cfg.validate()
        assert is_valid is True
        assert errors == []

    def test_weight_sections_sum_to_one(self):
        """Test that risk scoring weight sections sum to ~1.0."""
        cfg = ConfigManager()
        for key in ["risk_scoring.wildfire_weights", "risk_scoring.flood_weights",
                    "risk_scoring.overall_weights"]:
            weights = cfg.get(key)
            total = sum(weights.values())
            assert 0.99 <= total <= 1.01, f"{key} sums to {total}"


class TestConfigSingleton:
    """Tests for the get_config() singleton accessor."""

    def test_get_config_returns_same_instance(self):
        """Test that get_config() returns a shared singleton."""
        cfg1 = get_config()
        cfg2 = get_config()
        assert cfg1 is cfg2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
