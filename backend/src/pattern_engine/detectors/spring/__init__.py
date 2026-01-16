"""
Spring Pattern Detection Package

This package provides Spring pattern detection for Wyckoff accumulation analysis.
Springs are high-probability long entry signals representing shakeouts below
Creek support with low volume and rapid recovery.

Public Exports:
---------------
- SpringDetectorCore: Core detector with dependency injection (Story 18.8.4)
- DetectionConfig: Configuration for detection parameters
- SpringCandidate: Intermediate detection candidate
- SpringRiskProfile: Risk analysis for position sizing
- SpringConfidenceScorer: Confidence scoring with testable methods
- SpringRiskAnalyzer: Risk analysis for stop/target/R:R calculation
- ScoreResult: Individual scoring method result
- RiskConfig: Configuration for risk calculations
- analyze_spring_timing: Timing analysis for spring patterns

Usage:
------
>>> from src.pattern_engine.detectors.spring import SpringDetectorCore
>>> from src.pattern_engine.detectors.spring import SpringConfidenceScorer, SpringRiskAnalyzer
>>>
>>> scorer = SpringConfidenceScorer()
>>> analyzer = SpringRiskAnalyzer()
>>> detector = SpringDetectorCore(scorer, analyzer)
>>> spring = detector.detect(trading_range, bars, phase, symbol)

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

Timing Analysis:
----------------
>>> from src.pattern_engine.detectors.spring import analyze_spring_timing
>>> timing, intervals, avg = analyze_spring_timing(springs)
>>> print(f"Timing: {timing}, Avg interval: {avg} bars")

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
from src.pattern_engine.detectors.spring.detector import (
    DetectionConfig,
    SpringDetectorCore,
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
from src.pattern_engine.detectors.spring.timing_analyzer import (
    analyze_spring_timing,
)

__all__ = [
    # Core detector (Story 18.8.4)
    "SpringDetectorCore",
    "DetectionConfig",
    # Models
    "SpringCandidate",
    "SpringRiskProfile",
    # Confidence scoring (Story 18.8.2)
    "SpringConfidenceScorer",
    "ScoreResult",
    "ConfidenceResult",
    "ComponentScores",
    # Risk analysis (Story 18.8.3)
    "SpringRiskAnalyzer",
    "RiskConfig",
    "DEFAULT_RISK_CONFIG",
    # Timing analysis (Story 18.8.4)
    "analyze_spring_timing",
]
