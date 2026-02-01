"""
Accuracy testing models.

This module contains models for pattern detector accuracy testing
including labeled patterns and accuracy metrics.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AccuracyMetrics(BaseModel):
    """
    Comprehensive accuracy metrics for Wyckoff pattern detectors (Story 12.3 Task 1).

    Combines standard ML metrics with Wyckoff-specific validation to ensure
    detectors not only identify patterns but do so within correct campaign phases
    and sequential logic.

    Standard ML Metrics:
        precision: TP / (TP + FP) - How many detected patterns were correct?
        recall: TP / (TP + FN) - How many actual patterns were detected?
        f1_score: Harmonic mean of precision and recall
        confusion_matrix: TP, FP, TN, FN counts

    Wyckoff-Specific Metrics (Critical for Methodology Validation):
        phase_accuracy: % of patterns detected in correct Wyckoff phase
        campaign_validity_rate: % of patterns within valid campaigns
        sequential_logic_score: % of patterns with correct prerequisite events
        false_phase_rate: % of patterns incorrectly detected in wrong phase
        confirmation_rate: % of patterns with subsequent confirmation events
        phase_breakdown: Accuracy per phase
        campaign_type_breakdown: Accuracy per campaign type
        prerequisite_violation_rate: % of detections missing required events

    Author: Story 12.3 Task 1
    """

    # Core identification
    detector_name: str = Field(..., max_length=100, description="Detector name")
    detector_version: str = Field(default="1.0", max_length=50, description="Version identifier")
    test_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Test run timestamp (UTC)"
    )
    dataset_version: str = Field(default="v1", max_length=20, description="Dataset version")
    pattern_type: Literal["SPRING", "SOS", "UTAD", "LPS"] = Field(
        description="Pattern being tested"
    )

    # Sample counts
    total_samples: int = Field(..., ge=0, description="Total test cases")
    true_positives: int = Field(..., ge=0, description="Correctly detected patterns")
    false_positives: int = Field(..., ge=0, description="Incorrectly detected patterns")
    true_negatives: int = Field(..., ge=0, description="Correctly rejected non-patterns")
    false_negatives: int = Field(..., ge=0, description="Missed valid patterns")

    # Standard accuracy metrics (use Decimal for financial precision)
    precision: Decimal = Field(..., decimal_places=4, description="Precision (TP / (TP + FP))")
    recall: Decimal = Field(..., decimal_places=4, description="Recall (TP / (TP + FN))")
    f1_score: Decimal = Field(..., decimal_places=4, description="F1-score (harmonic mean)")
    confusion_matrix: dict[str, int] = Field(
        ..., description="Full confusion matrix (TP, FP, TN, FN)"
    )

    # Test configuration
    threshold_used: Decimal = Field(
        default=Decimal("0.70"),
        ge=Decimal("0"),
        le=Decimal("1.0"),
        decimal_places=2,
        description="Confidence threshold applied",
    )

    # NFR compliance
    passes_nfr_target: bool = Field(..., description="Meets NFR precision target?")
    nfr_target: Decimal = Field(..., decimal_places=2, description="NFR target precision")

    # Additional metadata
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional test details")

    # Wyckoff-specific accuracy metrics (Story 12.3 - CRITICAL)
    phase_accuracy: Decimal = Field(
        default=Decimal("0"),
        decimal_places=4,
        description="% of patterns detected in correct Wyckoff phase",
    )
    campaign_validity_rate: Decimal = Field(
        default=Decimal("0"),
        decimal_places=4,
        description="% of patterns within valid Accumulation/Distribution campaigns",
    )
    sequential_logic_score: Decimal = Field(
        default=Decimal("0"),
        decimal_places=4,
        description="% of patterns with correct prerequisite events",
    )
    false_phase_rate: Decimal = Field(
        default=Decimal("0"),
        decimal_places=4,
        description="% of patterns incorrectly detected in wrong phase",
    )
    confirmation_rate: Decimal = Field(
        default=Decimal("0"),
        decimal_places=4,
        description="% of patterns with subsequent confirmation events",
    )
    phase_breakdown: dict[str, dict[str, int]] = Field(
        default_factory=dict,
        description="Accuracy per phase: {'Phase C': {'TP': 10, 'FP': 2}, ...}",
    )
    campaign_type_breakdown: dict[str, dict[str, int]] = Field(
        default_factory=dict,
        description="Accuracy per campaign type: {'ACCUMULATION': {...}, 'DISTRIBUTION': {...}}",
    )
    prerequisite_violation_rate: Decimal = Field(
        default=Decimal("0"),
        decimal_places=4,
        description="% of detections missing required preliminary events",
    )

    @field_validator("test_timestamp", mode="before")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        """Enforce UTC timezone on test timestamp (matches OHLCVBar pattern)."""
        if isinstance(v, datetime):
            if v.tzinfo is None:
                return v.replace(tzinfo=UTC)
            return v.astimezone(UTC)
        return v

    @field_validator(
        "precision",
        "recall",
        "f1_score",
        "threshold_used",
        "nfr_target",
        "phase_accuracy",
        "campaign_validity_rate",
        "sequential_logic_score",
        "false_phase_rate",
        "confirmation_rate",
        "prerequisite_violation_rate",
        mode="before",
    )
    @classmethod
    def convert_to_decimal(cls, v) -> Decimal:
        """Convert numeric values to Decimal for financial precision."""
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))

    # Computed properties for additional metrics
    @property
    def accuracy(self) -> Decimal:
        """Overall accuracy: (TP + TN) / (TP + TN + FP + FN)."""
        total = (
            self.true_positives + self.true_negatives + self.false_positives + self.false_negatives
        )
        if total == 0:
            return Decimal("0")
        return Decimal(str(self.true_positives + self.true_negatives)) / Decimal(str(total))

    @property
    def specificity(self) -> Decimal:
        """Specificity (True Negative Rate): TN / (TN + FP)."""
        denominator = self.true_negatives + self.false_positives
        if denominator == 0:
            return Decimal("0")
        return Decimal(str(self.true_negatives)) / Decimal(str(denominator))

    @property
    def negative_predictive_value(self) -> Decimal:
        """NPV: TN / (TN + FN)."""
        denominator = self.true_negatives + self.false_negatives
        if denominator == 0:
            return Decimal("0")
        return Decimal(str(self.true_negatives)) / Decimal(str(denominator))

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "detector_name": "SpringDetector",
                "detector_version": "1.0",
                "test_timestamp": "2024-12-20T18:30:00Z",
                "dataset_version": "v1",
                "pattern_type": "SPRING",
                "total_samples": 100,
                "true_positives": 76,
                "false_positives": 9,
                "true_negatives": 0,
                "false_negatives": 15,
                "precision": "0.8941",
                "recall": "0.8352",
                "f1_score": "0.8636",
                "confusion_matrix": {"TP": 76, "FP": 9, "TN": 0, "FN": 15},
                "threshold_used": "0.70",
                "passes_nfr_target": True,
                "nfr_target": "0.75",
                "phase_accuracy": "0.9211",
                "campaign_validity_rate": "0.9474",
                "sequential_logic_score": "0.8421",
                "false_phase_rate": "0.0789",
                "confirmation_rate": "0.8158",
                "prerequisite_violation_rate": "0.1579",
            }
        }
    )


class LabeledPattern(BaseModel):
    """
    Labeled pattern dataset entry for accuracy testing (Story 12.2/12.3).

    Represents a single labeled pattern from the test dataset used for validating
    detector accuracy. Each entry contains ground truth labels for pattern identification,
    phase classification, and campaign context.

    Attributes:
        symbol: Trading symbol (e.g., AAPL, MSFT)
        date: Pattern occurrence date
        pattern_type: Pattern type (SPRING, SOS, UTAD, LPS, FALSE_SPRING)
        confidence: Expected confidence score (70-95 range)
        correctness: Ground truth correctness (CORRECT, INCORRECT, AMBIGUOUS)
        phase: Wyckoff phase context (optional)
        campaign_id: Associated campaign identifier (optional)
        notes: Additional context or edge case description (optional)
    """

    symbol: str = Field(..., max_length=20, description="Trading symbol")
    pattern_date: date = Field(..., description="Pattern occurrence date", alias="date")
    pattern_type: str = Field(
        ..., max_length=50, description="Pattern type (SPRING, SOS, UTAD, LPS, FALSE_SPRING)"
    )
    confidence: int = Field(..., ge=0, le=100, description="Confidence score (0-100)")
    correctness: str = Field(
        ..., max_length=20, description="Ground truth (CORRECT, INCORRECT, AMBIGUOUS)"
    )
    phase: Optional[str] = Field(None, max_length=20, description="Wyckoff phase context")
    campaign_id: Optional[UUID] = Field(None, description="Associated campaign ID")
    notes: Optional[str] = Field(None, max_length=500, description="Additional context")

    model_config = ConfigDict(
        populate_by_name=True,  # Allow both 'pattern_date' and 'date' alias
        json_schema_extra={
            "example": {
                "symbol": "AAPL",
                "date": "2024-01-15",
                "pattern_type": "SPRING",
                "confidence": 85,
                "correctness": "CORRECT",
                "phase": "Phase C",
                "notes": "Strong volume climax, tight stop placement",
            }
        },
    )
