"""Unit tests for Wyckoff algorithms.

Story 11.5.1 Tasks 1-2: Test schematic matching and P&F counting.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from backend.src.models.chart import TradingRangeLevels
from backend.src.repositories.wyckoff_algorithms import (
    _calculate_atr,
    _calculate_schematic_confidence,
    calculate_cause_building,
    match_wyckoff_schematic,
)


class MockPattern:
    """Mock Pattern ORM for testing."""

    def __init__(self, pattern_type, timestamp, confidence=85):
        self.pattern_type = pattern_type
        self.pattern_bar_timestamp = timestamp
        self.confidence_score = confidence
        self.entry_price = Decimal("150.00")


class MockOHLCVBar:
    """Mock OHLCV Bar ORM for testing."""

    def __init__(self, high, low, close, timestamp):
        self.high = Decimal(str(high))
        self.low = Decimal(str(low))
        self.close = Decimal(str(close))
        self.timestamp = timestamp


class MockTradingRange:
    """Mock Trading Range ORM for testing."""

    def __init__(self, start, end):
        self.id = uuid4()
        self.start_timestamp = start
        self.end_timestamp = end


@pytest.mark.asyncio
class TestSchematicMatching:
    """Test schematic matching algorithm."""

    async def test_accumulation_1_match(self):
        """Test matching Accumulation Schematic #1 (with Spring)."""
        # Setup mock session
        session = AsyncMock()

        # Create pattern sequence for Accumulation #1
        now = datetime.utcnow()
        patterns = [
            MockPattern("PS", now - timedelta(days=90)),
            MockPattern("SC", now - timedelta(days=80)),
            MockPattern("AR", now - timedelta(days=70)),
            MockPattern("ST", now - timedelta(days=55)),
            MockPattern("SPRING", now - timedelta(days=40)),
            MockPattern("SOS", now - timedelta(days=15)),
        ]

        # Mock query result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = patterns
        session.execute = AsyncMock(return_value=mock_result)

        # Execute
        result = await match_wyckoff_schematic(
            session, "AAPL", "1D", now - timedelta(days=90), now, creek_level=140.0, ice_level=160.0
        )

        # Verify
        assert result is not None
        assert result.schematic_type == "ACCUMULATION_1"
        assert result.confidence_score >= 60
        assert result.template_data is not None
        assert len(result.template_data) > 0

    async def test_accumulation_2_match(self):
        """Test matching Accumulation Schematic #2 (LPS without Spring)."""
        session = AsyncMock()

        now = datetime.utcnow()
        patterns = [
            MockPattern("PS", now - timedelta(days=90)),
            MockPattern("SC", now - timedelta(days=80)),
            MockPattern("AR", now - timedelta(days=70)),
            MockPattern("ST", now - timedelta(days=55)),
            MockPattern("LPS", now - timedelta(days=40)),
            MockPattern("SOS", now - timedelta(days=15)),
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = patterns
        session.execute = AsyncMock(return_value=mock_result)

        result = await match_wyckoff_schematic(
            session,
            "MSFT",
            "1D",
            now - timedelta(days=90),
            now,
        )

        assert result is not None
        assert result.schematic_type == "ACCUMULATION_2"
        assert result.confidence_score >= 60

    async def test_no_patterns_returns_none(self):
        """Test that no patterns returns None."""
        session = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        session.execute = AsyncMock(return_value=mock_result)

        result = await match_wyckoff_schematic(
            session,
            "AAPL",
            "1D",
            datetime.utcnow() - timedelta(days=90),
            datetime.utcnow(),
        )

        assert result is None

    async def test_low_confidence_returns_none(self):
        """Test that low confidence (< 60%) returns None."""
        session = AsyncMock()

        # Only 2 patterns - won't match any schematic well
        now = datetime.utcnow()
        patterns = [
            MockPattern("PS", now - timedelta(days=90)),
            MockPattern("SC", now - timedelta(days=80)),
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = patterns
        session.execute = AsyncMock(return_value=mock_result)

        result = await match_wyckoff_schematic(
            session,
            "AAPL",
            "1D",
            now - timedelta(days=90),
            now,
        )

        # With only 2/6 patterns, confidence should be < 60%
        assert result is None


class TestSchematicConfidence:
    """Test confidence scoring function."""

    def test_perfect_accumulation_1_match(self):
        """Test perfect match for Accumulation #1."""
        now = datetime.utcnow()
        patterns = [
            MockPattern("PS", now - timedelta(days=90)),
            MockPattern("SC", now - timedelta(days=80)),
            MockPattern("AR", now - timedelta(days=70)),
            MockPattern("ST", now - timedelta(days=55)),
            MockPattern("SPRING", now - timedelta(days=40)),
            MockPattern("SOS", now - timedelta(days=15)),
        ]

        confidence = _calculate_schematic_confidence(patterns, "ACCUMULATION_1", 140.0, 160.0)

        # Should be 100% (base) + 10% (critical pattern bonus) = 110%, capped at 95%
        assert confidence >= 95.0

    def test_partial_match(self):
        """Test partial pattern match."""
        now = datetime.utcnow()
        patterns = [
            MockPattern("PS", now - timedelta(days=90)),
            MockPattern("SC", now - timedelta(days=80)),
            MockPattern("AR", now - timedelta(days=70)),
        ]

        confidence = _calculate_schematic_confidence(patterns, "ACCUMULATION_1", 140.0, 160.0)

        # 3/6 patterns = 50% base confidence
        assert 45.0 <= confidence <= 55.0

    def test_missing_critical_pattern(self):
        """Test match without critical pattern (Spring for Acc #1)."""
        now = datetime.utcnow()
        patterns = [
            MockPattern("PS", now - timedelta(days=90)),
            MockPattern("SC", now - timedelta(days=80)),
            MockPattern("AR", now - timedelta(days=70)),
            MockPattern("ST", now - timedelta(days=55)),
            MockPattern("SOS", now - timedelta(days=15)),
        ]

        confidence = _calculate_schematic_confidence(patterns, "ACCUMULATION_1", 140.0, 160.0)

        # 5/6 patterns but missing SPRING = ~83%, no bonus
        assert 80.0 <= confidence <= 85.0


@pytest.mark.asyncio
class TestCauseBuildingCalculation:
    """Test P&F counting algorithm."""

    async def test_active_range_with_bars(self):
        """Test P&F count with active trading range."""
        session = AsyncMock()

        # Setup trading range
        tr_id = uuid4()
        trading_ranges = [
            TradingRangeLevels(
                trading_range_id=tr_id,
                symbol="AAPL",
                creek_level=140.0,
                ice_level=160.0,
                jump_target=180.0,
                range_status="ACTIVE",
            )
        ]

        # Mock trading range ORM
        now = datetime.utcnow()
        start = now - timedelta(days=50)
        end = now
        mock_tr = MockTradingRange(start, end)
        mock_tr.id = tr_id

        mock_tr_result = MagicMock()
        mock_tr_result.scalar_one_or_none.return_value = mock_tr

        # Create OHLCV bars with varying ranges
        # Some wide-range bars (> 2x ATR) for accumulation columns
        bars = [MockOHLCVBar(145.0, 142.0, 143.5, start + timedelta(days=i)) for i in range(30)]
        # Add some wide-range bars
        bars.extend(
            [MockOHLCVBar(150.0, 142.0, 148.0, start + timedelta(days=30 + i)) for i in range(10)]
        )

        mock_bars_result = MagicMock()
        mock_bars_result.scalars.return_value.all.return_value = bars

        # Setup execute to return different results based on query
        async def mock_execute(query):
            # First call is for TradingRange, second is for OHLCV bars
            if not hasattr(mock_execute, "call_count"):
                mock_execute.call_count = 0
            mock_execute.call_count += 1

            if mock_execute.call_count == 1:
                return mock_tr_result
            else:
                return mock_bars_result

        session.execute = mock_execute

        # Execute
        result = await calculate_cause_building(session, "AAPL", "1D", trading_ranges)

        # Verify
        assert result is not None
        assert result.column_count >= 0
        assert result.target_column_count > 0
        assert result.projected_jump > trading_ranges[0].ice_level
        assert 0.0 <= result.progress_percentage <= 100.0
        assert "P&F Count" in result.count_methodology

    async def test_no_active_range_returns_none(self):
        """Test that no active range returns None."""
        session = AsyncMock()

        trading_ranges = [
            TradingRangeLevels(
                trading_range_id=uuid4(),
                symbol="AAPL",
                creek_level=140.0,
                ice_level=160.0,
                jump_target=180.0,
                range_status="COMPLETED",  # Not ACTIVE
            )
        ]

        result = await calculate_cause_building(session, "AAPL", "1D", trading_ranges)

        assert result is None

    async def test_empty_trading_ranges_returns_none(self):
        """Test that empty trading ranges list returns None."""
        session = AsyncMock()

        result = await calculate_cause_building(session, "AAPL", "1D", [])

        assert result is None


class TestATRCalculation:
    """Test Average True Range calculation."""

    def test_atr_calculation(self):
        """Test basic ATR calculation."""
        now = datetime.utcnow()
        bars = [MockOHLCVBar(150.0, 145.0, 148.0, now + timedelta(days=i)) for i in range(20)]

        atr = _calculate_atr(bars, period=14)

        # Should be close to the average range (5.0)
        assert 4.0 <= atr <= 6.0

    def test_atr_with_few_bars(self):
        """Test ATR with fewer bars than period."""
        now = datetime.utcnow()
        bars = [MockOHLCVBar(150.0, 145.0, 148.0, now + timedelta(days=i)) for i in range(5)]

        atr = _calculate_atr(bars, period=14)

        # Should still calculate based on available bars
        assert atr > 0.0

    def test_atr_with_single_bar(self):
        """Test ATR with single bar (edge case)."""
        bars = [MockOHLCVBar(150.0, 145.0, 148.0, datetime.utcnow())]

        atr = _calculate_atr(bars, period=14)

        # Should return simple range
        assert atr == 5.0
