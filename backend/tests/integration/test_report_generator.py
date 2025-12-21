"""
Integration Tests for HTML Report Generation (Story 12.3 Task 8)

Tests end-to-end report generation with template rendering and chart generation.

Author: Story 12.3 QA Fix
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from src.backtesting.accuracy_tester import FalseNegativeCase, FalsePositiveCase
from src.backtesting.report_generator import AccuracyReportGenerator
from src.models.backtest import AccuracyMetrics, LabeledPattern


@pytest.fixture
def sample_metrics():
    """Sample accuracy metrics for report generation."""
    return AccuracyMetrics(
        detector_name="SpringDetector",
        detector_version="1.0",
        pattern_type="SPRING",
        dataset_version="v1",
        total_samples=100,
        true_positives=75,
        false_positives=10,
        true_negatives=5,
        false_negatives=10,
        precision=Decimal("0.8824"),
        recall=Decimal("0.8824"),
        f1_score=Decimal("0.8824"),
        phase_accuracy=Decimal("0.90"),
        campaign_validity_rate=Decimal("0.92"),
        sequential_logic_score=Decimal("0.85"),
        confirmation_rate=Decimal("0.88"),
        false_phase_rate=Decimal("0.10"),
        phase_breakdown={
            "C": {"TP": 65, "FP": 5},
            "D": {"TP": 10, "FP": 5},
        },
        campaign_type_breakdown={
            "ACCUMULATION": {"TP": 70, "FP": 8},
            "DISTRIBUTION": {"TP": 5, "FP": 2},
        },
        confusion_matrix={"TP": 75, "FP": 10, "TN": 5, "FN": 10},
        threshold_used=Decimal("0.70"),
        passes_nfr_target=True,
        nfr_target=Decimal("0.75"),
        metadata={"detector_type": "PATTERN"},
    )


@pytest.fixture
def sample_false_positives():
    """Sample false positive cases."""
    return [
        FalsePositiveCase(
            labeled_pattern=LabeledPattern(
                id=str(uuid4()),
                symbol="AAPL",
                date=datetime(2024, 1, 15, tzinfo=UTC),
                pattern_type="SPRING",
                confidence=82,
                correctness=False,
                outcome_win=False,
                phase="A",
                trading_range_id="TR_001",
                entry_price=Decimal("150.00"),
                stop_loss=Decimal("148.00"),
                target_price=Decimal("155.00"),
                volume_ratio=Decimal("0.65"),
                spread_ratio=Decimal("0.80"),
                justification="False Spring - wrong phase",
                reviewer_verified=True,
                campaign_id=str(uuid4()),
                campaign_type="ACCUMULATION",
                campaign_phase="A",
                phase_position="early Phase A",
                volume_characteristics={"type": "normal"},
                spread_characteristics={"type": "normal"},
                sr_test_result="support broken",
                preliminary_events=[],
                subsequent_confirmation=False,
                sequential_validity=False,
                false_positive_reason="Pattern in Phase A instead of Phase C",
            ),
            detected_confidence=82,
            reason="Pattern detected in wrong phase (A instead of C)",
        )
        for _ in range(5)
    ]


@pytest.fixture
def sample_false_negatives():
    """Sample false negative cases."""
    return [
        FalseNegativeCase(
            labeled_pattern=LabeledPattern(
                id=str(uuid4()),
                symbol="AAPL",
                date=datetime(2024, 1, 15, tzinfo=UTC),
                pattern_type="SPRING",
                confidence=72,
                correctness=True,
                outcome_win=True,
                phase="C",
                trading_range_id="TR_002",
                entry_price=Decimal("150.00"),
                stop_loss=Decimal("148.00"),
                target_price=Decimal("155.00"),
                volume_ratio=Decimal("0.65"),
                spread_ratio=Decimal("0.80"),
                justification="Valid Spring but low confidence",
                reviewer_verified=True,
                campaign_id=str(uuid4()),
                campaign_type="ACCUMULATION",
                campaign_phase="C",
                phase_position="mid Phase C",
                volume_characteristics={"type": "diminishing"},
                spread_characteristics={"type": "narrowing"},
                sr_test_result="support held",
                preliminary_events=["PS", "SC"],
                subsequent_confirmation=True,
                sequential_validity=True,
                false_positive_reason=None,
            ),
            reason="Confidence 72% below 75% threshold",
        )
        for _ in range(5)
    ]


def test_generate_html_report_basic(sample_metrics, tmp_path):
    """Test basic HTML report generation without FP/FN or threshold tuning."""
    generator = AccuracyReportGenerator()
    output_file = tmp_path / "basic_report.html"

    generator.generate_html_report(
        metrics=sample_metrics,
        output_path=output_file,
    )

    # Verify file created
    assert output_file.exists()

    # Verify file has content
    content = output_file.read_text(encoding="utf-8")
    assert len(content) > 1000  # Should be substantial HTML

    # Verify key sections present
    assert "SpringDetector v1.0" in content
    assert "Detector Accuracy Report" in content
    assert "Summary Metrics" in content
    assert "Confusion Matrix" in content
    assert "Wyckoff Methodology Metrics" in content

    # Verify metrics rendered
    assert "88.24%" in content  # Precision/Recall/F1
    assert "NFR Compliance" in content


def test_generate_html_report_with_fp_fn(
    sample_metrics, sample_false_positives, sample_false_negatives, tmp_path
):
    """Test HTML report generation with false positive/negative analysis."""
    generator = AccuracyReportGenerator()
    output_file = tmp_path / "report_with_errors.html"

    generator.generate_html_report(
        metrics=sample_metrics,
        output_path=output_file,
        false_positives=sample_false_positives,
        false_negatives=sample_false_negatives,
    )

    assert output_file.exists()
    content = output_file.read_text(encoding="utf-8")

    # Verify error analysis section
    assert "Error Analysis" in content
    assert "False Positives" in content
    assert "False Negatives" in content

    # Verify FP/FN details rendered
    assert "Pattern detected in wrong phase" in content or "wrong phase" in content
    assert "Confidence" in content


def test_generate_html_report_with_charts(sample_metrics, tmp_path):
    """Test HTML report generation with confusion matrix chart."""
    generator = AccuracyReportGenerator()
    output_file = tmp_path / "report_with_charts.html"

    generator.generate_html_report(
        metrics=sample_metrics,
        output_path=output_file,
    )

    assert output_file.exists()
    content = output_file.read_text(encoding="utf-8")

    # Verify chart embedded as base64
    assert "data:image/png;base64," in content
    assert "<img src=" in content


def test_generate_html_report_with_threshold_tuning(sample_metrics, tmp_path):
    """Test HTML report generation with threshold tuning data."""
    generator = AccuracyReportGenerator()
    output_file = tmp_path / "report_with_tuning.html"

    threshold_tuning_data = {
        70: Decimal("0.8500"),
        75: Decimal("0.8824"),
        80: Decimal("0.8700"),
        85: Decimal("0.8400"),
    }

    generator.generate_html_report(
        metrics=sample_metrics,
        output_path=output_file,
        threshold_tuning_data=threshold_tuning_data,
    )

    assert output_file.exists()
    content = output_file.read_text(encoding="utf-8")

    # Verify threshold tuning section
    assert "Threshold Tuning" in content or "threshold" in content.lower()


def test_generate_html_report_nfr_pass_badge(sample_metrics, tmp_path):
    """Test NFR PASS badge rendering."""
    generator = AccuracyReportGenerator()
    output_file = tmp_path / "report_nfr_pass.html"

    sample_metrics.passes_nfr_target = True

    generator.generate_html_report(
        metrics=sample_metrics,
        output_path=output_file,
    )

    content = output_file.read_text(encoding="utf-8")

    # Verify PASS badge
    assert "badge-pass" in content or "PASS" in content


def test_generate_html_report_nfr_fail_badge(sample_metrics, tmp_path):
    """Test NFR FAIL badge rendering."""
    generator = AccuracyReportGenerator()
    output_file = tmp_path / "report_nfr_fail.html"

    sample_metrics.passes_nfr_target = False
    sample_metrics.precision = Decimal("0.70")  # Below 75% target

    generator.generate_html_report(
        metrics=sample_metrics,
        output_path=output_file,
    )

    content = output_file.read_text(encoding="utf-8")

    # Verify FAIL badge
    assert "badge-fail" in content or "FAIL" in content


def test_report_creates_parent_directories(sample_metrics, tmp_path):
    """Test that report generation creates parent directories if needed."""
    generator = AccuracyReportGenerator()
    nested_path = tmp_path / "reports" / "accuracy" / "spring.html"

    generator.generate_html_report(
        metrics=sample_metrics,
        output_path=nested_path,
    )

    assert nested_path.exists()
    assert nested_path.parent.exists()


def test_report_phase_breakdown_rendering(sample_metrics, tmp_path):
    """Test phase breakdown table rendering."""
    generator = AccuracyReportGenerator()
    output_file = tmp_path / "report_phase_breakdown.html"

    generator.generate_html_report(
        metrics=sample_metrics,
        output_path=output_file,
    )

    content = output_file.read_text(encoding="utf-8")

    # Verify phase breakdown table
    assert "Phase Breakdown" in content
    assert "Phase C" in content or "Phase D" in content


def test_report_wyckoff_metrics_thresholds(sample_metrics, tmp_path):
    """Test Wyckoff metrics with threshold indicators."""
    generator = AccuracyReportGenerator()
    output_file = tmp_path / "report_wyckoff.html"

    # Set metrics to trigger different color coding
    sample_metrics.phase_accuracy = Decimal("0.90")  # Good (≥85%)
    sample_metrics.campaign_validity_rate = Decimal("0.92")  # Good (≥90%)

    generator.generate_html_report(
        metrics=sample_metrics,
        output_path=output_file,
    )

    content = output_file.read_text(encoding="utf-8")

    # Verify Wyckoff metrics section
    assert "Phase Accuracy" in content
    assert "Campaign Validity" in content
    assert "90.00%" in content  # Phase accuracy
    assert "92.00%" in content  # Campaign validity
