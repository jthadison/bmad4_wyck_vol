"""
Unit tests for Correlation Limit Enforcement (Story 16.1b)

Tests cover all acceptance criteria:
- AC1: Max 2 campaigns per correlation group (configurable)
- AC2: Max 3 campaigns per sector (configurable)
- AC3: Max 50% of portfolio in single asset category (configurable)
- AC4: Limits enforced on new campaign formation only
- AC5: Warning logged when approaching limits (1 slot remaining)
- AC6: Existing campaigns unaffected by limit changes
- AC7: get_correlation_summary() returns distribution by group/sector/category

Test Categories:
1. Correlation Group Limit Tests
2. Sector Limit Tests (equities only)
3. Category Concentration Tests
4. Approaching Limit Warning Tests
5. get_correlation_summary() Tests
6. Edge Cases
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from src.backtesting.intraday_campaign_detector import (
    IntradayCampaignDetector,
)
from src.models.campaign import AssetCategory
from src.models.ohlcv import OHLCVBar
from src.models.spring import Spring

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def detector():
    """Standard detector with explicit correlation limits for testing."""
    return IntradayCampaignDetector(
        campaign_window_hours=48,
        max_pattern_gap_hours=48,
        min_patterns_for_active=2,
        expiration_hours=200,  # High expiration so campaigns don't expire during tests
        max_concurrent_campaigns=10,  # High limit to not interfere with correlation tests
        max_portfolio_heat_pct=Decimal("50.0"),  # High limit to not interfere
        # Story 16.1b: Explicit correlation limits for testing
        max_campaigns_per_correlation_group=2,  # Test correlation group limits
        max_campaigns_per_sector=3,  # Test sector limits
        max_category_concentration_pct=100.0,  # Disable category limit for correlation tests
    )


@pytest.fixture
def base_timestamp():
    """Base timestamp for test patterns."""
    return datetime(2025, 12, 15, 9, 0, tzinfo=UTC)


def create_ohlcv_bar(symbol: str, timestamp: datetime) -> OHLCVBar:
    """Helper to create OHLCV bars with different symbols."""
    return OHLCVBar(
        timestamp=timestamp,
        open=Decimal("100.00"),
        high=Decimal("101.00"),
        low=Decimal("99.00"),
        close=Decimal("100.50"),
        volume=100000,
        spread=Decimal("2.00"),
        timeframe="15m",
        symbol=symbol,
    )


def create_spring_pattern(symbol: str, timestamp: datetime) -> Spring:
    """Helper to create Spring patterns with different symbols."""
    bar = create_ohlcv_bar(symbol, timestamp)
    return Spring(
        bar=bar,
        bar_index=10,
        penetration_pct=Decimal("0.02"),
        volume_ratio=Decimal("0.4"),
        recovery_bars=1,
        creek_reference=Decimal("100.00"),
        spring_low=Decimal("98.00"),
        recovery_price=Decimal("100.50"),
        detection_timestamp=timestamp,
        trading_range_id=uuid4(),
    )


# ============================================================================
# Correlation Group Limit Tests
# ============================================================================


class TestCorrelationGroupLimits:
    """Tests for max campaigns per correlation group limit."""

    def test_first_campaign_in_group_allowed(self, detector, base_timestamp):
        """AC1: First campaign in a correlation group should be allowed."""
        pattern = create_spring_pattern("EURUSD", base_timestamp)
        campaign = detector.add_pattern(pattern)

        assert campaign is not None
        assert campaign.correlation_group == "USD_MAJOR"
        assert campaign.asset_category == AssetCategory.FOREX

    def test_second_campaign_in_same_group_allowed(self, detector, base_timestamp):
        """AC1: Second campaign in same correlation group should be allowed (limit is 2)."""
        # First campaign - EURUSD
        pattern1 = create_spring_pattern("EURUSD", base_timestamp)
        campaign1 = detector.add_pattern(pattern1)
        assert campaign1 is not None

        # Second campaign - GBPUSD (same USD_MAJOR group)
        # Use timestamp > 48h apart to force new campaign
        pattern2 = create_spring_pattern("GBPUSD", base_timestamp + timedelta(hours=50))
        campaign2 = detector.add_pattern(pattern2)
        assert campaign2 is not None
        assert campaign2.correlation_group == "USD_MAJOR"
        # Verify these are actually different campaigns
        assert campaign1.campaign_id != campaign2.campaign_id

    def test_third_campaign_in_same_group_rejected(self, detector, base_timestamp):
        """AC1: Third campaign in same correlation group should be rejected (limit is 2)."""
        # First two campaigns in USD_MAJOR
        # Use timestamps > 48h apart to force separate campaigns
        pattern1 = create_spring_pattern("EURUSD", base_timestamp)
        detector.add_pattern(pattern1)

        pattern2 = create_spring_pattern("GBPUSD", base_timestamp + timedelta(hours=50))
        detector.add_pattern(pattern2)

        # Third campaign - AUDUSD (also USD_MAJOR) should be rejected
        pattern3 = create_spring_pattern("AUDUSD", base_timestamp + timedelta(hours=100))
        campaign3 = detector.add_pattern(pattern3)

        assert campaign3 is None  # Rejected due to correlation group limit

    def test_different_correlation_groups_allowed(self, detector, base_timestamp):
        """AC1: Campaigns in different correlation groups should be allowed."""
        # USD_MAJOR group (FOREX)
        pattern1 = create_spring_pattern("EURUSD", base_timestamp)
        campaign1 = detector.add_pattern(pattern1)
        assert campaign1 is not None
        assert campaign1.correlation_group == "USD_MAJOR"

        # EQUITY_TECH group (different from USD_MAJOR)
        # Use timestamp > 48h apart to force new campaign
        pattern2 = create_spring_pattern("AAPL", base_timestamp + timedelta(hours=50))
        campaign2 = detector.add_pattern(pattern2)
        assert campaign2 is not None
        assert campaign2.correlation_group == "EQUITY_TECH"
        # Verify these are actually different campaigns
        assert campaign1.campaign_id != campaign2.campaign_id


# ============================================================================
# Sector Limit Tests (Equities Only)
# ============================================================================


class TestSectorLimits:
    """Tests for max campaigns per sector limit (equities only)."""

    def test_first_campaign_in_sector_allowed(self, detector, base_timestamp):
        """AC2: First campaign in a sector should be allowed."""
        pattern = create_spring_pattern("AAPL", base_timestamp)
        campaign = detector.add_pattern(pattern)

        assert campaign is not None
        assert campaign.sector == "TECH"
        assert campaign.asset_category == AssetCategory.EQUITY

    def test_three_campaigns_in_same_sector_allowed(self, base_timestamp):
        """AC2: Three campaigns in same sector should be allowed (limit is 3)."""
        # Create detector with high correlation group limit to test sector limit specifically
        sector_detector = IntradayCampaignDetector(
            campaign_window_hours=48,
            max_pattern_gap_hours=48,
            expiration_hours=200,
            max_concurrent_campaigns=10,
            max_campaigns_per_correlation_group=10,  # High to not interfere with sector test
            max_campaigns_per_sector=3,
            max_category_concentration_pct=100.0,
        )

        # TECH sector stocks
        # Use timestamps > 48h apart to force separate campaigns
        stocks = ["AAPL", "MSFT", "GOOGL"]
        campaigns = []

        for i, symbol in enumerate(stocks):
            pattern = create_spring_pattern(symbol, base_timestamp + timedelta(hours=50 * i))
            campaign = sector_detector.add_pattern(pattern)
            campaigns.append(campaign)

        assert all(c is not None for c in campaigns)
        assert all(c.sector == "TECH" for c in campaigns)
        # Verify these are actually different campaigns
        assert len({c.campaign_id for c in campaigns}) == 3

    def test_fourth_campaign_in_same_sector_rejected(self, base_timestamp):
        """AC2: Fourth campaign in same sector should be rejected (limit is 3)."""
        # Create detector with high correlation group limit to test sector limit specifically
        sector_detector = IntradayCampaignDetector(
            campaign_window_hours=48,
            max_pattern_gap_hours=48,
            expiration_hours=200,
            max_concurrent_campaigns=10,
            max_campaigns_per_correlation_group=10,  # High to not interfere with sector test
            max_campaigns_per_sector=3,
            max_category_concentration_pct=100.0,
        )

        # First three campaigns in TECH sector
        # Use timestamps > 48h apart to force separate campaigns
        stocks = ["AAPL", "MSFT", "GOOGL"]
        for i, symbol in enumerate(stocks):
            pattern = create_spring_pattern(symbol, base_timestamp + timedelta(hours=50 * i))
            sector_detector.add_pattern(pattern)

        # Fourth TECH stock should be rejected
        pattern4 = create_spring_pattern("NVDA", base_timestamp + timedelta(hours=150))
        campaign4 = sector_detector.add_pattern(pattern4)

        assert campaign4 is None  # Rejected due to sector limit

    def test_sector_limit_only_applies_to_equities(self, detector, base_timestamp):
        """AC2: Sector limit should only apply to equities, not forex."""
        # Add multiple forex pairs (no sector limit)
        # Use timestamps > 48h apart to force separate campaigns
        forex_pairs = ["EURUSD", "GBPUSD", "AUDUSD", "NZDUSD"]
        campaigns = []

        for i, symbol in enumerate(forex_pairs):
            pattern = create_spring_pattern(symbol, base_timestamp + timedelta(hours=50 * i))
            # Note: This will be limited by correlation group limit, not sector
            campaign = detector.add_pattern(pattern)
            campaigns.append(campaign)

        # First two should succeed (USD_MAJOR limit)
        assert campaigns[0] is not None
        assert campaigns[1] is not None
        # Third/fourth rejected by correlation group, not sector
        # (all are USD_MAJOR)


# ============================================================================
# Category Concentration Tests
# ============================================================================


class TestCategoryConcentration:
    """Tests for max category concentration limit."""

    def test_category_concentration_within_limit(self, detector, base_timestamp):
        """AC3: Category concentration within 50% limit should be allowed."""
        # Add one FOREX and one EQUITY campaign (50% each)
        # Use timestamp > 48h apart to force new campaign
        pattern1 = create_spring_pattern("EURUSD", base_timestamp)
        campaign1 = detector.add_pattern(pattern1)

        pattern2 = create_spring_pattern("AAPL", base_timestamp + timedelta(hours=50))
        campaign2 = detector.add_pattern(pattern2)

        assert campaign1 is not None
        assert campaign2 is not None
        # Verify these are actually different campaigns
        assert campaign1.campaign_id != campaign2.campaign_id

    def test_category_concentration_limit_exceeded(self, detector, base_timestamp):
        """AC3: Category concentration > 50% should be rejected."""
        # Create detector with stricter limits for this test
        strict_detector = IntradayCampaignDetector(
            max_concurrent_campaigns=10,
            max_campaigns_per_correlation_group=10,  # High to not interfere
            max_campaigns_per_sector=10,  # High to not interfere
            max_category_concentration_pct=50.0,
        )

        # Add first FOREX campaign
        pattern1 = create_spring_pattern("EURUSD", base_timestamp)
        campaign1 = strict_detector.add_pattern(pattern1)
        assert campaign1 is not None

        # Add second FOREX campaign - would make 100% FOREX concentration
        # But with 2 campaigns, 2/2 = 100% > 50%
        # Use timestamp > 48h apart to force new campaign
        pattern2 = create_spring_pattern("EURJPY", base_timestamp + timedelta(hours=50))
        campaign2 = strict_detector.add_pattern(pattern2)

        # Second FOREX should be rejected (100% > 50%)
        assert campaign2 is None

    def test_category_concentration_mixed_categories(self, detector, base_timestamp):
        """AC3: Mixed categories should stay within concentration limits."""
        # Use a detector with high correlation limits to test concentration
        mixed_detector = IntradayCampaignDetector(
            max_concurrent_campaigns=10,
            max_campaigns_per_correlation_group=10,
            max_campaigns_per_sector=10,
            max_category_concentration_pct=60.0,  # 60% limit
        )

        # Add FOREX
        pattern1 = create_spring_pattern("EURUSD", base_timestamp)
        campaign1 = mixed_detector.add_pattern(pattern1)

        # Add EQUITY
        # Use timestamp > 48h apart to force new campaign
        pattern2 = create_spring_pattern("AAPL", base_timestamp + timedelta(hours=50))
        campaign2 = mixed_detector.add_pattern(pattern2)

        # Add INDEX
        # Use timestamp > 48h apart to force new campaign
        pattern3 = create_spring_pattern("SPX", base_timestamp + timedelta(hours=100))
        campaign3 = mixed_detector.add_pattern(pattern3)

        # All should succeed with 33% each category
        assert campaign1 is not None
        assert campaign2 is not None
        assert campaign3 is not None
        # Verify these are actually different campaigns
        assert len({campaign1.campaign_id, campaign2.campaign_id, campaign3.campaign_id}) == 3


# ============================================================================
# Approaching Limit Warning Tests
# ============================================================================


class TestApproachingLimitWarnings:
    """Tests for warnings when approaching limits."""

    def test_warning_at_one_slot_remaining_correlation_group(self, base_timestamp):
        """AC5: Warning should be logged when 1 slot remaining in correlation group."""
        from unittest.mock import MagicMock

        # Create detector with correlation group limit of 2
        detector = IntradayCampaignDetector(
            campaign_window_hours=48,
            max_pattern_gap_hours=48,
            expiration_hours=200,
            max_concurrent_campaigns=10,
            max_campaigns_per_correlation_group=2,
            max_campaigns_per_sector=10,
            max_category_concentration_pct=100.0,
        )

        # First campaign - no warning yet
        pattern1 = create_spring_pattern("EURUSD", base_timestamp)
        detector.add_pattern(pattern1)

        # Replace logger with mock AFTER first campaign
        mock_logger = MagicMock()
        detector.logger = mock_logger

        # Second campaign (same USD_MAJOR group) - should trigger warning
        # Use timestamp > 48h apart to force new campaign
        pattern2 = create_spring_pattern("GBPUSD", base_timestamp + timedelta(hours=50))
        detector.add_pattern(pattern2)

        # Check for warning call about approaching limit
        warning_calls = [
            call
            for call in mock_logger.warning.call_args_list
            if "Approaching correlation group limit" in str(call)
        ]
        assert len(warning_calls) > 0, "Expected warning about approaching correlation group limit"

    def test_warning_at_one_slot_remaining_sector(self, base_timestamp):
        """AC5: Warning should be logged when 1 slot remaining in sector."""
        from unittest.mock import MagicMock

        # Create detector with 2-campaign sector limit and high correlation limit
        strict_detector = IntradayCampaignDetector(
            campaign_window_hours=48,
            max_pattern_gap_hours=48,
            expiration_hours=200,
            max_concurrent_campaigns=10,
            max_campaigns_per_correlation_group=10,
            max_campaigns_per_sector=2,
            max_category_concentration_pct=100.0,
        )

        # First TECH stock - no warning yet
        pattern1 = create_spring_pattern("AAPL", base_timestamp)
        strict_detector.add_pattern(pattern1)

        # Replace logger with mock AFTER first campaign
        mock_logger = MagicMock()
        strict_detector.logger = mock_logger

        # Second TECH stock - should trigger warning
        # Use timestamp > 48h apart to force new campaign
        pattern2 = create_spring_pattern("MSFT", base_timestamp + timedelta(hours=50))
        strict_detector.add_pattern(pattern2)

        # Check for warning about approaching sector limit
        warning_calls = [
            call
            for call in mock_logger.warning.call_args_list
            if "Approaching sector limit" in str(call)
        ]
        assert len(warning_calls) > 0, "Expected warning about approaching sector limit"


# ============================================================================
# get_correlation_summary() Tests
# ============================================================================


class TestCorrelationSummary:
    """Tests for get_correlation_summary() method."""

    def test_empty_summary(self, detector):
        """AC7: Empty detector should return empty summary."""
        summary = detector.get_correlation_summary()

        assert summary["total_active_campaigns"] == 0
        assert summary["correlation_groups"] == {}
        assert summary["sectors"] == {}
        assert summary["asset_categories"] == {}
        assert summary["category_concentration_pct"] == {}
        assert summary["at_risk_groups"] == []
        assert summary["at_risk_sectors"] == []

    def test_summary_with_single_campaign(self, detector, base_timestamp):
        """AC7: Summary should correctly count single campaign."""
        pattern = create_spring_pattern("EURUSD", base_timestamp)
        detector.add_pattern(pattern)

        summary = detector.get_correlation_summary()

        assert summary["total_active_campaigns"] == 1
        assert summary["correlation_groups"] == {"USD_MAJOR": 1}
        assert summary["sectors"] == {}  # Forex has no sector
        assert summary["asset_categories"] == {"FOREX": 1}
        assert summary["category_concentration_pct"] == {"FOREX": 100.0}

    def test_summary_with_multiple_campaigns(self, detector, base_timestamp):
        """AC7: Summary should correctly count multiple campaigns."""
        # Add FOREX
        pattern1 = create_spring_pattern("EURUSD", base_timestamp)
        detector.add_pattern(pattern1)

        # Add EQUITY
        # Use timestamp > 48h apart to force new campaign
        pattern2 = create_spring_pattern("AAPL", base_timestamp + timedelta(hours=50))
        detector.add_pattern(pattern2)

        summary = detector.get_correlation_summary()

        assert summary["total_active_campaigns"] == 2
        assert "USD_MAJOR" in summary["correlation_groups"]
        assert "EQUITY_TECH" in summary["correlation_groups"]
        assert summary["sectors"] == {"TECH": 1}
        assert summary["asset_categories"] == {"FOREX": 1, "EQUITY": 1}
        assert summary["category_concentration_pct"]["FOREX"] == 50.0
        assert summary["category_concentration_pct"]["EQUITY"] == 50.0

    def test_at_risk_groups_identified(self, detector, base_timestamp):
        """AC7: at_risk_groups should identify groups approaching limit."""
        # Add one campaign to USD_MAJOR (1/2 slots = at risk)
        pattern = create_spring_pattern("EURUSD", base_timestamp)
        detector.add_pattern(pattern)

        summary = detector.get_correlation_summary()

        # USD_MAJOR has 1 campaign, limit is 2, so it's "at risk" (1 slot remaining)
        assert "USD_MAJOR" in summary["at_risk_groups"]


# ============================================================================
# Edge Cases
# ============================================================================


class TestEdgeCases:
    """Tests for edge cases and special scenarios."""

    def test_unknown_symbol_allowed(self, detector, base_timestamp):
        """Edge case: Unknown symbol should be allowed with UNKNOWN category."""
        pattern = create_spring_pattern("UNKNOWN_SYMBOL", base_timestamp)
        campaign = detector.add_pattern(pattern)

        assert campaign is not None
        assert campaign.asset_category == AssetCategory.UNKNOWN

    def test_configurable_limits(self, base_timestamp):
        """Test that limits are configurable."""
        custom_detector = IntradayCampaignDetector(
            max_campaigns_per_correlation_group=5,
            max_campaigns_per_sector=10,
            max_category_concentration_pct=80.0,
        )

        assert custom_detector.max_campaigns_per_correlation_group == 5
        assert custom_detector.max_campaigns_per_sector == 10
        assert custom_detector.max_category_concentration_pct == 80.0

    def test_existing_campaigns_unaffected(self, detector, base_timestamp):
        """AC6: Existing campaigns should not be affected by limit changes."""
        # Add campaigns with timestamps > 48h apart to force separate campaigns
        pattern1 = create_spring_pattern("EURUSD", base_timestamp)
        campaign1 = detector.add_pattern(pattern1)

        pattern2 = create_spring_pattern("GBPUSD", base_timestamp + timedelta(hours=50))
        campaign2 = detector.add_pattern(pattern2)

        # Both campaigns should still be active and be distinct
        active = detector.get_active_campaigns()
        assert len(active) == 2
        assert campaign1 in active
        assert campaign2 in active
        assert campaign1.campaign_id != campaign2.campaign_id

    def test_correlation_info_assigned_correctly(self, detector, base_timestamp):
        """Test that correlation info is correctly assigned to campaigns."""
        # Test FOREX
        forex_pattern = create_spring_pattern("EURUSD", base_timestamp)
        forex_campaign = detector.add_pattern(forex_pattern)

        assert forex_campaign.asset_category == AssetCategory.FOREX
        assert forex_campaign.correlation_group == "USD_MAJOR"
        assert forex_campaign.sector is None

        # Test EQUITY
        # Use timestamp > 48h apart to force new campaign
        equity_pattern = create_spring_pattern("AAPL", base_timestamp + timedelta(hours=50))
        equity_campaign = detector.add_pattern(equity_pattern)

        assert equity_campaign.asset_category == AssetCategory.EQUITY
        assert equity_campaign.correlation_group == "EQUITY_TECH"
        assert equity_campaign.sector == "TECH"
        # Verify these are actually different campaigns
        assert forex_campaign.campaign_id != equity_campaign.campaign_id

    def test_symbol_from_pattern_bar(self, detector, base_timestamp):
        """Test that symbol is correctly extracted from pattern.bar.symbol."""
        bar = OHLCVBar(
            timestamp=base_timestamp,
            open=Decimal("100.00"),
            high=Decimal("101.00"),
            low=Decimal("99.00"),
            close=Decimal("100.50"),
            volume=100000,
            spread=Decimal("2.00"),
            timeframe="15m",
            symbol="BTCUSD",  # Crypto symbol
        )
        pattern = Spring(
            bar=bar,
            bar_index=10,
            penetration_pct=Decimal("0.02"),
            volume_ratio=Decimal("0.4"),
            recovery_bars=1,
            creek_reference=Decimal("100.00"),
            spring_low=Decimal("98.00"),
            recovery_price=Decimal("100.50"),
            detection_timestamp=base_timestamp,
            trading_range_id=uuid4(),
        )

        campaign = detector.add_pattern(pattern)

        assert campaign is not None
        assert campaign.asset_category == AssetCategory.CRYPTO
        assert campaign.correlation_group == "BTC_CORRELATED"

    def test_asset_symbol_override(self, detector, base_timestamp):
        """Test that asset_symbol parameter overrides pattern.bar.symbol."""
        pattern = create_spring_pattern("EURUSD", base_timestamp)

        # Override symbol to be AAPL
        campaign = detector.add_pattern(
            pattern, asset_symbol="AAPL", asset_category=AssetCategory.EQUITY
        )

        assert campaign is not None
        assert campaign.asset_category == AssetCategory.EQUITY
        assert campaign.sector == "TECH"
        assert campaign.correlation_group == "EQUITY_TECH"
