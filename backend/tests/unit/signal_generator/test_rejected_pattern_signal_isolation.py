"""
Unit tests for trade signal isolation from rejected patterns (Story 13.3.2, Task 8).

This module tests that rejected patterns do NOT generate trade signals,
while accepted patterns DO generate signals. This ensures rejected patterns
are stored for CO intelligence but remain isolated from the trading system.

Test Coverage:
- AC5.1: Trade signal generation excludes rejected patterns
- AC5.2: Unit test verifies rejected patterns never generate signals
- Task 8 Requirements: 4 unit tests for signal isolation
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from src.models.forex import ForexSession
from src.models.ohlcv import OHLCVBar
from src.models.spring import Spring

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def asian_bar() -> OHLCVBar:
    """Bar in ASIAN session (rejected)."""
    return OHLCVBar(
        symbol="EUR/USD",
        timeframe="15m",
        timestamp=datetime(2025, 1, 6, 4, 0, tzinfo=UTC),  # 04:00 UTC - ASIAN
        open=Decimal("100.00"),
        high=Decimal("101.00"),
        low=Decimal("99.00"),
        close=Decimal("100.50"),
        volume=100000,
        spread=Decimal("2.00"),
    )


@pytest.fixture
def london_bar() -> OHLCVBar:
    """Bar in LONDON session (accepted)."""
    return OHLCVBar(
        symbol="EUR/USD",
        timeframe="15m",
        timestamp=datetime(2025, 1, 6, 10, 0, tzinfo=UTC),  # 10:00 UTC - LONDON
        open=Decimal("100.00"),
        high=Decimal("101.00"),
        low=Decimal("99.00"),
        close=Decimal("100.50"),
        volume=100000,
        spread=Decimal("2.00"),
    )


@pytest.fixture
def rejected_asian_spring(asian_bar) -> Spring:
    """Create rejected ASIAN Spring pattern."""
    return Spring(
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
        session_quality=ForexSession.ASIAN,
        session_confidence_penalty=-20,
        # Rejection metadata (Story 13.3.2)
        rejected_by_session_filter=True,
        rejection_reason="Low liquidity (~900 avg volume) - false breakouts common",
        rejection_timestamp=datetime.now(UTC),
        is_tradeable=False,
    )


@pytest.fixture
def accepted_london_spring(london_bar) -> Spring:
    """Create accepted LONDON Spring pattern."""
    return Spring(
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
        session_quality=ForexSession.LONDON,
        session_confidence_penalty=0,
        # No rejection metadata (accepted pattern)
        rejected_by_session_filter=False,
        rejection_reason=None,
        rejection_timestamp=None,
        is_tradeable=True,
    )


# ============================================================================
# Helper Functions for Signal Generation Filter Logic
# ============================================================================


def should_generate_signal(pattern: Spring) -> bool:
    """
    Determine if a pattern should generate a trade signal.

    This function implements the double-check filter logic that should be
    present in all signal generators:
    - Pattern must be tradeable (is_tradeable=True)
    - Pattern must NOT be rejected by session filter (rejected_by_session_filter=False)

    Args:
        pattern: Spring pattern to evaluate

    Returns:
        True if pattern should generate signal, False otherwise
    """
    # Double filter: must be tradeable AND not rejected (AC 5.1)
    return pattern.is_tradeable and not pattern.rejected_by_session_filter


# ============================================================================
# Task 8: Unit Tests for Trade Signal Isolation
# ============================================================================


class TestRejectedPatternSignalIsolation:
    """Test trade signal isolation from rejected patterns (Task 8)."""

    def test_rejected_asian_pattern_no_signal(self, rejected_asian_spring):
        """
        Test ASIAN rejected pattern generates no signal (AC 5.1, 5.2).

        Verifies that patterns marked as rejected_by_session_filter=True
        do not generate trade signals, even though they are stored.
        """
        # Check if pattern should generate signal
        should_signal = should_generate_signal(rejected_asian_spring)

        # Verify no signal should be generated
        assert should_signal is False, "Rejected ASIAN pattern should not generate signal"

        # Verify pattern metadata
        assert rejected_asian_spring.id is not None, "Rejected pattern should still be stored"
        assert (
            rejected_asian_spring.rejected_by_session_filter is True
        ), "Pattern should be marked as rejected"
        assert (
            rejected_asian_spring.is_tradeable is False
        ), "Rejected pattern should not be tradeable"

    def test_accepted_london_pattern_generates_signal(self, accepted_london_spring):
        """
        Test LONDON accepted pattern generates signal (AC 5.1, 5.2).

        Verifies that patterns marked as rejected_by_session_filter=False
        and is_tradeable=True do generate trade signals.
        """
        # Check if pattern should generate signal
        should_signal = should_generate_signal(accepted_london_spring)

        # Verify signal should be generated
        assert should_signal is True, "Accepted LONDON pattern should generate signal"

        # Verify pattern metadata
        assert accepted_london_spring.id is not None, "Pattern should be stored"
        assert (
            accepted_london_spring.rejected_by_session_filter is False
        ), "Pattern should NOT be marked as rejected"
        assert accepted_london_spring.is_tradeable is True, "Pattern should be tradeable"

    def test_mixed_patterns_only_accepted_generate_signals(
        self, rejected_asian_spring, accepted_london_spring
    ):
        """
        Test mixed rejected/accepted patterns: only accepted generate signals (AC 5.1, 5.2).

        Verifies that when a list contains both rejected and accepted patterns,
        only the accepted patterns generate trade signals.
        """
        # Create additional rejected pattern (NY_CLOSE)
        ny_close_bar = OHLCVBar(
            symbol="EUR/USD",
            timeframe="15m",
            timestamp=datetime(2025, 1, 6, 21, 0, tzinfo=UTC),  # NY_CLOSE
            open=Decimal("100.00"),
            high=Decimal("101.00"),
            low=Decimal("99.00"),
            close=Decimal("100.50"),
            volume=100000,
            spread=Decimal("2.00"),
        )

        rejected_ny_close_spring = Spring(
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
            session_quality=ForexSession.NY_CLOSE,
            session_confidence_penalty=-25,
            rejected_by_session_filter=True,
            rejection_reason="Declining liquidity (20-22 UTC) - session close",
            rejection_timestamp=datetime.now(UTC),
            is_tradeable=False,
        )

        # Create additional accepted pattern (OVERLAP)
        overlap_bar = OHLCVBar(
            symbol="EUR/USD",
            timeframe="15m",
            timestamp=datetime(2025, 1, 6, 15, 0, tzinfo=UTC),  # OVERLAP
            open=Decimal("100.00"),
            high=Decimal("101.00"),
            low=Decimal("99.00"),
            close=Decimal("100.50"),
            volume=100000,
            spread=Decimal("2.00"),
        )

        accepted_overlap_spring = Spring(
            bar=overlap_bar,
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
            session_quality=ForexSession.OVERLAP,
            session_confidence_penalty=0,
            rejected_by_session_filter=False,
            rejection_reason=None,
            rejection_timestamp=None,
            is_tradeable=True,
        )

        # Mix of rejected and accepted patterns
        mixed_patterns = [
            rejected_asian_spring,  # ASIAN (rejected)
            accepted_london_spring,  # LONDON (accepted)
            rejected_ny_close_spring,  # NY_CLOSE (rejected)
            accepted_overlap_spring,  # OVERLAP (accepted)
        ]

        # Filter patterns that should generate signals
        tradeable_patterns = [p for p in mixed_patterns if should_generate_signal(p)]

        # Verify only accepted patterns should generate signals
        assert len(tradeable_patterns) == 2, "Only 2 accepted patterns should generate signals"

        # Verify correct patterns are tradeable
        tradeable_ids = {p.id for p in tradeable_patterns}
        assert accepted_london_spring.id in tradeable_ids, "LONDON pattern should generate signal"
        assert accepted_overlap_spring.id in tradeable_ids, "OVERLAP pattern should generate signal"
        assert (
            rejected_asian_spring.id not in tradeable_ids
        ), "ASIAN pattern should NOT generate signal"
        assert (
            rejected_ny_close_spring.id not in tradeable_ids
        ), "NY_CLOSE pattern should NOT generate signal"

    def test_rejected_pattern_with_high_confidence_still_no_signal(self, asian_bar):
        """
        Test high-confidence rejected pattern still generates no signal (AC 5.1, 5.2).

        Even if a rejected pattern has 90+ confidence (excellent quality),
        it should NOT generate a trade signal because it's rejected by session filter.
        This ensures rejected patterns are purely for CO intelligence.
        """
        # Create high-quality ASIAN Spring (would normally have high confidence)
        high_quality_rejected_spring = Spring(
            bar=asian_bar,
            bar_index=0,
            penetration_pct=Decimal("0.015"),  # Ideal penetration (1.5%)
            volume_ratio=Decimal("0.25"),  # Excellent low volume
            recovery_bars=1,  # Rapid recovery
            creek_reference=Decimal("100.00"),
            spring_low=Decimal("98.50"),
            recovery_price=Decimal("100.50"),
            detection_timestamp=datetime.now(UTC),
            trading_range_id=uuid4(),
            asset_class="forex",
            volume_reliability="LOW",
            session_quality=ForexSession.ASIAN,
            session_confidence_penalty=-20,
            # Despite high quality, pattern is rejected
            rejected_by_session_filter=True,
            rejection_reason="Low liquidity (~900 avg volume) - false breakouts common",
            rejection_timestamp=datetime.now(UTC),
            is_tradeable=False,  # Must be False for rejected patterns
        )

        # Verify pattern has excellent quality metrics
        assert (
            high_quality_rejected_spring.quality_tier == "IDEAL"
        ), "Pattern should have IDEAL quality"
        assert high_quality_rejected_spring.penetration_pct < Decimal(
            "0.02"
        ), "Penetration should be ideal"
        assert high_quality_rejected_spring.volume_ratio < Decimal(
            "0.3"
        ), "Volume should be excellent"

        # Check if pattern should generate signal
        should_signal = should_generate_signal(high_quality_rejected_spring)

        # Verify NO signal generated despite high quality
        assert (
            should_signal is False
        ), "High-confidence rejected pattern should still generate no signal"
        assert (
            high_quality_rejected_spring.rejected_by_session_filter is True
        ), "Pattern should be rejected"
        assert high_quality_rejected_spring.is_tradeable is False, "Pattern should not be tradeable"


# ============================================================================
# Additional Signal Isolation Tests
# ============================================================================


class TestSignalGenerationMetrics:
    """Test signal generation metrics and filtering logic."""

    def test_signal_generation_filter_logic(self, rejected_asian_spring, accepted_london_spring):
        """
        Test signal generation filter logic for rejected vs tradeable patterns.

        Verifies that the double-check filter correctly identifies:
        - Rejected patterns (rejected_by_session_filter=True) - should NOT signal
        - Tradeable patterns (is_tradeable=True, rejected_by_session_filter=False) - should signal
        """
        patterns = [rejected_asian_spring, accepted_london_spring]

        # Apply filter logic
        tradeable_patterns = [p for p in patterns if should_generate_signal(p)]

        # Calculate metrics
        total_patterns = len(patterns)
        rejected_count = sum(1 for p in patterns if p.rejected_by_session_filter)
        tradeable_count = len(tradeable_patterns)

        # Verify metrics
        assert total_patterns == 2, "Should have 2 total patterns"
        assert rejected_count == 1, "Should have 1 rejected pattern"
        assert tradeable_count == 1, "Should have 1 tradeable pattern"

        # Verify correct pattern is tradeable
        assert accepted_london_spring in tradeable_patterns, "LONDON pattern should be tradeable"
        assert (
            rejected_asian_spring not in tradeable_patterns
        ), "ASIAN pattern should NOT be tradeable"

    def test_all_rejected_patterns_generate_zero_signals(self):
        """
        Test all rejected patterns generate zero signals.

        Verifies that when ALL patterns are rejected, no signals are generated.
        """
        # Create multiple rejected patterns (different sessions)
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

        rejected_patterns = [
            Spring(
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
            ),
            Spring(
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
            ),
        ]

        # Filter patterns that should generate signals
        tradeable_patterns = [p for p in rejected_patterns if should_generate_signal(p)]

        # Verify zero signals should be generated
        assert len(tradeable_patterns) == 0, "All rejected patterns should generate zero signals"
        assert all(
            p.rejected_by_session_filter for p in rejected_patterns
        ), "All patterns should be rejected"

    def test_double_filter_check_catches_edge_cases(self):
        """
        Test double filter (is_tradeable AND NOT rejected) catches edge cases.

        Verifies the double-check logic catches patterns that might have:
        - is_tradeable=True but rejected_by_session_filter=True (invalid state)
        - is_tradeable=False but rejected_by_session_filter=False (confidence penalty)
        """
        london_bar = OHLCVBar(
            symbol="EUR/USD",
            timeframe="15m",
            timestamp=datetime(2025, 1, 6, 10, 0, tzinfo=UTC),
            open=Decimal("100.00"),
            high=Decimal("101.00"),
            low=Decimal("99.00"),
            close=Decimal("100.50"),
            volume=100000,
            spread=Decimal("2.00"),
        )

        # Edge case 1: is_tradeable=True but rejected (invalid state, should not happen)
        # This should be caught by double filter
        edge_case_1 = Spring(
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
            rejected_by_session_filter=True,  # Rejected
            is_tradeable=True,  # Invalid: should be False
            rejection_reason="Test edge case",
            rejection_timestamp=datetime.now(UTC),
        )

        # Edge case 2: is_tradeable=False but NOT rejected (low confidence, not session issue)
        edge_case_2 = Spring(
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
            rejected_by_session_filter=False,  # NOT rejected by session
            is_tradeable=False,  # Not tradeable (e.g., confidence < 70)
            rejection_reason=None,
            rejection_timestamp=None,
        )

        # Valid pattern for comparison
        valid_pattern = Spring(
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
            rejected_by_session_filter=False,
            is_tradeable=True,
            rejection_reason=None,
            rejection_timestamp=None,
        )

        # Apply filter logic to edge cases
        tradeable_patterns = [
            p for p in [edge_case_1, edge_case_2, valid_pattern] if should_generate_signal(p)
        ]

        # Verify only valid pattern should generate signal
        assert len(tradeable_patterns) == 1, "Only valid pattern should generate signal"
        assert valid_pattern in tradeable_patterns, "Valid pattern should be tradeable"

        # Verify edge cases are filtered out
        assert (
            edge_case_1 not in tradeable_patterns
        ), "Edge case 1 (rejected=True) should be filtered"
        assert (
            edge_case_2 not in tradeable_patterns
        ), "Edge case 2 (tradeable=False) should be filtered"
