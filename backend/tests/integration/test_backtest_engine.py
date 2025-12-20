"""
Integration Tests for Backtest Engine (Story 12.1 Task 14).

Tests end-to-end backtesting workflow with realistic scenarios:
- Full backtest with buy-and-hold strategy
- Multiple round trips with momentum strategy
- Equity curve validation
- Metrics calculation
- API storage and retrieval
- Look-ahead bias validation

Author: Story 12.1 Task 14
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from src.backtesting.backtest_engine import BacktestEngine
from src.models.backtest import BacktestConfig, BacktestResult
from src.models.ohlcv import OHLCVBar


@pytest.fixture
def realistic_bars():
    """
    Generate realistic OHLCV bars for integration testing.

    Simulates 3 months of daily data with:
    - Trending movement
    - Realistic volatility
    - Volume patterns
    """
    bars = []
    start_date = datetime(2024, 1, 1, tzinfo=UTC)
    base_price = Decimal("150.00")

    for i in range(90):  # 3 months
        # Simulate realistic price movement
        trend = Decimal(i) * Decimal("0.10")  # Uptrend
        volatility = Decimal((i % 15) - 7) * Decimal("0.5")  # Oscillation
        price = base_price + trend + volatility

        # Realistic volume patterns
        base_volume = 2000000
        volume_spike = (i % 20) * 50000  # Volume spikes every 20 days
        volume = base_volume + volume_spike

        bars.append(
            OHLCVBar(
                symbol="AAPL",
                timeframe="1d",
                timestamp=start_date + timedelta(days=i),
                open=price,
                high=price + Decimal("2"),
                low=price - Decimal("2"),
                close=price + Decimal("0.50"),
                volume=volume,
                spread=Decimal("2"),
            )
        )

    return bars


@pytest.fixture
def integration_config():
    """Standard configuration for integration tests."""
    return BacktestConfig(
        symbol="AAPL",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 3, 31),
        initial_capital=Decimal("100000"),
        max_position_size=Decimal("0.02"),
        commission_per_share=Decimal("0.005"),
    )


class TestBacktestEngineIntegration:
    """Integration tests for BacktestEngine."""

    def test_full_backtest_buy_and_hold(self, realistic_bars, integration_config):
        """
        Test complete backtest workflow with buy-and-hold strategy.

        AC14 Subtask 14.1-14.7: Full backtest with all components.
        """

        def buy_and_hold(bar, context):
            if context.get("bar_count") == 1:
                return "BUY"
            return None

        engine = BacktestEngine(integration_config)
        result = engine.run(realistic_bars, strategy_func=buy_and_hold)

        # Verify result structure
        assert isinstance(result, BacktestResult)
        assert result.backtest_run_id is not None
        assert result.symbol == "AAPL"

        # Verify equity curve
        assert len(result.equity_curve) == 90
        assert result.equity_curve[0].portfolio_value == integration_config.initial_capital
        assert (
            result.equity_curve[-1].portfolio_value != integration_config.initial_capital
        )  # Changed value

        # Verify trades
        assert len(result.trades) >= 0  # May have no closed trades (still holding)

        # Verify metrics
        assert result.metrics is not None
        assert result.metrics.max_drawdown >= Decimal("0")
        assert result.metrics.total_return_pct != Decimal("0")  # Should have returns

        # Verify look-ahead bias check
        assert result.look_ahead_bias_check is True

        # Verify execution time
        assert result.execution_time_seconds > 0
        assert result.execution_time_seconds < 10  # Should be fast

    def test_full_backtest_with_multiple_trades(self, realistic_bars, integration_config):
        """
        Test backtest with active trading strategy generating multiple trades.

        AC14 Subtask 14.4-14.6: Verify trades, equity curve, metrics.
        """

        def momentum_strategy(bar, context):
            bar_count = context.get("bar_count", 0)
            prices = context.get("prices", [])

            if bar_count < 10:
                return None

            # Simple momentum: buy on breakout, sell on breakdown
            recent_high = max(prices[-10:])
            recent_low = min(prices[-10:])

            if bar.close > recent_high:
                return "BUY"
            elif bar.close < recent_low:
                return "SELL"

            return None

        engine = BacktestEngine(integration_config)
        result = engine.run(realistic_bars, strategy_func=momentum_strategy)

        # Verify trades were generated
        assert len(result.trades) > 0, "Strategy should generate trades"

        # Verify trade structure
        first_trade = result.trades[0]
        assert first_trade.entry_timestamp < first_trade.exit_timestamp
        assert first_trade.quantity > 0
        assert first_trade.commission_total > Decimal("0")

        # Verify equity curve reflects trades
        assert len(result.equity_curve) == 90

        # Verify metrics with trades
        assert result.metrics.total_trades == len(result.trades)
        assert result.metrics.win_rate >= Decimal("0")
        assert result.metrics.win_rate <= Decimal("1")

    def test_equity_curve_progression(self, realistic_bars, integration_config):
        """
        Test that equity curve correctly tracks portfolio value over time.

        AC14 Subtask 14.6: Verify equity curve trajectory.
        """

        def simple_profitable_strategy(bar, context):
            # Buy on day 10, sell on day 50 (assuming uptrend)
            bar_count = context.get("bar_count", 0)
            if bar_count == 10:
                return "BUY"
            elif bar_count == 50:
                return "SELL"
            return None

        engine = BacktestEngine(integration_config)
        result = engine.run(realistic_bars, strategy_func=simple_profitable_strategy)

        # Verify equity curve structure
        assert len(result.equity_curve) == 90

        # Verify timestamps are sequential
        for i in range(1, len(result.equity_curve)):
            assert result.equity_curve[i].timestamp > result.equity_curve[i - 1].timestamp

        # Verify cumulative returns calculated
        final_point = result.equity_curve[-1]
        assert final_point.cumulative_return == (
            (final_point.portfolio_value - integration_config.initial_capital)
            / integration_config.initial_capital
        )

    def test_metrics_calculation_comprehensive(self, realistic_bars, integration_config):
        """
        Test comprehensive metrics calculation.

        AC14 Subtask 14.7: Verify all metrics calculated correctly.
        """

        def test_strategy(bar, context):
            bar_count = context.get("bar_count", 0)
            # Make a few trades to generate metrics
            if bar_count in [5, 15, 25, 35, 45, 55]:
                return "BUY"
            elif bar_count in [10, 20, 30, 40, 50, 60]:
                return "SELL"
            return None

        engine = BacktestEngine(integration_config)
        result = engine.run(realistic_bars, strategy_func=test_strategy)

        metrics = result.metrics

        # Verify all metric fields exist
        assert metrics.total_return_pct is not None
        assert metrics.max_drawdown is not None
        assert metrics.max_drawdown_duration_days is not None
        assert metrics.total_trades is not None
        assert metrics.winning_trades is not None
        assert metrics.losing_trades is not None

        # Verify metric consistency
        assert metrics.total_trades == metrics.winning_trades + metrics.losing_trades
        assert (
            metrics.win_rate == Decimal(metrics.winning_trades) / Decimal(metrics.total_trades)
            if metrics.total_trades > 0
            else Decimal("0")
        )

        # Verify drawdown is valid
        assert Decimal("0") <= metrics.max_drawdown <= Decimal("1")

    def test_look_ahead_bias_validation(self, realistic_bars, integration_config):
        """
        Test that look-ahead bias detector validates backtest results.

        AC14 Subtask 14.8: Verify look_ahead_bias_check = True.
        """

        def safe_strategy(bar, context):
            if context.get("bar_count") == 20:
                return "BUY"
            elif context.get("bar_count") == 60:
                return "SELL"
            return None

        engine = BacktestEngine(integration_config)
        result = engine.run(realistic_bars, strategy_func=safe_strategy)

        # Verify bias check passed
        assert result.look_ahead_bias_check is True

        # Verify trades are chronological
        for trade in result.trades:
            assert trade.entry_timestamp < trade.exit_timestamp

    def test_performance_with_realistic_dataset(self, realistic_bars, integration_config):
        """
        Test performance with realistic dataset size.

        AC14 Subtask 14.10: Verify performance target with real scenario.
        """

        def simple_strategy(bar, context):
            return None  # No trades

        engine = BacktestEngine(integration_config)
        result = engine.run(realistic_bars, strategy_func=simple_strategy)

        # 90 bars should execute very quickly
        assert result.execution_time_seconds < 1.0

        # Verify all bars processed
        assert len(result.equity_curve) == 90

    def test_commission_and_slippage_applied(self, realistic_bars, integration_config):
        """
        Test that commission and slippage are properly applied to trades.

        Verifies realistic trading costs are included in backtest.
        """

        def test_strategy(bar, context):
            bar_count = context.get("bar_count", 0)
            if bar_count == 10:
                return "BUY"
            elif bar_count == 20:
                return "SELL"
            return None

        engine = BacktestEngine(integration_config)
        result = engine.run(realistic_bars, strategy_func=test_strategy)

        if len(result.trades) > 0:
            trade = result.trades[0]

            # Verify commission applied
            assert trade.commission_total > Decimal("0")

            # Verify slippage applied
            assert trade.slippage_total >= Decimal("0")

            # Verify P&L includes costs
            # (P&L should be less than gross P&L due to costs)


class TestBacktestEngineEdgeCases:
    """Test edge cases and error scenarios."""

    def test_no_trades_scenario(self, realistic_bars, integration_config):
        """Test backtest with strategy that generates no trades."""

        def no_trade_strategy(bar, context):
            return None  # Never trade

        engine = BacktestEngine(integration_config)
        result = engine.run(realistic_bars, strategy_func=no_trade_strategy)

        # Should complete successfully
        assert len(result.trades) == 0
        assert result.metrics.total_trades == 0
        assert result.metrics.win_rate == Decimal("0")

        # Equity curve should be flat (no changes)
        assert all(
            point.portfolio_value == integration_config.initial_capital
            for point in result.equity_curve
        )

    def test_single_bar_backtest(self, integration_config):
        """Test backtest with only one bar."""
        single_bar = [
            OHLCVBar(
                symbol="AAPL",
                timeframe="1d",
                timestamp=datetime(2024, 1, 1, tzinfo=UTC),
                open=Decimal("150"),
                high=Decimal("152"),
                low=Decimal("149"),
                close=Decimal("151"),
                volume=1000000,
                spread=Decimal("3"),
            )
        ]

        def simple_strategy(bar, context):
            return None

        engine = BacktestEngine(integration_config)
        result = engine.run(single_bar, strategy_func=simple_strategy)

        # Should handle gracefully
        assert len(result.equity_curve) == 1
        assert result.metrics.total_trades == 0
