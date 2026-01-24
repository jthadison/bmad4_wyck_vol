"""
Pattern detection events for real-time signal processing.

Story 19.3: Pattern Detection Integration

This module defines event models emitted when patterns are detected,
enabling downstream processing by signal generators and notification systems.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from src.models.ohlcv import OHLCVBar
from src.models.phase_classification import WyckoffPhase


class PatternType(str, Enum):
    """Wyckoff pattern types detected by the pattern engine."""

    SPRING = "SPRING"  # Phase C: Shakeout below Creek
    SOS = "SOS"  # Phase D: Sign of Strength breakout above Ice
    LPS = "LPS"  # Phase D/E: Last Point of Support pullback to Ice
    UTAD = "UTAD"  # Distribution: Upthrust After Distribution
    AR = "AR"  # Phase A: Automatic Rally after SC/Spring
    SC = "SC"  # Phase A: Selling Climax


class PatternDetectedEvent(BaseModel):
    """
    Event emitted when a Wyckoff pattern is detected.

    This event is emitted by the RealtimePatternDetector for downstream
    processing by signal generators, notification systems, and persistence.

    Attributes:
        event_id: Unique identifier for this event
        timestamp: When the pattern was detected (UTC)
        symbol: Trading symbol (e.g., "AAPL", "SPY")
        pattern_type: Type of Wyckoff pattern detected
        confidence: Detection confidence score (0.0 to 1.0)
        phase: Current Wyckoff phase when pattern was detected
        levels: Key price levels (creek, ice, jump)
        bar_data: OHLCV bar that triggered the detection
        metadata: Additional pattern-specific metadata
    """

    event_id: UUID = Field(default_factory=uuid4, description="Unique event identifier")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When pattern was detected (UTC)",
    )
    symbol: str = Field(..., min_length=1, description="Trading symbol")
    pattern_type: PatternType = Field(..., description="Type of Wyckoff pattern")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Detection confidence (0.0-1.0)")
    phase: WyckoffPhase = Field(..., description="Current Wyckoff phase")
    levels: dict[str, float] = Field(
        default_factory=dict,
        description="Key price levels (creek, ice, jump)",
    )
    bar_data: dict[str, Any] = Field(..., description="OHLCV bar that triggered detection")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional pattern-specific metadata",
    )

    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
        },
    )

    @classmethod
    def from_spring(
        cls,
        symbol: str,
        bar: OHLCVBar,
        phase: WyckoffPhase,
        confidence: float,
        creek_level: float,
        ice_level: float | None = None,
        **metadata: Any,
    ) -> PatternDetectedEvent:
        """Create event from Spring detection."""
        return cls(
            symbol=symbol,
            pattern_type=PatternType.SPRING,
            confidence=confidence,
            phase=phase,
            levels={
                "creek": creek_level,
                "ice": ice_level or 0.0,
            },
            bar_data=bar.model_dump(),
            metadata=metadata,
        )

    @classmethod
    def from_sos(
        cls,
        symbol: str,
        bar: OHLCVBar,
        phase: WyckoffPhase,
        confidence: float,
        ice_level: float,
        breakout_pct: float,
        **metadata: Any,
    ) -> PatternDetectedEvent:
        """Create event from SOS breakout detection."""
        return cls(
            symbol=symbol,
            pattern_type=PatternType.SOS,
            confidence=confidence,
            phase=phase,
            levels={
                "ice": ice_level,
            },
            bar_data=bar.model_dump(),
            metadata={
                "breakout_pct": breakout_pct,
                **metadata,
            },
        )

    @classmethod
    def from_lps(
        cls,
        symbol: str,
        bar: OHLCVBar,
        phase: WyckoffPhase,
        confidence: float,
        ice_level: float,
        pullback_pct: float,
        **metadata: Any,
    ) -> PatternDetectedEvent:
        """Create event from LPS detection."""
        return cls(
            symbol=symbol,
            pattern_type=PatternType.LPS,
            confidence=confidence,
            phase=phase,
            levels={
                "ice": ice_level,
            },
            bar_data=bar.model_dump(),
            metadata={
                "pullback_pct": pullback_pct,
                **metadata,
            },
        )

    @classmethod
    def from_utad(
        cls,
        symbol: str,
        bar: OHLCVBar,
        phase: WyckoffPhase,
        confidence: float,
        ice_level: float,
        penetration_pct: float,
        **metadata: Any,
    ) -> PatternDetectedEvent:
        """Create event from UTAD detection."""
        return cls(
            symbol=symbol,
            pattern_type=PatternType.UTAD,
            confidence=confidence,
            phase=phase,
            levels={
                "ice": ice_level,
            },
            bar_data=bar.model_dump(),
            metadata={
                "penetration_pct": penetration_pct,
                **metadata,
            },
        )

    @classmethod
    def from_ar(
        cls,
        symbol: str,
        bar: OHLCVBar,
        phase: WyckoffPhase,
        confidence: float,
        recovery_pct: float,
        prior_pattern: str,
        **metadata: Any,
    ) -> PatternDetectedEvent:
        """Create event from AR detection."""
        return cls(
            symbol=symbol,
            pattern_type=PatternType.AR,
            confidence=confidence,
            phase=phase,
            levels={},
            bar_data=bar.model_dump(),
            metadata={
                "recovery_pct": recovery_pct,
                "prior_pattern": prior_pattern,
                **metadata,
            },
        )

    @classmethod
    def from_sc(
        cls,
        symbol: str,
        bar: OHLCVBar,
        phase: WyckoffPhase,
        confidence: float,
        volume_ratio: float,
        **metadata: Any,
    ) -> PatternDetectedEvent:
        """Create event from SC detection."""
        return cls(
            symbol=symbol,
            pattern_type=PatternType.SC,
            confidence=confidence,
            phase=phase,
            levels={},
            bar_data=bar.model_dump(),
            metadata={
                "volume_ratio": volume_ratio,
                **metadata,
            },
        )
