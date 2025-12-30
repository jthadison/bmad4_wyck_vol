#!/usr/bin/env python3
"""
Benchmark Comparison and Reporting Script (Story 12.9 - Task 8)

This script compares benchmark results between two runs (baseline vs current)
and generates:
1. Console report with regression/improvement analysis
2. HTML report with visualizations
3. PR comment for GitHub Actions

Usage:
    # Compare current run against baseline
    poetry run python benchmarks/compare_benchmarks.py \
        --baseline .benchmarks/main/benchmark_results.json \
        --current .benchmarks/pr/benchmark_results.json \
        --output reports/benchmark_comparison.html

    # Generate PR comment for GitHub Actions
    poetry run python benchmarks/compare_benchmarks.py \
        --baseline baseline.json \
        --current current.json \
        --pr-comment

Output:
    - Console: Colored summary with pass/fail status
    - HTML: Interactive charts and tables
    - PR comment: Markdown-formatted summary for GitHub
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def load_benchmark_results(filepath: Path) -> dict[str, Any]:
    """
    Load benchmark results from JSON file.

    Args:
        filepath: Path to benchmark results JSON file

    Returns:
        Dictionary of benchmark results
    """
    if not filepath.exists():
        print(f"❌ File not found: {filepath}")
        sys.exit(1)

    with open(filepath) as f:
        return json.load(f)


def calculate_regression(baseline_mean: float, current_mean: float) -> float:
    """
    Calculate regression percentage.

    Args:
        baseline_mean: Baseline mean latency (seconds)
        current_mean: Current mean latency (seconds)

    Returns:
        Regression percentage (positive = slower, negative = faster)
    """
    if baseline_mean == 0:
        return 0.0

    return (current_mean - baseline_mean) / baseline_mean * 100


def format_latency(seconds: float) -> str:
    """
    Format latency in appropriate units (ms or µs).

    Args:
        seconds: Latency in seconds

    Returns:
        Formatted string (e.g., "0.78ms" or "8.50µs")
    """
    if seconds >= 0.001:
        return f"{seconds * 1000:.2f}ms"
    else:
        return f"{seconds * 1_000_000:.2f}µs"


def generate_console_report(
    baseline: dict[str, Any],
    current: dict[str, Any],
    threshold_pct: float = 10.0,
) -> bool:
    """
    Generate console report comparing baseline and current benchmarks.

    Args:
        baseline: Baseline benchmark results
        current: Current benchmark results
        threshold_pct: Regression threshold percentage

    Returns:
        True if all benchmarks pass, False if any regressions detected
    """
    print("=" * 80)
    print("BENCHMARK COMPARISON REPORT")
    print("=" * 80)
    print()

    all_pass = True
    regressions = []
    improvements = []

    for benchmark_name in sorted(current.keys()):
        if benchmark_name not in baseline:
            print(f"⚠️  {benchmark_name}: NEW BENCHMARK (no baseline)")
            continue

        baseline_stats = baseline[benchmark_name].get("stats", {}).get("stats", {})
        current_stats = current[benchmark_name].get("stats", {}).get("stats", {})

        baseline_mean = baseline_stats.get("mean", 0)
        current_mean = current_stats.get("mean", 0)

        if baseline_mean == 0 or current_mean == 0:
            print(f"⚠️  {benchmark_name}: INCOMPLETE DATA")
            continue

        regression_pct = calculate_regression(baseline_mean, current_mean)

        # Determine status
        if regression_pct > threshold_pct:
            status = "❌ REGRESSION"
            all_pass = False
            regressions.append((benchmark_name, regression_pct))
        elif regression_pct < -5.0:  # 5% improvement
            status = "✅ IMPROVED"
            improvements.append((benchmark_name, abs(regression_pct)))
        else:
            status = "✅ PASS"

        # Print result
        print(f"{status}: {benchmark_name}")
        print(f"  Baseline: {format_latency(baseline_mean)}")
        print(f"  Current:  {format_latency(current_mean)}")
        print(f"  Change:   {regression_pct:+.1f}%")
        print()

    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total benchmarks: {len(current)}")
    print(f"Regressions (>{threshold_pct}%): {len(regressions)}")
    print(f"Improvements (>5%): {len(improvements)}")
    print()

    if regressions:
        print("⚠️  REGRESSIONS DETECTED:")
        for name, pct in regressions:
            print(f"  - {name}: {pct:+.1f}%")
        print()

    if improvements:
        print("✅ IMPROVEMENTS:")
        for name, pct in improvements:
            print(f"  - {name}: {pct:.1f}% faster")
        print()

    if all_pass:
        print("✅ ALL BENCHMARKS PASSED")
    else:
        print("❌ PERFORMANCE REGRESSION DETECTED")

    print("=" * 80)
    return all_pass


def generate_pr_comment(
    baseline: dict[str, Any],
    current: dict[str, Any],
    threshold_pct: float = 10.0,
) -> str:
    """
    Generate GitHub PR comment with benchmark comparison.

    Args:
        baseline: Baseline benchmark results
        current: Current benchmark results
        threshold_pct: Regression threshold percentage

    Returns:
        Markdown-formatted PR comment
    """
    regressions = []
    improvements = []
    unchanged = []

    for benchmark_name in sorted(current.keys()):
        if benchmark_name not in baseline:
            continue

        baseline_stats = baseline[benchmark_name].get("stats", {}).get("stats", {})
        current_stats = current[benchmark_name].get("stats", {}).get("stats", {})

        baseline_mean = baseline_stats.get("mean", 0)
        current_mean = current_stats.get("mean", 0)

        if baseline_mean == 0 or current_mean == 0:
            continue

        regression_pct = calculate_regression(baseline_mean, current_mean)

        if regression_pct > threshold_pct:
            regressions.append((benchmark_name, baseline_mean, current_mean, regression_pct))
        elif regression_pct < -5.0:
            improvements.append((benchmark_name, baseline_mean, current_mean, regression_pct))
        else:
            unchanged.append((benchmark_name, baseline_mean, current_mean, regression_pct))

    # Build markdown comment
    comment = []
    comment.append("## 📊 Performance Benchmark Results")
    comment.append("")

    if regressions:
        comment.append("### ❌ Regressions Detected")
        comment.append("")
        comment.append("| Benchmark | Baseline | Current | Change |")
        comment.append("|-----------|----------|---------|--------|")
        for name, baseline_mean, current_mean, regression_pct in regressions:
            comment.append(
                f"| `{name}` | {format_latency(baseline_mean)} | {format_latency(current_mean)} | 🔴 {regression_pct:+.1f}% |"
            )
        comment.append("")
        comment.append(
            f"⚠️ **{len(regressions)} benchmark(s) exceeded {threshold_pct}% regression threshold**"
        )
        comment.append("")

    if improvements:
        comment.append("### ✅ Improvements")
        comment.append("")
        comment.append("| Benchmark | Baseline | Current | Change |")
        comment.append("|-----------|----------|---------|--------|")
        for name, baseline_mean, current_mean, regression_pct in improvements:
            comment.append(
                f"| `{name}` | {format_latency(baseline_mean)} | {format_latency(current_mean)} | 🟢 {regression_pct:+.1f}% |"
            )
        comment.append("")

    if unchanged:
        comment.append("<details><summary>✅ Unchanged (within tolerance)</summary>")
        comment.append("")
        comment.append("| Benchmark | Baseline | Current | Change |")
        comment.append("|-----------|----------|---------|--------|")
        for name, baseline_mean, current_mean, regression_pct in unchanged:
            comment.append(
                f"| `{name}` | {format_latency(baseline_mean)} | {format_latency(current_mean)} | {regression_pct:+.1f}% |"
            )
        comment.append("")
        comment.append("</details>")
        comment.append("")

    # Summary
    total = len(regressions) + len(improvements) + len(unchanged)
    comment.append("---")
    comment.append(f"**Total benchmarks**: {total}")
    comment.append(f"- ❌ Regressions: {len(regressions)}")
    comment.append(f"- ✅ Improvements: {len(improvements)}")
    comment.append(f"- ⚪ Unchanged: {len(unchanged)}")

    return "\n".join(comment)


def generate_html_report(
    baseline: dict[str, Any],
    current: dict[str, Any],
    output_file: Path,
    threshold_pct: float = 10.0,
) -> None:
    """
    Generate HTML report with visualizations.

    Args:
        baseline: Baseline benchmark results
        current: Current benchmark results
        output_file: Output HTML file path
        threshold_pct: Regression threshold percentage
    """
    html = []
    html.append("<!DOCTYPE html>")
    html.append("<html>")
    html.append("<head>")
    html.append("<meta charset='utf-8'>")
    html.append("<title>Benchmark Comparison Report</title>")
    html.append("<style>")
    html.append(
        """
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 40px; }
        h1 { color: #333; }
        table { border-collapse: collapse; width: 100%; margin: 20px 0; }
        th { background-color: #f5f5f5; padding: 12px; text-align: left; border-bottom: 2px solid #ddd; }
        td { padding: 10px; border-bottom: 1px solid #eee; }
        .regression { color: #d73a49; font-weight: bold; }
        .improvement { color: #28a745; font-weight: bold; }
        .unchanged { color: #666; }
        .pass { background-color: #d4edda; }
        .fail { background-color: #f8d7da; }
        .warning { background-color: #fff3cd; }
    """
    )
    html.append("</style>")
    html.append("</head>")
    html.append("<body>")
    html.append("<h1>📊 Benchmark Comparison Report</h1>")

    # Generate table
    html.append("<table>")
    html.append("<thead>")
    html.append(
        "<tr><th>Benchmark</th><th>Baseline</th><th>Current</th><th>Change</th><th>Status</th></tr>"
    )
    html.append("</thead>")
    html.append("<tbody>")

    for benchmark_name in sorted(current.keys()):
        if benchmark_name not in baseline:
            continue

        baseline_stats = baseline[benchmark_name].get("stats", {}).get("stats", {})
        current_stats = current[benchmark_name].get("stats", {}).get("stats", {})

        baseline_mean = baseline_stats.get("mean", 0)
        current_mean = current_stats.get("mean", 0)

        if baseline_mean == 0 or current_mean == 0:
            continue

        regression_pct = calculate_regression(baseline_mean, current_mean)

        # Determine status and CSS class
        if regression_pct > threshold_pct:
            status = "❌ REGRESSION"
            css_class = "fail"
            change_class = "regression"
        elif regression_pct < -5.0:
            status = "✅ IMPROVED"
            css_class = "pass"
            change_class = "improvement"
        else:
            status = "✅ PASS"
            css_class = "pass"
            change_class = "unchanged"

        html.append(f"<tr class='{css_class}'>")
        html.append(f"<td><code>{benchmark_name}</code></td>")
        html.append(f"<td>{format_latency(baseline_mean)}</td>")
        html.append(f"<td>{format_latency(current_mean)}</td>")
        html.append(f"<td class='{change_class}'>{regression_pct:+.1f}%</td>")
        html.append(f"<td>{status}</td>")
        html.append("</tr>")

    html.append("</tbody>")
    html.append("</table>")
    html.append("</body>")
    html.append("</html>")

    # Write to file
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text("\n".join(html))

    print(f"✅ HTML report generated: {output_file}")


def main() -> int:
    """
    Main entry point for benchmark comparison script.

    Returns:
        Exit code (0 = success, 1 = failure)
    """
    parser = argparse.ArgumentParser(description="Compare benchmark results")
    parser.add_argument("--baseline", required=True, help="Baseline benchmark results JSON file")
    parser.add_argument("--current", required=True, help="Current benchmark results JSON file")
    parser.add_argument("--output", help="Output HTML report file")
    parser.add_argument(
        "--pr-comment",
        action="store_true",
        help="Generate PR comment (outputs to stdout)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=10.0,
        help="Regression threshold percentage (default: 10.0)",
    )

    args = parser.parse_args()

    baseline = load_benchmark_results(Path(args.baseline))
    current = load_benchmark_results(Path(args.current))

    # Console report (always)
    all_pass = generate_console_report(baseline, current, args.threshold)

    # HTML report (optional)
    if args.output:
        generate_html_report(baseline, current, Path(args.output), args.threshold)

    # PR comment (optional)
    if args.pr_comment:
        pr_comment = generate_pr_comment(baseline, current, args.threshold)
        print("\n" + "=" * 80)
        print("PR COMMENT (copy to GitHub)")
        print("=" * 80)
        print(pr_comment)

    # Exit code: 0 = pass, 1 = regression detected
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
