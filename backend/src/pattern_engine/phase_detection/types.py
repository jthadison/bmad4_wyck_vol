"""
Type definitions for Wyckoff phase detection.

This module defines the core types used throughout the phase detection
system, including phase classifications, events, and configuration.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class PhaseType(Enum):
    """
    Wyckoff accumulation/distribution phases.

    Phases represent distinct stages in the Wyckoff market cycle:
    - Phase A: Stopping action (SC, AR, ST)
    - Phase B: Building cause (trading range)
    - Phase C: Test (Spring/UTAD)
    - Phase D: Markup/Markdown (SOS/SOW, LPS/LPSY)
    - Phase E: Trend continuation
    """

    A = "A"  # Stopping action
    B = "B"  # Building cause
    C = "C"  # Test
    D = "D"  # Markup/Markdown
    E = "E"  # Trend continuation


class EventType(Enum):
    """
    Wyckoff structural events.

    Events are specific price/volume patterns that mark phase transitions.
    """

    # Phase A events
    SELLING_CLIMAX = "SC"  # High volume selling exhaustion
    AUTOMATIC_RALLY = "AR"  # Post-SC bounce
    SECONDARY_TEST = "ST"  # Test of SC low

    # Phase B/C events
    SPRING = "SPRING"  # Shakeout below support
    UPTHRUST_AFTER_DISTRIBUTION = "UTAD"  # False breakout above resistance

    # Phase D events
    SIGN_OF_STRENGTH = "SOS"  # Breakout with volume
    SIGN_OF_WEAKNESS = "SOW"  # Breakdown with volume
    LAST_POINT_OF_SUPPORT = "LPS"  # Pullback to broken resistance
    LAST_POINT_OF_SUPPLY = "LPSY"  # Rally to broken support


@dataclass
class PhaseEvent:
    """
    A detected Wyckoff event.

    Attributes:
        event_type: The type of Wyckoff event
        timestamp: When the event occurred
        bar_index: Index in the OHLCV data
        price: Price level at event
        volume: Volume at event
        confidence: Detection confidence (0-1)
        metadata: Additional event-specific data
    """

    event_type: EventType
    timestamp: datetime
    bar_index: int
    price: float
    volume: float
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PhaseResult:
    """
    Result of phase classification.

    Attributes:
        phase: Current phase classification
        confidence: Overall confidence (0-1)
        events: Events detected in this phase
        start_bar: Starting bar index of phase
        duration_bars: Number of bars in phase
        metadata: Additional classification data
    """

    phase: Optional[PhaseType]
    confidence: float
    events: list[PhaseEvent] = field(default_factory=list)
    start_bar: int = 0
    duration_bars: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DetectionConfig:
    """
    Configuration for phase detection.

    Attributes:
        min_phase_duration: Minimum bars for phase validity
        volume_threshold_sc: Volume multiple for SC detection
        volume_threshold_sos: Volume multiple for SOS detection
        spring_volume_max: Maximum volume ratio for valid spring
        lookback_bars: Bars to analyze for pattern detection
        confidence_threshold: Minimum confidence for signals
    """

    min_phase_duration: int = 10
    volume_threshold_sc: float = 2.0  # 2x average for SC
    volume_threshold_sos: float = 1.5  # 1.5x average for SOS
    spring_volume_max: float = 0.7  # <0.7x average for Spring
    lookback_bars: int = 100
    confidence_threshold: float = 0.6  # Minimum confidence for signals
