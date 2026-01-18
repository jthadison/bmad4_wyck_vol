"""
Integration tests for IntradayCampaignDetector Event Publishing (Story 15.6).

Tests cover:
1. CAMPAIGN_FORMED event on new campaign
2. PATTERN_DETECTED event on pattern addition
3. CAMPAIGN_ACTIVATED event on state transition
4. CAMPAIGN_COMPLETED event on completion
5. CAMPAIGN_FAILED event on expiration
6. Event metadata correctness
7. Event subscriber integration

Author: Developer Agent (Story 15.6 Implementation)
"""

import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from src.backtesting.event_publisher import EventPublisher
from src.backtesting.intraday_campaign_detector import (
    CampaignState,
    ExitReason,
    IntradayCampaignDetector,
)
from src.models.automatic_rally import AutomaticRally
from src.models.campaign_event import CampaignEvent, CampaignEventType
from src.models.lps import LPS
from src.models.ohlcv import OHLCVBar
from src.models.sos_breakout import SOSBreakout
from src.models.spring import Spring

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def event_publisher():
    """Create EventPublisher instance."""
    publisher = EventPublisher(max_queue_size=100)
    yield publisher
    publisher.shutdown(timeout=2.0)


@pytest.fixture
def detector_with_publisher(event_publisher):
    """Detector with event publisher configured."""
    return IntradayCampaignDetector(
        campaign_window_hours=48,
        max_pattern_gap_hours=48,
        min_patterns_for_active=2,
        expiration_hours=72,
        max_concurrent_campaigns=3,
        max_portfolio_heat_pct=Decimal("10.0"),
        event_publisher=event_publisher,
    )


@pytest.fixture
def detector_without_publisher():
    """Detector without event publisher (for comparison)."""
    return IntradayCampaignDetector(
        campaign_window_hours=48,
        max_pattern_gap_hours=48,
        min_patterns_for_active=2,
        expiration_hours=72,
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
    """Sample Spring pattern."""
    return Spring(
        bar=sample_bar,
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


@pytest.fixture
def sample_sos(sample_bar, base_timestamp):
    """Sample SOS breakout pattern."""
    sos_bar = OHLCVBar(
        timestamp=base_timestamp + timedelta(hours=2),
        open=Decimal("100.00"),
        high=Decimal("103.00"),
        low=Decimal("100.00"),
        close=Decimal("102.50"),
        volume=200000,
        spread=Decimal("3.00"),
        timeframe="15m",
        symbol="EUR/USD",
    )
    return SOSBreakout(
        bar=sos_bar,
        breakout_pct=Decimal("0.025"),
        volume_ratio=Decimal("2.0"),
        ice_reference=Decimal("100.00"),
        breakout_price=Decimal("102.50"),
        detection_timestamp=base_timestamp + timedelta(hours=2),
        trading_range_id=uuid4(),
        spread_ratio=Decimal("1.5"),
        close_position=Decimal("0.83"),
        spread=Decimal("3.00"),
    )


@pytest.fixture
def sample_lps(sample_bar, base_timestamp):
    """Sample LPS pattern."""
    lps_bar = OHLCVBar(
        timestamp=base_timestamp + timedelta(hours=5),
        open=Decimal("102.00"),
        high=Decimal("102.50"),
        low=Decimal("100.50"),
        close=Decimal("101.50"),
        volume=120000,
        spread=Decimal("2.00"),
        timeframe="15m",
        symbol="EUR/USD",
    )
    return LPS(
        bar=lps_bar,
        distance_from_ice=Decimal("0.015"),
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
        hold_level=Decimal("100.00"),
        hold_bars=2,
        confidence_score=Decimal("0.75"),
        lps_low=Decimal("100.50"),
        lps_high=Decimal("102.50"),
        detection_timestamp=base_timestamp + timedelta(hours=5),
        trading_range_id=uuid4(),
    )


@pytest.fixture
def high_quality_ar(sample_bar, base_timestamp):
    """High-quality AR pattern for activation tests."""
    ar_bar = OHLCVBar(
        timestamp=base_timestamp + timedelta(hours=1),
        open=Decimal("99.00"),
        high=Decimal("102.00"),
        low=Decimal("98.50"),
        close=Decimal("101.50"),
        volume=180000,
        spread=Decimal("3.50"),
        timeframe="15m",
        symbol="EUR/USD",
    )
    # SC reference for the AR
    sc_bar = OHLCVBar(
        timestamp=base_timestamp,
        open=Decimal("100.00"),
        high=Decimal("100.50"),
        low=Decimal("96.00"),
        close=Decimal("98.00"),
        volume=300000,
        spread=Decimal("4.50"),
        timeframe="15m",
        symbol="EUR/USD",
    )
    return AutomaticRally(
        bar=ar_bar.model_dump(),
        bar_index=11,
        rally_pct=Decimal("0.0625"),  # 6.25% rally from SC low
        bars_after_sc=3,
        sc_reference=sc_bar.model_dump(),
        sc_low=Decimal("96.00"),
        ar_high=Decimal("102.00"),
        volume_profile="HIGH",
        detection_timestamp=base_timestamp + timedelta(hours=1),
        quality_score=0.85,  # High quality for activation
        recovery_percent=Decimal("0.50"),
        volume_trend="DECLINING",
    )


# ============================================================================
# Test Cases
# ============================================================================


class TestCampaignFormedEvent:
    """Test CAMPAIGN_FORMED event publishing."""

    def test_campaign_formed_event_on_new_campaign(
        self, detector_with_publisher, event_publisher, sample_spring
    ):
        """Test that CAMPAIGN_FORMED event is published when new campaign is created."""
        received_events: list[CampaignEvent] = []

        def on_event(event: CampaignEvent):
            received_events.append(event)

        event_publisher.subscribe("CAMPAIGN_FORMED", on_event)

        # Add first pattern - should create new campaign
        campaign = detector_with_publisher.add_pattern(sample_spring)
        time.sleep(0.1)

        assert len(received_events) == 1
        event = received_events[0]
        assert event.event_type == CampaignEventType.CAMPAIGN_FORMED
        assert event.campaign_id == campaign.campaign_id
        assert event.pattern_type == "Spring"
        assert event.metadata["campaign_state"] == "FORMING"
        assert "strength_score" in event.metadata
        assert event.metadata["pattern_count"] == 1

    def test_no_event_without_publisher(self, detector_without_publisher, sample_spring):
        """Test that no errors occur when no publisher is configured."""
        # Should not raise any errors
        campaign = detector_without_publisher.add_pattern(sample_spring)
        assert campaign is not None
        assert campaign.state == CampaignState.FORMING


class TestPatternDetectedEvent:
    """Test PATTERN_DETECTED event publishing."""

    def test_pattern_detected_on_second_pattern(
        self, detector_with_publisher, event_publisher, sample_spring, sample_sos
    ):
        """Test PATTERN_DETECTED when adding pattern to existing campaign."""
        received_events: list[CampaignEvent] = []

        def on_event(event: CampaignEvent):
            received_events.append(event)

        event_publisher.subscribe("PATTERN_DETECTED", on_event)

        # Create campaign with first pattern
        detector_with_publisher.add_pattern(sample_spring)

        # Add second pattern
        campaign = detector_with_publisher.add_pattern(sample_sos)
        time.sleep(0.1)

        # Should have PATTERN_DETECTED for second pattern
        assert len(received_events) >= 1
        sos_event = [e for e in received_events if e.pattern_type == "SOSBreakout"]
        assert len(sos_event) == 1
        assert sos_event[0].campaign_id == campaign.campaign_id

    def test_pattern_detected_metadata(
        self, detector_with_publisher, event_publisher, sample_spring, sample_sos
    ):
        """Test that PATTERN_DETECTED has correct metadata."""
        received_events: list[CampaignEvent] = []

        def on_event(event: CampaignEvent):
            received_events.append(event)

        event_publisher.subscribe("PATTERN_DETECTED", on_event)

        detector_with_publisher.add_pattern(sample_spring)
        detector_with_publisher.add_pattern(sample_sos)
        time.sleep(0.1)

        sos_event = [e for e in received_events if e.pattern_type == "SOSBreakout"][0]
        assert "campaign_state" in sos_event.metadata
        assert "campaign_phase" in sos_event.metadata
        assert "pattern_count" in sos_event.metadata
        assert sos_event.metadata["pattern_count"] == 2


class TestCampaignActivatedEvent:
    """Test CAMPAIGN_ACTIVATED event publishing."""

    def test_campaign_activated_on_second_pattern(
        self, detector_with_publisher, event_publisher, sample_spring, sample_sos
    ):
        """Test CAMPAIGN_ACTIVATED when campaign transitions to ACTIVE."""
        received_events: list[CampaignEvent] = []

        def on_event(event: CampaignEvent):
            received_events.append(event)

        event_publisher.subscribe("CAMPAIGN_ACTIVATED", on_event)

        # First pattern - FORMING state
        detector_with_publisher.add_pattern(sample_spring)

        # Second pattern - should transition to ACTIVE
        campaign = detector_with_publisher.add_pattern(sample_sos)
        time.sleep(0.1)

        assert len(received_events) == 1
        event = received_events[0]
        assert event.event_type == CampaignEventType.CAMPAIGN_ACTIVATED
        assert event.campaign_id == campaign.campaign_id
        assert event.metadata["campaign_state"] == "ACTIVE"

    def test_campaign_activated_by_high_quality_ar(
        self, detector_with_publisher, event_publisher, sample_spring, high_quality_ar
    ):
        """Test CAMPAIGN_ACTIVATED when high-quality AR activates campaign."""
        received_events: list[CampaignEvent] = []

        def on_event(event: CampaignEvent):
            received_events.append(event)

        event_publisher.subscribe("CAMPAIGN_ACTIVATED", on_event)

        # First pattern
        detector_with_publisher.add_pattern(sample_spring)

        # High-quality AR should activate campaign
        campaign = detector_with_publisher.add_pattern(high_quality_ar)
        time.sleep(0.1)

        assert len(received_events) == 1
        event = received_events[0]
        assert event.event_type == CampaignEventType.CAMPAIGN_ACTIVATED
        assert event.pattern_type == "AutomaticRally"
        assert event.metadata.get("ar_quality_score") == 0.85


class TestCampaignCompletedEvent:
    """Test CAMPAIGN_COMPLETED event publishing."""

    def test_campaign_completed_event(
        self, detector_with_publisher, event_publisher, sample_spring, sample_sos
    ):
        """Test CAMPAIGN_COMPLETED when campaign is marked completed."""
        received_events: list[CampaignEvent] = []

        def on_event(event: CampaignEvent):
            received_events.append(event)

        event_publisher.subscribe("CAMPAIGN_COMPLETED", on_event)

        # Create active campaign
        detector_with_publisher.add_pattern(sample_spring)
        campaign = detector_with_publisher.add_pattern(sample_sos)

        # Mark as completed
        detector_with_publisher.mark_campaign_completed(
            campaign_id=campaign.campaign_id,
            exit_price=Decimal("105.00"),
            exit_reason=ExitReason.TARGET_HIT,
        )
        time.sleep(0.1)

        assert len(received_events) == 1
        event = received_events[0]
        assert event.event_type == CampaignEventType.CAMPAIGN_COMPLETED
        assert event.campaign_id == campaign.campaign_id
        assert event.metadata["exit_reason"] == "TARGET_HIT"
        assert event.metadata["exit_price"] == 105.0

    def test_campaign_completed_includes_metrics(
        self, detector_with_publisher, event_publisher, sample_spring, sample_sos
    ):
        """Test that CAMPAIGN_COMPLETED includes performance metrics."""
        received_events: list[CampaignEvent] = []

        def on_event(event: CampaignEvent):
            received_events.append(event)

        event_publisher.subscribe("CAMPAIGN_COMPLETED", on_event)

        detector_with_publisher.add_pattern(sample_spring)
        campaign = detector_with_publisher.add_pattern(sample_sos)

        detector_with_publisher.mark_campaign_completed(
            campaign_id=campaign.campaign_id,
            exit_price=Decimal("105.00"),
            exit_reason=ExitReason.TARGET_HIT,
        )
        time.sleep(0.1)

        event = received_events[0]
        assert "r_multiple" in event.metadata
        assert "points_gained" in event.metadata
        assert "duration_bars" in event.metadata


class TestCampaignFailedEvent:
    """Test CAMPAIGN_FAILED event publishing."""

    def test_campaign_failed_on_expiration(
        self, detector_with_publisher, event_publisher, sample_spring
    ):
        """Test CAMPAIGN_FAILED when campaign expires."""
        received_events: list[CampaignEvent] = []

        def on_event(event: CampaignEvent):
            received_events.append(event)

        event_publisher.subscribe("CAMPAIGN_FAILED", on_event)

        # Create campaign
        campaign = detector_with_publisher.add_pattern(sample_spring)

        # Expire campaigns (73 hours later)
        future_time = sample_spring.detection_timestamp + timedelta(hours=73)
        detector_with_publisher.expire_stale_campaigns(future_time)
        time.sleep(0.1)

        assert len(received_events) == 1
        event = received_events[0]
        assert event.event_type == CampaignEventType.CAMPAIGN_FAILED
        assert event.campaign_id == campaign.campaign_id
        assert "failure_reason" in event.metadata
        assert "hours_elapsed" in event.metadata


class TestWildcardSubscription:
    """Test wildcard event subscription."""

    def test_wildcard_receives_all_events(
        self, detector_with_publisher, event_publisher, sample_spring, sample_sos
    ):
        """Test that wildcard subscription receives all event types."""
        received_events: list[CampaignEvent] = []

        def on_all(event: CampaignEvent):
            received_events.append(event)

        event_publisher.subscribe("*", on_all)

        # Create and activate campaign
        detector_with_publisher.add_pattern(sample_spring)  # CAMPAIGN_FORMED
        campaign = detector_with_publisher.add_pattern(
            sample_sos
        )  # PATTERN_DETECTED + CAMPAIGN_ACTIVATED

        # Complete campaign
        detector_with_publisher.mark_campaign_completed(
            campaign_id=campaign.campaign_id,
            exit_price=Decimal("105.00"),
            exit_reason=ExitReason.TARGET_HIT,
        )  # CAMPAIGN_COMPLETED

        time.sleep(0.2)

        # Should have received all event types
        event_types = {e.event_type for e in received_events}
        assert CampaignEventType.CAMPAIGN_FORMED in event_types
        assert CampaignEventType.PATTERN_DETECTED in event_types
        assert CampaignEventType.CAMPAIGN_ACTIVATED in event_types
        assert CampaignEventType.CAMPAIGN_COMPLETED in event_types


class TestEventPublishingPerformance:
    """Test that event publishing doesn't impact pattern processing."""

    def test_add_pattern_with_publisher_same_result_as_without(
        self,
        detector_with_publisher,
        detector_without_publisher,
        sample_spring,
        sample_sos,
        event_publisher,
    ):
        """Test that adding patterns with publisher produces same campaigns."""
        # With publisher
        campaign_with = detector_with_publisher.add_pattern(sample_spring)
        detector_with_publisher.add_pattern(sample_sos)

        # Without publisher - use copies of patterns with new timestamps
        spring_copy = Spring(
            bar=sample_spring.bar,
            bar_index=sample_spring.bar_index,
            penetration_pct=sample_spring.penetration_pct,
            volume_ratio=sample_spring.volume_ratio,
            recovery_bars=sample_spring.recovery_bars,
            creek_reference=sample_spring.creek_reference,
            spring_low=sample_spring.spring_low,
            recovery_price=sample_spring.recovery_price,
            detection_timestamp=sample_spring.detection_timestamp,
            trading_range_id=sample_spring.trading_range_id,
        )

        sos_copy = SOSBreakout(
            bar=sample_sos.bar,
            breakout_pct=sample_sos.breakout_pct,
            volume_ratio=sample_sos.volume_ratio,
            ice_reference=sample_sos.ice_reference,
            breakout_price=sample_sos.breakout_price,
            detection_timestamp=sample_sos.detection_timestamp,
            trading_range_id=sample_sos.trading_range_id,
            spread_ratio=sample_sos.spread_ratio,
            close_position=sample_sos.close_position,
            spread=sample_sos.spread,
        )

        campaign_without = detector_without_publisher.add_pattern(spring_copy)
        detector_without_publisher.add_pattern(sos_copy)

        # Both should be ACTIVE with 2 patterns
        assert campaign_with.state == CampaignState.ACTIVE
        assert campaign_without.state == CampaignState.ACTIVE
        assert len(campaign_with.patterns) == 2
        assert len(campaign_without.patterns) == 2


class TestEventMetadataCorrectness:
    """Test that event metadata contains correct information."""

    def test_formed_event_has_correct_metadata(
        self, detector_with_publisher, event_publisher, sample_spring
    ):
        """Test CAMPAIGN_FORMED metadata correctness."""
        received_events: list[CampaignEvent] = []

        def on_event(event: CampaignEvent):
            received_events.append(event)

        event_publisher.subscribe("*", on_event)

        campaign = detector_with_publisher.add_pattern(sample_spring)
        time.sleep(0.1)

        formed_events = [
            e for e in received_events if e.event_type == CampaignEventType.CAMPAIGN_FORMED
        ]
        assert len(formed_events) == 1

        event = formed_events[0]
        assert event.metadata["campaign_state"] == "FORMING"
        assert event.metadata["pattern_count"] == 1
        # Strength score should be present (may be 0 or calculated value)
        assert "strength_score" in event.metadata
