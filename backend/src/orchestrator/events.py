"""
Event Models for Orchestrator Event Bus.

Defines typed event classes for communication between pipeline stages
and detectors. Events enable loose coupling between components.

Story 8.1: Master Orchestrator Architecture (AC: 3)
"""

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class Event(BaseModel):
    """
    Base class for all orchestrator events.

    All events include:
    - Unique event_id for tracking
    - event_type for routing
    - timestamp for ordering
    - correlation_id for request tracing
    - symbol and timeframe for context
    - data dict for event-specific payload

    Example:
        >>> event = Event(
        ...     event_type="custom_event",
        ...     correlation_id=uuid4(),
        ...     symbol="AAPL",
        ...     timeframe="1d",
        ...     data={"key": "value"}
        ... )
    """

    event_id: UUID = Field(default_factory=uuid4, description="Unique event identifier")
    event_type: str = Field(..., description="Type of event for routing")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Event timestamp (UTC)"
    )
    correlation_id: UUID = Field(..., description="Request correlation ID for tracing")
    symbol: str = Field(..., max_length=20, description="Stock symbol")
    timeframe: str = Field(..., description="Bar timeframe")
    data: dict[str, Any] = Field(default_factory=dict, description="Event-specific payload")

    class Config:
        """Pydantic configuration."""

        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
        }


class BarIngestedEvent(Event):
    """
    Emitted when an OHLCV bar is ingested into the pipeline.

    Used by Stage 1 (Data) to notify downstream stages that bar data is available.

    Attributes:
        bar_timestamp: Timestamp of the ingested bar
        bar_index: Index of the bar in the sequence
    """

    event_type: Literal["bar_ingested"] = "bar_ingested"
    bar_timestamp: datetime = Field(..., description="Timestamp of the ingested bar")
    bar_index: int = Field(..., ge=0, description="Index of the bar in sequence")


class VolumeAnalyzedEvent(Event):
    """
    Emitted when volume analysis completes for a bar sequence.

    Used by Stage 2 (Volume) to notify pattern detectors that volume metrics
    are available. Includes key metrics for downstream processing.

    Attributes:
        volume_ratio: Current bar volume / 20-bar average
        spread_ratio: Current bar spread / 20-bar average
        close_position: Position of close within bar range (0.0-1.0)
        effort_result: Effort vs result classification
        bars_analyzed: Number of bars in the analysis
    """

    event_type: Literal["volume_analyzed"] = "volume_analyzed"
    volume_ratio: float | None = Field(None, description="Volume ratio (current/20-bar avg)")
    spread_ratio: float | None = Field(None, description="Spread ratio (current/20-bar avg)")
    close_position: float = Field(..., ge=0.0, le=1.0, description="Close position in bar range")
    effort_result: str = Field(
        ..., description="Effort/result classification: CLIMACTIC, ABSORPTION, NO_DEMAND, NORMAL"
    )
    bars_analyzed: int = Field(..., ge=1, description="Number of bars analyzed")


class RangeDetectedEvent(Event):
    """
    Emitted when a trading range is detected.

    Used by Stage 3 (Range) to notify phase and pattern detectors that a
    valid trading range has been identified.

    Attributes:
        range_id: Unique identifier for the detected range
        creek: Support level (Creek)
        ice: Resistance level (Ice)
        jump: Price target (Jump)
        quality_score: Range quality score (0-100)
        support: Support price level
        resistance: Resistance price level
    """

    event_type: Literal["range_detected"] = "range_detected"
    range_id: UUID = Field(..., description="Trading range identifier")
    creek: float = Field(..., description="Support level (Creek)")
    ice: float = Field(..., description="Resistance level (Ice)")
    jump: float | None = Field(None, description="Price target (Jump)")
    quality_score: int = Field(..., ge=0, le=100, description="Range quality score")
    support: float = Field(..., description="Support price level")
    resistance: float = Field(..., description="Resistance price level")


class PhaseDetectedEvent(Event):
    """
    Emitted when a Wyckoff phase is detected.

    Used by Stage 4 (Phase) to notify pattern detectors which phase is
    currently active. Enables FR15 phase-pattern alignment validation.

    Attributes:
        phase: Wyckoff phase (A, B, C, D, E)
        confidence: Phase confidence percentage (0-100)
        duration: Number of bars since phase began
        trading_allowed: Whether trading is allowed in this phase (FR14)
    """

    event_type: Literal["phase_detected"] = "phase_detected"
    phase: str = Field(..., description="Wyckoff phase: A, B, C, D, E")
    confidence: int = Field(..., ge=0, le=100, description="Phase confidence percentage")
    duration: int = Field(..., ge=0, description="Bars since phase began")
    trading_allowed: bool = Field(..., description="FR14 trading restriction status")


class PatternDetectedEvent(Event):
    """
    Emitted when a Wyckoff pattern is detected.

    Used by Stage 5 (Pattern) to notify risk validation that a tradeable
    pattern has been identified. Includes all pattern details for signal generation.

    Attributes:
        pattern_id: Unique identifier for the detected pattern
        pattern_type: Pattern type (SPRING, SOS, LPS, ST, UTAD)
        confidence_score: Pattern confidence score (0-100)
        entry_price: Suggested entry price
        stop_price: Suggested stop loss price
        target_price: Suggested target price
        phase: Wyckoff phase where pattern was detected
    """

    event_type: Literal["pattern_detected"] = "pattern_detected"
    pattern_id: UUID = Field(default_factory=uuid4, description="Pattern identifier")
    pattern_type: str = Field(..., description="Pattern type: SPRING, SOS, LPS, ST, UTAD")
    confidence_score: int = Field(..., ge=0, le=100, description="Pattern confidence score")
    entry_price: float = Field(..., gt=0, description="Suggested entry price")
    stop_price: float = Field(..., gt=0, description="Suggested stop loss price")
    target_price: float = Field(..., gt=0, description="Suggested target price")
    phase: str = Field(..., description="Phase where pattern detected")


class SignalGeneratedEvent(Event):
    """
    Emitted when a trade signal is generated.

    Used by Stage 7 (Signal) to notify external systems (WebSocket, database)
    that a new trade signal has been created.

    Attributes:
        signal_id: Unique identifier for the generated signal
        pattern_type: Source pattern type
        entry_price: Entry price
        stop_price: Stop loss price
        target_price: Target price
        position_size: Calculated position size in shares
        risk_amount: Dollar risk amount
        r_multiple: Risk/reward ratio
    """

    event_type: Literal["signal_generated"] = "signal_generated"
    signal_id: UUID = Field(default_factory=uuid4, description="Signal identifier")
    pattern_type: str = Field(..., description="Source pattern type")
    entry_price: float = Field(..., gt=0, description="Entry price")
    stop_price: float = Field(..., gt=0, description="Stop loss price")
    target_price: float = Field(..., gt=0, description="Target price")
    position_size: int = Field(..., ge=0, description="Position size in shares")
    risk_amount: float = Field(..., ge=0, description="Dollar risk amount")
    r_multiple: float = Field(..., gt=0, description="Risk/reward ratio")


class DetectorFailedEvent(Event):
    """
    Emitted when a detector fails during analysis.

    Used for monitoring and error tracking. Enables circuit breaker pattern.

    Attributes:
        detector_name: Name of the failed detector
        error_message: Error description
        stack_trace: Optional stack trace for debugging
        retry_count: Number of retries attempted
    """

    event_type: Literal["detector_failed"] = "detector_failed"
    detector_name: str = Field(..., description="Name of the failed detector")
    error_message: str = Field(..., description="Error description")
    stack_trace: str | None = Field(None, description="Stack trace for debugging")
    retry_count: int = Field(default=0, ge=0, description="Retry attempts")
