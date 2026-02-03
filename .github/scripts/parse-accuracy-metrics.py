#!/usr/bin/env python3
"""
Parse pytest accuracy test results and generate markdown table.

This script reads pytest JSON report output and extracts detector accuracy
metrics (precision, recall, F1-score) for display in PR comments.

Usage:
    python parse-accuracy-metrics.py [report_path]

Output:
    Prints markdown table to stdout for use in GitHub Actions.
"""

import json
import sys
from pathlib import Path


def parse_pytest_report(report_path: str) -> dict:
    """Parse pytest JSON report for accuracy metrics.

    Args:
        report_path: Path to pytest JSON report file

    Returns:
        Dictionary mapping detector names to their metrics
    """
    try:
        with open(report_path) as f:
            report = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Warning: Could not parse report: {e}", file=sys.stderr)
        return {}

    metrics = {}

    # Extract metrics from test results
    for test in report.get('tests', []):
        nodeid = test.get('nodeid', '')

        # Look for accuracy test results
        if 'detector_accuracy' in nodeid or 'test_accuracy' in nodeid:
            # Extract detector name from test node ID
            # Expected format: tests/integration/test_detector_accuracy.py::test_spring_detector_accuracy
            parts = nodeid.split('::')
            if len(parts) >= 2:
                test_name = parts[-1]
                # Extract detector type from test name
                detector = test_name.replace('test_', '').replace('_detector_accuracy', '').replace('_accuracy', '')
                detector = detector.replace('_', ' ').title()

                # Get metrics from test metadata or call info
                metadata = test.get('metadata', {})
                call_info = test.get('call', {})

                metrics[detector] = {
                    'precision': metadata.get('precision', call_info.get('precision')),
                    'recall': metadata.get('recall', call_info.get('recall')),
                    'f1': metadata.get('f1_score', call_info.get('f1_score')),
                    'passed': test.get('outcome') == 'passed',
                    'duration': call_info.get('duration', 0)
                }

    return metrics


def format_metric(value) -> str:
    """Format a metric value for display.

    Args:
        value: Metric value (float, None, or string)

    Returns:
        Formatted string representation
    """
    if value is None:
        return 'N/A'
    if isinstance(value, (int, float)):
        return f'{value:.1%}' if value <= 1 else f'{value:.1f}%'
    return str(value)


def generate_markdown_table(metrics: dict) -> str:
    """Generate markdown table from metrics.

    Args:
        metrics: Dictionary mapping detector names to their metrics

    Returns:
        Markdown formatted table string
    """
    rows = [
        "| Detector | Precision | Recall | F1 Score | Status |",
        "|----------|-----------|--------|----------|--------|"
    ]

    if not metrics:
        # Return placeholder table when no metrics available
        rows.append("| Spring | Pending | Pending | Pending | ⏳ |")
        rows.append("| SOS | Pending | Pending | Pending | ⏳ |")
        rows.append("| UTAD | Pending | Pending | Pending | ⏳ |")
        rows.append("| LPS | Pending | Pending | Pending | ⏳ |")
    else:
        for detector, data in sorted(metrics.items()):
            status = "✅" if data.get('passed') else "❌"
            precision = format_metric(data.get('precision'))
            recall = format_metric(data.get('recall'))
            f1 = format_metric(data.get('f1'))
            rows.append(f"| {detector} | {precision} | {recall} | {f1} | {status} |")

    return "\n".join(rows)


def generate_summary(metrics: dict) -> str:
    """Generate summary statistics.

    Args:
        metrics: Dictionary mapping detector names to their metrics

    Returns:
        Summary string
    """
    if not metrics:
        return "*Accuracy tests are currently under development.*"

    total = len(metrics)
    passed = sum(1 for m in metrics.values() if m.get('passed'))

    return f"**{passed}/{total}** detectors meeting accuracy thresholds (Precision ≥75%, Recall ≥70%)"


def main():
    """Main entry point."""
    # Ensure UTF-8 encoding for stdout (needed for emoji on Windows)
    import io
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    else:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    report_path = sys.argv[1] if len(sys.argv) > 1 else 'pytest-report.json'

    if Path(report_path).exists():
        metrics = parse_pytest_report(report_path)
    else:
        print(f"Report file not found: {report_path}", file=sys.stderr)
        metrics = {}

    # Output markdown table
    print(generate_markdown_table(metrics))
    print()
    print(generate_summary(metrics))


if __name__ == '__main__':
    main()
