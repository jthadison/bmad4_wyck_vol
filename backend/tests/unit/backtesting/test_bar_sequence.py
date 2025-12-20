"""
Unit tests for BarSequence (Story 12.1 Task 10).

Tests:
- BacktestBarSequence prevents look-ahead bias
- LiveBarSequence for real-time trading
- Look-ahead bias detection (accessing future data raises IndexError)
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from src.backtesting.bar_sequence import BacktestBarSequence, LiveBarSequence
from src.models.ohlcv import OHLCVBar


@pytest.fixture
def sample_bars():
    """Create sample OHLCV bars for testing."""
    bars = []
    for i in range(10):
        bars.append(
            OHLCVBar(
                symbol="AAPL",
                timeframe="1d",
                timestamp=datetime(2024, 1, i + 1, tzinfo=UTC),
                open=Decimal("100") + Decimal(i),
                high=Decimal("105") + Decimal(i),
                low=Decimal("95") + Decimal(i),
                close=Decimal("102") + Decimal(i),
                volume=1000000 + i * 10000,
                spread=Decimal("5"),
            )
        )
    return bars


class TestBacktestBarSequenceInitialization:
    """Test BacktestBarSequence initialization."""

    def test_initialization_valid(self, sample_bars):
        """Test initialization with valid parameters."""
        sequence = BacktestBarSequence(sample_bars, current_index=5)
        assert sequence.current_index() == 5
        assert sequence.length() == 6  # 0-5 = 6 bars

    def test_initialization_first_bar(self, sample_bars):
        """Test initialization at first bar."""
        sequence = BacktestBarSequence(sample_bars, current_index=0)
        assert sequence.current_index() == 0
        assert sequence.length() == 1

    def test_initialization_last_bar(self, sample_bars):
        """Test initialization at last bar."""
        sequence = BacktestBarSequence(sample_bars, current_index=9)
        assert sequence.current_index() == 9
        assert sequence.length() == 10

    def test_initialization_empty_bars_raises_error(self):
        """Test that empty bar list raises ValueError."""
        with pytest.raises(ValueError, match="empty bar list"):
            BacktestBarSequence([], current_index=0)

    def test_initialization_negative_index_raises_error(self, sample_bars):
        """Test that negative index raises ValueError."""
        with pytest.raises(ValueError, match="out of bounds"):
            BacktestBarSequence(sample_bars, current_index=-1)

    def test_initialization_index_too_large_raises_error(self, sample_bars):
        """Test that index >= length raises ValueError."""
        with pytest.raises(ValueError, match="out of bounds"):
            BacktestBarSequence(sample_bars, current_index=10)


class TestBacktestBarSequenceGetBar:
    """Test BacktestBarSequence.get_bar() method."""

    def test_get_current_bar(self, sample_bars):
        """Test getting current bar."""
        sequence = BacktestBarSequence(sample_bars, current_index=5)
        bar = sequence.get_bar(5)
        assert bar is not None
        assert bar.close == Decimal("107")  # 102 + 5

    def test_get_historical_bar(self, sample_bars):
        """Test getting historical bar (before current)."""
        sequence = BacktestBarSequence(sample_bars, current_index=5)
        bar = sequence.get_bar(3)
        assert bar is not None
        assert bar.close == Decimal("105")  # 102 + 3

    def test_get_first_bar(self, sample_bars):
        """Test getting first bar."""
        sequence = BacktestBarSequence(sample_bars, current_index=5)
        bar = sequence.get_bar(0)
        assert bar is not None
        assert bar.close == Decimal("102")

    def test_get_future_bar_raises_error(self, sample_bars):
        """Test that accessing future bar raises IndexError."""
        sequence = BacktestBarSequence(sample_bars, current_index=5)
        with pytest.raises(IndexError, match="future data"):
            sequence.get_bar(6)

    def test_get_far_future_bar_raises_error(self, sample_bars):
        """Test that accessing far future bar raises IndexError."""
        sequence = BacktestBarSequence(sample_bars, current_index=2)
        with pytest.raises(IndexError, match="future data"):
            sequence.get_bar(9)

    def test_get_negative_index_returns_none(self, sample_bars):
        """Test that negative index returns None."""
        sequence = BacktestBarSequence(sample_bars, current_index=5)
        bar = sequence.get_bar(-1)
        assert bar is None


class TestBacktestBarSequenceGetBars:
    """Test BacktestBarSequence.get_bars() method."""

    def test_get_all_historical_bars(self, sample_bars):
        """Test getting all bars up to current."""
        sequence = BacktestBarSequence(sample_bars, current_index=5)
        bars = sequence.get_bars(0, 5)
        assert len(bars) == 6
        assert bars[0].close == Decimal("102")
        assert bars[5].close == Decimal("107")

    def test_get_partial_historical_range(self, sample_bars):
        """Test getting partial range of historical bars."""
        sequence = BacktestBarSequence(sample_bars, current_index=8)
        bars = sequence.get_bars(2, 5)
        assert len(bars) == 4
        assert bars[0].close == Decimal("104")  # 102 + 2
        assert bars[3].close == Decimal("107")  # 102 + 5

    def test_get_single_bar_range(self, sample_bars):
        """Test getting single bar as range."""
        sequence = BacktestBarSequence(sample_bars, current_index=5)
        bars = sequence.get_bars(3, 3)
        assert len(bars) == 1
        assert bars[0].close == Decimal("105")

    def test_get_future_range_raises_error(self, sample_bars):
        """Test that range ending in future raises IndexError."""
        sequence = BacktestBarSequence(sample_bars, current_index=5)
        with pytest.raises(IndexError, match="future data"):
            sequence.get_bars(0, 6)

    def test_get_partial_future_range_raises_error(self, sample_bars):
        """Test that range partially in future raises IndexError."""
        sequence = BacktestBarSequence(sample_bars, current_index=5)
        with pytest.raises(IndexError, match="future data"):
            sequence.get_bars(3, 7)

    def test_get_inverted_range_raises_error(self, sample_bars):
        """Test that start > end raises ValueError."""
        sequence = BacktestBarSequence(sample_bars, current_index=5)
        with pytest.raises(ValueError, match="start_index"):
            sequence.get_bars(5, 3)

    def test_get_negative_start_raises_error(self, sample_bars):
        """Test that negative start index raises IndexError."""
        sequence = BacktestBarSequence(sample_bars, current_index=5)
        with pytest.raises(IndexError, match="negative"):
            sequence.get_bars(-1, 3)


class TestBacktestBarSequenceLookAheadBiasPrevention:
    """Test that BacktestBarSequence prevents look-ahead bias."""

    def test_cannot_peek_one_bar_ahead(self, sample_bars):
        """Test that peeking one bar ahead is blocked."""
        sequence = BacktestBarSequence(sample_bars, current_index=5)
        with pytest.raises(IndexError):
            sequence.get_bar(6)

    def test_cannot_get_future_range(self, sample_bars):
        """Test that future range is blocked."""
        sequence = BacktestBarSequence(sample_bars, current_index=5)
        with pytest.raises(IndexError):
            sequence.get_bars(6, 9)

    def test_length_limited_to_current_index(self, sample_bars):
        """Test that length only counts accessible bars."""
        sequence = BacktestBarSequence(sample_bars, current_index=5)
        # Total bars = 10, but only 6 accessible (0-5)
        assert sequence.length() == 6

    def test_at_first_bar_only_one_accessible(self, sample_bars):
        """Test that at first bar, only 1 bar is accessible."""
        sequence = BacktestBarSequence(sample_bars, current_index=0)
        assert sequence.length() == 1
        bars = sequence.get_bars(0, 0)
        assert len(bars) == 1

        # Cannot access second bar
        with pytest.raises(IndexError):
            sequence.get_bar(1)


class TestLiveBarSequenceInitialization:
    """Test LiveBarSequence initialization."""

    def test_initialization_with_bars(self, sample_bars):
        """Test initialization with bars."""
        sequence = LiveBarSequence(sample_bars)
        assert sequence.length() == 10
        assert sequence.current_index() == 9

    def test_initialization_with_empty_bars(self):
        """Test initialization with empty bar list."""
        sequence = LiveBarSequence([])
        assert sequence.length() == 0
        assert sequence.current_index() == -1

    def test_initialization_with_one_bar(self, sample_bars):
        """Test initialization with single bar."""
        sequence = LiveBarSequence(sample_bars[:1])
        assert sequence.length() == 1
        assert sequence.current_index() == 0


class TestLiveBarSequenceGetBar:
    """Test LiveBarSequence.get_bar() method."""

    def test_get_latest_bar(self, sample_bars):
        """Test getting latest bar."""
        sequence = LiveBarSequence(sample_bars)
        bar = sequence.get_bar(9)
        assert bar is not None
        assert bar.close == Decimal("111")  # 102 + 9

    def test_get_historical_bar(self, sample_bars):
        """Test getting historical bar."""
        sequence = LiveBarSequence(sample_bars)
        bar = sequence.get_bar(5)
        assert bar is not None
        assert bar.close == Decimal("107")

    def test_get_first_bar(self, sample_bars):
        """Test getting first bar."""
        sequence = LiveBarSequence(sample_bars)
        bar = sequence.get_bar(0)
        assert bar is not None
        assert bar.close == Decimal("102")

    def test_get_future_bar_returns_none(self, sample_bars):
        """Test that future bar returns None (not yet received)."""
        sequence = LiveBarSequence(sample_bars)
        bar = sequence.get_bar(10)
        assert bar is None

    def test_get_negative_index_returns_none(self, sample_bars):
        """Test that negative index returns None."""
        sequence = LiveBarSequence(sample_bars)
        bar = sequence.get_bar(-1)
        assert bar is None


class TestLiveBarSequenceGetBars:
    """Test LiveBarSequence.get_bars() method."""

    def test_get_all_bars(self, sample_bars):
        """Test getting all received bars."""
        sequence = LiveBarSequence(sample_bars)
        bars = sequence.get_bars(0, 9)
        assert len(bars) == 10
        assert bars[0].close == Decimal("102")
        assert bars[9].close == Decimal("111")

    def test_get_partial_range(self, sample_bars):
        """Test getting partial range."""
        sequence = LiveBarSequence(sample_bars)
        bars = sequence.get_bars(3, 6)
        assert len(bars) == 4
        assert bars[0].close == Decimal("105")
        assert bars[3].close == Decimal("108")

    def test_get_out_of_bounds_raises_error(self, sample_bars):
        """Test that out of bounds range raises IndexError."""
        sequence = LiveBarSequence(sample_bars)
        with pytest.raises(IndexError):
            sequence.get_bars(0, 10)

    def test_get_inverted_range_raises_error(self, sample_bars):
        """Test that start > end raises ValueError."""
        sequence = LiveBarSequence(sample_bars)
        with pytest.raises(ValueError):
            sequence.get_bars(5, 3)


class TestLiveVsBacktestComparison:
    """Test differences between Live and Backtest implementations."""

    def test_live_allows_all_received_bars(self, sample_bars):
        """Test that LiveBarSequence allows accessing all received bars."""
        live_sequence = LiveBarSequence(sample_bars)
        bars = live_sequence.get_bars(0, 9)
        assert len(bars) == 10

    def test_backtest_restricts_to_current_index(self, sample_bars):
        """Test that BacktestBarSequence restricts to current_index."""
        backtest_sequence = BacktestBarSequence(sample_bars, current_index=5)
        bars = backtest_sequence.get_bars(0, 5)
        assert len(bars) == 6

        # Backtest cannot access beyond current_index
        with pytest.raises(IndexError):
            backtest_sequence.get_bars(0, 9)

    def test_live_returns_none_for_future_backtest_raises(self, sample_bars):
        """Test that Live returns None, Backtest raises for future access."""
        live_sequence = LiveBarSequence(sample_bars)
        backtest_sequence = BacktestBarSequence(sample_bars, current_index=5)

        # Live: future bar returns None (not received yet)
        future_bar = live_sequence.get_bar(10)
        assert future_bar is None

        # Backtest: future bar raises IndexError (look-ahead bias)
        with pytest.raises(IndexError):
            backtest_sequence.get_bar(6)
