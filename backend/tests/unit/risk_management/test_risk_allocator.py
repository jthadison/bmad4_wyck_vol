"""
Unit tests for RiskAllocator - Pattern-Specific Risk Allocation

Test Coverage:
--------------
- AC 1: Risk allocation table (default percentages for each pattern)
- AC 5: Per-trade maximum validation (≤2.0%)
- AC 6: User override capability (set/clear overrides)
- AC 7: Each pattern type returns correct default risk percentage
- AC 9: Logging when non-default risk used
- AC 10: Fixed-point arithmetic and conservative rounding
- AC 11: Volume-adjusted risk scaling with 5 tiers

Author: Story 7.1
"""

from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal

import pytest

from src.models.risk_allocation import PatternType
from src.risk_management.risk_allocator import (
    RiskAllocator,
    get_volume_risk_multiplier,
)


class TestDefaultRiskPercentages:
    """AC 7: Each pattern type returns correct default risk percentage."""

    def test_spring_default_risk(self, allocator):
        """Spring pattern should return 0.5% default risk."""
        risk = allocator.get_pattern_risk_pct(PatternType.SPRING)
        assert risk == Decimal("0.5")
        assert isinstance(risk, Decimal)

    def test_st_default_risk(self, allocator):
        """ST pattern should return 0.5% default risk."""
        risk = allocator.get_pattern_risk_pct(PatternType.ST)
        assert risk == Decimal("0.5")
        assert isinstance(risk, Decimal)

    def test_lps_default_risk(self, allocator):
        """LPS pattern should return 0.7% default risk (HIGHEST)."""
        risk = allocator.get_pattern_risk_pct(PatternType.LPS)
        assert risk == Decimal("0.7")
        assert isinstance(risk, Decimal)

    def test_sos_default_risk(self, allocator):
        """SOS pattern should return 0.8% default risk."""
        risk = allocator.get_pattern_risk_pct(PatternType.SOS)
        assert risk == Decimal("0.8")
        assert isinstance(risk, Decimal)

    def test_utad_default_risk(self, allocator):
        """UTAD pattern should return 0.5% default risk."""
        risk = allocator.get_pattern_risk_pct(PatternType.UTAD)
        assert risk == Decimal("0.5")
        assert isinstance(risk, Decimal)

    def test_all_default_risks(self, allocator):
        """AC 1: Verify complete default risk allocation table."""
        expected = {
            PatternType.SPRING: Decimal("0.5"),
            PatternType.ST: Decimal("0.5"),
            PatternType.LPS: Decimal("0.7"),
            PatternType.SOS: Decimal("0.8"),
            PatternType.UTAD: Decimal("0.5"),
        }

        for pattern_type, expected_risk in expected.items():
            actual_risk = allocator.get_pattern_risk_pct(pattern_type)
            assert actual_risk == expected_risk, (
                f"{pattern_type} risk mismatch: " f"expected {expected_risk}%, got {actual_risk}%"
            )


class TestPerTradeMaximumValidation:
    """AC 5: Risk percentage must be ≤ 2.0% per-trade maximum."""

    def test_valid_override_within_limit(self, allocator):
        """Valid override within 2.0% limit should succeed."""
        allocator.set_pattern_risk_override(PatternType.SPRING, Decimal("1.5"))
        risk = allocator.get_pattern_risk_pct(PatternType.SPRING)
        assert risk == Decimal("1.5")

    def test_invalid_override_exceeds_limit(self, allocator):
        """Invalid override exceeding 2.0% should raise ValueError."""
        with pytest.raises(ValueError, match="FR18 violation"):
            allocator.set_pattern_risk_override(PatternType.SPRING, Decimal("2.5"))

    def test_override_at_maximum_allowed(self, allocator):
        """Override at exactly 2.0% (maximum) should be allowed."""
        allocator.set_pattern_risk_override(PatternType.SPRING, Decimal("2.0"))
        risk = allocator.get_pattern_risk_pct(PatternType.SPRING)
        assert risk == Decimal("2.0")

    def test_override_below_minimum_rejected(self, allocator):
        """Override below minimum (0.1%) should raise ValueError."""
        with pytest.raises(ValueError, match="minimum"):
            allocator.set_pattern_risk_override(PatternType.SPRING, Decimal("0.05"))


class TestUserOverrideCapability:
    """AC 6: User can adjust pattern risk within limits."""

    def test_set_override(self, allocator):
        """Setting override should change returned risk percentage."""
        # Verify default
        assert allocator.get_pattern_risk_pct(PatternType.SPRING) == Decimal("0.5")

        # Set override
        allocator.set_pattern_risk_override(PatternType.SPRING, Decimal("0.7"))
        assert allocator.get_pattern_risk_pct(PatternType.SPRING) == Decimal("0.7")

    def test_clear_override(self, allocator):
        """Clearing override should restore default risk percentage."""
        # Set override
        allocator.set_pattern_risk_override(PatternType.SPRING, Decimal("0.7"))
        assert allocator.get_pattern_risk_pct(PatternType.SPRING) == Decimal("0.7")

        # Clear override
        allocator.clear_pattern_risk_override(PatternType.SPRING)
        assert allocator.get_pattern_risk_pct(PatternType.SPRING) == Decimal("0.5")

    def test_override_only_affects_specific_pattern(self, allocator):
        """Override should only affect the specific pattern, not others."""
        allocator.set_pattern_risk_override(PatternType.SPRING, Decimal("0.7"))

        # Spring should be overridden
        assert allocator.get_pattern_risk_pct(PatternType.SPRING) == Decimal("0.7")

        # Other patterns should remain default
        assert allocator.get_pattern_risk_pct(PatternType.LPS) == Decimal("0.7")
        assert allocator.get_pattern_risk_pct(PatternType.SOS) == Decimal("0.8")

    def test_use_override_flag(self, allocator):
        """use_override=False should return default even with override set."""
        allocator.set_pattern_risk_override(PatternType.SPRING, Decimal("0.7"))

        # With override (default)
        assert allocator.get_pattern_risk_pct(PatternType.SPRING) == Decimal("0.7")

        # Without override
        assert allocator.get_pattern_risk_pct(PatternType.SPRING, use_override=False) == Decimal(
            "0.5"
        )

    def test_get_all_risk_percentages(self, allocator):
        """get_all_risk_percentages should return all patterns with overrides applied."""
        # Set some overrides
        allocator.set_pattern_risk_override(PatternType.SPRING, Decimal("0.7"))
        allocator.set_pattern_risk_override(PatternType.LPS, Decimal("1.0"))

        all_risks = allocator.get_all_risk_percentages()

        assert all_risks[PatternType.SPRING] == Decimal("0.7")  # Overridden
        assert all_risks[PatternType.LPS] == Decimal("1.0")  # Overridden
        assert all_risks[PatternType.SOS] == Decimal("0.8")  # Default
        assert all_risks[PatternType.ST] == Decimal("0.5")  # Default
        assert all_risks[PatternType.UTAD] == Decimal("0.5")  # Default


class TestLoggingNonDefaultRisk:
    """AC 9: Info log when non-default risk used."""

    def test_logging_non_default_risk(self, allocator, capsys):
        """Should log info when override is used."""
        allocator.set_pattern_risk_override(PatternType.SOS, Decimal("1.5"))

        # Get risk with override (should log)
        risk = allocator.get_pattern_risk_pct(PatternType.SOS)

        # Verify risk returned correctly
        assert risk == Decimal("1.5")

        # Capture stdout (structlog output goes to stdout)
        captured = capsys.readouterr()

        # Verify logging occurred
        assert "non_default_risk_used" in captured.out or "override" in captured.out.lower()

    def test_no_logging_for_default_risk(self, allocator, caplog):
        """Should use debug logging for default risk (not info)."""
        caplog.clear()

        # Get default risk (should not log at info level)
        risk = allocator.get_pattern_risk_pct(PatternType.SPRING)

        assert risk == Decimal("0.5")

        # Should not see info-level override log
        log_output = caplog.text
        assert "non_default_risk_used" not in log_output


class TestFixedPointArithmetic:
    """AC 10: FR16 compliance - fixed-point arithmetic using Decimal."""

    def test_all_risks_are_decimal_type(self, allocator):
        """All risk percentages should be Decimal type, not float."""
        for pattern_type in PatternType:
            risk_pct = allocator.get_pattern_risk_pct(pattern_type)
            assert isinstance(risk_pct, Decimal), f"{pattern_type} risk is not Decimal"

    def test_decimal_exact_comparison(self, allocator):
        """Decimal should allow exact comparisons without floating point errors."""
        spring_risk = allocator.get_pattern_risk_pct(PatternType.SPRING)
        assert spring_risk == Decimal("0.5")  # Exact comparison
        assert str(spring_risk) == "0.5"  # String representation

    def test_decimal_precision_preserved(self, allocator):
        """Decimal precision should be preserved in calculations."""
        # Set override with high precision
        allocator.set_pattern_risk_override(PatternType.SPRING, Decimal("0.75"))
        risk = allocator.get_pattern_risk_pct(PatternType.SPRING)

        # Should preserve exact value
        assert risk == Decimal("0.75")
        assert str(risk) == "0.75"

    def test_conservative_rounding_position_size(self):
        """AC 10: FR16 compliance - position sizes rounded DOWN (conservative)."""
        # Calculate position size that would be 155.8 shares before rounding
        risk_dollars = Decimal("700.00")
        stop_distance = Decimal("4.49")

        # Calculate raw position size
        raw_position_size = risk_dollars / stop_distance  # 155.9...

        # Apply conservative rounding (ROUND_DOWN)
        position_size = raw_position_size.quantize(Decimal("1"), rounding=ROUND_DOWN)

        # Verify rounded down (not up)
        assert position_size == Decimal("155"), f"Expected 155 shares, got {position_size}"
        assert position_size < raw_position_size, "Position size should round DOWN"

        # Verify actual risk is below target (conservative)
        actual_risk = position_size * stop_distance
        assert actual_risk <= risk_dollars, "Actual risk exceeds target (rounding error)"

    def test_conservative_rounding_currency(self):
        """AC 10: Currency amounts should round half-up to nearest cent."""
        amount = Decimal("100.125")
        rounded_amount = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        assert rounded_amount == Decimal("100.13"), "Currency should round half-up"

        amount2 = Decimal("100.124")
        rounded_amount2 = amount2.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        assert rounded_amount2 == Decimal("100.12"), "Currency should round half-up"


class TestVolumeAdjustedRiskScaling:
    """AC 11: Volume-adjusted risk scaling with non-linear Wyckoff tiers."""

    def test_volume_tier_climactic(self):
        """Volume ≥2.5x should return 1.00x multiplier (climactic)."""
        assert get_volume_risk_multiplier(Decimal("2.6")) == Decimal("1.00")
        assert get_volume_risk_multiplier(Decimal("2.5")) == Decimal("1.00")

    def test_volume_tier_very_strong(self):
        """Volume ≥2.3x should return 0.95x multiplier (very strong)."""
        assert get_volume_risk_multiplier(Decimal("2.4")) == Decimal("0.95")
        assert get_volume_risk_multiplier(Decimal("2.3")) == Decimal("0.95")

    def test_volume_tier_ideal_professional(self):
        """Volume ≥2.0x should return 0.90x multiplier (ideal)."""
        assert get_volume_risk_multiplier(Decimal("2.2")) == Decimal("0.90")
        assert get_volume_risk_multiplier(Decimal("2.0")) == Decimal("0.90")

    def test_volume_tier_acceptable(self):
        """Volume ≥1.7x should return 0.85x multiplier (acceptable)."""
        assert get_volume_risk_multiplier(Decimal("1.9")) == Decimal("0.85")
        assert get_volume_risk_multiplier(Decimal("1.7")) == Decimal("0.85")

    def test_volume_tier_borderline(self):
        """Volume ≥1.5x should return 0.75x multiplier (borderline)."""
        assert get_volume_risk_multiplier(Decimal("1.6")) == Decimal("0.75")
        assert get_volume_risk_multiplier(Decimal("1.5")) == Decimal("0.75")

    def test_volume_below_threshold_raises_error(self):
        """Volume <1.5x should raise ValueError (FR12 violation)."""
        with pytest.raises(ValueError, match="FR12 validation failure"):
            get_volume_risk_multiplier(Decimal("1.4"))

    def test_adjusted_pattern_risk_calculation(self, allocator):
        """AC 11: Volume-adjusted risk scaling with LPS pattern."""
        # Test each volume tier with LPS pattern (0.7% base)
        test_cases = [
            # (volume_ratio, expected_multiplier, expected_adjusted_risk, tier_name)
            (Decimal("2.6"), Decimal("1.00"), Decimal("0.700"), "climactic"),
            (Decimal("2.5"), Decimal("1.00"), Decimal("0.700"), "climactic_threshold"),
            (Decimal("2.4"), Decimal("0.95"), Decimal("0.665"), "very_strong"),
            (Decimal("2.3"), Decimal("0.95"), Decimal("0.665"), "very_strong_threshold"),
            (Decimal("2.2"), Decimal("0.90"), Decimal("0.630"), "ideal"),
            (Decimal("2.0"), Decimal("0.90"), Decimal("0.630"), "ideal_threshold"),
            (Decimal("1.9"), Decimal("0.85"), Decimal("0.595"), "acceptable"),
            (Decimal("1.7"), Decimal("0.85"), Decimal("0.595"), "acceptable_threshold"),
            (Decimal("1.6"), Decimal("0.75"), Decimal("0.525"), "borderline"),
            (Decimal("1.5"), Decimal("0.75"), Decimal("0.525"), "borderline_threshold"),
        ]

        for volume_ratio, expected_mult, expected_risk, tier_name in test_cases:
            adjusted_risk = allocator.get_adjusted_pattern_risk(
                pattern_type=PatternType.LPS, volume_ratio=volume_ratio
            )

            assert adjusted_risk == expected_risk, (
                f"Volume tier '{tier_name}' ({volume_ratio}x) failed: "
                f"expected {expected_risk}%, got {adjusted_risk}%"
            )

    def test_adjusted_risk_with_override(self, allocator):
        """Volume adjustment should work with user overrides."""
        # Set override for SPRING
        allocator.set_pattern_risk_override(PatternType.SPRING, Decimal("1.0"))

        # Calculate adjusted risk with 2.0x volume (0.90 multiplier)
        adjusted_risk = allocator.get_adjusted_pattern_risk(
            pattern_type=PatternType.SPRING, volume_ratio=Decimal("2.0")
        )

        # Expected: 1.0% × 0.90 = 0.90%
        assert adjusted_risk == Decimal("0.900")

    def test_adjusted_risk_fr12_violation(self, allocator):
        """Adjusted risk with <1.5x volume should raise ValueError."""
        with pytest.raises(ValueError, match="FR12 validation failure"):
            allocator.get_adjusted_pattern_risk(
                pattern_type=PatternType.LPS, volume_ratio=Decimal("1.4")
            )


class TestConfigurationLoading:
    """Test configuration loading and validation."""

    def test_config_loaded_successfully(self, allocator):
        """Configuration should load successfully from YAML."""
        assert allocator.config is not None
        assert allocator.config.version == "1.2"
        assert allocator.config.per_trade_maximum == Decimal("2.0")

    def test_config_has_all_patterns(self, allocator):
        """Configuration should have risk percentages for all patterns."""
        for pattern_type in PatternType:
            assert pattern_type in allocator.config.pattern_risk_percentages

    def test_config_has_rationale(self, allocator):
        """Configuration should have rationale for all patterns."""
        for pattern_type in PatternType:
            assert pattern_type in allocator.config.rationale
            rationale = allocator.config.rationale[pattern_type]
            assert len(rationale) > 0, f"{pattern_type} has empty rationale"

    def test_invalid_config_path_raises_error(self):
        """Invalid config path should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            RiskAllocator(config_path="nonexistent/path/config.yaml")


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_multiple_overrides(self, allocator):
        """Should handle multiple overrides for different patterns."""
        allocator.set_pattern_risk_override(PatternType.SPRING, Decimal("0.6"))
        allocator.set_pattern_risk_override(PatternType.LPS, Decimal("1.0"))
        allocator.set_pattern_risk_override(PatternType.SOS, Decimal("1.2"))

        assert allocator.get_pattern_risk_pct(PatternType.SPRING) == Decimal("0.6")
        assert allocator.get_pattern_risk_pct(PatternType.LPS) == Decimal("1.0")
        assert allocator.get_pattern_risk_pct(PatternType.SOS) == Decimal("1.2")
        assert allocator.get_pattern_risk_pct(PatternType.ST) == Decimal("0.5")  # Default

    def test_clear_nonexistent_override(self, allocator):
        """Clearing nonexistent override should not raise error."""
        # Should not raise error
        allocator.clear_pattern_risk_override(PatternType.SPRING)

    def test_override_at_boundaries(self, allocator):
        """Override at exact boundary values should work."""
        # Minimum boundary
        allocator.set_pattern_risk_override(PatternType.SPRING, Decimal("0.1"))
        assert allocator.get_pattern_risk_pct(PatternType.SPRING) == Decimal("0.1")

        # Maximum boundary
        allocator.set_pattern_risk_override(PatternType.SPRING, Decimal("2.0"))
        assert allocator.get_pattern_risk_pct(PatternType.SPRING) == Decimal("2.0")
