"""
Campaign Lifecycle Management Data Models (Story 9.1)

Purpose:
--------
Provides Pydantic models for campaign creation, lifecycle management, and
multi-phase position building (Spring → SOS → LPS) within same trading range.

Data Models:
------------
1. CampaignStatus: Lifecycle state enum (ACTIVE, MARKUP, COMPLETED, INVALIDATED)
2. CampaignPosition: Individual position within campaign (Spring/SOS/LPS entry)
3. Campaign: Main campaign entity with full lifecycle tracking

Key Features:
-------------
- Campaign ID format: {symbol}-{range_start_date} (AC: 3)
- Lifecycle states: ACTIVE → MARKUP → COMPLETED | INVALIDATED (AC: 4)
- Risk limits: 5% max campaign allocation (FR18)
- Optimistic locking: Version field for concurrent updates
- UTC timestamps: All datetime fields enforced UTC
- Decimal precision: NUMERIC(18,8) for prices, NUMERIC(12,2) for amounts

Integration:
------------
- Story 8.8: Links to TradeSignal via signal_id
- Epic 2: References TradingRange via trading_range_id
- Story 8.10: MasterOrchestrator calls campaign_service.get_or_create_campaign()
- Story 9.2: BMAD allocation uses total_allocation tracking
- Story 9.3: Signal prioritization considers campaign context
- Story 9.5: Exit management triggers status transitions

Author: Story 9.1
"""

from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator, model_validator


class EntryDetails(BaseModel):
    """
    Individual pattern entry details within a campaign (Story 9.7).

    Tracks metadata for each entry point (Spring/SOS/LPS) in the campaign's
    multi-phase position building sequence.

    Fields:
    -------
    - pattern_type: SPRING | SOS | LPS
    - entry_price: Actual fill price
    - shares: Position size
    - risk_allocated: Percentage of portfolio allocated
    - position_id: UUID linking to Position record

    Example:
    --------
    >>> entry = EntryDetails(
    ...     pattern_type="SPRING",
    ...     entry_price=Decimal("150.00"),
    ...     shares=Decimal("100"),
    ...     risk_allocated=Decimal("2.0"),
    ...     position_id=UUID("...")
    ... )
    """

    pattern_type: Literal["SPRING", "SOS", "LPS"] = Field(..., description="Entry pattern type")
    entry_price: Decimal = Field(
        ..., decimal_places=8, max_digits=18, description="Actual fill price"
    )
    shares: Decimal = Field(
        ..., ge=Decimal("0.01"), decimal_places=8, max_digits=18, description="Position size"
    )
    risk_allocated: Decimal = Field(
        ..., decimal_places=2, max_digits=5, description="% of portfolio allocated"
    )
    position_id: UUID = Field(..., description="UUID linking to Position record")

    model_config = {"json_encoders": {Decimal: str, UUID: str}}


class CampaignStatus(str, Enum):
    """
    Campaign lifecycle states (AC: 4).

    State Transitions:
    ------------------
    ACTIVE → MARKUP: After SOS entry confirmed
    MARKUP → COMPLETED: All positions closed successfully
    ACTIVE → INVALIDATED: Stop hit or range breakdown
    MARKUP → INVALIDATED: Emergency exit triggered
    COMPLETED: Terminal state (no further transitions)
    INVALIDATED: Terminal state (no further transitions)
    """

    ACTIVE = "ACTIVE"  # Campaign in progress, open positions
    MARKUP = "MARKUP"  # SOS confirmed, in markup phase
    COMPLETED = "COMPLETED"  # All positions closed, campaign finished
    INVALIDATED = "INVALIDATED"  # Campaign invalidated (stop hit, spring low break)


class CampaignPosition(BaseModel):
    """
    Individual position within a campaign (Spring, SOS, or LPS entry).

    Represents a single entry point in the multi-phase position building
    process. Each position links to a TradeSignal and tracks real-time P&L.

    Fields:
    -------
    - position_id: Unique position identifier (UUID)
    - signal_id: Foreign key to TradeSignal
    - pattern_type: SPRING | SOS | LPS
    - entry_date: When position opened (UTC)
    - entry_price: Actual fill price (NUMERIC 18,8)
    - shares: Position size in shares/lots (NUMERIC 18,8)
    - stop_loss: Initial stop loss level
    - target_price: Primary target (Jump level)
    - current_price: Last market price (real-time update)
    - current_pnl: Unrealized P&L = (current_price - entry_price) * shares
    - status: OPEN | CLOSED | PARTIAL
    - allocation_percent: Portion of campaign budget (e.g., 2.0% for Spring)
    - risk_amount: Dollar risk = (entry_price - stop_loss) * shares

    Example:
    --------
    >>> position = CampaignPosition(
    ...     signal_id=UUID("..."),
    ...     pattern_type="SPRING",
    ...     entry_date=datetime.now(UTC),
    ...     entry_price=Decimal("150.25"),
    ...     shares=Decimal("100"),
    ...     stop_loss=Decimal("148.00"),
    ...     target_price=Decimal("156.00"),
    ...     current_price=Decimal("152.00"),
    ...     status="OPEN",
    ...     allocation_percent=Decimal("2.0"),
    ...     risk_amount=Decimal("225.00")
    ... )
    """

    position_id: UUID = Field(default_factory=uuid4, description="Unique position identifier")
    signal_id: UUID = Field(..., description="Foreign key to TradeSignal")
    pattern_type: Literal["SPRING", "SOS", "LPS"] = Field(..., description="Entry pattern type")
    entry_date: datetime = Field(..., description="Position open timestamp (UTC)")
    entry_price: Decimal = Field(
        ..., decimal_places=8, max_digits=18, description="Actual fill price"
    )
    shares: Decimal = Field(
        ..., ge=Decimal("0.01"), decimal_places=8, max_digits=18, description="Position size"
    )
    stop_loss: Decimal = Field(
        ..., decimal_places=8, max_digits=18, description="Initial stop loss level"
    )
    target_price: Decimal = Field(
        ..., decimal_places=8, max_digits=18, description="Primary target (Jump level)"
    )
    current_price: Decimal = Field(
        ..., decimal_places=8, max_digits=18, description="Last market price (real-time)"
    )
    current_pnl: Decimal = Field(..., decimal_places=2, max_digits=12, description="Unrealized P&L")
    status: Literal["OPEN", "CLOSED", "PARTIAL"] = Field(..., description="Position status")
    allocation_percent: Decimal = Field(
        ..., decimal_places=2, max_digits=5, description="% of campaign budget"
    )
    risk_amount: Decimal = Field(..., decimal_places=2, max_digits=12, description="Dollar risk")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Creation timestamp"
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Last update timestamp"
    )

    @field_validator("entry_date", "created_at", "updated_at")
    @classmethod
    def enforce_utc(cls, v: datetime) -> datetime:
        """Ensure all datetimes are in UTC timezone."""
        if v.tzinfo is None:
            raise ValueError("Datetime must have timezone (UTC required)")
        if v.tzinfo != UTC:
            # Convert to UTC if in different timezone
            v = v.astimezone(UTC)
        return v

    @model_validator(mode="after")
    def calculate_current_pnl(self) -> "CampaignPosition":
        """Calculate current_pnl from price difference and shares."""
        calculated_pnl = (self.current_price - self.entry_price) * self.shares
        # Round to 2 decimal places for money
        calculated_pnl = calculated_pnl.quantize(Decimal("0.01"))
        # Allow small rounding differences (within 1 cent)
        if abs(self.current_pnl - calculated_pnl) > Decimal("0.01"):
            raise ValueError(
                f"current_pnl {self.current_pnl} doesn't match calculated "
                f"{calculated_pnl} = ({self.current_price} - {self.entry_price}) * {self.shares}"
            )
        return self

    model_config = {"json_encoders": {Decimal: str, datetime: lambda v: v.isoformat(), UUID: str}}


class Campaign(BaseModel):
    """
    Multi-phase position building campaign within same trading range (AC: 2).

    A campaign tracks all signals (Spring → SOS → LPS) within a single trading
    range as a unified entity. Enforces 5% maximum campaign risk (FR18) and
    manages lifecycle states (ACTIVE → MARKUP → COMPLETED | INVALIDATED).

    Campaign ID Format (AC: 3):
    ----------------------------
    {symbol}-{range_start_date}
    Example: "AAPL-2024-10-15"

    Lifecycle States (AC: 4):
    --------------------------
    ACTIVE: Campaign in progress, open positions
    MARKUP: SOS confirmed, in markup phase
    COMPLETED: All positions closed successfully
    INVALIDATED: Stop hit or range breakdown

    State Transitions:
    ------------------
    ACTIVE → MARKUP (after SOS entry)
    MARKUP → COMPLETED (all positions closed)
    ACTIVE → INVALIDATED (stop hit)
    MARKUP → INVALIDATED (emergency exit)

    Fields:
    -------
    - id: Campaign unique ID (UUID, PK)
    - campaign_id: Human-readable ID format: {symbol}-{range_start_date}
    - symbol: Ticker symbol (e.g., "AAPL")
    - timeframe: Bar interval (e.g., "1h", "1d")
    - trading_range_id: Foreign key to TradingRange
    - status: Current lifecycle state (ACTIVE, MARKUP, COMPLETED, INVALIDATED)
    - phase: Wyckoff phase (C, D, E)
    - positions: All campaign positions (Spring, SOS, LPS)
    - total_risk: Total dollar risk across all positions
    - total_allocation: Total % of portfolio allocated (max 5%, FR18)
    - current_risk: Current open risk (updated as positions close)
    - weighted_avg_entry: Average entry price across positions
    - total_shares: Sum of all position shares
    - total_pnl: Current unrealized P&L (sum of position PnLs)
    - start_date: Campaign start date (UTC)
    - completed_at: When campaign finished (UTC, nullable)
    - invalidation_reason: If invalidated, reason (e.g., "Spring low break")
    - version: Optimistic locking version (increment on update)

    Example:
    --------
    >>> campaign = Campaign(
    ...     campaign_id="AAPL-2024-10-15",
    ...     symbol="AAPL",
    ...     timeframe="1d",
    ...     trading_range_id=UUID("..."),
    ...     status=CampaignStatus.ACTIVE,
    ...     phase="C",
    ...     positions=[position1, position2],
    ...     total_risk=Decimal("450.00"),
    ...     total_allocation=Decimal("3.5"),
    ...     start_date=datetime.now(UTC)
    ... )
    """

    # Core identification
    id: UUID = Field(default_factory=uuid4, description="Campaign unique ID (PK)")
    campaign_id: str = Field(..., max_length=50, description="Human-readable ID: {symbol}-{date}")
    symbol: str = Field(..., max_length=20, description="Ticker symbol")
    timeframe: str = Field(..., max_length=5, description="Bar interval (e.g., 1h, 1d)")
    trading_range_id: UUID = Field(..., description="Foreign key to TradingRange")

    # Lifecycle management
    status: CampaignStatus = Field(..., description="Current lifecycle state")
    phase: Literal["C", "D", "E"] = Field(..., description="Wyckoff phase")

    # Positions and risk tracking
    positions: list[CampaignPosition] = Field(
        default_factory=list, description="All campaign positions"
    )
    entries: dict[str, EntryDetails] = Field(
        default_factory=dict,
        description="Entry details by pattern type (SPRING/SOS/LPS mapping)",
    )
    total_risk: Decimal = Field(
        ..., decimal_places=2, max_digits=12, description="Total dollar risk"
    )
    total_allocation: Decimal = Field(
        ..., decimal_places=2, max_digits=5, description="Total % of portfolio (max 5%)"
    )
    current_risk: Decimal = Field(
        ..., decimal_places=2, max_digits=12, description="Current open risk"
    )
    weighted_avg_entry: Decimal | None = Field(
        None, decimal_places=8, max_digits=18, description="Average entry price"
    )
    total_shares: Decimal = Field(
        ..., ge=Decimal("0"), decimal_places=8, max_digits=18, description="Sum of position shares"
    )
    total_pnl: Decimal = Field(
        ..., decimal_places=2, max_digits=12, description="Current unrealized P&L"
    )

    # Timestamps
    start_date: datetime = Field(..., description="Campaign start date (UTC)")
    completed_at: datetime | None = Field(None, description="Campaign completion timestamp (UTC)")
    invalidation_reason: str | None = Field(None, description="Invalidation reason if applicable")

    # Optimistic locking
    version: int = Field(default=1, ge=1, description="Optimistic locking version")

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Creation timestamp"
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Last update timestamp"
    )

    @field_validator("total_allocation")
    @classmethod
    def validate_allocation_limit(cls, v: Decimal) -> Decimal:
        """Enforce FR18: 5% campaign maximum."""
        if v > Decimal("5.0"):
            raise ValueError(f"Campaign allocation {v}% exceeds maximum limit of 5.0% (FR18)")
        return v

    @field_validator("start_date", "completed_at", "created_at", "updated_at")
    @classmethod
    def enforce_utc(cls, v: datetime | None) -> datetime | None:
        """Ensure all datetimes are in UTC timezone."""
        if v is None:
            return None
        if v.tzinfo is None:
            raise ValueError("Datetime must have timezone (UTC required)")
        if v.tzinfo != UTC:
            v = v.astimezone(UTC)
        return v

    @model_validator(mode="after")
    def validate_terminal_states(self) -> "Campaign":
        """Validate completed_at is set for terminal states."""
        if self.status in [CampaignStatus.COMPLETED, CampaignStatus.INVALIDATED]:
            if self.completed_at is None:
                raise ValueError(f"completed_at must be set for terminal state {self.status.value}")
        if self.status == CampaignStatus.INVALIDATED:
            if self.invalidation_reason is None:
                raise ValueError("invalidation_reason must be set when status is INVALIDATED")
        return self

    def get_open_positions(self) -> list[CampaignPosition]:
        """
        Get all open positions in campaign.

        Returns:
        --------
        list[CampaignPosition]
            Positions with status="OPEN"
        """
        return [p for p in self.positions if p.status == "OPEN"]

    def calculate_total_pnl(self) -> Decimal:
        """
        Calculate total unrealized P&L across all positions.

        Returns:
        --------
        Decimal
            Sum of all position current_pnl values
        """
        return sum((p.current_pnl for p in self.positions), Decimal("0.00"))

    def is_active(self) -> bool:
        """
        Check if campaign is in active state (can accept new positions).

        Returns:
        --------
        bool
            True if status in [ACTIVE, MARKUP]
        """
        return self.status in [CampaignStatus.ACTIVE, CampaignStatus.MARKUP]

    def can_add_position(self, new_allocation: Decimal) -> bool:
        """
        Check if new position can be added without exceeding 5% limit (FR18).

        Parameters:
        -----------
        new_allocation : Decimal
            Allocation % for new position (e.g., Decimal("1.5") for 1.5%)

        Returns:
        --------
        bool
            True if (total_allocation + new_allocation) <= 5.0%
        """
        return (self.total_allocation + new_allocation) <= Decimal("5.0")

    model_config = {"json_encoders": {Decimal: str, datetime: lambda v: v.isoformat(), UUID: str}}


# Maximum campaign risk (FR18)
MAX_CAMPAIGN_RISK_PCT = Decimal("5.0")

# Valid state transitions (AC: 4)
VALID_CAMPAIGN_TRANSITIONS: dict[CampaignStatus, list[CampaignStatus]] = {
    CampaignStatus.ACTIVE: [CampaignStatus.MARKUP, CampaignStatus.INVALIDATED],
    CampaignStatus.MARKUP: [CampaignStatus.COMPLETED, CampaignStatus.INVALIDATED],
    CampaignStatus.COMPLETED: [],  # Terminal state
    CampaignStatus.INVALIDATED: [],  # Terminal state
}
