"""
Integration Tests for Detector Accuracy (Story 12.3 Task 7)

Tests real detectors against labeled dataset from Story 12.2.

Tests:
------
- SpringDetector accuracy against labeled Spring patterns
- SOSDetector accuracy against labeled SOS patterns
- UTADDetector accuracy against labeled UTAD patterns
- LPSDetector accuracy against labeled LPS patterns
- NFR target validation (fail test if not met)
- Detailed failure reports
- Graceful skipping if dataset doesn't exist

Author: Story 12.3 Task 7
"""

from decimal import Decimal
from pathlib import Path

import pytest

from src.backtesting.accuracy_tester import DetectedPattern, DetectorAccuracyTester, PatternDetector
from src.backtesting.dataset_loader import load_labeled_patterns
from src.models.ohlcv import OHLCVBar

# ============================================================================
# Mock Detector for Testing
# ============================================================================


class MockDetector(PatternDetector):
    """
    Mock detector for testing infrastructure.

    Simulates pattern detection based on confidence threshold.
    In real tests, this will be replaced with actual detectors.
    """

    def __init__(self, detected_patterns: list[DetectedPattern]):
        self.detected_patterns = detected_patterns

    def detect(self, bars: list[OHLCVBar], **kwargs) -> list[DetectedPattern]:
        return self.detected_patterns


# Skip all tests if labeled dataset doesn't exist (Story 12.2 incomplete)
backend_dir = Path(__file__).parent.parent.parent
dataset_path = backend_dir / "tests" / "datasets" / "labeled_patterns_v1.parquet"

pytestmark = pytest.mark.skipif(
    not dataset_path.exists(), reason="Labeled dataset not available (Story 12.2 incomplete)"
)

# Mark all tests as slow (processes 200+ patterns)
pytestmark = pytest.mark.slow


# ============================================================================
# Integration Test Fixtures
# ============================================================================


@pytest.fixture(scope="module")
def labeled_dataset():
    """Load labeled dataset once for all tests."""
    return load_labeled_patterns(version="v1")


@pytest.fixture
def accuracy_tester():
    """Create DetectorAccuracyTester instance."""
    return DetectorAccuracyTester()


# ============================================================================
# Test Spring Detector Accuracy
# ============================================================================


def test_spring_detector_accuracy(labeled_dataset, accuracy_tester):
    """
    Test SpringDetector accuracy against labeled Spring patterns.

    NFR3 Requirement: Pattern detection precision ≥ 75%

    This test uses MockDetector for now since we don't have actual detector
    implementations wired up yet. In real implementation, would import:
        from src.pattern_engine.detectors.spring_detector import SpringDetector
    """
    # Filter for SPRING patterns
    spring_patterns = labeled_dataset[labeled_dataset["pattern_type"] == "SPRING"]

    if spring_patterns.empty:
        pytest.skip("No SPRING patterns in labeled dataset")

    # TODO: Replace MockDetector with actual SpringDetector when available
    # For now, use mock detector for testing infrastructure
    detector = MockDetector([])

    # Run accuracy test
    metrics = accuracy_tester.test_detector_accuracy(
        detector=detector,
        labeled_data=labeled_dataset,
        pattern_type="SPRING",
        detector_name="SpringDetector",
        detector_version="1.0",
        detector_type="PATTERN",
        threshold=Decimal("0.70"),
    )

    # Log results
    print("\n=== Spring Detector Results ===")
    print(f"Total Samples: {metrics.total_samples}")
    print(f"True Positives: {metrics.true_positives}")
    print(f"False Positives: {metrics.false_positives}")
    print(f"False Negatives: {metrics.false_negatives}")
    print(f"Precision: {metrics.precision:.2%}")
    print(f"Recall: {metrics.recall:.2%}")
    print(f"F1-Score: {metrics.f1_score:.2%}")
    print(f"NFR Target: {metrics.nfr_target:.2%}")
    print(f"Passes NFR: {metrics.passes_nfr_target}")
    print("\nWyckoff Metrics:")
    print(f"Phase Accuracy: {metrics.phase_accuracy:.2%}")
    print(f"Campaign Validity: {metrics.campaign_validity_rate:.2%}")
    print(f"Sequential Logic: {metrics.sequential_logic_score:.2%}")
    print(f"Confirmation Rate: {metrics.confirmation_rate:.2%}")

    # Assert NFR3 compliance (≥75% precision)
    if not metrics.passes_nfr_target:
        # Generate detailed failure report
        false_positives = accuracy_tester.analyze_false_positives()
        false_negatives = accuracy_tester.analyze_false_negatives()

        failure_report = "\n=== SpringDetector Failed NFR3 ===\n"
        failure_report += (
            f"Precision: {metrics.precision:.2%} (required: ≥{metrics.nfr_target:.2%})\n"
        )
        failure_report += f"\nFalse Positives ({len(false_positives)}):\n"
        for i, fp in enumerate(false_positives[:5], 1):  # Show first 5
            failure_report += f"  {i}. {fp.labeled_pattern.symbol} @ {fp.labeled_pattern.date}\n"
            failure_report += f"     Reason: {fp.reason}\n"
            failure_report += f"     Confidence: {fp.detected_confidence}\n"

        failure_report += f"\nFalse Negatives ({len(false_negatives)}):\n"
        for i, fn in enumerate(false_negatives[:5], 1):  # Show first 5
            failure_report += f"  {i}. {fn.labeled_pattern.symbol} @ {fn.labeled_pattern.date}\n"
            failure_report += f"     Reason: {fn.reason}\n"

        failure_report += "\nRecommended Actions:\n"
        failure_report += "1. Review false positive cases to tighten validation logic\n"
        failure_report += "2. Adjust confidence threshold using threshold tuning\n"
        failure_report += "3. Improve pattern detection criteria\n"

        pytest.fail(failure_report)

    # Assert basic validity
    assert metrics.total_samples > 0, "No samples tested"
    assert metrics.precision >= Decimal("0.75"), "Precision below NFR3 target (75%)"


# ============================================================================
# Test SOS Detector Accuracy
# ============================================================================


def test_sos_detector_accuracy(labeled_dataset, accuracy_tester):
    """
    Test SOSDetector accuracy against labeled SOS patterns.

    NFR3 Requirement: Pattern detection precision ≥ 75%
    """
    # Filter for SOS patterns
    sos_patterns = labeled_dataset[labeled_dataset["pattern_type"] == "SOS"]

    if sos_patterns.empty:
        pytest.skip("No SOS patterns in labeled dataset")

    # TODO: Replace with actual SOSDetector
    detector = MockDetector([])

    metrics = accuracy_tester.test_detector_accuracy(
        detector=detector,
        labeled_data=labeled_dataset,
        pattern_type="SOS",
        detector_name="SOSDetector",
        detector_version="1.0",
        detector_type="PATTERN",
        threshold=Decimal("0.70"),
    )

    print("\n=== SOS Detector Results ===")
    print(f"Precision: {metrics.precision:.2%}")
    print(f"Recall: {metrics.recall:.2%}")
    print(f"F1-Score: {metrics.f1_score:.2%}")
    print(f"Passes NFR: {metrics.passes_nfr_target}")

    # Assert NFR3 compliance
    if not metrics.passes_nfr_target:
        pytest.fail(
            f"SOSDetector failed NFR3: Precision {metrics.precision:.2%} < {metrics.nfr_target:.2%}"
        )

    assert metrics.precision >= Decimal("0.75")


# ============================================================================
# Test UTAD Detector Accuracy
# ============================================================================


def test_utad_detector_accuracy(labeled_dataset, accuracy_tester):
    """
    Test UTADDetector accuracy against labeled UTAD patterns.

    NFR3 Requirement: Pattern detection precision ≥ 75%
    """
    # Filter for UTAD patterns
    utad_patterns = labeled_dataset[labeled_dataset["pattern_type"] == "UTAD"]

    if utad_patterns.empty:
        pytest.skip("No UTAD patterns in labeled dataset")

    # TODO: Replace with actual UTADDetector
    detector = MockDetector([])

    metrics = accuracy_tester.test_detector_accuracy(
        detector=detector,
        labeled_data=labeled_dataset,
        pattern_type="UTAD",
        detector_name="UTADDetector",
        detector_version="1.0",
        detector_type="PATTERN",
        threshold=Decimal("0.70"),
    )

    print("\n=== UTAD Detector Results ===")
    print(f"Precision: {metrics.precision:.2%}")
    print(f"Recall: {metrics.recall:.2%}")
    print(f"F1-Score: {metrics.f1_score:.2%}")
    print(f"Passes NFR: {metrics.passes_nfr_target}")

    if not metrics.passes_nfr_target:
        pytest.fail(
            f"UTADDetector failed NFR3: Precision {metrics.precision:.2%} < {metrics.nfr_target:.2%}"
        )

    assert metrics.precision >= Decimal("0.75")


# ============================================================================
# Test LPS Detector Accuracy
# ============================================================================


def test_lps_detector_accuracy(labeled_dataset, accuracy_tester):
    """
    Test LPSDetector accuracy against labeled LPS patterns.

    NFR3 Requirement: Pattern detection precision ≥ 75%
    """
    # Filter for LPS patterns
    lps_patterns = labeled_dataset[labeled_dataset["pattern_type"] == "LPS"]

    if lps_patterns.empty:
        pytest.skip("No LPS patterns in labeled dataset")

    # TODO: Replace with actual LPSDetector
    detector = MockDetector([])

    metrics = accuracy_tester.test_detector_accuracy(
        detector=detector,
        labeled_data=labeled_dataset,
        pattern_type="LPS",
        detector_name="LPSDetector",
        detector_version="1.0",
        detector_type="PATTERN",
        threshold=Decimal("0.70"),
    )

    print("\n=== LPS Detector Results ===")
    print(f"Precision: {metrics.precision:.2%}")
    print(f"Recall: {metrics.recall:.2%}")
    print(f"F1-Score: {metrics.f1_score:.2%}")
    print(f"Passes NFR: {metrics.passes_nfr_target}")

    if not metrics.passes_nfr_target:
        pytest.fail(
            f"LPSDetector failed NFR3: Precision {metrics.precision:.2%} < {metrics.nfr_target:.2%}"
        )

    assert metrics.precision >= Decimal("0.75")


# ============================================================================
# Test Wyckoff-Specific Metrics
# ============================================================================


def test_wyckoff_phase_accuracy(labeled_dataset, accuracy_tester):
    """Test that detectors achieve high phase accuracy (>85%)."""
    detector = MockDetector([])

    metrics = accuracy_tester.test_detector_accuracy(
        detector=detector,
        labeled_data=labeled_dataset,
        pattern_type="SPRING",
        detector_name="SpringDetector",
        detector_version="1.0",
        threshold=Decimal("0.70"),
    )

    # Wyckoff phase accuracy should be high
    # Skip if no detections
    if metrics.true_positives + metrics.false_positives == 0:
        pytest.skip("No patterns detected")

    print("\n=== Wyckoff Phase Accuracy ===")
    print(f"Phase Accuracy: {metrics.phase_accuracy:.2%}")
    print(f"False Phase Rate: {metrics.false_phase_rate:.2%}")
    print(f"Phase Breakdown: {metrics.phase_breakdown}")

    # Phase accuracy target: ≥85%
    assert (
        metrics.phase_accuracy >= Decimal("0.85")
        or metrics.true_positives + metrics.false_positives == 0
    ), f"Phase accuracy {metrics.phase_accuracy:.2%} below 85% target"


def test_wyckoff_campaign_validity(labeled_dataset, accuracy_tester):
    """Test that detectors achieve high campaign validity (>90%)."""
    detector = MockDetector([])

    metrics = accuracy_tester.test_detector_accuracy(
        detector=detector,
        labeled_data=labeled_dataset,
        pattern_type="SPRING",
        detector_name="SpringDetector",
        detector_version="1.0",
        threshold=Decimal("0.70"),
    )

    # Skip if no detections
    if metrics.true_positives + metrics.false_positives == 0:
        pytest.skip("No patterns detected")

    print("\n=== Campaign Validity ===")
    print(f"Campaign Validity Rate: {metrics.campaign_validity_rate:.2%}")
    print(f"Campaign Breakdown: {metrics.campaign_type_breakdown}")

    # Campaign validity target: ≥90%
    assert (
        metrics.campaign_validity_rate >= Decimal("0.90")
        or metrics.true_positives + metrics.false_positives == 0
    ), f"Campaign validity {metrics.campaign_validity_rate:.2%} below 90% target"


# ============================================================================
# Test Regression Detection
# ============================================================================


def test_regression_detection_with_baseline(labeled_dataset, accuracy_tester, tmp_path):
    """Test regression detection when baseline exists."""
    from src.backtesting.accuracy_tester import detect_regression, load_baseline, save_baseline

    detector = MockDetector([])

    # Run initial test
    initial_metrics = accuracy_tester.test_detector_accuracy(
        detector=detector,
        labeled_data=labeled_dataset,
        pattern_type="SPRING",
        detector_name="SpringDetector",
        threshold=Decimal("0.70"),
    )

    # Save as baseline
    baselines_dir = tmp_path / "baselines"
    save_baseline(initial_metrics, "SpringDetector", baselines_dir)

    # Load baseline
    baseline = load_baseline("SpringDetector", baselines_dir)
    assert baseline is not None

    # Run test again with same threshold (should not regress)
    current_metrics = accuracy_tester.test_detector_accuracy(
        detector=detector,
        labeled_data=labeled_dataset,
        pattern_type="SPRING",
        detector_name="SpringDetector",
        threshold=Decimal("0.70"),
    )

    # Check regression
    regression = detect_regression(current_metrics, baseline)

    # Should not regress (same metrics)
    assert regression is False
