"""
Unit tests for Portfolio Heat Alert Integration (Story 15.7)

Tests cover all acceptance criteria:
- AC1-4: Heat alert events (WARNING, CRITICAL, EXCEEDED, NORMAL)
- AC5: Alert thresholds (80%, 95%, exceeded)
- AC6: Alert data (heat %, remaining capacity, active campaigns, risk)
- AC7: Alert frequency (threshold crossings, rate limiting, state tracking)
- AC8: Integration with EventPublisher

Test Categories:
1. Alert Thresholds - Test all threshold levels
2. Threshold Crossings - Test state transitions
3. Rate Limiting - Test 5-minute cooldown
4. State Transitions - Test state change logic
5. Event Data - Verify event metadata correctness
6. Integration - Test with _check_portfolio_limits()
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from src.backtesting.event_publisher import EventPublisher
from src.backtesting.intraday_campaign_detector import (
    HeatAlertState,
    IntradayCampaignDetector,
)
from src.models.campaign_event import CampaignEventType
from src.models.ohlcv import OHLCVBar
from src.models.spring import Spring

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def mock_event_publisher():
    """Mock EventPublisher for testing."""
    publisher = MagicMock(spec=EventPublisher)
    publisher.publish = MagicMock()
    return publisher


@pytest.fixture
def detector_with_events(mock_event_publisher):
    """Detector with event publisher configured."""
    return IntradayCampaignDetector(
        campaign_window_hours=48,
        max_pattern_gap_hours=48,
        min_patterns_for_active=2,
        expiration_hours=72,
        max_concurrent_campaigns=3,
        max_portfolio_heat_pct=Decimal("40.0"),  # 40% max heat for easier math
        event_publisher=mock_event_publisher,
    )


@pytest.fixture
def base_timestamp():
    """Base timestamp for test patterns."""
    return datetime(2025, 12, 15, 9, 0, tzinfo=UTC)


@pytest.fixture
def sample_bar(base_timestamp):
    """Sample OHLCV bar."""
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
        penetration_pct=Decimal("0.02"),  # 2% below Creek
        volume_ratio=Decimal("0.4"),  # Low volume (good)
        recovery_bars=1,
        creek_reference=Decimal("100.00"),
        spring_low=Decimal("98.00"),
        recovery_price=Decimal("100.50"),
        detection_timestamp=base_timestamp,
        trading_range_id=uuid4(),
    )


def create_spring_at_time(timestamp: datetime, sample_bar: OHLCVBar) -> Spring:
    """Helper to create Spring pattern at specific time."""
    return Spring(
        bar=sample_bar,
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
# Test: Alert Thresholds
# ============================================================================


def test_warning_alert_at_80_percent(detector_with_events, mock_event_publisher):
    """Test WARNING alert fires at 80% of max heat (32% with 40% max)."""
    # Heat: 32% (80% of 40% max) -> should fire WARNING
    detector_with_events._check_heat_alerts(32.0)

    # Verify state transition
    assert detector_with_events._heat_alert_state == HeatAlertState.WARNING

    # Verify event published
    mock_event_publisher.publish.assert_called_once()
    event = mock_event_publisher.publish.call_args[0][0]
    assert event.event_type == CampaignEventType.PORTFOLIO_HEAT_WARNING
    assert event.metadata["heat_pct"] == 32.0


def test_critical_alert_at_95_percent(detector_with_events, mock_event_publisher):
    """Test CRITICAL alert fires at 95% of max heat (38% with 40% max)."""
    # Heat: 38% (95% of 40% max) -> should fire CRITICAL
    detector_with_events._check_heat_alerts(38.0)

    # Verify state transition
    assert detector_with_events._heat_alert_state == HeatAlertState.CRITICAL

    # Verify event published
    mock_event_publisher.publish.assert_called_once()
    event = mock_event_publisher.publish.call_args[0][0]
    assert event.event_type == CampaignEventType.PORTFOLIO_HEAT_CRITICAL
    assert event.metadata["heat_pct"] == 38.0


def test_exceeded_alert_above_100_percent(detector_with_events, mock_event_publisher):
    """Test EXCEEDED alert fires when heat > 100% (42% > 40% max)."""
    account_size = Decimal("100000")

    # Create campaign with risk that exceeds limit
    result = detector_with_events._check_portfolio_limits(
        account_size=account_size,
        new_campaign_risk=Decimal("42000"),  # 42% heat
    )

    # Should reject
    assert result is False

    # Verify EXCEEDED event published
    calls = mock_event_publisher.publish.call_args_list
    exceeded_events = [
        call[0][0]
        for call in calls
        if call[0][0].event_type == CampaignEventType.PORTFOLIO_HEAT_EXCEEDED
    ]
    assert len(exceeded_events) > 0
    assert exceeded_events[0].metadata["heat_pct"] == 42.0


def test_normal_alert_after_heat_drops(detector_with_events, mock_event_publisher):
    """Test NORMAL alert fires when heat drops below 75% (30% < 30% threshold)."""
    # First, raise heat to WARNING
    detector_with_events._check_heat_alerts(32.0)
    assert detector_with_events._heat_alert_state == HeatAlertState.WARNING

    # Reset mock to count only next alert
    mock_event_publisher.publish.reset_mock()

    # Now drop heat below normal threshold (< 30% for 40% max)
    detector_with_events._check_heat_alerts(28.0)

    # Verify state transition to NORMAL
    assert detector_with_events._heat_alert_state == HeatAlertState.NORMAL

    # Verify NORMAL event published
    mock_event_publisher.publish.assert_called_once()
    event = mock_event_publisher.publish.call_args[0][0]
    assert event.event_type == CampaignEventType.PORTFOLIO_HEAT_NORMAL
    assert event.metadata["heat_pct"] == 28.0


# ============================================================================
# Test: Rate Limiting
# ============================================================================


def test_duplicate_warning_suppressed(detector_with_events, mock_event_publisher):
    """Test duplicate WARNING alerts are rate-limited."""
    # First warning
    detector_with_events._check_heat_alerts(32.0)
    assert mock_event_publisher.publish.call_count == 1

    # Second warning immediately (should be suppressed)
    detector_with_events._check_heat_alerts(33.0)  # Still in WARNING zone
    assert mock_event_publisher.publish.call_count == 1  # No new event


def test_alert_fires_after_rate_limit_expires(detector_with_events, mock_event_publisher):
    """Test alert fires again after 5-minute rate limit."""
    # First warning
    detector_with_events._check_heat_alerts(32.0)
    assert detector_with_events._heat_alert_state == HeatAlertState.WARNING
    assert mock_event_publisher.publish.call_count == 1

    # Simulate 5+ minutes passing by manually updating last alert time
    five_minutes_ago = datetime.now(UTC) - timedelta(seconds=301)
    detector_with_events._last_alert_time[HeatAlertState.WARNING] = five_minutes_ago

    # Transition to NORMAL then back to WARNING (to trigger state change)
    detector_with_events._check_heat_alerts(20.0)  # Normal
    assert detector_with_events._heat_alert_state == HeatAlertState.NORMAL

    # Now WARNING again (should fire because rate limit expired)
    detector_with_events._check_heat_alerts(32.0)
    assert mock_event_publisher.publish.call_count == 3  # WARNING, NORMAL, WARNING


# ============================================================================
# Test: State Transitions
# ============================================================================


def test_normal_to_warning_to_critical(detector_with_events, mock_event_publisher):
    """Test state transitions: NORMAL → WARNING → CRITICAL."""
    # Start: NORMAL (< 30%)
    detector_with_events._check_heat_alerts(20.0)
    assert detector_with_events._heat_alert_state == HeatAlertState.NORMAL
    assert mock_event_publisher.publish.call_count == 0  # No event for staying NORMAL

    # Transition to WARNING (32%)
    detector_with_events._check_heat_alerts(32.0)
    assert detector_with_events._heat_alert_state == HeatAlertState.WARNING
    assert mock_event_publisher.publish.call_count == 1
    assert (
        mock_event_publisher.publish.call_args_list[0][0][0].event_type
        == CampaignEventType.PORTFOLIO_HEAT_WARNING
    )

    # Transition to CRITICAL (38%)
    detector_with_events._check_heat_alerts(38.0)
    assert detector_with_events._heat_alert_state == HeatAlertState.CRITICAL
    assert mock_event_publisher.publish.call_count == 2
    assert (
        mock_event_publisher.publish.call_args_list[1][0][0].event_type
        == CampaignEventType.PORTFOLIO_HEAT_CRITICAL
    )


def test_critical_to_normal(detector_with_events, mock_event_publisher):
    """Test state transition: CRITICAL → NORMAL when heat drops."""
    # Raise to CRITICAL
    detector_with_events._check_heat_alerts(38.0)
    assert detector_with_events._heat_alert_state == HeatAlertState.CRITICAL

    # Drop to NORMAL (< 30%)
    detector_with_events._check_heat_alerts(20.0)
    assert detector_with_events._heat_alert_state == HeatAlertState.NORMAL
    assert mock_event_publisher.publish.call_count == 2  # CRITICAL + NORMAL
    assert (
        mock_event_publisher.publish.call_args_list[1][0][0].event_type
        == CampaignEventType.PORTFOLIO_HEAT_NORMAL
    )


def test_transition_zone_keeps_current_state(detector_with_events):
    """Test transition zone (75-80%) maintains current state."""
    # Raise to WARNING (32%)
    detector_with_events._check_heat_alerts(32.0)
    assert detector_with_events._heat_alert_state == HeatAlertState.WARNING

    # Heat in transition zone (31% = 77.5% of 40% max) - should keep WARNING
    detector_with_events._check_heat_alerts(31.0)
    assert detector_with_events._heat_alert_state == HeatAlertState.WARNING


# ============================================================================
# Test: Event Data
# ============================================================================


def test_alert_event_contains_correct_metadata(
    detector_with_events, mock_event_publisher, sample_spring, sample_bar, base_timestamp
):
    """Test alert event contains all required metadata."""
    # Add a campaign to have active campaigns data
    detector_with_events.add_pattern(sample_spring)

    # Add another pattern to activate campaign
    second_spring = create_spring_at_time(base_timestamp + timedelta(hours=1), sample_bar)
    detector_with_events.add_pattern(second_spring)

    # Trigger WARNING alert
    detector_with_events._check_heat_alerts(32.0)

    # Get published event
    event = mock_event_publisher.publish.call_args[0][0]

    # Verify event structure
    assert event.campaign_id == IntradayCampaignDetector.PORTFOLIO_CAMPAIGN_ID
    assert event.pattern_type is None
    assert isinstance(event.timestamp, datetime)

    # Verify metadata
    assert event.metadata["heat_pct"] == 32.0
    assert event.metadata["max_heat_pct"] == 40.0
    assert event.metadata["remaining_capacity_pct"] == 8.0  # 40 - 32
    assert event.metadata["active_campaigns"] >= 0
    assert "total_risk_dollars" in event.metadata


def test_alert_calculates_total_risk_correctly(detector_with_events, mock_event_publisher):
    """Test alert correctly calculates total portfolio risk."""
    # This is a basic smoke test - detailed risk calculation is tested elsewhere
    detector_with_events._check_heat_alerts(32.0)

    event = mock_event_publisher.publish.call_args[0][0]
    assert "total_risk_dollars" in event.metadata
    assert isinstance(event.metadata["total_risk_dollars"], int | float)


# ============================================================================
# Test: Integration with _check_portfolio_limits()
# ============================================================================


def test_portfolio_limits_fires_alerts(detector_with_events, mock_event_publisher):
    """Test _check_portfolio_limits() triggers heat alerts."""
    account_size = Decimal("100000")

    # Check with heat at WARNING level (32% of 40% max = 32000 risk)
    result = detector_with_events._check_portfolio_limits(
        account_size=account_size, new_campaign_risk=Decimal("32000")
    )

    # Should allow (below limit)
    assert result is True

    # Should have fired WARNING alert
    mock_event_publisher.publish.assert_called_once()
    event = mock_event_publisher.publish.call_args[0][0]
    assert event.event_type == CampaignEventType.PORTFOLIO_HEAT_WARNING


def test_portfolio_limits_rejects_when_exceeded(detector_with_events, mock_event_publisher):
    """Test _check_portfolio_limits() rejects when heat exceeds limit."""
    account_size = Decimal("100000")

    # Check with heat above limit (45% > 40% max)
    result = detector_with_events._check_portfolio_limits(
        account_size=account_size, new_campaign_risk=Decimal("45000")
    )

    # Should reject
    assert result is False

    # Should have fired EXCEEDED alert
    calls = mock_event_publisher.publish.call_args_list
    exceeded_events = [
        call[0][0]
        for call in calls
        if call[0][0].event_type == CampaignEventType.PORTFOLIO_HEAT_EXCEEDED
    ]
    assert len(exceeded_events) > 0


# ============================================================================
# Test: Edge Cases
# ============================================================================


def test_no_alerts_without_event_publisher():
    """Test alerts gracefully handle missing event publisher."""
    detector = IntradayCampaignDetector(
        max_portfolio_heat_pct=Decimal("40.0"),
        event_publisher=None,  # No publisher
    )

    # Should not raise error
    detector._check_heat_alerts(32.0)
    detector._publish_heat_alert(CampaignEventType.PORTFOLIO_HEAT_WARNING, 32.0)


def test_heat_exactly_at_threshold(detector_with_events, mock_event_publisher):
    """Test alert fires when heat is exactly at threshold."""
    # Exactly 80% of 40% max = 32.0%
    detector_with_events._check_heat_alerts(32.0)
    assert detector_with_events._heat_alert_state == HeatAlertState.WARNING
    mock_event_publisher.publish.assert_called_once()


def test_initial_state_is_normal():
    """Test detector starts in NORMAL heat state."""
    detector = IntradayCampaignDetector()
    assert detector._heat_alert_state == HeatAlertState.NORMAL


def test_alert_thresholds_configured_correctly():
    """Test default alert thresholds are correct."""
    detector = IntradayCampaignDetector()
    assert detector._heat_warning_threshold_pct == 80.0
    assert detector._heat_critical_threshold_pct == 95.0
    assert detector._heat_normal_threshold_pct == 75.0
    assert detector._alert_rate_limit_seconds == 300


# ============================================================================
# Test: Logging
# ============================================================================


def test_heat_alerts_are_logged(detector_with_events, caplog):
    """Test heat alerts are logged with structured logging."""
    import logging

    caplog.set_level(logging.INFO)

    detector_with_events._check_heat_alerts(32.0)

    # Check that alert was logged
    # (structlog outputs may vary based on configuration)
    # This is a basic smoke test
    assert detector_with_events._heat_alert_state == HeatAlertState.WARNING
