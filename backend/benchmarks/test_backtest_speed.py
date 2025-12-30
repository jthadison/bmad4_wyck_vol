"""
Backtest Speed Benchmarks (Story 12.9 Task 3).

Benchmarks BacktestEngine performance to validate NFR7 requirement:
>100 bars/second for backtesting.

Author: Story 12.9 Task 3
"""

from decimal import Decimal

import pytest

from benchmarks.benchmark_config import NFR7_TARGET_BARS_PER_SECOND
from src.backtesting.backtest_engine import BacktestEngine
from src.models.backtest import BacktestConfig, BacktestResult
from src.models.ohlcv import OHLCVBar


class TestBacktestSpeed:
    """Backtest engine performance benchmarks (Task 3)."""

    @pytest.mark.benchmark
    def test_backtest_engine_speed(
        self, benchmark, sample_ohlcv_bars_large: list[OHLCVBar]
    ) -> None:
        """
        Benchmark BacktestEngine processing 1000 bars.

        Target: NFR7 >100 bars/second.
        """
        from datetime import datetime

        config = BacktestConfig(
            symbol="BENCH_LARGE",
            start_date=datetime(2024, 1, 1).date(),
            end_date=datetime(2024, 12, 31).date(),
            initial_capital=Decimal("100000"),
            max_position_size=Decimal("0.02"),
            commission_per_share=Decimal("0.005"),
        )

        def run_backtest() -> BacktestResult:
            """Run backtest with buy-and-hold strategy."""
            engine = BacktestEngine(config)

            def simple_strategy(bar, context):
                if context.get("bar_count", 0) == 1:
                    return "BUY"
                return None

            return engine.run(sample_ohlcv_bars_large[:1000], strategy_func=simple_strategy)

        result = benchmark(run_backtest)

        # Verify result
        assert result.backtest_run_id is not None
        assert len(result.equity_curve) == 1000

        # Calculate bars/second
        stats = benchmark.stats
        mean_time = stats.mean
        bars_per_second = 1000 / mean_time

        assert (
            bars_per_second >= NFR7_TARGET_BARS_PER_SECOND
        ), f"Backtest too slow: {bars_per_second:.0f} bars/s (NFR7 target: >{NFR7_TARGET_BARS_PER_SECOND} bars/s)"

        print("\n=== NFR7 Backtest Performance ===")
        print(f"Bars/second: {bars_per_second:.0f}")
        print(f"Time for 1000 bars: {mean_time:.3f}s")
        print(f"Target: >{NFR7_TARGET_BARS_PER_SECOND} bars/s")
        print(f"Status: {'✓ PASS' if bars_per_second >= NFR7_TARGET_BARS_PER_SECOND else '✗ FAIL'}")

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

        stats = benchmark.stats
        per_order_ms = (stats.mean / 100) * 1000

        assert per_order_ms < 10, f"Order simulation too slow: {per_order_ms:.2f}ms per order"

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

        stats = benchmark.stats
        time_ms = stats.mean * 1000

        assert time_ms < 50, f"Metrics calculation too slow: {time_ms:.2f}ms"
