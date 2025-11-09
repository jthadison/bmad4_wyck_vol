"""
Integration tests for Risk Allocation Configuration

Test Coverage:
--------------
- AC 8: Configuration changes properly update risk allocation
- Integration with YAML configuration files
- Full workflow testing (load → modify → reload)

Author: Story 7.1
"""

import tempfile
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from src.models.risk_allocation import PatternType
from src.risk_management.risk_allocator import RiskAllocator


class TestConfigurationUpdateIntegration:
    """AC 8: Configuration changes properly update risk allocation."""

    @pytest.fixture
    def temp_config_path(self):
        """Create temporary config file for testing."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            temp_config = {
                "risk_allocation": {
                    "version": "1.0",
                    "per_trade_maximum": 2.0,
                    "pattern_risk_percentages": {
                        "SPRING": 0.5,
                        "ST": 0.5,
                        "LPS": 0.7,
                        "SOS": 0.8,
                        "UTAD": 0.5,
                    },
                    "rationale": {
                        "SPRING": "Phase C test, 70% success",
                        "ST": "Secondary Test validates Spring",
                        "LPS": "Pullback confirmation, 75% success",
                        "SOS": "Breakout with false-breakout risk",
                        "UTAD": "Distribution short entry",
                    },
                    "override_allowed": True,
                    "override_constraints": {
                        "minimum_risk_pct": 0.1,
                        "maximum_risk_pct": 2.0,
                    },
                }
            }
            yaml.dump(temp_config, f)
            temp_path = f.name

        yield temp_path

        # Cleanup
        Path(temp_path).unlink()

    def test_configuration_update_integration(self, temp_config_path):
        """Configuration changes should properly update risk allocation."""
        # Load allocator with initial config
        allocator = RiskAllocator(config_path=temp_config_path)
        assert allocator.get_pattern_risk_pct(PatternType.SPRING) == Decimal("0.5")

        # Modify config file (simulate user editing YAML)
        with open(temp_config_path) as f:
            config = yaml.safe_load(f)

        config["risk_allocation"]["pattern_risk_percentages"]["SPRING"] = 0.8

        with open(temp_config_path, "w") as f:
            yaml.dump(config, f)

        # Reload allocator with updated config
        allocator_updated = RiskAllocator(config_path=temp_config_path)
        assert allocator_updated.get_pattern_risk_pct(PatternType.SPRING) == Decimal("0.8")

    def test_multiple_pattern_updates(self, temp_config_path):
        """Multiple pattern updates should all be reflected."""
        # Load initial config
        allocator = RiskAllocator(config_path=temp_config_path)

        # Modify multiple patterns
        with open(temp_config_path) as f:
            config = yaml.safe_load(f)

        config["risk_allocation"]["pattern_risk_percentages"]["SPRING"] = 0.6
        config["risk_allocation"]["pattern_risk_percentages"]["LPS"] = 1.0
        config["risk_allocation"]["pattern_risk_percentages"]["SOS"] = 1.2

        with open(temp_config_path, "w") as f:
            yaml.dump(config, f)

        # Reload and verify all changes
        allocator_updated = RiskAllocator(config_path=temp_config_path)
        assert allocator_updated.get_pattern_risk_pct(PatternType.SPRING) == Decimal("0.6")
        assert allocator_updated.get_pattern_risk_pct(PatternType.LPS) == Decimal("1.0")
        assert allocator_updated.get_pattern_risk_pct(PatternType.SOS) == Decimal("1.2")

    def test_per_trade_maximum_update(self, temp_config_path):
        """Updating per_trade_maximum should be enforced."""
        # Load and verify initial maximum
        allocator = RiskAllocator(config_path=temp_config_path)
        assert allocator.config.per_trade_maximum == Decimal("2.0")

        # Update maximum to 1.5%
        with open(temp_config_path) as f:
            config = yaml.safe_load(f)

        config["risk_allocation"]["per_trade_maximum"] = 1.5

        with open(temp_config_path, "w") as f:
            yaml.dump(config, f)

        # Reload and verify new maximum
        allocator_updated = RiskAllocator(config_path=temp_config_path)
        assert allocator_updated.config.per_trade_maximum == Decimal("1.5")

    def test_invalid_config_rejected_on_reload(self, temp_config_path):
        """Invalid configuration should be rejected during reload."""
        # Modify config to have risk > per_trade_maximum
        with open(temp_config_path) as f:
            config = yaml.safe_load(f)

        config["risk_allocation"]["pattern_risk_percentages"]["SPRING"] = 2.5  # Exceeds 2.0%

        with open(temp_config_path, "w") as f:
            yaml.dump(config, f)

        # Should raise validation error
        with pytest.raises(ValueError, match="exceeds per-trade maximum"):
            RiskAllocator(config_path=temp_config_path)


class TestFullWorkflowIntegration:
    """Test complete workflow from config to risk calculation."""

    @pytest.fixture
    def temp_config_path(self):
        """Create temporary config file for testing."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            temp_config = {
                "risk_allocation": {
                    "version": "1.2",
                    "per_trade_maximum": 2.0,
                    "pattern_risk_percentages": {
                        "SPRING": 0.5,
                        "ST": 0.5,
                        "LPS": 0.7,
                        "SOS": 0.8,
                        "UTAD": 0.5,
                    },
                    "rationale": {
                        "SPRING": "Phase C test entry",
                        "ST": "Secondary Test",
                        "LPS": "Last Point of Support",
                        "SOS": "Sign of Strength",
                        "UTAD": "Upthrust After Distribution",
                    },
                    "override_allowed": True,
                    "override_constraints": {
                        "minimum_risk_pct": 0.1,
                        "maximum_risk_pct": 2.0,
                    },
                }
            }
            yaml.dump(temp_config, f)
            temp_path = f.name

        yield temp_path

        # Cleanup
        Path(temp_path).unlink()

    def test_complete_workflow_default_config(self, temp_config_path):
        """Test complete workflow with default configuration."""
        # 1. Load allocator
        allocator = RiskAllocator(config_path=temp_config_path)

        # 2. Get default risks
        spring_risk = allocator.get_pattern_risk_pct(PatternType.SPRING)
        lps_risk = allocator.get_pattern_risk_pct(PatternType.LPS)

        assert spring_risk == Decimal("0.5")
        assert lps_risk == Decimal("0.7")

        # 3. Set override
        allocator.set_pattern_risk_override(PatternType.SPRING, Decimal("0.7"))
        spring_risk_override = allocator.get_pattern_risk_pct(PatternType.SPRING)
        assert spring_risk_override == Decimal("0.7")

        # 4. Get volume-adjusted risk
        adjusted_risk = allocator.get_adjusted_pattern_risk(
            pattern_type=PatternType.LPS,
            volume_ratio=Decimal("2.4"),  # Very strong
        )
        # LPS 0.7% × 0.95 = 0.665%
        assert adjusted_risk == Decimal("0.665")

    def test_workflow_with_config_updates(self, temp_config_path):
        """Test workflow across config updates."""
        # 1. Load initial allocator
        allocator1 = RiskAllocator(config_path=temp_config_path)
        assert allocator1.get_pattern_risk_pct(PatternType.SPRING) == Decimal("0.5")

        # 2. Update config file
        with open(temp_config_path) as f:
            config = yaml.safe_load(f)

        config["risk_allocation"]["pattern_risk_percentages"]["SPRING"] = 0.6

        with open(temp_config_path, "w") as f:
            yaml.dump(config, f)

        # 3. Load new allocator (simulates app restart)
        allocator2 = RiskAllocator(config_path=temp_config_path)
        assert allocator2.get_pattern_risk_pct(PatternType.SPRING) == Decimal("0.6")

        # 4. Original allocator should still have old config
        assert allocator1.get_pattern_risk_pct(PatternType.SPRING) == Decimal("0.5")

    def test_workflow_override_persistence(self, temp_config_path):
        """Test that overrides are per-instance, not persisted to config."""
        # 1. Load allocator and set override
        allocator1 = RiskAllocator(config_path=temp_config_path)
        allocator1.set_pattern_risk_override(PatternType.SPRING, Decimal("1.0"))
        assert allocator1.get_pattern_risk_pct(PatternType.SPRING) == Decimal("1.0")

        # 2. Load new allocator (should have default, not override)
        allocator2 = RiskAllocator(config_path=temp_config_path)
        assert allocator2.get_pattern_risk_pct(PatternType.SPRING) == Decimal("0.5")


class TestConfigurationValidation:
    """Test configuration validation during load."""

    def test_missing_pattern_in_config(self):
        """Missing pattern in config should raise error."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            # Config missing ST pattern
            incomplete_config = {
                "risk_allocation": {
                    "version": "1.0",
                    "per_trade_maximum": 2.0,
                    "pattern_risk_percentages": {
                        "SPRING": 0.5,
                        "LPS": 0.7,
                        "SOS": 0.8,
                        "UTAD": 0.5,
                        # Missing ST
                    },
                    "rationale": {
                        "SPRING": "Test",
                        "LPS": "Test",
                        "SOS": "Test",
                        "UTAD": "Test",
                    },
                }
            }
            yaml.dump(incomplete_config, f)
            temp_path = f.name

        try:
            # Should work - Pydantic doesn't enforce dict keys match enum
            allocator = RiskAllocator(config_path=temp_path)

            # But accessing ST should raise KeyError
            with pytest.raises(KeyError):
                allocator.get_pattern_risk_pct(PatternType.ST)
        finally:
            Path(temp_path).unlink()

    def test_invalid_yaml_structure(self):
        """Invalid YAML structure should raise error."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            # Missing 'risk_allocation' key
            invalid_config = {"invalid_key": {"data": "value"}}
            yaml.dump(invalid_config, f)
            temp_path = f.name

        try:
            with pytest.raises(ValueError, match="missing 'risk_allocation' key"):
                RiskAllocator(config_path=temp_path)
        finally:
            Path(temp_path).unlink()
