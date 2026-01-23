"""
Unit Tests for BarWindowManager (Story 19.2)

Test Coverage:
--------------
- Window creation and initialization
- Rolling window FIFO behavior (add/evict)
- State tracking (ready, hydrating, insufficient_data)
- Startup hydration
- Memory usage calculation
- Window querying and management

Author: Story 19.2
"""

from collections import deque
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from src.models.ohlcv import OHLCVBar
from src.pattern_engine.bar_window_manager import (
    BarWindow,
    BarWindowManager,
    WindowState,
)


class TestWindowState:
    """Test Suite for WindowState enum."""

    def test_window_state_has_all_required_states(self):
        """Verify WindowState has all required states (AC5)."""
        required_states = {"ready", "hydrating", "insufficient_data"}
        actual_states = {state.value for state in WindowState}
        assert actual_states == required_states

    def test_window_state_values(self):
        """Verify WindowState enum values match specification."""
        assert WindowState.READY.value == "ready"
        assert WindowState.HYDRATING.value == "hydrating"
        assert WindowState.INSUFFICIENT_DATA.value == "insufficient_data"


class TestBarWindow:
    """Test Suite for BarWindow dataclass."""

    def test_bar_window_initialization(self):
        """Verify BarWindow initializes with correct defaults."""
        window = BarWindow(symbol="AAPL")

        assert window.symbol == "AAPL"
        assert isinstance(window.bars, deque)
        assert window.bars.maxlen == 200
        assert window.state == WindowState.HYDRATING
        assert window.last_updated is None

    def test_bar_window_deque_maxlen_enforced(self):
        """Verify deque maxlen is enforced to 200 (AC1, AC3)."""
        window = BarWindow(symbol="AAPL")

        # Add 250 bars
        for i in range(250):
            bar = _create_test_bar("AAPL", i)
            window.bars.append(bar)

        # Should only have 200 bars (oldest 50 evicted)
        assert len(window.bars) == 200

    def test_bar_window_fifo_behavior(self):
        """Verify FIFO eviction behavior (AC3)."""
        window = BarWindow(symbol="AAPL")

        # Add 200 bars
        bars = [_create_test_bar("AAPL", i) for i in range(200)]
        for bar in bars:
            window.bars.append(bar)

        # Add one more bar
        new_bar = _create_test_bar("AAPL", 200)
        window.bars.append(new_bar)

        # Oldest bar (index 0) should be evicted
        assert len(window.bars) == 200
        assert window.bars[0].timestamp == bars[1].timestamp  # Second bar is now first
        assert window.bars[-1].timestamp == new_bar.timestamp


class TestBarWindowManager:
    """Test Suite for BarWindowManager class."""

    def test_initialization(self):
        """Verify BarWindowManager initializes correctly."""
        manager = BarWindowManager()

        assert manager.WINDOW_SIZE == 200
        assert manager._windows == {}
        assert manager._alpaca_client is None

    def test_initialization_with_alpaca_client(self):
        """Verify BarWindowManager accepts Alpaca client."""
        mock_client = Mock()
        manager = BarWindowManager(alpaca_client=mock_client)

        assert manager._alpaca_client is mock_client

    @pytest.mark.asyncio
    async def test_add_bar_creates_window_if_not_exists(self):
        """Verify add_bar creates window for new symbol."""
        manager = BarWindowManager()
        bar = _create_test_bar("AAPL", 0)

        await manager.add_bar("AAPL", bar)

        assert "AAPL" in manager._windows
        assert len(manager._windows["AAPL"].bars) == 1

    @pytest.mark.asyncio
    async def test_add_bar_appends_to_existing_window(self):
        """Verify add_bar appends to existing window (AC3)."""
        manager = BarWindowManager()

        # Add 5 bars
        for i in range(5):
            bar = _create_test_bar("AAPL", i)
            await manager.add_bar("AAPL", bar)

        assert len(manager._windows["AAPL"].bars) == 5

    @pytest.mark.asyncio
    async def test_add_bar_fifo_eviction_when_full(self):
        """Verify oldest bar evicted when window full (AC3)."""
        manager = BarWindowManager()

        # Add 200 bars
        bars = [_create_test_bar("AAPL", i) for i in range(200)]
        for bar in bars:
            await manager.add_bar("AAPL", bar)

        # Add one more
        new_bar = _create_test_bar("AAPL", 200)
        await manager.add_bar("AAPL", new_bar)

        window = manager._windows["AAPL"]
        assert len(window.bars) == 200
        # First bar should now be bars[1] (bars[0] evicted)
        assert window.bars[0].timestamp == bars[1].timestamp

    @pytest.mark.asyncio
    async def test_add_bar_updates_state_to_ready(self):
        """Verify window state becomes READY when 200 bars added (AC1, AC5)."""
        manager = BarWindowManager()

        # Add 199 bars - should still be HYDRATING
        for i in range(199):
            bar = _create_test_bar("AAPL", i)
            await manager.add_bar("AAPL", bar)

        assert manager._windows["AAPL"].state == WindowState.HYDRATING

        # Add 200th bar - should become READY
        bar_200 = _create_test_bar("AAPL", 199)
        await manager.add_bar("AAPL", bar_200)

        assert manager._windows["AAPL"].state == WindowState.READY

    @pytest.mark.asyncio
    async def test_add_bar_updates_last_updated_timestamp(self):
        """Verify last_updated timestamp is updated on add_bar."""
        manager = BarWindowManager()
        bar = _create_test_bar("AAPL", 0)

        before = datetime.now(UTC)
        await manager.add_bar("AAPL", bar)
        after = datetime.now(UTC)

        window = manager._windows["AAPL"]
        assert window.last_updated is not None
        assert before <= window.last_updated <= after

    def test_get_bars_returns_list_of_bars(self):
        """Verify get_bars returns all bars for symbol."""
        manager = BarWindowManager()
        window = BarWindow(symbol="AAPL")
        bars = [_create_test_bar("AAPL", i) for i in range(10)]
        window.bars.extend(bars)
        manager._windows["AAPL"] = window

        result = manager.get_bars("AAPL")

        assert len(result) == 10
        assert all(isinstance(bar, OHLCVBar) for bar in result)

    def test_get_bars_returns_empty_list_for_unknown_symbol(self):
        """Verify get_bars returns empty list for non-existent symbol."""
        manager = BarWindowManager()

        result = manager.get_bars("UNKNOWN")

        assert result == []

    def test_get_state_returns_correct_state(self):
        """Verify get_state returns window state (AC5)."""
        manager = BarWindowManager()
        window = BarWindow(symbol="AAPL", state=WindowState.READY)
        manager._windows["AAPL"] = window

        state = manager.get_state("AAPL")

        assert state == WindowState.READY

    def test_get_state_returns_insufficient_data_for_unknown_symbol(self):
        """Verify get_state returns INSUFFICIENT_DATA for non-existent symbol."""
        manager = BarWindowManager()

        state = manager.get_state("UNKNOWN")

        assert state == WindowState.INSUFFICIENT_DATA

    def test_get_memory_usage_empty_manager(self):
        """Verify memory usage calculation for empty manager."""
        manager = BarWindowManager()

        usage = manager.get_memory_usage()

        assert usage == 0

    def test_get_memory_usage_single_symbol(self):
        """Verify memory usage calculation for single symbol (AC6)."""
        manager = BarWindowManager()
        window = BarWindow(symbol="AAPL")

        # Add 200 bars
        for i in range(200):
            window.bars.append(_create_test_bar("AAPL", i))

        manager._windows["AAPL"] = window

        usage = manager.get_memory_usage()

        # Expected: (200 bars × 100 bytes) + (1 symbol × 500 bytes overhead)
        expected = (200 * 100) + 500
        assert usage == expected

    def test_get_memory_usage_50_symbols_under_limit(self):
        """Verify memory usage for 50 symbols is under 50MB (AC6)."""
        manager = BarWindowManager()

        # Add 50 symbols with 200 bars each
        for symbol_idx in range(50):
            symbol = f"SYM{symbol_idx:02d}"
            window = BarWindow(symbol=symbol)

            for bar_idx in range(200):
                window.bars.append(_create_test_bar(symbol, bar_idx))

            manager._windows[symbol] = window

        usage = manager.get_memory_usage()

        # Expected: (50 symbols × 200 bars × 100 bytes) + (50 symbols × 500 bytes overhead)
        # = 1,000,000 + 25,000 = 1,025,000 bytes ≈ 1MB
        expected = (50 * 200 * 100) + (50 * 500)
        assert usage == expected
        assert usage < 50 * 1024 * 1024  # < 50MB

    def test_get_window_count(self):
        """Verify get_window_count returns correct count."""
        manager = BarWindowManager()

        # Add 3 windows
        for symbol in ["AAPL", "TSLA", "MSFT"]:
            manager._windows[symbol] = BarWindow(symbol=symbol)

        assert manager.get_window_count() == 3

    def test_get_ready_count(self):
        """Verify get_ready_count returns correct count of READY windows."""
        manager = BarWindowManager()

        # Add windows with different states
        manager._windows["AAPL"] = BarWindow(symbol="AAPL", state=WindowState.READY)
        manager._windows["TSLA"] = BarWindow(symbol="TSLA", state=WindowState.HYDRATING)
        manager._windows["MSFT"] = BarWindow(symbol="MSFT", state=WindowState.READY)
        manager._windows["NVDA"] = BarWindow(symbol="NVDA", state=WindowState.INSUFFICIENT_DATA)

        assert manager.get_ready_count() == 2

    def test_clear_symbol(self):
        """Verify clear_symbol removes window for symbol."""
        manager = BarWindowManager()
        manager._windows["AAPL"] = BarWindow(symbol="AAPL")

        manager.clear_symbol("AAPL")

        assert "AAPL" not in manager._windows

    def test_clear_symbol_unknown_symbol_no_error(self):
        """Verify clear_symbol handles unknown symbol gracefully."""
        manager = BarWindowManager()

        # Should not raise error
        manager.clear_symbol("UNKNOWN")

    def test_clear_all(self):
        """Verify clear_all removes all windows."""
        manager = BarWindowManager()

        # Add multiple windows
        for symbol in ["AAPL", "TSLA", "MSFT"]:
            manager._windows[symbol] = BarWindow(symbol=symbol)

        manager.clear_all()

        assert len(manager._windows) == 0

    @pytest.mark.asyncio
    async def test_hydrate_symbol_without_client_raises_error(self):
        """Verify hydrate_symbol raises error if Alpaca client not configured."""
        manager = BarWindowManager(alpaca_client=None)

        with pytest.raises(ValueError, match="Alpaca client not configured"):
            await manager.hydrate_symbol("AAPL")

    @pytest.mark.asyncio
    async def test_hydrate_symbol_validates_empty_symbol(self):
        """Verify hydrate_symbol validates symbol parameter (High Issue #2)."""
        mock_client = AsyncMock()
        manager = BarWindowManager(alpaca_client=mock_client)

        # Test empty string
        with pytest.raises(ValueError, match="Symbol cannot be empty"):
            await manager.hydrate_symbol("")

        # Test whitespace only
        with pytest.raises(ValueError, match="Symbol cannot be empty"):
            await manager.hydrate_symbol("   ")

    @pytest.mark.asyncio
    async def test_hydrate_symbol_normalizes_symbol(self):
        """Verify hydrate_symbol normalizes symbol to uppercase (High Issue #2)."""
        mock_client = AsyncMock()
        mock_client.fetch_historical_bars.return_value = [
            _create_test_bar("AAPL", i) for i in range(200)
        ]
        manager = BarWindowManager(alpaca_client=mock_client)

        # Hydrate with lowercase
        await manager.hydrate_symbol("aapl")

        # Should be normalized to uppercase in window
        assert "AAPL" in manager._windows
        assert "aapl" not in manager._windows

    @pytest.mark.asyncio
    async def test_hydrate_symbol_creates_window(self):
        """Verify hydrate_symbol creates window for symbol (AC2)."""
        mock_client = AsyncMock()
        mock_client.fetch_historical_bars.return_value = [
            _create_test_bar("AAPL", i) for i in range(200)
        ]

        manager = BarWindowManager(alpaca_client=mock_client)

        await manager.hydrate_symbol("AAPL")

        assert "AAPL" in manager._windows

    @pytest.mark.asyncio
    async def test_hydrate_symbol_fetches_200_bars(self):
        """Verify hydrate_symbol fetches historical bars (AC2)."""
        from datetime import date

        mock_client = AsyncMock()
        mock_client.fetch_historical_bars.return_value = [
            _create_test_bar("AAPL", i) for i in range(200)
        ]

        manager = BarWindowManager(alpaca_client=mock_client)

        await manager.hydrate_symbol("AAPL")

        # Verify Alpaca client was called with date range
        assert mock_client.fetch_historical_bars.called
        call_args = mock_client.fetch_historical_bars.call_args
        assert call_args.kwargs["symbol"] == "AAPL"
        assert isinstance(call_args.kwargs["start_date"], date)
        assert isinstance(call_args.kwargs["end_date"], date)
        assert call_args.kwargs["timeframe"] == "1m"

    @pytest.mark.asyncio
    async def test_hydrate_symbol_state_ready_when_200_bars(self):
        """Verify window state is READY when 200 bars fetched (AC2, AC5)."""
        mock_client = AsyncMock()
        mock_client.fetch_historical_bars.return_value = [
            _create_test_bar("AAPL", i) for i in range(200)
        ]

        manager = BarWindowManager(alpaca_client=mock_client)

        state = await manager.hydrate_symbol("AAPL")

        assert state == WindowState.READY
        assert manager._windows["AAPL"].state == WindowState.READY

    @pytest.mark.asyncio
    async def test_hydrate_symbol_insufficient_data_when_less_than_200(self):
        """Verify window state is INSUFFICIENT_DATA when < 200 bars (AC5)."""
        mock_client = AsyncMock()
        # Only 50 bars available
        mock_client.fetch_historical_bars.return_value = [
            _create_test_bar("NEWIPO", i) for i in range(50)
        ]

        manager = BarWindowManager(alpaca_client=mock_client)

        state = await manager.hydrate_symbol("NEWIPO")

        assert state == WindowState.INSUFFICIENT_DATA
        assert manager._windows["NEWIPO"].state == WindowState.INSUFFICIENT_DATA

    @pytest.mark.asyncio
    async def test_hydrate_symbol_handles_api_error(self):
        """Verify hydrate_symbol handles API errors gracefully."""
        mock_client = AsyncMock()
        mock_client.fetch_historical_bars.side_effect = RuntimeError("API Error")

        manager = BarWindowManager(alpaca_client=mock_client)

        with pytest.raises(RuntimeError, match="Failed to hydrate AAPL"):
            await manager.hydrate_symbol("AAPL")

        # Window should be in INSUFFICIENT_DATA state
        assert manager._windows["AAPL"].state == WindowState.INSUFFICIENT_DATA


# Helper Functions
def _create_test_bar(symbol: str, index: int) -> OHLCVBar:
    """
    Create a test OHLCVBar for testing.

    Args:
        symbol: Stock symbol
        index: Bar index (used to generate unique timestamps)

    Returns:
        OHLCVBar instance
    """
    from datetime import timedelta

    # Start at Jan 1, 2024, 9:30 AM and add 1 minute per index
    base_timestamp = datetime(2024, 1, 1, 9, 30, tzinfo=UTC)
    timestamp = base_timestamp + timedelta(minutes=index)

    return OHLCVBar(
        id=uuid4(),
        symbol=symbol,
        timeframe="1m",
        timestamp=timestamp,
        open=Decimal("150.00"),
        high=Decimal("151.00"),
        low=Decimal("149.00"),
        close=Decimal("150.50"),
        volume=1000000,
        spread=Decimal("2.00"),
        spread_ratio=Decimal("1.0"),
        volume_ratio=Decimal("1.0"),
        created_at=datetime.now(UTC),
    )
