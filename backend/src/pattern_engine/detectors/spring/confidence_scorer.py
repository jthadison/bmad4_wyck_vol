"""
Spring Pattern Confidence Scorer

This module provides confidence scoring for Spring patterns with independent,
testable scoring methods for each factor.

Scoring Components:
-------------------
- Volume Quality (40 pts): Low volume proves supply exhaustion
- Penetration Depth (35 pts): Optimal shakeout depth 1-2%
- Recovery Speed (25 pts): Faster recovery = stronger demand
- Test Confirmation (20 pts): FR13 requirement
- Creek Strength Bonus (10 pts): Strong support quality
- Volume Trend Bonus (10 pts): Declining volume pattern

FR Requirements:
----------------
- FR4: Spring detection (0-5% penetration below Creek)
- FR12: Volume validation (<0.7x average)
- FR13: Test confirmation required for signal generation

Author: Story 18.8.2 - Spring Confidence Scorer Extraction
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, TypedDict

import structlog

if TYPE_CHECKING:
    from src.models.creek_level import CreekLevel
    from src.models.spring import Spring
    from src.models.test import Test

logger = structlog.get_logger(__name__)


@dataclass
class ScoreResult:
    """Result from individual scoring method."""

    points: int
    quality: str
    max_points: int


class ComponentScores(TypedDict):
    """Component scores breakdown from confidence calculation."""

    volume_quality: int
    penetration_depth: int
    recovery_speed: int
    test_confirmation: int
    creek_strength_bonus: int
    volume_trend_bonus: int
    raw_total: int


class ConfidenceResult(TypedDict):
    """Result from SpringConfidenceScorer.calculate()."""

    total_score: int
    component_scores: ComponentScores
    quality_tier: str


class SpringConfidenceScorer:
    """
    Confidence scorer for Spring patterns with independent scoring methods.

    Each scoring method is self-contained and testable. The calculate() method
    combines all scores to produce the final confidence.

    Scoring Formula:
        Base Components (120 points max):
        - Volume Quality: 40 points
        - Penetration Depth: 35 points
        - Recovery Speed: 25 points
        - Test Confirmation: 20 points

        Bonuses:
        - Creek Strength: +10 points
        - Volume Trend: +10 points

        Final score capped at 100.

    Example:
        >>> scorer = SpringConfidenceScorer()
        >>> score = scorer.calculate(spring, creek, previous_tests)
        >>> print(f"Confidence: {score.total_score}%")
    """

    # Volume thresholds
    VOLUME_EXCEPTIONAL = Decimal("0.3")
    VOLUME_EXCELLENT = Decimal("0.4")
    VOLUME_IDEAL = Decimal("0.5")
    VOLUME_ACCEPTABLE = Decimal("0.6")

    # Penetration thresholds
    PENETRATION_IDEAL_MIN = Decimal("0.01")
    PENETRATION_IDEAL_MAX = Decimal("0.02")
    PENETRATION_GOOD_MAX = Decimal("0.03")
    PENETRATION_ACCEPTABLE_MAX = Decimal("0.04")

    def _score_volume(self, volume_ratio: Decimal) -> ScoreResult:
        """
        Score volume quality (40 points max).

        Low volume proves supply exhaustion - most important indicator.

        Args:
            volume_ratio: Volume relative to average (e.g., 0.3 = 30% of average)

        Returns:
            ScoreResult with points, quality tier, and max points
        """
        if volume_ratio < self.VOLUME_EXCEPTIONAL:
            return ScoreResult(points=40, quality="EXCEPTIONAL", max_points=40)
        elif volume_ratio < self.VOLUME_EXCELLENT:
            return ScoreResult(points=30, quality="EXCELLENT", max_points=40)
        elif volume_ratio < self.VOLUME_IDEAL:
            return ScoreResult(points=20, quality="IDEAL", max_points=40)
        elif volume_ratio < self.VOLUME_ACCEPTABLE:
            return ScoreResult(points=10, quality="ACCEPTABLE", max_points=40)
        else:
            return ScoreResult(points=5, quality="MARGINAL", max_points=40)

    def _score_penetration(self, penetration_pct: Decimal) -> ScoreResult:
        """
        Score penetration depth (35 points max).

        Optimal shakeout depth is 1-2% below Creek level. Shallow penetrations
        (<1%) are still valid but less convincing as shakeouts.

        Args:
            penetration_pct: Penetration percentage (e.g., 0.015 = 1.5%)

        Returns:
            ScoreResult with points, quality tier, and max points
        """
        if self.PENETRATION_IDEAL_MIN <= penetration_pct < self.PENETRATION_IDEAL_MAX:
            return ScoreResult(points=35, quality="IDEAL", max_points=35)
        elif penetration_pct < self.PENETRATION_IDEAL_MIN:
            # Shallow penetration: valid spring but less convincing shakeout
            return ScoreResult(points=20, quality="SHALLOW", max_points=35)
        elif penetration_pct < self.PENETRATION_GOOD_MAX:
            return ScoreResult(points=25, quality="GOOD", max_points=35)
        elif penetration_pct < self.PENETRATION_ACCEPTABLE_MAX:
            return ScoreResult(points=15, quality="ACCEPTABLE", max_points=35)
        else:
            return ScoreResult(points=5, quality="DEEP", max_points=35)

    def _score_recovery(self, recovery_bars: int) -> ScoreResult:
        """
        Score recovery speed (25 points max).

        Faster recovery indicates stronger demand absorption.

        Args:
            recovery_bars: Number of bars to recover above Creek

        Returns:
            ScoreResult with points, quality tier, and max points
        """
        if recovery_bars == 1:
            return ScoreResult(points=25, quality="IMMEDIATE", max_points=25)
        elif recovery_bars == 2:
            return ScoreResult(points=20, quality="STRONG", max_points=25)
        elif recovery_bars == 3:
            return ScoreResult(points=15, quality="GOOD", max_points=25)
        else:
            return ScoreResult(points=10, quality="SLOW", max_points=25)

    def _score_follow_through(self, has_test: bool) -> ScoreResult:
        """
        Score test confirmation / follow-through (20 points).

        Test confirmation is FR13 requirement for signal generation.

        Args:
            has_test: Whether test confirmation exists

        Returns:
            ScoreResult with points, quality tier, and max points
        """
        if has_test:
            return ScoreResult(points=20, quality="PRESENT", max_points=20)
        return ScoreResult(points=0, quality="NONE", max_points=20)

    def _score_creek_strength(self, creek_strength: int) -> ScoreResult:
        """
        Score Creek support strength bonus (10 points max).

        Strong support indicates more reliable spring pattern.

        Args:
            creek_strength: Creek strength score (0-100)

        Returns:
            ScoreResult with points, quality tier, and max points
        """
        if creek_strength >= 80:
            return ScoreResult(points=10, quality="EXCELLENT", max_points=10)
        elif creek_strength >= 70:
            return ScoreResult(points=7, quality="STRONG", max_points=10)
        elif creek_strength >= 60:
            return ScoreResult(points=5, quality="MODERATE", max_points=10)
        return ScoreResult(points=0, quality="WEAK", max_points=10)

    def _score_volume_trend(
        self, spring_volume: Decimal, previous_tests: list[Test]
    ) -> ScoreResult:
        """
        Score volume trend bonus (10 points max).

        Declining volume from previous tests indicates bullish accumulation.

        Args:
            spring_volume: Spring bar volume ratio
            previous_tests: List of previous Test patterns

        Returns:
            ScoreResult with points, quality tier, and max points
        """
        if len(previous_tests) < 2:
            return ScoreResult(points=0, quality="INSUFFICIENT_DATA", max_points=10)

        prev_volumes = [test.volume_ratio for test in previous_tests[-2:]]
        avg_prev_volume = sum(prev_volumes, Decimal("0")) / len(prev_volumes)

        if avg_prev_volume <= Decimal("0"):
            return ScoreResult(points=0, quality="INVALID_DATA", max_points=10)

        volume_change_pct = (avg_prev_volume - spring_volume) / avg_prev_volume

        if volume_change_pct >= Decimal("0.2"):
            return ScoreResult(points=10, quality="DECLINING", max_points=10)
        elif volume_change_pct >= Decimal("-0.2"):
            return ScoreResult(points=5, quality="STABLE", max_points=10)
        return ScoreResult(points=0, quality="RISING", max_points=10)

    def _determine_quality_tier(self, score: int) -> str:
        """
        Determine quality tier from final score.

        Args:
            score: Final confidence score (0-100)

        Returns:
            Quality tier string
        """
        if score >= 90:
            return "EXCELLENT"
        elif score >= 80:
            return "GOOD"
        elif score >= 70:
            return "ACCEPTABLE"
        return "REJECTED"

    def calculate(
        self,
        spring: Spring,
        creek: CreekLevel,
        previous_tests: list[Test] | None = None,
    ) -> ConfidenceResult:
        """
        Calculate total confidence score for Spring pattern.

        Combines all scoring components to produce final confidence.

        Args:
            spring: Spring pattern to score
            creek: Creek level that spring penetrated
            previous_tests: Optional list of previous tests for trend analysis

        Returns:
            ConfidenceResult with total_score, component_scores, and quality_tier

        Raises:
            ValueError: If spring or creek is None
        """
        if spring is None:
            raise ValueError("Spring required for confidence calculation")
        if creek is None:
            raise ValueError("Creek level required for confidence calculation")

        if previous_tests is None:
            previous_tests = []

        # Score each component
        volume_score = self._score_volume(spring.volume_ratio)
        penetration_score = self._score_penetration(spring.penetration_pct)
        recovery_score = self._score_recovery(spring.recovery_bars)
        follow_through_score = self._score_follow_through(len(previous_tests) > 0)
        creek_score = self._score_creek_strength(creek.strength_score)
        trend_score = self._score_volume_trend(spring.volume_ratio, previous_tests)

        # Calculate raw total
        raw_total = (
            volume_score.points
            + penetration_score.points
            + recovery_score.points
            + follow_through_score.points
            + creek_score.points
            + trend_score.points
        )

        # Cap at 100
        final_score = min(raw_total, 100)
        quality_tier = self._determine_quality_tier(final_score)

        component_scores = {
            "volume_quality": volume_score.points,
            "penetration_depth": penetration_score.points,
            "recovery_speed": recovery_score.points,
            "test_confirmation": follow_through_score.points,
            "creek_strength_bonus": creek_score.points,
            "volume_trend_bonus": trend_score.points,
            "raw_total": raw_total,
        }

        logger.debug(
            "spring_confidence_calculated",
            total_score=final_score,
            quality_tier=quality_tier,
            component_scores=component_scores,
        )

        return {
            "total_score": final_score,
            "component_scores": component_scores,
            "quality_tier": quality_tier,
        }
