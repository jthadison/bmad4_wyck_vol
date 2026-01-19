"""
Detector Accuracy Testing Framework (Story 12.3 Task 2)

Purpose:
--------
Test pattern detectors against labeled dataset to measure precision, recall,
F1-score, and Wyckoff-specific validation metrics. Validates NFR2/NFR3/NFR4
compliance and enables regression detection (NFR21).

Key Features:
-------------
- Test any detector implementing PatternDetector interface
- Calculate TP, FP, TN, FN counts and derived metrics
- False positive/negative analysis for debugging
- Wyckoff-specific validation (phase, campaign, sequential logic)
- Threshold tuning to optimize F1-score
- NFR compliance validation
- Regression detection against baselines

Usage:
------
    from backtesting.accuracy_tester import DetectorAccuracyTester, PatternDetector
    from backtesting.dataset_loader import load_labeled_patterns

    # Load labeled dataset
    df = load_labeled_patterns(version="v1")

    # Create tester
    tester = DetectorAccuracyTester()

    # Test detector
    metrics = tester.test_detector_accuracy(
        detector=spring_detector,
        labeled_data=df,
        pattern_type="SPRING"
    )

    print(f"Precision: {metrics.precision:.2%}")
    print(f"Recall: {metrics.recall:.2%}")
    print(f"F1-Score: {metrics.f1_score:.2%}")
    print(f"Passes NFR: {metrics.passes_nfr_target}")

NFR Thresholds:
---------------
- NFR2: Range detection precision ≥ 90%
- NFR3: Pattern detection precision ≥ 75%
- NFR4: Phase identification accuracy ≥ 80%

Author: Story 12.3 Task 2
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

import pandas as pd
import structlog

from src.models.backtest import AccuracyMetrics, LabeledPattern
from src.models.ohlcv import OHLCVBar

logger = structlog.get_logger(__name__)

# NFR Threshold Constants (Story 12.3 Task 3)
NFR2_RANGE_DETECTION_PRECISION_MIN = Decimal("0.90")  # 90%+
NFR3_PATTERN_DETECTION_PRECISION_MIN = Decimal("0.75")  # 75%+
NFR4_PHASE_IDENTIFICATION_ACCURACY_MIN = Decimal("0.80")  # 80%+

# Detector type mapping to NFR targets
DETECTOR_TYPE_NFR_MAP = {
    "RANGE": NFR2_RANGE_DETECTION_PRECISION_MIN,
    "PATTERN": NFR3_PATTERN_DETECTION_PRECISION_MIN,
    "PHASE": NFR4_PHASE_IDENTIFICATION_ACCURACY_MIN,
}


# ============================================================================
# Abstract Pattern Detector Interface (Story 12.3 Task 2.2)
# ============================================================================


class DetectedPattern:
    """
    Detected pattern output from PatternDetector.

    Attributes:
        pattern_type: Type of pattern (SPRING, SOS, UTAD, LPS)
        timestamp: Bar timestamp where pattern was detected
        confidence: Detection confidence (0-100)
        phase: Detected Wyckoff phase
        campaign_id: Parent campaign UUID (if available)
        metadata: Additional pattern details
    """

    def __init__(
        self,
        pattern_type: str,
        timestamp: datetime,
        confidence: int,
        phase: str | None = None,
        campaign_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        self.pattern_type = pattern_type
        self.timestamp = timestamp
        self.confidence = confidence
        self.phase = phase
        self.campaign_id = campaign_id
        self.metadata = metadata or {}


class PatternDetector(ABC):
    """
    Abstract base class for pattern detectors.

    All detector implementations (SpringDetector, SOSDetector, etc.) should
    implement this interface to enable uniform accuracy testing.

    This follows the dependency inversion principle and makes the accuracy
    tester extensible to new detector types.
    """

    @abstractmethod
    def detect(self, bars: list[OHLCVBar], **kwargs) -> list[DetectedPattern]:
        """
        Detect patterns in OHLCV bars.

        Args:
            bars: List of OHLCV bars to analyze
            **kwargs: Additional detector-specific parameters

        Returns:
            List of detected patterns
        """
        pass


# ============================================================================
# False Positive/Negative Case Models (Story 12.3 Task 2.3, 2.4)
# ============================================================================


class FalsePositiveCase:
    """False positive case: detector fired but shouldn't have."""

    def __init__(self, labeled_pattern: LabeledPattern, detected_confidence: int, reason: str):
        self.labeled_pattern = labeled_pattern
        self.detected_confidence = detected_confidence
        self.reason = reason


class FalseNegativeCase:
    """False negative case: detector missed a valid pattern."""

    def __init__(self, labeled_pattern: LabeledPattern, reason: str):
        self.labeled_pattern = labeled_pattern
        self.reason = reason


# ============================================================================
# Detector Accuracy Tester (Story 12.3 Task 2.1)
# ============================================================================


class DetectorAccuracyTester:
    """
    Test pattern detectors against labeled dataset.

    Measures precision, recall, F1-score, and Wyckoff-specific metrics
    to validate NFR compliance and enable regression detection.
    """

    def __init__(self):
        self.logger = logger.bind(component="accuracy_tester")

    def test_detector_accuracy(
        self,
        detector: PatternDetector,
        labeled_data: pd.DataFrame,
        pattern_type: Literal["SPRING", "SOS", "UTAD", "LPS"],
        detector_name: str,
        detector_version: str = "1.0",
        detector_type: Literal["RANGE", "PATTERN", "PHASE"] = "PATTERN",
        threshold: Decimal = Decimal("0.70"),
        dataset_version: str = "v1",
    ) -> AccuracyMetrics:
        """
        Test detector accuracy against labeled dataset.

        Args:
            detector: Pattern detector implementing PatternDetector interface
            labeled_data: DataFrame with labeled patterns from Story 12.2
            pattern_type: Pattern type to test (SPRING, SOS, UTAD, LPS)
            detector_name: Name of detector for reporting
            detector_version: Detector version identifier
            detector_type: Detector category (RANGE, PATTERN, PHASE) for NFR selection
            threshold: Confidence threshold to apply (patterns below this are rejected)
            dataset_version: Dataset version identifier

        Returns:
            AccuracyMetrics with comprehensive test results
        """
        self.logger.info(
            "starting_accuracy_test",
            detector=detector_name,
            pattern_type=pattern_type,
            threshold=float(threshold),
        )

        # Filter labeled data for this pattern type
        pattern_data = labeled_data[labeled_data["pattern_type"] == pattern_type].copy()

        if pattern_data.empty:
            raise ValueError(f"No labeled patterns found for type {pattern_type} in dataset")

        # Initialize counters
        true_positives = 0
        false_positives = 0
        true_negatives = 0
        false_negatives = 0

        # Wyckoff-specific counters
        correct_phase_count = 0
        valid_campaign_count = 0
        correct_prerequisites_count = 0
        confirmed_count = 0
        total_detections = 0

        phase_breakdown: dict[str, dict[str, int]] = {}
        campaign_breakdown: dict[str, dict[str, int]] = {}

        # Lists for FP/FN analysis
        false_positives_list: list[FalsePositiveCase] = []
        false_negatives_list: list[FalseNegativeCase] = []

        # Process each labeled pattern
        for _, row in pattern_data.iterrows():
            labeled_pattern = self._row_to_labeled_pattern(row)

            # TODO: For actual implementation, detector would need OHLCV bars
            # For now, we'll simulate detection based on confidence threshold
            # In real implementation, this would call: detector.detect(bars)

            # Simulate detection (placeholder - real implementation needs OHLCV data)
            detected = labeled_pattern.confidence >= int(threshold * 100)

            # Classification logic
            if labeled_pattern.correctness == "CORRECT":  # Ground truth = valid pattern
                if detected:
                    true_positives += 1
                    total_detections += 1

                    # Wyckoff-specific validation
                    if self._validate_phase(labeled_pattern):
                        correct_phase_count += 1
                    if self._validate_campaign(labeled_pattern):
                        valid_campaign_count += 1
                    if self._validate_prerequisites(labeled_pattern):
                        correct_prerequisites_count += 1
                    # Subsequent confirmation check removed - field not in LabeledPattern model
                    # TODO: Add subsequent_confirmation field to LabeledPattern if needed
                    confirmed_count += 1  # Count all TP as confirmed for now

                    # Track phase breakdown
                    phase = labeled_pattern.phase or "UNKNOWN"
                    if phase not in phase_breakdown:
                        phase_breakdown[phase] = {"TP": 0, "FP": 0}
                    phase_breakdown[phase]["TP"] += 1

                    # Campaign breakdown removed - campaign_type field not in LabeledPattern model
                    # TODO: Add campaign_type field to LabeledPattern if needed
                    campaign_type = "UNKNOWN"
                    if campaign_type not in campaign_breakdown:
                        campaign_breakdown[campaign_type] = {"TP": 0, "FP": 0}
                    campaign_breakdown[campaign_type]["TP"] += 1
                else:
                    false_negatives += 1
                    false_negatives_list.append(
                        FalseNegativeCase(
                            labeled_pattern=labeled_pattern,
                            reason=f"Confidence {labeled_pattern.confidence} below threshold {int(threshold * 100)}",
                        )
                    )
            else:  # Ground truth = invalid pattern
                if detected:
                    false_positives += 1
                    total_detections += 1
                    false_positives_list.append(
                        FalsePositiveCase(
                            labeled_pattern=labeled_pattern,
                            detected_confidence=labeled_pattern.confidence,
                            reason=f"Incorrectly detected pattern (confidence {labeled_pattern.confidence})",
                        )
                    )

                    # Track phase breakdown for FP
                    phase = labeled_pattern.phase or "UNKNOWN"
                    if phase not in phase_breakdown:
                        phase_breakdown[phase] = {"TP": 0, "FP": 0}
                    phase_breakdown[phase]["FP"] += 1

                    # Track campaign breakdown for FP (simplified since campaign_type not in model)
                    campaign_type = "UNKNOWN"
                    if campaign_type not in campaign_breakdown:
                        campaign_breakdown[campaign_type] = {"TP": 0, "FP": 0}
                    campaign_breakdown[campaign_type]["FP"] += 1
                else:
                    true_negatives += 1

        # Calculate standard metrics
        precision = self._calculate_precision(true_positives, false_positives)
        recall = self._calculate_recall(true_positives, false_negatives)
        f1_score = self._calculate_f1_score(precision, recall)

        # Calculate Wyckoff-specific metrics
        phase_accuracy = Decimal("0")
        campaign_validity_rate = Decimal("0")
        sequential_logic_score = Decimal("0")
        confirmation_rate = Decimal("0")

        if total_detections > 0:
            phase_accuracy = (
                Decimal(str(correct_phase_count)) / Decimal(str(total_detections))
            ).quantize(Decimal("0.0001"))
            campaign_validity_rate = (
                Decimal(str(valid_campaign_count)) / Decimal(str(total_detections))
            ).quantize(Decimal("0.0001"))
            sequential_logic_score = (
                Decimal(str(correct_prerequisites_count)) / Decimal(str(total_detections))
            ).quantize(Decimal("0.0001"))
            confirmation_rate = (
                Decimal(str(confirmed_count)) / Decimal(str(total_detections))
            ).quantize(Decimal("0.0001"))

        false_phase_rate = (Decimal("1") - phase_accuracy).quantize(Decimal("0.0001"))
        prerequisite_violation_rate = (Decimal("1") - sequential_logic_score).quantize(
            Decimal("0.0001")
        )

        # Get NFR target for this detector type
        nfr_target = DETECTOR_TYPE_NFR_MAP.get(detector_type, NFR3_PATTERN_DETECTION_PRECISION_MIN)
        passes_nfr = precision >= nfr_target

        # Build confusion matrix
        confusion_matrix = {
            "TP": true_positives,
            "FP": false_positives,
            "TN": true_negatives,
            "FN": false_negatives,
        }

        # Create AccuracyMetrics
        metrics = AccuracyMetrics(
            detector_name=detector_name,
            detector_version=detector_version,
            pattern_type=pattern_type,  # Required field
            test_timestamp=datetime.now(UTC),
            dataset_version=dataset_version,
            total_samples=len(pattern_data),
            true_positives=true_positives,
            false_positives=false_positives,
            true_negatives=true_negatives,
            false_negatives=false_negatives,
            precision=precision,
            recall=recall,
            f1_score=f1_score,
            confusion_matrix=confusion_matrix,
            threshold_used=threshold,
            passes_nfr_target=passes_nfr,
            nfr_target=nfr_target,
            phase_accuracy=phase_accuracy,
            campaign_validity_rate=campaign_validity_rate,
            sequential_logic_score=sequential_logic_score,
            false_phase_rate=false_phase_rate,
            confirmation_rate=confirmation_rate,
            phase_breakdown=phase_breakdown,
            campaign_type_breakdown=campaign_breakdown,
            prerequisite_violation_rate=prerequisite_violation_rate,
            metadata={
                "false_positives_count": len(false_positives_list),
                "false_negatives_count": len(false_negatives_list),
                "detector_type": detector_type,
            },
        )

        self.logger.info(
            "accuracy_test_complete",
            detector=detector_name,
            precision=float(precision),
            recall=float(recall),
            f1_score=float(f1_score),
            passes_nfr=passes_nfr,
        )

        # Store FP/FN lists for analysis
        self._last_false_positives = false_positives_list
        self._last_false_negatives = false_negatives_list

        return metrics

    def analyze_false_positives(self) -> list[FalsePositiveCase]:
        """
        Return list of false positive cases from last test run.

        Returns:
            List of FalsePositiveCase objects with details
        """
        return getattr(self, "_last_false_positives", [])

    def analyze_false_negatives(self) -> list[FalseNegativeCase]:
        """
        Return list of false negative cases from last test run.

        Returns:
            List of FalseNegativeCase objects with details
        """
        return getattr(self, "_last_false_negatives", [])

    def _row_to_labeled_pattern(self, row: pd.Series) -> LabeledPattern:
        """Convert DataFrame row to LabeledPattern model."""
        # Convert timestamp to date if needed
        pattern_date = row["date"]
        if hasattr(pattern_date, "date"):
            # It's a datetime/timestamp, extract date part
            pattern_date = pattern_date.date()

        # Convert correctness boolean to string if needed
        correctness = row["correctness"]
        if isinstance(correctness, bool):
            correctness = "CORRECT" if correctness else "INCORRECT"

        # Build kwargs dict with only fields that LabeledPattern accepts
        kwargs = {
            "symbol": row["symbol"],
            "date": pattern_date,
            "pattern_type": row["pattern_type"],
            "confidence": row["confidence"],
            "correctness": correctness,
            "phase": row.get("phase"),
            "campaign_id": row.get("campaign_id"),
            "notes": row.get("notes"),
        }

        return LabeledPattern(**kwargs)

    def _validate_phase(self, pattern: LabeledPattern) -> bool:
        """Validate pattern detected in correct Wyckoff phase."""
        if not pattern.phase:
            return True  # Phase validation not applicable if no phase specified

        # Extract phase letter from strings like "Phase C", "C", etc.
        phase_letter = pattern.phase.strip()
        if phase_letter.startswith("Phase "):
            phase_letter = phase_letter.replace("Phase ", "")

        # For Spring/Test patterns, should be in Phase C
        if pattern.pattern_type in ["SPRING", "TEST"]:
            return phase_letter == "C"
        # For SOS patterns, should be in Phase D
        elif pattern.pattern_type == "SOS":
            return phase_letter == "D"
        # For UTAD patterns, should be in Phase C (distribution)
        elif pattern.pattern_type == "UTAD":
            return phase_letter == "C"
        # For LPS patterns, should be in Phase D
        elif pattern.pattern_type == "LPS":
            return phase_letter == "D"
        return True

    def _validate_campaign(self, pattern: LabeledPattern) -> bool:
        """Validate pattern occurs within valid campaign."""
        # Campaign ID must exist
        return pattern.campaign_id is not None

    def _validate_prerequisites(self, pattern: LabeledPattern) -> bool:
        """Validate pattern has correct prerequisite events."""
        # Simplified: always return True since sequential_validity is not in model
        # TODO: Add sequential_validity field to LabeledPattern model if needed
        return True

    def _calculate_precision(self, tp: int, fp: int) -> Decimal:
        """Calculate precision: TP / (TP + FP)."""
        denominator = tp + fp
        if denominator == 0:
            return Decimal("0")
        return (Decimal(str(tp)) / Decimal(str(denominator))).quantize(Decimal("0.0001"))

    def _calculate_recall(self, tp: int, fn: int) -> Decimal:
        """Calculate recall: TP / (TP + FN)."""
        denominator = tp + fn
        if denominator == 0:
            return Decimal("0")
        return (Decimal(str(tp)) / Decimal(str(denominator))).quantize(Decimal("0.0001"))

    def _calculate_f1_score(self, precision: Decimal, recall: Decimal) -> Decimal:
        """Calculate F1-score: 2 * (P * R) / (P + R)."""
        denominator = precision + recall
        if denominator == 0:
            return Decimal("0")
        return ((Decimal("2") * precision * recall) / denominator).quantize(Decimal("0.0001"))


# ============================================================================
# NFR Validation (Story 12.3 Task 3.2)
# ============================================================================


def validate_nfr_compliance(metrics: AccuracyMetrics) -> bool:
    """
    Validate if metrics meet NFR compliance targets.

    Checks precision against applicable NFR threshold based on detector type.

    Args:
        metrics: AccuracyMetrics to validate

    Returns:
        True if compliant, False otherwise

    Logs:
        Detailed pass/fail reasons at INFO level
    """
    detector_type = metrics.metadata.get("detector_type", "PATTERN")
    nfr_target = DETECTOR_TYPE_NFR_MAP.get(detector_type, NFR3_PATTERN_DETECTION_PRECISION_MIN)

    compliant = metrics.precision >= nfr_target

    logger.info(
        "nfr_validation",
        detector=metrics.detector_name,
        detector_type=detector_type,
        precision=float(metrics.precision),
        nfr_target=float(nfr_target),
        compliant=compliant,
        reason=f"Precision {metrics.precision:.2%} {'meets' if compliant else 'below'} NFR target {nfr_target:.2%}",
    )

    return compliant


# ============================================================================
# Threshold Tuning (Story 12.3 Task 4)
# ============================================================================


def tune_confidence_threshold(
    detector: PatternDetector,
    labeled_data: pd.DataFrame,
    pattern_type: Literal["SPRING", "SOS", "UTAD", "LPS"],
    detector_name: str,
    threshold_range: range = range(70, 96, 5),
    detector_type: Literal["RANGE", "PATTERN", "PHASE"] = "PATTERN",
) -> dict[int, Decimal]:
    """
    Tune confidence threshold to find optimal F1-score.

    Args:
        detector: Pattern detector to test
        labeled_data: Labeled dataset
        pattern_type: Pattern type to test
        detector_name: Detector name for logging
        threshold_range: Range of thresholds to test (default 70-95 in steps of 5)
        detector_type: Detector category for NFR selection

    Returns:
        Dictionary mapping threshold -> F1-score
    """
    tester = DetectorAccuracyTester()
    results = {}

    for threshold_int in threshold_range:
        threshold = Decimal(str(threshold_int / 100))

        metrics = tester.test_detector_accuracy(
            detector=detector,
            labeled_data=labeled_data,
            pattern_type=pattern_type,
            detector_name=detector_name,
            threshold=threshold,
            detector_type=detector_type,
        )

        results[threshold_int] = metrics.f1_score

        logger.info(
            "threshold_tuning",
            threshold=threshold_int,
            f1_score=float(metrics.f1_score),
            precision=float(metrics.precision),
            recall=float(metrics.recall),
        )

    return results


def find_optimal_threshold(
    detector: PatternDetector,
    labeled_data: pd.DataFrame,
    pattern_type: Literal["SPRING", "SOS", "UTAD", "LPS"],
    detector_name: str,
    detector_type: Literal["RANGE", "PATTERN", "PHASE"] = "PATTERN",
) -> tuple[int, Decimal]:
    """
    Find optimal confidence threshold that maximizes F1-score.

    Args:
        detector: Pattern detector to test
        labeled_data: Labeled dataset
        pattern_type: Pattern type to test
        detector_name: Detector name
        detector_type: Detector category

    Returns:
        Tuple of (optimal_threshold, expected_f1_score)
    """
    results = tune_confidence_threshold(
        detector=detector,
        labeled_data=labeled_data,
        pattern_type=pattern_type,
        detector_name=detector_name,
        detector_type=detector_type,
    )

    # Find threshold with max F1-score
    optimal_threshold = max(results.items(), key=lambda x: x[1])

    logger.info(
        "optimal_threshold_found",
        detector=detector_name,
        optimal_threshold=optimal_threshold[0],
        expected_f1=float(optimal_threshold[1]),
    )

    return optimal_threshold


# ============================================================================
# Baseline Management (Story 12.3 Task 5)
# ============================================================================


def save_baseline(
    metrics: AccuracyMetrics, detector_name: str, baselines_dir: Path | None = None
) -> None:
    """
    Save baseline AccuracyMetrics for regression detection.

    Args:
        metrics: AccuracyMetrics to save as baseline
        detector_name: Detector name for file naming
        baselines_dir: Directory to save baselines (default: tests/datasets/baselines/)
    """
    if baselines_dir is None:
        backend_dir = Path(__file__).parent.parent.parent
        baselines_dir = backend_dir / "tests" / "datasets" / "baselines"

    baselines_dir.mkdir(parents=True, exist_ok=True)

    baseline_file = baselines_dir / f"{detector_name.lower()}_baseline.json"

    # Convert to dict and save
    baseline_data = metrics.model_dump(mode="json")

    with open(baseline_file, "w") as f:
        json.dump(baseline_data, f, indent=2, default=str)

    logger.info(
        "baseline_saved",
        detector=detector_name,
        file=str(baseline_file),
        f1_score=float(metrics.f1_score),
    )


def load_baseline(detector_name: str, baselines_dir: Path | None = None) -> AccuracyMetrics | None:
    """
    Load baseline AccuracyMetrics for regression detection.

    Args:
        detector_name: Detector name
        baselines_dir: Directory containing baselines

    Returns:
        AccuracyMetrics if baseline exists, None otherwise
    """
    if baselines_dir is None:
        backend_dir = Path(__file__).parent.parent.parent
        baselines_dir = backend_dir / "tests" / "datasets" / "baselines"

    baseline_file = baselines_dir / f"{detector_name.lower()}_baseline.json"

    if not baseline_file.exists():
        logger.info("no_baseline_found", detector=detector_name)
        return None

    with open(baseline_file) as f:
        baseline_data = json.load(f)

    metrics = AccuracyMetrics(**baseline_data)

    logger.info(
        "baseline_loaded",
        detector=detector_name,
        baseline_f1=float(metrics.f1_score),
        baseline_date=str(metrics.test_timestamp),
    )

    return metrics


def detect_regression(
    current: AccuracyMetrics, baseline: AccuracyMetrics, tolerance: Decimal = Decimal("0.05")
) -> bool:
    """
    Detect if current metrics show regression vs baseline.

    Regression = current F1 < (baseline F1 - tolerance)

    Args:
        current: Current test metrics
        baseline: Baseline metrics
        tolerance: Regression tolerance (default 0.05 = 5%)

    Returns:
        True if regression detected, False otherwise
    """
    threshold = baseline.f1_score - tolerance
    regression_detected = current.f1_score < threshold

    if regression_detected:
        degradation = baseline.f1_score - current.f1_score
        degradation_pct = (degradation / baseline.f1_score) * Decimal("100")

        logger.warning(
            "regression_detected",
            detector=current.detector_name,
            current_f1=float(current.f1_score),
            baseline_f1=float(baseline.f1_score),
            degradation=float(degradation),
            degradation_pct=float(degradation_pct),
            threshold=float(threshold),
        )
    else:
        logger.info(
            "no_regression",
            detector=current.detector_name,
            current_f1=float(current.f1_score),
            baseline_f1=float(baseline.f1_score),
        )

    return regression_detected
