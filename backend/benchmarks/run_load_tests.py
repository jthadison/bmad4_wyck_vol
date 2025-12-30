#!/usr/bin/env python3
"""
Load Testing Runner Script for Story 12.9 - Task 9

This script provides convenient commands to run Locust load tests
with predefined configurations for different scenarios.

Usage:
    # Run light load test (10 users)
    poetry run python benchmarks/run_load_tests.py light

    # Run medium load test (50 users)
    poetry run python benchmarks/run_load_tests.py medium

    # Run heavy load test (100 users)
    poetry run python benchmarks/run_load_tests.py heavy

    # Run stress test (200 users, heavy workload)
    poetry run python benchmarks/run_load_tests.py stress

    # Run with custom parameters
    poetry run python benchmarks/run_load_tests.py custom --users 150 --spawn-rate 10
"""

import argparse
import subprocess
import sys
from pathlib import Path


def run_locust(
    users: int,
    spawn_rate: int,
    run_time: str,
    host: str,
    user_class: str = "WyckoffTradingUser",
    report_name: str = "load_test_report",
) -> int:
    """
    Run Locust load test with specified parameters.

    Args:
        users: Number of concurrent users
        spawn_rate: Users spawned per second
        run_time: Test duration (e.g., "5m", "30s")
        host: Target host URL
        user_class: Locust user class to use
        report_name: Output report filename (without extension)

    Returns:
        Exit code (0 = success, non-zero = failure)
    """
    output_file = Path(f"benchmarks/reports/{report_name}.html")
    output_file.parent.mkdir(parents=True, exist_ok=True)

    print(f"🚀 Running load test: {users} users, {spawn_rate} spawn/sec, {run_time}")
    print(f"   Host: {host}")
    print(f"   User class: {user_class}")
    print(f"   Report: {output_file}")
    print()

    cmd = [
        "poetry",
        "run",
        "locust",
        "-f",
        "benchmarks/locustfile.py",
        f"{user_class}",
        "--host",
        host,
        "--users",
        str(users),
        "--spawn-rate",
        str(spawn_rate),
        "--run-time",
        run_time,
        "--headless",
        "--html",
        str(output_file),
        "--csv",
        str(output_file.with_suffix("")),  # CSV output
    ]

    result = subprocess.run(cmd, cwd=Path.cwd())

    if result.returncode == 0:
        print()
        print("=" * 80)
        print("✅ LOAD TEST COMPLETED")
        print("=" * 80)
        print(f"HTML Report: {output_file}")
        print(f"CSV Stats:   {output_file.with_suffix('.csv')}")
        print()
    else:
        print()
        print("=" * 80)
        print("❌ LOAD TEST FAILED")
        print("=" * 80)
        print(f"Exit code: {result.returncode}")
        print()

    return result.returncode


def main() -> int:
    """
    Main entry point for load testing runner.

    Returns:
        Exit code (0 = success, non-zero = failure)
    """
    parser = argparse.ArgumentParser(description="Run Locust load tests")
    parser.add_argument(
        "scenario",
        choices=["light", "medium", "heavy", "stress", "custom"],
        help="Load test scenario",
    )
    parser.add_argument(
        "--host",
        default="http://localhost:8000",
        help="Target host URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--users",
        type=int,
        help="Number of concurrent users (custom scenario only)",
    )
    parser.add_argument(
        "--spawn-rate",
        type=int,
        help="Users spawned per second (custom scenario only)",
    )
    parser.add_argument(
        "--run-time",
        help="Test duration (e.g., 5m, 30s) (custom scenario only)",
    )

    args = parser.parse_args()

    # Predefined scenarios
    if args.scenario == "light":
        return run_locust(
            users=10,
            spawn_rate=2,
            run_time="2m",
            host=args.host,
            report_name="load_test_light",
        )

    elif args.scenario == "medium":
        return run_locust(
            users=50,
            spawn_rate=5,
            run_time="5m",
            host=args.host,
            report_name="load_test_medium",
        )

    elif args.scenario == "heavy":
        return run_locust(
            users=100,
            spawn_rate=10,
            run_time="5m",
            host=args.host,
            report_name="load_test_heavy",
        )

    elif args.scenario == "stress":
        return run_locust(
            users=200,
            spawn_rate=20,
            run_time="10m",
            host=args.host,
            user_class="HeavyLoadUser",
            report_name="load_test_stress",
        )

    elif args.scenario == "custom":
        if not all([args.users, args.spawn_rate, args.run_time]):
            print("❌ Custom scenario requires --users, --spawn-rate, and --run-time")
            return 1

        return run_locust(
            users=args.users,
            spawn_rate=args.spawn_rate,
            run_time=args.run_time,
            host=args.host,
            report_name=f"load_test_custom_{args.users}users",
        )

    else:
        print(f"❌ Unknown scenario: {args.scenario}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
