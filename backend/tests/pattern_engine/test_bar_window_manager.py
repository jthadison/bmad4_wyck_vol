"""
Unit Tests for BarWindowManager (Story 19.2, Story 19.26)

Test Coverage:
--------------
- Window creation and initialization
- Rolling window FIFO behavior (add/evict)
- State tracking (ready, hydrating, insufficient_data)
- Startup hydration
- Memory usage calculation
- Window querying and management
- Staleness detection (Story 19.26)

Author: Story 19.2, Story 19.26
"""

from collections import deque
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock

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

    def test_bar_window_deque_maxlen_enforced(self, create_test_bar):
        """Verify deque maxlen is enforced to 200 (AC1, AC3)."""
        window = BarWindow(symbol="AAPL")

        # Add 250 bars
        for i in range(250):
            bar = create_test_bar("AAPL", i)
            window.bars.append(bar)

        # Should only have 200 bars (oldest 50 evicted)
        assert len(window.bars) == 200

    def test_bar_window_fifo_behavior(self, create_test_bar):
        """Verify FIFO eviction behavior (AC3)."""
        window = BarWindow(symbol="AAPL")

        # Add 200 bars
        bars = [create_test_bar("AAPL", i) for i in range(200)]
        for bar in bars:
            window.bars.append(bar)

        # Add one more bar
        new_bar = create_test_bar("AAPL", 200)
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
    async def test_add_bar_creates_window_if_not_exists(self, create_test_bar):
        """Verify add_bar creates window for new symbol."""
        manager = BarWindowManager()
        bar = create_test_bar("AAPL", 0)

        await manager.add_bar("AAPL", bar)

        assert "AAPL" in manager._windows
        assert len(manager._windows["AAPL"].bars) == 1

    @pytest.mark.asyncio
    async def test_add_bar_appends_to_existing_window(self, create_test_bar):
        """Verify add_bar appends to existing window (AC3)."""
        manager = BarWindowManager()

        # Add 5 bars
        for i in range(5):
            bar = create_test_bar("AAPL", i)
            await manager.add_bar("AAPL", bar)

        assert len(manager._windows["AAPL"].bars) == 5

    @pytest.mark.asyncio
    async def test_add_bar_fifo_eviction_when_full(self, create_test_bar):
        """Verify oldest bar evicted when window full (AC3)."""
        manager = BarWindowManager()

        # Add 200 bars
        bars = [create_test_bar("AAPL", i) for i in range(200)]
        for bar in bars:
            await manager.add_bar("AAPL", bar)

        # Add one more
        new_bar = create_test_bar("AAPL", 200)
        await manager.add_bar("AAPL", new_bar)

        window = manager._windows["AAPL"]
        assert len(window.bars) == 200
        # First bar should now be bars[1] (bars[0] evicted)
        assert window.bars[0].timestamp == bars[1].timestamp

    @pytest.mark.asyncio
    async def test_add_bar_updates_state_to_ready(self, create_test_bar):
        """Verify window state becomes READY when 200 bars added (AC1, AC5)."""
        manager = BarWindowManager()

        # Add 199 bars - should still be HYDRATING
        for i in range(199):
            bar = create_test_bar("AAPL", i)
            await manager.add_bar("AAPL", bar)

        assert manager._windows["AAPL"].state == WindowState.HYDRATING

        # Add 200th bar - should become READY
        bar_200 = create_test_bar("AAPL", 199)
        await manager.add_bar("AAPL", bar_200)

        assert manager._windows["AAPL"].state == WindowState.READY

    @pytest.mark.asyncio
    async def test_add_bar_updates_last_updated_timestamp(self, create_test_bar):
        """Verify last_updated timestamp is updated on add_bar."""
        manager = BarWindowManager()
        bar = create_test_bar("AAPL", 0)

        before = datetime.now(UTC)
        await manager.add_bar("AAPL", bar)
        after = datetime.now(UTC)

        window = manager._windows["AAPL"]
        assert window.last_updated is not None
        assert before <= window.last_updated <= after

    def test_get_bars_returns_list_of_bars(self, create_test_bar):
        """Verify get_bars returns all bars for symbol."""
        manager = BarWindowManager()
        window = BarWindow(symbol="AAPL")
        bars = [create_test_bar("AAPL", i) for i in range(10)]
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

    def test_get_memory_usage_single_symbol(self, create_test_bar):
        """Verify memory usage calculation for single symbol (AC6)."""
        manager = BarWindowManager()
        window = BarWindow(symbol="AAPL")

        # Add 200 bars
        for i in range(200):
            window.bars.append(create_test_bar("AAPL", i))

        manager._windows["AAPL"] = window

        usage = manager.get_memory_usage()

        # Expected: (200 bars × 100 bytes) + (1 symbol × 500 bytes overhead)
        expected = (200 * 100) + 500
        assert usage == expected

    def test_get_memory_usage_50_symbols_under_limit(self, create_test_bar):
        """Verify memory usage for 50 symbols is under 50MB (AC6)."""
        manager = BarWindowManager()

        # Add 50 symbols with 200 bars each
        for symbol_idx in range(50):
            symbol = f"SYM{symbol_idx:02d}"
            window = BarWindow(symbol=symbol)

            for bar_idx in range(200):
                window.bars.append(create_test_bar(symbol, bar_idx))

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
    async def test_hydrate_symbol_normalizes_symbol(self, create_test_bar):
        """Verify hydrate_symbol normalizes symbol to uppercase (High Issue #2)."""
        mock_client = AsyncMock()
        mock_client.fetch_historical_bars.return_value = [
            create_test_bar("AAPL", i) for i in range(200)
        ]
        manager = BarWindowManager(alpaca_client=mock_client)

        # Hydrate with lowercase
        await manager.hydrate_symbol("aapl")

        # Should be normalized to uppercase in window
        assert "AAPL" in manager._windows
        assert "aapl" not in manager._windows

    @pytest.mark.asyncio
    async def test_hydrate_symbol_creates_window(self, create_test_bar):
        """Verify hydrate_symbol creates window for symbol (AC2)."""
        mock_client = AsyncMock()
        mock_client.fetch_historical_bars.return_value = [
            create_test_bar("AAPL", i) for i in range(200)
        ]

        manager = BarWindowManager(alpaca_client=mock_client)

        await manager.hydrate_symbol("AAPL")

        assert "AAPL" in manager._windows

    @pytest.mark.asyncio
    async def test_hydrate_symbol_fetches_200_bars(self, create_test_bar):
        """Verify hydrate_symbol fetches historical bars (AC2)."""
        from datetime import date

        mock_client = AsyncMock()
        mock_client.fetch_historical_bars.return_value = [
            create_test_bar("AAPL", i) for i in range(200)
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
    async def test_hydrate_symbol_state_ready_when_200_bars(self, create_test_bar):
        """Verify window state is READY when 200 bars fetched (AC2, AC5)."""
        mock_client = AsyncMock()
        mock_client.fetch_historical_bars.return_value = [
            create_test_bar("AAPL", i) for i in range(200)
        ]

        manager = BarWindowManager(alpaca_client=mock_client)

        state = await manager.hydrate_symbol("AAPL")

        assert state == WindowState.READY
        assert manager._windows["AAPL"].state == WindowState.READY

    @pytest.mark.asyncio
    async def test_hydrate_symbol_insufficient_data_when_less_than_200(self, create_test_bar):
        """Verify window state is INSUFFICIENT_DATA when < 200 bars (AC5)."""
        mock_client = AsyncMock()
        # Only 50 bars available
        mock_client.fetch_historical_bars.return_value = [
            create_test_bar("NEWIPO", i) for i in range(50)
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


def _create_bar_with_timestamp(create_test_bar, symbol: str, timestamp: datetime, index: int = 0):
    """Helper to create a bar with a specific timestamp."""
    base_bar = create_test_bar(symbol, index)
    return OHLCVBar(
        symbol=symbol,
        timeframe="1m",
        timestamp=timestamp,
        open=base_bar.open,
        high=base_bar.high,
        low=base_bar.low,
        close=base_bar.close,
        volume=base_bar.volume,
        spread=base_bar.spread,
    )


class TestStalenessDetection:
    """Test Suite for Staleness Detection (Story 19.26)."""

    def test_is_stale_returns_true_for_unknown_symbol(self):
        """Verify is_stale returns True for non-existent symbol."""
        manager = BarWindowManager()

        assert manager.is_stale("UNKNOWN") is True

    def test_is_stale_returns_true_for_empty_window(self):
        """Verify is_stale returns True when window has no bars."""
        manager = BarWindowManager()
        manager._windows["AAPL"] = BarWindow(symbol="AAPL")

        assert manager.is_stale("AAPL") is True

    def test_is_stale_returns_false_for_fresh_data(self, create_test_bar):
        """Verify is_stale returns False when last bar is recent (Scenario 1)."""
        manager = BarWindowManager()
        window = BarWindow(symbol="AAPL")

        # Create a bar with recent timestamp (30 seconds ago)
        recent_time = datetime.now(UTC) - timedelta(seconds=30)
        bar = _create_bar_with_timestamp(create_test_bar, "AAPL", recent_time)
        window.bars.append(bar)
        manager._windows["AAPL"] = window

        assert manager.is_stale("AAPL") is False

    def test_is_stale_returns_true_for_old_data(self, create_test_bar):
        """Verify is_stale returns True when last bar is old (Scenario 2)."""
        manager = BarWindowManager()
        window = BarWindow(symbol="AAPL")

        # Create a bar with old timestamp (6 minutes ago, > 5 min threshold)
        old_time = datetime.now(UTC) - timedelta(minutes=6)
        bar = _create_bar_with_timestamp(create_test_bar, "AAPL", old_time)
        window.bars.append(bar)
        manager._windows["AAPL"] = window

        assert manager.is_stale("AAPL") is True

    def test_get_staleness_info_no_data(self):
        """Verify get_staleness_info returns correct info when no data."""
        manager = BarWindowManager()

        info = manager.get_staleness_info("UNKNOWN")

        assert info["is_stale"] is True
        assert info["reason"] == "no_data"
        assert info["last_bar_time"] is None
        assert info["age_seconds"] is None

    def test_get_staleness_info_fresh_data(self, create_test_bar):
        """Verify get_staleness_info returns correct info for fresh data."""
        manager = BarWindowManager()
        window = BarWindow(symbol="AAPL")

        # Create a bar with recent timestamp
        recent_time = datetime.now(UTC) - timedelta(seconds=30)
        bar = _create_bar_with_timestamp(create_test_bar, "AAPL", recent_time)
        window.bars.append(bar)
        manager._windows["AAPL"] = window

        info = manager.get_staleness_info("AAPL")

        assert info["is_stale"] is False
        assert info["reason"] is None
        assert info["last_bar_time"] is not None
        assert info["age_seconds"] is not None
        assert info["age_seconds"] < 60  # Should be less than 60 seconds

    def test_get_staleness_info_stale_data(self, create_test_bar):
        """Verify get_staleness_info returns correct info for stale data."""
        manager = BarWindowManager()
        window = BarWindow(symbol="AAPL")

        # Create a bar with old timestamp (8 minutes ago)
        old_time = datetime.now(UTC) - timedelta(minutes=8)
        bar = _create_bar_with_timestamp(create_test_bar, "AAPL", old_time)
        window.bars.append(bar)
        manager._windows["AAPL"] = window

        info = manager.get_staleness_info("AAPL")

        assert info["is_stale"] is True
        assert info["reason"] == "data_old"
        assert info["last_bar_time"] is not None
        assert info["age_seconds"] is not None
        assert info["age_seconds"] > 300  # Should be > 5 minutes

    def test_get_stale_symbols(self, create_test_bar):
        """Verify get_stale_symbols returns list of stale symbols."""
        manager = BarWindowManager()

        # Add fresh symbol
        fresh_window = BarWindow(symbol="AAPL")
        fresh_time = datetime.now(UTC) - timedelta(seconds=30)
        fresh_bar = _create_bar_with_timestamp(create_test_bar, "AAPL", fresh_time)
        fresh_window.bars.append(fresh_bar)
        manager._windows["AAPL"] = fresh_window

        # Add stale symbol
        stale_window = BarWindow(symbol="TSLA")
        stale_time = datetime.now(UTC) - timedelta(minutes=8)
        stale_bar = _create_bar_with_timestamp(create_test_bar, "TSLA", stale_time)
        stale_window.bars.append(stale_bar)
        manager._windows["TSLA"] = stale_window

        stale_symbols = manager.get_stale_symbols()

        assert "TSLA" in stale_symbols
        assert "AAPL" not in stale_symbols

    def test_get_stale_count(self, create_test_bar):
        """Verify get_stale_count returns correct count."""
        manager = BarWindowManager()

        # Add fresh symbol
        fresh_window = BarWindow(symbol="AAPL")
        fresh_time = datetime.now(UTC) - timedelta(seconds=30)
        fresh_bar = _create_bar_with_timestamp(create_test_bar, "AAPL", fresh_time)
        fresh_window.bars.append(fresh_bar)
        manager._windows["AAPL"] = fresh_window

        # Add 2 stale symbols
        for symbol in ["TSLA", "MEME"]:
            stale_window = BarWindow(symbol=symbol)
            stale_time = datetime.now(UTC) - timedelta(minutes=10)
            stale_bar = _create_bar_with_timestamp(create_test_bar, symbol, stale_time)
            stale_window.bars.append(stale_bar)
            manager._windows[symbol] = stale_window

        assert manager.get_stale_count() == 2

    @pytest.mark.asyncio
    async def test_staleness_clears_on_fresh_data(self, create_test_bar):
        """Verify staleness clears automatically when fresh data arrives (Scenario 3)."""
        manager = BarWindowManager()

        # Start with stale data
        stale_window = BarWindow(symbol="AAPL")
        stale_time = datetime.now(UTC) - timedelta(minutes=10)
        stale_bar = _create_bar_with_timestamp(create_test_bar, "AAPL", stale_time, 0)
        stale_window.bars.append(stale_bar)
        manager._windows["AAPL"] = stale_window

        # Verify initially stale
        assert manager.is_stale("AAPL") is True

        # Add fresh data
        fresh_time = datetime.now(UTC) - timedelta(seconds=10)
        fresh_bar = _create_bar_with_timestamp(create_test_bar, "AAPL", fresh_time, 1)
        await manager.add_bar("AAPL", fresh_bar)

        # Should no longer be stale
        assert manager.is_stale("AAPL") is False

    def test_get_all_staleness_info(self, create_test_bar):
        """Verify get_all_staleness_info returns info for all symbols."""
        manager = BarWindowManager()

        # Add two symbols with different staleness states
        for i, symbol in enumerate(["AAPL", "TSLA"]):
            window = BarWindow(symbol=symbol)
            # AAPL fresh, TSLA stale
            offset = timedelta(seconds=30) if i == 0 else timedelta(minutes=10)
            bar_time = datetime.now(UTC) - offset
            bar = _create_bar_with_timestamp(create_test_bar, symbol, bar_time)
            window.bars.append(bar)
            manager._windows[symbol] = window

        all_info = manager.get_all_staleness_info()

        assert "AAPL" in all_info
        assert "TSLA" in all_info
        assert all_info["AAPL"]["is_stale"] is False
        assert all_info["TSLA"]["is_stale"] is True
