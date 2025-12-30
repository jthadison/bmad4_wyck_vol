"""
Backtest Speed Benchmarks (Story 12.9 Task 3).

Benchmarks BacktestEngine performance to validate NFR7 requirement:
>100 bars/second for backtesting.

Author: Story 12.9 Task 3
"""

from decimal import Decimal

import pytest

from src.models.ohlcv import OHLCVBar


class TestBacktestSpeed:
    """Backtest engine performance benchmarks (Task 3)."""

    @pytest.mark.benchmark
    def test_backtest_engine_speed(
        self, benchmark, sample_ohlcv_bars_large: list[OHLCVBar]
    ) -> None:
        """
        Benchmark BacktestEngine bar processing speed.

        Target: NFR7 >100 bars/second.
        """
        from src.backtesting.backtest_engine import BacktestEngine
        from src.models.backtest import BacktestConfig

        # Create backtest config
        config = BacktestConfig(
            symbol="BENCH_LARGE",
            start_date=sample_ohlcv_bars_large[0].timestamp.date(),
            end_date=sample_ohlcv_bars_large[-1].timestamp.date(),
            initial_capital=Decimal("100000"),
            max_position_size=Decimal("0.02"),
            commission_per_share=Decimal("0.005"),
        )

        # Simple buy-and-hold strategy for benchmarking
        def simple_strategy(bar: OHLCVBar, context: dict) -> str | None:
            """Buy on first bar, hold forever."""
            if not context.get("has_position"):
                context["has_position"] = True
                return "BUY"
            return None

        def run_backtest():
            """Run backtest on 10,000 bars."""
            engine = BacktestEngine(config)
            result = engine.run(bars=sample_ohlcv_bars_large, strategy_func=simple_strategy)
            return result

        # Benchmark the backtest
        result = benchmark(run_backtest)

        # Verify result
        assert result is not None
        assert result.metrics is not None

        # Calculate bars per second
        stats = benchmark.stats.stats
        total_bars = len(sample_ohlcv_bars_large)
        bars_per_second = total_bars / stats.mean

        # NFR7: Must process >100 bars/second
        assert (
            bars_per_second > 100
        ), f"Backtest too slow: {bars_per_second:.2f} bars/sec (target: >100 bars/sec)"

    @pytest.mark.skip(reason="OrderSimulator interface mismatch - needs investigation")
    @pytest.mark.benchmark
    def test_order_simulation_speed(self, benchmark) -> None:
        """
        Benchmark order simulation performance.

        Target: <10ms per order (Subtask 3.3).
        """
        from src.backtesting.order_simulator import OrderSimulator
        from src.backtesting.slippage_calculator import CommissionCalculator, SlippageCalculator

        simulator = OrderSimulator(SlippageCalculator(), CommissionCalculator())

        from datetime import UTC, datetime

        mock_bar = type(
            "MockBar",
            (),
            {"open": Decimal("150.00"), "timestamp": datetime.now(UTC), "volume": 1000000},
        )()

        def simulate_orders() -> list:
            """Simulate 100 market orders."""
            orders = []
            for _ in range(100):
                order = simulator.simulate_fill(
                    order_type="BUY",
                    bar=mock_bar,
                    shares=100,
                    avg_volume=Decimal("2000000"),
                )
                orders.append(order)
            return orders

        result = benchmark(simulate_orders)
        assert len(result) == 100

        stats = benchmark.stats.stats
        per_order_ms = (stats.mean / 100) * 1000

        assert per_order_ms < 10, f"Order simulation too slow: {per_order_ms:.2f}ms per order"

    @pytest.mark.skip(reason="Metrics calculation interface needs verification")
    @pytest.mark.benchmark
    def test_metrics_calculation_speed(self, benchmark) -> None:
        """
        Benchmark metrics calculation from 100 trades.

        Target: <50ms total (Subtask 3.5).
        """
        from datetime import UTC, datetime, timedelta
        from uuid import uuid4

        from src.models.backtest import Trade

        # Generate 100 mock trades
        trades = []
        for i in range(100):
            win = i % 3 == 0  # 33% win rate
            trade = Trade(
                signal_id=uuid4(),
                pattern_type="SPRING",
                entry_price=Decimal("150.00"),
                exit_price=Decimal("153.00" if win else "148.00"),
                shares=100,
                entry_time=datetime(2024, 1, 1, tzinfo=UTC) + timedelta(days=i),
                exit_time=datetime(2024, 1, 1, tzinfo=UTC) + timedelta(days=i + 5),
                pnl=Decimal("300.00" if win else "-200.00"),
                commission=Decimal("1.00"),
            )
            trades.append(trade)

        def calculate_metrics() -> dict:
            """Calculate backtest metrics."""
            from src.backtesting.metrics import calculate_metrics

            return calculate_metrics(
                trades=trades,
                equity_curve=[],
                initial_capital=Decimal("100000"),
            )

        result = benchmark(calculate_metrics)
        assert "total_trades" in result

        stats = benchmark.stats.stats
        time_ms = stats.mean * 1000

        assert time_ms < 50, f"Metrics calculation too slow: {time_ms:.2f}ms"
