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
- SpringRiskAnalyzer: Risk analysis for stop/target/R:R calculation
- ScoreResult: Individual scoring method result
- RiskConfig: Configuration for risk calculations

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

Risk Analysis:
--------------
>>> from src.pattern_engine.detectors.spring import SpringRiskAnalyzer
>>> analyzer = SpringRiskAnalyzer()
>>> profile = analyzer.analyze(candidate, trading_range)
>>> print(f"R:R Ratio: {profile.risk_reward_ratio}")

FR Requirements:
----------------
- FR4: Spring detection (0-5% penetration below Creek)
- FR12: Volume validation (<0.7x average)
- FR16: Position sizing based on risk profile
- FR17: Structural stop loss placement
"""

from src.pattern_engine.detectors.spring.confidence_scorer import (
    ComponentScores,
    ConfidenceResult,
    ScoreResult,
    SpringConfidenceScorer,
)
from src.pattern_engine.detectors.spring.models import (
    SpringCandidate,
    SpringRiskProfile,
)
from src.pattern_engine.detectors.spring.risk_analyzer import (
    DEFAULT_RISK_CONFIG,
    RiskConfig,
    SpringRiskAnalyzer,
)

__all__ = [
    "SpringCandidate",
    "SpringRiskProfile",
    "SpringConfidenceScorer",
    "SpringRiskAnalyzer",
    "ScoreResult",
    "ConfidenceResult",
    "ComponentScores",
    "RiskConfig",
    "DEFAULT_RISK_CONFIG",
]
