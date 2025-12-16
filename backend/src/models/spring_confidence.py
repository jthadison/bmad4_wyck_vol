"""
Spring confidence scoring data model.

This module defines the SpringConfidence dataclass which represents the
calculated confidence score and component breakdown for a Spring pattern.

Purpose:
--------
Quantify spring quality using multi-dimensional scoring to filter out
marginal springs and ensure only high-probability setups (70%+ confidence)
generate trading signals (FR4).

Scoring Formula (Team-Approved 2025-11-03):
--------------------------------------------
Base Components (100 points):
- Volume Quality: 40 points (most important indicator)
- Penetration Depth: 35 points (critical for spring quality)
- Recovery Speed: 25 points (demand strength indicator)
- Test Confirmation: 20 points (FR13 requirement)

Bonuses (+20 points max):
- Creek Strength Bonus: +10 points (strong support quality)
- Volume Trend Bonus: +10 points (declining volume pattern)

Total: 120 points possible, capped at 100 for final score

FR4 Requirement:
----------------
Minimum 70% confidence required for signal generation.
Springs scoring <70% are rejected.

Usage:
------
>>> from src.pattern_engine.detectors.spring_detector import calculate_spring_confidence
>>>
>>> confidence = calculate_spring_confidence(
>>>     spring=spring,
>>>     creek=creek_level,
>>>     previous_tests=[test1, test2]  # Optional
>>> )
>>>
>>> print(f"Confidence: {confidence.total_score}%")
>>> print(f"Quality Tier: {confidence.quality_tier}")
>>> print(f"Components: {confidence.component_scores}")

Author: Generated for Story 5.4
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SpringConfidence(BaseModel):
    """
    Confidence score and component breakdown for Spring pattern quality assessment.

    Attributes:
        total_score: Final confidence score 0-100 (capped from possible 120)
        component_scores: Dict with breakdown by component
        quality_tier: EXCELLENT (90-100) / GOOD (80-89) / ACCEPTABLE (70-79) / REJECTED (<70)

    Component Scores Dict Keys:
        - volume_quality: 0-40 points
        - penetration_depth: 0-35 points
        - recovery_speed: 0-25 points
        - test_confirmation: 0-20 points
        - creek_strength_bonus: 0-10 points
        - volume_trend_bonus: 0-10 points
        - raw_total: Sum before capping (0-120)

    Example:
        >>> confidence = SpringConfidence(
        ...     total_score=95,
        ...     component_scores={
        ...         "volume_quality": 40,
        ...         "penetration_depth": 35,
        ...         "recovery_speed": 25,
        ...         "test_confirmation": 20,
        ...         "creek_strength_bonus": 10,
        ...         "volume_trend_bonus": 10,
        ...         "raw_total": 140
        ...     },
        ...     quality_tier="EXCELLENT"
        ... )
        >>> print(f"Spring confidence: {confidence.total_score}% ({confidence.quality_tier})")
    """

    total_score: int = Field(
        ..., ge=0, le=100, description="Final confidence score 0-100 (capped from possible 120)"
    )
    component_scores: dict[str, int] = Field(
        ..., description="Breakdown by component (volume, penetration, recovery, test, bonuses)"
    )
    quality_tier: str = Field(
        ..., description="EXCELLENT (90-100) / GOOD (80-89) / ACCEPTABLE (70-79) / REJECTED (<70)"
    )

    @property
    def meets_threshold(self) -> bool:
        """
        Check if confidence meets FR4 minimum threshold (70%).

        Returns:
            bool: True if total_score >= 70, False otherwise
        """
        return self.total_score >= 70

    @property
    def is_excellent(self) -> bool:
        """
        Check if spring is excellent quality (90-100%).

        Returns:
            bool: True if total_score >= 90
        """
        return self.total_score >= 90

    @property
    def is_good(self) -> bool:
        """
        Check if spring is good quality (80-89%).

        Returns:
            bool: True if total_score in range 80-89
        """
        return 80 <= self.total_score < 90

    @property
    def is_acceptable(self) -> bool:
        """
        Check if spring is acceptable quality (70-79%).

        Returns:
            bool: True if total_score in range 70-79
        """
        return 70 <= self.total_score < 80
