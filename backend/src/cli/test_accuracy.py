#!/usr/bin/env python3
"""
CLI Tool for Local Detector Accuracy Testing (Story 12.3 Task 11)

This tool allows developers to run detector accuracy tests locally with:
- Interactive detector selection
- Threshold tuning mode
- HTML report generation
- Baseline comparison
- NFR compliance checking

Usage:
    python -m src.cli.test_accuracy --detector SpringDetector
    python -m src.cli.test_accuracy --detector all --tune-threshold
    python -m src.cli.test_accuracy --detector SpringDetector --threshold 0.75 --save-baseline
    python -m src.cli.test_accuracy --compare-baseline

Author: Story 12.3 Task 11
"""

import argparse
from decimal import Decimal
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from src.backtesting.accuracy_tester import (
    DetectorAccuracyTester,
    detect_regression,
    load_baseline,
    save_baseline,
    tune_confidence_threshold,
)
from src.backtesting.dataset_loader import load_labeled_patterns
from src.backtesting.report_generator import AccuracyReportGenerator

console = Console()


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Local Detector Accuracy Testing Tool (Story 12.3)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test a specific detector
  python -m src.cli.test_accuracy --detector SpringDetector

  # Test all detectors
  python -m src.cli.test_accuracy --detector all

  # Tune threshold for optimal F1-score
  python -m src.cli.test_accuracy --detector SpringDetector --tune-threshold

  # Test with specific threshold and save as baseline
  python -m src.cli.test_accuracy --detector SpringDetector --threshold 0.75 --save-baseline

  # Compare current metrics against baseline
  python -m src.cli.test_accuracy --detector SpringDetector --compare-baseline

  # Generate HTML report only
  python -m src.cli.test_accuracy --detector SpringDetector --generate-report
        """,
    )

    parser.add_argument(
        "--detector",
        type=str,
        required=True,
        choices=["SpringDetector", "SOSDetector", "UTADDetector", "LPSDetector", "all"],
        help="Detector to test (or 'all' for all detectors)",
    )

    parser.add_argument(
        "--threshold",
        type=float,
        default=0.70,
        help="Confidence threshold for detection (default: 0.70)",
    )

    parser.add_argument(
        "--tune-threshold",
        action="store_true",
        help="Run threshold tuning to find optimal F1-score",
    )

    parser.add_argument(
        "--threshold-min",
        type=float,
        default=0.50,
        help="Minimum threshold for tuning (default: 0.50)",
    )

    parser.add_argument(
        "--threshold-max",
        type=float,
        default=0.95,
        help="Maximum threshold for tuning (default: 0.95)",
    )

    parser.add_argument(
        "--threshold-step",
        type=float,
        default=0.05,
        help="Step size for threshold tuning (default: 0.05)",
    )

    parser.add_argument(
        "--save-baseline",
        action="store_true",
        help="Save current metrics as baseline for regression detection",
    )

    parser.add_argument(
        "--compare-baseline",
        action="store_true",
        help="Compare current metrics against existing baseline",
    )

    parser.add_argument(
        "--generate-report",
        action="store_true",
        help="Generate HTML accuracy report",
    )

    parser.add_argument(
        "--dataset-version",
        type=str,
        default="v1",
        help="Labeled dataset version to use (default: v1)",
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        default="tests/reports",
        help="Output directory for reports (default: tests/reports)",
    )

    return parser.parse_args()


def get_pattern_type_for_detector(detector_name: str) -> str:
    """Map detector name to pattern type."""
    mapping = {
        "SpringDetector": "SPRING",
        "SOSDetector": "SOS",
        "UTADDetector": "UTAD",
        "LPSDetector": "LPS",
    }
    return mapping.get(detector_name, "UNKNOWN")


def test_detector(
    detector_name: str,
    threshold: Decimal,
    dataset_version: str = "v1",
) -> dict[str, Any]:
    """
    Test a single detector and return metrics.

    Args:
        detector_name: Name of detector to test
        threshold: Confidence threshold
        dataset_version: Labeled dataset version

    Returns:
        Dictionary with metrics and test results
    """
    console.print(f"\n[bold cyan]Testing {detector_name}...[/bold cyan]")
    console.print(
        "[yellow]⚠️  Using simulated detector (real detectors not yet integrated)[/yellow]"
    )

    # Load labeled dataset
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(f"Loading labeled dataset ({dataset_version})...", total=None)
        labeled_data = load_labeled_patterns(version=dataset_version)
        progress.update(task, completed=True)

    pattern_type = get_pattern_type_for_detector(detector_name)

    # Filter for specific pattern type
    pattern_data = labeled_data[labeled_data["pattern_type"] == pattern_type]

    if pattern_data.empty:
        console.print(f"[yellow]⚠️ No {pattern_type} patterns found in dataset[/yellow]")
        return {"error": f"No {pattern_type} patterns in dataset"}

    console.print(f"Found {len(pattern_data)} {pattern_type} patterns")

    # Create simulated detector for testing infrastructure
    # TODO: Replace with real detector when available
    # from src.pattern_engine.detectors.spring_detector import SpringDetector
    # detector = SpringDetector()
    from src.backtesting.accuracy_tester import DetectedPattern, PatternDetector
    from src.models.ohlcv import OHLCVBar

    class SimulatedDetector(PatternDetector):
        """Simulated detector for CLI testing until real detectors are integrated."""

        def detect(self, bars: list[OHLCVBar], **kwargs) -> list[DetectedPattern]:
            return []

    detector = SimulatedDetector()

    # Run accuracy test
    tester = DetectorAccuracyTester()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Running accuracy test...", total=None)
        metrics = tester.test_detector_accuracy(
            detector=detector,
            labeled_data=labeled_data,
            pattern_type=pattern_type,
            detector_name=detector_name,
            detector_version="1.0",
            threshold=threshold,
        )
        progress.update(task, completed=True)

    # Get FP/FN analysis
    false_positives = tester.analyze_false_positives()
    false_negatives = tester.analyze_false_negatives()

    return {
        "metrics": metrics,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "pattern_type": pattern_type,
    }


def display_metrics(detector_name: str, metrics: Any) -> None:
    """Display metrics in a formatted table."""
    table = Table(title=f"{detector_name} Accuracy Metrics", show_header=True)
    table.add_column("Metric", style="cyan", width=30)
    table.add_column("Value", style="magenta", justify="right")
    table.add_column("Status", justify="center")

    # Standard metrics
    table.add_row(
        "Total Samples",
        str(metrics.total_samples),
        "",
    )
    table.add_row(
        "True Positives",
        str(metrics.true_positives),
        "✓" if metrics.true_positives > 0 else "",
    )
    table.add_row(
        "False Positives",
        str(metrics.false_positives),
        "⚠️" if metrics.false_positives > 10 else "",
    )
    table.add_row(
        "False Negatives",
        str(metrics.false_negatives),
        "⚠️" if metrics.false_negatives > 10 else "",
    )
    table.add_row(
        "True Negatives",
        str(metrics.true_negatives),
        "",
    )

    table.add_section()

    # Performance metrics
    precision_pct = float(metrics.precision) * 100
    recall_pct = float(metrics.recall) * 100
    f1_pct = float(metrics.f1_score) * 100

    table.add_row(
        "Precision",
        f"{precision_pct:.2f}%",
        "✓" if metrics.precision >= Decimal("0.75") else "✗",
    )
    table.add_row(
        "Recall",
        f"{recall_pct:.2f}%",
        "✓" if metrics.recall >= Decimal("0.75") else "✗",
    )
    table.add_row(
        "F1-Score",
        f"{f1_pct:.2f}%",
        "✓" if metrics.f1_score >= Decimal("0.75") else "✗",
    )

    table.add_section()

    # Wyckoff-specific metrics
    phase_acc_pct = float(metrics.phase_accuracy) * 100
    campaign_validity_pct = float(metrics.campaign_validity_rate) * 100

    table.add_row(
        "Phase Accuracy",
        f"{phase_acc_pct:.2f}%",
        "✓" if metrics.phase_accuracy >= Decimal("0.85") else "✗",
    )
    table.add_row(
        "Campaign Validity",
        f"{campaign_validity_pct:.2f}%",
        "✓" if metrics.campaign_validity_rate >= Decimal("0.90") else "✗",
    )

    table.add_section()

    # NFR Compliance
    nfr_target_pct = float(metrics.nfr_target) * 100
    table.add_row(
        "NFR Target",
        f"{nfr_target_pct:.0f}%",
        "",
    )
    table.add_row(
        "NFR Compliance",
        "PASS" if metrics.passes_nfr_target else "FAIL",
        "✓" if metrics.passes_nfr_target else "✗",
    )

    console.print(table)


def run_threshold_tuning(
    detector_name: str,
    dataset_version: str,
    min_threshold: float,
    max_threshold: float,
    step: float,
) -> None:
    """Run interactive threshold tuning."""
    console.print(
        Panel.fit(
            f"[bold]Threshold Tuning Mode[/bold]\n\n"
            f"Detector: {detector_name}\n"
            f"Range: {min_threshold:.2f} - {max_threshold:.2f}\n"
            f"Step: {step:.2f}",
            border_style="cyan",
        )
    )

    # Load dataset
    labeled_data = load_labeled_patterns(version=dataset_version)
    pattern_type = get_pattern_type_for_detector(detector_name)

    # Create simulated detector
    from src.backtesting.accuracy_tester import DetectedPattern, PatternDetector
    from src.models.ohlcv import OHLCVBar

    class SimulatedDetector(PatternDetector):
        """Simulated detector for threshold tuning."""

        def detect(self, bars: list[OHLCVBar], **kwargs) -> list[DetectedPattern]:
            return []

    detector = SimulatedDetector()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Tuning thresholds...", total=None)

        # Build threshold range
        threshold_range = range(
            int(min_threshold * 100), int(max_threshold * 100) + 1, int(step * 100)
        )

        threshold_results = tune_confidence_threshold(
            detector=detector,
            labeled_data=labeled_data,
            pattern_type=pattern_type,
            detector_name=detector_name,
            threshold_range=threshold_range,
        )

        progress.update(task, completed=True)

    # Display results
    table = Table(title="Threshold Tuning Results", show_header=True)
    table.add_column("Threshold", style="cyan", justify="right")
    table.add_column("Precision", style="green", justify="right")
    table.add_column("Recall", style="blue", justify="right")
    table.add_column("F1-Score", style="magenta", justify="right")
    table.add_column("Best", justify="center")

    # Find best threshold
    best_threshold = max(threshold_results.items(), key=lambda x: x[1])[0]

    for threshold, f1_score in sorted(threshold_results.items()):
        is_best = threshold == best_threshold
        table.add_row(
            f"{threshold:.2f}",
            "-",  # Would need to store precision/recall
            "-",
            f"{float(f1_score):.4f}",
            "⭐" if is_best else "",
        )

    console.print(table)
    console.print(
        f"\n[bold green]Optimal Threshold: {best_threshold:.2f} "
        f"(F1-Score: {float(threshold_results[best_threshold]):.4f})[/bold green]"
    )


def main() -> None:
    """Main CLI entry point."""
    args = parse_args()

    console.print(
        Panel.fit(
            "[bold cyan]Detector Accuracy Testing Tool[/bold cyan]\n"
            "Story 12.3 Task 11: Local Accuracy Testing CLI",
            border_style="cyan",
        )
    )

    # Handle threshold tuning mode
    if args.tune_threshold:
        if args.detector == "all":
            console.print("[yellow]Threshold tuning requires a specific detector[/yellow]")
            return

        run_threshold_tuning(
            detector_name=args.detector,
            dataset_version=args.dataset_version,
            min_threshold=args.threshold_min,
            max_threshold=args.threshold_max,
            step=args.threshold_step,
        )
        return

    # Determine detectors to test
    detectors = (
        ["SpringDetector", "SOSDetector", "UTADDetector", "LPSDetector"]
        if args.detector == "all"
        else [args.detector]
    )

    # Test each detector
    results = {}
    for detector_name in detectors:
        result = test_detector(
            detector_name=detector_name,
            threshold=Decimal(str(args.threshold)),
            dataset_version=args.dataset_version,
        )

        if "error" in result:
            console.print(f"[red]Error testing {detector_name}: {result['error']}[/red]")
            continue

        results[detector_name] = result

        # Display metrics
        display_metrics(detector_name, result["metrics"])

        # Compare with baseline if requested
        if args.compare_baseline:
            baselines_dir = Path("tests/datasets/baselines")
            baseline = load_baseline(detector_name, baselines_dir)

            if baseline:
                regression = detect_regression(result["metrics"], baseline)
                if regression:
                    console.print(
                        f"\n[bold red]⚠️ REGRESSION DETECTED for {detector_name}[/bold red]"
                    )
                    console.print(
                        f"Current F1: {result['metrics'].f1_score:.4f} vs "
                        f"Baseline F1: {baseline.f1_score:.4f}"
                    )
                else:
                    console.print(f"\n[bold green]✓ No regression for {detector_name}[/bold green]")
            else:
                console.print(f"\n[yellow]No baseline found for {detector_name}[/yellow]")

        # Save baseline if requested
        if args.save_baseline:
            baselines_dir = Path("tests/datasets/baselines")
            save_baseline(result["metrics"], detector_name, baselines_dir)
            console.print(f"\n[bold green]✓ Baseline saved for {detector_name}[/bold green]")

        # Generate HTML report if requested
        if args.generate_report:
            output_dir = Path(args.output_dir)
            output_file = output_dir / f"accuracy_{detector_name}.html"

            report_gen = AccuracyReportGenerator()
            report_gen.generate_html_report(
                metrics=result["metrics"],
                output_path=output_file,
                false_positives=result["false_positives"],
                false_negatives=result["false_negatives"],
            )

            console.print(f"\n[bold green]✓ HTML report saved: {output_file}[/bold green]")

    # Final summary
    console.print("\n" + "=" * 80)
    console.print("[bold]Summary[/bold]")
    console.print("=" * 80)

    for detector_name, result in results.items():
        if "metrics" in result:
            metrics = result["metrics"]
            status = "✓ PASS" if metrics.passes_nfr_target else "✗ FAIL"
            console.print(f"{detector_name:20} | F1: {metrics.f1_score:.4f} | NFR: {status}")


if __name__ == "__main__":
    main()
