"""
Phase Status Response Models (Feature 11: Wyckoff Cycle Compass)

Pydantic models for the phase status endpoint that powers the
Wyckoff Phase Compass / Phase Gauge UI component.
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class PhaseStatusEvent(BaseModel):
    """A recent Wyckoff event detected in the current analysis window."""

    event_type: str = Field(..., description="Event type: SC, AR, ST, SPRING, UTAD, SOS, LPS, etc.")
    bar_index: int = Field(..., description="Bars ago (0 = current)")
    price: float = Field(..., description="Price level at event")
    timestamp: Optional[datetime] = Field(None, description="Event timestamp")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Detection confidence")


class PhaseStatusResponse(BaseModel):
    """
    Current Wyckoff phase status for a symbol.

    Used by the Phase Compass UI to show where in the Wyckoff cycle
    (A -> B -> C -> D -> E) a symbol currently sits.
    """

    symbol: str = Field(..., description="Trading symbol")
    timeframe: str = Field(..., description="Analysis timeframe")
    phase: Optional[Literal["A", "B", "C", "D", "E"]] = Field(
        None, description="Current phase: A, B, C, D, E, or null if unknown"
    )
    confidence: float = Field(..., ge=0.0, le=1.0, description="Phase classification confidence")
    phase_duration_bars: int = Field(..., ge=0, description="Number of bars in current phase")
    progression_pct: float = Field(
        ..., ge=0.0, le=1.0, description="Estimated progression within phase (0.0 to 1.0)"
    )
    dominant_event: Optional[str] = Field(None, description="Most recent significant event type")
    recent_events: list[PhaseStatusEvent] = Field(
        default_factory=list, description="Recent detected events"
    )
    bias: Literal["ACCUMULATION", "DISTRIBUTION", "UNKNOWN"] = Field(
        ..., description="Market bias: ACCUMULATION, DISTRIBUTION, or UNKNOWN"
    )
    updated_at: datetime = Field(..., description="Timestamp of this analysis")
    data_source: Literal["MOCK", "LIVE"] = Field(
        "MOCK",
        description="MOCK until wired to real PhaseClassifier (Epic 23); LIVE when production data.",
    )
