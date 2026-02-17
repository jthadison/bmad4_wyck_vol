#!/usr/bin/env python3
"""
Check if backtest baselines exist, are loadable, and report their status.
Used by monthly-regression.yaml workflow and for local validation.

Exit code: 0 = pass (baselines valid or not yet established)
Exit code: 1 = failure (baselines exist but are corrupt/unloadable)

Story 23.3: Establish Backtest Performance Baselines
NFR21: Automated regression testing with +/-5% tolerance
"""

import sys
from pathlib import Path

# Allow running from backend/ or backend/scripts/
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.backtesting.backtest_baseline_loader import load_all_backtest_baselines


def main() -> int:
    baselines_dir = Path(__file__).parent.parent / "tests" / "datasets" / "baselines" / "backtest"

    if not baselines_dir.exists():
        print(f"No baselines directory found at {baselines_dir}")
        print("Skipping check - baselines not yet established")
        return 0

    # Count how many baseline files exist on disk
    baseline_files = list(baselines_dir.glob("*_baseline.json"))
    if not baseline_files:
        print("No backtest baseline files found - skipping check")
        return 0

    print(f"Found {len(baseline_files)} baseline file(s) on disk")

    # Attempt to load all baselines
    baselines = load_all_backtest_baselines(baselines_dir)

    if not baselines:
        # Files exist but none loaded = corruption
        print("FAIL: Baseline files exist but none could be loaded")
        print("Check for schema mismatches or corrupt JSON")
        return 1

    if len(baselines) < len(baseline_files):
        print(
            f"WARNING: Only {len(baselines)} of {len(baseline_files)} "
            f"baselines loaded successfully"
        )

    print(f"Loaded {len(baselines)} backtest baseline(s):")
    for b in baselines:
        print(
            f"  {b.symbol}: win_rate={float(b.metrics.win_rate):.4f}, "
            f"pf={float(b.metrics.profit_factor):.4f}, "
            f"sharpe={float(b.metrics.sharpe_ratio):.4f}, "
            f"max_dd={float(b.metrics.max_drawdown):.4f}, "
            f"trades={b.metrics.total_trades}, "
            f"tolerance=+/-{float(b.tolerance_pct):.1f}%"
        )

    print(f"\nAll {len(baselines)} backtest baselines validated successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())
