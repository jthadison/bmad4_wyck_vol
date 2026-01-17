"""
Unit tests for IntradayCampaignDetector (Story 13.4)

Tests cover all acceptance criteria:
- AC4.1-AC4.8: Core campaign detection
- AC4.9: Risk metadata extraction
- AC4.10: Sequence-based phase assignment
- AC4.11: Portfolio risk management

Test Categories:
1. Campaign Creation & State Transitions (AC4.1-AC4.3)
2. Time Window Grouping (AC4.2, AC4.5)
3. Active Campaign Retrieval (AC4.4)
4. Campaign Expiration (AC4.7)
5. Pattern Sequence Validation (AC4.8, AC4.10)
6. Risk Metadata Extraction (AC4.9)
7. Portfolio Limits Enforcement (AC4.11)
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from src.backtesting.intraday_campaign_detector import (
    CampaignState,
    IntradayCampaignDetector,
)
from src.models.lps import LPS
from src.models.ohlcv import OHLCVBar
from src.models.sos_breakout import SOSBreakout
from src.models.spring import Spring
from src.models.wyckoff_phase import WyckoffPhase

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
        max_portfolio_heat_pct=10.0,  # FR7.7/AC7.14
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
        spread=Decimal("2.00"),  # high - low = 101 - 99
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
        spread=Decimal("3.00"),  # high - low = 103 - 100
        timeframe="15m",
        symbol="EUR/USD",
    )
    return SOSBreakout(
        bar=sos_bar,
        breakout_pct=Decimal("0.025"),  # 2.5% above Ice
        volume_ratio=Decimal("2.0"),  # High volume (good)
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
        spread=Decimal("2.00"),  # high - low = 102.5 - 100.5
        timeframe="15m",
        symbol="EUR/USD",
    )
    return LPS(
        bar=lps_bar,
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
        bounce_bar_timestamp=base_timestamp + timedelta(hours=6),
        detection_timestamp=base_timestamp + timedelta(hours=5),
        trading_range_id=uuid4(),
        atr_14=Decimal("2.50"),
        stop_distance=Decimal("3.00"),
        stop_distance_pct=Decimal("3.0"),
        stop_price=Decimal("97.00"),
        volume_trend="DECLINING",
        volume_trend_quality="EXCELLENT",
        volume_trend_bonus=5,
    )


# ============================================================================
# AC4.1: Campaign Creation from First Pattern
# ============================================================================


def test_campaign_creation_from_first_spring(detector, sample_spring):
    """AC4.1: First Spring pattern creates campaign in FORMING state."""
    detector.add_pattern(sample_spring)

    campaigns = detector.get_active_campaigns()
    assert len(campaigns) == 1
    assert campaigns[0].state == CampaignState.FORMING
    assert len(campaigns[0].patterns) == 1
    assert isinstance(campaigns[0].patterns[0], Spring)


def test_campaign_creation_from_first_sos(detector, sample_sos):
    """AC4.1: First SOS pattern creates campaign in FORMING state."""
    detector.add_pattern(sample_sos)

    campaigns = detector.get_active_campaigns()
    assert len(campaigns) == 1
    assert campaigns[0].state == CampaignState.FORMING
    assert len(campaigns[0].patterns) == 1
    assert isinstance(campaigns[0].patterns[0], SOSBreakout)


def test_campaign_creation_from_first_lps(detector, sample_lps):
    """AC4.1: First LPS pattern creates campaign in FORMING state."""
    detector.add_pattern(sample_lps)

    campaigns = detector.get_active_campaigns()
    assert len(campaigns) == 1
    assert campaigns[0].state == CampaignState.FORMING
    assert len(campaigns[0].patterns) == 1
    assert isinstance(campaigns[0].patterns[0], LPS)


# ============================================================================
# AC4.2, AC4.3: Campaign Grouping and State Transitions
# ============================================================================


def test_campaign_transition_to_active(detector, sample_spring, sample_sos):
    """AC4.3: Campaign transitions to ACTIVE when 2+ patterns detected."""
    detector.add_pattern(sample_spring)
    detector.add_pattern(sample_sos)

    campaigns = detector.get_active_campaigns()
    assert len(campaigns) == 1
    assert campaigns[0].state == CampaignState.ACTIVE
    assert len(campaigns[0].patterns) == 2


def test_patterns_grouped_within_48h_window(detector, sample_spring, base_timestamp):
    """AC4.2, AC4.5: Patterns within 48h window grouped into same campaign."""
    detector.add_pattern(sample_spring)

    # Add SOS 24 hours later (within 48h window)
    sos_bar = OHLCVBar(
        timestamp=base_timestamp + timedelta(hours=24),
        open=Decimal("100.00"),
        high=Decimal("103.00"),
        low=Decimal("100.00"),
        close=Decimal("102.50"),
        volume=200000,
        spread=Decimal("3.00"),  # high - low
        timeframe="15m",
        symbol="EUR/USD",
    )
    sos = SOSBreakout(
        bar=sos_bar,
        breakout_pct=Decimal("0.025"),
        volume_ratio=Decimal("2.0"),
        ice_reference=Decimal("100.00"),
        breakout_price=Decimal("102.50"),
        detection_timestamp=base_timestamp + timedelta(hours=24),
        trading_range_id=uuid4(),
        spread_ratio=Decimal("1.5"),
        close_position=Decimal("0.83"),
        spread=Decimal("3.00"),
    )
    detector.add_pattern(sos)

    campaigns = detector.get_active_campaigns()
    assert len(campaigns) == 1  # Same campaign
    assert len(campaigns[0].patterns) == 2


def test_patterns_outside_48h_window_create_new_campaign(
    detector, sample_spring, base_timestamp, sample_bar
):
    """AC4.2, AC4.5: Patterns outside 48h window create new campaign."""
    detector.add_pattern(sample_spring)

    # Add SOS 50 hours later (outside 48h window)
    sos_bar = OHLCVBar(
        timestamp=base_timestamp + timedelta(hours=50),
        open=Decimal("100.00"),
        high=Decimal("103.00"),
        low=Decimal("100.00"),
        close=Decimal("102.50"),
        volume=200000,
        spread=Decimal("3.00"),  # high - low
        timeframe="15m",
        symbol="EUR/USD",
    )
    sos = SOSBreakout(
        bar=sos_bar,
        breakout_pct=Decimal("0.025"),
        volume_ratio=Decimal("2.0"),
        ice_reference=Decimal("100.00"),
        breakout_price=Decimal("102.50"),
        detection_timestamp=base_timestamp + timedelta(hours=50),
        trading_range_id=uuid4(),
        spread_ratio=Decimal("1.5"),
        close_position=Decimal("0.83"),
        spread=Decimal("3.00"),
    )
    detector.add_pattern(sos)

    campaigns = detector.get_active_campaigns()
    assert len(campaigns) == 2  # New campaign created
    assert campaigns[0].state == CampaignState.FORMING  # First campaign still FORMING
    assert campaigns[1].state == CampaignState.FORMING  # Second campaign FORMING


def test_max_pattern_gap_enforced(detector, sample_spring, base_timestamp, sample_bar):
    """AC4.5: Max 48h gap between patterns enforced."""
    detector.add_pattern(sample_spring)

    # Add second Spring within gap
    spring2_bar = OHLCVBar(
        timestamp=base_timestamp + timedelta(hours=10),
        open=Decimal("100.00"),
        high=Decimal("101.00"),
        low=Decimal("98.50"),
        close=Decimal("100.50"),
        volume=90000,
        spread=Decimal("2.50"),  # high - low
        timeframe="15m",
        symbol="EUR/USD",
    )
    spring2 = Spring(
        bar=spring2_bar,
        bar_index=20,
        penetration_pct=Decimal("0.015"),
        volume_ratio=Decimal("0.5"),
        recovery_bars=2,
        creek_reference=Decimal("100.00"),
        spring_low=Decimal("98.50"),
        recovery_price=Decimal("100.50"),
        detection_timestamp=base_timestamp + timedelta(hours=10),
        trading_range_id=uuid4(),
    )
    detector.add_pattern(spring2)

    campaigns = detector.get_active_campaigns()
    assert len(campaigns) == 1
    assert len(campaigns[0].patterns) == 2  # Grouped into same campaign


# ============================================================================
# AC4.4: get_active_campaigns() Method
# ============================================================================


def test_get_active_campaigns_returns_forming_and_active(detector, sample_spring, sample_sos):
    """AC4.4: get_active_campaigns() returns FORMING and ACTIVE campaigns."""
    detector.add_pattern(sample_spring)
    detector.add_pattern(sample_sos)

    active = detector.get_active_campaigns()
    assert len(active) == 1
    assert active[0].state == CampaignState.ACTIVE


def test_get_active_campaigns_excludes_failed(detector, sample_spring, base_timestamp):
    """AC4.4: get_active_campaigns() excludes FAILED campaigns."""
    detector.add_pattern(sample_spring)

    # Expire campaign
    future_time = base_timestamp + timedelta(hours=73)
    detector.expire_stale_campaigns(future_time)

    active = detector.get_active_campaigns()
    assert len(active) == 0  # FAILED campaign excluded


def test_get_active_campaigns_includes_current_phase(detector, sample_spring, sample_sos):
    """AC4.4: Active campaigns include current_phase."""
    detector.add_pattern(sample_spring)
    detector.add_pattern(sample_sos)

    active = detector.get_active_campaigns()
    assert active[0].current_phase is not None
    assert active[0].current_phase == WyckoffPhase.D  # SOS = Phase D


# ============================================================================
# AC4.5: Campaign Rules (2 patterns min, 48h gap, 72h expiration)
# ============================================================================


def test_min_2_patterns_for_active(detector, sample_spring):
    """AC4.5: Campaign requires 2+ patterns to transition to ACTIVE."""
    detector.add_pattern(sample_spring)

    campaigns = detector.get_active_campaigns()
    assert len(campaigns) == 1
    assert campaigns[0].state == CampaignState.FORMING  # Not ACTIVE yet


def test_2_patterns_transitions_to_active(detector, sample_spring, sample_sos):
    """AC4.5: 2 patterns transitions campaign to ACTIVE."""
    detector.add_pattern(sample_spring)
    detector.add_pattern(sample_sos)

    campaigns = detector.get_active_campaigns()
    assert len(campaigns) == 1
    assert campaigns[0].state == CampaignState.ACTIVE


# ============================================================================
# AC4.7: Campaign Expiration (72h)
# ============================================================================


def test_campaign_expires_after_72_hours(detector, sample_spring, base_timestamp):
    """AC4.7: Campaign expires after 72 hours without completion."""
    detector.add_pattern(sample_spring)

    # 73 hours later
    future_time = base_timestamp + timedelta(hours=73)
    detector.expire_stale_campaigns(future_time)

    active = detector.get_active_campaigns()
    assert len(active) == 0  # Expired campaigns not active

    all_campaigns = detector.campaigns
    assert all_campaigns[0].state == CampaignState.FAILED
    assert "Expired after" in all_campaigns[0].failure_reason


def test_campaign_not_expired_before_72_hours(detector, sample_spring, base_timestamp):
    """AC4.7: Campaign not expired before 72 hours."""
    detector.add_pattern(sample_spring)

    # 71 hours later (before expiration)
    future_time = base_timestamp + timedelta(hours=71)
    detector.expire_stale_campaigns(future_time)

    active = detector.get_active_campaigns()
    assert len(active) == 1  # Still active
    assert active[0].state == CampaignState.FORMING


def test_expiration_called_on_add_pattern(detector, sample_spring, base_timestamp):
    """AC4.7: Expiration check runs on each add_pattern() call."""
    detector.add_pattern(sample_spring)

    # Create second pattern 73 hours later
    spring2_bar = OHLCVBar(
        timestamp=base_timestamp + timedelta(hours=73),
        open=Decimal("100.00"),
        high=Decimal("101.00"),
        low=Decimal("98.00"),
        close=Decimal("100.50"),
        volume=90000,
        spread=Decimal("3.00"),  # high - low
        timeframe="15m",
        symbol="EUR/USD",
    )
    spring2 = Spring(
        bar=spring2_bar,
        bar_index=100,
        penetration_pct=Decimal("0.02"),
        volume_ratio=Decimal("0.4"),
        recovery_bars=1,
        creek_reference=Decimal("100.00"),
        spring_low=Decimal("98.00"),
        recovery_price=Decimal("100.50"),
        detection_timestamp=base_timestamp + timedelta(hours=73),
        trading_range_id=uuid4(),
    )
    detector.add_pattern(spring2)

    # First campaign should be expired
    assert detector.campaigns[0].state == CampaignState.FAILED
    # Second pattern creates new campaign
    assert detector.campaigns[1].state == CampaignState.FORMING


# ============================================================================
# AC4.8, AC4.10: Pattern Sequence Validation
# ============================================================================


def test_valid_sequence_spring_to_sos(detector, sample_spring, sample_sos):
    """AC4.8, AC4.10: Valid sequence Spring → SOS accepted."""
    detector.add_pattern(sample_spring)
    detector.add_pattern(sample_sos)

    campaigns = detector.get_active_campaigns()
    assert len(campaigns) == 1
    assert len(campaigns[0].patterns) == 2
    assert campaigns[0].current_phase == WyckoffPhase.D


def test_valid_sequence_sos_to_lps(detector, sample_sos, sample_lps):
    """AC4.8, AC4.10: Valid sequence SOS → LPS accepted."""
    detector.add_pattern(sample_sos)
    detector.add_pattern(sample_lps)

    campaigns = detector.get_active_campaigns()
    assert len(campaigns) == 1
    assert len(campaigns[0].patterns) == 2
    assert campaigns[0].current_phase == WyckoffPhase.D


def test_valid_sequence_spring_spring_sos(detector, sample_spring, base_timestamp, sample_bar):
    """AC4.8, AC4.10: Valid sequence Spring → Spring → SOS accepted."""
    detector.add_pattern(sample_spring)

    # Add second Spring
    spring2_bar = OHLCVBar(
        timestamp=base_timestamp + timedelta(hours=10),
        open=Decimal("100.00"),
        high=Decimal("101.00"),
        low=Decimal("98.50"),
        close=Decimal("100.50"),
        volume=90000,
        spread=Decimal("2.50"),  # high - low
        timeframe="15m",
        symbol="EUR/USD",
    )
    spring2 = Spring(
        bar=spring2_bar,
        bar_index=20,
        penetration_pct=Decimal("0.015"),
        volume_ratio=Decimal("0.5"),
        recovery_bars=2,
        creek_reference=Decimal("100.00"),
        spring_low=Decimal("98.50"),
        recovery_price=Decimal("100.50"),
        detection_timestamp=base_timestamp + timedelta(hours=10),
        trading_range_id=uuid4(),
    )

    # Add SOS
    sos_bar = OHLCVBar(
        timestamp=base_timestamp + timedelta(hours=20),
        open=Decimal("100.00"),
        high=Decimal("103.00"),
        low=Decimal("100.00"),
        close=Decimal("102.50"),
        volume=200000,
        spread=Decimal("3.00"),  # high - low
        timeframe="15m",
        symbol="EUR/USD",
    )
    sos = SOSBreakout(
        bar=sos_bar,
        breakout_pct=Decimal("0.025"),
        volume_ratio=Decimal("2.0"),
        ice_reference=Decimal("100.00"),
        breakout_price=Decimal("102.50"),
        detection_timestamp=base_timestamp + timedelta(hours=20),
        trading_range_id=uuid4(),
        spread_ratio=Decimal("1.5"),
        close_position=Decimal("0.83"),
        spread=Decimal("3.00"),
    )

    detector.add_pattern(spring2)
    detector.add_pattern(sos)

    campaigns = detector.get_active_campaigns()
    assert len(campaigns) == 1
    assert len(campaigns[0].patterns) == 3


def test_invalid_sequence_spring_after_sos_rejected(
    detector, sample_sos, base_timestamp, sample_bar
):
    """AC4.8, AC4.10: Invalid sequence SOS → Spring rejected with warning logged."""
    detector.add_pattern(sample_sos)

    # Add second SOS to make campaign ACTIVE with Phase D
    sos2_bar = OHLCVBar(
        timestamp=base_timestamp + timedelta(hours=5),
        open=Decimal("102.00"),
        high=Decimal("104.00"),
        low=Decimal("102.00"),
        close=Decimal("103.50"),
        volume=220000,
        spread=Decimal("2.00"),  # high - low
        timeframe="15m",
        symbol="EUR/USD",
    )
    sos2 = SOSBreakout(
        bar=sos2_bar,
        breakout_pct=Decimal("0.035"),
        volume_ratio=Decimal("2.2"),
        ice_reference=Decimal("100.00"),
        breakout_price=Decimal("103.50"),
        detection_timestamp=base_timestamp + timedelta(hours=5),
        trading_range_id=uuid4(),
        spread_ratio=Decimal("1.3"),
        close_position=Decimal("0.75"),
        spread=Decimal("2.00"),
    )
    detector.add_pattern(sos2)

    campaigns = detector.get_active_campaigns()
    assert len(campaigns) == 1
    assert campaigns[0].state == CampaignState.ACTIVE
    assert campaigns[0].current_phase == WyckoffPhase.D

    # Try adding Spring after SOS (invalid - Phase C cannot follow Phase D)
    spring_bar = OHLCVBar(
        timestamp=base_timestamp + timedelta(hours=10),
        open=Decimal("100.00"),
        high=Decimal("101.00"),
        low=Decimal("98.00"),
        close=Decimal("100.50"),
        volume=90000,
        spread=Decimal("3.00"),  # high - low
        timeframe="15m",
        symbol="EUR/USD",
    )
    spring = Spring(
        bar=spring_bar,
        bar_index=20,
        penetration_pct=Decimal("0.02"),
        volume_ratio=Decimal("0.4"),
        recovery_bars=1,
        creek_reference=Decimal("100.00"),
        spring_low=Decimal("98.00"),
        recovery_price=Decimal("100.50"),
        detection_timestamp=base_timestamp + timedelta(hours=10),
        trading_range_id=uuid4(),
    )
    detector.add_pattern(spring)

    campaigns = detector.get_active_campaigns()
    # Pattern should be added but phase should remain unchanged
    assert len(campaigns[0].patterns) == 3
    # Phase should still be D (from SOS, not updated due to invalid sequence)
    assert campaigns[0].current_phase == WyckoffPhase.D


def test_invalid_sequence_spring_after_lps_rejected(
    detector, sample_lps, base_timestamp, sample_bar
):
    """AC4.8, AC4.10: Invalid sequence LPS → Spring rejected."""
    detector.add_pattern(sample_lps)

    # Try adding Spring after LPS (invalid)
    spring_bar = OHLCVBar(
        timestamp=base_timestamp + timedelta(hours=10),
        open=Decimal("100.00"),
        high=Decimal("101.00"),
        low=Decimal("98.00"),
        close=Decimal("100.50"),
        volume=90000,
        spread=Decimal("3.00"),  # high - low
        timeframe="15m",
        symbol="EUR/USD",
    )
    spring = Spring(
        bar=spring_bar,
        bar_index=20,
        penetration_pct=Decimal("0.02"),
        volume_ratio=Decimal("0.4"),
        recovery_bars=1,
        creek_reference=Decimal("100.00"),
        spring_low=Decimal("98.00"),
        recovery_price=Decimal("100.50"),
        detection_timestamp=base_timestamp + timedelta(hours=10),
        trading_range_id=uuid4(),
    )
    detector.add_pattern(spring)

    campaigns = detector.get_active_campaigns()
    # Pattern should be added but phase should remain unchanged
    assert len(campaigns[0].patterns) == 2


# ============================================================================
# AC4.9: Risk Metadata Extraction
# ============================================================================


def test_risk_metadata_extraction_spring_sos(detector, sample_spring, sample_sos):
    """AC4.9: Campaign extracts risk metadata from Spring and SOS patterns."""
    detector.add_pattern(sample_spring)
    detector.add_pattern(sample_sos)

    campaign = detector.get_active_campaigns()[0]

    # Support level: Lowest Spring low
    assert campaign.support_level == sample_spring.spring_low

    # Resistance level: Highest SOS breakout
    assert campaign.resistance_level == sample_sos.breakout_price

    # Strength score: Average of pattern quality scores
    assert 0.0 < campaign.strength_score <= 1.0

    # Risk per share: Latest price - support
    assert campaign.risk_per_share == sample_sos.breakout_price - sample_spring.spring_low

    # Range width percentage
    expected_range_width = (
        (sample_sos.breakout_price - sample_spring.spring_low)
        / sample_spring.spring_low
        * Decimal("100")
    )
    assert campaign.range_width_pct == expected_range_width


def test_risk_metadata_multiple_springs_uses_lowest(
    detector, sample_spring, base_timestamp, sample_bar
):
    """AC4.9: Support level uses LOWEST Spring low from multiple Springs."""
    detector.add_pattern(sample_spring)

    # Add second Spring with lower low
    spring2_bar = OHLCVBar(
        timestamp=base_timestamp + timedelta(hours=10),
        open=Decimal("100.00"),
        high=Decimal("101.00"),
        low=Decimal("97.00"),  # Lower low
        close=Decimal("100.50"),
        volume=90000,
        spread=Decimal("4.00"),  # high - low
        timeframe="15m",
        symbol="EUR/USD",
    )
    spring2 = Spring(
        bar=spring2_bar,
        bar_index=20,
        penetration_pct=Decimal("0.03"),
        volume_ratio=Decimal("0.5"),
        recovery_bars=2,
        creek_reference=Decimal("100.00"),
        spring_low=Decimal("97.00"),  # Lower than first Spring
        recovery_price=Decimal("100.50"),
        detection_timestamp=base_timestamp + timedelta(hours=10),
        trading_range_id=uuid4(),
    )
    detector.add_pattern(spring2)

    campaign = detector.get_active_campaigns()[0]
    assert campaign.support_level == Decimal("97.00")  # Lowest of the two


def test_risk_metadata_lps_uses_ice_as_resistance(detector, sample_sos, sample_lps):
    """AC4.9: Resistance level uses Ice from LPS patterns."""
    detector.add_pattern(sample_sos)
    detector.add_pattern(sample_lps)

    campaign = detector.get_active_campaigns()[0]

    # Resistance should be max of SOS breakout and LPS ice_level
    expected_resistance = max(sample_sos.breakout_price, sample_lps.ice_level)
    assert campaign.resistance_level == expected_resistance


def test_strength_score_calculation(detector, sample_spring, sample_sos):
    """AC4.9: Strength score calculated from pattern quality tiers."""
    detector.add_pattern(sample_spring)
    detector.add_pattern(sample_sos)

    campaign = detector.get_active_campaigns()[0]

    # Story 14.2: New strength calculation logic
    # Base (2 patterns): 0.2
    # Quality: Spring (no quality_tier visible) + SOS (GOOD) = avg ~0.15
    # Phase D: +0.2
    # Total: ~0.50-0.60
    assert 0.50 <= campaign.strength_score <= 0.60


# ============================================================================
# AC4.10: Sequence-Based Phase Assignment
# ============================================================================


def test_phase_assignment_spring_phase_c(detector, sample_spring):
    """AC4.10: Spring pattern assigns Phase C."""
    detector.add_pattern(sample_spring)

    # Need 2 patterns for ACTIVE state to set phase
    spring2_bar = OHLCVBar(
        timestamp=sample_spring.detection_timestamp + timedelta(hours=5),
        open=Decimal("100.00"),
        high=Decimal("101.00"),
        low=Decimal("98.50"),
        close=Decimal("100.50"),
        volume=90000,
        spread=Decimal("2.50"),  # high - low
        timeframe="15m",
        symbol="EUR/USD",
    )
    spring2 = Spring(
        bar=spring2_bar,
        bar_index=20,
        penetration_pct=Decimal("0.015"),
        volume_ratio=Decimal("0.5"),
        recovery_bars=2,
        creek_reference=Decimal("100.00"),
        spring_low=Decimal("98.50"),
        recovery_price=Decimal("100.50"),
        detection_timestamp=sample_spring.detection_timestamp + timedelta(hours=5),
        trading_range_id=uuid4(),
    )
    detector.add_pattern(spring2)

    campaign = detector.get_active_campaigns()[0]
    assert campaign.current_phase == WyckoffPhase.C


def test_phase_assignment_sos_phase_d(detector, sample_spring, sample_sos):
    """AC4.10: SOS pattern assigns Phase D."""
    detector.add_pattern(sample_spring)
    detector.add_pattern(sample_sos)

    campaign = detector.get_active_campaigns()[0]
    assert campaign.current_phase == WyckoffPhase.D


def test_phase_assignment_lps_phase_d(detector, sample_sos, sample_lps):
    """AC4.10: LPS pattern assigns Phase D."""
    detector.add_pattern(sample_sos)
    detector.add_pattern(sample_lps)

    campaign = detector.get_active_campaigns()[0]
    assert campaign.current_phase == WyckoffPhase.D


def test_phase_updated_on_new_pattern(detector, sample_spring, sample_sos, base_timestamp):
    """AC4.10: Phase updates when new patterns added to ACTIVE campaign."""
    detector.add_pattern(sample_spring)

    # Add second Spring to make it ACTIVE
    spring2_bar = OHLCVBar(
        timestamp=base_timestamp + timedelta(hours=5),
        open=Decimal("100.00"),
        high=Decimal("101.00"),
        low=Decimal("98.50"),
        close=Decimal("100.50"),
        volume=90000,
        spread=Decimal("2.50"),  # high - low
        timeframe="15m",
        symbol="EUR/USD",
    )
    spring2 = Spring(
        bar=spring2_bar,
        bar_index=20,
        penetration_pct=Decimal("0.015"),
        volume_ratio=Decimal("0.5"),
        recovery_bars=2,
        creek_reference=Decimal("100.00"),
        spring_low=Decimal("98.50"),
        recovery_price=Decimal("100.50"),
        detection_timestamp=base_timestamp + timedelta(hours=5),
        trading_range_id=uuid4(),
    )
    detector.add_pattern(spring2)

    campaign = detector.get_active_campaigns()[0]
    assert campaign.current_phase == WyckoffPhase.C  # Spring = Phase C

    # Add SOS - phase should update to D
    detector.add_pattern(sample_sos)
    assert campaign.current_phase == WyckoffPhase.D  # SOS = Phase D


# ============================================================================
# AC4.11: Portfolio Risk Management
# ============================================================================


def test_max_concurrent_campaigns_enforced(base_timestamp, sample_bar):
    """AC4.11: Max concurrent campaigns limit enforced."""
    # Extended expiration (200h) is test-specific to validate concurrent limit logic
    # Production default (72h) is more appropriate for real trading scenarios
    detector = IntradayCampaignDetector(
        max_concurrent_campaigns=3,
        campaign_window_hours=48,  # Patterns >48h apart create new campaigns
        expiration_hours=200,  # Test-only: keep campaigns alive for limit enforcement testing
    )

    # Create 3 campaigns (max_concurrent_campaigns = 3)
    # Use 60h spacing to ensure campaigns don't group (>48h window)
    for i in range(3):
        spring_bar = OHLCVBar(
            timestamp=base_timestamp + timedelta(hours=i * 60),  # 60h apart
            open=Decimal("100.00"),
            high=Decimal("101.00"),
            low=Decimal("98.00"),
            close=Decimal("100.50"),
            volume=100000,
            spread=Decimal("3.00"),  # high - low
            timeframe="15m",
            symbol="EUR/USD",
        )
        spring = Spring(
            bar=spring_bar,
            bar_index=i * 10,
            penetration_pct=Decimal("0.02"),
            volume_ratio=Decimal("0.4"),
            recovery_bars=1,
            creek_reference=Decimal("100.00"),
            spring_low=Decimal("98.00"),
            recovery_price=Decimal("100.50"),
            detection_timestamp=base_timestamp + timedelta(hours=i * 60),
            trading_range_id=uuid4(),
        )
        detector.add_pattern(spring)

    assert len(detector.get_active_campaigns()) == 3

    # Try to create 4th campaign (should be blocked)
    spring4_bar = OHLCVBar(
        timestamp=base_timestamp + timedelta(hours=200),
        open=Decimal("100.00"),
        high=Decimal("101.00"),
        low=Decimal("98.00"),
        close=Decimal("100.50"),
        volume=100000,
        spread=Decimal("3.00"),  # high - low
        timeframe="15m",
        symbol="EUR/USD",
    )
    spring4 = Spring(
        bar=spring4_bar,
        bar_index=40,
        penetration_pct=Decimal("0.02"),
        volume_ratio=Decimal("0.4"),
        recovery_bars=1,
        creek_reference=Decimal("100.00"),
        spring_low=Decimal("98.00"),
        recovery_price=Decimal("100.50"),
        detection_timestamp=base_timestamp + timedelta(hours=200),
        trading_range_id=uuid4(),
    )
    detector.add_pattern(spring4)

    # Should still be only 3 campaigns (4th blocked by limit)
    assert len(detector.get_active_campaigns()) == 3


def test_max_concurrent_campaigns_custom_limit(base_timestamp, sample_bar):
    """AC4.11: Custom max_concurrent_campaigns limit respected."""
    # Extended expiration (200h) is test-specific to validate concurrent limit logic
    # Production default (72h) is more appropriate for real trading scenarios
    detector = IntradayCampaignDetector(
        max_concurrent_campaigns=2,
        campaign_window_hours=48,
        expiration_hours=200,  # Test-only: keep campaigns alive for limit enforcement testing
    )

    # Create 2 campaigns
    for i in range(2):
        spring_bar = OHLCVBar(
            timestamp=base_timestamp + timedelta(hours=i * 60),
            open=Decimal("100.00"),
            high=Decimal("101.00"),
            low=Decimal("98.00"),
            close=Decimal("100.50"),
            volume=100000,
            spread=Decimal("3.00"),  # high - low
            timeframe="15m",
            symbol="EUR/USD",
        )
        spring = Spring(
            bar=spring_bar,
            bar_index=i * 10,
            penetration_pct=Decimal("0.02"),
            volume_ratio=Decimal("0.4"),
            recovery_bars=1,
            creek_reference=Decimal("100.00"),
            spring_low=Decimal("98.00"),
            recovery_price=Decimal("100.50"),
            detection_timestamp=base_timestamp + timedelta(hours=i * 60),
            trading_range_id=uuid4(),
        )
        detector.add_pattern(spring)

    assert len(detector.get_active_campaigns()) == 2

    # 3rd campaign should be blocked
    spring3_bar = OHLCVBar(
        timestamp=base_timestamp + timedelta(hours=150),
        open=Decimal("100.00"),
        high=Decimal("101.00"),
        low=Decimal("98.00"),
        close=Decimal("100.50"),
        volume=100000,
        spread=Decimal("3.00"),  # high - low
        timeframe="15m",
        symbol="EUR/USD",
    )
    spring3 = Spring(
        bar=spring3_bar,
        bar_index=30,
        penetration_pct=Decimal("0.02"),
        volume_ratio=Decimal("0.4"),
        recovery_bars=1,
        creek_reference=Decimal("100.00"),
        spring_low=Decimal("98.00"),
        recovery_price=Decimal("100.50"),
        detection_timestamp=base_timestamp + timedelta(hours=150),
        trading_range_id=uuid4(),
    )
    detector.add_pattern(spring3)

    assert len(detector.get_active_campaigns()) == 2


def test_portfolio_limits_allow_patterns_in_existing_campaigns(
    sample_spring, sample_sos, base_timestamp
):
    """AC4.11: Portfolio limits don't block patterns added to existing campaigns."""
    # Extended expiration (200h) is test-specific to validate concurrent limit logic
    # Production default (72h) is more appropriate for real trading scenarios
    detector = IntradayCampaignDetector(
        max_concurrent_campaigns=3,
        campaign_window_hours=48,
        expiration_hours=200,  # Test-only: keep campaigns alive for limit enforcement testing
    )

    # Create 3 campaigns at limit
    for i in range(3):
        spring_bar = OHLCVBar(
            timestamp=base_timestamp + timedelta(hours=i * 60),
            open=Decimal("100.00"),
            high=Decimal("101.00"),
            low=Decimal("98.00"),
            close=Decimal("100.50"),
            volume=100000,
            spread=Decimal("3.00"),  # high - low
            timeframe="15m",
            symbol="EUR/USD",
        )
        spring = Spring(
            bar=spring_bar,
            bar_index=i * 10,
            penetration_pct=Decimal("0.02"),
            volume_ratio=Decimal("0.4"),
            recovery_bars=1,
            creek_reference=Decimal("100.00"),
            spring_low=Decimal("98.00"),
            recovery_price=Decimal("100.50"),
            detection_timestamp=base_timestamp + timedelta(hours=i * 60),
            trading_range_id=uuid4(),
        )
        detector.add_pattern(spring)

    # Add SOS to first campaign (should be allowed - not creating new campaign)
    sos_bar = OHLCVBar(
        timestamp=base_timestamp + timedelta(hours=2),
        open=Decimal("100.00"),
        high=Decimal("103.00"),
        low=Decimal("100.00"),
        close=Decimal("102.50"),
        volume=200000,
        spread=Decimal("3.00"),  # high - low
        timeframe="15m",
        symbol="EUR/USD",
    )
    sos = SOSBreakout(
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
    detector.add_pattern(sos)

    # First campaign should have 2 patterns
    assert len(detector.campaigns[0].patterns) == 2


# ============================================================================
# Integration Tests
# ============================================================================


def test_complete_campaign_lifecycle(detector, sample_spring, sample_sos, sample_lps):
    """Integration: Complete campaign lifecycle Spring → SOS → LPS."""
    # Start with Spring
    detector.add_pattern(sample_spring)
    assert len(detector.get_active_campaigns()) == 1
    assert detector.get_active_campaigns()[0].state == CampaignState.FORMING

    # Add SOS - transition to ACTIVE
    detector.add_pattern(sample_sos)
    campaign = detector.get_active_campaigns()[0]
    assert campaign.state == CampaignState.ACTIVE
    assert campaign.current_phase == WyckoffPhase.D
    assert len(campaign.patterns) == 2

    # Add LPS - still ACTIVE, Phase D
    detector.add_pattern(sample_lps)
    campaign = detector.get_active_campaigns()[0]
    assert campaign.state == CampaignState.ACTIVE
    assert campaign.current_phase == WyckoffPhase.D
    assert len(campaign.patterns) == 3

    # Verify risk metadata updated
    assert campaign.support_level == sample_spring.spring_low
    assert campaign.resistance_level is not None
    assert campaign.strength_score > 0.0
    assert campaign.risk_per_share is not None


def test_multiple_concurrent_campaigns(detector, base_timestamp):
    """Integration: Multiple concurrent campaigns tracked independently."""
    # Campaign 1: Spring at T+0
    spring1_bar = OHLCVBar(
        timestamp=base_timestamp,
        open=Decimal("100.00"),
        high=Decimal("101.00"),
        low=Decimal("98.00"),
        close=Decimal("100.50"),
        volume=100000,
        spread=Decimal("3.00"),  # high - low
        timeframe="15m",
        symbol="EUR/USD",
    )
    spring1 = Spring(
        bar=spring1_bar,
        bar_index=0,
        penetration_pct=Decimal("0.02"),
        volume_ratio=Decimal("0.4"),
        recovery_bars=1,
        creek_reference=Decimal("100.00"),
        spring_low=Decimal("98.00"),
        recovery_price=Decimal("100.50"),
        detection_timestamp=base_timestamp,
        trading_range_id=uuid4(),
    )

    # Campaign 2: Spring at T+60h (outside window)
    spring2_bar = OHLCVBar(
        timestamp=base_timestamp + timedelta(hours=60),
        open=Decimal("105.00"),
        high=Decimal("106.00"),
        low=Decimal("103.00"),
        close=Decimal("105.50"),
        volume=100000,
        spread=Decimal("3.00"),  # high - low
        timeframe="15m",
        symbol="EUR/USD",
    )
    spring2 = Spring(
        bar=spring2_bar,
        bar_index=100,
        penetration_pct=Decimal("0.02"),
        volume_ratio=Decimal("0.4"),
        recovery_bars=1,
        creek_reference=Decimal("105.00"),
        spring_low=Decimal("103.00"),
        recovery_price=Decimal("105.50"),
        detection_timestamp=base_timestamp + timedelta(hours=60),
        trading_range_id=uuid4(),
    )

    detector.add_pattern(spring1)
    detector.add_pattern(spring2)

    campaigns = detector.get_active_campaigns()
    assert len(campaigns) == 2
    assert campaigns[0].patterns[0] == spring1
    assert campaigns[1].patterns[0] == spring2
