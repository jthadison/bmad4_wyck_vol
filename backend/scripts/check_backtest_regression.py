#!/usr/bin/env python3
"""
Re-run backtests and compare current metrics against stored baselines.
Used by monthly-regression.yaml workflow to detect performance degradation.

Exit code: 0 = pass (all metrics within tolerance, or baselines not yet established)
Exit code: 1 = failure (regression detected in one or more symbols)

Story 23.3: Establish Backtest Performance Baselines
NFR21: Automated regression testing with +/-5% tolerance
"""

import hashlib
import sys
from pathlib import Path

# Allow running from backend/ or backend/scripts/
sys.path.insert(0, str(Path(__file__).parent.parent))
# Allow importing generate_backtest_baselines from scripts/
sys.path.insert(0, str(Path(__file__).parent))

from generate_backtest_baselines import generate_ohlcv_bars, run_backtest

from src.backtesting.backtest_baseline_loader import (
    detect_backtest_regression,
    load_backtest_baseline,
)

# Must match generate_backtest_baselines.py
RNG_SEED = 42

SYMBOL_CONFIGS = {
    "SPX500": {"base_price": 4500.0, "base_volume": 50_000_000.0, "max_position_size": "0.10"},
    "US30": {"base_price": 35000.0, "base_volume": 30_000_000.0, "max_position_size": "0.40"},
    "EURUSD": {"base_price": 1.08, "base_volume": 100_000.0, "max_position_size": "0.10"},
}


def main() -> int:
    baselines_dir = Path(__file__).parent.parent / "tests" / "datasets" / "baselines" / "backtest"

    if not baselines_dir.exists():
        print(f"No baselines directory found at {baselines_dir}")
        print("Skipping check - baselines not yet established")
        return 0

    baseline_files = list(baselines_dir.glob("*_baseline.json"))
    if not baseline_files:
        print("No backtest baseline files found - skipping check")
        return 0

    print(f"Found {len(baseline_files)} baseline file(s)")
    print("=" * 60)

    any_regression = False

    for symbol, cfg in SYMBOL_CONFIGS.items():
        print(f"\n--- {symbol} ---")

        # Load stored baseline
        baseline = load_backtest_baseline(symbol, baselines_dir)
        if baseline is None:
            print(f"  No baseline file for {symbol} - skipping")
            continue

        # Re-run backtest with same config and seed as generator
        symbol_offset = int(hashlib.md5(symbol.encode()).hexdigest(), 16) % 1000
        seed = RNG_SEED + symbol_offset

        bars = generate_ohlcv_bars(
            symbol, cfg["base_price"], cfg["base_volume"], n_bars=504, seed=seed
        )
        result = run_backtest(bars, max_position_size=cfg["max_position_size"])
        current = result.summary

        # Print current vs baseline
        print(f"  {'Metric':<22} {'Baseline':>12} {'Current':>12}")
        print(f"  {'-' * 46}")
        print(
            f"  {'win_rate':<22} {float(baseline.metrics.win_rate):>12.4f}"
            f" {float(current.win_rate):>12.4f}"
        )
        print(
            f"  {'profit_factor':<22} {float(baseline.metrics.profit_factor):>12.4f}"
            f" {float(current.profit_factor):>12.4f}"
        )
        print(
            f"  {'sharpe_ratio':<22} {float(baseline.metrics.sharpe_ratio):>12.4f}"
            f" {float(current.sharpe_ratio):>12.4f}"
        )
        print(
            f"  {'max_drawdown':<22} {float(baseline.metrics.max_drawdown):>12.4f}"
            f" {float(current.max_drawdown):>12.4f}"
        )
        print(
            f"  {'avg_r_multiple':<22} {float(baseline.metrics.average_r_multiple):>12.4f}"
            f" {float(current.average_r_multiple):>12.4f}"
        )
        print(
            f"  {'total_trades':<22} {baseline.metrics.total_trades:>12}"
            f" {current.total_trades:>12}"
        )

        # Compare
        regression, degraded = detect_backtest_regression(current, baseline)
        if regression:
            any_regression = True
            print(f"  REGRESSION DETECTED: {', '.join(degraded)}")
        else:
            print("  PASS - all metrics within tolerance")

    print("\n" + "=" * 60)
    if any_regression:
        print("FAIL: Regression detected in one or more symbols")
        return 1

    print("All backtest baselines pass regression check")
    return 0


if __name__ == "__main__":
    sys.exit(main())
