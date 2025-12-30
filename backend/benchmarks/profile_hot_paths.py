#!/usr/bin/env python3
"""
Performance Profiling Script for Story 12.9 - Task 5

This script uses py-spy to profile CPU hot paths in the signal generation
and backtest execution pipelines. It generates flame graphs (SVG files) that
visualize where the code spends the most time.

Usage:
    # Profile signal generation benchmarks
    poetry run python benchmarks/profile_hot_paths.py signal

    # Profile backtest benchmarks
    poetry run python benchmarks/profile_hot_paths.py backtest

    # Profile all benchmarks
    poetry run python benchmarks/profile_hot_paths.py all

Output:
    benchmarks/profiles/signal_generation_flamegraph.svg
    benchmarks/profiles/backtest_flamegraph.svg

Flame Graph Interpretation:
    - Width: Time spent in function (wider = more time)
    - Height: Call stack depth (taller = deeper nesting)
    - Color: Function module (different colors for visual separation)
    - Hot paths: Wide boxes at the bottom of the graph

Performance Optimization Workflow:
    1. Run profiling: python benchmarks/profile_hot_paths.py all
    2. Open SVG files in browser
    3. Identify wide boxes (hot paths)
    4. Optimize those functions
    5. Re-run benchmarks to verify improvement
"""

import argparse
import subprocess
import sys
from pathlib import Path


def profile_signal_generation() -> int:
    """
    Profile signal generation benchmarks using py-spy.

    Returns:
        Exit code (0 = success, non-zero = failure)
    """
    output_file = Path("benchmarks/profiles/signal_generation_flamegraph.svg")
    output_file.parent.mkdir(parents=True, exist_ok=True)

    print("Profiling signal generation benchmarks...")
    print(f"Output: {output_file}")
    print("This will take 30-60 seconds...")

    cmd = [
        "poetry",
        "run",
        "py-spy",
        "record",
        "-o",
        str(output_file),
        "-f",
        "flamegraph",
        "-r",
        "100",  # Sample 100 times/second
        "-d",
        "30",  # Run for 30 seconds
        "--",
        "pytest",
        "benchmarks/test_signal_generation_latency.py",
        "--benchmark-only",
        "-v",
    ]

    result = subprocess.run(cmd, cwd=Path.cwd())

    if result.returncode == 0:
        print(f"\n[OK] Flame graph generated: {output_file}")
        print("     Open in browser to analyze hot paths")
    else:
        print(f"\n[FAILED] Profiling failed with exit code {result.returncode}")

    return result.returncode


def profile_backtest() -> int:
    """
    Profile backtest benchmarks using py-spy.

    Returns:
        Exit code (0 = success, non-zero = failure)
    """
    output_file = Path("benchmarks/profiles/backtest_flamegraph.svg")
    output_file.parent.mkdir(parents=True, exist_ok=True)

    print("Profiling backtest benchmarks...")
    print(f"Output: {output_file}")
    print("This will take 30-60 seconds...")

    cmd = [
        "poetry",
        "run",
        "py-spy",
        "record",
        "-o",
        str(output_file),
        "-f",
        "flamegraph",
        "-r",
        "100",  # Sample 100 times/second
        "-d",
        "30",  # Run for 30 seconds
        "--",
        "pytest",
        "benchmarks/test_backtest_speed.py",
        "--benchmark-only",
        "-v",
    ]

    result = subprocess.run(cmd, cwd=Path.cwd())

    if result.returncode == 0:
        print(f"\n[OK] Flame graph generated: {output_file}")
        print("     Open in browser to analyze hot paths")
    else:
        print(f"\n[FAILED] Profiling failed with exit code {result.returncode}")

    return result.returncode


def profile_all() -> int:
    """
    Profile all benchmarks.

    Returns:
        Exit code (0 = success, non-zero = failure)
    """
    print("=" * 80)
    print("PROFILING ALL BENCHMARKS")
    print("=" * 80)
    print()

    # Profile signal generation
    signal_result = profile_signal_generation()
    print()

    # Profile backtest
    backtest_result = profile_backtest()
    print()

    # Summary
    print("=" * 80)
    print("PROFILING SUMMARY")
    print("=" * 80)
    print(f"Signal generation: {'[SUCCESS]' if signal_result == 0 else '[FAILED]'}")
    print(f"Backtest:          {'[SUCCESS]' if backtest_result == 0 else '[FAILED]'}")
    print()

    if signal_result == 0 and backtest_result == 0:
        print("Next steps:")
        print("1. Open flame graphs in browser:")
        print("   - benchmarks/profiles/signal_generation_flamegraph.svg")
        print("   - benchmarks/profiles/backtest_flamegraph.svg")
        print("2. Identify wide boxes (hot paths)")
        print("3. Optimize those functions (Task 6)")
        print("4. Re-run benchmarks to verify improvement")
        return 0
    else:
        print("[WARNING] Some profiling runs failed. Check output above for details.")
        return 1


def main() -> int:
    """
    Main entry point for profiling script.

    Returns:
        Exit code (0 = success, non-zero = failure)
    """
    parser = argparse.ArgumentParser(
        description="Profile signal generation and backtest benchmarks using py-spy"
    )
    parser.add_argument(
        "target",
        choices=["signal", "backtest", "all"],
        help="Which benchmarks to profile",
    )

    args = parser.parse_args()

    if args.target == "signal":
        return profile_signal_generation()
    elif args.target == "backtest":
        return profile_backtest()
    elif args.target == "all":
        return profile_all()
    else:
        print(f"Unknown target: {args.target}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
