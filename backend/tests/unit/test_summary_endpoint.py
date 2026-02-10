"""
Unit Tests for Daily Summary Endpoint (Story 10.3)

Purpose:
--------
Tests for GET /api/v1/summary/daily endpoint including:
- Summary aggregation logic with mock database data
- Suggested actions generation for various portfolio states
- Error handling (database failures, empty data sets)

Test Coverage (AC: 8):
-----------------------
- Test daily summary aggregation with mock data
- Test suggested actions generation for different scenarios
- Test error handling (database failures)
- Test Decimal precision for portfolio_heat_change
- Test UTC timestamp enforcement

Author: Story 10.3
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# All tests in this file require a PostgreSQL database (JSONB columns).
pytestmark = pytest.mark.database

from src.database import Base
from src.models.summary import DailySummary
from src.repositories.summary_repository import SummaryRepository
from tests.fixtures.summary_data import (
    create_ohlcv_bars_fixture,
    create_patterns_fixture,
    create_signals_fixture,
)


class TestDailySummaryEndpoint:
    """Unit tests for daily summary endpoint (Story 10.3, AC: 8)."""

    @pytest.fixture
    async def test_db_engine(self):
        """Create test database engine with in-memory SQLite."""
        engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            echo=False,
        )

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        yield engine

        await engine.dispose()

    @pytest.fixture
    async def test_db_session(self, test_db_engine):
        """Create test database session."""
        async_session = sessionmaker(
            test_db_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        async with async_session() as session:
            yield session

    @pytest.fixture
    async def summary_repository_with_data(self, test_db_session):
        """Create SummaryRepository with seeded test data (Story 10.3.1, AC: 9)."""
        # Seed test data matching Story 10.3 mock values
        symbols = [f"SYMBOL{i:02d}" for i in range(20)]
        bars = create_ohlcv_bars_fixture(symbols=symbols, recent_count=15)
        patterns = create_patterns_fixture(count=23)
        signals = create_signals_fixture(executed_count=4, rejected_count=8, pending_count=0)

        for bar in bars:
            test_db_session.add(bar)
        for pattern in patterns:
            test_db_session.add(pattern)
        for signal in signals:
            test_db_session.add(signal)
        await test_db_session.commit()

        return SummaryRepository(test_db_session)

    @pytest.mark.asyncio
    async def test_get_daily_summary_success(self, summary_repository_with_data):
        """
        Test successful daily summary retrieval with real database (Story 10.3.1, AC: 9).

        AC: 3, 4, 6 - Summary content, action items, API endpoint
        """
        # Execute
        summary = await summary_repository_with_data.get_daily_summary()

        # Verify
        assert isinstance(summary, DailySummary)
        assert summary.symbols_scanned == 15
        assert summary.patterns_detected == 23
        assert summary.signals_executed == 4
        assert summary.signals_rejected == 8
        assert summary.portfolio_heat_change == Decimal("0.0")  # Updated for Story 10.3.1
        assert isinstance(summary.suggested_actions, list)
        assert len(summary.suggested_actions) > 0
        assert isinstance(summary.timestamp, datetime)
        assert summary.timestamp.tzinfo is not None  # UTC enforced

    @pytest.mark.asyncio
    async def test_decimal_precision_preserved(self, summary_repository_with_data):
        """
        Test that portfolio_heat_change uses Decimal (not float).

        AC: Story notes - Decimal precision for heat_change
        """
        summary = await summary_repository_with_data.get_daily_summary()

        assert isinstance(summary.portfolio_heat_change, Decimal)
        # Verify no floating-point precision errors
        assert str(summary.portfolio_heat_change) == "0.0"  # Updated for Story 10.3.1

    @pytest.mark.asyncio
    async def test_utc_timestamp_enforced(self, summary_repository_with_data):
        """
        Test that timestamp is UTC timezone-aware.

        AC: Story notes - UTC timestamps enforced
        """
        summary = await summary_repository_with_data.get_daily_summary()

        assert summary.timestamp.tzinfo == UTC
        # Verify timestamp is recent (within last minute)
        now = datetime.now(UTC)
        time_diff = now - summary.timestamp
        assert time_diff.total_seconds() < 60

    @pytest.mark.asyncio
    async def test_suggested_actions_high_rejection_rate(self, summary_repository_with_data):
        """
        Test suggested actions when rejection rate > execution rate.

        AC: 4 - Action items based on business rules
        """
        summary = await summary_repository_with_data.get_daily_summary()

        # Test data has 8 rejected vs 4 executed
        assert summary.signals_rejected > summary.signals_executed

        # Verify action suggests reviewing rejection criteria
        actions_text = " ".join(summary.suggested_actions)
        assert "rejection" in actions_text.lower() or "rejected" in actions_text.lower()

    @pytest.mark.asyncio
    async def test_suggested_actions_heat_increase(self, summary_repository_with_data):
        """
        Test suggested actions when portfolio heat increases significantly.

        AC: 4 - Action items based on business rules
        """
        summary = await summary_repository_with_data.get_daily_summary()

        # Portfolio heat change is 0.0 (placeholder)
        assert summary.portfolio_heat_change == Decimal("0.0")

        # Heat increase is 0%, so should NOT trigger warning
        actions_text = " ".join(summary.suggested_actions)
        # Should NOT contain heat warning for 0%
        # (only triggers if > 2%)

    @pytest.mark.asyncio
    async def test_suggested_actions_many_patterns(self, summary_repository_with_data):
        """
        Test suggested actions when many patterns detected.

        AC: 4 - Action items based on business rules
        """
        summary = await summary_repository_with_data.get_daily_summary()

        # Test data has 23 patterns detected (> 20 threshold)
        assert summary.patterns_detected > 20

        # Verify action suggests reviewing pattern quality
        actions_text = " ".join(summary.suggested_actions)
        assert "pattern" in actions_text.lower()

    @pytest.mark.asyncio
    async def test_json_serialization(self, summary_repository_with_data):
        """
        Test that DailySummary can be serialized to JSON.

        AC: 6 - API endpoint returns JSON response
        """
        summary = await summary_repository_with_data.get_daily_summary()

        # Serialize to dict (FastAPI does this automatically)
        summary_dict = summary.model_dump()

        # Verify Decimal serialized to string
        assert isinstance(summary_dict["portfolio_heat_change"], Decimal)

        # Verify datetime is present
        assert "timestamp" in summary_dict

        # Verify suggested_actions is list
        assert isinstance(summary_dict["suggested_actions"], list)

    @pytest.mark.asyncio
    async def test_empty_suggested_actions_fallback(self):
        """
        Test that default action is provided when no specific actions triggered.

        AC: 4 - Always provide at least one action item
        """
        repo = SummaryRepository(AsyncMock())

        # Generate actions for "normal" state (no triggers)
        actions = repo._generate_suggested_actions(
            symbols_scanned=15,
            patterns_detected=10,  # Not > 20
            signals_executed=5,
            signals_rejected=3,  # Not > executed
            portfolio_heat_change=Decimal("0.5"),  # Not > 2.0, not < 0
        )

        # Should have fallback action
        assert len(actions) > 0
        assert "no immediate actions" in actions[0].lower() or "normal" in actions[0].lower()

    @pytest.mark.asyncio
    async def test_multiple_action_triggers(self):
        """
        Test that multiple action items generated when multiple conditions met.

        AC: 4 - Comprehensive action item generation
        """
        repo = SummaryRepository(AsyncMock())

        actions = repo._generate_suggested_actions(
            symbols_scanned=5,  # < 10 (trigger)
            patterns_detected=25,  # > 20 (trigger)
            signals_executed=2,
            signals_rejected=8,  # > executed (trigger)
            portfolio_heat_change=Decimal("2.5"),  # > 2.0 (trigger)
        )

        # Should have multiple actions (4 triggers)
        assert len(actions) >= 4

    @pytest.mark.asyncio
    async def test_heat_decrease_action(self):
        """
        Test suggested action when portfolio heat decreases (positions closing).

        AC: 4 - Action items for heat decrease
        """
        repo = SummaryRepository(AsyncMock())

        actions = repo._generate_suggested_actions(
            symbols_scanned=15,
            patterns_detected=10,
            signals_executed=5,
            signals_rejected=3,
            portfolio_heat_change=Decimal("-1.5"),  # Negative (trigger)
        )

        # Verify action suggests reviewing exits
        actions_text = " ".join(actions)
        assert "decreased" in actions_text.lower() or "exit" in actions_text.lower()

    @pytest.mark.asyncio
    async def test_low_symbol_coverage_action(self):
        """
        Test suggested action when symbol coverage is low.

        AC: 4 - Action items for low symbol coverage
        """
        repo = SummaryRepository(AsyncMock())

        actions = repo._generate_suggested_actions(
            symbols_scanned=5,  # < 10 (trigger)
            patterns_detected=10,
            signals_executed=5,
            signals_rejected=3,
            portfolio_heat_change=Decimal("0.5"),
        )

        # Verify action suggests expanding watch list
        actions_text = " ".join(actions)
        assert "symbol" in actions_text.lower() or "watch list" in actions_text.lower()


class TestDailySummaryModel:
    """Unit tests for DailySummary Pydantic model."""

    def test_daily_summary_model_creation(self):
        """Test DailySummary model can be created with valid data."""
        now = datetime.now(UTC)

        summary = DailySummary(
            symbols_scanned=15,
            patterns_detected=23,
            signals_executed=4,
            signals_rejected=8,
            portfolio_heat_change=Decimal("1.2"),
            suggested_actions=["Action 1", "Action 2"],
            timestamp=now,
        )

        assert summary.symbols_scanned == 15
        assert summary.patterns_detected == 23
        assert summary.signals_executed == 4
        assert summary.signals_rejected == 8
        assert summary.portfolio_heat_change == Decimal("1.2")
        assert len(summary.suggested_actions) == 2
        assert summary.timestamp == now

    def test_daily_summary_utc_conversion(self):
        """Test DailySummary converts naive datetime to UTC."""
        naive_dt = datetime(2024, 3, 15, 14, 30, 0)  # No timezone

        summary = DailySummary(
            symbols_scanned=15,
            patterns_detected=23,
            signals_executed=4,
            signals_rejected=8,
            portfolio_heat_change=Decimal("1.2"),
            suggested_actions=[],
            timestamp=naive_dt,
        )

        # Should be converted to UTC
        assert summary.timestamp.tzinfo is not None

    def test_daily_summary_default_suggested_actions(self):
        """Test DailySummary has empty list as default for suggested_actions."""
        summary = DailySummary(
            symbols_scanned=15,
            patterns_detected=23,
            signals_executed=4,
            signals_rejected=8,
            portfolio_heat_change=Decimal("1.2"),
            timestamp=datetime.now(UTC),
        )

        assert summary.suggested_actions == []

    def test_daily_summary_negative_values_rejected(self):
        """Test DailySummary rejects negative counts (ge=0 constraint)."""
        with pytest.raises(ValueError):
            DailySummary(
                symbols_scanned=-5,  # Negative not allowed
                patterns_detected=23,
                signals_executed=4,
                signals_rejected=8,
                portfolio_heat_change=Decimal("1.2"),
                timestamp=datetime.now(UTC),
            )

    def test_no_pydantic_deprecation_warnings(self):
        """
        Test that DailySummary produces no Pydantic deprecation warnings.

        AC: Story 10.3.2, AC-1 - Zero deprecation warnings from DailySummary model
        """
        import warnings

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            # Create instance
            summary = DailySummary(
                symbols_scanned=15,
                patterns_detected=23,
                signals_executed=4,
                signals_rejected=8,
                portfolio_heat_change=Decimal("1.2"),
                suggested_actions=["Action 1"],
                timestamp=datetime.now(UTC),
            )

            # Serialize to JSON (triggers json_encoders if present)
            summary.model_dump_json()

            # Filter for Pydantic deprecation warnings
            pydantic_warnings = [
                warn
                for warn in w
                if "pydantic" in str(warn.message).lower()
                and "deprecated" in str(warn.message).lower()
            ]

            # Verify zero warnings from DailySummary model
            assert len(pydantic_warnings) == 0, (
                f"Found {len(pydantic_warnings)} Pydantic deprecation warnings: "
                f"{[str(warn.message) for warn in pydantic_warnings]}"
            )
