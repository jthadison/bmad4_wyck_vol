"""
Unit tests for Story 16.7b: Adaptive Validation Rules & Regime Statistics

Tests cover:
1. Adaptive quality thresholds by market regime
2. Volume multiplier adjustments by regime
3. Regime-aware campaign creation
4. RegimePerformanceAnalyzer statistics
5. Regime performance reporting
6. Cache behavior for statistics

Author: Developer Agent (Story 16.7b Implementation)
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from src.backtesting.intraday_campaign_detector import (
    REGIME_QUALITY_THRESHOLDS,
    REGIME_VOLUME_MULTIPLIERS,
    Campaign,
    CampaignState,
    ExitReason,
    IntradayCampaignDetector,
)
from src.backtesting.regime_performance_analyzer import RegimePerformanceAnalyzer
from src.models.market_context import MarketRegime
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
        max_concurrent_campaigns=10,  # Allow more for testing
        max_portfolio_heat_pct=Decimal("20.0"),
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


def create_spring(bar: OHLCVBar, bar_index: int = 10) -> Spring:
    """Helper to create a Spring pattern."""
    return Spring(
        bar=bar,
        bar_index=bar_index,
        penetration_pct=Decimal("0.02"),
        volume_ratio=Decimal("0.4"),
        recovery_bars=1,
        creek_reference=Decimal("100.00"),
        spring_low=Decimal("98.00"),
        recovery_price=Decimal("100.50"),
        detection_timestamp=bar.timestamp,
        trading_range_id=uuid4(),
    )


def create_completed_campaign(
    regime: MarketRegime,
    r_multiple: Decimal,
    exit_reason: ExitReason = ExitReason.TARGET_HIT,
) -> Campaign:
    """Helper to create a completed campaign for statistics testing."""
    campaign = Campaign(
        start_time=datetime.now(UTC),
        state=CampaignState.COMPLETED,
        market_regime=regime,
        r_multiple=r_multiple,
        exit_reason=exit_reason,
        exit_price=Decimal("105.00"),
        exit_timestamp=datetime.now(UTC),
        points_gained=Decimal("5.00"),
        risk_per_share=Decimal("2.00"),
    )
    return campaign


# ============================================================================
# AC1: Adaptive Quality Threshold Tests
# ============================================================================


class TestAdaptiveQualityThreshold:
    """Tests for _get_quality_threshold method (AC1)."""

    def test_ranging_regime_standard_threshold(self, detector):
        """AC1: RANGING (SIDEWAYS) should use standard 0.7 threshold."""
        threshold = detector._get_quality_threshold(MarketRegime.SIDEWAYS)
        assert threshold == 0.7

    def test_trending_up_higher_threshold(self, detector):
        """AC1: TRENDING_UP should increase threshold to 0.8."""
        threshold = detector._get_quality_threshold(MarketRegime.TRENDING_UP)
        assert threshold == 0.8

    def test_trending_down_higher_threshold(self, detector):
        """AC1: TRENDING_DOWN should increase threshold to 0.8."""
        threshold = detector._get_quality_threshold(MarketRegime.TRENDING_DOWN)
        assert threshold == 0.8

    def test_high_volatility_threshold(self, detector):
        """AC1: HIGH_VOLATILITY should use 0.75 threshold."""
        threshold = detector._get_quality_threshold(MarketRegime.HIGH_VOLATILITY)
        assert threshold == 0.75

    def test_low_volatility_standard_threshold(self, detector):
        """AC1: LOW_VOLATILITY should use standard 0.7 threshold."""
        threshold = detector._get_quality_threshold(MarketRegime.LOW_VOLATILITY)
        assert threshold == 0.7

    def test_none_regime_returns_default(self, detector):
        """None regime should return default 0.7 threshold."""
        threshold = detector._get_quality_threshold(None)
        assert threshold == 0.7

    def test_all_regimes_have_thresholds(self):
        """All MarketRegime values should have defined thresholds."""
        for regime in MarketRegime:
            assert regime in REGIME_QUALITY_THRESHOLDS


# ============================================================================
# AC2: Volume Multiplier Tests
# ============================================================================


class TestVolumeMultiplier:
    """Tests for _get_volume_multiplier method (AC2)."""

    def test_ranging_standard_multiplier(self, detector):
        """AC2: RANGING (SIDEWAYS) should use standard 1.0 multiplier."""
        multiplier = detector._get_volume_multiplier(MarketRegime.SIDEWAYS)
        assert multiplier == 1.0

    def test_high_volatility_increased_multiplier(self, detector):
        """AC2: HIGH_VOLATILITY should increase volume requirement by 20%."""
        multiplier = detector._get_volume_multiplier(MarketRegime.HIGH_VOLATILITY)
        assert multiplier == 1.2

    def test_low_volatility_decreased_multiplier(self, detector):
        """AC2: LOW_VOLATILITY should decrease volume requirement by 10%."""
        multiplier = detector._get_volume_multiplier(MarketRegime.LOW_VOLATILITY)
        assert multiplier == 0.9

    def test_trending_standard_multiplier(self, detector):
        """AC2: TRENDING regimes should use standard 1.0 multiplier."""
        assert detector._get_volume_multiplier(MarketRegime.TRENDING_UP) == 1.0
        assert detector._get_volume_multiplier(MarketRegime.TRENDING_DOWN) == 1.0

    def test_none_regime_returns_default(self, detector):
        """None regime should return default 1.0 multiplier."""
        multiplier = detector._get_volume_multiplier(None)
        assert multiplier == 1.0

    def test_all_regimes_have_multipliers(self):
        """All MarketRegime values should have defined multipliers."""
        for regime in MarketRegime:
            assert regime in REGIME_VOLUME_MULTIPLIERS


# ============================================================================
# AC3: Regime-Aware Campaign Creation Tests
# ============================================================================


class TestRegimeAwareCampaignCreation:
    """Tests for regime-aware validation in campaign detection (AC3)."""

    def test_campaign_stores_regime(self, detector, sample_bar):
        """AC3: Campaign should store market regime from add_pattern."""
        spring = create_spring(sample_bar)

        campaign = detector.add_pattern(
            spring,
            market_regime=MarketRegime.SIDEWAYS,
        )

        assert campaign is not None
        assert campaign.market_regime == MarketRegime.SIDEWAYS

    def test_campaign_stores_quality_threshold(self, detector, sample_bar):
        """AC3: Campaign should store adaptive quality threshold."""
        spring = create_spring(sample_bar)

        campaign = detector.add_pattern(
            spring,
            market_regime=MarketRegime.TRENDING_UP,
        )

        assert campaign is not None
        assert campaign.regime_quality_threshold == 0.8

    def test_campaign_stores_volume_multiplier(self, detector, sample_bar):
        """AC3: Campaign should store adaptive volume multiplier."""
        spring = create_spring(sample_bar)

        campaign = detector.add_pattern(
            spring,
            market_regime=MarketRegime.HIGH_VOLATILITY,
        )

        assert campaign is not None
        assert campaign.regime_volume_multiplier == 1.2

    def test_campaign_without_regime_uses_defaults(self, detector, sample_bar):
        """Campaign without regime should use default thresholds."""
        spring = create_spring(sample_bar)

        campaign = detector.add_pattern(spring)

        assert campaign is not None
        assert campaign.market_regime is None
        assert campaign.regime_quality_threshold == 0.7
        assert campaign.regime_volume_multiplier == 1.0

    def test_set_campaign_regime_updates_all_fields(self, detector, sample_bar):
        """set_campaign_regime should update all regime tracking fields."""
        spring = create_spring(sample_bar)
        campaign = detector.add_pattern(spring)

        detector.set_campaign_regime(campaign, MarketRegime.HIGH_VOLATILITY)

        assert campaign.market_regime == MarketRegime.HIGH_VOLATILITY
        assert campaign.regime_quality_threshold == 0.75
        assert campaign.regime_volume_multiplier == 1.2


# ============================================================================
# AC4: RegimePerformanceAnalyzer Tests
# ============================================================================


class TestRegimePerformanceAnalyzer:
    """Tests for RegimePerformanceAnalyzer (AC4)."""

    def test_get_regime_statistics_empty(self, detector):
        """get_regime_statistics should handle empty campaigns."""
        analyzer = RegimePerformanceAnalyzer(detector)
        stats = analyzer.get_regime_statistics()

        assert len(stats) == len(MarketRegime)
        for regime in MarketRegime:
            assert stats[regime]["total_campaigns"] == 0
            assert stats[regime]["win_rate"] == 0.0
            assert stats[regime]["avg_r_multiple"] == 0.0
            assert stats[regime]["success_rate"] == 0.0

    def test_win_rate_calculation(self, detector):
        """Win rate should be correctly calculated from R-multiples."""
        # Add completed campaigns directly to detector's index
        campaigns = [
            create_completed_campaign(MarketRegime.SIDEWAYS, Decimal("2.0")),  # Win
            create_completed_campaign(MarketRegime.SIDEWAYS, Decimal("-1.0")),  # Loss
            create_completed_campaign(MarketRegime.SIDEWAYS, Decimal("1.5")),  # Win
            create_completed_campaign(MarketRegime.SIDEWAYS, Decimal("0.5")),  # Win
        ]
        for c in campaigns:
            detector._add_to_indexes(c)

        analyzer = RegimePerformanceAnalyzer(detector)
        stats = analyzer.get_regime_statistics()

        assert stats[MarketRegime.SIDEWAYS]["total_campaigns"] == 4
        assert stats[MarketRegime.SIDEWAYS]["win_rate"] == 0.75  # 3/4 wins

    def test_avg_r_multiple_calculation(self, detector):
        """Average R-multiple should be correctly calculated."""
        campaigns = [
            create_completed_campaign(MarketRegime.SIDEWAYS, Decimal("2.0")),
            create_completed_campaign(MarketRegime.SIDEWAYS, Decimal("3.0")),
            create_completed_campaign(MarketRegime.SIDEWAYS, Decimal("1.0")),
        ]
        for c in campaigns:
            detector._add_to_indexes(c)

        analyzer = RegimePerformanceAnalyzer(detector)
        stats = analyzer.get_regime_statistics()

        # (2 + 3 + 1) / 3 = 2.0
        assert stats[MarketRegime.SIDEWAYS]["avg_r_multiple"] == 2.0

    def test_success_rate_calculation(self, detector):
        """Success rate should count campaigns with R >= 2.0 or TARGET_HIT."""
        campaigns = [
            create_completed_campaign(MarketRegime.SIDEWAYS, Decimal("2.5"), ExitReason.TARGET_HIT),
            create_completed_campaign(MarketRegime.SIDEWAYS, Decimal("1.5"), ExitReason.TIME_EXIT),
            create_completed_campaign(MarketRegime.SIDEWAYS, Decimal("2.0"), ExitReason.PHASE_E),
            create_completed_campaign(MarketRegime.SIDEWAYS, Decimal("0.5"), ExitReason.STOP_OUT),
        ]
        for c in campaigns:
            detector._add_to_indexes(c)

        analyzer = RegimePerformanceAnalyzer(detector)
        stats = analyzer.get_regime_statistics()

        # 3 successes: R=2.5 TARGET_HIT, R=2.0 PHASE_E, R=2.5 is >=2
        # Actually: R=2.5 TARGET_HIT = success, R=1.5 TIME_EXIT = not success,
        # R=2.0 PHASE_E = success (PHASE_E exit reason), R=0.5 STOP_OUT = not success
        # So 2/4 = 0.5
        assert stats[MarketRegime.SIDEWAYS]["success_rate"] == 0.5


class TestRegimePerformanceReport:
    """Tests for regime performance reporting (AC4)."""

    def test_get_optimal_regime_insufficient_data(self, detector):
        """get_optimal_regime should return None with insufficient data."""
        analyzer = RegimePerformanceAnalyzer(detector)
        optimal = analyzer.get_optimal_regime()
        assert optimal is None

    def test_get_optimal_regime_with_data(self, detector):
        """get_optimal_regime should identify best performing regime."""
        # Add 5 sideways campaigns with 80% win rate
        for i in range(5):
            r = Decimal("2.0") if i < 4 else Decimal("-1.0")
            c = create_completed_campaign(MarketRegime.SIDEWAYS, r)
            detector._add_to_indexes(c)

        # Add 5 trending campaigns with 40% win rate
        for i in range(5):
            r = Decimal("2.0") if i < 2 else Decimal("-1.0")
            c = create_completed_campaign(MarketRegime.TRENDING_UP, r)
            detector._add_to_indexes(c)

        analyzer = RegimePerformanceAnalyzer(detector)
        optimal = analyzer.get_optimal_regime()

        assert optimal == MarketRegime.SIDEWAYS

    def test_regime_performance_report_structure(self, detector):
        """get_regime_performance_report should return expected structure."""
        analyzer = RegimePerformanceAnalyzer(detector)
        report = analyzer.get_regime_performance_report()

        assert "generated_at" in report
        assert "total_campaigns_analyzed" in report
        assert "optimal_regime" in report
        assert "regime_statistics" in report
        assert "recommendations" in report

    def test_export_to_json(self, detector):
        """export_to_json should return valid JSON string."""
        # Add some data
        c = create_completed_campaign(MarketRegime.SIDEWAYS, Decimal("2.0"))
        detector._add_to_indexes(c)

        analyzer = RegimePerformanceAnalyzer(detector)
        json_str = analyzer.export_to_json()

        import json

        data = json.loads(json_str)
        assert "regime_statistics" in data
        assert "SIDEWAYS" in data["regime_statistics"]

    def test_export_to_csv(self, detector):
        """export_to_csv should return valid CSV string."""
        c = create_completed_campaign(MarketRegime.SIDEWAYS, Decimal("2.0"))
        detector._add_to_indexes(c)

        analyzer = RegimePerformanceAnalyzer(detector)
        csv_str = analyzer.export_to_csv()

        lines = csv_str.strip().split("\n")
        assert len(lines) > 1  # Header + data
        assert "regime,total_campaigns,win_rate" in lines[0]


class TestRegimeTransitionWarnings:
    """Tests for regime transition warnings (AC4)."""

    def test_no_warning_same_regime(self, detector):
        """No warning when staying in same regime."""
        analyzer = RegimePerformanceAnalyzer(detector)
        warning = analyzer.get_regime_transition_warning(
            MarketRegime.SIDEWAYS, MarketRegime.SIDEWAYS
        )
        assert warning is None

    def test_high_volatility_warning(self, detector):
        """Warning when transitioning to HIGH_VOLATILITY."""
        analyzer = RegimePerformanceAnalyzer(detector)
        warning = analyzer.get_regime_transition_warning(
            MarketRegime.SIDEWAYS, MarketRegime.HIGH_VOLATILITY
        )

        assert warning is not None
        assert "High volatility" in warning
        assert "20%" in warning

    def test_trending_warning(self, detector):
        """Warning when transitioning to trending regime."""
        analyzer = RegimePerformanceAnalyzer(detector)
        warning = analyzer.get_regime_transition_warning(
            MarketRegime.SIDEWAYS, MarketRegime.TRENDING_UP
        )

        assert warning is not None
        assert "trending" in warning.lower()
        assert "0.8" in warning


class TestStatisticsCache:
    """Tests for statistics caching behavior."""

    def test_cache_valid_within_ttl(self, detector):
        """Cache should be valid within TTL."""
        analyzer = RegimePerformanceAnalyzer(detector, cache_ttl_seconds=3600)

        # First call populates cache
        stats1 = analyzer.get_regime_statistics()

        # Add campaign after cache
        c = create_completed_campaign(MarketRegime.SIDEWAYS, Decimal("2.0"))
        detector._add_to_indexes(c)

        # Second call should return cached (stale) data
        stats2 = analyzer.get_regime_statistics()

        # Cache not invalidated, so should still show 0
        assert stats2[MarketRegime.SIDEWAYS]["total_campaigns"] == 0

    def test_cache_invalidation(self, detector):
        """invalidate_cache should force fresh calculation."""
        analyzer = RegimePerformanceAnalyzer(detector)

        # First call
        stats1 = analyzer.get_regime_statistics()

        # Add campaign
        c = create_completed_campaign(MarketRegime.SIDEWAYS, Decimal("2.0"))
        detector._add_to_indexes(c)

        # Invalidate cache
        analyzer.invalidate_cache()

        # Now should see new campaign
        stats2 = analyzer.get_regime_statistics()
        assert stats2[MarketRegime.SIDEWAYS]["total_campaigns"] == 1


class TestFilterCampaignsByRegime:
    """Tests for filter_campaigns_by_regime method."""

    def test_filter_by_regime(self, detector):
        """Should filter campaigns by specified regime."""
        sideways = create_completed_campaign(MarketRegime.SIDEWAYS, Decimal("2.0"))
        trending = create_completed_campaign(MarketRegime.TRENDING_UP, Decimal("1.0"))
        detector._add_to_indexes(sideways)
        detector._add_to_indexes(trending)

        analyzer = RegimePerformanceAnalyzer(detector)
        filtered = analyzer.filter_campaigns_by_regime(MarketRegime.SIDEWAYS)

        assert len(filtered) == 1
        assert filtered[0].market_regime == MarketRegime.SIDEWAYS

    def test_filter_excludes_forming_by_default(self, detector, sample_bar):
        """Should exclude FORMING campaigns by default."""
        # Add forming campaign via add_pattern
        spring = create_spring(sample_bar)
        detector.add_pattern(spring, market_regime=MarketRegime.SIDEWAYS)

        # Add completed campaign
        completed = create_completed_campaign(MarketRegime.SIDEWAYS, Decimal("2.0"))
        detector._add_to_indexes(completed)

        analyzer = RegimePerformanceAnalyzer(detector)
        filtered = analyzer.filter_campaigns_by_regime(MarketRegime.SIDEWAYS)

        # Should only include completed, not forming
        assert len(filtered) == 1
        assert filtered[0].state == CampaignState.COMPLETED

    def test_filter_includes_forming_when_specified(self, detector, sample_bar):
        """Should include FORMING campaigns when include_forming=True."""
        spring = create_spring(sample_bar)
        detector.add_pattern(spring, market_regime=MarketRegime.SIDEWAYS)

        analyzer = RegimePerformanceAnalyzer(detector)
        filtered = analyzer.filter_campaigns_by_regime(MarketRegime.SIDEWAYS, include_forming=True)

        assert len(filtered) == 1
        assert filtered[0].state == CampaignState.FORMING
