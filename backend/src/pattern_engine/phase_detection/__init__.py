"""
Wyckoff Phase Detection Package.

Provides unified phase detection for Wyckoff accumulation/distribution analysis.

Usage:
    from pattern_engine.phase_detection import PhaseClassifier, PhaseType

    classifier = PhaseClassifier()
    result = classifier.classify(ohlcv_data)
    print(f"Current phase: {result.phase.value}, confidence: {result.confidence}")

Note:
    This package consolidates functionality from phase_detector.py and
    phase_detector_v2.py. The old modules are deprecated and will be
    removed in a future version.

Package Structure:
    - types.py: Core type definitions (PhaseType, EventType, dataclasses)
    - event_detectors.py: Wyckoff event detection classes
    - phase_classifier.py: Phase classification logic
    - confidence_scorer.py: Confidence scoring for classifications
"""

from .confidence_scorer import (
    PhaseConfidenceScorer,
    ScoringFactors,
)
from .event_detectors import (
    AutomaticRallyDetector,
    BaseEventDetector,
    LastPointOfSupportDetector,
    SecondaryTestDetector,
    SellingClimaxDetector,
    SignOfStrengthDetector,
    SpringDetector,
)
from .phase_classifier import PhaseClassifier
from .types import (
    DetectionConfig,
    EventType,
    PhaseEvent,
    PhaseResult,
    PhaseType,
)

__all__ = [
    # Types
    "PhaseType",
    "EventType",
    "PhaseEvent",
    "PhaseResult",
    "DetectionConfig",
    # Event Detectors
    "BaseEventDetector",
    "SellingClimaxDetector",
    "AutomaticRallyDetector",
    "SecondaryTestDetector",
    "SpringDetector",
    "SignOfStrengthDetector",
    "LastPointOfSupportDetector",
    # Classification
    "PhaseClassifier",
    # Scoring
    "PhaseConfidenceScorer",
    "ScoringFactors",
]
