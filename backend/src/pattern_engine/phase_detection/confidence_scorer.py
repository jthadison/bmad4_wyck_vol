"""
Phase detection confidence scoring module.

This module provides confidence scoring for phase classifications,
considering volume, timing, and structural factors.

Wired to real implementations (Story 23.1):
- calculate_phase_confidence from pattern_engine._phase_detector_impl
"""

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from src.models.phase_classification import PhaseEvents, WyckoffPhase

from .types import DetectionConfig, EventType, PhaseEvent, PhaseType

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


@dataclass
class ScoringFactors:
    """
    Individual scoring factors for confidence calculation.

    Attributes:
        volume_score: Score based on volume confirmation (0-1)
        timing_score: Score based on phase timing/duration (0-1)
        structure_score: Score based on price structure quality (0-1)
        event_score: Score based on event sequence completeness (0-1)
    """

    volume_score: float = 0.0
    timing_score: float = 0.0
    structure_score: float = 0.0
    event_score: float = 0.0

    def aggregate(self, weights: Optional[dict] = None) -> float:
        """
        Aggregate individual scores into overall confidence.

        Args:
            weights: Optional custom weights for each factor.
                     Default weights: volume=0.3, timing=0.2, structure=0.25, event=0.25

        Returns:
            Weighted average confidence score (0-1)
        """
        if weights is None:
            weights = {
                "volume": 0.30,
                "timing": 0.20,
                "structure": 0.25,
                "event": 0.25,
            }

        return (
            self.volume_score * weights["volume"]
            + self.timing_score * weights["timing"]
            + self.structure_score * weights["structure"]
            + self.event_score * weights["event"]
        )


class PhaseConfidenceScorer:
    """
    Calculates confidence scores for phase classifications.

    Scoring is based on multiple factors:
    - Volume: How well volume confirms the phase (e.g., high volume SC, low volume Spring)
    - Timing: Whether phase duration is appropriate (not too short/long)
    - Structure: Quality of price structure (support/resistance definition)
    - Events: Completeness of expected event sequence

    Attributes:
        config: Detection configuration parameters
    """

    # Default weights for scoring factors
    DEFAULT_WEIGHTS = {
        "volume": 0.30,
        "timing": 0.20,
        "structure": 0.25,
        "event": 0.25,
    }

    # Expected events per phase (using tuples for immutability)
    # Note: Distribution events (UTAD, SOW, LPSY) to be added in Story 22.7b
    PHASE_EXPECTED_EVENTS: dict[PhaseType, tuple[str, ...]] = {
        PhaseType.A: ("SC", "AR", "ST"),
        PhaseType.B: (),  # Variable, mostly range-bound action
        PhaseType.C: ("SPRING",),  # or UTAD for distribution
        PhaseType.D: ("SOS", "LPS"),  # or SOW, LPSY for distribution
        PhaseType.E: (),  # Trend continuation
    }

    def __init__(self, config: Optional[DetectionConfig] = None) -> None:
        """
        Initialize the confidence scorer.

        Args:
            config: Detection configuration. Uses defaults if not provided.
        """
        self.config = config or DetectionConfig()

    def calculate_confidence(
        self,
        phase: PhaseType,
        events: list[PhaseEvent],
        ohlcv: pd.DataFrame,
        phase_start_bar: int,
    ) -> float:
        """
        Calculate overall confidence for a phase classification.

        Args:
            phase: The classified phase
            events: Events detected in this phase
            ohlcv: OHLCV data for the analysis period
            phase_start_bar: Starting bar index of the phase

        Returns:
            Confidence score between 0 and 1
        """
        from src.pattern_engine._phase_detector_impl import calculate_phase_confidence

        wyckoff_phase = _PHASE_TYPE_TO_WYCKOFF[phase]
        phase_events = _events_to_phase_events(events)
        confidence_int = calculate_phase_confidence(wyckoff_phase, phase_events)
        return confidence_int / 100.0  # Convert 0-100 to 0.0-1.0

    def calculate_factors(
        self,
        phase: PhaseType,
        events: list[PhaseEvent],
        ohlcv: pd.DataFrame,
        phase_start_bar: int,
    ) -> ScoringFactors:
        """
        Calculate individual scoring factors.

        Args:
            phase: The classified phase
            events: Events detected in this phase
            ohlcv: OHLCV data for the analysis period
            phase_start_bar: Starting bar index of the phase

        Returns:
            ScoringFactors with individual scores
        """
        duration_bars = len(ohlcv) - phase_start_bar
        timing_score = self._score_timing(phase, duration_bars)
        event_score = self._score_event_sequence(phase, events)
        volume_score = self._score_volume_confirmation(phase, events, ohlcv)
        structure_score = self._score_structure(phase, ohlcv, phase_start_bar)

        return ScoringFactors(
            volume_score=volume_score,
            timing_score=timing_score,
            structure_score=structure_score,
            event_score=event_score,
        )

    def _score_volume_confirmation(
        self,
        phase: PhaseType,
        events: list[PhaseEvent],
        ohlcv: pd.DataFrame,
    ) -> float:
        """
        Score volume confirmation for the phase.

        Volume scoring rules:
        - Phase A (SC): Volume should be >2x average (exhaustion)
        - Phase B: Volume should be declining (consolidation)
        - Phase C (Spring): Volume should be <0.7x average (lack of supply)
        - Phase D (SOS): Volume should be >1.5x average (demand)

        Args:
            phase: Current phase
            events: Detected events
            ohlcv: OHLCV data

        Returns:
            Volume score (0-1)
        """
        if ohlcv.empty or "volume" not in ohlcv.columns:
            return 0.5  # Neutral if no volume data

        avg_volume = ohlcv["volume"].mean()
        if avg_volume <= 0:
            return 0.5

        # Score based on volume pattern alignment with phase
        event_volumes = [e.volume for e in events if e.volume > 0]
        if not event_volumes:
            return 0.5

        avg_event_volume = sum(event_volumes) / len(event_volumes)
        volume_ratio = avg_event_volume / avg_volume if avg_volume > 0 else 1.0

        # Phase-specific volume expectations
        if phase == PhaseType.A:  # SC phase - expect high volume
            return min(1.0, volume_ratio / 2.0)  # 2x volume = 1.0 score
        elif phase == PhaseType.C:  # Spring phase - expect low volume
            return min(1.0, max(0.0, 1.0 - volume_ratio))  # Low volume = high score
        elif phase in (PhaseType.D, PhaseType.E):  # SOS/LPS - expect high volume
            return min(1.0, volume_ratio / 1.5)  # 1.5x volume = 1.0 score
        else:
            return 0.5  # Neutral for Phase B

    def _score_timing(
        self,
        phase: PhaseType,
        duration_bars: int,
    ) -> float:
        """
        Score phase timing/duration.

        Timing scoring rules:
        - Too short (<min_phase_duration): Low score
        - Appropriate duration: High score
        - Excessively long: Slightly reduced score

        Args:
            phase: Current phase
            duration_bars: Number of bars in phase

        Returns:
            Timing score (0-1)
        """
        min_duration = self.config.min_phase_duration

        if duration_bars < min_duration:
            # Too short - linear penalty
            return max(0.0, duration_bars / min_duration * 0.5)

        # Optimal duration range (1-3x minimum)
        if duration_bars <= min_duration * 3:
            return 1.0

        # Excessively long - slight penalty
        excess_ratio = duration_bars / (min_duration * 3)
        return max(0.6, 1.0 - (excess_ratio - 1) * 0.1)

    def _score_structure(
        self,
        phase: PhaseType,
        ohlcv: pd.DataFrame,
        phase_start_bar: int,
    ) -> float:
        """
        Score price structure quality.

        Structure scoring considers:
        - Clear support/resistance levels
        - Range definition
        - Trend alignment

        Args:
            phase: Current phase
            ohlcv: OHLCV data
            phase_start_bar: Starting bar of phase

        Returns:
            Structure score (0-1)
        """
        if ohlcv.empty or len(ohlcv) < 2:
            return 0.5

        phase_data = ohlcv.iloc[phase_start_bar:]
        if phase_data.empty or len(phase_data) < 2:
            return 0.5

        # Calculate range tightening (accumulation indicator)
        first_half = phase_data.iloc[: len(phase_data) // 2]
        second_half = phase_data.iloc[len(phase_data) // 2 :]

        if first_half.empty or second_half.empty:
            return 0.5

        first_range = first_half["high"].max() - first_half["low"].min()
        second_range = second_half["high"].max() - second_half["low"].min()

        if first_range <= 0:
            return 0.5

        # Tightening range is positive for accumulation (Phase B/C)
        tightening = 1.0 - (second_range / first_range)

        if phase in (PhaseType.B, PhaseType.C):
            # Tightening range is good for accumulation
            return max(0.0, min(1.0, 0.5 + tightening))
        elif phase in (PhaseType.D, PhaseType.E):
            # Expanding range is good for markup
            return max(0.0, min(1.0, 0.5 - tightening))
        else:
            return 0.5

    def _score_event_sequence(
        self,
        phase: PhaseType,
        events: list[PhaseEvent],
    ) -> float:
        """
        Score event sequence completeness.

        Checks if expected events for the phase have been detected.

        Args:
            phase: Current phase
            events: Detected events

        Returns:
            Event sequence score (0-1)
        """
        expected = self.PHASE_EXPECTED_EVENTS.get(phase, ())

        if not expected:
            # No specific events expected (Phase B, E)
            return 0.7  # Neutral score

        # Check how many expected events were detected
        event_types = {e.event_type.value for e in events}
        matches = sum(1 for exp in expected if exp in event_types)

        return matches / len(expected) if expected else 0.7
