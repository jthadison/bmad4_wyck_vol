"""
Unit tests for Backtest Engine Core (Story 12.1 Task 5).

Tests event-driven execution, order fills, position tracking, and result generation.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

import pytest

from src.backtesting.backtest_engine import BacktestEngine
from src.models.backtest import BacktestConfig
from src.models.ohlcv import OHLCVBar


@pytest.fixture
def config():
    """Fixture for backtest configuration."""
    return BacktestConfig(
        symbol="AAPL",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 31),
        initial_capital=Decimal("100000"),
        max_position_size=Decimal("0.10"),  # 10% position size
        commission_per_share=Decimal("0.005"),
    )


@pytest.fixture
def sample_bars():
    """Fixture for sample OHLCV bars (uptrend)."""
    bars = []
    for i in range(10):
        bar = OHLCVBar(
            symbol="AAPL",
            timeframe="1d",
            open=Decimal(f"{150 + i}.00"),
            high=Decimal(f"{152 + i}.00"),
            low=Decimal(f"{149 + i}.00"),
            close=Decimal(f"{151 + i}.00"),
            volume=50000,
            spread=Decimal("3.00"),
            timestamp=datetime(2024, 1, i + 1, 9, 30),
        )
        bars.append(bar)
    return bars


class TestBacktestEngineInitialization:
    """Test BacktestEngine initialization."""

    def test_initialization_with_config(self, config):
        """Test engine initializes with configuration."""
        engine = BacktestEngine(config)

        assert engine.config == config
        assert engine.position_manager.initial_capital == Decimal("100000")
        assert engine.position_manager.cash == Decimal("100000")
        assert engine.equity_curve == []
        assert engine.bars_processed == 0

    def test_initialization_creates_components(self, config):
        """Test engine creates all necessary components."""
        engine = BacktestEngine(config)

        assert engine.slippage_calc is not None
        assert engine.commission_calc is not None
        assert engine.order_simulator is not None
        assert engine.position_manager is not None


class TestEventDrivenExecution:
    """Test event-driven bar-by-bar execution."""

    def test_run_with_no_signals(self, config, sample_bars):
        """Test running backtest with strategy that generates no signals."""

        def no_signal_strategy(bar: OHLCVBar, context: dict) -> Optional[str]:
            return None  # Never trade

        engine = BacktestEngine(config)
        result = engine.run(sample_bars, no_signal_strategy)

        # Should have equity curve but no trades
        assert len(result.equity_curve) == len(sample_bars)
        assert len(result.trades) == 0
        assert result.metrics.total_trades == 0

        # Cash should remain unchanged
        final_cash = result.equity_curve[-1].cash
        assert final_cash == Decimal("100000")

    def test_run_processes_bars_sequentially(self, config, sample_bars):
        """Test bars are processed in sequential order."""
        bars_seen = []

        def tracking_strategy(bar: OHLCVBar, context: dict) -> Optional[str]:
            bars_seen.append(bar.timestamp)
            return None

        engine = BacktestEngine(config)
        engine.run(sample_bars, tracking_strategy)

        # Verify bars processed in order
        assert len(bars_seen) == len(sample_bars)
        for i in range(len(bars_seen) - 1):
            assert bars_seen[i] < bars_seen[i + 1]

    def test_run_with_empty_bars_raises_error(self, config):
        """Test running with empty bar list raises error."""

        def dummy_strategy(bar: OHLCVBar, context: dict) -> Optional[str]:
            return None

        engine = BacktestEngine(config)

        with pytest.raises(ValueError, match="Cannot run backtest with empty bar list"):
            engine.run([], dummy_strategy)


class TestSimpleBuyAndHold:
    """Test simple buy-and-hold strategy."""

    def test_buy_and_hold_uptrend(self, config, sample_bars):
        """Test buy-and-hold in uptrend generates profit."""

        def buy_and_hold(bar: OHLCVBar, context: dict) -> Optional[str]:
            # Buy on first bar, hold until last bar
            if context.get("bar_count", 0) == 1:
                return "BUY"
            elif context.get("bar_count", 0) == len(sample_bars):
                return "SELL"
            return None

        engine = BacktestEngine(config)
        result = engine.run(sample_bars, buy_and_hold)

        # Should have 1 completed trade
        assert len(result.trades) == 1
        trade = result.trades[0]

        # Trade should be profitable (bought at ~150, sold at ~160)
        assert trade.realized_pnl > Decimal("0")
        assert trade.entry_price < trade.exit_price

        # Win rate should be 100%
        assert result.metrics.win_rate == Decimal("1.0")
        assert result.metrics.winning_trades == 1
        assert result.metrics.losing_trades == 0

    def test_buy_and_hold_equity_curve(self, config, sample_bars):
        """Test equity curve tracks portfolio value correctly."""

        def buy_and_hold(bar: OHLCVBar, context: dict) -> Optional[str]:
            if context.get("bar_count", 0) == 1:
                return "BUY"
            return None

        engine = BacktestEngine(config)
        result = engine.run(sample_bars, buy_and_hold)

        # Equity curve should have entry for each bar
        assert len(result.equity_curve) == len(sample_bars)

        # First point should be initial capital
        assert result.equity_curve[0].portfolio_value == Decimal("100000")
        assert result.equity_curve[0].cash == Decimal("100000")

        # After buy, should have less cash and some positions value
        # (Buy happens on bar 1, filled on bar 2)
        if len(result.equity_curve) > 2:
            assert result.equity_curve[2].cash < Decimal("100000")
            assert result.equity_curve[2].positions_value > Decimal("0")


class TestPositionSizing:
    """Test position sizing logic."""

    def test_position_size_respects_max_position_size(self, config, sample_bars):
        """Test position sizing doesn't exceed max_position_size."""

        def buy_first_bar(bar: OHLCVBar, context: dict) -> Optional[str]:
            if context.get("bar_count", 0) == 1:
                return "BUY"
            return None

        engine = BacktestEngine(config)
        result = engine.run(sample_bars, buy_first_bar)

        # Check order was created
        # Position value should be ~10% of $100k = ~$10k
        # At price ~$151, that's ~66 shares
        # Check via equity curve after fill
        if len(result.equity_curve) > 2:
            positions_value = result.equity_curve[2].positions_value
            portfolio_value = result.equity_curve[2].portfolio_value

            # Position should be roughly 10% of portfolio
            position_pct = positions_value / portfolio_value
            assert position_pct <= Decimal("0.11")  # Allow for slippage

    def test_position_size_limited_by_cash(self, config):
        """Test position sizing limited by available cash."""
        # Create config with very large position size
        large_config = BacktestConfig(
            symbol="AAPL",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            initial_capital=Decimal("1000"),  # Small capital
            max_position_size=Decimal("0.50"),  # 50% position size
        )

        bars = [
            OHLCVBar(
                symbol="AAPL",
                timeframe="1d",
                open=Decimal("150.00"),
                high=Decimal("152.00"),
                low=Decimal("149.00"),
                close=Decimal("151.00"),
                volume=50000,
                spread=Decimal("3.00"),
                timestamp=datetime(2024, 1, 1, 9, 30),
            ),
            OHLCVBar(
                symbol="AAPL",
                timeframe="1d",
                open=Decimal("151.00"),
                high=Decimal("153.00"),
                low=Decimal("150.00"),
                close=Decimal("152.00"),
                volume=50000,
                spread=Decimal("3.00"),
                timestamp=datetime(2024, 1, 2, 9, 30),
            ),
        ]

        def buy_strategy(bar: OHLCVBar, context: dict) -> Optional[str]:
            if context.get("bar_count", 0) == 1:
                return "BUY"
            return None

        engine = BacktestEngine(large_config)
        result = engine.run(bars, buy_strategy)

        # Should buy what we can afford (max ~6 shares at $151)
        final_cash = result.equity_curve[-1].cash
        assert final_cash >= Decimal("0")  # Shouldn't go negative


class TestStrategyContext:
    """Test strategy context tracking."""

    def test_strategy_context_tracks_bar_count(self, config, sample_bars):
        """Test strategy context tracks bar count."""
        bar_counts = []

        def tracking_strategy(bar: OHLCVBar, context: dict) -> Optional[str]:
            bar_counts.append(context.get("bar_count", 0))
            return None

        engine = BacktestEngine(config)
        engine.run(sample_bars, tracking_strategy)

        assert bar_counts == list(range(1, len(sample_bars) + 1))

    def test_strategy_context_tracks_prices(self, config, sample_bars):
        """Test strategy context tracks price history."""
        price_history_lengths = []

        def tracking_strategy(bar: OHLCVBar, context: dict) -> Optional[str]:
            prices = context.get("prices", [])
            price_history_lengths.append(len(prices))
            return None

        engine = BacktestEngine(config)
        engine.run(sample_bars, tracking_strategy)

        # Price history should grow with each bar
        assert price_history_lengths == list(range(len(sample_bars)))

    def test_strategy_can_use_context_for_indicators(self, config, sample_bars):
        """Test strategy can use context for indicator calculations."""
        signals_generated = []

        def sma_strategy(bar: OHLCVBar, context: dict) -> Optional[str]:
            # Simple moving average crossover
            prices = context.get("prices", [])

            if len(prices) >= 5:
                sma_5 = sum(prices[-5:]) / 5
                if bar.close > sma_5 * Decimal("1.01"):
                    signals_generated.append("BUY")
                    return "BUY"

            return None

        engine = BacktestEngine(config)
        result = engine.run(sample_bars, sma_strategy)

        # Should have generated some signals
        assert len(signals_generated) > 0


class TestMultipleTrades:
    """Test strategies with multiple round-trip trades."""

    def test_multiple_round_trips(self, config):
        """Test multiple buy/sell cycles."""
        bars = []
        # Create oscillating price bars
        for i in range(20):
            price = Decimal("150") if i % 4 < 2 else Decimal("155")
            bar = OHLCVBar(
                symbol="AAPL",
                timeframe="1d",
                open=price,
                high=price + Decimal("2"),
                low=price - Decimal("1"),
                close=price,
                volume=50000,
                spread=Decimal("3.00"),
                timestamp=datetime(2024, 1, i + 1, 9, 30),
            )
            bars.append(bar)

        def swing_strategy(bar: OHLCVBar, context: dict) -> Optional[str]:
            # Buy when price drops, sell when price rises
            prev_close = context.get("prev_close", bar.close)

            if bar.close < prev_close and not context.get("has_position", False):
                context["has_position"] = True
                return "BUY"
            elif bar.close > prev_close and context.get("has_position", False):
                context["has_position"] = False
                return "SELL"

            return None

        engine = BacktestEngine(config)
        result = engine.run(bars, swing_strategy)

        # Should have multiple trades
        assert len(result.trades) >= 2
        assert result.metrics.total_trades >= 2


class TestOrderFillTiming:
    """Test orders are filled at correct time (next bar)."""

    def test_market_order_fills_next_bar(self, config):
        """Test market orders fill at next bar open."""
        bars = [
            OHLCVBar(
                symbol="AAPL",
                timeframe="1d",
                open=Decimal("150.00"),
                high=Decimal("152.00"),
                low=Decimal("149.00"),
                close=Decimal("151.00"),
                volume=50000,
                spread=Decimal("3.00"),
                timestamp=datetime(2024, 1, 1, 9, 30),
            ),
            OHLCVBar(
                symbol="AAPL",
                timeframe="1d",
                open=Decimal("152.00"),  # Fill should happen at this price + slippage
                high=Decimal("154.00"),
                low=Decimal("151.00"),
                close=Decimal("153.00"),
                volume=50000,
                spread=Decimal("3.00"),
                timestamp=datetime(2024, 1, 2, 9, 30),
            ),
            OHLCVBar(
                symbol="AAPL",
                timeframe="1d",
                open=Decimal("153.00"),
                high=Decimal("155.00"),
                low=Decimal("152.00"),
                close=Decimal("154.00"),
                volume=50000,
                spread=Decimal("3.00"),
                timestamp=datetime(2024, 1, 3, 9, 30),
            ),
        ]

        def buy_first_bar(bar: OHLCVBar, context: dict) -> Optional[str]:
            if context.get("bar_count", 0) == 1:
                return "BUY"
            elif context.get("bar_count", 0) == 3:
                return "SELL"
            return None

        engine = BacktestEngine(config)
        result = engine.run(bars, buy_first_bar)

        assert len(result.trades) == 1
        trade = result.trades[0]

        # Entry should be around bar 2's open ($152 + slippage)
        assert trade.entry_price >= Decimal("152.00")
        assert trade.entry_price <= Decimal("152.10")  # With slippage

        # Exit should be around bar 3's open ($153 - slippage for sell)
        assert trade.exit_price >= Decimal("152.90")
        assert trade.exit_price <= Decimal("153.00")


class TestMetricsCalculation:
    """Test performance metrics calculation."""

    def test_metrics_with_no_trades(self, config, sample_bars):
        """Test metrics calculation with no trades."""

        def no_trade_strategy(bar: OHLCVBar, context: dict) -> Optional[str]:
            return None

        engine = BacktestEngine(config)
        result = engine.run(sample_bars, no_trade_strategy)

        assert result.metrics.total_trades == 0
        assert result.metrics.win_rate == Decimal("0")
        assert result.metrics.winning_trades == 0
        assert result.metrics.losing_trades == 0

    def test_metrics_with_winning_trade(self, config, sample_bars):
        """Test metrics with profitable trade."""

        def buy_and_hold(bar: OHLCVBar, context: dict) -> Optional[str]:
            if context.get("bar_count", 0) == 1:
                return "BUY"
            elif context.get("bar_count", 0) == len(sample_bars):
                return "SELL"
            return None

        engine = BacktestEngine(config)
        result = engine.run(sample_bars, buy_and_hold)

        assert result.metrics.total_trades == 1
        assert result.metrics.winning_trades == 1
        assert result.metrics.losing_trades == 0
        assert result.metrics.win_rate == Decimal("1.0")
        assert result.metrics.profit_factor == Decimal("0")  # No losses
        assert result.metrics.total_return_pct > Decimal("0")


class TestResultGeneration:
    """Test backtest result generation."""

    def test_result_contains_all_fields(self, config, sample_bars):
        """Test result contains all required fields."""

        def simple_strategy(bar: OHLCVBar, context: dict) -> Optional[str]:
            return None

        engine = BacktestEngine(config)
        result = engine.run(sample_bars, simple_strategy)

        assert result.backtest_run_id is not None
        assert result.symbol == "AAPL"
        assert result.start_date == date(2024, 1, 1)
        assert result.end_date == date(2024, 1, 31)
        assert result.config == config
        assert isinstance(result.equity_curve, list)
        assert isinstance(result.trades, list)
        assert result.metrics is not None
        assert result.look_ahead_bias_check is True
        assert result.execution_time_seconds >= 0

    def test_result_tracks_execution_time(self, config, sample_bars):
        """Test result includes execution time."""

        def simple_strategy(bar: OHLCVBar, context: dict) -> Optional[str]:
            return None

        engine = BacktestEngine(config)
        result = engine.run(sample_bars, simple_strategy)

        # Should have non-zero execution time
        assert result.execution_time_seconds > 0
        assert result.execution_time_seconds < 10  # Should be fast for 10 bars


class TestDrawdownCalculation:
    """Test drawdown calculation."""

    def test_drawdown_with_no_trades(self, config, sample_bars):
        """Test drawdown with no position changes."""

        def no_trade_strategy(bar: OHLCVBar, context: dict) -> Optional[str]:
            return None

        engine = BacktestEngine(config)
        result = engine.run(sample_bars, no_trade_strategy)

        # No trading = no drawdown
        assert result.metrics.max_drawdown == Decimal("0")
        assert result.metrics.max_drawdown_duration_days == 0

    def test_drawdown_tracks_peak_decline(self, config):
        """Test drawdown calculation tracks peak-to-trough decline."""
        # Create declining price bars
        bars = []
        for i in range(10):
            price = Decimal(f"{160 - i * 2}")  # Declining from 160 to 142
            bar = OHLCVBar(
                symbol="AAPL",
                timeframe="1d",
                open=price,
                high=price + Decimal("1"),
                low=price - Decimal("1"),
                close=price,
                volume=50000,
                spread=Decimal("2.00"),
                timestamp=datetime(2024, 1, i + 1, 9, 30),
            )
            bars.append(bar)

        def buy_and_hold(bar: OHLCVBar, context: dict) -> Optional[str]:
            if context.get("bar_count", 0) == 1:
                return "BUY"
            return None

        engine = BacktestEngine(config)
        result = engine.run(bars, buy_and_hold)

        # Should have significant drawdown
        assert result.metrics.max_drawdown > Decimal("0")
        assert result.metrics.max_drawdown_duration_days > 0
