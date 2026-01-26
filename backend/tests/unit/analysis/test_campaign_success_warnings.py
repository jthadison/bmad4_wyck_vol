"""
Tests for statistical warnings in Campaign Success Analyzer (Story 16.5b).

Tests the warning generation for statistical validity concerns including:
- Low sample size warnings (<30 campaigns)
- Critical sample size warnings (<10 campaigns)
- Insufficient tier data warnings (<5 campaigns per tier)
- None handling in quality score calculation
"""

from decimal import Decimal

from src.analysis.campaign_success_analyzer import CampaignSuccessAnalyzer
from src.models.campaign import QualityTierPerformance

# ========================================
# Story 16.5b: Statistical Warnings Tests
# ========================================


def test_generate_correlation_warnings_sufficient_sample():
    """Test no warnings with sufficient sample size (Story 16.5b)."""
    analyzer = CampaignSuccessAnalyzer(None)  # type: ignore

    # Create tier performance with sufficient data (30+ campaigns, 5+ per tier)
    tiers = [
        QualityTierPerformance(
            tier="EXCEPTIONAL",
            campaign_count=10,
            win_rate=Decimal("75.00"),
            avg_r_multiple=Decimal("2.5"),
            median_r_multiple=Decimal("2.3"),
            total_r_multiple=Decimal("25.0"),
        ),
        QualityTierPerformance(
            tier="STRONG",
            campaign_count=15,
            win_rate=Decimal("70.00"),
            avg_r_multiple=Decimal("2.0"),
            median_r_multiple=Decimal("1.8"),
            total_r_multiple=Decimal("30.0"),
        ),
        QualityTierPerformance(
            tier="ACCEPTABLE",
            campaign_count=10,
            win_rate=Decimal("60.00"),
            avg_r_multiple=Decimal("1.5"),
            median_r_multiple=Decimal("1.2"),
            total_r_multiple=Decimal("15.0"),
        ),
    ]

    warnings = analyzer._generate_correlation_warnings(35, tiers)
    assert len(warnings) == 0, "Should have no warnings with sufficient data"


def test_generate_correlation_warnings_low_sample():
    """Test warning with low sample size (Story 16.5b)."""
    analyzer = CampaignSuccessAnalyzer(None)  # type: ignore

    # Sample size of 20 (< 30 recommended)
    tiers = [
        QualityTierPerformance(
            tier="STRONG",
            campaign_count=20,
            win_rate=Decimal("70.00"),
            avg_r_multiple=Decimal("2.0"),
            median_r_multiple=Decimal("1.8"),
            total_r_multiple=Decimal("40.0"),
        )
    ]

    warnings = analyzer._generate_correlation_warnings(20, tiers)
    assert len(warnings) == 1
    assert "Low sample size (20 campaigns)" in warnings[0]
    assert "30+ campaigns" in warnings[0]


def test_generate_correlation_warnings_critical_sample():
    """Test critical warning with very low sample size (Story 16.5b)."""
    analyzer = CampaignSuccessAnalyzer(None)  # type: ignore

    # Sample size of 8 (< 10 critical)
    tiers = [
        QualityTierPerformance(
            tier="ACCEPTABLE",
            campaign_count=8,
            win_rate=Decimal("62.50"),
            avg_r_multiple=Decimal("1.8"),
            median_r_multiple=Decimal("1.5"),
            total_r_multiple=Decimal("14.4"),
        )
    ]

    warnings = analyzer._generate_correlation_warnings(8, tiers)
    assert len(warnings) == 1
    assert "Very low sample size (8 campaigns)" in warnings[0]
    assert "at least 30 campaigns" in warnings[0]


def test_generate_correlation_warnings_insufficient_tier_data():
    """Test warning with insufficient tier data (Story 16.5b)."""
    analyzer = CampaignSuccessAnalyzer(None)  # type: ignore

    # Tiers with < 5 campaigns
    tiers = [
        QualityTierPerformance(
            tier="EXCEPTIONAL",
            campaign_count=2,
            win_rate=Decimal("100.00"),
            avg_r_multiple=Decimal("3.0"),
            median_r_multiple=Decimal("3.0"),
            total_r_multiple=Decimal("6.0"),
        ),
        QualityTierPerformance(
            tier="STRONG",
            campaign_count=3,
            win_rate=Decimal("66.67"),
            avg_r_multiple=Decimal("2.0"),
            median_r_multiple=Decimal("2.0"),
            total_r_multiple=Decimal("6.0"),
        ),
        QualityTierPerformance(
            tier="ACCEPTABLE",
            campaign_count=25,
            win_rate=Decimal("60.00"),
            avg_r_multiple=Decimal("1.5"),
            median_r_multiple=Decimal("1.2"),
            total_r_multiple=Decimal("37.5"),
        ),
    ]

    warnings = analyzer._generate_correlation_warnings(30, tiers)
    assert len(warnings) == 1
    assert "Some quality tiers have insufficient data" in warnings[0]
    assert "EXCEPTIONAL (2)" in warnings[0]
    assert "STRONG (3)" in warnings[0]
    assert "5+ campaigns per tier" in warnings[0]


def test_generate_correlation_warnings_multiple_issues():
    """Test multiple warnings for combined issues (Story 16.5b)."""
    analyzer = CampaignSuccessAnalyzer(None)  # type: ignore

    # Low sample size AND insufficient tier data
    tiers = [
        QualityTierPerformance(
            tier="STRONG",
            campaign_count=15,
            win_rate=Decimal("73.33"),
            avg_r_multiple=Decimal("2.2"),
            median_r_multiple=Decimal("2.0"),
            total_r_multiple=Decimal("33.0"),
        ),
        QualityTierPerformance(
            tier="WEAK",
            campaign_count=3,
            win_rate=Decimal("33.33"),
            avg_r_multiple=Decimal("0.5"),
            median_r_multiple=Decimal("0.3"),
            total_r_multiple=Decimal("1.5"),
        ),
    ]

    warnings = analyzer._generate_correlation_warnings(18, tiers)
    assert len(warnings) == 2
    assert any("Low sample size (18 campaigns)" in w for w in warnings)
    assert any("WEAK (3)" in w for w in warnings)


def test_none_handling_in_quality_score_calculation():
    """Test that None values are handled in quality score calculation (Story 16.5b)."""
    from unittest.mock import MagicMock

    analyzer = CampaignSuccessAnalyzer(None)  # type: ignore

    # Create mock campaign with None values to test the calculation logic
    # (CampaignMetrics model requires these fields, but we want to test edge cases)
    campaign = MagicMock()
    campaign.win_rate = None
    campaign.actual_r_achieved = None
    campaign.target_achievement_pct = None

    # Should not raise error and should return 0
    score = analyzer._calculate_derived_quality_score(campaign)
    assert score == 0

    # Test with some None, some valid
    campaign.win_rate = Decimal("75.0")  # 30 points (75 * 0.4)
    campaign.actual_r_achieved = None  # 0 points
    campaign.target_achievement_pct = Decimal("80.0")  # 24 points (80 * 0.3)

    score = analyzer._calculate_derived_quality_score(campaign)
    assert score == 54  # 30 + 0 + 24

    # Test with all valid values
    campaign.win_rate = Decimal("80.0")  # 32 points (80 * 0.4)
    campaign.actual_r_achieved = Decimal("2.5")  # 25 points (min(30, 2.5 * 10))
    campaign.target_achievement_pct = Decimal("90.0")  # 27 points (90 * 0.3)

    score = analyzer._calculate_derived_quality_score(campaign)
    assert score == 84  # 32 + 25 + 27
