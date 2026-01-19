"""
Unit Tests for Detector Accuracy Testing (Story 12.3 Task 6)

Tests:
------
- AccuracyMetrics model validation
- Metrics calculations (precision, recall, F1-score)
- Edge cases (zero TP, zero FP, perfect/useless detector)
- NFR validation logic
- Threshold tuning
- Regression detection
- Baseline management

Author: Story 12.3 Task 6
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pandas as pd
import pytest

from src.backtesting.accuracy_tester import (
    DetectedPattern,
    DetectorAccuracyTester,
    PatternDetector,
    detect_regression,
    find_optimal_threshold,
    load_baseline,
    save_baseline,
    tune_confidence_threshold,
    validate_nfr_compliance,
)
from src.models.backtest import AccuracyMetrics
from src.models.ohlcv import OHLCVBar

# ============================================================================
# Mock Detector for Testing
# ============================================================================


class MockDetector(PatternDetector):
    """Mock detector that returns predictable results."""

    def __init__(self, patterns: list[DetectedPattern]):
        self.patterns = patterns

    def detect(self, bars: list[OHLCVBar], **kwargs) -> list[DetectedPattern]:
        return self.patterns


class PerfectDetector(PatternDetector):
    """Detector that perfectly matches ground truth."""

    def detect(self, bars: list[OHLCVBar], **kwargs) -> list[DetectedPattern]:
        # In real implementation, would analyze bars
        # For testing, return all patterns with 100% confidence
        return [
            DetectedPattern(
                pattern_type="SPRING",
                timestamp=datetime.now(UTC),
                confidence=100,
                phase="C",
                campaign_id=str(uuid4()),
            )
        ]


class UselessDetector(PatternDetector):
    """Detector that never finds anything."""

    def detect(self, bars: list[OHLCVBar], **kwargs) -> list[DetectedPattern]:
        return []


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def sample_accuracy_metrics():
    """Sample AccuracyMetrics for testing."""
    return AccuracyMetrics(
        detector_name="TestDetector",
        detector_version="1.0",
        test_timestamp=datetime.now(UTC),
        dataset_version="v1",
        pattern_type="SPRING",  # Required field
        total_samples=100,
        true_positives=75,
        false_positives=10,
        true_negatives=5,
        false_negatives=10,
        precision=Decimal("0.8824"),  # 75 / (75 + 10)
        recall=Decimal("0.8824"),  # 75 / (75 + 10)
        f1_score=Decimal("0.8824"),
        confusion_matrix={"TP": 75, "FP": 10, "TN": 5, "FN": 10},
        threshold_used=Decimal("0.70"),
        passes_nfr_target=True,
        nfr_target=Decimal("0.75"),
        metadata={"detector_type": "PATTERN"},
    )


@pytest.fixture
def sample_labeled_data():
    """Sample labeled dataset for testing."""
    data = []

    # Create 50 true positive cases (correct patterns, high confidence)
    for i in range(50):
        data.append(
            {
                "id": str(uuid4()),
                "symbol": "AAPL",
                "date": datetime.now(UTC),
                "pattern_type": "SPRING",
                "confidence": 85,
                "correctness": True,
                "outcome_win": True,
                "phase": "C",
                "trading_range_id": f"TR_{i}",
                "entry_price": Decimal("150.00"),
                "stop_loss": Decimal("148.00"),
                "target_price": Decimal("155.00"),
                "volume_ratio": Decimal("0.65"),
                "spread_ratio": Decimal("0.80"),
                "justification": "Valid Spring",
                "reviewer_verified": True,
                "campaign_id": str(uuid4()),
                "campaign_type": "ACCUMULATION",
                "campaign_phase": "C",
                "phase_position": "late Phase C",
                "volume_characteristics": {"type": "diminishing"},
                "spread_characteristics": {"type": "narrowing"},
                "sr_test_result": "support held",
                "preliminary_events": ["PS", "SC", "AR"],
                "subsequent_confirmation": True,
                "sequential_validity": True,
                "false_positive_reason": None,
            }
        )

    # Create 10 false positive cases (incorrect patterns, high confidence)
    for i in range(10):
        data.append(
            {
                "id": str(uuid4()),
                "symbol": "AAPL",
                "date": datetime.now(UTC),
                "pattern_type": "SPRING",
                "confidence": 82,
                "correctness": False,
                "outcome_win": False,
                "phase": "A",  # Wrong phase
                "trading_range_id": f"TR_{i + 50}",
                "entry_price": Decimal("150.00"),
                "stop_loss": Decimal("148.00"),
                "target_price": Decimal("155.00"),
                "volume_ratio": Decimal("0.65"),
                "spread_ratio": Decimal("0.80"),
                "justification": "False Spring - wrong phase",
                "reviewer_verified": True,
                "campaign_id": str(uuid4()),
                "campaign_type": "ACCUMULATION",
                "campaign_phase": "A",
                "phase_position": "early Phase A",
                "volume_characteristics": {"type": "normal"},
                "spread_characteristics": {"type": "normal"},
                "sr_test_result": "support broken",
                "preliminary_events": [],
                "subsequent_confirmation": False,
                "sequential_validity": False,
                "false_positive_reason": "Pattern in Phase A instead of Phase C",
            }
        )

    # Create 10 false negative cases (valid patterns, confidence below test threshold but >= 70)
    for i in range(10):
        data.append(
            {
                "id": str(uuid4()),
                "symbol": "AAPL",
                "date": datetime.now(UTC),
                "pattern_type": "SPRING",
                "confidence": 72,  # Below 75% test threshold but valid for model
                "correctness": True,
                "outcome_win": True,
                "phase": "C",
                "trading_range_id": f"TR_{i + 60}",
                "entry_price": Decimal("150.00"),
                "stop_loss": Decimal("148.00"),
                "target_price": Decimal("155.00"),
                "volume_ratio": Decimal("0.65"),
                "spread_ratio": Decimal("0.80"),
                "justification": "Valid Spring but low confidence",
                "reviewer_verified": True,
                "campaign_id": str(uuid4()),
                "campaign_type": "ACCUMULATION",
                "campaign_phase": "C",
                "phase_position": "mid Phase C",
                "volume_characteristics": {"type": "diminishing"},
                "spread_characteristics": {"type": "narrowing"},
                "sr_test_result": "support held",
                "preliminary_events": ["PS", "SC"],
                "subsequent_confirmation": True,
                "sequential_validity": True,
                "false_positive_reason": None,
            }
        )

    # Create 10 true negative cases (invalid patterns, low confidence)
    for i in range(10):
        data.append(
            {
                "id": str(uuid4()),
                "symbol": "AAPL",
                "date": datetime.now(UTC),
                "pattern_type": "SPRING",
                "confidence": 71,  # Below 75% test threshold but valid for model
                "correctness": False,
                "outcome_win": False,
                "phase": "E",
                "trading_range_id": f"TR_{i + 70}",
                "entry_price": Decimal("150.00"),
                "stop_loss": Decimal("148.00"),
                "target_price": Decimal("155.00"),
                "volume_ratio": Decimal("0.65"),
                "spread_ratio": Decimal("0.80"),
                "justification": "Invalid pattern",
                "reviewer_verified": True,
                "campaign_id": str(uuid4()),
                "campaign_type": "DISTRIBUTION",
                "campaign_phase": "E",
                "phase_position": "late Phase E",
                "volume_characteristics": {"type": "normal"},
                "spread_characteristics": {"type": "normal"},
                "sr_test_result": "resistance broken",
                "preliminary_events": [],
                "subsequent_confirmation": False,
                "sequential_validity": False,
                "false_positive_reason": "Pattern in wrong campaign type",
            }
        )

    return pd.DataFrame(data)


# ============================================================================
# Test AccuracyMetrics Model
# ============================================================================


def test_accuracy_metrics_creation(sample_accuracy_metrics):
    """Test AccuracyMetrics model creation and validation."""
    assert sample_accuracy_metrics.detector_name == "TestDetector"
    assert sample_accuracy_metrics.total_samples == 100
    assert sample_accuracy_metrics.true_positives == 75
    assert sample_accuracy_metrics.precision == Decimal("0.8824")


def test_accuracy_metrics_decimal_conversion():
    """Test Decimal conversion for metrics."""
    metrics = AccuracyMetrics(
        detector_name="Test",
        pattern_type="SPRING",  # Required field
        total_samples=100,
        true_positives=80,
        false_positives=10,
        true_negatives=5,
        false_negatives=5,
        precision="0.8889",  # String input
        recall=0.9412,  # Float input
        f1_score=Decimal("0.9143"),  # Decimal input
        confusion_matrix={"TP": 80, "FP": 10, "TN": 5, "FN": 5},
        passes_nfr_target=True,
        nfr_target="0.75",
    )

    assert isinstance(metrics.precision, Decimal)
    assert isinstance(metrics.recall, Decimal)
    assert isinstance(metrics.f1_score, Decimal)
    assert metrics.precision == Decimal("0.8889")


def test_accuracy_metrics_utc_timestamp():
    """Test UTC timestamp enforcement."""
    naive_dt = datetime(2024, 12, 20, 18, 30, 0)

    metrics = AccuracyMetrics(
        detector_name="Test",
        pattern_type="SPRING",  # Required field
        test_timestamp=naive_dt,
        total_samples=100,
        true_positives=80,
        false_positives=10,
        true_negatives=5,
        false_negatives=5,
        precision=Decimal("0.8889"),
        recall=Decimal("0.9412"),
        f1_score=Decimal("0.9143"),
        confusion_matrix={"TP": 80, "FP": 10, "TN": 5, "FN": 5},
        passes_nfr_target=True,
        nfr_target=Decimal("0.75"),
    )

    assert metrics.test_timestamp.tzinfo == UTC


def test_accuracy_metrics_computed_properties(sample_accuracy_metrics):
    """Test computed properties (accuracy, specificity, NPV)."""
    # Overall accuracy: (TP + TN) / (TP + TN + FP + FN) = (75 + 5) / 100 = 0.80
    assert sample_accuracy_metrics.accuracy == Decimal("0.80")

    # Specificity: TN / (TN + FP) = 5 / (5 + 10) = 0.3333...
    specificity = sample_accuracy_metrics.specificity
    assert specificity > Decimal("0.33") and specificity < Decimal("0.34")

    # NPV: TN / (TN + FN) = 5 / (5 + 10) = 0.3333...
    npv = sample_accuracy_metrics.negative_predictive_value
    assert npv > Decimal("0.33") and npv < Decimal("0.34")


# ============================================================================
# Test Metrics Calculations
# ============================================================================


def test_precision_calculation():
    """Test precision calculation: TP / (TP + FP)."""
    tester = DetectorAccuracyTester()

    # Normal case (quantized to 4 decimal places)
    precision = tester._calculate_precision(tp=80, fp=10)
    assert precision == Decimal("0.8889")  # 80/90 = 0.888888... rounded to 0.8889

    # Edge case: Zero FP (perfect precision)
    precision = tester._calculate_precision(tp=80, fp=0)
    assert precision == Decimal("1.0000")

    # Edge case: Zero TP and FP
    precision = tester._calculate_precision(tp=0, fp=0)
    assert precision == Decimal("0")


def test_recall_calculation():
    """Test recall calculation: TP / (TP + FN)."""
    tester = DetectorAccuracyTester()

    # Normal case (quantized to 4 decimal places)
    recall = tester._calculate_recall(tp=80, fn=10)
    assert recall == Decimal("0.8889")  # 80/90 = 0.888888... rounded to 0.8889

    # Edge case: Zero FN (perfect recall)
    recall = tester._calculate_recall(tp=80, fn=0)
    assert recall == Decimal("1.0000")

    # Edge case: Zero TP and FN
    recall = tester._calculate_recall(tp=0, fn=0)
    assert recall == Decimal("0")


def test_f1_score_calculation():
    """Test F1-score calculation: 2 * (P * R) / (P + R)."""
    tester = DetectorAccuracyTester()

    # Normal case
    precision = Decimal("0.8")
    recall = Decimal("0.9")
    f1 = tester._calculate_f1_score(precision, recall)
    # F1 = 2 * (0.8 * 0.9) / (0.8 + 0.9) = 1.44 / 1.7 = 0.847...
    assert f1 > Decimal("0.847") and f1 < Decimal("0.848")

    # Edge case: Perfect precision and recall
    f1 = tester._calculate_f1_score(Decimal("1.0"), Decimal("1.0"))
    assert f1 == Decimal("1.0")

    # Edge case: Zero precision and recall
    f1 = tester._calculate_f1_score(Decimal("0"), Decimal("0"))
    assert f1 == Decimal("0")


def test_detector_accuracy_with_mock_data(sample_labeled_data):
    """Test detector accuracy testing with mock data."""
    tester = DetectorAccuracyTester()
    detector = MockDetector([])

    metrics = tester.test_detector_accuracy(
        detector=detector,
        labeled_data=sample_labeled_data,
        pattern_type="SPRING",
        detector_name="MockDetector",
        threshold=Decimal("0.75"),  # Use 75% threshold
    )

    # Expected counts based on sample_labeled_data:
    # - 50 TP (correctness=True, confidence=85 >= 75)
    # - 10 FP (correctness=False, confidence=82 >= 75)
    # - 10 FN (correctness=True, confidence=72 < 75)
    # - 10 TN (correctness=False, confidence=71 < 75)

    assert metrics.true_positives == 50
    assert metrics.false_positives == 10
    assert metrics.false_negatives == 10
    assert metrics.true_negatives == 10

    # Precision = 50 / (50 + 10) = 0.8333...
    assert metrics.precision > Decimal("0.83") and metrics.precision < Decimal("0.84")

    # Recall = 50 / (50 + 10) = 0.8333...
    assert metrics.recall > Decimal("0.83") and metrics.recall < Decimal("0.84")


# ============================================================================
# Test NFR Validation
# ============================================================================


def test_nfr_validation_pattern_detector_pass():
    """Test NFR validation for pattern detector (≥75%)."""
    metrics = AccuracyMetrics(
        detector_name="SpringDetector",
        pattern_type="SPRING",  # Required field
        total_samples=100,
        true_positives=76,
        false_positives=9,
        true_negatives=0,
        false_negatives=15,
        precision=Decimal("0.8941"),  # 89.41% - PASS
        recall=Decimal("0.8352"),
        f1_score=Decimal("0.8636"),
        confusion_matrix={"TP": 76, "FP": 9, "TN": 0, "FN": 15},
        passes_nfr_target=True,
        nfr_target=Decimal("0.75"),
        metadata={"detector_type": "PATTERN"},
    )

    assert validate_nfr_compliance(metrics) is True


def test_nfr_validation_pattern_detector_fail():
    """Test NFR validation for pattern detector (below 75%)."""
    metrics = AccuracyMetrics(
        detector_name="SpringDetector",
        pattern_type="SPRING",  # Required field
        total_samples=100,
        true_positives=70,
        false_positives=30,
        true_negatives=0,
        false_negatives=0,
        precision=Decimal("0.70"),  # 70% - FAIL (below 75%)
        recall=Decimal("1.0"),
        f1_score=Decimal("0.8235"),
        confusion_matrix={"TP": 70, "FP": 30, "TN": 0, "FN": 0},
        passes_nfr_target=False,
        nfr_target=Decimal("0.75"),
        metadata={"detector_type": "PATTERN"},
    )

    assert validate_nfr_compliance(metrics) is False


def test_nfr_validation_range_detector():
    """Test NFR validation for range detector (≥90%)."""
    metrics = AccuracyMetrics(
        detector_name="RangeDetector",
        pattern_type="SPRING",  # Required field (using SPRING as placeholder for range tests)
        total_samples=100,
        true_positives=91,
        false_positives=9,
        true_negatives=0,
        false_negatives=0,
        precision=Decimal("0.91"),  # 91% - PASS
        recall=Decimal("1.0"),
        f1_score=Decimal("0.9533"),
        confusion_matrix={"TP": 91, "FP": 9, "TN": 0, "FN": 0},
        passes_nfr_target=True,
        nfr_target=Decimal("0.90"),
        metadata={"detector_type": "RANGE"},
    )

    assert validate_nfr_compliance(metrics) is True


# ============================================================================
# Test Threshold Tuning
# ============================================================================


def test_tune_confidence_threshold(sample_labeled_data):
    """Test threshold tuning returns F1 scores for each threshold."""
    detector = MockDetector([])

    results = tune_confidence_threshold(
        detector=detector,
        labeled_data=sample_labeled_data,
        pattern_type="SPRING",
        detector_name="MockDetector",
        threshold_range=range(70, 86, 5),  # 70, 75, 80, 85
    )

    # Should return 4 results
    assert len(results) == 4
    assert 70 in results
    assert 75 in results
    assert 80 in results
    assert 85 in results

    # All F1 scores should be Decimal
    for f1 in results.values():
        assert isinstance(f1, Decimal)


def test_find_optimal_threshold(sample_labeled_data):
    """Test finding optimal threshold that maximizes F1-score."""
    detector = MockDetector([])

    optimal_threshold, expected_f1 = find_optimal_threshold(
        detector=detector,
        labeled_data=sample_labeled_data,
        pattern_type="SPRING",
        detector_name="MockDetector",
    )

    # Should return threshold and F1-score
    assert isinstance(optimal_threshold, int)
    assert isinstance(expected_f1, Decimal)
    assert optimal_threshold >= 70
    assert optimal_threshold <= 95


# ============================================================================
# Test Regression Detection
# ============================================================================


def test_detect_regression_with_5_percent_drop():
    """Test regression detection with exactly 5% drop."""
    baseline = AccuracyMetrics(
        detector_name="Test",
        pattern_type="SPRING",  # Required field
        total_samples=100,
        true_positives=80,
        false_positives=10,
        true_negatives=5,
        false_negatives=5,
        precision=Decimal("0.8889"),
        recall=Decimal("0.9412"),
        f1_score=Decimal("0.80"),  # Baseline F1
        confusion_matrix={"TP": 80, "FP": 10, "TN": 5, "FN": 5},
        passes_nfr_target=True,
        nfr_target=Decimal("0.75"),
    )

    current = AccuracyMetrics(
        detector_name="Test",
        pattern_type="SPRING",  # Required field
        total_samples=100,
        true_positives=75,
        false_positives=15,
        true_negatives=5,
        false_negatives=5,
        precision=Decimal("0.8333"),
        recall=Decimal("0.9375"),
        f1_score=Decimal("0.75"),  # 5% drop (0.80 - 0.05 = 0.75)
        confusion_matrix={"TP": 75, "FP": 15, "TN": 5, "FN": 5},
        passes_nfr_target=True,
        nfr_target=Decimal("0.75"),
    )

    # 5% drop is at the boundary (0.75 == 0.75), so NOT a regression
    # Regression requires current < (baseline - tolerance)
    assert detect_regression(current, baseline) is False


def test_detect_regression_with_6_percent_drop():
    """Test regression detection with 6% drop."""
    baseline = AccuracyMetrics(
        detector_name="Test",
        pattern_type="SPRING",  # Required field
        total_samples=100,
        true_positives=80,
        false_positives=10,
        true_negatives=5,
        false_negatives=5,
        precision=Decimal("0.8889"),
        recall=Decimal("0.9412"),
        f1_score=Decimal("0.80"),
        confusion_matrix={"TP": 80, "FP": 10, "TN": 5, "FN": 5},
        passes_nfr_target=True,
        nfr_target=Decimal("0.75"),
    )

    current = AccuracyMetrics(
        detector_name="Test",
        pattern_type="SPRING",  # Required field
        total_samples=100,
        true_positives=70,
        false_positives=20,
        true_negatives=5,
        false_negatives=5,
        precision=Decimal("0.7778"),
        recall=Decimal("0.9333"),
        f1_score=Decimal("0.74"),  # 6% drop
        confusion_matrix={"TP": 70, "FP": 20, "TN": 5, "FN": 5},
        passes_nfr_target=False,
        nfr_target=Decimal("0.75"),
    )

    assert detect_regression(current, baseline) is True


def test_no_regression_with_2_percent_drop():
    """Test no regression with 2.5% drop (within tolerance)."""
    baseline = AccuracyMetrics(
        detector_name="Test",
        pattern_type="SPRING",  # Required field
        total_samples=100,
        true_positives=80,
        false_positives=10,
        true_negatives=5,
        false_negatives=5,
        precision=Decimal("0.8889"),
        recall=Decimal("0.9412"),
        f1_score=Decimal("0.80"),
        confusion_matrix={"TP": 80, "FP": 10, "TN": 5, "FN": 5},
        passes_nfr_target=True,
        nfr_target=Decimal("0.75"),
    )

    current = AccuracyMetrics(
        detector_name="Test",
        pattern_type="SPRING",  # Required field
        total_samples=100,
        true_positives=78,
        false_positives=12,
        true_negatives=5,
        false_negatives=5,
        precision=Decimal("0.8667"),
        recall=Decimal("0.9398"),
        f1_score=Decimal("0.78"),  # 2.5% drop (within 5% tolerance)
        confusion_matrix={"TP": 78, "FP": 12, "TN": 5, "FN": 5},
        passes_nfr_target=True,
        nfr_target=Decimal("0.75"),
    )

    assert detect_regression(current, baseline) is False


# ============================================================================
# Test Baseline Management
# ============================================================================


def test_save_and_load_baseline(sample_accuracy_metrics, tmp_path):
    """Test saving and loading baseline metrics."""
    baselines_dir = tmp_path / "baselines"
    baselines_dir.mkdir()

    # Save baseline
    save_baseline(
        metrics=sample_accuracy_metrics, detector_name="TestDetector", baselines_dir=baselines_dir
    )

    # Verify file exists
    baseline_file = baselines_dir / "testdetector_baseline.json"
    assert baseline_file.exists()

    # Load baseline
    loaded_metrics = load_baseline(detector_name="TestDetector", baselines_dir=baselines_dir)

    assert loaded_metrics is not None
    assert loaded_metrics.detector_name == "TestDetector"
    assert loaded_metrics.f1_score == sample_accuracy_metrics.f1_score
    assert loaded_metrics.precision == sample_accuracy_metrics.precision


def test_load_baseline_not_found(tmp_path):
    """Test loading baseline when file doesn't exist."""
    baselines_dir = tmp_path / "baselines"
    baselines_dir.mkdir()

    loaded_metrics = load_baseline(detector_name="NonExistent", baselines_dir=baselines_dir)

    assert loaded_metrics is None


# ============================================================================
# Test False Positive/Negative Analysis
# ============================================================================


def test_false_positive_analysis(sample_labeled_data):
    """Test false positive analysis returns cases."""
    tester = DetectorAccuracyTester()
    detector = MockDetector([])

    # Use 0.75 threshold to get expected FP/FN split
    metrics = tester.test_detector_accuracy(
        detector=detector,
        labeled_data=sample_labeled_data,
        pattern_type="SPRING",
        detector_name="MockDetector",
        threshold=Decimal("0.75"),
    )

    # Get false positives
    false_positives = tester.analyze_false_positives()

    # Should have 10 FP cases (confidence 82, correctness False)
    assert len(false_positives) == 10

    # Each FP case should have details
    for fp in false_positives:
        assert fp.labeled_pattern is not None
        assert fp.detected_confidence > 0
        assert fp.reason is not None


def test_false_negative_analysis(sample_labeled_data):
    """Test false negative analysis returns cases."""
    tester = DetectorAccuracyTester()
    detector = MockDetector([])

    # Use 0.75 threshold to get expected FP/FN split
    metrics = tester.test_detector_accuracy(
        detector=detector,
        labeled_data=sample_labeled_data,
        pattern_type="SPRING",
        detector_name="MockDetector",
        threshold=Decimal("0.75"),
    )

    # Get false negatives
    false_negatives = tester.analyze_false_negatives()

    # Should have 10 FN cases (confidence 72, correctness True, below threshold)
    assert len(false_negatives) == 10

    # Each FN case should have details
    for fn in false_negatives:
        assert fn.labeled_pattern is not None
        assert fn.reason is not None
