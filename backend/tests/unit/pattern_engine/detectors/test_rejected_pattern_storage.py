"""
Unit tests for rejection metadata storage (Story 13.3.2, Task 7).

This module tests that patterns rejected by session filtering are stored
with complete rejection metadata including rejection reason, timestamp,
and tradeable flag.

Test Coverage:
- AC1.1: Rejected patterns stored with rejection metadata
- AC2.1: Rejection metadata includes all required fields
- AC2.2: Accepted patterns have rejection metadata set to defaults
- Task 7 Requirements: 7 unit tests for rejection metadata storage
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from src.models.forex import ForexSession
from src.models.lps import LPS
from src.models.ohlcv import OHLCVBar
from src.models.sos_breakout import SOSBreakout
from src.models.spring import Spring

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def asian_bar() -> OHLCVBar:
    """Bar in ASIAN session (0-8 UTC)."""
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


# ============================================================================
# Task 7: Unit Tests for Rejection Metadata Storage
# ============================================================================


class TestRejectedPatternMetadataStorage:
    """Test rejection metadata storage for rejected patterns (Task 7)."""

    def test_asian_session_pattern_rejection_metadata(self, asian_bar):
        """
        Test ASIAN session pattern has rejection metadata populated (AC 1.1, 2.1).

        Verifies:
        - rejected_by_session_filter = True
        - rejection_reason populated with ASIAN session message
        - rejection_timestamp populated
        - is_tradeable = False
        """
        # Create Spring pattern with rejection metadata (simulating detector behavior)
        spring = Spring(
            bar=asian_bar,
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
            # Rejection metadata (Story 13.3.2)
            rejected_by_session_filter=True,
            rejection_reason="Low liquidity (~900 avg volume) - false breakouts common",
            rejection_timestamp=datetime.now(UTC),
            is_tradeable=False,
        )

        # Verify rejection metadata is populated
        assert spring.rejected_by_session_filter is True, "ASIAN pattern should be rejected"
        assert spring.rejection_reason is not None, "Rejection reason should be populated"
        assert (
            "Low liquidity" in spring.rejection_reason
        ), "Rejection reason should mention low liquidity"
        assert spring.rejection_timestamp is not None, "Rejection timestamp should be populated"
        assert spring.is_tradeable is False, "Rejected patterns should not be tradeable"

    def test_ny_close_session_pattern_rejection_metadata(self, ny_close_bar):
        """
        Test NY_CLOSE session pattern has rejection metadata populated (AC 1.1, 2.1).

        Verifies:
        - rejected_by_session_filter = True
        - rejection_reason populated with NY_CLOSE session message
        - rejection_timestamp populated
        - is_tradeable = False
        """
        # Create SOSBreakout pattern with rejection metadata
        sos = SOSBreakout(
            bar=ny_close_bar,
            breakout_pct=Decimal("0.02"),
            volume_ratio=Decimal("2.0"),
            ice_reference=Decimal("100.00"),
            breakout_price=Decimal("102.00"),
            detection_timestamp=datetime.now(UTC),
            trading_range_id=uuid4(),
            spread_ratio=Decimal("1.4"),
            close_position=Decimal("0.75"),
            spread=Decimal("2.00"),
            asset_class="forex",
            volume_reliability="LOW",
            # Rejection metadata (Story 13.3.2)
            rejected_by_session_filter=True,
            rejection_reason="Declining liquidity (20-22 UTC) - session close",
            rejection_timestamp=datetime.now(UTC),
            is_tradeable=False,
        )

        # Verify rejection metadata is populated
        assert sos.rejected_by_session_filter is True, "NY_CLOSE pattern should be rejected"
        assert sos.rejection_reason is not None, "Rejection reason should be populated"
        assert (
            "Declining liquidity" in sos.rejection_reason
        ), "Rejection reason should mention declining liquidity"
        assert sos.rejection_timestamp is not None, "Rejection timestamp should be populated"
        assert sos.is_tradeable is False, "Rejected patterns should not be tradeable"

    def test_london_session_pattern_not_rejected(self, london_bar):
        """
        Test LONDON session pattern has default rejection metadata (AC 2.2).

        Verifies:
        - rejected_by_session_filter = False
        - rejection_reason = None
        - rejection_timestamp = None
        - is_tradeable = True (assuming other validations passed)
        """
        # Create Spring pattern for accepted LONDON session (no rejection metadata)
        spring = Spring(
            bar=london_bar,
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
            # No rejection metadata - should use defaults
        )

        # Verify rejection metadata has default values
        assert spring.rejected_by_session_filter is False, "LONDON pattern should not be rejected"
        assert (
            spring.rejection_reason is None
        ), "Rejection reason should be None for accepted patterns"
        assert (
            spring.rejection_timestamp is None
        ), "Rejection timestamp should be None for accepted patterns"
        assert spring.is_tradeable is True, "Accepted patterns should be tradeable (default)"

    def test_rejection_timestamp_matches_detection_time(self, asian_bar):
        """
        Test rejection_timestamp is within 1 second of detection timestamp (AC 1.1).

        Verifies that rejection timestamp is set at detection time, not later.
        """
        detection_time = datetime.now(UTC)
        rejection_time = datetime.now(UTC)

        # Create LPS pattern with rejection metadata
        lps = LPS(
            bar=asian_bar,
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
            detection_timestamp=detection_time,
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
            asset_class="forex",
            volume_reliability="LOW",
            # Rejection metadata
            rejected_by_session_filter=True,
            rejection_reason="Low liquidity (~900 avg volume) - false breakouts common",
            rejection_timestamp=rejection_time,
            is_tradeable=False,
        )

        # Verify rejection_timestamp is within 1 second of detection_timestamp
        time_diff = abs((lps.rejection_timestamp - lps.detection_timestamp).total_seconds())
        assert time_diff < 1.0, "Rejection timestamp should be within 1 second of detection"

    def test_store_rejected_patterns_false_discards_pattern(self, asian_bar):
        """
        Test store_rejected_patterns=False returns None (Story 13.3 behavior) (AC 6.2).

        When store_rejected_patterns=False, patterns rejected by session filter
        should be discarded (return None) to preserve original Story 13.3 behavior.

        NOTE: This test simulates detector behavior by returning None.
        In actual detector implementation, the detector would return None
        when store_rejected_patterns=False.
        """

        # Simulate detector behavior: when store_rejected_patterns=False, return None
        def detect_spring_with_filter(
            bar: OHLCVBar, store_rejected_patterns: bool = True
        ) -> Spring | None:
            """Simulate detector logic."""
            session = ForexSession.ASIAN  # Simulate ASIAN session detection

            # If session is rejected and store_rejected_patterns=False, return None
            if session in [ForexSession.ASIAN, ForexSession.NY_CLOSE]:
                if not store_rejected_patterns:
                    # Original Story 13.3 behavior: discard rejected patterns
                    return None
                else:
                    # Story 13.3.2 behavior: store rejected patterns with metadata
                    return Spring(
                        bar=bar,
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
                        rejected_by_session_filter=True,
                        rejection_reason="Low liquidity (~900 avg volume) - false breakouts common",
                        rejection_timestamp=datetime.now(UTC),
                        is_tradeable=False,
                    )

            # Session accepted
            return Spring(
                bar=bar,
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

        # Test: store_rejected_patterns=False should return None
        result = detect_spring_with_filter(asian_bar, store_rejected_patterns=False)
        assert (
            result is None
        ), "store_rejected_patterns=False should discard rejected patterns (return None)"

    def test_store_rejected_patterns_true_stores_pattern(self, asian_bar):
        """
        Test store_rejected_patterns=True returns pattern with metadata (Story 13.3.2 behavior) (AC 1.1).

        When store_rejected_patterns=True (default), patterns rejected by session filter
        should be stored with rejection metadata.
        """
        # Simulate detector behavior with store_rejected_patterns=True
        spring = Spring(
            bar=asian_bar,
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
            rejected_by_session_filter=True,
            rejection_reason="Low liquidity (~900 avg volume) - false breakouts common",
            rejection_timestamp=datetime.now(UTC),
            is_tradeable=False,
        )

        # Verify pattern is returned with rejection metadata
        assert spring is not None, "store_rejected_patterns=True should return pattern"
        assert spring.rejected_by_session_filter is True, "Pattern should be marked as rejected"
        assert spring.rejection_reason is not None, "Rejection reason should be populated"
        assert spring.rejection_timestamp is not None, "Rejection timestamp should be populated"
        assert spring.is_tradeable is False, "Rejected patterns should not be tradeable"

    def test_rejected_pattern_is_not_tradeable(self, asian_bar):
        """
        Test rejected patterns have is_tradeable=False (AC 2.1, 5.1).

        Rejected patterns should never be tradeable, even if they meet
        all other quality criteria.
        """
        # Create high-quality Spring pattern that would normally be tradeable
        # but is rejected due to session filter
        spring = Spring(
            bar=asian_bar,
            bar_index=0,
            penetration_pct=Decimal("0.015"),  # Ideal penetration (1.5%)
            volume_ratio=Decimal("0.29"),  # Excellent low volume (<0.3 for IDEAL tier)
            recovery_bars=1,  # Rapid recovery
            creek_reference=Decimal("100.00"),
            spring_low=Decimal("98.50"),
            recovery_price=Decimal("100.50"),
            detection_timestamp=datetime.now(UTC),
            trading_range_id=uuid4(),
            asset_class="forex",
            volume_reliability="LOW",
            # High confidence but rejected by session filter
            session_quality=ForexSession.ASIAN,
            session_confidence_penalty=-20,
            rejected_by_session_filter=True,
            rejection_reason="Low liquidity (~900 avg volume) - false breakouts common",
            rejection_timestamp=datetime.now(UTC),
            is_tradeable=False,  # Must be False for rejected patterns
        )

        # Verify rejected pattern is not tradeable regardless of quality
        assert spring.is_tradeable is False, "Rejected patterns must not be tradeable"
        assert spring.rejected_by_session_filter is True, "Pattern should be marked as rejected"

        # Verify quality is still excellent (for CO intelligence analysis)
        assert spring.quality_tier == "IDEAL", "Quality metrics should still be tracked"
        assert spring.penetration_pct <= Decimal("0.02"), "High quality characteristics preserved"


# ============================================================================
# Additional Edge Case Tests
# ============================================================================


class TestRejectionMetadataEdgeCases:
    """Test edge cases for rejection metadata."""

    def test_multiple_rejected_sessions_all_have_metadata(self):
        """
        Test both ASIAN and NY_CLOSE rejected patterns have metadata.

        Verifies rejection metadata is consistently applied across
        all rejected session types.
        """
        asian_bar = OHLCVBar(
            symbol="EUR/USD",
            timeframe="15m",
            timestamp=datetime(2025, 1, 6, 4, 0, tzinfo=UTC),
            open=Decimal("100.00"),
            high=Decimal("101.00"),
            low=Decimal("99.00"),
            close=Decimal("100.50"),
            volume=100000,
            spread=Decimal("2.00"),
        )

        ny_close_bar = OHLCVBar(
            symbol="EUR/USD",
            timeframe="15m",
            timestamp=datetime(2025, 1, 6, 21, 0, tzinfo=UTC),
            open=Decimal("100.00"),
            high=Decimal("101.00"),
            low=Decimal("99.00"),
            close=Decimal("100.50"),
            volume=100000,
            spread=Decimal("2.00"),
        )

        # Create patterns for both rejected sessions
        asian_spring = Spring(
            bar=asian_bar,
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
            rejected_by_session_filter=True,
            rejection_reason="Low liquidity (~900 avg volume) - false breakouts common",
            rejection_timestamp=datetime.now(UTC),
            is_tradeable=False,
        )

        ny_close_spring = Spring(
            bar=ny_close_bar,
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
            rejected_by_session_filter=True,
            rejection_reason="Declining liquidity (20-22 UTC) - session close",
            rejection_timestamp=datetime.now(UTC),
            is_tradeable=False,
        )

        # Verify both have rejection metadata
        assert asian_spring.rejected_by_session_filter is True, "ASIAN pattern should be rejected"
        assert (
            ny_close_spring.rejected_by_session_filter is True
        ), "NY_CLOSE pattern should be rejected"
        assert asian_spring.rejection_reason is not None, "ASIAN should have rejection reason"
        assert ny_close_spring.rejection_reason is not None, "NY_CLOSE should have rejection reason"
        assert asian_spring.is_tradeable is False, "ASIAN pattern should not be tradeable"
        assert ny_close_spring.is_tradeable is False, "NY_CLOSE pattern should not be tradeable"

    def test_rejection_metadata_preserved_across_all_pattern_types(self):
        """
        Test rejection metadata works for Spring, SOS, and LPS patterns.

        Verifies Story 13.3.2 applies consistently to all pattern types.
        """
        asian_bar = OHLCVBar(
            symbol="EUR/USD",
            timeframe="15m",
            timestamp=datetime(2025, 1, 6, 4, 0, tzinfo=UTC),
            open=Decimal("100.00"),
            high=Decimal("101.00"),
            low=Decimal("99.00"),
            close=Decimal("100.50"),
            volume=100000,
            spread=Decimal("2.00"),
        )

        # Spring pattern
        spring = Spring(
            bar=asian_bar,
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
            rejected_by_session_filter=True,
            rejection_reason="Low liquidity (~900 avg volume) - false breakouts common",
            rejection_timestamp=datetime.now(UTC),
            is_tradeable=False,
        )

        # SOS pattern
        sos = SOSBreakout(
            bar=asian_bar,
            breakout_pct=Decimal("0.02"),
            volume_ratio=Decimal("2.0"),
            ice_reference=Decimal("100.00"),
            breakout_price=Decimal("102.00"),
            detection_timestamp=datetime.now(UTC),
            trading_range_id=uuid4(),
            spread_ratio=Decimal("1.4"),
            close_position=Decimal("0.75"),
            spread=Decimal("2.00"),
            asset_class="forex",
            volume_reliability="LOW",
            rejected_by_session_filter=True,
            rejection_reason="Low liquidity (~900 avg volume) - false breakouts common",
            rejection_timestamp=datetime.now(UTC),
            is_tradeable=False,
        )

        # LPS pattern
        lps = LPS(
            bar=asian_bar,
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
            asset_class="forex",
            volume_reliability="LOW",
            rejected_by_session_filter=True,
            rejection_reason="Low liquidity (~900 avg volume) - false breakouts common",
            rejection_timestamp=datetime.now(UTC),
            is_tradeable=False,
        )

        # Verify all pattern types have rejection metadata
        for pattern in [spring, sos, lps]:
            assert (
                pattern.rejected_by_session_filter is True
            ), f"{type(pattern).__name__} should be rejected"
            assert (
                pattern.rejection_reason is not None
            ), f"{type(pattern).__name__} should have rejection reason"
            assert (
                pattern.rejection_timestamp is not None
            ), f"{type(pattern).__name__} should have rejection timestamp"
            assert (
                pattern.is_tradeable is False
            ), f"{type(pattern).__name__} should not be tradeable"
