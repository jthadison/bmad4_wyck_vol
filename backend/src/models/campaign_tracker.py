"""
Campaign Tracker Visualization Models (Story 11.4)

Purpose:
--------
Provides Pydantic models for the campaign tracker UI visualization,
including progression tracking, health status, and real-time updates.

Data Models:
------------
1. CampaignEntryDetail: Detailed entry info for UI display
2. CampaignProgressionModel: Phase progression (Spring → SOS → LPS)
3. CampaignHealthStatus: Health indicator (green/yellow/red)
4. TradingRangeLevels: Key price levels (creek/ice/jump)
5. ExitPlanDisplay: Exit strategy for UI
6. PreliminaryEvent: PS/SC/AR/ST events before Spring
7. CampaignQualityScore: Quality based on preliminary events
8. CampaignResponse: Main API response model
9. CampaignUpdatedMessage: WebSocket update message

Integration:
------------
- Story 11.1: Configuration system integration
- Story 10.9: WebSocket real-time updates
- Story 9.1-9.6: Campaign lifecycle and performance tracking

Author: Story 11.4
"""

from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_serializer


class CampaignEntryDetail(BaseModel):
    """
    Detailed entry information for campaign tracker visualization.

    Represents a single position entry within a campaign with complete details
    for UI display including prices, P&L, and status.

    Fields:
    -------
    - pattern_type: SPRING | SOS | LPS | UTAD
    - signal_id: UUID of the signal that generated this entry
    - entry_price: Actual entry fill price
    - position_size: Position size in shares/lots
    - shares: Number of shares (same as position_size for clarity)
    - status: PENDING | FILLED | STOPPED | CLOSED
    - pnl: Current profit/loss (unrealized or realized)
    - pnl_percent: P&L as percentage of entry value
    - entry_timestamp: When position was entered
    - exit_timestamp: When position was exited (if closed)

    Example:
    --------
    >>> from decimal import Decimal
    >>> from datetime import datetime, UTC
    >>> from uuid import uuid4
    >>> entry = CampaignEntryDetail(
    ...     pattern_type="SPRING",
    ...     signal_id=uuid4(),
    ...     entry_price=Decimal("152.35"),
    ...     position_size=Decimal("100"),
    ...     shares=100,
    ...     status="FILLED",
    ...     pnl=Decimal("210.50"),
    ...     pnl_percent=Decimal("2.1"),
    ...     entry_timestamp=datetime.now(UTC),
    ...     exit_timestamp=None
    ... )
    """

    pattern_type: str = Field(..., description="SPRING | SOS | LPS | UTAD")
    signal_id: UUID = Field(..., description="Signal UUID")
    entry_price: Decimal = Field(
        ..., decimal_places=8, max_digits=18, description="Entry fill price"
    )
    position_size: Decimal = Field(
        ..., decimal_places=8, max_digits=18, description="Position size"
    )
    shares: int = Field(..., description="Number of shares")
    status: str = Field(..., description="PENDING | FILLED | STOPPED | CLOSED")
    pnl: Decimal = Field(..., decimal_places=8, max_digits=18, description="Profit/loss")
    pnl_percent: Decimal = Field(..., decimal_places=8, max_digits=18, description="P&L percentage")
    entry_timestamp: Any = Field(..., description="Entry timestamp")
    exit_timestamp: Any | None = Field(None, description="Exit timestamp if closed")

    model_config = ConfigDict(json_encoders={Decimal: str})

    @model_serializer
    def serialize_model(self) -> dict[str, Any]:
        """Serialize with Decimal and datetime as strings."""
        return {
            "pattern_type": self.pattern_type,
            "signal_id": str(self.signal_id),
            "entry_price": str(self.entry_price),
            "position_size": str(self.position_size),
            "shares": self.shares,
            "status": self.status,
            "pnl": str(self.pnl),
            "pnl_percent": str(self.pnl_percent),
            "entry_timestamp": self.entry_timestamp.isoformat()
            if hasattr(self.entry_timestamp, "isoformat")
            else str(self.entry_timestamp),
            "exit_timestamp": self.exit_timestamp.isoformat()
            if self.exit_timestamp and hasattr(self.exit_timestamp, "isoformat")
            else (str(self.exit_timestamp) if self.exit_timestamp else None),
        }


class CampaignProgressionModel(BaseModel):
    """
    Campaign progression through Wyckoff BMAD phases.

    Tracks which phases have been completed and what's expected next,
    following the Spring → SOS → LPS sequence.

    Fields:
    -------
    - completed_phases: List of completed entry patterns
    - pending_phases: List of pending/expected entry patterns
    - next_expected: Human-readable description of next expected entry
    - current_phase: Current Wyckoff phase (C, D, or E)

    Example:
    --------
    >>> progression = CampaignProgressionModel(
    ...     completed_phases=["SPRING", "SOS"],
    ...     pending_phases=["LPS"],
    ...     next_expected="Phase E watch - monitoring for LPS",
    ...     current_phase="D"
    ... )
    """

    completed_phases: list[str] = Field(
        default_factory=list, description="Completed entry patterns"
    )
    pending_phases: list[str] = Field(default_factory=list, description="Pending entry patterns")
    next_expected: str = Field(..., description="Next expected entry description")
    current_phase: str = Field(..., description="Wyckoff phase: C, D, E")

    model_config = ConfigDict()


class CampaignHealthStatus(str, Enum):
    """
    Campaign health status indicator.

    Values:
    -------
    - GREEN: On track, healthy (< 4% allocation, no stops, positive/neutral P&L)
    - YELLOW: Approaching limits (4-5% allocation, nearing risk limits)
    - RED: Invalidated (stop hit, creek/ice breached, > 5% allocation)
    """

    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


class TradingRangeLevels(BaseModel):
    """
    Key price levels from trading range for campaign context.

    Fields:
    -------
    - creek_level: Support level (invalidation point for Springs)
    - ice_level: Resistance level (breakout level for SOS)
    - jump_target: Projected target based on cause factor

    Example:
    --------
    >>> from decimal import Decimal
    >>> levels = TradingRangeLevels(
    ...     creek_level=Decimal("145.00"),
    ...     ice_level=Decimal("160.00"),
    ...     jump_target=Decimal("175.00")
    ... )
    """

    creek_level: Decimal = Field(..., decimal_places=8, max_digits=18, description="Support level")
    ice_level: Decimal = Field(..., decimal_places=8, max_digits=18, description="Resistance level")
    jump_target: Decimal = Field(
        ..., decimal_places=8, max_digits=18, description="Projected target"
    )

    model_config = ConfigDict(json_encoders={Decimal: str})

    @model_serializer
    def serialize_model(self) -> dict[str, Any]:
        """Serialize with Decimal as strings."""
        return {
            "creek_level": str(self.creek_level),
            "ice_level": str(self.ice_level),
            "jump_target": str(self.jump_target),
        }


class ExitPlanDisplay(BaseModel):
    """
    Campaign exit strategy for UI display.

    Note: This is different from ExitRule which is the database model.
    This model is optimized for frontend display with simplified fields.

    Fields:
    -------
    - target_1: First target price (Ice or Jump)
    - target_2: Second target price (Jump)
    - target_3: Third target price (Jump × 1.5)
    - current_stop: Current stop loss level
    - partial_exit_percentages: Exit percentages at each target

    Example:
    --------
    >>> from decimal import Decimal
    >>> exit_plan = ExitPlanDisplay(
    ...     target_1=Decimal("160.00"),
    ...     target_2=Decimal("168.50"),
    ...     target_3=Decimal("175.00"),
    ...     current_stop=Decimal("150.00"),
    ...     partial_exit_percentages={"T1": 50, "T2": 30, "T3": 20}
    ... )
    """

    target_1: Decimal = Field(..., decimal_places=8, max_digits=18, description="First target")
    target_2: Decimal = Field(..., decimal_places=8, max_digits=18, description="Second target")
    target_3: Decimal = Field(..., decimal_places=8, max_digits=18, description="Third target")
    current_stop: Decimal = Field(
        ..., decimal_places=8, max_digits=18, description="Current stop loss"
    )
    partial_exit_percentages: dict[str, int] = Field(
        ..., description="Exit percentages: {T1: 50, T2: 30, T3: 20}"
    )

    model_config = ConfigDict(json_encoders={Decimal: str})

    @model_serializer
    def serialize_model(self) -> dict[str, Any]:
        """Serialize with Decimal as strings."""
        return {
            "target_1": str(self.target_1),
            "target_2": str(self.target_2),
            "target_3": str(self.target_3),
            "current_stop": str(self.current_stop),
            "partial_exit_percentages": self.partial_exit_percentages,
        }


class PreliminaryEvent(BaseModel):
    """
    Preliminary Wyckoff event detected before Spring entry.

    Tracks PS, SC, AR, ST events that occurred before the campaign
    Spring entry, used for campaign quality scoring.

    Fields:
    -------
    - event_type: PS | SC | AR | ST
    - timestamp: When event was detected
    - price: Price at event
    - bar_index: Bar index in data series

    Example:
    --------
    >>> from decimal import Decimal
    >>> from datetime import datetime, UTC
    >>> event = PreliminaryEvent(
    ...     event_type="PS",
    ...     timestamp=datetime.now(UTC),
    ...     price=Decimal("150.00"),
    ...     bar_index=100
    ... )
    """

    event_type: str = Field(..., description="PS | SC | AR | ST")
    timestamp: Any = Field(..., description="Event timestamp")
    price: Decimal = Field(..., decimal_places=8, max_digits=18, description="Price at event")
    bar_index: int = Field(..., description="Bar index in series")

    model_config = ConfigDict(json_encoders={Decimal: str})

    @model_serializer
    def serialize_model(self) -> dict[str, Any]:
        """Serialize with Decimal and datetime as strings."""
        return {
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat()
            if hasattr(self.timestamp, "isoformat")
            else str(self.timestamp),
            "price": str(self.price),
            "bar_index": self.bar_index,
        }


class CampaignQualityScore(str, Enum):
    """
    Campaign quality score based on preliminary event completeness.

    Values:
    -------
    - COMPLETE: All 4 events detected (PS, SC, AR, ST) - highest reliability
    - PARTIAL: 2-3 events detected - standard quality
    - MINIMAL: 0-1 events detected - lower quality
    """

    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    MINIMAL = "MINIMAL"


class CampaignResponse(BaseModel):
    """
    Complete campaign details for frontend campaign tracker.

    Comprehensive response model containing all data needed to display
    a campaign card with progression bar, entries, P&L, health status,
    and exit plan.

    Fields:
    -------
    Campaign identification:
    - id: Campaign UUID
    - symbol: Trading symbol
    - timeframe: Chart timeframe
    - trading_range_id: Associated trading range UUID
    - status: ACTIVE | MARKUP | COMPLETED | INVALIDATED

    Risk and allocation:
    - total_allocation: Percentage of portfolio (0-5.0%)
    - current_risk: Dollar amount at risk

    Position data:
    - entries: List of CampaignEntryDetail objects
    - average_entry: Weighted average entry price (if positions open)
    - total_pnl: Combined unrealized + realized P&L
    - total_pnl_percent: Total P&L as percentage

    Campaign state:
    - progression: CampaignProgressionModel showing completed/pending phases
    - health: CampaignHealthStatus (green/yellow/red)

    Trading context:
    - exit_plan: ExitPlanDisplay with targets and stops
    - trading_range_levels: TradingRangeLevels with creek/ice/jump

    Wyckoff quality (AC: 11, 12):
    - preliminary_events: List of PreliminaryEvent (PS, SC, AR, ST)
    - campaign_quality_score: COMPLETE | PARTIAL | MINIMAL

    Timestamps:
    - started_at: Campaign start timestamp
    - completed_at: Campaign completion timestamp (if complete)

    Example:
    --------
    >>> from decimal import Decimal
    >>> from datetime import datetime, UTC
    >>> from uuid import uuid4
    >>> campaign = CampaignResponse(
    ...     id=uuid4(),
    ...     symbol="AAPL",
    ...     timeframe="1d",
    ...     trading_range_id=uuid4(),
    ...     status="ACTIVE",
    ...     total_allocation=Decimal("4.5"),
    ...     current_risk=Decimal("2250.00"),
    ...     entries=[...],
    ...     average_entry=Decimal("152.35"),
    ...     total_pnl=Decimal("255.80"),
    ...     total_pnl_percent=Decimal("1.3"),
    ...     progression=CampaignProgressionModel(...),
    ...     health=CampaignHealthStatus.GREEN,
    ...     exit_plan=ExitPlanDisplay(...),
    ...     trading_range_levels=TradingRangeLevels(...),
    ...     preliminary_events=[...],
    ...     campaign_quality_score=CampaignQualityScore.COMPLETE,
    ...     started_at=datetime.now(UTC),
    ...     completed_at=None
    ... )
    """

    # Campaign identification
    id: UUID = Field(..., description="Campaign UUID")
    symbol: str = Field(..., max_length=20, description="Trading symbol")
    timeframe: str = Field(..., description="Chart timeframe: 1m, 5m, 15m, 1h, 1d")
    trading_range_id: UUID = Field(..., description="Trading range UUID")
    status: str = Field(..., description="ACTIVE | MARKUP | COMPLETED | INVALIDATED")

    # Risk and allocation
    total_allocation: Decimal = Field(
        ..., decimal_places=2, max_digits=5, description="Portfolio percentage (0-5.0%)"
    )
    current_risk: Decimal = Field(
        ..., decimal_places=2, max_digits=12, description="Dollar risk amount"
    )

    # Position data
    entries: list[CampaignEntryDetail] = Field(
        default_factory=list, description="List of campaign entries"
    )
    average_entry: Decimal | None = Field(
        None, decimal_places=8, max_digits=18, description="Weighted average entry"
    )
    total_pnl: Decimal = Field(
        ..., decimal_places=8, max_digits=18, description="Total P&L (unrealized + realized)"
    )
    total_pnl_percent: Decimal = Field(
        ..., decimal_places=8, max_digits=18, description="Total P&L percentage"
    )

    # Campaign state
    progression: CampaignProgressionModel = Field(..., description="Phase progression")
    health: CampaignHealthStatus = Field(..., description="Health status")

    # Trading context
    exit_plan: ExitPlanDisplay = Field(..., description="Exit strategy")
    trading_range_levels: TradingRangeLevels = Field(..., description="Key price levels")

    # Wyckoff quality enhancement (AC: 11, 12)
    preliminary_events: list[PreliminaryEvent] = Field(
        default_factory=list, description="PS, SC, AR, ST events before Spring"
    )
    campaign_quality_score: CampaignQualityScore = Field(
        ..., description="Quality based on preliminary events"
    )

    # Timestamps
    started_at: Any = Field(..., description="Campaign start timestamp")
    completed_at: Any | None = Field(None, description="Campaign completion timestamp")

    model_config = ConfigDict(json_encoders={Decimal: str})

    @model_serializer
    def serialize_model(self) -> dict[str, Any]:
        """Serialize with Decimal, UUID, and datetime as strings."""
        return {
            "id": str(self.id),
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "trading_range_id": str(self.trading_range_id),
            "status": self.status,
            "total_allocation": str(self.total_allocation),
            "current_risk": str(self.current_risk),
            "entries": [e.serialize_model() for e in self.entries],
            "average_entry": str(self.average_entry) if self.average_entry else None,
            "total_pnl": str(self.total_pnl),
            "total_pnl_percent": str(self.total_pnl_percent),
            "progression": {
                "completed_phases": self.progression.completed_phases,
                "pending_phases": self.progression.pending_phases,
                "next_expected": self.progression.next_expected,
                "current_phase": self.progression.current_phase,
            },
            "health": self.health.value,
            "exit_plan": self.exit_plan.serialize_model(),
            "trading_range_levels": self.trading_range_levels.serialize_model(),
            "preliminary_events": [e.serialize_model() for e in self.preliminary_events],
            "campaign_quality_score": self.campaign_quality_score.value,
            "started_at": self.started_at.isoformat()
            if hasattr(self.started_at, "isoformat")
            else str(self.started_at),
            "completed_at": self.completed_at.isoformat()
            if self.completed_at and hasattr(self.completed_at, "isoformat")
            else (str(self.completed_at) if self.completed_at else None),
        }


class CampaignUpdatedMessage(BaseModel):
    """
    WebSocket message for real-time campaign updates.

    Sent when campaign state changes (P&L, status, progression) to
    provide real-time updates to connected clients.

    Fields:
    -------
    - type: Message type ("campaign_updated")
    - sequence_number: Message sequence number for ordering
    - campaign_id: UUID of updated campaign
    - updated_fields: List of field names that changed
    - campaign: Full CampaignResponse object
    - timestamp: Update timestamp

    Example:
    --------
    >>> from datetime import datetime, UTC
    >>> from uuid import uuid4
    >>> message = CampaignUpdatedMessage(
    ...     type="campaign_updated",
    ...     sequence_number=1245,
    ...     campaign_id=uuid4(),
    ...     updated_fields=["pnl", "progression"],
    ...     campaign=CampaignResponse(...),
    ...     timestamp=datetime.now(UTC)
    ... )
    """

    type: str = Field(default="campaign_updated", description="Message type")
    sequence_number: int = Field(..., description="Message sequence number")
    campaign_id: UUID = Field(..., description="Updated campaign UUID")
    updated_fields: list[str] = Field(..., description="Changed field names")
    campaign: CampaignResponse = Field(..., description="Full campaign data")
    timestamp: Any = Field(..., description="Update timestamp")

    model_config = ConfigDict(json_encoders={Decimal: str})

    @model_serializer
    def serialize_model(self) -> dict[str, Any]:
        """Serialize with UUID and datetime as strings."""
        return {
            "type": self.type,
            "sequence_number": self.sequence_number,
            "campaign_id": str(self.campaign_id),
            "updated_fields": self.updated_fields,
            "campaign": self.campaign.serialize_model(),
            "timestamp": self.timestamp.isoformat()
            if hasattr(self.timestamp, "isoformat")
            else str(self.timestamp),
        }
