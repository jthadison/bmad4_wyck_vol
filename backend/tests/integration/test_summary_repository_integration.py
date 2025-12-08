"""
Integration Tests for Summary Repository (Story 10.3.1)

Purpose:
--------
Tests real database queries for daily summary aggregation with realistic data.

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
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.database import Base
from src.repositories.summary_repository import SummaryRepository
from tests.fixtures.summary_data import (
    create_ohlcv_bars_fixture,
    create_patterns_fixture,
    create_signals_fixture,
)


@pytest.fixture
async def test_db_engine():
    """
    Create test database engine with in-memory SQLite.

    Note: Uses SQLite for simplicity in tests. Production uses PostgreSQL with TimescaleDB.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest.fixture
async def test_db_session(test_db_engine):
    """Create test database session."""
    async_session = sessionmaker(
        test_db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        yield session


class TestSummaryRepositoryIntegration:
    """Integration tests for Summary Repository with real database (Story 10.3.1, AC: 10)."""

    @pytest.mark.asyncio
    async def test_symbols_scanned_aggregation_real_db(self, test_db_session):
        """
        Test symbols scanned aggregation with real database (Story 10.3.1, AC: 1).

        Seeds 20 symbols: 10 within last 24h, 10 older.
        Verifies query returns exactly 10 recent symbols.
        """
        # Arrange: Create 20 symbols, 10 recent, 10 old
        symbols = [f"SYMBOL{i:02d}" for i in range(20)]
        bars = create_ohlcv_bars_fixture(symbols=symbols, recent_count=10)

        # Add bars to database
        for bar in bars:
            test_db_session.add(bar)
        await test_db_session.commit()

        repository = SummaryRepository(test_db_session)

        # Act: Query symbols scanned
        now = datetime.now(UTC)
        twenty_four_hours_ago = now - timedelta(hours=24)
        symbols_scanned = await repository._get_symbols_scanned(twenty_four_hours_ago, now)

        # Assert: Exactly 10 recent symbols
        assert symbols_scanned == 10

    @pytest.mark.asyncio
    async def test_patterns_detected_aggregation_real_db(self, test_db_session):
        """
        Test patterns detected aggregation with real database (Story 10.3.1, AC: 2).

        Seeds 15 patterns within last 24h.
        Verifies query returns exactly 15.
        """
        # Arrange: Create 15 recent patterns
        patterns = create_patterns_fixture(count=15)

        # Add patterns to database
        for pattern in patterns:
            test_db_session.add(pattern)
        await test_db_session.commit()

        repository = SummaryRepository(test_db_session)

        # Act: Query patterns detected
        now = datetime.now(UTC)
        twenty_four_hours_ago = now - timedelta(hours=24)
        patterns_detected = await repository._get_patterns_detected(twenty_four_hours_ago, now)

        # Assert: Exactly 15 patterns
        assert patterns_detected == 15

    @pytest.mark.asyncio
    async def test_signals_executed_vs_rejected_aggregation(self, test_db_session):
        """
        Test signals executed vs rejected aggregation (Story 10.3.1, AC: 3, 4).

        Seeds 5 executed, 3 rejected, 2 pending signals.
        Verifies query returns executed=5, rejected=3 (pending excluded).
        """
        # Arrange: Create signals with different statuses
        signals = create_signals_fixture(
            executed_count=5,
            rejected_count=3,
            pending_count=2,
        )

        # Add signals to database
        for signal in signals:
            test_db_session.add(signal)
        await test_db_session.commit()

        repository = SummaryRepository(test_db_session)

        # Act: Query signals
        now = datetime.now(UTC)
        twenty_four_hours_ago = now - timedelta(hours=24)
        signals_executed = await repository._get_signals_executed(twenty_four_hours_ago, now)
        signals_rejected = await repository._get_signals_rejected(twenty_four_hours_ago, now)

        # Assert: Correct counts
        assert signals_executed == 5
        assert signals_rejected == 3

    @pytest.mark.asyncio
    async def test_portfolio_heat_change_calculation(self, test_db_session):
        """
        Test portfolio heat change calculation (Story 10.3.1, AC: 5).

        Note: Portfolio heat snapshot table not yet implemented.
        Verifies graceful fallback to 0.0.
        """
        # Arrange
        repository = SummaryRepository(test_db_session)

        # Act: Query portfolio heat change
        heat_change = await repository._get_portfolio_heat_change()

        # Assert: Returns 0.0 (placeholder until table exists)
        assert heat_change == Decimal("0.0")
        assert isinstance(heat_change, Decimal)

    @pytest.mark.asyncio
    async def test_24_hour_boundary_accuracy(self, test_db_session):
        """
        Test 24-hour boundary accuracy (Story 10.3.1, AC: 7).

        Seeds data at:
        - 24h 1s ago (should be excluded)
        - 23h 59m 59s ago (should be included)
        - 12h ago (should be included)

        Verifies only data within exact 24h window is counted.
        """
        # Arrange: Create bars at specific timestamps
        now = datetime.now(UTC)
        exactly_24h_ago = now - timedelta(hours=24)

        bars = []

        # Bar outside window (24h 1s ago) - should be excluded
        bars.append(
            create_ohlcv_bars_fixture(
                symbols=["OUT_SYMBOL"],
                recent_count=0,
            )[0]._replace(timestamp=exactly_24h_ago - timedelta(seconds=1))
        )

        # Bar inside window (23h 59m 59s ago) - should be included
        bars.append(
            create_ohlcv_bars_fixture(
                symbols=["IN_SYMBOL1"],
                recent_count=0,
            )[0]._replace(timestamp=exactly_24h_ago + timedelta(seconds=1))
        )

        # Bar inside window (12h ago) - should be included
        bars.append(
            create_ohlcv_bars_fixture(
                symbols=["IN_SYMBOL2"],
                recent_count=0,
            )[0]._replace(timestamp=now - timedelta(hours=12))
        )

        # Add bars to database
        for bar in bars:
            test_db_session.add(bar)
        await test_db_session.commit()

        repository = SummaryRepository(test_db_session)

        # Act: Query symbols scanned
        symbols_scanned = await repository._get_symbols_scanned(exactly_24h_ago, now)

        # Assert: Only 2 symbols included (OUT_SYMBOL excluded)
        assert symbols_scanned == 2

    @pytest.mark.asyncio
    async def test_empty_database_graceful_handling(self, test_db_session):
        """
        Test empty database graceful handling (Story 10.3.1, AC: 8).

        Runs query against empty database.
        Verifies all counts return 0, heat change returns 0.0, no exceptions raised.
        """
        # Arrange: Empty database (no seeding)
        repository = SummaryRepository(test_db_session)

        # Act: Query all metrics
        now = datetime.now(UTC)
        twenty_four_hours_ago = now - timedelta(hours=24)

        symbols_scanned = await repository._get_symbols_scanned(twenty_four_hours_ago, now)
        patterns_detected = await repository._get_patterns_detected(twenty_four_hours_ago, now)
        signals_executed = await repository._get_signals_executed(twenty_four_hours_ago, now)
        signals_rejected = await repository._get_signals_rejected(twenty_four_hours_ago, now)
        portfolio_heat_change = await repository._get_portfolio_heat_change()

        # Assert: All metrics return graceful defaults
        assert symbols_scanned == 0
        assert patterns_detected == 0
        assert signals_executed == 0
        assert signals_rejected == 0
        assert portfolio_heat_change == Decimal("0.0")

    @pytest.mark.asyncio
    async def test_full_daily_summary_integration(self, test_db_session):
        """
        Test full daily summary integration (Story 10.3.1, AC: 1-8).

        Seeds realistic dataset:
        - 15 unique symbols
        - 23 patterns
        - 4 executed signals
        - 8 rejected signals

        Verifies get_daily_summary() aggregates all metrics correctly.
        """
        # Arrange: Seed realistic dataset
        symbols = [f"PAIR{i:02d}" for i in range(15)]
        bars = create_ohlcv_bars_fixture(symbols=symbols, recent_count=15)
        patterns = create_patterns_fixture(count=23)
        signals = create_signals_fixture(executed_count=4, rejected_count=8, pending_count=2)

        for bar in bars:
            test_db_session.add(bar)
        for pattern in patterns:
            test_db_session.add(pattern)
        for signal in signals:
            test_db_session.add(signal)
        await test_db_session.commit()

        repository = SummaryRepository(test_db_session)

        # Act: Get daily summary
        summary = await repository.get_daily_summary()

        # Assert: All metrics aggregated correctly
        assert summary.symbols_scanned == 15
        assert summary.patterns_detected == 23
        assert summary.signals_executed == 4
        assert summary.signals_rejected == 8
        assert summary.portfolio_heat_change == Decimal("0.0")  # Placeholder
        assert isinstance(summary.suggested_actions, list)
        assert len(summary.suggested_actions) > 0
        assert summary.timestamp.tzinfo is not None  # UTC enforced
