"""
Unit tests for BarBuffer.

Tests the circular buffer functionality for OHLCV bars.
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from src.market_data.realtime.bar_buffer import BarBuffer
from src.models.ohlcv import OHLCVBar


def create_test_bar(symbol: str = "AAPL", close: float = 150.0) -> OHLCVBar:
    """Create a test OHLCVBar."""
    return OHLCVBar(
        symbol=symbol,
        timeframe="1m",
        timestamp=datetime.now(UTC),
        open=Decimal(str(close - 1)),
        high=Decimal(str(close + 1)),
        low=Decimal(str(close - 2)),
        close=Decimal(str(close)),
        volume=100000,
        spread=Decimal("3.0"),
    )


class TestBarBuffer:
    """Tests for BarBuffer class."""

    def test_init_default(self):
        """Test default initialization."""
        buffer = BarBuffer()
        assert buffer.max_bars == 50

    def test_init_custom_size(self):
        """Test custom buffer size."""
        buffer = BarBuffer(max_bars=100)
        assert buffer.max_bars == 100

    def test_init_invalid_size(self):
        """Test invalid buffer size raises error."""
        with pytest.raises(ValueError, match="max_bars must be at least 1"):
            BarBuffer(max_bars=0)

        with pytest.raises(ValueError, match="max_bars must be at least 1"):
            BarBuffer(max_bars=-1)

    def test_add_bar(self):
        """Test adding bars to buffer."""
        buffer = BarBuffer(max_bars=10)
        bar = create_test_bar()

        buffer.add_bar(bar)

        assert buffer.get_bar_count("AAPL") == 1
        assert buffer.get_latest_bar("AAPL") == bar

    def test_add_multiple_bars(self):
        """Test adding multiple bars."""
        buffer = BarBuffer(max_bars=10)

        for i in range(5):
            bar = create_test_bar(close=150.0 + i)
            buffer.add_bar(bar)

        assert buffer.get_bar_count("AAPL") == 5
        bars = buffer.get_bars("AAPL")
        assert len(bars) == 5
        # Check ordering (oldest to newest)
        assert float(bars[0].close) == 150.0
        assert float(bars[4].close) == 154.0

    def test_buffer_overflow(self):
        """Test that old bars are discarded when buffer is full."""
        buffer = BarBuffer(max_bars=3)

        # Add 5 bars
        for i in range(5):
            bar = create_test_bar(close=150.0 + i)
            buffer.add_bar(bar)

        # Should only have last 3
        assert buffer.get_bar_count("AAPL") == 3
        bars = buffer.get_bars("AAPL")

        # First 2 should be discarded (150.0, 151.0)
        assert float(bars[0].close) == 152.0
        assert float(bars[1].close) == 153.0
        assert float(bars[2].close) == 154.0

    def test_multiple_symbols(self):
        """Test buffer handles multiple symbols independently."""
        buffer = BarBuffer(max_bars=10)

        buffer.add_bar(create_test_bar(symbol="AAPL", close=150.0))
        buffer.add_bar(create_test_bar(symbol="AAPL", close=151.0))
        buffer.add_bar(create_test_bar(symbol="TSLA", close=250.0))

        assert buffer.get_bar_count("AAPL") == 2
        assert buffer.get_bar_count("TSLA") == 1
        assert len(buffer) == 2  # 2 symbols

    def test_get_bars_empty(self):
        """Test get_bars for unknown symbol returns empty list."""
        buffer = BarBuffer()
        assert buffer.get_bars("UNKNOWN") == []

    def test_get_latest_bar_empty(self):
        """Test get_latest_bar for unknown symbol returns None."""
        buffer = BarBuffer()
        assert buffer.get_latest_bar("UNKNOWN") is None

    def test_get_bar_count_empty(self):
        """Test get_bar_count for unknown symbol returns 0."""
        buffer = BarBuffer()
        assert buffer.get_bar_count("UNKNOWN") == 0

    def test_clear_symbol(self):
        """Test clearing bars for a specific symbol."""
        buffer = BarBuffer()

        buffer.add_bar(create_test_bar(symbol="AAPL"))
        buffer.add_bar(create_test_bar(symbol="TSLA"))

        buffer.clear_symbol("AAPL")

        assert buffer.get_bar_count("AAPL") == 0
        assert buffer.get_bar_count("TSLA") == 1

    def test_clear_symbol_nonexistent(self):
        """Test clearing nonexistent symbol does not raise."""
        buffer = BarBuffer()
        buffer.clear_symbol("UNKNOWN")  # Should not raise

    def test_clear_all(self):
        """Test clearing all buffers."""
        buffer = BarBuffer()

        buffer.add_bar(create_test_bar(symbol="AAPL"))
        buffer.add_bar(create_test_bar(symbol="TSLA"))

        buffer.clear_all()

        assert len(buffer) == 0
        assert buffer.get_symbols() == []

    def test_get_symbols(self):
        """Test getting list of symbols."""
        buffer = BarBuffer()

        buffer.add_bar(create_test_bar(symbol="AAPL"))
        buffer.add_bar(create_test_bar(symbol="TSLA"))
        buffer.add_bar(create_test_bar(symbol="GOOG"))

        symbols = buffer.get_symbols()
        assert len(symbols) == 3
        assert set(symbols) == {"AAPL", "TSLA", "GOOG"}

    def test_iteration(self):
        """Test iteration over symbols."""
        buffer = BarBuffer()

        buffer.add_bar(create_test_bar(symbol="AAPL"))
        buffer.add_bar(create_test_bar(symbol="TSLA"))

        symbols = list(buffer)
        assert set(symbols) == {"AAPL", "TSLA"}

    def test_len(self):
        """Test len() returns number of symbols."""
        buffer = BarBuffer()
        assert len(buffer) == 0

        buffer.add_bar(create_test_bar(symbol="AAPL"))
        assert len(buffer) == 1

        buffer.add_bar(create_test_bar(symbol="TSLA"))
        assert len(buffer) == 2

        # Adding more bars to same symbol doesn't increase len
        buffer.add_bar(create_test_bar(symbol="AAPL"))
        assert len(buffer) == 2

    def test_thread_safety(self):
        """Test buffer is thread-safe for concurrent access."""
        import threading

        buffer = BarBuffer(max_bars=100)
        errors = []

        def add_bars(symbol: str, count: int):
            try:
                for i in range(count):
                    buffer.add_bar(create_test_bar(symbol=symbol, close=100.0 + i))
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=add_bars, args=("AAPL", 50)),
            threading.Thread(target=add_bars, args=("TSLA", 50)),
            threading.Thread(target=add_bars, args=("GOOG", 50)),
        ]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        assert len(errors) == 0
        assert buffer.get_bar_count("AAPL") == 50
        assert buffer.get_bar_count("TSLA") == 50
        assert buffer.get_bar_count("GOOG") == 50
