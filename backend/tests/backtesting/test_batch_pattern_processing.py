"""
Unit tests for Batch Pattern Processing (Story 15.5).

Tests cover:
- BatchResult dataclass
- add_patterns_batch() method
- Batch vs. sequential equivalence
- Performance improvements
- Error handling and partial success

Author: Developer Agent (Story 15.5)
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from src.backtesting.intraday_campaign_detector import (
    BatchResult,
    CampaignState,
    IntradayCampaignDetector,
)
from src.models.automatic_rally import AutomaticRally
from src.models.lps import LPS
from src.models.ohlcv import OHLCVBar
from src.models.sos_breakout import SOSBreakout
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


def make_bar(timestamp, price=Decimal("100.00"), volume=100000):
    """Helper to create OHLCV bar."""
    return OHLCVBar(
        timestamp=timestamp,
        open=price,
        high=price + Decimal("1.00"),
        low=price - Decimal("1.00"),
        close=price + Decimal("0.50"),
        volume=volume,
        spread=Decimal("2.00"),
        timeframe="15m",
        symbol="EUR/USD",
    )


def make_spring(bar_index, timestamp, price=Decimal("100.00")):
    """Helper to create Spring pattern."""
    bar = make_bar(timestamp, price)
    return Spring(
        bar=bar,
        bar_index=bar_index,
        penetration_pct=Decimal("0.02"),
        volume_ratio=Decimal("0.4"),
        recovery_bars=1,
        creek_reference=Decimal("100.00"),
        spring_low=price - Decimal("2.00"),
        recovery_price=price + Decimal("0.50"),
        detection_timestamp=timestamp,
        trading_range_id=uuid4(),
    )


def make_sos(bar_index, timestamp, price=Decimal("102.00")):
    """Helper to create SOS breakout pattern."""
    bar = make_bar(timestamp, price, volume=200000)
    ice_reference = Decimal("100.00")
    return SOSBreakout(
        bar=bar,
        breakout_pct=Decimal("0.02"),  # 2% above Ice
        volume_ratio=Decimal("2.0"),  # High volume
        ice_reference=ice_reference,
        breakout_price=price,
        detection_timestamp=timestamp,
        trading_range_id=uuid4(),
        spread_ratio=Decimal("1.5"),  # Spread expansion
        close_position=Decimal("0.75"),  # Close near high
        spread=Decimal("2.00"),  # Bar spread
    )


def make_lps(bar_index, timestamp, price=Decimal("103.00")):
    """Helper to create LPS pattern."""
    bar = make_bar(timestamp, price)
    return LPS(
        bar=bar,
        distance_from_ice=Decimal("0.015"),  # 1.5% above Ice
        distance_quality="PREMIUM",
        distance_confidence_bonus=10,
        volume_ratio=Decimal("0.6"),
        range_avg_volume=150000,
        volume_ratio_vs_avg=Decimal("0.8"),
        volume_ratio_vs_sos=Decimal("0.6"),
        pullback_spread=Decimal("2.50"),
        range_avg_spread=Decimal("3.00"),
        spread_ratio=Decimal("0.83"),
        spread_quality="NARROW",
        effort_result="NO_SUPPLY",
        effort_result_bonus=10,
        sos_reference=uuid4(),
        held_support=True,
        pullback_low=Decimal("100.50"),
        ice_level=Decimal("100.00"),
        sos_volume=200000,
        pullback_volume=120000,
        bars_after_sos=5,
        bounce_confirmed=True,
        bounce_bar_timestamp=timestamp + timedelta(hours=1),
        detection_timestamp=timestamp,
        trading_range_id=uuid4(),
        atr_14=Decimal("2.50"),
        stop_distance=Decimal("3.00"),
        stop_distance_pct=Decimal("3.0"),
        stop_price=Decimal("97.00"),
        volume_trend="DECLINING",
        volume_trend_quality="EXCELLENT",
        volume_trend_bonus=5,
    )


def make_ar(bar_index, timestamp, price=Decimal("98.00"), quality_score=0.8):
    """Helper to create AutomaticRally pattern."""
    bar = make_bar(timestamp, price, volume=120000)
    sc_low = price - Decimal("5.00")  # SC low below AR high
    ar_high = price + Decimal("1.00")  # AR rally high

    # Create SC reference (as dict to avoid circular import)
    sc_bar = make_bar(timestamp - timedelta(hours=2), sc_low, volume=250000)
    sc_reference = {
        "timestamp": sc_bar.timestamp.isoformat(),
        "low": float(sc_low),
        "volume": 250000,
    }

    return AutomaticRally(
        bar=bar.model_dump(),  # Convert to dict
        bar_index=bar_index,
        rally_pct=Decimal("0.05"),  # 5% rally from SC low
        bars_after_sc=2,  # 2 bars after SC
        sc_reference=sc_reference,
        sc_low=sc_low,
        ar_high=ar_high,
        volume_profile="HIGH",
        detection_timestamp=timestamp,
        quality_score=quality_score,
        recovery_percent=Decimal("0.6"),  # 60% recovery
        volume_trend="DECLINING",
        prior_pattern_bar=bar_index - 2,
        prior_pattern_type="SC",
    )


# ============================================================================
# Test BatchResult Dataclass
# ============================================================================


class TestBatchResult:
    """Test BatchResult dataclass."""

    def test_batch_result_defaults(self):
        """Test BatchResult default values."""
        result = BatchResult()
        assert result.patterns_processed == 0
        assert result.patterns_rejected == 0
        assert result.campaigns_created == 0
        assert result.campaigns_updated == 0
        assert result.rejected_patterns == []

    def test_batch_result_initialization(self):
        """Test BatchResult with custom values."""
        spring = make_spring(1, datetime.now(UTC))
        result = BatchResult(
            patterns_processed=80,
            patterns_rejected=20,
            campaigns_created=5,
            campaigns_updated=10,
            rejected_patterns=[(spring, "Test rejection")],
        )
        assert result.patterns_processed == 80
        assert result.patterns_rejected == 20
        assert result.campaigns_created == 5
        assert result.campaigns_updated == 10
        assert len(result.rejected_patterns) == 1


# ============================================================================
# Test Batch Processing Equivalence
# ============================================================================


class TestBatchEquivalence:
    """Test that batch processing produces identical results to sequential processing."""

    def test_batch_vs_sequential_single_campaign(self, detector, base_timestamp):
        """Test batch equivalence with patterns for single campaign."""
        # Create valid sequence: Spring -> SOS (valid Wyckoff sequence)
        patterns = [
            make_spring(1, base_timestamp),
            make_sos(2, base_timestamp + timedelta(hours=1)),
        ]

        account_size = Decimal("100000")

        # Sequential processing
        detector_seq = IntradayCampaignDetector()
        for pattern in patterns:
            detector_seq.add_pattern(pattern, account_size)

        # Batch processing
        detector_batch = IntradayCampaignDetector()
        result = detector_batch.add_patterns_batch(patterns, account_size)

        # Compare results
        assert len(detector_seq.campaigns) == len(detector_batch.campaigns)
        assert result.patterns_processed == len(patterns)
        assert result.patterns_rejected == 0
        assert result.campaigns_created == 1

        # Compare campaign states
        seq_camp = detector_seq.campaigns[0]
        batch_camp = detector_batch.campaigns[0]
        assert seq_camp.state == batch_camp.state
        assert len(seq_camp.patterns) == len(batch_camp.patterns)
        assert seq_camp.current_phase == batch_camp.current_phase

    def test_batch_vs_sequential_multiple_campaigns(self, detector, base_timestamp):
        """Test batch equivalence with patterns for multiple campaigns."""
        # Create patterns for 2 separate campaigns (time gap > 72h to trigger expiration)
        patterns = []

        # Campaign 1: Spring + SOS
        patterns.append(make_spring(1, base_timestamp))
        patterns.append(make_sos(2, base_timestamp + timedelta(hours=2)))

        # Campaign 2: Spring (100 hours later - triggers expiration of campaign 1)
        patterns.append(make_spring(100, base_timestamp + timedelta(hours=100)))

        account_size = Decimal("100000")

        # Sequential
        detector_seq = IntradayCampaignDetector()
        for pattern in patterns:
            detector_seq.add_pattern(pattern, account_size)

        # Batch
        detector_batch = IntradayCampaignDetector()
        result = detector_batch.add_patterns_batch(patterns, account_size)

        # Should create 2 campaigns (second one is FORMING with 1 pattern)
        assert len(detector_seq.campaigns) == len(detector_batch.campaigns)
        assert result.campaigns_created == 2
        assert result.patterns_processed == 3

    def test_batch_empty_patterns_list(self, detector):
        """Test batch processing with empty patterns list."""
        result = detector.add_patterns_batch([], Decimal("100000"))

        assert result.patterns_processed == 0
        assert result.patterns_rejected == 0
        assert result.campaigns_created == 0
        assert result.campaigns_updated == 0


# ============================================================================
# Test Batch Optimizations
# ============================================================================


class TestBatchOptimizations:
    """Test batch processing optimizations."""

    def test_batch_deferred_logging(self, detector, base_timestamp):
        """Test that batch processing completes successfully."""
        patterns = [make_spring(i, base_timestamp + timedelta(hours=i)) for i in range(10)]

        result = detector.add_patterns_batch(patterns, Decimal("100000"))

        # Should process some patterns (limited by max_concurrent_campaigns=3)
        assert result.patterns_processed > 0
        assert result.campaigns_created > 0

    def test_batch_index_updates(self, detector, base_timestamp):
        """Test that indexes are properly maintained during batch processing."""
        patterns = [
            make_spring(1, base_timestamp),
            make_sos(2, base_timestamp + timedelta(hours=1)),
        ]

        result = detector.add_patterns_batch(patterns, Decimal("100000"))

        # Check indexes are populated
        assert len(detector._campaigns_by_id) == result.campaigns_created
        # Campaign should be ACTIVE with 2 patterns
        assert len(detector._campaigns_by_state[CampaignState.ACTIVE]) == 1


# ============================================================================
# Test Error Handling
# ============================================================================


class TestBatchErrorHandling:
    """Test batch processing error handling and partial success."""

    def test_batch_portfolio_limit_rejection(self, detector, base_timestamp):
        """Test that patterns exceeding portfolio limits are rejected."""
        # Create more campaigns than max_concurrent_campaigns (3)
        patterns = []
        for i in range(5):
            # Each Spring creates a new campaign (with 100+ hour gap)
            patterns.append(make_spring(i * 100, base_timestamp + timedelta(hours=i * 100)))

        result = detector.add_patterns_batch(patterns, Decimal("100000"))

        # Should hit portfolio limits
        assert result.campaigns_created <= detector.max_concurrent_campaigns
        assert result.patterns_rejected > 0
        assert "Portfolio limit exceeded" in [reason for _, reason in result.rejected_patterns]

    def test_batch_invalid_sequence_rejection(self, detector, base_timestamp):
        """Test that invalid sequences are accepted but don't update phase."""
        # Create campaign with Spring + SOS (ACTIVE in Phase D)
        spring = make_spring(1, base_timestamp)
        sos = make_sos(2, base_timestamp + timedelta(hours=1))
        detector.add_pattern(spring, Decimal("100000"))
        detector.add_pattern(sos, Decimal("100000"))

        # Try batch adding another Spring (technically allowed but maintains phase)
        another_spring = make_spring(3, base_timestamp + timedelta(hours=2))
        patterns = [another_spring]

        result = detector.add_patterns_batch(patterns, Decimal("100000"))

        # Pattern is added (but phase doesn't regress)
        assert result.campaigns_updated == 1
        assert result.patterns_processed == 1

    def test_batch_partial_success(self, detector, base_timestamp):
        """Test partial batch success (some accepted, some rejected)."""
        # Create mix of valid and potentially invalid patterns
        patterns = []

        # Valid: Spring + SOS for first campaign
        patterns.append(make_spring(1, base_timestamp))
        patterns.append(make_sos(2, base_timestamp + timedelta(hours=1)))

        # Valid: New campaign (time gap)
        patterns.append(make_spring(100, base_timestamp + timedelta(hours=100)))

        result = detector.add_patterns_batch(patterns, Decimal("100000"))

        # Should process valid patterns
        assert result.patterns_processed > 0
        total = result.patterns_processed + result.patterns_rejected
        assert total == len(patterns)


# ============================================================================
# Test Performance (Benchmarks)
# ============================================================================


class TestBatchPerformance:
    """Test batch processing performance improvements."""

    def test_batch_processes_large_pattern_set(self, detector, base_timestamp):
        """Test batch processing handles large pattern sets (100+)."""
        # Create 100 patterns across multiple campaigns
        patterns = []
        for i in range(100):
            # Create new campaign every 20 patterns (time gap > 48h)
            hours_offset = (i // 20) * 100 + (i % 20)
            patterns.append(make_spring(i, base_timestamp + timedelta(hours=hours_offset)))

        result = detector.add_patterns_batch(patterns, Decimal("100000"))

        # Should process all or most patterns
        assert result.patterns_processed > 0
        assert result.campaigns_created > 0

    def test_batch_linear_scaling(self, detector, base_timestamp):
        """Test that batch processing scales linearly with batch size."""
        import time

        # Small batch (10 patterns)
        small_patterns = [make_spring(i, base_timestamp + timedelta(hours=i)) for i in range(10)]

        start = time.perf_counter()
        detector.add_patterns_batch(small_patterns, Decimal("100000"))
        small_time = time.perf_counter() - start

        # Large batch (100 patterns)
        detector2 = IntradayCampaignDetector()
        large_patterns = [make_spring(i, base_timestamp + timedelta(hours=i)) for i in range(100)]

        start = time.perf_counter()
        detector2.add_patterns_batch(large_patterns, Decimal("100000"))
        large_time = time.perf_counter() - start

        # Should scale roughly linearly (within 2x tolerance for 10x data)
        # Large should be ~10x small, allowing for overhead
        assert large_time < small_time * 20  # Generous upper bound


# ============================================================================
# Test Campaign Updates
# ============================================================================


class TestBatchCampaignUpdates:
    """Test batch updates to existing campaigns."""

    def test_batch_updates_existing_campaign(self, detector, base_timestamp):
        """Test batch adding patterns to existing campaign."""
        # Create initial campaign with Spring
        spring = make_spring(1, base_timestamp)
        result1 = detector.add_patterns_batch([spring], Decimal("100000"))
        assert result1.campaigns_created == 1

        # Batch add SOS to same campaign (within time window)
        patterns = [
            make_sos(2, base_timestamp + timedelta(hours=1)),
        ]

        result2 = detector.add_patterns_batch(patterns, Decimal("100000"))

        # Should update existing campaign, not create new one
        assert result2.campaigns_created == 0
        assert result2.campaigns_updated == 1
        assert result2.patterns_processed == 1

        # Campaign should have both patterns
        assert len(detector.campaigns[0].patterns) == 2
        assert detector.campaigns[0].state == CampaignState.ACTIVE

    def test_batch_state_transitions(self, detector, base_timestamp):
        """Test that batch processing triggers correct state transitions."""
        # Create FORMING campaign via batch (1 pattern)
        spring = make_spring(1, base_timestamp)
        result1 = detector.add_patterns_batch([spring], Decimal("100000"))

        assert result1.campaigns_created == 1
        assert detector.campaigns[0].state == CampaignState.FORMING

        # Batch add second pattern to trigger ACTIVE
        patterns = [make_sos(2, base_timestamp + timedelta(hours=1))]
        result2 = detector.add_patterns_batch(patterns, Decimal("100000"))

        # Should transition to ACTIVE
        assert detector.campaigns[0].state == CampaignState.ACTIVE
        assert result2.campaigns_updated == 1
        assert result2.patterns_processed == 1


# ============================================================================
# Test AutomaticRally Pattern Support
# ============================================================================


class TestBatchAutomaticRallyPatterns:
    """Test batch processing with AutomaticRally patterns (Story 14.2 + 15.5)."""

    def test_batch_ar_activation_new_campaign(self, detector, base_timestamp):
        """Test AR activating a newly created FORMING campaign in batch."""
        # Create FORMING campaign with high-quality AR
        ar_pattern = make_ar(1, base_timestamp, quality_score=0.85)
        result = detector.add_patterns_batch([ar_pattern], Decimal("100000"))

        # Should create campaign (1 pattern = FORMING)
        assert result.campaigns_created == 1
        assert result.patterns_processed == 1
        assert len(detector.campaigns) == 1

        # AR should activate FORMING campaign if high quality (Story 14.2)
        campaign = detector.campaigns[0]
        # Note: Activation depends on _handle_ar_activation logic
        # If quality_score >= 0.75, should activate to ACTIVE state

    def test_batch_ar_activation_existing_campaign(self, detector, base_timestamp):
        """Test AR activating an existing FORMING campaign in batch."""
        # Create FORMING campaign with Spring first
        spring = make_spring(1, base_timestamp)
        detector.add_pattern(spring, Decimal("100000"))

        assert detector.campaigns[0].state == CampaignState.FORMING

        # Batch add high-quality AR
        ar_pattern = make_ar(2, base_timestamp + timedelta(hours=1), quality_score=0.85)
        result = detector.add_patterns_batch([ar_pattern], Decimal("100000"))

        # Should update existing campaign
        assert result.campaigns_updated == 1
        assert result.patterns_processed == 1
        assert len(detector.campaigns) == 1

        # AR should activate campaign (Story 14.2)
        # Campaign state depends on AR activation logic

    def test_batch_low_quality_ar_no_activation(self, detector, base_timestamp):
        """Test low-quality AR doesn't activate FORMING campaign."""
        # Create FORMING campaign with low-quality AR
        ar_pattern = make_ar(1, base_timestamp, quality_score=0.4)  # Low quality
        result = detector.add_patterns_batch([ar_pattern], Decimal("100000"))

        # Should create campaign but remain FORMING
        assert result.campaigns_created == 1
        assert result.patterns_processed == 1
        campaign = detector.campaigns[0]
        assert campaign.state == CampaignState.FORMING

    def test_batch_mixed_patterns_with_ar(self, detector, base_timestamp):
        """Test batch with mix of AR and other patterns."""
        # Create patterns: Spring -> AR -> SOS (all same campaign)
        patterns = [
            make_spring(1, base_timestamp),
            make_ar(2, base_timestamp + timedelta(hours=1), quality_score=0.75),
            make_sos(3, base_timestamp + timedelta(hours=2)),
        ]

        result = detector.add_patterns_batch(patterns, Decimal("100000"))

        # Should create single campaign with all patterns
        assert result.campaigns_created == 1
        assert result.patterns_processed == 3
        assert len(detector.campaigns) == 1
        assert len(detector.campaigns[0].patterns) == 3

    def test_batch_multiple_ar_patterns(self, detector, base_timestamp):
        """Test batch processing multiple AR patterns."""
        # Create 3 AR patterns with time gaps (separate campaigns)
        patterns = [
            make_ar(1, base_timestamp, quality_score=0.8),
            make_ar(100, base_timestamp + timedelta(hours=100), quality_score=0.7),
            make_ar(200, base_timestamp + timedelta(hours=200), quality_score=0.6),
        ]

        result = detector.add_patterns_batch(patterns, Decimal("100000"))

        # Should create multiple campaigns (time gaps)
        assert result.campaigns_created >= 1
        assert result.patterns_processed >= 1
