"""
Unit tests for Spring package models.

Tests SpringCandidate and SpringRiskProfile data classes
with full validation coverage.

Coverage Target: 95%+
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from src.models.ohlcv import OHLCVBar
from src.pattern_engine.detectors.spring import SpringCandidate, SpringRiskProfile

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_bar():
    """Create a sample OHLCV bar for testing."""
    return OHLCVBar(
        symbol="AAPL",
        timestamp=datetime(2024, 1, 15, 14, 30, tzinfo=UTC),
        open=Decimal("100.00"),
        high=Decimal("101.00"),
        low=Decimal("98.00"),
        close=Decimal("100.50"),
        volume=150000,
        spread=Decimal("3.00"),
        timeframe="1d",
    )


@pytest.fixture
def valid_candidate(sample_bar):
    """Create a valid SpringCandidate instance."""
    return SpringCandidate(
        bar_index=25,
        bar=sample_bar,
        penetration_pct=Decimal("0.02"),
        recovery_pct=Decimal("0.015"),
        creek_level=Decimal("100.00"),
    )


@pytest.fixture
def valid_risk_profile():
    """Create a valid SpringRiskProfile instance."""
    return SpringRiskProfile(
        stop_loss=Decimal("97.50"),
        initial_target=Decimal("105.00"),
        risk_reward_ratio=Decimal("2.5"),
    )


# =============================================================================
# SpringCandidate Tests
# =============================================================================


class TestSpringCandidateCreation:
    """Test SpringCandidate instantiation."""

    def test_valid_candidate_creation(self, sample_bar):
        """Test creating a valid SpringCandidate."""
        candidate = SpringCandidate(
            bar_index=25,
            bar=sample_bar,
            penetration_pct=Decimal("0.02"),
            recovery_pct=Decimal("0.015"),
            creek_level=Decimal("100.00"),
        )

        assert candidate.bar_index == 25
        assert candidate.bar == sample_bar
        assert candidate.penetration_pct == Decimal("0.02")
        assert candidate.recovery_pct == Decimal("0.015")
        assert candidate.creek_level == Decimal("100.00")

    def test_candidate_zero_penetration(self, sample_bar):
        """Test candidate with zero penetration (valid edge case)."""
        candidate = SpringCandidate(
            bar_index=10,
            bar=sample_bar,
            penetration_pct=Decimal("0"),
            recovery_pct=Decimal("0.01"),
            creek_level=Decimal("95.00"),
        )

        assert candidate.penetration_pct == Decimal("0")

    def test_candidate_max_penetration(self, sample_bar):
        """Test candidate with maximum 5% penetration."""
        candidate = SpringCandidate(
            bar_index=10,
            bar=sample_bar,
            penetration_pct=Decimal("0.05"),
            recovery_pct=Decimal("0.01"),
            creek_level=Decimal("95.00"),
        )

        assert candidate.penetration_pct == Decimal("0.05")


class TestSpringCandidateValidation:
    """Test SpringCandidate validation logic."""

    def test_negative_bar_index_raises(self, sample_bar):
        """Test that negative bar_index raises ValueError."""
        with pytest.raises(ValueError, match="bar_index must be >= 0"):
            SpringCandidate(
                bar_index=-1,
                bar=sample_bar,
                penetration_pct=Decimal("0.02"),
                recovery_pct=Decimal("0.015"),
                creek_level=Decimal("100.00"),
            )

    def test_negative_penetration_raises(self, sample_bar):
        """Test that negative penetration_pct raises ValueError."""
        with pytest.raises(ValueError, match="penetration_pct must be >= 0"):
            SpringCandidate(
                bar_index=25,
                bar=sample_bar,
                penetration_pct=Decimal("-0.01"),
                recovery_pct=Decimal("0.015"),
                creek_level=Decimal("100.00"),
            )

    def test_excessive_penetration_raises(self, sample_bar):
        """Test that penetration > 5% raises ValueError (indicates breakdown)."""
        with pytest.raises(ValueError, match="penetration_pct exceeds 5% maximum"):
            SpringCandidate(
                bar_index=25,
                bar=sample_bar,
                penetration_pct=Decimal("0.06"),
                recovery_pct=Decimal("0.015"),
                creek_level=Decimal("100.00"),
            )

    def test_zero_recovery_raises(self, sample_bar):
        """Test that zero recovery_pct raises ValueError."""
        with pytest.raises(ValueError, match="recovery_pct must be > 0"):
            SpringCandidate(
                bar_index=25,
                bar=sample_bar,
                penetration_pct=Decimal("0.02"),
                recovery_pct=Decimal("0"),
                creek_level=Decimal("100.00"),
            )

    def test_negative_recovery_raises(self, sample_bar):
        """Test that negative recovery_pct raises ValueError."""
        with pytest.raises(ValueError, match="recovery_pct must be > 0"):
            SpringCandidate(
                bar_index=25,
                bar=sample_bar,
                penetration_pct=Decimal("0.02"),
                recovery_pct=Decimal("-0.01"),
                creek_level=Decimal("100.00"),
            )

    def test_zero_creek_level_raises(self, sample_bar):
        """Test that zero creek_level raises ValueError."""
        with pytest.raises(ValueError, match="creek_level must be > 0"):
            SpringCandidate(
                bar_index=25,
                bar=sample_bar,
                penetration_pct=Decimal("0.02"),
                recovery_pct=Decimal("0.015"),
                creek_level=Decimal("0"),
            )

    def test_negative_creek_level_raises(self, sample_bar):
        """Test that negative creek_level raises ValueError."""
        with pytest.raises(ValueError, match="creek_level must be > 0"):
            SpringCandidate(
                bar_index=25,
                bar=sample_bar,
                penetration_pct=Decimal("0.02"),
                recovery_pct=Decimal("0.015"),
                creek_level=Decimal("-100.00"),
            )


class TestSpringCandidateProperties:
    """Test SpringCandidate computed properties."""

    def test_is_ideal_penetration_in_range(self, sample_bar):
        """Test is_ideal_penetration returns True for 1-2% range."""
        candidate = SpringCandidate(
            bar_index=25,
            bar=sample_bar,
            penetration_pct=Decimal("0.015"),  # 1.5%
            recovery_pct=Decimal("0.01"),
            creek_level=Decimal("100.00"),
        )

        assert candidate.is_ideal_penetration is True

    def test_is_ideal_penetration_at_lower_bound(self, sample_bar):
        """Test is_ideal_penetration at exactly 1%."""
        candidate = SpringCandidate(
            bar_index=25,
            bar=sample_bar,
            penetration_pct=Decimal("0.01"),  # Exactly 1%
            recovery_pct=Decimal("0.01"),
            creek_level=Decimal("100.00"),
        )

        assert candidate.is_ideal_penetration is True

    def test_is_ideal_penetration_at_upper_bound(self, sample_bar):
        """Test is_ideal_penetration at exactly 2%."""
        candidate = SpringCandidate(
            bar_index=25,
            bar=sample_bar,
            penetration_pct=Decimal("0.02"),  # Exactly 2%
            recovery_pct=Decimal("0.01"),
            creek_level=Decimal("100.00"),
        )

        assert candidate.is_ideal_penetration is True

    def test_is_ideal_penetration_below_range(self, sample_bar):
        """Test is_ideal_penetration returns False below 1%."""
        candidate = SpringCandidate(
            bar_index=25,
            bar=sample_bar,
            penetration_pct=Decimal("0.005"),  # 0.5%
            recovery_pct=Decimal("0.01"),
            creek_level=Decimal("100.00"),
        )

        assert candidate.is_ideal_penetration is False

    def test_is_ideal_penetration_above_range(self, sample_bar):
        """Test is_ideal_penetration returns False above 2%."""
        candidate = SpringCandidate(
            bar_index=25,
            bar=sample_bar,
            penetration_pct=Decimal("0.03"),  # 3%
            recovery_pct=Decimal("0.01"),
            creek_level=Decimal("100.00"),
        )

        assert candidate.is_ideal_penetration is False


# =============================================================================
# SpringRiskProfile Tests
# =============================================================================


class TestSpringRiskProfileCreation:
    """Test SpringRiskProfile instantiation."""

    def test_valid_risk_profile_creation(self):
        """Test creating a valid SpringRiskProfile."""
        profile = SpringRiskProfile(
            stop_loss=Decimal("97.50"),
            initial_target=Decimal("105.00"),
            risk_reward_ratio=Decimal("2.5"),
        )

        assert profile.stop_loss == Decimal("97.50")
        assert profile.initial_target == Decimal("105.00")
        assert profile.risk_reward_ratio == Decimal("2.5")

    def test_minimal_risk_profile(self):
        """Test risk profile with minimal valid values."""
        profile = SpringRiskProfile(
            stop_loss=Decimal("0.01"),
            initial_target=Decimal("0.02"),
            risk_reward_ratio=Decimal("0.01"),
        )

        assert profile.stop_loss == Decimal("0.01")
        assert profile.initial_target == Decimal("0.02")


class TestSpringRiskProfileValidation:
    """Test SpringRiskProfile validation logic."""

    def test_zero_stop_loss_raises(self):
        """Test that zero stop_loss raises ValueError."""
        with pytest.raises(ValueError, match="stop_loss must be > 0"):
            SpringRiskProfile(
                stop_loss=Decimal("0"),
                initial_target=Decimal("105.00"),
                risk_reward_ratio=Decimal("2.5"),
            )

    def test_negative_stop_loss_raises(self):
        """Test that negative stop_loss raises ValueError."""
        with pytest.raises(ValueError, match="stop_loss must be > 0"):
            SpringRiskProfile(
                stop_loss=Decimal("-10.00"),
                initial_target=Decimal("105.00"),
                risk_reward_ratio=Decimal("2.5"),
            )

    def test_zero_initial_target_raises(self):
        """Test that zero initial_target raises ValueError."""
        with pytest.raises(ValueError, match="initial_target must be > 0"):
            SpringRiskProfile(
                stop_loss=Decimal("97.50"),
                initial_target=Decimal("0"),
                risk_reward_ratio=Decimal("2.5"),
            )

    def test_negative_initial_target_raises(self):
        """Test that negative initial_target raises ValueError."""
        with pytest.raises(ValueError, match="initial_target must be > 0"):
            SpringRiskProfile(
                stop_loss=Decimal("97.50"),
                initial_target=Decimal("-105.00"),
                risk_reward_ratio=Decimal("2.5"),
            )

    def test_target_less_than_stop_raises(self):
        """Test that initial_target <= stop_loss raises ValueError."""
        with pytest.raises(ValueError, match="initial_target .* must be > stop_loss"):
            SpringRiskProfile(
                stop_loss=Decimal("100.00"),
                initial_target=Decimal("95.00"),
                risk_reward_ratio=Decimal("2.5"),
            )

    def test_target_equal_to_stop_raises(self):
        """Test that initial_target == stop_loss raises ValueError."""
        with pytest.raises(ValueError, match="initial_target .* must be > stop_loss"):
            SpringRiskProfile(
                stop_loss=Decimal("100.00"),
                initial_target=Decimal("100.00"),
                risk_reward_ratio=Decimal("2.5"),
            )

    def test_zero_risk_reward_raises(self):
        """Test that zero risk_reward_ratio raises ValueError."""
        with pytest.raises(ValueError, match="risk_reward_ratio must be > 0"):
            SpringRiskProfile(
                stop_loss=Decimal("97.50"),
                initial_target=Decimal("105.00"),
                risk_reward_ratio=Decimal("0"),
            )

    def test_negative_risk_reward_raises(self):
        """Test that negative risk_reward_ratio raises ValueError."""
        with pytest.raises(ValueError, match="risk_reward_ratio must be > 0"):
            SpringRiskProfile(
                stop_loss=Decimal("97.50"),
                initial_target=Decimal("105.00"),
                risk_reward_ratio=Decimal("-2.5"),
            )


class TestSpringRiskProfileProperties:
    """Test SpringRiskProfile computed properties."""

    def test_is_favorable_above_threshold(self):
        """Test is_favorable returns True for R:R >= 1.5."""
        profile = SpringRiskProfile(
            stop_loss=Decimal("97.50"),
            initial_target=Decimal("105.00"),
            risk_reward_ratio=Decimal("2.5"),
        )

        assert profile.is_favorable is True

    def test_is_favorable_at_threshold(self):
        """Test is_favorable returns True at exactly 1.5."""
        profile = SpringRiskProfile(
            stop_loss=Decimal("97.50"),
            initial_target=Decimal("105.00"),
            risk_reward_ratio=Decimal("1.5"),
        )

        assert profile.is_favorable is True

    def test_is_favorable_below_threshold(self):
        """Test is_favorable returns False for R:R < 1.5."""
        profile = SpringRiskProfile(
            stop_loss=Decimal("97.50"),
            initial_target=Decimal("105.00"),
            risk_reward_ratio=Decimal("1.2"),
        )

        assert profile.is_favorable is False

    def test_risk_amount_calculation(self):
        """Test risk_amount property calculation."""
        profile = SpringRiskProfile(
            stop_loss=Decimal("97.50"),
            initial_target=Decimal("105.00"),
            risk_reward_ratio=Decimal("2.5"),
        )

        # risk_amount = initial_target - stop_loss
        expected = Decimal("105.00") - Decimal("97.50")
        assert profile.risk_amount == expected
        assert profile.risk_amount == Decimal("7.50")


# =============================================================================
# Package Export Tests
# =============================================================================


class TestPackageExports:
    """Test that models are correctly exported from package."""

    def test_spring_candidate_import(self):
        """Test SpringCandidate can be imported from package."""
        from src.pattern_engine.detectors.spring import SpringCandidate

        assert SpringCandidate is not None

    def test_spring_risk_profile_import(self):
        """Test SpringRiskProfile can be imported from package."""
        from src.pattern_engine.detectors.spring import SpringRiskProfile

        assert SpringRiskProfile is not None

    def test_all_exports(self):
        """Test __all__ exports are correct."""
        from src.pattern_engine.detectors import spring

        assert hasattr(spring, "__all__")
        assert "SpringCandidate" in spring.__all__
        assert "SpringRiskProfile" in spring.__all__


# =============================================================================
# Edge Cases and Integration
# =============================================================================


class TestEdgeCases:
    """Test edge cases and unusual inputs."""

    def test_candidate_with_large_creek_level(self, sample_bar):
        """Test candidate with large creek level (forex rates)."""
        candidate = SpringCandidate(
            bar_index=0,  # First bar
            bar=sample_bar,
            penetration_pct=Decimal("0.001"),  # 0.1%
            recovery_pct=Decimal("0.0001"),
            creek_level=Decimal("1.23456789"),  # Forex precision
        )

        assert candidate.creek_level == Decimal("1.23456789")

    def test_candidate_bar_index_zero(self, sample_bar):
        """Test candidate at bar index 0."""
        candidate = SpringCandidate(
            bar_index=0,
            bar=sample_bar,
            penetration_pct=Decimal("0.02"),
            recovery_pct=Decimal("0.01"),
            creek_level=Decimal("100.00"),
        )

        assert candidate.bar_index == 0

    def test_risk_profile_very_small_values(self):
        """Test risk profile with very small decimal values."""
        profile = SpringRiskProfile(
            stop_loss=Decimal("0.00001"),
            initial_target=Decimal("0.00002"),
            risk_reward_ratio=Decimal("0.00001"),
        )

        assert profile.stop_loss == Decimal("0.00001")

    def test_risk_profile_large_values(self):
        """Test risk profile with large values (crypto)."""
        profile = SpringRiskProfile(
            stop_loss=Decimal("50000.00"),
            initial_target=Decimal("75000.00"),
            risk_reward_ratio=Decimal("2.0"),
        )

        assert profile.initial_target == Decimal("75000.00")
        assert profile.risk_amount == Decimal("25000.00")
