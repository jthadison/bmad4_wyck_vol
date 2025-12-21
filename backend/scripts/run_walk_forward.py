#!/usr/bin/env python3
"""
Walk-Forward Testing CLI Tool (Story 12.4 Task 12).

Command-line tool for running walk-forward validation tests locally.
Provides colored console output and JSON report generation.

Usage:
    python scripts/run_walk_forward.py --symbols AAPL,MSFT --start-date 2020-01-01 --end-date 2023-12-31

Author: Story 12.4 Task 12
"""

import argparse
import json
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.backtesting.walk_forward_engine import WalkForwardEngine
from src.models.backtest import BacktestConfig, WalkForwardConfig


class Colors:
    """ANSI color codes for terminal output."""

    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def print_colored(text: str, color: str, bold: bool = False):
    """Print colored text to console."""
    if bold:
        print(f"{Colors.BOLD}{color}{text}{Colors.RESET}")
    else:
        print(f"{color}{text}{Colors.RESET}")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Run walk-forward validation test",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run walk-forward on AAPL for 2020-2023
  python scripts/run_walk_forward.py --symbols AAPL --start-date 2020-01-01 --end-date 2023-12-31

  # Run with custom window sizes
  python scripts/run_walk_forward.py --symbols AAPL,MSFT --start-date 2020-01-01 --end-date 2023-12-31 --train-months 12 --validate-months 6

  # Save results to JSON file
  python scripts/run_walk_forward.py --symbols AAPL --start-date 2020-01-01 --end-date 2023-12-31 --output results.json
        """,
    )

    # Required arguments
    parser.add_argument(
        "--symbols",
        required=True,
        help="Comma-separated list of symbols (e.g., AAPL,MSFT,GOOGL)",
    )
    parser.add_argument(
        "--start-date",
        required=True,
        help="Start date in YYYY-MM-DD format",
    )
    parser.add_argument(
        "--end-date",
        required=True,
        help="End date in YYYY-MM-DD format",
    )

    # Optional arguments
    parser.add_argument(
        "--train-months",
        type=int,
        default=6,
        help="Training window size in months (default: 6)",
    )
    parser.add_argument(
        "--validate-months",
        type=int,
        default=3,
        help="Validation window size in months (default: 3)",
    )
    parser.add_argument(
        "--primary-metric",
        choices=["win_rate", "avg_r_multiple", "profit_factor", "sharpe_ratio"],
        default="win_rate",
        help="Primary metric for degradation detection (default: win_rate)",
    )
    parser.add_argument(
        "--degradation-threshold",
        type=float,
        default=0.80,
        help="Minimum performance ratio (default: 0.80 = 80%%)",
    )
    parser.add_argument(
        "--output",
        help="Path to save JSON report (optional)",
    )

    args = parser.parse_args()

    # Parse symbols
    symbols = [s.strip() for s in args.symbols.split(",")]

    # Parse dates
    try:
        start_date = datetime.strptime(args.start_date, "%Y-%m-%d").date()
        end_date = datetime.strptime(args.end_date, "%Y-%m-%d").date()
    except ValueError as e:
        print_colored(f"Error: Invalid date format - {e}", Colors.RED)
        return 1

    # Print header
    print_colored("\n" + "=" * 80, Colors.BLUE, bold=True)
    print_colored("  WALK-FORWARD VALIDATION TEST", Colors.BLUE, bold=True)
    print_colored("=" * 80 + "\n", Colors.BLUE, bold=True)

    # Print configuration
    print_colored("Configuration:", Colors.BOLD)
    print(f"  Symbols: {', '.join(symbols)}")
    print(f"  Date Range: {start_date} to {end_date}")
    print(f"  Train Window: {args.train_months} months")
    print(f"  Validate Window: {args.validate_months} months")
    print(f"  Primary Metric: {args.primary_metric}")
    print(f"  Degradation Threshold: {args.degradation_threshold * 100:.0f}%")
    print()

    # Create configuration
    base_config = BacktestConfig(
        symbol=symbols[0],  # Use first symbol for now
        start_date=start_date,
        end_date=end_date,
    )

    config = WalkForwardConfig(
        symbols=symbols,
        overall_start_date=start_date,
        overall_end_date=end_date,
        train_period_months=args.train_months,
        validate_period_months=args.validate_months,
        backtest_config=base_config,
        primary_metric=args.primary_metric,
        degradation_threshold=Decimal(str(args.degradation_threshold)),
    )

    # Run walk-forward test
    print_colored("Running walk-forward test...\n", Colors.BOLD)

    try:
        engine = WalkForwardEngine()
        result = engine.walk_forward_test(symbols, config)

        # Print results
        print_colored("\n" + "=" * 80, Colors.BLUE, bold=True)
        print_colored("  RESULTS", Colors.BLUE, bold=True)
        print_colored("=" * 80 + "\n", Colors.BLUE, bold=True)

        # Summary statistics
        print_colored("Summary Statistics:", Colors.BOLD)
        stats = result.summary_statistics
        print(f"  Total Windows: {stats.get('total_windows', 0)}")
        print(f"  Avg Validate Win Rate: {stats.get('avg_validate_win_rate', 0) * 100:.1f}%")
        print(f"  Avg Validate R-Multiple: {stats.get('avg_validate_avg_r', 0):.2f}")
        print(f"  Avg Validate Profit Factor: {stats.get('avg_validate_profit_factor', 0):.2f}")
        print(f"  Stability Score (CV): {float(result.stability_score):.4f}")
        print()

        # Degradation summary
        degradation_count = stats.get("degradation_count", 0)
        if degradation_count > 0:
            print_colored(
                f"Degradation Detected: {degradation_count} windows ({stats.get('degradation_percentage', 0):.1f}%)",
                Colors.YELLOW,
            )
        else:
            print_colored("No Degradation Detected", Colors.GREEN)
        print()

        # Window details
        print_colored("Window Details:", Colors.BOLD)
        for window in result.windows:
            color = Colors.RED if window.degradation_detected else Colors.GREEN
            status = "DEGRADED" if window.degradation_detected else "OK"

            print_colored(
                f"  Window {window.window_number}: {window.train_start_date} to {window.validate_end_date}",
                color,
            )
            print(
                f"    Train Win Rate: {float(window.train_metrics.win_rate) * 100:.1f}% | "
                f"Validate Win Rate: {float(window.validate_metrics.win_rate) * 100:.1f}% | "
                f"Ratio: {float(window.performance_ratio) * 100:.1f}% ({status})"
            )

        print()

        # Statistical significance
        print_colored("Statistical Significance (p-values):", Colors.BOLD)
        sig = result.statistical_significance
        for metric, pvalue in sig.items():
            if pvalue < 0.05:
                print_colored(
                    f"  {metric}: {pvalue:.4f} (SIGNIFICANT - potential overfitting)",
                    Colors.YELLOW,
                )
            else:
                print_colored(
                    f"  {metric}: {pvalue:.4f} (not significant - good)",
                    Colors.GREEN,
                )

        print()

        # Execution time
        print_colored("Execution Time:", Colors.BOLD)
        print(f"  Total: {result.total_execution_time_seconds:.2f}s")
        print(f"  Avg per Window: {result.avg_window_execution_time_seconds:.2f}s")
        print()

        # Save to JSON if requested
        if args.output:
            output_path = Path(args.output)

            # Convert to dict for JSON serialization
            result_dict = result.model_dump(mode="json")

            with open(output_path, "w") as f:
                json.dump(result_dict, f, indent=2)

            print_colored(f"Results saved to {output_path}", Colors.GREEN)
            print()

        print_colored("=" * 80 + "\n", Colors.BLUE, bold=True)

        return 0

    except Exception as e:
        print_colored(f"\nError: {e}", Colors.RED)
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
