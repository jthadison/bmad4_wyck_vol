"""
Wyckoff phase classification module.

This module provides the PhaseClassifier class for determining the current
Wyckoff phase based on detected events and market structure.

Wired to real implementations (Story 23.1):
- classify_phase from pattern_engine.phase_classifier
- calculate_phase_confidence from pattern_engine._phase_detector_impl
- is_valid_phase_transition from pattern_engine.phase_validator
"""

from typing import Optional

import pandas as pd

from src.models.phase_classification import PhaseClassification, PhaseEvents, WyckoffPhase

from .types import DetectionConfig, EventType, PhaseEvent, PhaseResult, PhaseType

# ============================================================================
# Type mapping: Facade PhaseType <-> Real WyckoffPhase
# ============================================================================

_PHASE_TYPE_TO_WYCKOFF: dict[PhaseType, WyckoffPhase] = {
    PhaseType.A: WyckoffPhase.A,
    PhaseType.B: WyckoffPhase.B,
    PhaseType.C: WyckoffPhase.C,
    PhaseType.D: WyckoffPhase.D,
    PhaseType.E: WyckoffPhase.E,
}

_WYCKOFF_TO_PHASE_TYPE: dict[WyckoffPhase, PhaseType] = {
    v: k for k, v in _PHASE_TYPE_TO_WYCKOFF.items()
}


def _events_to_phase_events(events: list[PhaseEvent]) -> PhaseEvents:
    """Convert facade PhaseEvent list to real PhaseEvents model."""
    sc = None
    ar = None
    sts: list[dict] = []
    spring = None
    sos = None
    lps = None

    for event in events:
        event_dict: dict = {
            "bar_index": event.bar_index,
            "confidence": int(event.confidence * 100),  # Convert 0.0-1.0 to 0-100
            "bar": {
                "timestamp": event.timestamp.isoformat(),
                "close": event.price,
                "volume": event.volume,
            },
            **event.metadata,
        }

        if event.event_type == EventType.SELLING_CLIMAX:
            sc = event_dict
        elif event.event_type == EventType.AUTOMATIC_RALLY:
            ar = event_dict
        elif event.event_type == EventType.SECONDARY_TEST:
            sts.append(event_dict)
        elif event.event_type == EventType.SPRING:
            spring = event_dict
        elif event.event_type == EventType.SIGN_OF_STRENGTH:
            sos = event_dict
        elif event.event_type == EventType.LAST_POINT_OF_SUPPORT:
            lps = event_dict

    return PhaseEvents(
        selling_climax=sc,
        automatic_rally=ar,
        secondary_tests=sts,
        spring=spring,
        sos_breakout=sos,
        last_point_of_support=lps,
    )


def _classification_to_phase_result(
    classification: PhaseClassification,
    events: list[PhaseEvent],
) -> PhaseResult:
    """Convert a real PhaseClassification to facade PhaseResult."""
    phase_type = (
        _WYCKOFF_TO_PHASE_TYPE.get(classification.phase)
        if classification.phase is not None
        else None
    )

    return PhaseResult(
        phase=phase_type,
        confidence=classification.confidence / 100.0,  # Convert 0-100 to 0.0-1.0
        events=events,
        start_bar=classification.phase_start_index,
        duration_bars=classification.duration,
        metadata={
            "trading_allowed": classification.trading_allowed,
            "rejection_reason": classification.rejection_reason,
        },
    )


class PhaseClassifier:
    """
    Classifies market structure into Wyckoff phases.

    The classifier analyzes detected events and price/volume structure to
    determine the current phase of accumulation or distribution.

    Phase Transition Rules:
    -----------------------
    Phase A (Stopping Action):
        - Entry: Selling Climax (SC) detected
        - Events: SC -> AR -> ST
        - Exit: Secondary Test (ST) confirms support

    Phase B (Building Cause):
        - Entry: After Phase A completion
        - Duration: Typically longest phase (min 10 bars)
        - Events: Multiple tests of support/resistance
        - Exit: Spring or UTAD detected

    Phase C (Test):
        - Entry: Spring (accumulation) or UTAD (distribution)
        - Events: Final shakeout/false breakout
        - Exit: Successful test holds support/resistance

    Phase D (Markup/Markdown):
        - Entry: SOS (accumulation) or SOW (distribution)
        - Events: LPS/LPSY as entry opportunities
        - Exit: Price reaches target or exhaustion

    Phase E (Trend Continuation):
        - Entry: Clear trend established
        - Events: Continuation patterns
        - Exit: New accumulation/distribution begins

    Attributes:
        config: Detection configuration parameters
    """

    def __init__(self, config: Optional[DetectionConfig] = None) -> None:
        """
        Initialize the phase classifier.

        Args:
            config: Detection configuration. Uses defaults if not provided.
        """
        self.config = config or DetectionConfig()
        self._current_phase: Optional[PhaseType] = None
        self._phase_start_bar: int = 0
        self._detected_events: list[PhaseEvent] = []

    def classify(
        self,
        ohlcv: pd.DataFrame,
        events: Optional[list[PhaseEvent]] = None,
    ) -> PhaseResult:
        """
        Classify the current Wyckoff phase.

        Analyzes the OHLCV data and detected events to determine which
        phase of the Wyckoff cycle the market is currently in.

        Args:
            ohlcv: DataFrame with columns [timestamp, open, high, low, close, volume]
            events: Optional list of pre-detected events

        Returns:
            PhaseResult with classification and confidence
        """
        from src.pattern_engine.phase_classifier import classify_phase as real_classify_phase

        if events:
            phase_events = _events_to_phase_events(events)
        else:
            phase_events = PhaseEvents()

        # Call real classify_phase
        classification = real_classify_phase(phase_events)

        return _classification_to_phase_result(classification, events or [])

    def _determine_phase_from_events(
        self,
        events: list[PhaseEvent],
        current_bar: int,
    ) -> Optional[PhaseType]:
        """
        Determine phase based on detected events sequence.

        Args:
            events: List of detected events in chronological order
            current_bar: Current bar index for duration calculation

        Returns:
            Classified PhaseType, or None if no phase detected
        """
        from src.pattern_engine.phase_classifier import classify_phase as real_classify_phase

        phase_events = _events_to_phase_events(events)
        classification = real_classify_phase(phase_events, current_bar_index=current_bar)

        if classification.phase is None:
            return None
        return _WYCKOFF_TO_PHASE_TYPE.get(classification.phase)

    def _check_phase_transition(
        self,
        current_phase: PhaseType,
        latest_event: PhaseEvent,
    ) -> Optional[PhaseType]:
        """
        Check if a phase transition should occur.

        Phase transition rules:
        - A -> B: After ST confirmation
        - B -> C: Spring or UTAD detected
        - C -> D: Test holds, SOS/SOW confirmed
        - D -> E: Trend established, LPS/LPSY complete

        Args:
            current_phase: The current classified phase
            latest_event: Most recently detected event

        Returns:
            New phase if transition occurs, None otherwise
        """
        from src.pattern_engine.phase_validator import is_valid_phase_transition

        # Determine proposed phase from the latest event
        proposed = self._determine_phase_from_events(
            self._detected_events + [latest_event],
            latest_event.bar_index,
        )
        if proposed is None or proposed == current_phase:
            return None

        # Validate the transition using the real validator
        current_wyckoff = _PHASE_TYPE_TO_WYCKOFF[current_phase]
        proposed_wyckoff = _PHASE_TYPE_TO_WYCKOFF[proposed]

        if is_valid_phase_transition(current_wyckoff, proposed_wyckoff):
            return proposed
        return None

    def _validate_phase_duration(
        self,
        phase: PhaseType,
        duration_bars: int,
    ) -> bool:
        """
        Validate that phase has met minimum duration requirements.

        Args:
            phase: Phase to validate
            duration_bars: Number of bars in the phase

        Returns:
            True if duration is valid, False otherwise
        """
        return duration_bars >= self.config.min_phase_duration

    def _calculate_phase_confidence(
        self,
        phase: PhaseType,
        events: list[PhaseEvent],
        duration_bars: int,
    ) -> float:
        """
        Calculate confidence score for phase classification.

        Factors considered:
        - Event sequence completeness
        - Volume confirmation
        - Duration appropriateness
        - Price structure quality

        Args:
            phase: Classified phase
            events: Events supporting the classification
            duration_bars: Phase duration

        Returns:
            Confidence score between 0 and 1
        """
        from src.pattern_engine._phase_detector_impl import calculate_phase_confidence

        wyckoff_phase = _PHASE_TYPE_TO_WYCKOFF[phase]
        phase_events = _events_to_phase_events(events)
        confidence_int = calculate_phase_confidence(wyckoff_phase, phase_events)
        return confidence_int / 100.0  # Convert 0-100 to 0.0-1.0

    def reset(self) -> None:
        """Reset classifier state for new analysis."""
        self._current_phase = None
        self._phase_start_bar = 0
        self._detected_events = []
