"""
Unit tests for CampaignRiskMetadata model - Story 22.10

Tests the risk-related metadata functionality including validation,
position sizing, and risk/reward calculations.
"""

from decimal import Decimal

import pytest

from src.models.campaign_risk import CampaignRiskMetadata


class TestCampaignRiskMetadataCreation:
    """Test CampaignRiskMetadata instantiation."""

    def test_default_creation(self):
        """Test creating with defaults."""
        risk = CampaignRiskMetadata()

        assert risk.support_level is None
        assert risk.resistance_level is None
        assert risk.risk_per_share is None
        assert risk.stop_loss_price is None
        assert risk.initial_target is None
        assert risk.jump_level is None
        assert risk.position_size == Decimal("0")
        assert risk.dollar_risk == Decimal("0")
        assert risk.account_risk_pct == 0.0
        assert risk.strength_score == 0.0

    def test_custom_creation(self):
        """Test creating with custom values."""
        risk = CampaignRiskMetadata(
            support_level=Decimal("145.00"),
            resistance_level=Decimal("160.00"),
            risk_per_share=Decimal("5.00"),
            stop_loss_price=Decimal("143.00"),
            initial_target=Decimal("175.00"),
        )

        assert risk.support_level == Decimal("145.00")
        assert risk.resistance_level == Decimal("160.00")
        assert risk.risk_per_share == Decimal("5.00")
        assert risk.stop_loss_price == Decimal("143.00")
        assert risk.initial_target == Decimal("175.00")


class TestRiskRewardCalculation:
    """Test calculate_risk_reward method."""

    def test_risk_reward_calculation(self):
        """Test basic risk/reward calculation."""
        risk = CampaignRiskMetadata(
            initial_target=Decimal("175.00"),
            stop_loss_price=Decimal("145.00"),
            risk_per_share=Decimal("5.00"),
        )

        rr = risk.calculate_risk_reward()

        # Reward = 175 - 145 = 30, Risk = 5
        # R:R = 30 / 5 = 6.0
        assert rr == Decimal("6.0")

    def test_risk_reward_missing_target(self):
        """Test risk/reward with missing target."""
        risk = CampaignRiskMetadata(
            stop_loss_price=Decimal("145.00"),
            risk_per_share=Decimal("5.00"),
        )

        assert risk.calculate_risk_reward() is None

    def test_risk_reward_missing_stop_loss(self):
        """Test risk/reward with missing stop loss."""
        risk = CampaignRiskMetadata(
            initial_target=Decimal("175.00"),
            risk_per_share=Decimal("5.00"),
        )

        assert risk.calculate_risk_reward() is None

    def test_risk_reward_zero_risk(self):
        """Test risk/reward with zero risk per share."""
        risk = CampaignRiskMetadata(
            initial_target=Decimal("175.00"),
            stop_loss_price=Decimal("145.00"),
            risk_per_share=Decimal("0"),
        )

        assert risk.calculate_risk_reward() is None


class TestRangeWidthCalculation:
    """Test calculate_range_width method."""

    def test_range_width_calculation(self):
        """Test basic range width calculation."""
        risk = CampaignRiskMetadata(
            support_level=Decimal("100.00"),
            resistance_level=Decimal("110.00"),
        )

        width = risk.calculate_range_width()

        # (110 - 100) / 100 * 100 = 10%
        assert width == Decimal("10.00")

    def test_range_width_missing_support(self):
        """Test range width with missing support."""
        risk = CampaignRiskMetadata(
            resistance_level=Decimal("110.00"),
        )

        assert risk.calculate_range_width() is None

    def test_range_width_missing_resistance(self):
        """Test range width with missing resistance."""
        risk = CampaignRiskMetadata(
            support_level=Decimal("100.00"),
        )

        assert risk.calculate_range_width() is None

    def test_range_width_zero_support(self):
        """Test range width with zero support."""
        risk = CampaignRiskMetadata(
            support_level=Decimal("0"),
            resistance_level=Decimal("110.00"),
        )

        assert risk.calculate_range_width() is None


class TestRiskValidation:
    """Test validate and is_valid methods."""

    def test_valid_risk_parameters(self):
        """Test validation with valid parameters."""
        risk = CampaignRiskMetadata(
            support_level=Decimal("100.00"),
            resistance_level=Decimal("110.00"),
            risk_per_share=Decimal("5.00"),
            dollar_risk=Decimal("500.00"),
            account_risk_pct=1.5,
        )

        valid, errors = risk.validate()

        assert valid is True
        assert len(errors) == 0
        assert risk.is_valid() is True

    def test_invalid_support_above_resistance(self):
        """Test validation fails when support >= resistance."""
        risk = CampaignRiskMetadata(
            support_level=Decimal("120.00"),
            resistance_level=Decimal("110.00"),
        )

        valid, errors = risk.validate()

        assert valid is False
        assert len(errors) == 1
        assert "Support level" in errors[0]
        assert risk.is_valid() is False

    def test_invalid_zero_risk_per_share(self):
        """Test validation fails with zero risk_per_share."""
        risk = CampaignRiskMetadata(
            risk_per_share=Decimal("0"),
        )

        valid, errors = risk.validate()

        assert valid is False
        assert any("Risk per share" in e for e in errors)

    def test_invalid_negative_risk_per_share(self):
        """Test validation fails with negative risk_per_share."""
        risk = CampaignRiskMetadata(
            risk_per_share=Decimal("-5.00"),
        )

        valid, errors = risk.validate()

        assert valid is False
        assert any("Risk per share" in e for e in errors)

    def test_invalid_negative_dollar_risk(self):
        """Test validation fails with negative dollar_risk."""
        risk = CampaignRiskMetadata(
            dollar_risk=Decimal("-500.00"),
        )

        valid, errors = risk.validate()

        assert valid is False
        assert any("Dollar risk" in e for e in errors)

    def test_invalid_account_risk_exceeds_limit(self):
        """Test validation fails when account risk > 2%."""
        risk = CampaignRiskMetadata(
            account_risk_pct=2.5,
        )

        valid, errors = risk.validate()

        assert valid is False
        assert any("Account risk percentage" in e for e in errors)

    def test_multiple_validation_errors(self):
        """Test validation collects multiple errors."""
        risk = CampaignRiskMetadata(
            support_level=Decimal("120.00"),
            resistance_level=Decimal("110.00"),
            risk_per_share=Decimal("-5.00"),
            account_risk_pct=3.0,
        )

        valid, errors = risk.validate()

        assert valid is False
        assert len(errors) >= 3


class TestPositionSizeCalculation:
    """Test calculate_position_size method."""

    def test_position_size_calculation(self):
        """Test basic position size calculation."""
        risk = CampaignRiskMetadata(
            risk_per_share=Decimal("5.00"),
        )

        size = risk.calculate_position_size(
            account_size=Decimal("100000"),
            risk_pct=Decimal("2.0"),
        )

        # $100,000 * 2% / $5.00 = 400 shares
        assert size == Decimal("400")

    def test_position_size_rounds_to_whole_shares(self):
        """Test position size rounds to whole shares."""
        risk = CampaignRiskMetadata(
            risk_per_share=Decimal("3.00"),
        )

        size = risk.calculate_position_size(
            account_size=Decimal("100000"),
            risk_pct=Decimal("1.0"),
        )

        # $100,000 * 1% / $3.00 = 333.33 -> 333 shares
        assert size == Decimal("333")

    def test_position_size_exceeds_risk_limit(self):
        """Test position size raises error when risk > 2%."""
        risk = CampaignRiskMetadata(
            risk_per_share=Decimal("5.00"),
        )

        with pytest.raises(ValueError, match="2.0% hard limit"):
            risk.calculate_position_size(
                account_size=Decimal("100000"),
                risk_pct=Decimal("2.5"),
            )

    def test_position_size_zero_risk_per_share(self):
        """Test position size with zero risk_per_share."""
        risk = CampaignRiskMetadata(
            risk_per_share=Decimal("0"),
        )

        size = risk.calculate_position_size(
            account_size=Decimal("100000"),
            risk_pct=Decimal("2.0"),
        )

        assert size == Decimal("0")

    def test_position_size_no_risk_per_share(self):
        """Test position size with None risk_per_share."""
        risk = CampaignRiskMetadata()

        size = risk.calculate_position_size(
            account_size=Decimal("100000"),
            risk_pct=Decimal("2.0"),
        )

        assert size == Decimal("0")

    def test_position_size_zero_account(self):
        """Test position size with zero account."""
        risk = CampaignRiskMetadata(
            risk_per_share=Decimal("5.00"),
        )

        size = risk.calculate_position_size(
            account_size=Decimal("0"),
            risk_pct=Decimal("2.0"),
        )

        assert size == Decimal("0")


class TestATRTracking:
    """Test update_atr method."""

    def test_update_atr_initial(self):
        """Test initial ATR update sets entry_atr."""
        risk = CampaignRiskMetadata()

        risk.update_atr(Decimal("2.50"))

        assert risk.entry_atr == Decimal("2.50")
        assert risk.max_atr_seen == Decimal("2.50")

    def test_update_atr_higher(self):
        """Test ATR update with higher value."""
        risk = CampaignRiskMetadata()
        risk.update_atr(Decimal("2.50"))
        risk.update_atr(Decimal("3.00"))

        assert risk.entry_atr == Decimal("2.50")  # Unchanged
        assert risk.max_atr_seen == Decimal("3.00")  # Updated

    def test_update_atr_lower(self):
        """Test ATR update with lower value doesn't change max."""
        risk = CampaignRiskMetadata()
        risk.update_atr(Decimal("3.00"))
        risk.update_atr(Decimal("2.50"))

        assert risk.entry_atr == Decimal("3.00")  # Unchanged
        assert risk.max_atr_seen == Decimal("3.00")  # Unchanged
