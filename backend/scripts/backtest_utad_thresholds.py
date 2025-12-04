"""
Threshold Sweep Backtester for UTAD Volume Thresholds (Story 9.1)

This script performs threshold sweep analysis to find optimal volume thresholds
for UTAD patterns, maximizing F1 score (precision × recall).

Usage:
    python backtest_utad_thresholds.py --dataset dataset.csv --output results.csv
    python backtest_utad_thresholds.py --dataset dataset.csv --session OVERLAP --output overlap_results.csv
"""

import argparse
from decimal import Decimal
from pathlib import Path
from typing import Optional

import pandas as pd


def load_backtest_dataset(csv_path: Path) -> pd.DataFrame:
    """
    Load backtest dataset from CSV.

    Args:
        csv_path: Path to CSV file created by build_utad_backtest_dataset.py

    Returns:
        DataFrame with pattern data and outcomes
    """
    df = pd.read_csv(csv_path)

    # Validate required columns
    required_cols = ["pattern_id", "symbol", "volume_ratio", "session", "outcome"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Dataset missing required columns: {missing_cols}")

    print(f"Loaded {len(df)} patterns from {csv_path}")
    print(f"  VALID: {(df['outcome'] == 'VALID').sum()}")
    print(f"  FALSE: {(df['outcome'] == 'FALSE').sum()}")
    print(f"  NEUTRAL: {(df['outcome'] == 'NEUTRAL').sum()}")

    return df


def run_threshold_sweep(
    df: pd.DataFrame,
    thresholds: list[Decimal],
    session_filter: Optional[str] = None,
) -> pd.DataFrame:
    """
    Run threshold sweep analysis across multiple threshold values.

    Args:
        df: DataFrame with pattern data
        thresholds: List of threshold values to test (e.g., [1.8, 2.0, 2.2, 2.5])
        session_filter: Optional session to filter by (e.g., "OVERLAP")

    Returns:
        DataFrame with sweep results
    """
    if session_filter:
        df = df[df["session"] == session_filter].copy()
        print(f"\nFiltered to {len(df)} patterns for session: {session_filter}")

    results = []

    for threshold in thresholds:
        # Patterns that would pass this threshold
        passed = df[df["volume_ratio"] >= float(threshold)]

        # Calculate confusion matrix components
        true_positives = len(passed[passed["outcome"] == "VALID"])
        false_positives = len(passed[passed["outcome"] == "FALSE"])
        false_negatives = len(
            df[(df["volume_ratio"] < float(threshold)) & (df["outcome"] == "VALID")]
        )
        true_negatives = len(
            df[(df["volume_ratio"] < float(threshold)) & (df["outcome"] == "FALSE")]
        )

        # Calculate metrics
        total_passed = len(passed)
        precision = (
            true_positives / (true_positives + false_positives)
            if (true_positives + false_positives) > 0
            else 0.0
        )
        recall = (
            true_positives / (true_positives + false_negatives)
            if (true_positives + false_negatives) > 0
            else 0.0
        )
        f1_score = (
            2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        )

        # Pass rate
        pass_rate = total_passed / len(df) if len(df) > 0 else 0.0

        results.append(
            {
                "threshold": float(threshold),
                "patterns_passed": total_passed,
                "pass_rate": pass_rate,
                "true_positives": true_positives,
                "false_positives": false_positives,
                "false_negatives": false_negatives,
                "true_negatives": true_negatives,
                "precision": precision,
                "recall": recall,
                "f1_score": f1_score,
            }
        )

    results_df = pd.DataFrame(results)
    return results_df


def find_optimal_threshold(sweep_results: pd.DataFrame) -> Decimal:
    """
    Find optimal threshold with highest F1 score.

    Args:
        sweep_results: DataFrame from run_threshold_sweep()

    Returns:
        Optimal threshold value
    """
    if sweep_results.empty:
        return Decimal("2.5")  # Default to baseline

    # Find row with highest F1 score
    max_f1_idx = sweep_results["f1_score"].idxmax()
    optimal_row = sweep_results.loc[max_f1_idx]

    # If multiple thresholds tie, we already have the first one (most conservative)
    return Decimal(str(optimal_row["threshold"]))


def plot_threshold_curves(
    sweep_results: pd.DataFrame,
    output_path: Path,
    session: Optional[str] = None,
) -> None:
    """
    Create matplotlib chart showing precision/recall/F1 curves.

    Args:
        sweep_results: DataFrame from run_threshold_sweep()
        output_path: Path to save PNG chart
        session: Optional session name for title
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("Warning: matplotlib not installed, skipping chart generation")
        return

    # Create output directory
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Create plot
    fig, ax = plt.subplots(figsize=(12, 6))

    # Plot curves
    ax.plot(
        sweep_results["threshold"],
        sweep_results["precision"],
        marker="o",
        label="Precision",
        linewidth=2,
    )
    ax.plot(
        sweep_results["threshold"],
        sweep_results["recall"],
        marker="s",
        label="Recall",
        linewidth=2,
    )
    ax.plot(
        sweep_results["threshold"],
        sweep_results["f1_score"],
        marker="^",
        label="F1 Score",
        linewidth=2,
        color="green",
    )

    # Find optimal threshold
    optimal_threshold = find_optimal_threshold(sweep_results)
    optimal_f1 = sweep_results[sweep_results["threshold"] == float(optimal_threshold)][
        "f1_score"
    ].values[0]

    # Mark optimal threshold
    ax.axvline(
        x=float(optimal_threshold),
        color="red",
        linestyle="--",
        alpha=0.7,
        label=f"Optimal: {optimal_threshold} (F1={optimal_f1:.3f})",
    )

    # Formatting
    ax.set_xlabel("Volume Threshold (multiple of average)", fontsize=12)
    ax.set_ylabel("Score", fontsize=12)
    title = "UTAD Threshold Optimization"
    if session:
        title += f" - {session} Session"
    ax.set_title(title, fontsize=14, fontweight="bold")
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    ax.set_ylim([0, 1])

    # Save
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    print(f"\n✓ Saved chart to {output_path}")
    plt.close()


def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="Backtest UTAD volume thresholds to find optimal values"
    )
    parser.add_argument(
        "--dataset",
        type=str,
        required=True,
        help="Path to backtest dataset CSV (from build_utad_backtest_dataset.py)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="docs/analysis/utad_threshold_sweep_results.csv",
        help="Output CSV file path for results",
    )
    parser.add_argument(
        "--session",
        type=str,
        default=None,
        choices=["OVERLAP", "LONDON", "NY", "ASIAN"],
        help="Filter to specific forex session (optional)",
    )
    parser.add_argument(
        "--min-threshold",
        type=float,
        default=1.8,
        help="Minimum threshold to test (default: 1.8 = 180%%)",
    )
    parser.add_argument(
        "--max-threshold",
        type=float,
        default=2.8,
        help="Maximum threshold to test (default: 2.8 = 280%%)",
    )
    parser.add_argument(
        "--step",
        type=float,
        default=0.1,
        help="Threshold increment step (default: 0.1)",
    )
    parser.add_argument(
        "--no-chart",
        action="store_true",
        help="Skip chart generation",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("UTAD Threshold Sweep Backtester (Story 9.1)")
    print("=" * 60)

    # Load dataset
    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        print(f"Error: Dataset not found at {dataset_path}")
        print("Run build_utad_backtest_dataset.py first to create the dataset.")
        return

    df = load_backtest_dataset(dataset_path)

    # Generate threshold range
    thresholds = []
    current = Decimal(str(args.min_threshold))
    max_threshold = Decimal(str(args.max_threshold))
    step = Decimal(str(args.step))

    while current <= max_threshold:
        thresholds.append(current)
        current += step

    print(
        f"\nTesting {len(thresholds)} thresholds from {args.min_threshold} to {args.max_threshold}"
    )
    if args.session:
        print(f"Session filter: {args.session}")

    # Run threshold sweep
    print("\nRunning threshold sweep...")
    sweep_results = run_threshold_sweep(df, thresholds, args.session)

    # Find optimal threshold
    optimal_threshold = find_optimal_threshold(sweep_results)
    optimal_row = sweep_results[sweep_results["threshold"] == float(optimal_threshold)]

    print("\n" + "=" * 60)
    print("OPTIMAL THRESHOLD FOUND")
    print("=" * 60)
    print(f"Threshold: {optimal_threshold} ({float(optimal_threshold) * 100:.0f}%)")
    print(f"F1 Score: {optimal_row['f1_score'].values[0]:.4f}")
    print(f"Precision: {optimal_row['precision'].values[0]:.4f}")
    print(f"Recall: {optimal_row['recall'].values[0]:.4f}")
    print(f"Pass Rate: {optimal_row['pass_rate'].values[0]:.2%}")
    print(f"Patterns Passed: {optimal_row['patterns_passed'].values[0]}")

    # Save results
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sweep_results.to_csv(output_path, index=False)
    print(f"\n✓ Saved sweep results to {output_path}")

    # Generate chart
    if not args.no_chart:
        chart_path = output_path.parent / output_path.stem.replace("_results", "_curves")
        chart_path = chart_path.with_suffix(".png")
        plot_threshold_curves(sweep_results, chart_path, args.session)

    # Print top 5 thresholds by F1 score
    print("\nTop 5 Thresholds by F1 Score:")
    print(
        sweep_results.nlargest(5, "f1_score")[
            ["threshold", "f1_score", "precision", "recall", "pass_rate"]
        ].to_string(index=False)
    )

    print("\n" + "=" * 60)
    print("Backtest complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
