"""
Wyckoff Phase Detection Package.

Provides unified phase detection for Wyckoff accumulation/distribution analysis.

Usage:
    from pattern_engine.phase_detection import PhaseClassifier, PhaseType

    classifier = PhaseClassifier()
    result = classifier.classify(ohlcv_data)
    print(f"Current phase: {result.phase.value}, confidence: {result.confidence}")

Migration Guide (Story 22.7c)
=============================
This package replaces the deprecated modules:
- pattern_engine.phase_detector (deprecated v0.2.0, removed v0.3.0)
- pattern_engine.phase_detector_v2 (deprecated v0.2.0, removed v0.3.0)

Migration mappings:
    # Old imports (deprecated):
    from pattern_engine.phase_detector import detect_selling_climax
    from pattern_engine.phase_detector_v2 import PhaseDetector

    # New imports (recommended):
    from pattern_engine.phase_detection import SellingClimaxDetector
    from pattern_engine.phase_detection import PhaseClassifier

    # Types are already available:
    from pattern_engine.phase_detection import PhaseType, EventType, PhaseResult

Note:
    Full implementation pending Story 22.7b (Migrate Phase Detector Logic).
    Until then, deprecated modules will continue to work via facades.

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
