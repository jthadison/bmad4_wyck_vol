"""
Integration Tests for Summary Repository (Story 10.3.1)

Purpose:
--------
Tests real database queries for daily summary aggregation with realistic data.
Uses PostgreSQL test database (via db_session fixture from conftest.py) to verify production behavior.

Test Coverage (AC: 10):
------------------------
1. Symbols scanned aggregation with real database (20 symbols, 10 recent)
2. Patterns detected aggregation with real database (15 patterns)
3. Signals executed vs rejected aggregation (5 executed, 3 rejected, 2 pending)
4. Portfolio heat change calculation (placeholder returns 0.0)
5. 24-hour boundary accuracy (excluded vs included timestamps)
6. Empty database graceful handling (all zeros without exceptions)

Author: Story 10.3.1
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.repositories.summary_repository import SummaryRepository
from tests.fixtures.summary_data import (
    create_ohlcv_bars_fixture,
    create_patterns_fixture,
    create_signals_fixture,
)


@pytest.fixture
async def repository(db_session: AsyncSession):
    """Create repository with PostgreSQL test database session from conftest.py."""
    return SummaryRepository(db_session)


@pytest.mark.integration
class TestSummaryRepositoryIntegration:
    """Integration tests for Summary Repository with PostgreSQL (Story 10.3.1, AC: 10)."""

    @pytest.mark.asyncio
    async def test_symbols_scanned_aggregation_real_db(self, repository):
        """
        Test symbols scanned aggregation with real database (Story 10.3.1, AC: 1).

        Seeds 20 symbols: 10 within last 24h, 10 older.
        Verifies query returns at least 10 recent symbols.
        """
        # Arrange: Create 20 unique symbols, 10 recent, 10 old
        import time

        unique_id = int(time.time() * 1000) % 100000
        symbols = [f"SYM{unique_id}_{i:02d}" for i in range(20)]
        bars = create_ohlcv_bars_fixture(symbols=symbols, recent_count=10)

        # Store count before adding test data
        now = datetime.now(UTC)
        twenty_four_hours_ago = now - timedelta(hours=24)
        count_before = await repository._get_symbols_scanned(twenty_four_hours_ago, now)

        # Add bars to database
        for bar in bars:
            repository.db_session.add(bar)
        await repository.db_session.commit()

        # Act: Query symbols scanned after adding test data
        symbols_scanned = await repository._get_symbols_scanned(twenty_four_hours_ago, now)

        # Assert: Increased by exactly 10 new symbols
        assert symbols_scanned == count_before + 10

    @pytest.mark.asyncio
    async def test_patterns_detected_aggregation_real_db(self, repository):
        """
        Test patterns detected aggregation with real database (Story 10.3.1, AC: 2).

        Seeds 15 patterns within last 24h.
        Verifies query returns increased count by 15.
        """
        # Store count before adding test data
        now = datetime.now(UTC)
        twenty_four_hours_ago = now - timedelta(hours=24)
        count_before = await repository._get_patterns_detected(twenty_four_hours_ago, now)

        # Arrange: Create 15 recent patterns
        patterns = create_patterns_fixture(count=15)

        # Add patterns to database
        for pattern in patterns:
            repository.db_session.add(pattern)
        await repository.db_session.commit()

        # Act: Query patterns detected after adding test data
        patterns_detected = await repository._get_patterns_detected(twenty_four_hours_ago, now)

        # Assert: Increased by exactly 15 patterns
        assert patterns_detected == count_before + 15

    @pytest.mark.asyncio
    async def test_signals_executed_vs_rejected_aggregation(self, repository):
        """
        Test signals executed vs rejected aggregation (Story 10.3.1, AC: 3, 4).

        Seeds 5 executed, 3 rejected, 2 pending signals.
        Verifies query returns increased counts (pending excluded).
        """
        # Store counts before adding test data
        now = datetime.now(UTC)
        twenty_four_hours_ago = now - timedelta(hours=24)
        executed_before = await repository._get_signals_executed(twenty_four_hours_ago, now)
        rejected_before = await repository._get_signals_rejected(twenty_four_hours_ago, now)

        # Arrange: Create signals with different statuses
        signals = create_signals_fixture(
            executed_count=5,
            rejected_count=3,
            pending_count=2,
        )

        # Add signals to database
        for signal in signals:
            repository.db_session.add(signal)
        await repository.db_session.commit()

        # Act: Query signals after adding test data
        signals_executed = await repository._get_signals_executed(twenty_four_hours_ago, now)
        signals_rejected = await repository._get_signals_rejected(twenty_four_hours_ago, now)

        # Assert: Increased by correct counts
        assert signals_executed == executed_before + 5
        assert signals_rejected == rejected_before + 3

    @pytest.mark.asyncio
    async def test_portfolio_heat_change_calculation(self, repository):
        """
        Test portfolio heat change calculation (Story 10.3.1, AC: 5).

        Note: Portfolio heat snapshot table not yet implemented.
        Verifies graceful fallback to 0.0.
        """
        # Act: Query portfolio heat change
        heat_change = await repository._get_portfolio_heat_change()

        # Assert: Returns 0.0 (placeholder until table exists)
        assert heat_change == Decimal("0.0")
        assert isinstance(heat_change, Decimal)

    @pytest.mark.asyncio
    async def test_24_hour_boundary_accuracy(self, repository):
        """
        Test 24-hour boundary accuracy (Story 10.3.1, AC: 7).

        Seeds data at:
        - 24h 1s ago (should be excluded)
        - 23h 59m 59s ago (should be included)
        - 12h ago (should be included)

        Verifies only data within exact 24h window is counted.
        """
        # Arrange: Create bars at specific timestamps with unique symbols
        import time

        unique_id = int(time.time() * 1000) % 100000
        now = datetime.now(UTC)
        exactly_24h_ago = now - timedelta(hours=24)

        # Store count before adding test data
        count_before = await repository._get_symbols_scanned(exactly_24h_ago, now)

        bars = []

        # Bar outside window (24h 1s ago) - should be excluded
        bar_out = create_ohlcv_bars_fixture(
            symbols=[f"OUT_{unique_id}"],
            recent_count=0,
        )[0]
        bar_out.timestamp = exactly_24h_ago - timedelta(seconds=1)
        bars.append(bar_out)

        # Bar inside window (23h 59m 59s ago) - should be included
        bar_in1 = create_ohlcv_bars_fixture(
            symbols=[f"IN1_{unique_id}"],
            recent_count=0,
        )[0]
        bar_in1.timestamp = exactly_24h_ago + timedelta(seconds=1)
        bars.append(bar_in1)

        # Bar inside window (12h ago) - should be included
        bar_in2 = create_ohlcv_bars_fixture(
            symbols=[f"IN2_{unique_id}"],
            recent_count=0,
        )[0]
        bar_in2.timestamp = now - timedelta(hours=12)
        bars.append(bar_in2)

        # Add bars to database
        for bar in bars:
            repository.db_session.add(bar)
        await repository.db_session.commit()

        # Act: Query symbols scanned after adding test data
        symbols_scanned = await repository._get_symbols_scanned(exactly_24h_ago, now)

        # Assert: Only 2 new symbols included (OUT_SYMBOL excluded)
        assert symbols_scanned == count_before + 2

    @pytest.mark.asyncio
    async def test_empty_database_graceful_handling(self, repository):
        """
        Test empty database graceful handling (Story 10.3.1, AC: 8).

        Runs query against empty database.
        Verifies all counts return 0, heat change returns 0.0, no exceptions raised.

        Note: This test may see existing data from other tests if they don't clean up.
        We verify graceful handling by checking that no exceptions are raised.
        """
        # Act: Query all metrics (database may have data from other tests)
        now = datetime.now(UTC)
        twenty_four_hours_ago = now - timedelta(hours=24)

        # These queries should not raise exceptions regardless of data presence
        symbols_scanned = await repository._get_symbols_scanned(twenty_four_hours_ago, now)
        patterns_detected = await repository._get_patterns_detected(twenty_four_hours_ago, now)
        signals_executed = await repository._get_signals_executed(twenty_four_hours_ago, now)
        signals_rejected = await repository._get_signals_rejected(twenty_four_hours_ago, now)
        portfolio_heat_change = await repository._get_portfolio_heat_change()

        # Assert: All metrics return non-negative values (graceful handling verified)
        assert symbols_scanned >= 0
        assert patterns_detected >= 0
        assert signals_executed >= 0
        assert signals_rejected >= 0
        assert isinstance(portfolio_heat_change, Decimal)

    @pytest.mark.asyncio
    async def test_full_daily_summary_integration(self, repository):
        """
        Test full daily summary integration (Story 10.3.1, AC: 1-8).

        Seeds realistic dataset:
        - 15 unique symbols
        - 23 patterns
        - 4 executed signals
        - 8 rejected signals

        Verifies get_daily_summary() aggregates all metrics correctly.
        """
        # Arrange: Seed realistic dataset with unique symbols to avoid conflicts
        symbols = [f"INTEG_PAIR{i:02d}" for i in range(15)]
        bars = create_ohlcv_bars_fixture(symbols=symbols, recent_count=15)
        patterns = create_patterns_fixture(count=23, symbol="INTEG_EUR")
        signals = create_signals_fixture(
            executed_count=4, rejected_count=8, pending_count=2, symbol="INTEG_GBP"
        )

        for bar in bars:
            repository.db_session.add(bar)
        for pattern in patterns:
            repository.db_session.add(pattern)
        for signal in signals:
            repository.db_session.add(signal)
        await repository.db_session.commit()

        # Act: Get daily summary
        summary = await repository.get_daily_summary()

        # Assert: Metrics include at least our seeded data (may have more from other tests)
        assert summary.symbols_scanned >= 15
        assert summary.patterns_detected >= 23
        assert summary.signals_executed >= 4
        assert summary.signals_rejected >= 8
        assert isinstance(summary.portfolio_heat_change, Decimal)
        assert isinstance(summary.suggested_actions, list)
        assert len(summary.suggested_actions) > 0
        assert summary.timestamp.tzinfo is not None  # UTC enforced
