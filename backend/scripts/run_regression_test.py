#!/usr/bin/env python3
"""
CLI Script for Running Regression Tests (Story 12.7 Task 9).

Executes regression tests across multiple symbols and reports results.
Can be run manually or integrated into CI/CD workflows.

Usage:
    python run_regression_test.py
    python run_regression_test.py --symbols AAPL,MSFT,GOOGL
    python run_regression_test.py --establish-baseline
    python run_regression_test.py --output results.json

Author: Story 12.7 Task 9
"""

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.backtesting.engine import BacktestEngine
from src.backtesting.regression_test_engine import RegressionTestEngine
from src.database import async_session_maker
from src.models.backtest import (
    BacktestConfig,
    CommissionConfig,
    RegressionTestConfig,
    SlippageConfig,
)
from src.repositories.regression_baseline_repository import RegressionBaselineRepository
from src.repositories.regression_test_repository import RegressionTestRepository
from src.services.regression_alert_service import AlertConfig, RegressionAlertService

# ANSI color codes for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"

# Default symbols (10 standard symbols from NFR21)
DEFAULT_SYMBOLS = [
    "AAPL",
    "MSFT",
    "GOOGL",
    "TSLA",
    "NVDA",
    "META",
    "AMZN",
    "SPY",
    "QQQ",
    "DIA",
]


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run regression tests for the Wyckoff trading system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_regression_test.py
  python run_regression_test.py --symbols AAPL,MSFT,GOOGL
  python run_regression_test.py --start-date 2020-01-01 --end-date 2023-12-31
  python run_regression_test.py --establish-baseline
  python run_regression_test.py --output regression_results.json

Exit Codes:
  0: Test passed (no regression detected)
  1: Test failed (regression detected)
  2: No baseline set (first run)
  3: Error during test execution
""",
    )

    parser.add_argument(
        "--symbols",
        type=str,
        default=",".join(DEFAULT_SYMBOLS),
        help=f"Comma-separated list of symbols (default: {','.join(DEFAULT_SYMBOLS)})",
    )

    parser.add_argument(
        "--start-date",
        type=str,
        default="2020-01-01",
        help="Test period start date in YYYY-MM-DD format (default: 2020-01-01)",
    )

    parser.add_argument(
        "--end-date",
        type=str,
        default=None,
        help="Test period end date in YYYY-MM-DD format (default: yesterday)",
    )

    parser.add_argument(
        "--establish-baseline",
        action="store_true",
        help="Establish new baseline from test results (only for PASS tests)",
    )

    parser.add_argument(
        "--alert",
        action="store_true",
        help="Send alerts if regression detected (requires alert service configuration)",
    )

    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Path to save JSON report (optional)",
    )

    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored output",
    )

    return parser.parse_args()


def print_header(text: str, use_color: bool = True):
    """Print section header."""
    if use_color:
        print(f"\n{BOLD}{BLUE}{'='*70}{RESET}")
        print(f"{BOLD}{BLUE}{text}{RESET}")
        print(f"{BOLD}{BLUE}{'='*70}{RESET}\n")
    else:
        print(f"\n{'='*70}")
        print(text)
        print(f"{'='*70}\n")


def print_status(status: str, use_color: bool = True):
    """Print test status with color."""
    if not use_color:
        print(f"Status: {status}")
        return

    if status == "PASS":
        print(f"Status: {BOLD}{GREEN}✓ {status}{RESET}")
    elif status == "FAIL":
        print(f"Status: {BOLD}{RED}✗ {status}{RESET}")
    elif status == "BASELINE_NOT_SET":
        print(f"Status: {BOLD}{YELLOW}⚠ {status}{RESET}")
    else:
        print(f"Status: {status}")


def print_metrics(metrics: dict, use_color: bool = True):
    """Print aggregate metrics."""
    print("\nAggregate Metrics:")
    print(f"  Total Trades:       {metrics['total_trades']}")
    print(f"  Win Rate:           {float(metrics['win_rate'])*100:.2f}%")
    print(f"  Avg R-Multiple:     {float(metrics['average_r_multiple']):.2f}")
    print(f"  Profit Factor:      {float(metrics['profit_factor']):.2f}")
    print(f"  Max Drawdown:       {float(metrics['max_drawdown'])*100:.2f}%")
    print(f"  Sharpe Ratio:       {float(metrics.get('sharpe_ratio', 0)):.2f}")


def print_degraded_metrics(degraded: list, comparisons: dict, use_color: bool = True):
    """Print degraded metrics with details."""
    if not degraded:
        if use_color:
            print(f"\n{GREEN}No metrics degraded beyond thresholds{RESET}")
        else:
            print("\nNo metrics degraded beyond thresholds")
        return

    print(f"\n{BOLD}{RED}Degraded Metrics:{RESET}" if use_color else "\nDegraded Metrics:")

    for metric_name in degraded:
        comparison = comparisons.get(metric_name)
        if comparison:
            # Handle both dict and MetricComparison objects
            if isinstance(comparison, dict):
                baseline = float(comparison["baseline_value"])
                current = float(comparison["current_value"])
                change = float(comparison["percent_change"])
                threshold = float(comparison["threshold"])
            else:
                # MetricComparison object
                baseline = float(comparison.baseline_value)
                current = float(comparison.current_value)
                change = float(comparison.percent_change)
                threshold = float(comparison.threshold)

            if use_color:
                print(f"  {RED}• {metric_name}:{RESET}")
            else:
                print(f"  • {metric_name}:")

            print(f"      Baseline:  {baseline:.4f}")
            print(f"      Current:   {current:.4f}")
            print(f"      Change:    {change:+.2f}%")
            print(f"      Threshold: {threshold:.2f}%")


async def run_regression_test(args):
    """Execute regression test with progress tracking."""
    start_time = time.time()
    use_color = not args.no_color

    # Parse arguments
    symbols = [s.strip() for s in args.symbols.split(",")]
    start_date = date.fromisoformat(args.start_date)

    if args.end_date:
        end_date = date.fromisoformat(args.end_date)
    else:
        # Default to yesterday
        end_date = date.today() - timedelta(days=1)

    print_header("Wyckoff Trading System - Regression Test", use_color)
    print(f"Symbols:     {', '.join(symbols)}")
    print(f"Date Range:  {start_date} to {end_date}")
    print(f"Total Symbols: {len(symbols)}")

    # Create configuration
    backtest_config = BacktestConfig(
        symbol=symbols[0],  # Will be overridden per symbol
        start_date=start_date,
        end_date=end_date,
        initial_capital=Decimal("100000.00"),
        position_size_pct=Decimal("0.10"),
        max_positions=5,
        commission_config=CommissionConfig(
            commission_type="PER_SHARE",
            commission_rate=Decimal("0.0050"),
        ),
        slippage_config=SlippageConfig(
            slippage_type="PERCENTAGE",
            slippage_rate=Decimal("0.0010"),
        ),
    )

    regression_config = RegressionTestConfig(
        symbols=symbols,
        start_date=start_date,
        end_date=end_date,
        backtest_config=backtest_config,
        degradation_thresholds={
            "win_rate": Decimal("5.0"),
            "average_r_multiple": Decimal("10.0"),
            "profit_factor": Decimal("15.0"),
        },
    )

    # Create repositories and engine
    async with async_session_maker() as session:
        test_repo = RegressionTestRepository(session)
        baseline_repo = RegressionBaselineRepository(session)
        backtest_engine = BacktestEngine()

        engine = RegressionTestEngine(
            backtest_engine=backtest_engine,
            test_repository=test_repo,
            baseline_repository=baseline_repo,
        )

        print_header("Running Regression Test", use_color)

        # Run test
        try:
            result = await engine.run_regression_test(regression_config)
        except Exception as e:
            print(
                f"\n{RED}Error during test execution: {e}{RESET}" if use_color else f"\nError: {e}"
            )
            return 3

    execution_time = time.time() - start_time

    # Print results
    print_header("Test Results", use_color)
    print(f"Test ID:     {result.test_id}")
    print(f"Version:     {result.codebase_version}")
    print(f"Execution Time: {execution_time:.2f} seconds")

    print_status(result.status, use_color)

    # Print metrics
    metrics_dict = result.aggregate_metrics.model_dump()
    print_metrics(metrics_dict, use_color)

    # Print per-symbol results
    print("\nPer-Symbol Results:")
    for symbol, symbol_result in result.per_symbol_results.items():
        print(
            f"  {symbol}: {symbol_result['total_trades']} trades, "
            f"{float(symbol_result['win_rate'])*100:.2f}% win rate"
        )

    # Print baseline comparison if available
    if result.baseline_comparison:
        print_header("Baseline Comparison", use_color)
        print_degraded_metrics(
            result.degraded_metrics,
            result.baseline_comparison.metric_comparisons,
            use_color,
        )

    # Establish baseline if requested
    if args.establish_baseline:
        if result.status == "PASS" or result.status == "BASELINE_NOT_SET":
            print_header("Establishing Baseline", use_color)
            async with async_session_maker() as session:
                baseline_repo = RegressionBaselineRepository(session)
                backtest_engine = BacktestEngine()
                test_repo = RegressionTestRepository(session)

                engine = RegressionTestEngine(
                    backtest_engine=backtest_engine,
                    test_repository=test_repo,
                    baseline_repository=baseline_repo,
                )

                baseline = await engine.establish_baseline(result.test_id)
                if use_color:
                    print(f"{GREEN}✓ Baseline established: {baseline.baseline_id}{RESET}")
                else:
                    print(f"Baseline established: {baseline.baseline_id}")
        else:
            if use_color:
                print(f"\n{YELLOW}⚠ Cannot establish baseline from FAIL test{RESET}")
            else:
                print("\nCannot establish baseline from FAIL test")

    # Save output if requested
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with output_path.open("w") as f:
            json.dump(result.model_dump(mode="json"), f, indent=2)

        if use_color:
            print(f"\n{GREEN}✓ Results saved to: {output_path}{RESET}")
        else:
            print(f"\nResults saved to: {output_path}")

    # Send alerts if requested
    if args.alert:
        print_header("Sending Alerts", use_color)

        # Build alert configuration from environment variables
        alert_config = AlertConfig(
            slack_webhook_url=os.getenv("SLACK_WEBHOOK_URL"),
            email_recipients=[
                email.strip()
                for email in os.getenv("ALERT_EMAIL_RECIPIENTS", "").split(",")
                if email.strip()
            ],
            webhook_url=os.getenv("ALERT_WEBHOOK_URL"),
            alert_on_pass=os.getenv("ALERT_ON_PASS", "false").lower() == "true",
            alert_on_fail=os.getenv("ALERT_ON_FAIL", "true").lower() == "true",
            alert_on_baseline_not_set=os.getenv("ALERT_ON_BASELINE_NOT_SET", "false").lower()
            == "true",
        )

        # Send alerts
        async with RegressionAlertService(alert_config) as alert_service:
            try:
                alert_results = await alert_service.send_alert(result, include_details=True)

                if alert_results:
                    for channel, success in alert_results.items():
                        if success:
                            if use_color:
                                print(f"  {GREEN}✓ {channel.capitalize()} alert sent{RESET}")
                            else:
                                print(f"  ✓ {channel.capitalize()} alert sent")
                        else:
                            if use_color:
                                print(f"  {RED}✗ {channel.capitalize()} alert failed{RESET}")
                            else:
                                print(f"  ✗ {channel.capitalize()} alert failed")
                else:
                    if use_color:
                        print(f"{YELLOW}No alerts sent (status does not match alert config){RESET}")
                    else:
                        print("No alerts sent (status does not match alert config)")

            except Exception as e:
                if use_color:
                    print(f"{RED}Error sending alerts: {e}{RESET}")
                else:
                    print(f"Error sending alerts: {e}")

    # Determine exit code
    if result.status == "PASS":
        return 0
    elif result.status == "FAIL":
        return 1
    elif result.status == "BASELINE_NOT_SET":
        if use_color:
            print(
                f"\n{YELLOW}⚠ No baseline set. Run with --establish-baseline to create one.{RESET}"
            )
        else:
            print("\nNo baseline set. Run with --establish-baseline to create one.")
        return 2
    else:
        return 3


def main():
    """Main entry point."""
    args = parse_arguments()

    try:
        exit_code = asyncio.run(run_regression_test(args))
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\nUnexpected error: {e}", file=sys.stderr)
        sys.exit(3)


if __name__ == "__main__":
    main()
