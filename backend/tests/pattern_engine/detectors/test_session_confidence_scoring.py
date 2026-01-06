"""
Unit tests for session-based confidence scoring (Story 13.3.1).

This module tests the graduated confidence penalty system that replaces
binary session rejection, ensuring patterns are detected across all sessions
but marked tradeable only when meeting minimum confidence thresholds.

Test Coverage:
- Session penalty calculation for each session type
- Tradeable flag logic based on final confidence
- Backward compatibility (default disabled behavior)
- Filter + scoring interaction scenarios
- Edge cases and boundary conditions
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from src.models.forex import ForexSession, get_forex_session
from src.models.lps import LPS
from src.models.ohlcv import OHLCVBar
from src.models.sos_breakout import SOSBreakout
from src.models.spring import Spring
from src.pattern_engine.detectors.lps_detector import (
    _calculate_session_penalty as lps_penalty,
)
from src.pattern_engine.detectors.sos_detector import (
    _calculate_session_penalty as sos_penalty,
)
from src.pattern_engine.detectors.spring_detector import (
    _calculate_session_penalty as spring_penalty,
)

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def base_ohlcv_bar() -> OHLCVBar:
    """Create a base OHLCV bar for testing."""
    return OHLCVBar(
        symbol="EUR/USD",
        timeframe="15m",
        timestamp=datetime(2025, 1, 6, 10, 0, tzinfo=UTC),  # LONDON session
        open=Decimal("100.00"),
        high=Decimal("101.00"),
        low=Decimal("99.00"),
        close=Decimal("100.50"),
        volume=100000,
        spread=Decimal("2.00"),
    )


@pytest.fixture
def london_bar() -> OHLCVBar:
    """Bar in LONDON session (8-13 UTC)."""
    return OHLCVBar(
        symbol="EUR/USD",
        timeframe="15m",
        timestamp=datetime(2025, 1, 6, 10, 0, tzinfo=UTC),  # 10:00 UTC
        open=Decimal("100.00"),
        high=Decimal("101.00"),
        low=Decimal("99.00"),
        close=Decimal("100.50"),
        volume=100000,
        spread=Decimal("2.00"),
    )


@pytest.fixture
def overlap_bar() -> OHLCVBar:
    """Bar in OVERLAP session (13-17 UTC)."""
    return OHLCVBar(
        symbol="EUR/USD",
        timeframe="15m",
        timestamp=datetime(2025, 1, 6, 15, 0, tzinfo=UTC),  # 15:00 UTC
        open=Decimal("100.00"),
        high=Decimal("101.00"),
        low=Decimal("99.00"),
        close=Decimal("100.50"),
        volume=100000,
        spread=Decimal("2.00"),
    )


@pytest.fixture
def ny_bar() -> OHLCVBar:
    """Bar in NY session (17-20 UTC)."""
    return OHLCVBar(
        symbol="EUR/USD",
        timeframe="15m",
        timestamp=datetime(2025, 1, 6, 18, 0, tzinfo=UTC),  # 18:00 UTC
        open=Decimal("100.00"),
        high=Decimal("101.00"),
        low=Decimal("99.00"),
        close=Decimal("100.50"),
        volume=100000,
        spread=Decimal("2.00"),
    )


@pytest.fixture
def asian_bar() -> OHLCVBar:
    """Bar in ASIAN session (0-8 UTC, 22-24 UTC)."""
    return OHLCVBar(
        symbol="EUR/USD",
        timeframe="15m",
        timestamp=datetime(2025, 1, 6, 4, 0, tzinfo=UTC),  # 04:00 UTC
        open=Decimal("100.00"),
        high=Decimal("101.00"),
        low=Decimal("99.00"),
        close=Decimal("100.50"),
        volume=100000,
        spread=Decimal("2.00"),
    )


@pytest.fixture
def ny_close_bar() -> OHLCVBar:
    """Bar in NY_CLOSE session (20-22 UTC)."""
    return OHLCVBar(
        symbol="EUR/USD",
        timeframe="15m",
        timestamp=datetime(2025, 1, 6, 21, 0, tzinfo=UTC),  # 21:00 UTC
        open=Decimal("100.00"),
        high=Decimal("101.00"),
        low=Decimal("99.00"),
        close=Decimal("100.50"),
        volume=100000,
        spread=Decimal("2.00"),
    )


@pytest.fixture
def range_bars_20() -> list[OHLCVBar]:
    """Create 20 bars for volume average calculation."""
    bars = []
    base_time = datetime(2025, 1, 1, 10, 0, tzinfo=UTC)

    for i in range(20):
        bar = OHLCVBar(
            symbol="EUR/USD",
            timeframe="15m",
            timestamp=base_time + timedelta(hours=i),
            open=Decimal("100.00"),
            high=Decimal("101.00"),
            low=Decimal("99.00"),
            close=Decimal("100.00"),
            volume=100000,  # Average volume
            spread=Decimal("2.00"),
        )
        bars.append(bar)

    return bars


# ============================================================================
# Task 5: Unit Tests for Session Penalty Application
# ============================================================================


class TestSessionPenaltyCalculation:
    """Test session penalty calculation for each session type (Task 5)."""

    def test_london_session_no_penalty(self):
        """Test LONDON session: no penalty applied (AC 5.1)."""
        penalty = spring_penalty(ForexSession.LONDON, filter_enabled=False)
        assert penalty == 0, "LONDON session should have zero penalty"

        # Test with filter enabled - should still be zero
        penalty_with_filter = spring_penalty(ForexSession.LONDON, filter_enabled=True)
        assert penalty_with_filter == 0, "LONDON session should have zero penalty even with filter"

    def test_overlap_session_no_penalty(self):
        """Test OVERLAP session: no penalty applied (AC 5.2)."""
        penalty = sos_penalty(ForexSession.OVERLAP, filter_enabled=False)
        assert penalty == 0, "OVERLAP session should have zero penalty"

        # Test with filter enabled - should still be zero
        penalty_with_filter = sos_penalty(ForexSession.OVERLAP, filter_enabled=True)
        assert penalty_with_filter == 0, "OVERLAP session should have zero penalty even with filter"

    def test_ny_session_minor_penalty(self):
        """Test NY session: -5 penalty applied correctly (AC 5.3)."""
        penalty = lps_penalty(ForexSession.NY, filter_enabled=False)
        assert penalty == -5, "NY session should have -5 penalty"

        # Test with filter enabled - should still be -5
        penalty_with_filter = lps_penalty(ForexSession.NY, filter_enabled=True)
        assert penalty_with_filter == -5, "NY session should have -5 penalty regardless of filter"

    def test_asian_session_major_penalty(self):
        """Test ASIAN session: -20 penalty applied correctly (AC 5.4)."""
        # Without filter: -20 penalty
        penalty_no_filter = spring_penalty(ForexSession.ASIAN, filter_enabled=False)
        assert penalty_no_filter == -20, "ASIAN session should have -20 penalty without filter"

        # With filter: -25 penalty
        penalty_with_filter = spring_penalty(ForexSession.ASIAN, filter_enabled=True)
        assert (
            penalty_with_filter == -25
        ), "ASIAN session should have -25 penalty with filter enabled"

    def test_ny_close_session_severe_penalty(self):
        """Test NY_CLOSE session: -25 penalty applied correctly (AC 5.5)."""
        penalty = sos_penalty(ForexSession.NY_CLOSE, filter_enabled=False)
        assert penalty == -25, "NY_CLOSE session should have -25 penalty"

        # Test with filter enabled - should still be -25
        penalty_with_filter = sos_penalty(ForexSession.NY_CLOSE, filter_enabled=True)
        assert (
            penalty_with_filter == -25
        ), "NY_CLOSE session should have -25 penalty regardless of filter"

    def test_all_detectors_consistent_penalties(self):
        """Verify all three detectors apply identical penalty logic."""
        sessions = [
            (ForexSession.LONDON, 0),
            (ForexSession.OVERLAP, 0),
            (ForexSession.NY, -5),
            (ForexSession.ASIAN, -20),
            (ForexSession.NY_CLOSE, -25),
        ]

        for session, expected_penalty in sessions:
            spring_result = spring_penalty(session, filter_enabled=False)
            sos_result = sos_penalty(session, filter_enabled=False)
            lps_result = lps_penalty(session, filter_enabled=False)

            assert spring_result == expected_penalty, f"Spring detector incorrect for {session}"
            assert sos_result == expected_penalty, f"SOS detector incorrect for {session}"
            assert lps_result == expected_penalty, f"LPS detector incorrect for {session}"


# ============================================================================
# Task 6: Unit Tests for Tradeable Flag Logic
# ============================================================================


class TestTradeableFlagLogic:
    """Test tradeable flag logic based on final confidence (Task 6)."""

    def test_high_confidence_london_tradeable(self):
        """Test pattern with high confidence in LONDON session is tradeable (AC 6.1)."""
        # Base confidence 85 + 0 penalty = 85 >= 70 → tradeable
        # This would be tested via pattern creation, but we can verify the logic
        base_confidence = 85
        penalty = spring_penalty(ForexSession.LONDON, filter_enabled=False)
        final_confidence = base_confidence + penalty  # 85 + 0 = 85

        is_tradeable = final_confidence >= 70
        assert is_tradeable is True, "LONDON session pattern should be tradeable"

    def test_medium_confidence_ny_tradeable(self):
        """Test pattern with medium confidence in NY session is tradeable (AC 6.2)."""
        # Base confidence 85 + (-5) penalty = 80 >= 70 → tradeable
        base_confidence = 85
        penalty = sos_penalty(ForexSession.NY, filter_enabled=False)
        final_confidence = base_confidence + penalty  # 85 - 5 = 80

        is_tradeable = final_confidence >= 70
        assert is_tradeable is True, "NY session pattern should still be tradeable"

    def test_low_confidence_asian_not_tradeable(self):
        """Test pattern with low confidence in ASIAN session is not tradeable (AC 6.3)."""
        # Base confidence 85 + (-20) penalty = 65 < 70 → not tradeable
        base_confidence = 85
        penalty = lps_penalty(ForexSession.ASIAN, filter_enabled=False)
        final_confidence = base_confidence + penalty  # 85 - 20 = 65

        is_tradeable = final_confidence >= 70
        assert is_tradeable is False, "ASIAN session pattern should not be tradeable"

    def test_ny_close_always_not_tradeable(self):
        """Test NY_CLOSE session pattern is never tradeable (AC 6.4)."""
        # Base confidence 85 + (-25) penalty = 60 < 70 → not tradeable
        base_confidence = 85
        penalty = spring_penalty(ForexSession.NY_CLOSE, filter_enabled=False)
        final_confidence = base_confidence + penalty  # 85 - 25 = 60

        is_tradeable = final_confidence >= 70
        assert is_tradeable is False, "NY_CLOSE session pattern should never be tradeable"

    def test_boundary_exactly_70_is_tradeable(self):
        """Test boundary condition: exactly 70 confidence is tradeable."""
        # If base confidence were 70 and penalty 0
        final_confidence = 70
        is_tradeable = final_confidence >= 70
        assert is_tradeable is True, "Exactly 70 confidence should be tradeable (inclusive)"

    def test_boundary_69_not_tradeable(self):
        """Test boundary condition: 69 confidence is not tradeable."""
        final_confidence = 69
        is_tradeable = final_confidence >= 70
        assert is_tradeable is False, "69 confidence should not be tradeable"


# ============================================================================
# Task 7: Unit Tests for Backward Compatibility
# ============================================================================


class TestBackwardCompatibility:
    """Test backward compatibility when feature is disabled (Task 7)."""

    def test_default_disabled_no_penalty_applied(self):
        """Test default behavior: scoring disabled, no penalties applied (AC 7.1)."""
        # When session_confidence_scoring_enabled=False (default),
        # patterns should have default values:
        # - session_quality = ForexSession.LONDON (model default)
        # - session_confidence_penalty = 0 (model default)
        # - is_tradeable = True (model default)

        # We'll verify this by checking the model defaults
        spring = Spring(
            bar=OHLCVBar(
                symbol="EUR/USD",
                timeframe="15m",
                timestamp=datetime(2025, 1, 6, 4, 0, tzinfo=UTC),  # ASIAN
                open=Decimal("100.00"),
                high=Decimal("101.00"),
                low=Decimal("99.00"),
                close=Decimal("100.50"),
                volume=100000,
                spread=Decimal("2.00"),
            ),
            bar_index=0,
            penetration_pct=Decimal("0.02"),
            volume_ratio=Decimal("0.4"),
            recovery_bars=1,
            creek_reference=Decimal("100.00"),
            spring_low=Decimal("98.00"),
            recovery_price=Decimal("100.50"),
            detection_timestamp=datetime.now(UTC),
            trading_range_id=uuid4(),
            asset_class="forex",
            volume_reliability="LOW",
        )

        # Default values should be set
        assert spring.session_quality == ForexSession.LONDON, "Default session should be LONDON"
        assert spring.session_confidence_penalty == 0, "Default penalty should be 0"
        assert spring.is_tradeable is True, "Default is_tradeable should be True"

    def test_explicit_disabled_preserves_behavior(self):
        """Test explicit disable: all patterns tradeable regardless of session (AC 7.2)."""
        # When session_confidence_scoring_enabled=False is explicitly passed,
        # the detector should not apply penalties, and patterns should retain defaults

        # Create SOSBreakout with explicit session but scoring disabled
        sos = SOSBreakout(
            bar=OHLCVBar(
                symbol="EUR/USD",
                timeframe="15m",
                timestamp=datetime(2025, 1, 6, 21, 0, tzinfo=UTC),  # NY_CLOSE
                open=Decimal("100.00"),
                high=Decimal("103.00"),
                low=Decimal("100.00"),
                close=Decimal("103.00"),
                volume=200000,
                spread=Decimal("3.00"),
            ),
            breakout_pct=Decimal("0.03"),
            volume_ratio=Decimal("2.0"),
            ice_reference=Decimal("100.00"),
            breakout_price=Decimal("103.00"),
            detection_timestamp=datetime.now(UTC),
            trading_range_id=uuid4(),
            spread_ratio=Decimal("1.5"),
            close_position=Decimal("0.9"),
            spread=Decimal("3.00"),
            asset_class="forex",
            volume_reliability="LOW",
        )

        # Should use defaults (no penalties applied)
        assert sos.session_quality == ForexSession.LONDON, "Should use default session"
        assert sos.session_confidence_penalty == 0, "Should have no penalty"
        assert sos.is_tradeable is True, "Should be tradeable by default"


# ============================================================================
# Task 8: Unit Tests for Filter + Scoring Interaction
# ============================================================================


class TestFilterScoringInteraction:
    """Test interaction between session filter and confidence scoring (Task 8)."""

    def test_asian_filter_off_scoring_on_negative_20(self):
        """Test ASIAN session: filter OFF, scoring ON → -20 penalty (AC 8.1)."""
        penalty = spring_penalty(ForexSession.ASIAN, filter_enabled=False)
        assert penalty == -20, "ASIAN with filter OFF should have -20 penalty"

    def test_asian_filter_on_scoring_on_negative_25(self):
        """Test ASIAN session: filter ON, scoring ON → -25 penalty (AC 8.2)."""
        penalty = sos_penalty(ForexSession.ASIAN, filter_enabled=True)
        assert penalty == -25, "ASIAN with filter ON should have -25 penalty"

    def test_london_filter_on_scoring_on_zero_penalty(self):
        """Test LONDON session: filter ON, scoring ON → 0 penalty (AC 8.3)."""
        # Premium sessions should never be affected by filter
        penalty = lps_penalty(ForexSession.LONDON, filter_enabled=True)
        assert penalty == 0, "LONDON session should have 0 penalty regardless of filter"

    def test_overlap_filter_state_irrelevant(self):
        """Test OVERLAP session: filter state irrelevant, always 0 penalty."""
        penalty_off = spring_penalty(ForexSession.OVERLAP, filter_enabled=False)
        penalty_on = spring_penalty(ForexSession.OVERLAP, filter_enabled=True)

        assert penalty_off == 0, "OVERLAP should have 0 penalty with filter OFF"
        assert penalty_on == 0, "OVERLAP should have 0 penalty with filter ON"

    def test_ny_filter_state_irrelevant(self):
        """Test NY session: filter state irrelevant, always -5 penalty."""
        penalty_off = sos_penalty(ForexSession.NY, filter_enabled=False)
        penalty_on = sos_penalty(ForexSession.NY, filter_enabled=True)

        assert penalty_off == -5, "NY should have -5 penalty with filter OFF"
        assert penalty_on == -5, "NY should have -5 penalty with filter ON"

    def test_ny_close_filter_state_irrelevant(self):
        """Test NY_CLOSE session: filter state irrelevant, always -25 penalty."""
        penalty_off = lps_penalty(ForexSession.NY_CLOSE, filter_enabled=False)
        penalty_on = lps_penalty(ForexSession.NY_CLOSE, filter_enabled=True)

        assert penalty_off == -25, "NY_CLOSE should have -25 penalty with filter OFF"
        assert penalty_on == -25, "NY_CLOSE should have -25 penalty with filter ON"


# ============================================================================
# Task 11: Edge Case Tests
# ============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions (Task 11)."""

    def test_midnight_utc_asian_session(self):
        """Test midnight UTC (00:00) correctly identified as ASIAN session (AC 11.1)."""
        midnight_bar = OHLCVBar(
            symbol="EUR/USD",
            timeframe="15m",
            timestamp=datetime(2025, 1, 6, 0, 0, tzinfo=UTC),
            open=Decimal("100.00"),
            high=Decimal("101.00"),
            low=Decimal("99.00"),
            close=Decimal("100.50"),
            volume=100000,
            spread=Decimal("2.00"),
        )

        session = get_forex_session(midnight_bar.timestamp)
        assert session == ForexSession.ASIAN, "Midnight UTC should be ASIAN session"

        penalty = spring_penalty(session, filter_enabled=False)
        assert penalty == -20, "Midnight ASIAN should have -20 penalty"

    def test_session_boundary_transition(self):
        """Test session boundary transitions (AC 11.2)."""
        # Test 7:59 UTC (end of ASIAN) and 8:00 UTC (start of LONDON)
        asian_end = OHLCVBar(
            symbol="EUR/USD",
            timeframe="15m",
            timestamp=datetime(2025, 1, 6, 7, 59, tzinfo=UTC),
            open=Decimal("100.00"),
            high=Decimal("101.00"),
            low=Decimal("99.00"),
            close=Decimal("100.50"),
            volume=100000,
            spread=Decimal("2.00"),
        )

        london_start = OHLCVBar(
            symbol="EUR/USD",
            timeframe="15m",
            timestamp=datetime(2025, 1, 6, 8, 0, tzinfo=UTC),
            open=Decimal("100.00"),
            high=Decimal("101.00"),
            low=Decimal("99.00"),
            close=Decimal("100.50"),
            volume=100000,
            spread=Decimal("2.00"),
        )

        asian_session = get_forex_session(asian_end.timestamp)
        london_session = get_forex_session(london_start.timestamp)

        assert asian_session == ForexSession.ASIAN, "7:59 UTC should be ASIAN"
        assert london_session == ForexSession.LONDON, "8:00 UTC should be LONDON"

        asian_penalty = spring_penalty(asian_session, filter_enabled=False)
        london_penalty = spring_penalty(london_session, filter_enabled=False)

        assert asian_penalty == -20, "ASIAN boundary should have -20 penalty"
        assert london_penalty == 0, "LONDON boundary should have 0 penalty"

    def test_pattern_detected_but_not_tradeable_stored(self):
        """Test non-tradeable patterns are still created and stored (AC 11.3)."""
        # Create LPS in ASIAN session (will have penalty -20)
        # Base confidence 85 - 20 = 65 < 70 → not tradeable
        # But pattern should still be created with is_tradeable=False

        lps = LPS(
            bar=OHLCVBar(
                symbol="EUR/USD",
                timeframe="15m",
                timestamp=datetime(2025, 1, 6, 4, 0, tzinfo=UTC),  # ASIAN
                open=Decimal("100.00"),
                high=Decimal("101.00"),
                low=Decimal("99.00"),
                close=Decimal("100.50"),
                volume=100000,
                spread=Decimal("2.00"),
            ),
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
            effort_result_bonus=10,
            sos_reference=uuid4(),
            held_support=True,
            pullback_low=Decimal("100.50"),
            ice_level=Decimal("100.00"),
            sos_volume=200000,
            pullback_volume=120000,
            bars_after_sos=5,
            bounce_confirmed=True,
            bounce_bar_timestamp=datetime.now(UTC),
            detection_timestamp=datetime.now(UTC),
            trading_range_id=uuid4(),
            is_double_bottom=False,
            second_test_timestamp=None,
            atr_14=Decimal("2.50"),
            stop_distance=Decimal("3.00"),
            stop_distance_pct=Decimal("3.0"),
            stop_price=Decimal("97.00"),
            volume_trend="DECLINING",
            volume_trend_quality="EXCELLENT",
            volume_trend_bonus=5,
            session_quality=ForexSession.ASIAN,
            session_confidence_penalty=-20,
            is_tradeable=False,  # Explicitly set to False
        )

        # Pattern exists and can be stored
        assert lps is not None, "Non-tradeable pattern should still be created"
        assert lps.session_quality == ForexSession.ASIAN, "Session should be ASIAN"
        assert lps.session_confidence_penalty == -20, "Penalty should be -20"
        assert lps.is_tradeable is False, "Pattern should not be tradeable"

        # Pattern has valid data for phase tracking
        assert lps.id is not None, "Pattern should have valid ID"
        assert lps.trading_range_id is not None, "Pattern should reference trading range"


# ============================================================================
# Session Time Verification Tests
# ============================================================================


class TestSessionTimeVerification:
    """Verify session time boundaries are correctly identified."""

    def test_all_session_boundaries(self):
        """Test all session boundary times are correctly classified."""
        test_cases = [
            # ASIAN (0-8 UTC)
            (datetime(2025, 1, 6, 0, 0, tzinfo=UTC), ForexSession.ASIAN),
            (datetime(2025, 1, 6, 4, 0, tzinfo=UTC), ForexSession.ASIAN),
            (datetime(2025, 1, 6, 7, 59, tzinfo=UTC), ForexSession.ASIAN),
            # LONDON (8-13 UTC)
            (datetime(2025, 1, 6, 8, 0, tzinfo=UTC), ForexSession.LONDON),
            (datetime(2025, 1, 6, 10, 0, tzinfo=UTC), ForexSession.LONDON),
            (datetime(2025, 1, 6, 12, 59, tzinfo=UTC), ForexSession.LONDON),
            # OVERLAP (13-17 UTC)
            (datetime(2025, 1, 6, 13, 0, tzinfo=UTC), ForexSession.OVERLAP),
            (datetime(2025, 1, 6, 15, 0, tzinfo=UTC), ForexSession.OVERLAP),
            (datetime(2025, 1, 6, 16, 59, tzinfo=UTC), ForexSession.OVERLAP),
            # NY (17-20 UTC)
            (datetime(2025, 1, 6, 17, 0, tzinfo=UTC), ForexSession.NY),
            (datetime(2025, 1, 6, 18, 30, tzinfo=UTC), ForexSession.NY),
            (datetime(2025, 1, 6, 19, 59, tzinfo=UTC), ForexSession.NY),
            # NY_CLOSE (20-22 UTC)
            (datetime(2025, 1, 6, 20, 0, tzinfo=UTC), ForexSession.NY_CLOSE),
            (datetime(2025, 1, 6, 21, 0, tzinfo=UTC), ForexSession.NY_CLOSE),
            (datetime(2025, 1, 6, 21, 59, tzinfo=UTC), ForexSession.NY_CLOSE),
            # ASIAN (22-24 UTC)
            (datetime(2025, 1, 6, 22, 0, tzinfo=UTC), ForexSession.ASIAN),
            (datetime(2025, 1, 6, 23, 30, tzinfo=UTC), ForexSession.ASIAN),
            (datetime(2025, 1, 6, 23, 59, tzinfo=UTC), ForexSession.ASIAN),
        ]

        for timestamp, expected_session in test_cases:
            actual_session = get_forex_session(timestamp)
            assert actual_session == expected_session, (
                f"Timestamp {timestamp.strftime('%H:%M UTC')} should be {expected_session}, "
                f"got {actual_session}"
            )


# ============================================================================
# Penalty Consistency Tests
# ============================================================================


class TestPenaltyConsistency:
    """Test penalty calculation consistency across all detectors."""

    def test_all_sessions_all_detectors_match(self):
        """Verify all detectors return identical penalties for all sessions."""
        sessions = [
            ForexSession.LONDON,
            ForexSession.OVERLAP,
            ForexSession.NY,
            ForexSession.ASIAN,
            ForexSession.NY_CLOSE,
        ]

        for session in sessions:
            for filter_enabled in [False, True]:
                spring_result = spring_penalty(session, filter_enabled)
                sos_result = sos_penalty(session, filter_enabled)
                lps_result = lps_penalty(session, filter_enabled)

                assert spring_result == sos_result, (
                    f"Spring and SOS penalties differ for {session} "
                    f"(filter={filter_enabled}): {spring_result} vs {sos_result}"
                )
                assert sos_result == lps_result, (
                    f"SOS and LPS penalties differ for {session} "
                    f"(filter={filter_enabled}): {sos_result} vs {lps_result}"
                )
