#!/usr/bin/env python3
"""
Alternative Performance Profiling using cProfile (Story 12.9 - Task 5)

This script uses Python's built-in cProfile to analyze performance when py-spy
has Windows compatibility issues. While cProfile adds more overhead than py-spy,
it's reliable across all platforms.

Usage:
    # Profile signal generation
    poetry run python benchmarks/profile_with_cprofile.py signal

    # Profile backtest
    poetry run python benchmarks/profile_with_cprofile.py backtest

Output:
    Prints top 50 slowest functions with timing statistics
"""

import argparse
import cProfile
import pstats
import sys
from decimal import Decimal
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def profile_signal_generation() -> None:
    """Profile signal generation pipeline."""
    print("=" * 80)
    print("PROFILING SIGNAL GENERATION PIPELINE")
    print("=" * 80)
    print()

    from datetime import UTC, datetime, timedelta

    from src.models.ohlcv import OHLCVBar
    from src.pattern_engine.detectors.spring_detector import detect_spring

    # Generate test data
    print("Generating 1000 OHLCV bars...")
    bars = []
    for i in range(1000):
        trend = Decimal(i) * Decimal("0.05")
        noise = Decimal((i % 10) - 5)
        price = Decimal("150.00") + trend + noise
        daily_range = Decimal("5.00")

        bars.append(
            OHLCVBar(
                symbol="PROFILE_TEST",
                timeframe="1d",
                timestamp=datetime(2024, 1, 1, tzinfo=UTC) + timedelta(days=i),
                open=price,
                high=price + daily_range,
                low=price - daily_range,
                close=price + (daily_range * Decimal("0.3")),
                volume=1000000 + (i * 10000),
                spread=daily_range,
            )
        )

    print(f"Running pattern detection on {len(bars)} bars...")
    print("This will take 10-20 seconds...")
    print()

    # Profile the detection
    profiler = cProfile.Profile()
    profiler.enable()

    # Run detection multiple times to get meaningful data
    for _ in range(10):
        result = detect_spring(bars, symbol="PROFILE_TEST")

    profiler.disable()

    # Print results
    print("=" * 80)
    print("TOP 50 SLOWEST FUNCTIONS")
    print("=" * 80)
    stats = pstats.Stats(profiler)
    stats.strip_dirs()
    stats.sort_stats("cumulative")
    stats.print_stats(50)


def profile_backtest() -> None:
    """Profile backtest execution."""
    print("=" * 80)
    print("PROFILING BACKTEST ENGINE")
    print("=" * 80)
    print()

    from datetime import UTC, datetime, timedelta

    from src.backtesting.backtest_engine import BacktestEngine
    from src.models.backtest import BacktestConfig
    from src.models.ohlcv import OHLCVBar

    # Generate test data
    print("Generating 10,000 OHLCV bars...")
    bars = []
    for i in range(10000):
        trend = Decimal(i) * Decimal("0.05")
        noise = Decimal((i % 10) - 5)
        price = Decimal("150.00") + trend + noise
        daily_range = Decimal("5.00")

        bars.append(
            OHLCVBar(
                symbol="PROFILE_TEST",
                timeframe="1d",
                timestamp=datetime(2024, 1, 1, tzinfo=UTC) + timedelta(days=i),
                open=price,
                high=price + daily_range,
                low=price - daily_range,
                close=price + (daily_range * Decimal("0.3")),
                volume=1000000 + (i * 10000),
                spread=daily_range,
            )
        )

    config = BacktestConfig(
        symbol="PROFILE_TEST",
        start_date=bars[0].timestamp.date(),
        end_date=bars[-1].timestamp.date(),
        initial_capital=Decimal("100000"),
        max_position_size=Decimal("0.02"),
        commission_per_share=Decimal("0.005"),
    )

    def simple_strategy(bar: OHLCVBar, context: dict) -> str | None:
        """Buy on first bar, hold forever."""
        if not context.get("has_position"):
            context["has_position"] = True
            return "BUY"
        return None

    print(f"Running backtest on {len(bars)} bars...")
    print("This will take 10-20 seconds...")
    print()

    # Profile the backtest
    profiler = cProfile.Profile()
    profiler.enable()

    engine = BacktestEngine(config)
    result = engine.run(bars=bars, strategy_func=simple_strategy)

    profiler.disable()

    # Print results
    print("=" * 80)
    print("TOP 50 SLOWEST FUNCTIONS")
    print("=" * 80)
    stats = pstats.Stats(profiler)
    stats.strip_dirs()
    stats.sort_stats("cumulative")
    stats.print_stats(50)

    print()
    print("=" * 80)
    print("BACKTEST RESULT")
    print("=" * 80)
    print(f"Total bars processed: {len(bars)}")
    print(f"Trades executed: {len(result.trades)}")
    print(f"Final portfolio value: ${result.equity_curve[-1].portfolio_value:,.2f}")


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Profile using cProfile")
    parser.add_argument(
        "target",
        choices=["signal", "backtest"],
        help="Which component to profile",
    )

    args = parser.parse_args()

    if args.target == "signal":
        profile_signal_generation()
    elif args.target == "backtest":
        profile_backtest()
    else:
        print(f"Unknown target: {args.target}")
        return 1

    print()
    print("=" * 80)
    print("PROFILING COMPLETE")
    print("=" * 80)
    print()
    print("Next steps:")
    print("1. Review 'cumulative time' column for hot paths")
    print("2. Focus on functions with high cumtime that are in src/ code")
    print("3. Consider optimizations:")
    print("   - Reduce redundant calculations")
    print("   - Cache expensive operations")
    print("   - Use vectorization for numerical operations")
    print("4. Re-run benchmarks to verify improvements")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
