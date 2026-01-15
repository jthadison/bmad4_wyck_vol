"""
Spring Pattern Detection Package

This package provides Spring pattern detection for Wyckoff accumulation analysis.
Springs are high-probability long entry signals representing shakeouts below
Creek support with low volume and rapid recovery.

Public Exports:
---------------
- SpringCandidate: Intermediate detection candidate
- SpringRiskProfile: Risk analysis for position sizing
- SpringConfidenceScorer: Confidence scoring with testable methods
- ScoreResult: Individual scoring method result

Usage:
------
>>> from src.pattern_engine.detectors.spring import SpringCandidate, SpringRiskProfile
>>> from decimal import Decimal
>>>
>>> candidate = SpringCandidate(
...     bar_index=25,
...     bar=ohlcv_bar,
...     penetration_pct=Decimal("0.02"),
...     recovery_pct=Decimal("0.015"),
...     creek_level=Decimal("100.00")
... )

Confidence Scoring:
-------------------
>>> from src.pattern_engine.detectors.spring import SpringConfidenceScorer
>>> scorer = SpringConfidenceScorer()
>>> result = scorer.calculate(spring, creek, previous_tests)
>>> print(f"Confidence: {result['total_score']}%")

FR Requirements:
----------------
- FR4: Spring detection (0-5% penetration below Creek)
- FR12: Volume validation (<0.7x average)
- FR16: Position sizing based on risk profile
"""

from src.pattern_engine.detectors.spring.confidence_scorer import (
    ScoreResult,
    SpringConfidenceScorer,
)
from src.pattern_engine.detectors.spring.models import (
    SpringCandidate,
    SpringRiskProfile,
)

__all__ = [
    "SpringCandidate",
    "SpringRiskProfile",
    "SpringConfidenceScorer",
    "ScoreResult",
]
