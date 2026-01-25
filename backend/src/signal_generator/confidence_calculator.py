"""
Signal Confidence Scoring Calculator (Story 19.6)

Purpose:
--------
Provides a deterministic confidence scoring system that evaluates signal quality
based on multiple weighted factors: pattern quality, phase strength, and volume
confirmation.

Scoring Weights (Per Story 19.6):
---------------------------------
- Pattern Quality: 40%
- Phase Strength: 30%
- Volume Confirmation: 30%

Grade Mapping:
--------------
- A+ : 90-100%
- A  : 80-89%
- B  : 70-79%
- C  : 60-69%
- F  : <60%

Features:
---------
- Deterministic: Same inputs always produce same output
- Configurable threshold: Default 70%, can be customized
- Pattern-specific volume scoring
- Grade classification for quick quality assessment

Integration:
------------
- Story 19.5: Integrates with validation pipeline
- Story 5.4, 6.5: Uses pattern confidence scoring
- Story 4.5: Uses phase confidence

Author: Story 19.6
"""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class ConfidenceGrade(str, Enum):
    """Signal confidence grade classification."""

    A_PLUS = "A+"
    A = "A"
    B = "B"
    C = "C"
    F = "F"


class ConfidenceResult(BaseModel):
    """
    Result of confidence calculation.

    Contains the overall confidence score, grade classification,
    and breakdown of component scores.

    Attributes:
        confidence_score: Overall confidence 0-100
        grade: Letter grade (A+, A, B, C, F)
        pattern_quality_score: Weighted pattern contribution
        phase_strength_score: Weighted phase contribution
        volume_score: Weighted volume contribution
        meets_threshold: Whether score meets minimum threshold
        threshold: Configured minimum threshold
    """

    confidence_score: float = Field(
        ..., ge=0.0, le=100.0, description="Overall confidence score 0-100"
    )
    grade: ConfidenceGrade = Field(..., description="Letter grade classification")
    pattern_quality_score: float = Field(
        ..., ge=0.0, le=100.0, description="Raw pattern quality input (0-100)"
    )
    phase_strength_score: float = Field(
        ..., ge=0.0, le=100.0, description="Raw phase strength input (0-100)"
    )
    volume_score: float = Field(
        ..., ge=0.0, le=100.0, description="Calculated volume confirmation score (0-100)"
    )
    meets_threshold: bool = Field(..., description="Whether score meets minimum threshold")
    threshold: float = Field(..., description="Configured minimum threshold")

    @property
    def rejection_reason(self) -> str | None:
        """Return rejection reason if below threshold."""
        if not self.meets_threshold:
            return (
                f"Below minimum confidence threshold "
                f"({self.confidence_score:.1f}% < {self.threshold:.1f}%)"
            )
        return None


# Weight constants per Story 19.6 specification
PATTERN_WEIGHT: float = 0.40
PHASE_WEIGHT: float = 0.30
VOLUME_WEIGHT: float = 0.30

# Default minimum confidence threshold
DEFAULT_MIN_THRESHOLD: float = 70.0


def get_grade(confidence: float) -> ConfidenceGrade:
    """
    Map confidence score to letter grade.

    Grade Ranges:
    - A+ : 90-100%
    - A  : 80-89%
    - B  : 70-79%
    - C  : 60-69%
    - F  : <60%

    Parameters:
    -----------
    confidence : float
        Confidence score 0-100

    Returns:
    --------
    ConfidenceGrade
        Letter grade classification
    """
    if confidence >= 90:
        return ConfidenceGrade.A_PLUS
    elif confidence >= 80:
        return ConfidenceGrade.A
    elif confidence >= 70:
        return ConfidenceGrade.B
    elif confidence >= 60:
        return ConfidenceGrade.C
    else:
        return ConfidenceGrade.F


def calculate_volume_score(
    pattern_type: Literal["SPRING", "SOS", "LPS", "UTAD", "SC", "AR"],
    volume_ratio: float,
) -> float:
    """
    Calculate volume confirmation score based on pattern type.

    Score ranges:
    - 1.0 (100%): Perfect confirmation
    - 0.9 (90%): Excellent confirmation
    - 0.75 (75%): Good confirmation
    - 0.6 (60%): Borderline confirmation
    - 0.0 (0%): Volume violation

    SPRING/UTAD: Lower volume is better (shakeout on low volume)
    SOS: Higher volume is better (breakout on high volume)
    LPS: Moderate volume preferred (healthy retest)
    SC: Ultra-high volume required (climax selling)
    AR: Moderate-high volume (automatic rally)

    Parameters:
    -----------
    pattern_type : str
        One of SPRING, SOS, LPS, UTAD, SC, AR
    volume_ratio : float
        Volume relative to average (e.g., 0.4 = 40% of average, 2.0 = 200%)

    Returns:
    --------
    float
        Volume score 0.0-1.0
    """
    if pattern_type == "SPRING":
        # Spring: Lower volume is better (shakeout)
        # Ideal: < 0.4x average, Violation: >= 0.7x
        if volume_ratio <= 0.4:
            return 1.0
        elif volume_ratio <= 0.5:
            return 0.9
        elif volume_ratio <= 0.6:
            return 0.75
        elif volume_ratio < 0.7:
            return 0.6
        else:
            return 0.0  # Violation

    elif pattern_type == "SOS":
        # SOS Breakout: Higher volume is better
        # Ideal: >= 2.0x average, Violation: < 1.5x
        if volume_ratio >= 2.0:
            return 1.0
        elif volume_ratio >= 1.8:
            return 0.9
        elif volume_ratio >= 1.6:
            return 0.75
        elif volume_ratio >= 1.5:
            return 0.6
        else:
            return 0.0  # Violation

    elif pattern_type == "LPS":
        # LPS Retest: Moderate volume preferred (healthy pullback)
        # Best: 0.6-1.0x average
        if 0.6 <= volume_ratio <= 1.0:
            return 1.0
        elif 0.5 <= volume_ratio < 0.6 or 1.0 < volume_ratio <= 1.2:
            return 0.85
        elif 0.4 <= volume_ratio < 0.5 or 1.2 < volume_ratio <= 1.4:
            return 0.7
        elif volume_ratio < 0.4 or volume_ratio > 1.4:
            return 0.5
        else:
            return 0.5

    elif pattern_type == "UTAD":
        # UTAD: Lower volume is better (failed upthrust)
        # Similar to Spring but for distribution
        if volume_ratio <= 0.4:
            return 1.0
        elif volume_ratio <= 0.5:
            return 0.9
        elif volume_ratio <= 0.6:
            return 0.75
        elif volume_ratio < 0.7:
            return 0.6
        else:
            return 0.0  # Violation

    elif pattern_type == "SC":
        # Selling Climax: Ultra-high volume required
        # Ideal: >= 3.0x average
        if volume_ratio >= 3.0:
            return 1.0
        elif volume_ratio >= 2.5:
            return 0.9
        elif volume_ratio >= 2.0:
            return 0.75
        elif volume_ratio >= 1.5:
            return 0.6
        else:
            return 0.3  # Weak climax

    elif pattern_type == "AR":
        # Automatic Rally: Moderate-high volume
        # Ideal: 1.2-1.8x average
        if 1.2 <= volume_ratio <= 1.8:
            return 1.0
        elif 1.0 <= volume_ratio < 1.2 or 1.8 < volume_ratio <= 2.0:
            return 0.85
        elif 0.8 <= volume_ratio < 1.0 or 2.0 < volume_ratio <= 2.5:
            return 0.7
        else:
            return 0.5

    else:
        # Unknown pattern type - return neutral score
        return 0.5


class ConfidenceCalculator:
    """
    Signal confidence scoring calculator.

    Evaluates signal quality using weighted combination of:
    - Pattern quality (40%)
    - Phase strength (30%)
    - Volume confirmation (30%)

    Supports configurable minimum threshold for auto-rejection.

    Example Usage:
    --------------
    >>> calculator = ConfidenceCalculator(min_threshold=70.0)
    >>> result = calculator.calculate(
    ...     pattern_quality=0.95,
    ...     phase_strength=0.90,
    ...     pattern_type="SPRING",
    ...     volume_ratio=0.4
    ... )
    >>> print(f"Score: {result.confidence_score}% Grade: {result.grade}")
    Score: 95.0% Grade: A+
    >>> print(f"Approved: {result.meets_threshold}")
    Approved: True
    """

    def __init__(self, min_threshold: float = DEFAULT_MIN_THRESHOLD) -> None:
        """
        Initialize calculator with minimum confidence threshold.

        Parameters:
        -----------
        min_threshold : float
            Minimum confidence threshold for approval (default 70.0)
        """
        if not 0.0 <= min_threshold <= 100.0:
            raise ValueError(f"min_threshold must be 0-100, got {min_threshold}")
        self.min_threshold = min_threshold

    def calculate(
        self,
        pattern_quality: float,
        phase_strength: float,
        pattern_type: Literal["SPRING", "SOS", "LPS", "UTAD", "SC", "AR"],
        volume_ratio: float,
    ) -> ConfidenceResult:
        """
        Calculate confidence score from component inputs.

        Formula:
        --------
        raw_score = (pattern_quality * 0.40 + phase_strength * 0.30 + volume_score * 0.30)
        confidence = round(raw_score * 100, 2)

        Parameters:
        -----------
        pattern_quality : float
            Pattern detection confidence 0.0-1.0
        phase_strength : float
            Phase identification confidence 0.0-1.0
        pattern_type : str
            Pattern type for volume scoring (SPRING, SOS, LPS, UTAD, SC, AR)
        volume_ratio : float
            Volume relative to average (e.g., 0.4 = 40% of average)

        Returns:
        --------
        ConfidenceResult
            Complete confidence calculation result

        Raises:
        -------
        ValueError
            If pattern_quality or phase_strength outside 0.0-1.0 range
        """
        # Validate inputs
        if not 0.0 <= pattern_quality <= 1.0:
            raise ValueError(f"pattern_quality must be 0.0-1.0, got {pattern_quality}")
        if not 0.0 <= phase_strength <= 1.0:
            raise ValueError(f"phase_strength must be 0.0-1.0, got {phase_strength}")
        if volume_ratio < 0.0:
            raise ValueError(f"volume_ratio must be non-negative, got {volume_ratio}")

        # Calculate volume score
        volume_score = calculate_volume_score(pattern_type, volume_ratio)

        # Calculate weighted confidence
        raw_score = (
            pattern_quality * PATTERN_WEIGHT
            + phase_strength * PHASE_WEIGHT
            + volume_score * VOLUME_WEIGHT
        )

        # Convert to 0-100 scale and round
        confidence_score = round(raw_score * 100, 2)

        # Get grade
        grade = get_grade(confidence_score)

        # Check threshold
        meets_threshold = confidence_score >= self.min_threshold

        return ConfidenceResult(
            confidence_score=confidence_score,
            grade=grade,
            pattern_quality_score=round(pattern_quality * 100, 2),
            phase_strength_score=round(phase_strength * 100, 2),
            volume_score=round(volume_score * 100, 2),
            meets_threshold=meets_threshold,
            threshold=self.min_threshold,
        )

    def calculate_from_scores(
        self,
        pattern_quality: float,
        phase_strength: float,
        volume_score: float,
    ) -> ConfidenceResult:
        """
        Calculate confidence from pre-calculated volume score.

        Use this when volume score is already computed (e.g., from validation).

        Parameters:
        -----------
        pattern_quality : float
            Pattern detection confidence 0.0-1.0
        phase_strength : float
            Phase identification confidence 0.0-1.0
        volume_score : float
            Pre-calculated volume confirmation score 0.0-1.0

        Returns:
        --------
        ConfidenceResult
            Complete confidence calculation result
        """
        # Validate inputs
        if not 0.0 <= pattern_quality <= 1.0:
            raise ValueError(f"pattern_quality must be 0.0-1.0, got {pattern_quality}")
        if not 0.0 <= phase_strength <= 1.0:
            raise ValueError(f"phase_strength must be 0.0-1.0, got {phase_strength}")
        if not 0.0 <= volume_score <= 1.0:
            raise ValueError(f"volume_score must be 0.0-1.0, got {volume_score}")

        # Calculate weighted confidence
        raw_score = (
            pattern_quality * PATTERN_WEIGHT
            + phase_strength * PHASE_WEIGHT
            + volume_score * VOLUME_WEIGHT
        )

        # Convert to 0-100 scale and round
        confidence_score = round(raw_score * 100, 2)

        # Get grade
        grade = get_grade(confidence_score)

        # Check threshold
        meets_threshold = confidence_score >= self.min_threshold

        return ConfidenceResult(
            confidence_score=confidence_score,
            grade=grade,
            pattern_quality_score=round(pattern_quality * 100, 2),
            phase_strength_score=round(phase_strength * 100, 2),
            volume_score=round(volume_score * 100, 2),
            meets_threshold=meets_threshold,
            threshold=self.min_threshold,
        )


# Convenience function for one-off calculations
def calculate_confidence(
    pattern_quality: float,
    phase_strength: float,
    volume_score: float,
    min_threshold: float = DEFAULT_MIN_THRESHOLD,
) -> ConfidenceResult:
    """
    Convenience function for one-off confidence calculation.

    Parameters:
    -----------
    pattern_quality : float
        Pattern detection confidence 0.0-1.0
    phase_strength : float
        Phase identification confidence 0.0-1.0
    volume_score : float
        Volume confirmation score 0.0-1.0
    min_threshold : float
        Minimum threshold for approval (default 70.0)

    Returns:
    --------
    ConfidenceResult
        Complete confidence calculation result

    Example:
    --------
    >>> result = calculate_confidence(
    ...     pattern_quality=0.95,
    ...     phase_strength=0.90,
    ...     volume_score=1.0
    ... )
    >>> print(f"Score: {result.confidence_score}%")
    Score: 95.0%
    """
    calculator = ConfidenceCalculator(min_threshold=min_threshold)
    return calculator.calculate_from_scores(pattern_quality, phase_strength, volume_score)
