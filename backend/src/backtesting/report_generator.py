"""
Accuracy Report Generator (Story 12.3 Task 8)

Purpose:
--------
Generates professional HTML reports for detector accuracy testing results.
Displays precision, recall, F1-score, confusion matrix, Wyckoff-specific metrics,
and threshold tuning charts.

Features:
---------
- Jinja2-based HTML templating
- Confusion matrix visualization with color coding
- False positive/negative examples
- NFR compliance badges
- Threshold tuning charts (matplotlib)
- Professional CSS styling

Usage:
------
    from backtesting.report_generator import AccuracyReportGenerator

    generator = AccuracyReportGenerator()
    generator.generate_html_report(
        metrics=accuracy_metrics,
        output_path="backend/tests/reports/spring_detector_20241220.html",
        false_positives=fp_cases,
        false_negatives=fn_cases
    )

Author: Story 12.3 Task 8
"""

from __future__ import annotations

import base64
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

import structlog
from jinja2 import Environment, FileSystemLoader

from src.backtesting.accuracy_tester import FalseNegativeCase, FalsePositiveCase
from src.models.backtest import AccuracyMetrics

logger = structlog.get_logger(__name__)


class AccuracyReportGenerator:
    """
    Generates HTML reports for detector accuracy testing (Story 12.3 Task 8.1).

    Creates professional, styled HTML reports with:
    - Summary metrics (precision, recall, F1-score)
    - Confusion matrix visualization
    - Wyckoff-specific metrics
    - False positive/negative examples
    - NFR compliance badges
    - Threshold tuning charts (if available)
    """

    def __init__(self):
        """Initialize report generator with Jinja2 environment."""
        self.logger = logger.bind(component="report_generator")

        # Set up Jinja2 environment
        templates_dir = Path(__file__).parent / "templates"
        templates_dir.mkdir(exist_ok=True)

        self.jinja_env = Environment(loader=FileSystemLoader(str(templates_dir)), autoescape=True)

        # Register custom filters
        self.jinja_env.filters["percentage"] = self._format_percentage
        self.jinja_env.filters["decimal"] = self._format_decimal

    def generate_html_report(
        self,
        metrics: AccuracyMetrics,
        output_path: str | Path,
        false_positives: list[FalsePositiveCase] | None = None,
        false_negatives: list[FalseNegativeCase] | None = None,
        threshold_tuning_data: dict[int, Any] | None = None,
    ) -> None:
        """
        Generate HTML report for accuracy metrics (Task 8.1).

        Args:
            metrics: AccuracyMetrics to report
            output_path: Where to save HTML file
            false_positives: List of FP cases for detailed analysis
            false_negatives: List of FN cases for detailed analysis
            threshold_tuning_data: Threshold tuning results for chart

        Example:
            >>> generator = AccuracyReportGenerator()
            >>> generator.generate_html_report(
            ...     metrics=spring_metrics,
            ...     output_path="tests/reports/spring_detector.html",
            ...     false_positives=fp_list[:10],
            ...     false_negatives=fn_list[:10]
            ... )
        """
        self.logger.info(
            "generating_html_report",
            detector=metrics.detector_name,
            output_path=str(output_path),
        )

        # Prepare template context
        context = self._prepare_context(
            metrics=metrics,
            false_positives=false_positives or [],
            false_negatives=false_negatives or [],
            threshold_tuning_data=threshold_tuning_data,
        )

        # Render template
        template = self.jinja_env.get_template("accuracy_report.html")
        html_content = template.render(**context)

        # Write to file
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html_content)

        self.logger.info(
            "html_report_generated",
            detector=metrics.detector_name,
            output_file=str(output_file),
            file_size_kb=output_file.stat().st_size / 1024,
        )

    def _prepare_context(
        self,
        metrics: AccuracyMetrics,
        false_positives: list[FalsePositiveCase],
        false_negatives: list[FalseNegativeCase],
        threshold_tuning_data: dict[int, Any] | None,
    ) -> dict[str, Any]:
        """Prepare Jinja2 template context with all report data."""
        # Get confusion matrix chart as base64
        confusion_chart = self._generate_confusion_matrix_chart(metrics)

        # Get threshold tuning chart if data available
        threshold_chart = None
        if threshold_tuning_data:
            threshold_chart = self._generate_threshold_chart(threshold_tuning_data)

        return {
            "metrics": metrics,
            "detector_name": metrics.detector_name,
            "detector_version": metrics.detector_version,
            "test_date": metrics.test_timestamp.strftime("%Y-%m-%d %H:%M UTC"),
            "dataset_version": metrics.dataset_version,
            "passes_nfr": metrics.passes_nfr_target,
            "nfr_badge_class": "badge-pass" if metrics.passes_nfr_target else "badge-fail",
            "nfr_badge_text": "PASS" if metrics.passes_nfr_target else "FAIL",
            # Core metrics
            "precision_pct": float(metrics.precision * 100),
            "recall_pct": float(metrics.recall * 100),
            "f1_score_pct": float(metrics.f1_score * 100),
            "accuracy_pct": float(metrics.accuracy * 100),
            # Confusion matrix
            "tp": metrics.true_positives,
            "fp": metrics.false_positives,
            "tn": metrics.true_negatives,
            "fn": metrics.false_negatives,
            "confusion_chart_base64": confusion_chart,
            # Wyckoff metrics
            "phase_accuracy_pct": float(metrics.phase_accuracy * 100),
            "campaign_validity_pct": float(metrics.campaign_validity_rate * 100),
            "sequential_logic_pct": float(metrics.sequential_logic_score * 100),
            "confirmation_rate_pct": float(metrics.confirmation_rate * 100),
            "phase_breakdown": metrics.phase_breakdown,
            "campaign_breakdown": metrics.campaign_type_breakdown,
            # FP/FN analysis
            "false_positives": false_positives[:10],  # Top 10
            "false_negatives": false_negatives[:10],  # Top 10
            "total_fp_count": len(false_positives),
            "total_fn_count": len(false_negatives),
            # Charts
            "threshold_chart_base64": threshold_chart,
            "has_threshold_chart": threshold_chart is not None,
            # Metadata
            "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        }

    def _generate_confusion_matrix_chart(self, metrics: AccuracyMetrics) -> str:
        """
        Generate confusion matrix heatmap as base64 image (Task 8.3).

        Returns:
            Base64-encoded PNG image string
        """
        try:
            import matplotlib.pyplot as plt
            import numpy as np

            # Create confusion matrix array
            cm = np.array(
                [
                    [metrics.true_positives, metrics.false_positives],
                    [metrics.false_negatives, metrics.true_negatives],
                ]
            )

            # Create figure
            fig, ax = plt.subplots(figsize=(6, 5))

            # Plot heatmap
            im = ax.imshow(cm, cmap="Blues", aspect="auto")

            # Labels
            ax.set_xticks([0, 1])
            ax.set_yticks([0, 1])
            ax.set_xticklabels(["Predicted Positive", "Predicted Negative"])
            ax.set_yticklabels(["Actual Positive", "Actual Negative"])

            # Annotate cells with values
            for i in range(2):
                for j in range(2):
                    text = ax.text(
                        j, i, str(cm[i, j]), ha="center", va="center", color="black", fontsize=20
                    )

            ax.set_title("Confusion Matrix", fontsize=14, fontweight="bold")
            plt.tight_layout()

            # Convert to base64
            buffer = BytesIO()
            plt.savefig(buffer, format="png", dpi=100, bbox_inches="tight")
            buffer.seek(0)
            image_base64 = base64.b64encode(buffer.read()).decode("utf-8")
            plt.close(fig)

            return image_base64

        except ImportError:
            self.logger.warning("matplotlib_not_available", feature="confusion_matrix_chart")
            return ""

    def _generate_threshold_chart(self, threshold_data: dict[int, Any]) -> str:
        """
        Generate threshold tuning chart as base64 image (Task 8.3).

        Args:
            threshold_data: Dict mapping threshold (int) to F1-score (Decimal)

        Returns:
            Base64-encoded PNG image string
        """
        try:
            import matplotlib.pyplot as plt

            # Extract data
            thresholds = sorted(threshold_data.keys())
            f1_scores = [float(threshold_data[t]) * 100 for t in thresholds]

            # Create figure
            fig, ax = plt.subplots(figsize=(8, 5))

            # Plot line chart
            ax.plot(thresholds, f1_scores, marker="o", linewidth=2, markersize=8, color="#2563eb")

            # Highlight optimal threshold
            max_f1_idx = f1_scores.index(max(f1_scores))
            optimal_threshold = thresholds[max_f1_idx]
            ax.plot(
                optimal_threshold,
                f1_scores[max_f1_idx],
                marker="*",
                markersize=20,
                color="red",
                label=f"Optimal: {optimal_threshold}%",
            )

            ax.set_xlabel("Confidence Threshold (%)", fontsize=12)
            ax.set_ylabel("F1-Score (%)", fontsize=12)
            ax.set_title("Threshold Tuning: F1-Score vs Confidence Threshold", fontsize=14)
            ax.grid(True, alpha=0.3)
            ax.legend()

            plt.tight_layout()

            # Convert to base64
            buffer = BytesIO()
            plt.savefig(buffer, format="png", dpi=100, bbox_inches="tight")
            buffer.seek(0)
            image_base64 = base64.b64encode(buffer.read()).decode("utf-8")
            plt.close(fig)

            return image_base64

        except ImportError:
            self.logger.warning("matplotlib_not_available", feature="threshold_chart")
            return ""

    @staticmethod
    def _format_percentage(value: float) -> str:
        """Format decimal as percentage (Jinja2 filter)."""
        return f"{value:.2f}%"

    @staticmethod
    def _format_decimal(value: float, places: int = 4) -> str:
        """Format decimal value (Jinja2 filter)."""
        return f"{value:.{places}f}"
