"""
Unit tests for Portfolio Heat Calculation (Story 14.3)

Tests cover all acceptance criteria for Story 14.3:
- Position sizing calculation
- Portfolio heat calculation
- Heat limit enforcement
- Multi-campaign risk management
- Input validation (2.0% risk limit, negative values, extreme values)

Test Categories:
1. Position Sizing Tests (4 tests)
2. Heat Calculation Tests (3 tests)
3. Heat Limit Enforcement Tests (3 tests)
4. Edge Cases and Validation (10 tests)

Total: 20 comprehensive test cases
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from src.backtesting.intraday_campaign_detector import (
    IntradayCampaignDetector,
    calculate_position_size,
)
from src.models.ohlcv import OHLCVBar
from src.models.spring import Spring

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def detector():
    """Standard detector with default configuration."""
    return IntradayCampaignDetector(
        campaign_window_hours=48,
        max_pattern_gap_hours=48,
        min_patterns_for_active=2,
        expiration_hours=72,
        max_concurrent_campaigns=3,
        max_portfolio_heat_pct=Decimal("10.0"),
    )


@pytest.fixture
def base_timestamp():
    """Base timestamp for test patterns."""
    return datetime(2025, 12, 15, 9, 0, tzinfo=UTC)


@pytest.fixture
def sample_bar(base_timestamp):
    """Sample OHLCV bar for pattern creation."""
    return OHLCVBar(
        timestamp=base_timestamp,
        open=Decimal("100.00"),
        high=Decimal("101.00"),
        low=Decimal("99.00"),
        close=Decimal("100.50"),
        volume=100000,
        spread=Decimal("2.00"),
        timeframe="15m",
        symbol="EUR/USD",
    )


@pytest.fixture
def sample_spring(sample_bar, base_timestamp):
    """Sample Spring pattern with calculated risk."""
    return Spring(
        bar=sample_bar,
        bar_index=0,
        penetration_pct=Decimal("0.02"),
        volume_ratio=Decimal("0.4"),
        recovery_bars=1,
        creek_reference=Decimal("100.00"),
        spring_low=Decimal("98.00"),
        recovery_price=Decimal("103.00"),  # risk_per_share will be 103 - 98 = 5.00
        detection_timestamp=base_timestamp,
        trading_range_id=uuid4(),
    )


# ============================================================================
# Position Sizing Tests
# ============================================================================


class TestPositionSizing:
    """Test position sizing calculations."""

    def test_calculate_position_size_valid(self):
        """Test position sizing with valid inputs."""
        position_size = calculate_position_size(
            account_size=Decimal("100000"),
            risk_pct_per_trade=Decimal("2.0"),
            risk_per_share=Decimal("5.00"),
        )
        # $100,000 × 2% / $5.00 = 400 shares
        assert position_size == Decimal("400")

    def test_calculate_position_size_zero_risk(self):
        """Test position sizing with zero risk_per_share."""
        position_size = calculate_position_size(
            account_size=Decimal("100000"),
            risk_pct_per_trade=Decimal("2.0"),
            risk_per_share=Decimal("0"),
        )
        assert position_size == Decimal("0")

    def test_calculate_position_size_zero_account(self):
        """Test position sizing with zero account_size."""
        position_size = calculate_position_size(
            account_size=Decimal("0"),
            risk_pct_per_trade=Decimal("2.0"),
            risk_per_share=Decimal("5.00"),
        )
        assert position_size == Decimal("0")

    def test_calculate_position_size_fractional_shares(self):
        """Test that position size rounds to whole shares."""
        position_size = calculate_position_size(
            account_size=Decimal("100000"),
            risk_pct_per_trade=Decimal("2.0"),
            risk_per_share=Decimal("4.99"),  # Would give 400.8016... shares
        )
        # Should round to whole shares using Decimal.quantize() which uses ROUND_HALF_EVEN by default
        # 400.8016... → 401 (rounds to nearest integer)
        assert position_size == Decimal("401")


# ============================================================================
# Heat Calculation Tests
# ============================================================================


class TestHeatCalculation:
    """Test portfolio heat calculation."""

    def test_single_campaign_heat_calculation(self, detector, sample_spring):
        """Test heat calculation with single campaign."""
        account_size = Decimal("100000")

        campaign = detector.add_pattern(
            sample_spring, account_size=account_size, risk_pct_per_trade=Decimal("2.0")
        )

        assert campaign is not None
        assert campaign.position_size > Decimal("0")
        assert campaign.dollar_risk > Decimal("0")

        # Check heat calculation
        heat = detector._calculate_portfolio_heat(account_size)
        assert heat > Decimal("0")
        assert heat <= Decimal("3")  # Should be ~2%

    def test_multiple_campaigns_heat_accumulation(
        self, detector, sample_spring, sample_bar, base_timestamp
    ):
        """Test that heat accumulates across multiple campaigns."""
        account_size = Decimal("100000")

        # Campaign 1
        spring1 = Spring(
            bar=sample_bar,
            bar_index=0,
            penetration_pct=Decimal("0.02"),
            volume_ratio=Decimal("0.4"),
            recovery_bars=1,
            creek_reference=Decimal("100.00"),
            spring_low=Decimal("98.00"),
            recovery_price=Decimal("103.00"),
            detection_timestamp=base_timestamp,
            trading_range_id=uuid4(),
        )

        campaign1 = detector.add_pattern(
            spring1, account_size=account_size, risk_pct_per_trade=Decimal("2.0")
        )
        assert campaign1 is not None
        heat1 = detector._calculate_portfolio_heat(account_size)

        # Campaign 2 (different timeframe for new campaign)
        spring2 = Spring(
            bar=sample_bar,
            bar_index=0,
            penetration_pct=Decimal("0.02"),
            volume_ratio=Decimal("0.4"),
            recovery_bars=1,
            creek_reference=Decimal("100.00"),
            spring_low=Decimal("98.00"),
            recovery_price=Decimal("103.00"),
            detection_timestamp=base_timestamp + timedelta(hours=60),
            trading_range_id=uuid4(),
        )

        campaign2 = detector.add_pattern(
            spring2, account_size=account_size, risk_pct_per_trade=Decimal("1.5")
        )
        assert campaign2 is not None
        heat2 = detector._calculate_portfolio_heat(account_size)

        # Heat should have increased
        assert heat2 > heat1

    def test_heat_calculation_zero_account_size(self, detector):
        """Test heat calculation with zero account size."""
        heat = detector._calculate_portfolio_heat(Decimal("0"))
        assert heat == Decimal("0")


# ============================================================================
# Heat Limit Enforcement Tests
# ============================================================================


class TestHeatLimitEnforcement:
    """Test portfolio heat limit enforcement."""

    def test_campaign_allowed_within_heat_limit(self, detector, sample_spring):
        """Test that campaign is allowed when within heat limits."""
        account_size = Decimal("100000")

        campaign = detector.add_pattern(
            sample_spring, account_size=account_size, risk_pct_per_trade=Decimal("2.0")
        )

        assert campaign is not None
        heat = detector._calculate_portfolio_heat(account_size)
        assert heat < Decimal("10")  # Well under 10% limit

    def test_campaign_rejected_exceeds_heat_limit(
        self, detector, sample_spring, sample_bar, base_timestamp
    ):
        """Test that campaign is rejected when heat would exceed limit."""
        detector.max_portfolio_heat_pct = Decimal("10.0")
        detector.max_concurrent_campaigns = 10  # Set high to test heat limit, not concurrent limit
        detector.expiration_hours = 300  # Increase to prevent campaign expiration during test
        account_size = Decimal("100000")

        # Create 5 campaigns with 2% risk each = 10% total heat
        # Use 50-hour spacing to create separate campaigns (> 48h window to avoid grouping)
        campaigns = []
        for i in range(5):
            spring = Spring(
                bar=sample_bar,
                bar_index=0,
                penetration_pct=Decimal("0.02"),
                volume_ratio=Decimal("0.4"),
                recovery_bars=1,
                creek_reference=Decimal("100.00"),
                spring_low=Decimal("98.00"),
                recovery_price=Decimal("103.00"),
                detection_timestamp=base_timestamp + timedelta(hours=50 * i),
                trading_range_id=uuid4(),
            )

            campaign = detector.add_pattern(
                spring, account_size=account_size, risk_pct_per_trade=Decimal("2.0")
            )
            campaigns.append(campaign)

        # First 5 campaigns should succeed (2% each = 10% total)
        assert all(c is not None for c in campaigns[:5])

        # 6th campaign should be rejected (would make 12% > 10% limit)
        spring_extra = Spring(
            bar=sample_bar,
            bar_index=0,
            penetration_pct=Decimal("0.02"),
            volume_ratio=Decimal("0.4"),
            recovery_bars=1,
            creek_reference=Decimal("100.00"),
            spring_low=Decimal("98.00"),
            recovery_price=Decimal("103.00"),
            detection_timestamp=base_timestamp + timedelta(hours=250),  # 250 hours from base
            trading_range_id=uuid4(),
        )

        campaign_extra = detector.add_pattern(
            spring_extra, account_size=account_size, risk_pct_per_trade=Decimal("2.0")
        )

        # Should be rejected
        assert campaign_extra is None

        # Heat should be at 10%
        heat = detector._calculate_portfolio_heat(account_size)
        assert heat <= Decimal("10")

    def test_campaign_metadata_dollar_risk_calculation(self, detector, sample_spring):
        """Test that dollar_risk is calculated correctly in metadata."""
        account_size = Decimal("100000")

        campaign = detector.add_pattern(
            sample_spring, account_size=account_size, risk_pct_per_trade=Decimal("2.0")
        )

        assert campaign is not None
        assert campaign.risk_per_share is not None
        assert campaign.risk_per_share > Decimal("0")
        assert campaign.dollar_risk == campaign.risk_per_share * campaign.position_size


# ============================================================================
# Edge Cases and Backward Compatibility
# ============================================================================


class TestEdgeCases:
    """Test edge cases and backward compatibility."""

    def test_add_pattern_without_account_size(self, detector, sample_spring):
        """Test adding pattern without account_size (backward compatibility)."""
        campaign = detector.add_pattern(sample_spring)

        assert campaign is not None
        assert campaign.position_size == Decimal("0")
        assert campaign.dollar_risk == Decimal("0")

    def test_campaign_with_zero_position_size(self, detector, sample_spring):
        """Test campaign with zero position size contributes no risk."""
        account_size = Decimal("100000")

        # Add campaign without account size
        campaign = detector.add_pattern(sample_spring)
        assert campaign is not None

        # Heat should be 0 since no position size
        heat = detector._calculate_portfolio_heat(account_size)
        assert heat == Decimal("0")

    def test_risk_pct_exceeds_hard_limit(self):
        """Test that risk_pct_per_trade exceeding 2.0% raises ValueError."""
        with pytest.raises(ValueError, match="exceeds 2.0% hard limit"):
            calculate_position_size(
                account_size=Decimal("100000"),
                risk_pct_per_trade=Decimal("3.0"),  # Exceeds 2.0% limit
                risk_per_share=Decimal("5.00"),
            )

    def test_negative_risk_pct_returns_zero(self):
        """Test that negative risk_pct_per_trade returns 0."""
        position_size = calculate_position_size(
            account_size=Decimal("100000"),
            risk_pct_per_trade=Decimal("-1.0"),  # Negative
            risk_per_share=Decimal("5.00"),
        )
        assert position_size == Decimal("0")

    def test_negative_account_size_returns_zero(self):
        """Test that negative account_size returns 0."""
        position_size = calculate_position_size(
            account_size=Decimal("-100000"),  # Negative
            risk_pct_per_trade=Decimal("2.0"),
            risk_per_share=Decimal("5.00"),
        )
        assert position_size == Decimal("0")

    def test_negative_risk_per_share_returns_zero(self):
        """Test that negative risk_per_share returns 0."""
        position_size = calculate_position_size(
            account_size=Decimal("100000"),
            risk_pct_per_trade=Decimal("2.0"),
            risk_per_share=Decimal("-5.00"),  # Negative
        )
        assert position_size == Decimal("0")

    def test_extremely_large_account_size(self):
        """Test position sizing with extremely large account size."""
        position_size = calculate_position_size(
            account_size=Decimal("1000000000"),  # $1 billion
            risk_pct_per_trade=Decimal("2.0"),
            risk_per_share=Decimal("5.00"),
        )
        # $1B × 2% / $5 = 4,000,000 shares
        assert position_size == Decimal("4000000")

    def test_extremely_small_risk_per_share(self):
        """Test position sizing with very small risk_per_share."""
        position_size = calculate_position_size(
            account_size=Decimal("100000"),
            risk_pct_per_trade=Decimal("2.0"),
            risk_per_share=Decimal("0.01"),  # 1 cent risk
        )
        # $100,000 × 2% / $0.01 = 200,000 shares
        assert position_size == Decimal("200000")

    def test_concurrent_and_heat_limits_interaction(
        self, detector, sample_spring, sample_bar, base_timestamp
    ):
        """Test that concurrent campaign limit is checked before heat limit."""
        detector.max_concurrent_campaigns = 2  # Limit to 2 campaigns
        detector.max_portfolio_heat_pct = Decimal("20.0")  # High heat limit
        detector.expiration_hours = 200  # Increase to prevent campaign expiration during test
        account_size = Decimal("100000")

        # Campaign 1
        spring1 = Spring(
            bar=sample_bar,
            bar_index=0,
            penetration_pct=Decimal("0.02"),
            volume_ratio=Decimal("0.4"),
            recovery_bars=1,
            creek_reference=Decimal("100.00"),
            spring_low=Decimal("98.00"),
            recovery_price=Decimal("103.00"),
            detection_timestamp=base_timestamp,
            trading_range_id=uuid4(),
        )

        campaign1 = detector.add_pattern(
            spring1, account_size=account_size, risk_pct_per_trade=Decimal("1.0")
        )
        assert campaign1 is not None

        # Campaign 2 (50 hours later to create separate campaign)
        spring2 = Spring(
            bar=sample_bar,
            bar_index=0,
            penetration_pct=Decimal("0.02"),
            volume_ratio=Decimal("0.4"),
            recovery_bars=1,
            creek_reference=Decimal("100.00"),
            spring_low=Decimal("98.00"),
            recovery_price=Decimal("103.00"),
            detection_timestamp=base_timestamp + timedelta(hours=50),
            trading_range_id=uuid4(),
        )

        campaign2 = detector.add_pattern(
            spring2, account_size=account_size, risk_pct_per_trade=Decimal("1.0")
        )
        assert campaign2 is not None

        # Campaign 3 - Should be rejected due to concurrent limit (not heat)
        spring3 = Spring(
            bar=sample_bar,
            bar_index=0,
            penetration_pct=Decimal("0.02"),
            volume_ratio=Decimal("0.4"),
            recovery_bars=1,
            creek_reference=Decimal("100.00"),
            spring_low=Decimal("98.00"),
            recovery_price=Decimal("103.00"),
            detection_timestamp=base_timestamp + timedelta(hours=100),
            trading_range_id=uuid4(),
        )

        campaign3 = detector.add_pattern(
            spring3, account_size=account_size, risk_pct_per_trade=Decimal("1.0")
        )

        # Should be rejected due to concurrent campaign limit
        assert campaign3 is None
        assert len(detector.get_active_campaigns()) == 2
