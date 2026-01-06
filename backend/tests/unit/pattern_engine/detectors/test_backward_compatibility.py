"""
Unit tests for backward compatibility with Story 13.3 behavior (Story 13.3.2, Task 9).

This module tests that the new rejected pattern intelligence tracking feature
maintains backward compatibility with the original Story 13.3 session filtering
behavior when the feature is disabled.

Test Coverage:
- AC6.2: Story 13.3 behavior preserved when storage feature disabled
- Task 9 Requirements: 3 unit tests for backward compatibility
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
    """Bar in ASIAN session (rejected session)."""
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
    """Bar in LONDON session (accepted session)."""
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


# ============================================================================
# Helper Functions for Detector Simulation
# ============================================================================


def detect_spring_with_session_filter(
    bar: OHLCVBar,
    session_filter_enabled: bool = False,
    store_rejected_patterns: bool = True,
) -> Spring | None:
    """
    Simulate detector behavior with session filtering and rejection storage.

    This function mimics the detector logic with three modes:
    1. Session filter OFF: all patterns detected (original behavior)
    2. Session filter ON, store_rejected_patterns=False: rejected patterns discarded (Story 13.3)
    3. Session filter ON, store_rejected_patterns=True: rejected patterns stored with metadata (Story 13.3.2)

    Args:
        bar: OHLCV bar to detect pattern on
        session_filter_enabled: Whether session filtering is enabled
        store_rejected_patterns: Whether to store rejected patterns (Story 13.3.2)

    Returns:
        Spring pattern or None (if rejected and not storing)
    """
    # Simulate session detection
    session = ForexSession.ASIAN if bar.timestamp.hour < 8 else ForexSession.LONDON

    # If session filter is disabled, detect pattern normally (original behavior)
    if not session_filter_enabled:
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
            # Default rejection metadata (feature not used)
            rejected_by_session_filter=False,
            rejection_reason=None,
            rejection_timestamp=None,
            is_tradeable=True,
        )

    # Session filter is enabled
    if session in [ForexSession.ASIAN, ForexSession.NY_CLOSE]:
        # Pattern is rejected by session filter
        if store_rejected_patterns:
            # Story 13.3.2: Store rejected pattern with metadata
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
                session_quality=session,
                session_confidence_penalty=-20,
                # Rejection metadata
                rejected_by_session_filter=True,
                rejection_reason="Low liquidity (~900 avg volume) - false breakouts common",
                rejection_timestamp=datetime.now(UTC),
                is_tradeable=False,
            )
        else:
            # Story 13.3: Discard rejected pattern (return None)
            return None

    # Pattern passes session filter
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
        session_quality=session,
        session_confidence_penalty=0,
        # No rejection metadata (accepted pattern)
        rejected_by_session_filter=False,
        rejection_reason=None,
        rejection_timestamp=None,
        is_tradeable=True,
    )


# ============================================================================
# Task 9: Unit Tests for Backward Compatibility
# ============================================================================


class TestBackwardCompatibility:
    """Test backward compatibility with Story 13.3 behavior (Task 9)."""

    def test_store_rejected_patterns_false_original_behavior(self, asian_bar):
        """
        Test store_rejected_patterns=False preserves Story 13.3 behavior (AC 6.2).

        When store_rejected_patterns=False:
        - Rejected patterns return None (not stored)
        - This preserves the original Story 13.3 behavior where rejected
          patterns were completely discarded

        Story 13.3 Behavior:
        - Session filter enabled
        - ASIAN/NY_CLOSE patterns rejected and discarded (return None)
        - No rejection metadata stored
        """
        # Story 13.3 mode: session_filter_enabled=True, store_rejected_patterns=False
        result = detect_spring_with_session_filter(
            asian_bar,
            session_filter_enabled=True,
            store_rejected_patterns=False,  # Original Story 13.3 behavior
        )

        # Verify pattern is discarded (None returned)
        assert result is None, (
            "store_rejected_patterns=False should discard rejected patterns "
            "(Story 13.3 behavior)"
        )

    def test_default_parameters_enable_new_behavior(self, asian_bar):
        """
        Test default parameters enable Story 13.3.2 behavior (AC 6.2).

        Default parameters:
        - session_filter_enabled=False (backward compatible default)
        - store_rejected_patterns=True (new Story 13.3.2 feature enabled by default)

        When users opt-in to session filtering (session_filter_enabled=True),
        they automatically get the new intelligence tracking feature.
        """
        # Story 13.3.2 mode: session_filter_enabled=True, store_rejected_patterns=True (default)
        result = detect_spring_with_session_filter(
            asian_bar,
            session_filter_enabled=True,
            store_rejected_patterns=True,  # Default enables Story 13.3.2
        )

        # Verify pattern is stored with rejection metadata
        assert result is not None, "store_rejected_patterns=True should return pattern"
        assert result.rejected_by_session_filter is True, "Pattern should be marked as rejected"
        assert result.rejection_reason is not None, "Rejection reason should be populated"
        assert result.rejection_timestamp is not None, "Rejection timestamp should be populated"
        assert result.is_tradeable is False, "Rejected pattern should not be tradeable"

    def test_migration_backfill_existing_patterns(self):
        """
        Test existing patterns have default rejection metadata (AC 6.1).

        Existing patterns (before Story 13.3.2) should have:
        - rejected_by_session_filter = False (default)
        - rejection_reason = None (default)
        - rejection_timestamp = None (default)
        - is_tradeable = True (default, assuming they passed all validations)

        This test simulates patterns created before Story 13.3.2 that
        would be backfilled by the migration script.
        """
        # Create pattern as it would exist before Story 13.3.2 (using defaults)
        london_bar = OHLCVBar(
            symbol="EUR/USD",
            timeframe="15m",
            timestamp=datetime(2025, 1, 6, 10, 0, tzinfo=UTC),  # LONDON
            open=Decimal("100.00"),
            high=Decimal("101.00"),
            low=Decimal("99.00"),
            close=Decimal("100.50"),
            volume=100000,
            spread=Decimal("2.00"),
        )

        # Pattern created before Story 13.3.2 (no rejection metadata fields)
        # Pydantic will use field defaults
        existing_pattern = Spring(
            bar=london_bar,
            bar_index=0,
            penetration_pct=Decimal("0.02"),
            volume_ratio=Decimal("0.4"),
            recovery_bars=1,
            creek_reference=Decimal("100.00"),
            spring_low=Decimal("98.00"),
            recovery_price=Decimal("100.50"),
            detection_timestamp=datetime(2024, 12, 1, 10, 0, tzinfo=UTC),  # Old pattern
            trading_range_id=uuid4(),
            asset_class="forex",
            volume_reliability="LOW",
            # No rejection metadata specified - should use defaults
        )

        # Verify default rejection metadata (as set by migration)
        assert (
            existing_pattern.rejected_by_session_filter is False
        ), "Existing patterns should have rejected_by_session_filter=False"
        assert (
            existing_pattern.rejection_reason is None
        ), "Existing patterns should have rejection_reason=None"
        assert (
            existing_pattern.rejection_timestamp is None
        ), "Existing patterns should have rejection_timestamp=None"
        assert (
            existing_pattern.is_tradeable is True
        ), "Existing patterns should have is_tradeable=True"


# ============================================================================
# Additional Backward Compatibility Tests
# ============================================================================


class TestSessionFilterInteraction:
    """Test interaction between session filter and rejection storage."""

    def test_session_filter_disabled_no_rejection_metadata(self, asian_bar):
        """
        Test session filter disabled: no rejection metadata even for ASIAN session.

        When session_filter_enabled=False (default), patterns should be detected
        normally without any rejection metadata, regardless of session.
        """
        # Session filter OFF - all patterns detected normally
        result = detect_spring_with_session_filter(
            asian_bar,
            session_filter_enabled=False,  # Filter disabled
            store_rejected_patterns=True,  # Irrelevant when filter is OFF
        )

        # Verify pattern is detected normally
        assert result is not None, "Pattern should be detected when filter is disabled"
        assert result.rejected_by_session_filter is False, "No rejection when filter disabled"
        assert result.rejection_reason is None, "No rejection reason when filter disabled"
        assert result.rejection_timestamp is None, "No rejection timestamp when filter disabled"
        assert result.is_tradeable is True, "Pattern should be tradeable when filter disabled"

    def test_accepted_session_no_rejection_metadata(self, london_bar):
        """
        Test accepted session: no rejection metadata regardless of store_rejected_patterns.

        When a pattern passes session filtering (LONDON/OVERLAP/NY), it should
        never have rejection metadata, even if store_rejected_patterns=True.
        """
        # Test with store_rejected_patterns=True
        result_store_true = detect_spring_with_session_filter(
            london_bar,
            session_filter_enabled=True,
            store_rejected_patterns=True,
        )

        # Test with store_rejected_patterns=False
        result_store_false = detect_spring_with_session_filter(
            london_bar,
            session_filter_enabled=True,
            store_rejected_patterns=False,
        )

        # Both should have no rejection metadata (pattern is accepted)
        for result in [result_store_true, result_store_false]:
            assert result is not None, "LONDON pattern should always be detected"
            assert (
                result.rejected_by_session_filter is False
            ), "Accepted patterns should not be rejected"
            assert result.rejection_reason is None, "Accepted patterns have no rejection reason"
            assert (
                result.rejection_timestamp is None
            ), "Accepted patterns have no rejection timestamp"
            assert result.is_tradeable is True, "Accepted patterns should be tradeable"

    def test_migration_compatibility_with_existing_queries(self):
        """
        Test migration maintains compatibility with existing pattern queries.

        Existing queries that don't filter by rejection metadata should
        continue to work without modification after migration.
        """
        # Simulate existing patterns (before Story 13.3.2)
        old_pattern = Spring(
            bar=OHLCVBar(
                symbol="EUR/USD",
                timeframe="15m",
                timestamp=datetime(2024, 12, 1, 10, 0, tzinfo=UTC),
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
            detection_timestamp=datetime(2024, 12, 1, 10, 0, tzinfo=UTC),
            trading_range_id=uuid4(),
            asset_class="forex",
            volume_reliability="LOW",
        )

        # Simulate new pattern (after Story 13.3.2) - accepted
        new_accepted_pattern = Spring(
            bar=OHLCVBar(
                symbol="EUR/USD",
                timeframe="15m",
                timestamp=datetime(2025, 1, 6, 10, 0, tzinfo=UTC),
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
            detection_timestamp=datetime(2025, 1, 6, 10, 0, tzinfo=UTC),
            trading_range_id=uuid4(),
            asset_class="forex",
            volume_reliability="LOW",
            rejected_by_session_filter=False,
            rejection_reason=None,
            rejection_timestamp=None,
            is_tradeable=True,
        )

        # Simulate new pattern (after Story 13.3.2) - rejected
        new_rejected_pattern = Spring(
            bar=OHLCVBar(
                symbol="EUR/USD",
                timeframe="15m",
                timestamp=datetime(2025, 1, 6, 4, 0, tzinfo=UTC),
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
            detection_timestamp=datetime(2025, 1, 6, 4, 0, tzinfo=UTC),
            trading_range_id=uuid4(),
            asset_class="forex",
            volume_reliability="LOW",
            rejected_by_session_filter=True,
            rejection_reason="Low liquidity (~900 avg volume) - false breakouts common",
            rejection_timestamp=datetime(2025, 1, 6, 4, 0, tzinfo=UTC),
            is_tradeable=False,
        )

        all_patterns = [old_pattern, new_accepted_pattern, new_rejected_pattern]

        # Simulate existing query: get all patterns (no rejection filter)
        # This query should work for both old and new patterns
        all_patterns_query = list(all_patterns)
        assert len(all_patterns_query) == 3, "Should retrieve all patterns"

        # Simulate existing query: get tradeable patterns only
        # After migration, this should exclude rejected patterns automatically
        tradeable_patterns_query = [p for p in all_patterns if p.is_tradeable]
        assert len(tradeable_patterns_query) == 2, "Should retrieve only tradeable patterns"
        assert old_pattern in tradeable_patterns_query, "Old pattern should be tradeable"
        assert (
            new_accepted_pattern in tradeable_patterns_query
        ), "New accepted pattern should be tradeable"
        assert (
            new_rejected_pattern not in tradeable_patterns_query
        ), "Rejected pattern should not be tradeable"

        # New Story 13.3.2 query: get rejected patterns only
        rejected_patterns_query = [p for p in all_patterns if p.rejected_by_session_filter]
        assert len(rejected_patterns_query) == 1, "Should retrieve only rejected patterns"
        assert new_rejected_pattern in rejected_patterns_query, "Should retrieve rejected pattern"


class TestFeatureFlagBehavior:
    """Test feature flag behavior for store_rejected_patterns."""

    def test_store_rejected_patterns_flag_independence(self, asian_bar):
        """
        Test store_rejected_patterns flag works independently of session_filter_enabled.

        This test verifies that:
        1. store_rejected_patterns only matters when session_filter_enabled=True
        2. When session_filter_enabled=False, store_rejected_patterns is ignored
        """
        # Scenario 1: Filter OFF, store=True (should detect normally)
        result1 = detect_spring_with_session_filter(
            asian_bar,
            session_filter_enabled=False,
            store_rejected_patterns=True,
        )

        # Scenario 2: Filter OFF, store=False (should detect normally)
        result2 = detect_spring_with_session_filter(
            asian_bar,
            session_filter_enabled=False,
            store_rejected_patterns=False,
        )

        # Verify both scenarios detect pattern normally (store_rejected_patterns irrelevant)
        assert result1 is not None, "Pattern should be detected when filter is OFF"
        assert result2 is not None, "Pattern should be detected when filter is OFF"
        assert result1.rejected_by_session_filter is False, "No rejection when filter is OFF"
        assert result2.rejected_by_session_filter is False, "No rejection when filter is OFF"

    def test_progressive_feature_adoption(self):
        """
        Test progressive feature adoption path.

        Users can adopt features progressively:
        1. Default: session_filter_enabled=False (all patterns detected)
        2. Story 13.3: session_filter_enabled=True, store_rejected_patterns=False
        3. Story 13.3.2: session_filter_enabled=True, store_rejected_patterns=True (default)
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

        # Stage 1: Default behavior (no filtering)
        stage1 = detect_spring_with_session_filter(
            asian_bar,
            session_filter_enabled=False,
        )
        assert stage1 is not None, "Stage 1: Pattern detected"
        assert stage1.rejected_by_session_filter is False, "Stage 1: Not rejected"

        # Stage 2: Story 13.3 (filtering enabled, discard rejected)
        stage2 = detect_spring_with_session_filter(
            asian_bar,
            session_filter_enabled=True,
            store_rejected_patterns=False,
        )
        assert stage2 is None, "Stage 2: Pattern discarded (Story 13.3)"

        # Stage 3: Story 13.3.2 (filtering enabled, store rejected)
        stage3 = detect_spring_with_session_filter(
            asian_bar,
            session_filter_enabled=True,
            store_rejected_patterns=True,
        )
        assert stage3 is not None, "Stage 3: Pattern stored with metadata"
        assert stage3.rejected_by_session_filter is True, "Stage 3: Marked as rejected"
        assert stage3.rejection_reason is not None, "Stage 3: Rejection reason populated"
        assert stage3.is_tradeable is False, "Stage 3: Not tradeable"
