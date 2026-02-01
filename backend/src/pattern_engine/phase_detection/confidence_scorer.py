"""
Phase detection confidence scoring module.

This module provides confidence scoring for phase classifications,
considering volume, timing, and structural factors.

TODO (Story 22.7b): Migrate implementation from phase_detector_v2.py
"""

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from .types import DetectionConfig, PhaseEvent, PhaseType


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

    # Expected events per phase
    PHASE_EXPECTED_EVENTS: dict[PhaseType, list[str]] = {
        PhaseType.A: ["SC", "AR", "ST"],
        PhaseType.B: [],  # Variable, mostly range-bound action
        PhaseType.C: ["SPRING"],  # or UTAD for distribution
        PhaseType.D: ["SOS", "LPS"],  # or SOW, LPSY for distribution
        PhaseType.E: [],  # Trend continuation
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

        Raises:
            NotImplementedError: Implementation pending Story 22.7b
        """
        # TODO (Story 22.7b): Implement full scoring logic
        raise NotImplementedError("Implementation pending Story 22.7b")

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

        Raises:
            NotImplementedError: Implementation pending Story 22.7b
        """
        raise NotImplementedError("Implementation pending Story 22.7b")

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

        Raises:
            NotImplementedError: Implementation pending Story 22.7b
        """
        raise NotImplementedError("Implementation pending Story 22.7b")

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

        Raises:
            NotImplementedError: Implementation pending Story 22.7b
        """
        raise NotImplementedError("Implementation pending Story 22.7b")

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
        expected = self.PHASE_EXPECTED_EVENTS.get(phase, [])

        if not expected:
            # No specific events expected (Phase B, E)
            return 0.7  # Neutral score

        # Check how many expected events were detected
        event_types = {e.event_type.value for e in events}
        matches = sum(1 for exp in expected if exp in event_types)

        return matches / len(expected) if expected else 0.7
