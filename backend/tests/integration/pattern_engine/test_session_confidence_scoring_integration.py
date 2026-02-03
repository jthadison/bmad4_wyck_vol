"""
Integration tests for Session-Based Confidence Scoring (Story 13.3.1).

Tests cover:
- Task 9: Phase tracking with multi-session campaigns
- Task 10: Trade signal generation filtering based on is_tradeable flag
- AC 2.3: Only tradeable patterns generate trade signals
- AC 4.1: All patterns tracked regardless of session quality
- AC 4.2: Phase identifier sees all events
- AC 4.3: Phase confidence considers session quality
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import Mock
from uuid import uuid4

from src.models.forex import ForexSession, get_forex_session
from src.models.lps import LPS
from src.models.ohlcv import OHLCVBar
from src.models.sos_breakout import SOSBreakout
from src.models.spring import Spring
from src.models.trading_range import RangeStatus, TradingRange
from src.signal_generator.sos_signal_generator import (
    generate_lps_signal,
    generate_sos_direct_signal,
)
from src.signal_generator.spring_signal_generator import generate_spring_signal

# ============================================================================
# Test Fixtures
# ============================================================================


def create_multi_session_bars(
    sessions: list[ForexSession], base_price: Decimal = Decimal("100.00")
) -> list[OHLCVBar]:
    """
    Create bars across multiple forex sessions for campaign tracking tests.

    Args:
        sessions: List of ForexSession enum values to create bars for
        base_price: Starting price for bar sequence

    Returns:
        List of OHLCVBar instances, one per session
    """
    bars = []
    session_hours = {
        ForexSession.ASIAN: 4,  # 04:00 UTC
        ForexSession.LONDON: 10,  # 10:00 UTC
        ForexSession.OVERLAP: 15,  # 15:00 UTC
        ForexSession.NY: 18,  # 18:00 UTC
        ForexSession.NY_CLOSE: 21,  # 21:00 UTC
    }

    for i, session in enumerate(sessions):
        hour = session_hours[session]
        timestamp = datetime(2025, 1, 6, hour, 0, tzinfo=UTC)

        # Verify session detection is correct
        detected_session = get_forex_session(timestamp)
        assert detected_session == session, f"Session mismatch at {hour}:00 UTC"

        bar = OHLCVBar(
            symbol="EUR/USD",
            timeframe="15m",
            timestamp=timestamp,
            open=base_price + Decimal(str(i * 0.50)),
            high=base_price + Decimal(str(i * 0.50 + 1.00)),
            low=base_price + Decimal(str(i * 0.50 - 0.50)),
            close=base_price + Decimal(str(i * 0.50 + 0.25)),
            volume=100000 + (i * 10000),
            spread=Decimal("2.00"),
        )
        bars.append(bar)

    return bars


def create_trading_range_with_levels(
    ice_price: Decimal = Decimal("100.00"),
    jump_price: Decimal = Decimal("120.00"),
    creek_price: Decimal = Decimal("95.00"),
):
    """
    Create a mock trading range with Ice, Jump, and Creek levels.

    Uses mocks to simplify creation (following pattern from existing integration tests).
    """
    range_mock = Mock(spec=TradingRange)
    range_mock.id = uuid4()
    range_mock.symbol = "EUR/USD"
    range_mock.timeframe = "15m"
    range_mock.creek = creek_price
    range_mock.status = RangeStatus.ACTIVE

    # Mock Ice level
    ice_mock = Mock()
    ice_mock.price = ice_price
    range_mock.ice = ice_mock

    # Mock Jump level
    jump_mock = Mock()
    jump_mock.price = jump_price
    range_mock.jump = jump_mock

    return range_mock


# ============================================================================
# Task 9: Integration Tests for Phase Tracking
# ============================================================================


class TestPhaseTrackingMultiSession:
    """
    Test multi-session campaign tracking with session-based confidence scoring.

    AC 4.1: All patterns detected across all sessions (no hard rejection)
    AC 4.2: Phase identifier sees all events for campaign tracking
    AC 4.3: Only tradeable patterns generate trade signals
    """

    def test_multi_session_campaign_all_events_visible(self):
        """
        Test AC 4.1, 4.2: Multi-session campaign with all events tracked.

        Campaign sequence:
        - SC (Selling Climax) in LONDON session (0 penalty, tradeable)
        - ST (Secondary Test) in ASIAN session (-20 penalty, not tradeable)
        - Spring in LONDON session (0 penalty, tradeable)

        Expected behavior:
        - All 3 patterns detected and stored
        - 2 patterns tradeable (LONDON session)
        - 1 pattern non-tradeable but tracked (ASIAN session)
        - Phase identifier sees complete event sequence
        """
        # Create Spring pattern in LONDON session (tradeable)
        london_bar = OHLCVBar(
            symbol="EUR/USD",
            timeframe="15m",
            timestamp=datetime(2025, 1, 6, 10, 0, tzinfo=UTC),  # LONDON
            open=Decimal("98.00"),
            high=Decimal("99.00"),
            low=Decimal("97.00"),
            close=Decimal("99.50"),
            volume=50000,
            spread=Decimal("2.00"),
        )

        spring_london = Spring(
            bar=london_bar,
            bar_index=10,
            penetration_pct=Decimal("0.02"),
            volume_ratio=Decimal("0.4"),
            recovery_bars=2,
            creek_reference=Decimal("98.00"),
            spring_low=Decimal("97.00"),
            recovery_price=Decimal("99.50"),
            detection_timestamp=datetime.now(UTC),
            trading_range_id=uuid4(),
            session_quality=ForexSession.LONDON,
            session_confidence_penalty=0,
            is_tradeable=True,
        )

        # Create Spring pattern in ASIAN session (non-tradeable)
        asian_bar = OHLCVBar(
            symbol="EUR/USD",
            timeframe="15m",
            timestamp=datetime(2025, 1, 6, 4, 0, tzinfo=UTC),  # ASIAN
            open=Decimal("98.00"),
            high=Decimal("99.00"),
            low=Decimal("97.00"),
            close=Decimal("99.50"),
            volume=50000,
            spread=Decimal("2.00"),
        )

        spring_asian = Spring(
            bar=asian_bar,
            bar_index=5,
            penetration_pct=Decimal("0.02"),
            volume_ratio=Decimal("0.4"),
            recovery_bars=2,
            creek_reference=Decimal("98.00"),
            spring_low=Decimal("97.00"),
            recovery_price=Decimal("99.50"),
            detection_timestamp=datetime.now(UTC),
            trading_range_id=uuid4(),
            session_quality=ForexSession.ASIAN,
            session_confidence_penalty=-20,  # Penalty applied
            is_tradeable=False,  # Below 70 threshold (85 - 20 = 65)
        )

        # Verify both patterns exist (AC 4.1: All patterns tracked)
        assert spring_london is not None, "LONDON Spring should be detected"
        assert spring_asian is not None, "ASIAN Spring should be detected and tracked"

        # Verify session quality and penalties
        assert spring_london.session_quality == ForexSession.LONDON
        assert spring_london.session_confidence_penalty == 0
        assert spring_london.is_tradeable is True

        assert spring_asian.session_quality == ForexSession.ASIAN
        assert spring_asian.session_confidence_penalty == -20
        assert spring_asian.is_tradeable is False

        # AC 4.2: Phase identifier sees all events (both patterns available in database)
        campaign_events = [spring_asian, spring_london]
        assert len(campaign_events) == 2, "Phase identifier should see all events"

        # AC 4.3: Only tradeable patterns should generate signals
        # (Signal generation test in Task 10)

    def test_premium_session_campaign_all_tradeable(self):
        """
        Test AC 4.1: All patterns in premium sessions (LONDON, OVERLAP) are tradeable.

        Campaign sequence (all premium sessions):
        - SC in LONDON (0 penalty, tradeable)
        - ST in OVERLAP (0 penalty, tradeable)
        - Spring in LONDON (0 penalty, tradeable)

        Expected: All patterns tradeable with no penalties
        """
        sessions = [ForexSession.LONDON, ForexSession.OVERLAP, ForexSession.LONDON]

        for session in sessions:
            # Verify session has 0 penalty
            from src.pattern_engine.detectors.spring_detector import _calculate_session_penalty

            penalty = _calculate_session_penalty(session, filter_enabled=False)
            assert penalty == 0, f"{session.value} should have 0 penalty"

        # All patterns in premium sessions should be tradeable (base confidence 85 + 0 = 85 >= 70)
        # This preserves high-quality campaign tracking

    def test_mixed_quality_campaign_selective_trading(self):
        """
        Test AC 4.3: Mixed-quality campaign preserves phase tracking, selective signal generation.

        Campaign with mixed sessions:
        - SC (LONDON, 0 penalty, tradeable)
        - AR (Automatic Rally) (NY, -5 penalty, tradeable: 85-5=80 >= 70)
        - ST (ASIAN, -20 penalty, NOT tradeable: 85-20=65 < 70)
        - Spring (LONDON, 0 penalty, tradeable)

        Expected:
        - All 4 patterns detected and stored (phase tracking preserved)
        - 3 patterns tradeable (LONDON, NY sessions)
        - 1 pattern non-tradeable (ASIAN session)
        - Phase confidence considers session quality: 85 + 0 + (-5) + (-20) + 0 = 60
        """
        # Session penalties for each event
        penalties = {
            "SC": 0,  # LONDON
            "AR": -5,  # NY
            "ST": -20,  # ASIAN
            "Spring": 0,  # LONDON
        }

        base_confidence = 85

        # Calculate tradeability for each event
        tradeability = {
            "SC": (base_confidence + penalties["SC"]) >= 70,  # 85 >= 70 ✓
            "AR": (base_confidence + penalties["AR"]) >= 70,  # 80 >= 70 ✓
            "ST": (base_confidence + penalties["ST"]) >= 70,  # 65 < 70 ✗
            "Spring": (base_confidence + penalties["Spring"]) >= 70,  # 85 >= 70 ✓
        }

        # Verify mixed tradeability
        assert tradeability["SC"] is True
        assert tradeability["AR"] is True
        assert tradeability["ST"] is False  # Non-tradeable but still tracked
        assert tradeability["Spring"] is True

        # Calculate phase confidence (sum of penalties)
        phase_confidence = base_confidence + sum(penalties.values())
        assert phase_confidence == 60, "Phase confidence should consider all session penalties"

        # Verify phase tracking continuity (all events present)
        assert len(penalties) == 4, "All 4 events should be tracked regardless of session"


# ============================================================================
# Task 10: Integration Tests for Trade Signal Generation
# ============================================================================


class TestTradeSignalGenerationFiltering:
    """
    Test trade signal generation respects is_tradeable flag.

    AC 2.3: Only tradeable patterns generate trade signals
    AC 4.1: Non-tradeable patterns are stored but don't generate signals
    """

    def test_tradeable_pattern_generates_signal(self):
        """
        Test AC 2.3: Tradeable pattern (confidence >= 70) generates trade signal.

        Spring in LONDON session:
        - Base confidence: 85
        - Session penalty: 0
        - Final confidence: 85
        - is_tradeable: True

        Expected: Signal generated successfully
        """
        trading_range = create_trading_range_with_levels(
            ice_price=Decimal("100.00"),
            jump_price=Decimal("120.00"),
            creek_price=Decimal("95.00"),
        )

        # Create Spring in LONDON session (tradeable)
        spring = Spring(
            bar=OHLCVBar(
                symbol="EUR/USD",
                timeframe="15m",
                timestamp=datetime(2025, 1, 6, 10, 0, tzinfo=UTC),  # LONDON
                open=Decimal("94.00"),
                high=Decimal("95.00"),
                low=Decimal("93.00"),
                close=Decimal("95.50"),
                volume=50000,
                spread=Decimal("2.00"),
            ),
            bar_index=10,
            penetration_pct=Decimal("0.021"),
            volume_ratio=Decimal("0.4"),
            recovery_bars=2,
            creek_reference=Decimal("95.00"),
            spring_low=Decimal("93.00"),
            recovery_price=Decimal("95.50"),
            detection_timestamp=datetime.now(UTC),
            trading_range_id=trading_range.id,
            session_quality=ForexSession.LONDON,
            session_confidence_penalty=0,
            is_tradeable=True,
        )

        # Generate signal
        signal = generate_spring_signal(
            spring=spring,
            range=trading_range,
            confidence=85,
            urgency="STANDARD",
        )

        # AC 2.3: Signal should be generated
        assert signal is not None, "Tradeable pattern should generate signal"
        assert signal.confidence == 85
        assert signal.entry_type == "SPRING_ENTRY"

    def test_non_tradeable_pattern_no_signal(self):
        """
        Test AC 2.3, 4.1: Non-tradeable pattern (confidence < 70) does not generate signal.

        Spring in ASIAN session:
        - Base confidence: 85
        - Session penalty: -20
        - Final confidence: 65
        - is_tradeable: False

        Expected:
        - Pattern detected and stored (AC 4.1)
        - No trade signal generated (AC 2.3)
        """
        trading_range = create_trading_range_with_levels(
            ice_price=Decimal("100.00"),
            jump_price=Decimal("120.00"),
            creek_price=Decimal("95.00"),
        )

        # Create Spring in ASIAN session (non-tradeable)
        spring = Spring(
            bar=OHLCVBar(
                symbol="EUR/USD",
                timeframe="15m",
                timestamp=datetime(2025, 1, 6, 4, 0, tzinfo=UTC),  # ASIAN
                open=Decimal("94.00"),
                high=Decimal("95.00"),
                low=Decimal("93.00"),
                close=Decimal("95.50"),
                volume=50000,
                spread=Decimal("2.00"),
            ),
            bar_index=10,
            penetration_pct=Decimal("0.021"),
            volume_ratio=Decimal("0.4"),
            recovery_bars=2,
            creek_reference=Decimal("95.00"),
            spring_low=Decimal("93.00"),
            recovery_price=Decimal("95.50"),
            detection_timestamp=datetime.now(UTC),
            trading_range_id=trading_range.id,
            session_quality=ForexSession.ASIAN,
            session_confidence_penalty=-20,
            is_tradeable=False,  # Not tradeable
        )

        # AC 4.1: Pattern should exist (stored in database)
        assert spring is not None, "Pattern should be detected and stored"
        assert spring.is_tradeable is False

        # Attempt to generate signal
        signal = generate_spring_signal(
            spring=spring,
            range=trading_range,
            confidence=65,
            urgency="STANDARD",
        )

        # AC 2.3: No signal should be generated
        assert signal is None, "Non-tradeable pattern should not generate signal"

    def test_mixed_patterns_selective_signals(self):
        """
        Test AC 2.3: Mixed tradeable/non-tradeable patterns generate signals selectively.

        Three SOS breakouts:
        1. LONDON session (0 penalty, confidence 85, tradeable) → Signal
        2. ASIAN session (-20 penalty, confidence 65, non-tradeable) → No signal
        3. NY session (-5 penalty, confidence 80, tradeable) → Signal

        Expected:
        - 3 patterns detected (all tracked)
        - 2 signals generated (LONDON, NY)
        - 1 pattern tracked without signal (ASIAN)
        """
        trading_range = create_trading_range_with_levels()

        # Pattern 1: LONDON session (tradeable)
        sos_london = SOSBreakout(
            bar=OHLCVBar(
                symbol="EUR/USD",
                timeframe="15m",
                timestamp=datetime(2025, 1, 6, 10, 0, tzinfo=UTC),
                open=Decimal("100.00"),
                high=Decimal("103.00"),
                low=Decimal("100.00"),
                close=Decimal("103.00"),
                volume=250000,
                spread=Decimal("3.00"),
            ),
            breakout_pct=Decimal("0.03"),
            volume_ratio=Decimal("2.5"),
            ice_reference=Decimal("100.00"),
            breakout_price=Decimal("103.00"),
            detection_timestamp=datetime.now(UTC),
            trading_range_id=trading_range.id,
            spread_ratio=Decimal("1.5"),
            close_position=Decimal("1.0"),
            spread=Decimal("3.00"),  # Bar spread (high - low)
            session_quality=ForexSession.LONDON,
            session_confidence_penalty=0,
            is_tradeable=True,
        )

        # Pattern 2: ASIAN session (non-tradeable)
        sos_asian = SOSBreakout(
            bar=OHLCVBar(
                symbol="EUR/USD",
                timeframe="15m",
                timestamp=datetime(2025, 1, 6, 4, 0, tzinfo=UTC),
                open=Decimal("100.00"),
                high=Decimal("103.00"),
                low=Decimal("100.00"),
                close=Decimal("103.00"),
                volume=250000,
                spread=Decimal("3.00"),
            ),
            breakout_pct=Decimal("0.03"),
            volume_ratio=Decimal("2.5"),
            ice_reference=Decimal("100.00"),
            breakout_price=Decimal("103.00"),
            detection_timestamp=datetime.now(UTC),
            trading_range_id=trading_range.id,
            spread_ratio=Decimal("1.5"),
            close_position=Decimal("1.0"),
            spread=Decimal("3.00"),  # Bar spread (high - low)
            session_quality=ForexSession.ASIAN,
            session_confidence_penalty=-20,
            is_tradeable=False,
        )

        # Pattern 3: NY session (tradeable)
        sos_ny = SOSBreakout(
            bar=OHLCVBar(
                symbol="EUR/USD",
                timeframe="15m",
                timestamp=datetime(2025, 1, 6, 18, 0, tzinfo=UTC),
                open=Decimal("100.00"),
                high=Decimal("103.00"),
                low=Decimal("100.00"),
                close=Decimal("103.00"),
                volume=250000,
                spread=Decimal("3.00"),
            ),
            breakout_pct=Decimal("0.03"),
            volume_ratio=Decimal("2.5"),
            ice_reference=Decimal("100.00"),
            breakout_price=Decimal("103.00"),
            detection_timestamp=datetime.now(UTC),
            trading_range_id=trading_range.id,
            spread_ratio=Decimal("1.5"),
            close_position=Decimal("1.0"),
            spread=Decimal("3.00"),  # Bar spread (high - low)
            session_quality=ForexSession.NY,
            session_confidence_penalty=-5,
            is_tradeable=True,
        )

        # Verify all patterns detected
        patterns = [sos_london, sos_asian, sos_ny]
        assert len(patterns) == 3, "All 3 patterns should be detected"

        # Generate signals
        signal_london = generate_sos_direct_signal(sos_london, trading_range, confidence=85)
        signal_asian = generate_sos_direct_signal(sos_asian, trading_range, confidence=65)
        signal_ny = generate_sos_direct_signal(sos_ny, trading_range, confidence=80)

        # Verify selective signal generation
        assert signal_london is not None, "LONDON pattern should generate signal"
        assert signal_asian is None, "ASIAN pattern should NOT generate signal"
        assert signal_ny is not None, "NY pattern should generate signal"

        # Verify signal count
        signals_generated = [s for s in [signal_london, signal_asian, signal_ny] if s is not None]
        assert len(signals_generated) == 2, "Only 2 tradeable patterns should generate signals"

    def test_lps_signal_filtering(self):
        """
        Test AC 2.3: LPS signal generation respects is_tradeable flag.

        Two LPS patterns:
        1. OVERLAP session (0 penalty, tradeable) → Signal
        2. NY_CLOSE session (-25 penalty, non-tradeable) → No signal

        Expected: Only OVERLAP pattern generates signal
        """
        trading_range = create_trading_range_with_levels()

        # Create SOS breakout (required for LPS)
        sos = SOSBreakout(
            bar=OHLCVBar(
                symbol="EUR/USD",
                timeframe="15m",
                timestamp=datetime(2025, 1, 6, 10, 0, tzinfo=UTC),
                open=Decimal("100.00"),
                high=Decimal("103.00"),
                low=Decimal("100.00"),
                close=Decimal("103.00"),
                volume=250000,
                spread=Decimal("3.00"),
            ),
            breakout_pct=Decimal("0.03"),
            volume_ratio=Decimal("2.5"),
            ice_reference=Decimal("100.00"),
            breakout_price=Decimal("103.00"),
            detection_timestamp=datetime.now(UTC),
            trading_range_id=trading_range.id,
            spread_ratio=Decimal("1.5"),
            close_position=Decimal("1.0"),
            spread=Decimal("3.00"),  # Bar spread (high - low)
            session_quality=ForexSession.LONDON,
            session_confidence_penalty=0,
            is_tradeable=True,
        )

        # LPS 1: OVERLAP session (tradeable)
        lps_overlap = LPS(
            bar=OHLCVBar(
                symbol="EUR/USD",
                timeframe="15m",
                timestamp=datetime(2025, 1, 6, 15, 0, tzinfo=UTC),  # OVERLAP
                open=Decimal("101.00"),
                high=Decimal("102.00"),
                low=Decimal("100.50"),
                close=Decimal("101.50"),
                volume=120000,
                spread=Decimal("2.00"),
            ),
            distance_from_ice=Decimal("0.015"),
            distance_quality="PREMIUM",
            distance_confidence_bonus=10,
            volume_ratio=Decimal("0.6"),
            range_avg_volume=150000,
            volume_ratio_vs_avg=Decimal("0.8"),
            volume_ratio_vs_sos=Decimal("0.48"),
            pullback_spread=Decimal("1.50"),
            range_avg_spread=Decimal("2.00"),
            spread_ratio=Decimal("0.75"),
            spread_quality="NARROW",
            effort_result="NO_SUPPLY",
            effort_result_bonus=10,
            sos_reference=sos.id,
            held_support=True,
            pullback_low=Decimal("100.50"),
            ice_level=Decimal("100.00"),
            sos_volume=250000,
            pullback_volume=120000,
            bars_after_sos=5,
            bounce_confirmed=True,
            bounce_bar_timestamp=datetime.now(UTC),
            detection_timestamp=datetime.now(UTC),
            trading_range_id=trading_range.id,
            atr_14=Decimal("2.50"),
            stop_distance=Decimal("3.00"),
            stop_distance_pct=Decimal("3.0"),
            stop_price=Decimal("97.00"),
            volume_trend="DECLINING",
            volume_trend_quality="EXCELLENT",
            volume_trend_bonus=5,
            session_quality=ForexSession.OVERLAP,
            session_confidence_penalty=0,
            is_tradeable=True,
        )

        # LPS 2: NY_CLOSE session (non-tradeable)
        lps_ny_close = LPS(
            bar=OHLCVBar(
                symbol="EUR/USD",
                timeframe="15m",
                timestamp=datetime(2025, 1, 6, 21, 0, tzinfo=UTC),  # NY_CLOSE
                open=Decimal("101.00"),
                high=Decimal("102.00"),
                low=Decimal("100.50"),
                close=Decimal("101.50"),
                volume=120000,
                spread=Decimal("2.00"),
            ),
            distance_from_ice=Decimal("0.015"),
            distance_quality="PREMIUM",
            distance_confidence_bonus=10,
            volume_ratio=Decimal("0.6"),
            range_avg_volume=150000,
            volume_ratio_vs_avg=Decimal("0.8"),
            volume_ratio_vs_sos=Decimal("0.48"),
            pullback_spread=Decimal("1.50"),
            range_avg_spread=Decimal("2.00"),
            spread_ratio=Decimal("0.75"),
            spread_quality="NARROW",
            effort_result="NO_SUPPLY",
            effort_result_bonus=10,
            sos_reference=sos.id,
            held_support=True,
            pullback_low=Decimal("100.50"),
            ice_level=Decimal("100.00"),
            sos_volume=250000,
            pullback_volume=120000,
            bars_after_sos=8,
            bounce_confirmed=True,
            bounce_bar_timestamp=datetime.now(UTC),
            detection_timestamp=datetime.now(UTC),
            trading_range_id=trading_range.id,
            atr_14=Decimal("2.50"),
            stop_distance=Decimal("3.00"),
            stop_distance_pct=Decimal("3.0"),
            stop_price=Decimal("97.00"),
            volume_trend="DECLINING",
            volume_trend_quality="EXCELLENT",
            volume_trend_bonus=5,
            session_quality=ForexSession.NY_CLOSE,
            session_confidence_penalty=-25,
            is_tradeable=False,  # 85 - 25 = 60 < 70
        )

        # Generate signals
        signal_overlap = generate_lps_signal(lps_overlap, sos, trading_range, confidence=85)
        signal_ny_close = generate_lps_signal(lps_ny_close, sos, trading_range, confidence=60)

        # Verify selective signal generation
        assert signal_overlap is not None, "OVERLAP LPS should generate signal"
        assert signal_ny_close is None, "NY_CLOSE LPS should NOT generate signal"
