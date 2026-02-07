"""
Unit Tests for BarProcessor (Story 18.9.3)

Tests for bar-by-bar processing logic including exit condition checking,
position updates, and equity curve generation.

Author: Story 18.9.3
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from src.backtesting.engine.bar_processor import (
    BarProcessingResult,
    BarProcessor,
    ExitSignal,
)
from src.models.backtest import BacktestPosition
from src.models.ohlcv import OHLCVBar


class TestBarProcessorInit:
    """Tests for BarProcessor initialization."""

    def test_default_values(self):
        """AC1: BarProcessor initializes with sensible defaults."""
        processor = BarProcessor()

        assert processor.stop_loss_pct == Decimal("0.02")
        assert processor.take_profit_pct == Decimal("0.06")

    def test_custom_values(self):
        """AC1: BarProcessor accepts custom threshold values."""
        processor = BarProcessor(
            stop_loss_pct=Decimal("0.03"),
            take_profit_pct=Decimal("0.10"),
        )

        assert processor.stop_loss_pct == Decimal("0.03")
        assert processor.take_profit_pct == Decimal("0.10")

    def test_stop_loss_pct_validation(self):
        """AC1: BarProcessor validates stop_loss_pct range."""
        with pytest.raises(ValueError, match="stop_loss_pct must be in"):
            BarProcessor(stop_loss_pct=Decimal("0"))

        with pytest.raises(ValueError, match="stop_loss_pct must be in"):
            BarProcessor(stop_loss_pct=Decimal("-0.01"))

        with pytest.raises(ValueError, match="stop_loss_pct must be in"):
            BarProcessor(stop_loss_pct=Decimal("1.5"))

        # Edge case: exactly 1.0 should be valid
        processor = BarProcessor(stop_loss_pct=Decimal("1.0"))
        assert processor.stop_loss_pct == Decimal("1.0")

    def test_take_profit_pct_validation(self):
        """AC1: BarProcessor validates take_profit_pct range."""
        with pytest.raises(ValueError, match="take_profit_pct must be in"):
            BarProcessor(take_profit_pct=Decimal("0"))

        with pytest.raises(ValueError, match="take_profit_pct must be in"):
            BarProcessor(take_profit_pct=Decimal("1.5"))


class TestBarProcessorProcess:
    """Tests for BarProcessor.process method."""

    @pytest.fixture
    def processor(self):
        """Create a BarProcessor with default settings."""
        return BarProcessor(
            stop_loss_pct=Decimal("0.02"),
            take_profit_pct=Decimal("0.06"),
        )

    @pytest.fixture
    def sample_bar(self):
        """Create a sample OHLCV bar."""
        return OHLCVBar(
            symbol="AAPL",
            timeframe="1d",
            timestamp=datetime(2024, 1, 15, 9, 30, tzinfo=UTC),
            open=Decimal("150.00"),
            high=Decimal("152.00"),
            low=Decimal("149.00"),
            close=Decimal("151.00"),
            volume=1000000,
            spread=Decimal("3.00"),  # high - low
        )

    @pytest.fixture
    def sample_position(self):
        """Create a sample open position."""
        return BacktestPosition(
            position_id=uuid4(),
            symbol="AAPL",
            side="LONG",
            quantity=100,
            average_entry_price=Decimal("150.00"),
            current_price=Decimal("150.00"),
            entry_timestamp=datetime(2024, 1, 10, 9, 30, tzinfo=UTC),
            last_updated=datetime(2024, 1, 10, 9, 30, tzinfo=UTC),
            unrealized_pnl=Decimal("0"),
            total_commission=Decimal("1.00"),
        )

    def test_process_no_positions(self, processor, sample_bar):
        """AC4: Process bar with no open positions."""
        result = processor.process(
            bar=sample_bar,
            index=0,
            positions={},
            cash=Decimal("100000"),
        )

        assert isinstance(result, BarProcessingResult)
        assert result.bar_index == 0
        assert result.timestamp == sample_bar.timestamp
        assert result.portfolio_value == Decimal("100000")
        assert result.cash == Decimal("100000")
        assert result.positions_value == Decimal("0")
        assert result.exit_signals == []
        assert result.equity_point is not None

    def test_process_with_position_updates_value(self, processor, sample_bar, sample_position):
        """AC4: Process bar updates position value correctly."""
        positions = {"AAPL": sample_position}
        cash = Decimal("85000")

        result = processor.process(
            bar=sample_bar,
            index=5,
            positions=positions,
            cash=cash,
        )

        # Position value: 100 shares * $151 = $15,100
        expected_position_value = Decimal("15100")
        expected_portfolio = cash + expected_position_value

        assert result.positions_value == expected_position_value
        assert result.portfolio_value == expected_portfolio
        assert result.cash == cash

    def test_process_updates_position_price(self, processor, sample_bar, sample_position):
        """AC4: Process bar updates position current_price."""
        positions = {"AAPL": sample_position}

        processor.process(
            bar=sample_bar,
            index=0,
            positions=positions,
            cash=Decimal("85000"),
        )

        # Position's current price should be updated to bar close
        assert positions["AAPL"].current_price == sample_bar.close
        assert positions["AAPL"].last_updated == sample_bar.timestamp

    def test_process_creates_equity_point(self, processor, sample_bar):
        """AC4: Process bar creates equity curve point."""
        result = processor.process(
            bar=sample_bar,
            index=10,
            positions={},
            cash=Decimal("100000"),
        )

        point = result.equity_point
        assert point is not None
        assert point.timestamp == sample_bar.timestamp
        assert point.portfolio_value == Decimal("100000")
        assert point.cash == Decimal("100000")
        assert point.positions_value == Decimal("0")


class TestBarProcessorExitConditions:
    """Tests for BarProcessor exit condition checking."""

    @pytest.fixture
    def processor(self):
        """Create a BarProcessor with specific thresholds."""
        return BarProcessor(
            stop_loss_pct=Decimal("0.02"),  # 2%
            take_profit_pct=Decimal("0.06"),  # 6%
        )

    @pytest.fixture
    def long_position(self):
        """Create a LONG position for testing."""
        return BacktestPosition(
            position_id=uuid4(),
            symbol="AAPL",
            side="LONG",
            quantity=100,
            average_entry_price=Decimal("100.00"),
            current_price=Decimal("100.00"),
            entry_timestamp=datetime(2024, 1, 10, 9, 30, tzinfo=UTC),
            last_updated=datetime(2024, 1, 10, 9, 30, tzinfo=UTC),
        )

    @pytest.fixture
    def short_position(self):
        """Create a SHORT position for testing."""
        return BacktestPosition(
            position_id=uuid4(),
            symbol="AAPL",
            side="SHORT",
            quantity=100,
            average_entry_price=Decimal("100.00"),
            current_price=Decimal("100.00"),
            entry_timestamp=datetime(2024, 1, 10, 9, 30, tzinfo=UTC),
            last_updated=datetime(2024, 1, 10, 9, 30, tzinfo=UTC),
        )

    def test_long_stop_loss_triggered(self, processor, long_position):
        """AC4: Long position triggers stop-loss when bar.low breaches stop level.

        Entry at $100, stop at $98 (2%). Bar low of $97 breaches the stop.
        Exit price should be the stop price ($98), not bar.close.
        """
        bar = OHLCVBar(
            symbol="AAPL",
            timeframe="1d",
            timestamp=datetime(2024, 1, 15, 9, 30, tzinfo=UTC),
            open=Decimal("99.00"),
            high=Decimal("99.50"),
            low=Decimal("97.00"),
            close=Decimal("97.50"),
            volume=1000000,
            spread=Decimal("2.50"),
        )

        result = processor.process(
            bar=bar,
            index=0,
            positions={"AAPL": long_position},
            cash=Decimal("90000"),
        )

        assert len(result.exit_signals) == 1
        exit_signal = result.exit_signals[0]
        assert exit_signal.symbol == "AAPL"
        assert exit_signal.reason == "stop_loss"
        # Stop price = 100 * (1 - 0.02) = 98.00
        assert exit_signal.exit_price == Decimal("98.00")

    def test_long_stop_loss_not_triggered_when_low_above_stop(self, processor, long_position):
        """AC4: Long stop-loss NOT triggered when bar.low stays above stop level.

        Entry at $100, stop at $98 (2%). Bar low of $98.50 does not breach.
        Even if close is below stop, stop should not trigger.
        """
        bar = OHLCVBar(
            symbol="AAPL",
            timeframe="1d",
            timestamp=datetime(2024, 1, 15, 9, 30, tzinfo=UTC),
            open=Decimal("99.00"),
            high=Decimal("99.50"),
            low=Decimal("98.50"),
            close=Decimal("98.50"),
            volume=1000000,
            spread=Decimal("1.00"),
        )

        result = processor.process(
            bar=bar,
            index=0,
            positions={"AAPL": long_position},
            cash=Decimal("90000"),
        )

        assert len(result.exit_signals) == 0

    def test_long_take_profit_triggered(self, processor, long_position):
        """AC4: Long position triggers take-profit when bar.high reaches target.

        Entry at $100, target at $106 (6%). Bar high of $108 reaches target.
        Exit price should be the target price ($106), not bar.close.
        """
        bar = OHLCVBar(
            symbol="AAPL",
            timeframe="1d",
            timestamp=datetime(2024, 1, 15, 9, 30, tzinfo=UTC),
            open=Decimal("105.00"),
            high=Decimal("108.00"),
            low=Decimal("105.00"),
            close=Decimal("107.00"),
            volume=1000000,
            spread=Decimal("3.00"),
        )

        result = processor.process(
            bar=bar,
            index=0,
            positions={"AAPL": long_position},
            cash=Decimal("90000"),
        )

        assert len(result.exit_signals) == 1
        exit_signal = result.exit_signals[0]
        assert exit_signal.symbol == "AAPL"
        assert exit_signal.reason == "take_profit"
        # Target price = 100 * (1 + 0.06) = 106.00
        assert exit_signal.exit_price == Decimal("106.00")

    def test_long_no_exit_within_range(self, processor, long_position):
        """AC4: Long position has no exit when bar range within thresholds.

        Entry at $100, stop at $98, target at $106.
        Bar low=$99 (above stop), bar high=$102 (below target).
        """
        bar = OHLCVBar(
            symbol="AAPL",
            timeframe="1d",
            timestamp=datetime(2024, 1, 15, 9, 30, tzinfo=UTC),
            open=Decimal("100.00"),
            high=Decimal("102.00"),
            low=Decimal("99.00"),
            close=Decimal("101.00"),
            volume=1000000,
            spread=Decimal("3.00"),
        )

        result = processor.process(
            bar=bar,
            index=0,
            positions={"AAPL": long_position},
            cash=Decimal("90000"),
        )

        assert len(result.exit_signals) == 0

    def test_long_both_hit_same_bar_stop_wins(self, processor, long_position):
        """AC4: If both stop and target hit in same bar, stop wins (conservative).

        Entry at $100, stop at $98, target at $106. Wide bar spans both.
        """
        bar = OHLCVBar(
            symbol="AAPL",
            timeframe="1d",
            timestamp=datetime(2024, 1, 15, 9, 30, tzinfo=UTC),
            open=Decimal("100.00"),
            high=Decimal("110.00"),
            low=Decimal("95.00"),
            close=Decimal("105.00"),
            volume=2000000,
            spread=Decimal("15.00"),
        )

        result = processor.process(
            bar=bar,
            index=0,
            positions={"AAPL": long_position},
            cash=Decimal("90000"),
        )

        assert len(result.exit_signals) == 1
        exit_signal = result.exit_signals[0]
        assert exit_signal.reason == "stop_loss"
        assert exit_signal.exit_price == Decimal("98.00")

    def test_short_stop_loss_triggered(self, processor, short_position):
        """AC4: Short position triggers stop-loss when bar.high breaches stop level.

        Entry at $100, stop at $102 (2%). Bar high of $104 breaches the stop.
        Exit price should be the stop price ($102), not bar.close.
        """
        bar = OHLCVBar(
            symbol="AAPL",
            timeframe="1d",
            timestamp=datetime(2024, 1, 15, 9, 30, tzinfo=UTC),
            open=Decimal("101.00"),
            high=Decimal("104.00"),
            low=Decimal("101.00"),
            close=Decimal("103.00"),
            volume=1000000,
            spread=Decimal("3.00"),
        )

        result = processor.process(
            bar=bar,
            index=0,
            positions={"AAPL": short_position},
            cash=Decimal("90000"),
        )

        assert len(result.exit_signals) == 1
        exit_signal = result.exit_signals[0]
        assert exit_signal.symbol == "AAPL"
        assert exit_signal.reason == "stop_loss"
        # Stop price = 100 * (1 + 0.02) = 102.00
        assert exit_signal.exit_price == Decimal("102.00")

    def test_short_take_profit_triggered(self, processor, short_position):
        """AC4: Short position triggers take-profit when bar.low reaches target.

        Entry at $100, target at $94 (6%). Bar low of $92 reaches target.
        Exit price should be the target price ($94), not bar.close.
        """
        bar = OHLCVBar(
            symbol="AAPL",
            timeframe="1d",
            timestamp=datetime(2024, 1, 15, 9, 30, tzinfo=UTC),
            open=Decimal("95.00"),
            high=Decimal("95.00"),
            low=Decimal("92.00"),
            close=Decimal("93.00"),
            volume=1000000,
            spread=Decimal("3.00"),
        )

        result = processor.process(
            bar=bar,
            index=0,
            positions={"AAPL": short_position},
            cash=Decimal("90000"),
        )

        assert len(result.exit_signals) == 1
        exit_signal = result.exit_signals[0]
        assert exit_signal.symbol == "AAPL"
        assert exit_signal.reason == "take_profit"
        # Target price = 100 * (1 - 0.06) = 94.00
        assert exit_signal.exit_price == Decimal("94.00")

    def test_short_both_hit_same_bar_stop_wins(self, processor, short_position):
        """AC4: If both stop and target hit in same bar for SHORT, stop wins.

        Entry at $100, stop at $102, target at $94. Wide bar spans both.
        """
        bar = OHLCVBar(
            symbol="AAPL",
            timeframe="1d",
            timestamp=datetime(2024, 1, 15, 9, 30, tzinfo=UTC),
            open=Decimal("100.00"),
            high=Decimal("105.00"),
            low=Decimal("90.00"),
            close=Decimal("97.00"),
            volume=2000000,
            spread=Decimal("15.00"),
        )

        result = processor.process(
            bar=bar,
            index=0,
            positions={"AAPL": short_position},
            cash=Decimal("90000"),
        )

        assert len(result.exit_signals) == 1
        exit_signal = result.exit_signals[0]
        assert exit_signal.reason == "stop_loss"
        assert exit_signal.exit_price == Decimal("102.00")

    def test_different_symbol_position_no_update(self, processor, long_position):
        """AC4: Position for different symbol not updated or checked."""
        # Bar for different symbol
        bar = OHLCVBar(
            symbol="MSFT",
            timeframe="1d",
            timestamp=datetime(2024, 1, 15, 9, 30, tzinfo=UTC),
            open=Decimal("400.00"),
            high=Decimal("405.00"),
            low=Decimal("395.00"),
            close=Decimal("402.00"),
            volume=500000,
            spread=Decimal("10.00"),
        )

        original_price = long_position.current_price

        result = processor.process(
            bar=bar,
            index=0,
            positions={"AAPL": long_position},
            cash=Decimal("90000"),
        )

        # AAPL position price should not change
        assert long_position.current_price == original_price
        assert len(result.exit_signals) == 0


class TestExitSignalDataclass:
    """Tests for ExitSignal dataclass."""

    def test_exit_signal_creation(self):
        """AC4: ExitSignal can be created with all fields."""
        signal = ExitSignal(
            symbol="AAPL",
            reason="stop_loss",
            exit_price=Decimal("98.50"),
        )

        assert signal.symbol == "AAPL"
        assert signal.reason == "stop_loss"
        assert signal.exit_price == Decimal("98.50")


class TestBarProcessingResultDataclass:
    """Tests for BarProcessingResult dataclass."""

    def test_result_creation_minimal(self):
        """AC4: BarProcessingResult can be created with required fields."""
        result = BarProcessingResult(
            bar_index=5,
            timestamp=datetime(2024, 1, 15, 9, 30, tzinfo=UTC),
            portfolio_value=Decimal("100000"),
            cash=Decimal("85000"),
            positions_value=Decimal("15000"),
        )

        assert result.bar_index == 5
        assert result.portfolio_value == Decimal("100000")
        assert result.exit_signals == []
        assert result.equity_point is None

    def test_result_creation_with_exit_signals(self):
        """AC4: BarProcessingResult can include exit signals."""
        exit_signals = [
            ExitSignal(symbol="AAPL", reason="stop_loss", exit_price=Decimal("98")),
            ExitSignal(symbol="MSFT", reason="take_profit", exit_price=Decimal("420")),
        ]

        result = BarProcessingResult(
            bar_index=10,
            timestamp=datetime(2024, 1, 15, 9, 30, tzinfo=UTC),
            portfolio_value=Decimal("105000"),
            cash=Decimal("50000"),
            positions_value=Decimal("55000"),
            exit_signals=exit_signals,
        )

        assert len(result.exit_signals) == 2
        assert result.exit_signals[0].symbol == "AAPL"
        assert result.exit_signals[1].symbol == "MSFT"
