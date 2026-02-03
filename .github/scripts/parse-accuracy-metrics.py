#!/usr/bin/env python3
"""
Parse accuracy test results from pytest JSON report.

Extracts precision, recall, and F1-score metrics from detector accuracy tests
and formats them as a markdown table for PR comments.

Usage:
    python parse-accuracy-metrics.py [accuracy-report.json]

If no file provided, generates placeholder table.
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, Optional


def parse_test_output(stdout: str) -> Dict[str, Dict[str, str]]:
    """
    Parse detector metrics from pytest stdout capture.

    Expected format:
        === Spring Detector Results ===
        Precision: 82.50%
        Recall: 75.00%
        F1-Score: 78.57%

    Returns:
        Dict mapping detector name to metrics dict with precision, recall, f1_score
    """
    metrics = {}

    # Pattern to match detector result sections
    detector_pattern = r"=== (\w+) Detector Results ==="
    metric_pattern = r"(Precision|Recall|F1-Score):\s+([\d.]+)%"

    # Find all detector sections
    sections = re.split(detector_pattern, stdout)

    # Process pairs of (detector_name, content)
    for i in range(1, len(sections), 2):
        if i + 1 >= len(sections):
            break

        detector_name = sections[i]
        content = sections[i + 1]

        # Extract metrics from content
        detector_metrics = {}
        for match in re.finditer(metric_pattern, content):
            metric_name = match.group(1).lower().replace("-", "_")
            metric_value = match.group(2)
            detector_metrics[metric_name] = metric_value

        if detector_metrics:
            metrics[detector_name] = detector_metrics

    return metrics


def determine_status(precision: Optional[str], recall: Optional[str]) -> str:
    """
    Determine test status emoji based on precision and recall thresholds.

    NFR Thresholds:
    - Precision ≥75%
    - Recall ≥70%
    """
    if precision is None or recall is None:
        return "⏳"

    try:
        prec_val = float(precision)
        rec_val = float(recall)

        if prec_val >= 75.0 and rec_val >= 70.0:
            return "✅"
        else:
            return "❌"
    except (ValueError, TypeError):
        return "⏳"


def format_metric(value: Optional[str]) -> str:
    """Format metric value with % sign or 'Pending'."""
    if value is None:
        return "Pending"
    return f"{value}%"


def generate_markdown_table(metrics: Dict[str, Dict[str, str]]) -> str:
    """
    Generate markdown table from parsed metrics.

    Args:
        metrics: Dict mapping detector name to metrics dict

    Returns:
        Formatted markdown table string
    """
    # Define detectors in desired order
    detectors = ["Spring", "SOS", "UTAD", "LPS"]

    rows = []
    for detector in detectors:
        detector_metrics = metrics.get(detector, {})

        precision = detector_metrics.get("precision")
        recall = detector_metrics.get("recall")
        f1_score = detector_metrics.get("f1_score")

        status = determine_status(precision, recall)

        rows.append(
            f"| {detector} | {format_metric(precision)} | {format_metric(recall)} | "
            f"{format_metric(f1_score)} | {status} |"
        )

    table = "| Detector | Precision | Recall | F1 Score | Status |\n"
    table += "|----------|-----------|--------|----------|--------|\n"
    table += "\n".join(rows)

    return table


def parse_json_report(report_path: Path) -> Dict[str, Dict[str, str]]:
    """
    Parse pytest JSON report and extract accuracy metrics.

    Args:
        report_path: Path to pytest JSON report file

    Returns:
        Dict mapping detector name to metrics
    """
    try:
        with open(report_path, "r", encoding="utf-8") as f:
            report = json.load(f)

        all_metrics = {}

        # Process each test
        for test in report.get("tests", []):
            # Look for accuracy tests
            if "test_detector_accuracy" not in test.get("nodeid", ""):
                continue

            # Extract stdout from test call
            stdout = ""
            if "call" in test and "stdout" in test["call"]:
                stdout = test["call"]["stdout"]

            # Parse metrics from stdout
            test_metrics = parse_test_output(stdout)
            all_metrics.update(test_metrics)

        return all_metrics

    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Warning: Could not parse JSON report: {e}", file=sys.stderr)
        return {}


def generate_placeholder_table() -> str:
    """Generate placeholder table when no metrics available."""
    return generate_markdown_table({})


def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        report_path = Path(sys.argv[1])
        if report_path.exists():
            metrics = parse_json_report(report_path)
            table = generate_markdown_table(metrics)
        else:
            table = generate_placeholder_table()
    else:
        table = generate_placeholder_table()

    print(table)


if __name__ == "__main__":
    main()
