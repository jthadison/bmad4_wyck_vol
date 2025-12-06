"""
Position Tracking Data Model - Campaign Position Management System

Purpose:
--------
Provides Pydantic model for tracking individual trading positions within campaigns.
Each position represents a single entry (Spring, SOS, or LPS) with comprehensive
tracking of entry details, current P&L, and lifecycle status.

Data Model:
-----------
Position: Individual position entry tracking with real-time P&L calculation

Integration:
------------
- Story 9.1: Links to campaigns via campaign_id FK
- Story 8.8: Links to signals via signal_id FK for traceability
- Story 9.4: Position tracking with real-time updates

Author: Story 9.4
"""

from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_serializer


class PositionStatus(str, Enum):
    """
    Position lifecycle status.

    Values:
    -------
    - OPEN: Position is currently active
    - CLOSED: Position has been exited (target hit, stopped out, or manually closed)
    """

    OPEN = "OPEN"
    CLOSED = "CLOSED"


class Position(BaseModel):
    """
    Individual trading position within a campaign.

    Represents a single entry (Spring, SOS, or LPS) with complete tracking
    of entry details, current market state, and P&L metrics. Positions remain
    in the database after closure for historical analysis and compliance.

    Fields:
    -------
    Core Identification:
    - id: Unique position identifier (UUID)
    - campaign_id: Parent campaign (FK to campaigns.id)
    - signal_id: Source signal for traceability (FK to signals.id)
    - symbol: Trading symbol (e.g., "AAPL", "EUR/USD")
    - timeframe: Bar interval (e.g., "1h", "4h")
    - pattern_type: SPRING | SOS | LPS

    Entry Details:
    - entry_date: Position entry timestamp (UTC)
    - entry_price: Actual fill price (NUMERIC(18,8))
    - shares: Position size (whole shares for stocks, lots for forex)
    - stop_loss: Stop loss price

    Current State (OPEN positions):
    - current_price: Latest market price
    - current_pnl: Unrealized P&L = (current_price - entry_price) × shares

    Exit Details (CLOSED positions):
    - status: OPEN | CLOSED
    - closed_date: Exit timestamp (UTC)
    - exit_price: Actual exit fill price
    - realized_pnl: Final P&L = (exit_price - entry_price) × shares

    Constraints:
    ------------
    - All price/PnL fields use Decimal type (NEVER float) for precision
    - All datetime fields enforce UTC timezone via validator
    - Closed positions maintained in database (compliance requirement)
    - Foreign keys: campaign_id (ON DELETE RESTRICT), signal_id

    Example:
    --------
    >>> from decimal import Decimal
    >>> from datetime import datetime, UTC
    >>> from uuid import uuid4
    >>> position = Position(
    ...     campaign_id=uuid4(),
    ...     signal_id=uuid4(),
    ...     symbol="AAPL",
    ...     timeframe="1h",
    ...     entry_date=datetime.now(UTC),
    ...     entry_price=Decimal("150.00"),
    ...     shares=Decimal("100"),
    ...     stop_loss=Decimal("148.00"),
    ...     current_price=Decimal("152.00"),
    ...     current_pnl=Decimal("200.00"),
    ...     status=PositionStatus.OPEN,
    ...     pattern_type="SPRING"
    ... )
    """

    # Core identification
    id: UUID = Field(default_factory=uuid4, description="Unique position identifier")
    campaign_id: UUID = Field(..., description="Parent campaign (FK to campaigns.id)")
    signal_id: UUID = Field(..., description="Source signal for traceability (FK to signals.id)")
    symbol: str = Field(..., max_length=20, description="Trading symbol")
    timeframe: str = Field(..., max_length=10, description="Bar interval")
    pattern_type: str = Field(
        ..., max_length=10, description="SPRING | SOS | LPS (entry pattern type)"
    )

    # Entry details
    entry_date: datetime = Field(..., description="Position entry timestamp (UTC)")
    entry_price: Decimal = Field(
        ...,
        decimal_places=8,
        max_digits=18,
        gt=Decimal("0"),
        description="Actual fill price",
    )
    shares: Decimal = Field(
        ...,
        decimal_places=8,
        max_digits=18,
        gt=Decimal("0"),
        description="Position size (shares/lots)",
    )
    stop_loss: Decimal = Field(
        ...,
        decimal_places=8,
        max_digits=18,
        gt=Decimal("0"),
        description="Stop loss price",
    )

    # Current state (OPEN positions)
    current_price: Decimal | None = Field(
        None,
        decimal_places=8,
        max_digits=18,
        description="Latest market price (OPEN positions only)",
    )
    current_pnl: Decimal | None = Field(
        None,
        decimal_places=8,
        max_digits=18,
        description="Unrealized P&L = (current_price - entry_price) × shares",
    )

    # Status
    status: PositionStatus = Field(default=PositionStatus.OPEN, description="OPEN | CLOSED")

    # Exit details (CLOSED positions)
    closed_date: datetime | None = Field(
        None, description="Exit timestamp (UTC, CLOSED positions only)"
    )
    exit_price: Decimal | None = Field(
        None,
        decimal_places=8,
        max_digits=18,
        description="Actual exit fill price (CLOSED positions only)",
    )
    realized_pnl: Decimal | None = Field(
        None,
        decimal_places=8,
        max_digits=18,
        description="Final P&L = (exit_price - entry_price) × shares",
    )

    # Timestamps
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Record creation timestamp"
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Record last update timestamp"
    )

    model_config = ConfigDict(
        json_encoders={Decimal: str, datetime: lambda v: v.isoformat()},
        use_enum_values=False,  # Keep enum objects, not string values
    )

    @field_validator("entry_date", "closed_date", "created_at", "updated_at", mode="before")
    @classmethod
    def ensure_utc(cls, v: datetime | str | None) -> datetime | None:
        """
        Enforce UTC timezone on all datetime fields.

        Critical for accurate timestamp handling across timezones and preventing
        timezone-related bugs in P&L calculations and audit trails.

        Parameters:
        -----------
        v : datetime | str | None
            Datetime value to validate

        Returns:
        --------
        datetime | None
            UTC-aware datetime or None

        Raises:
        -------
        ValueError
            If datetime cannot be parsed or converted to UTC
        """
        if v is None:
            return None

        # Handle string timestamps (from JSON deserialization)
        if isinstance(v, str):
            parsed = datetime.fromisoformat(v.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)

        # Handle datetime objects
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v.astimezone(UTC)

    @field_validator("pattern_type")
    @classmethod
    def validate_pattern_type(cls, v: str) -> str:
        """
        Validate pattern type is valid entry pattern.

        Valid entry patterns: SPRING, SOS, LPS

        Parameters:
        -----------
        v : str
            Pattern type to validate

        Returns:
        --------
        str
            Validated pattern type (uppercase)

        Raises:
        -------
        ValueError
            If pattern_type is invalid
        """
        valid_patterns = {"SPRING", "SOS", "LPS"}
        v_upper = v.upper()
        if v_upper not in valid_patterns:
            raise ValueError(
                f"Invalid pattern type: {v}. Valid entry patterns: {', '.join(valid_patterns)}"
            )
        return v_upper

    @field_validator("stop_loss")
    @classmethod
    def validate_stop_below_entry(cls, v: Decimal, info) -> Decimal:
        """
        Validate stop loss is below entry price (long positions).

        Parameters:
        -----------
        v : Decimal
            Stop loss price to validate

        Returns:
        --------
        Decimal
            Validated stop loss price

        Raises:
        -------
        ValueError
            If stop_loss >= entry_price
        """
        values = info.data
        if "entry_price" in values and v >= values["entry_price"]:
            raise ValueError(
                f"Stop loss {v} must be below entry price {values['entry_price']} for long positions"
            )
        return v

    @model_serializer
    def serialize_model(self) -> dict[str, Any]:
        """
        Serialize model with Decimal as strings and UUID as strings.

        Preserves decimal precision in JSON by serializing as strings,
        avoiding floating-point precision loss.

        Returns:
        --------
        dict[str, Any]
            Serialized model data
        """
        return {
            "id": str(self.id),
            "campaign_id": str(self.campaign_id),
            "signal_id": str(self.signal_id),
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "pattern_type": self.pattern_type,
            "entry_date": self.entry_date.isoformat(),
            "entry_price": str(self.entry_price),
            "shares": str(self.shares),
            "stop_loss": str(self.stop_loss),
            "current_price": str(self.current_price) if self.current_price else None,
            "current_pnl": str(self.current_pnl) if self.current_pnl else None,
            "status": self.status.value,
            "closed_date": self.closed_date.isoformat() if self.closed_date else None,
            "exit_price": str(self.exit_price) if self.exit_price else None,
            "realized_pnl": str(self.realized_pnl) if self.realized_pnl else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    def calculate_current_pnl(self, current_price: Decimal) -> Decimal:
        """
        Calculate unrealized P&L based on current market price.

        Formula: (current_price - entry_price) × shares

        Parameters:
        -----------
        current_price : Decimal
            Current market price

        Returns:
        --------
        Decimal
            Unrealized P&L (positive = profit, negative = loss)

        Example:
        --------
        >>> position = Position(...)  # entry_price=150.00, shares=100
        >>> position.calculate_current_pnl(Decimal("152.00"))
        Decimal('200.00')  # (152 - 150) × 100 = $200 profit
        """
        return (current_price - self.entry_price) * self.shares

    def calculate_realized_pnl(self, exit_price: Decimal) -> Decimal:
        """
        Calculate realized P&L based on exit price.

        Formula: (exit_price - entry_price) × shares

        Parameters:
        -----------
        exit_price : Decimal
            Actual exit fill price

        Returns:
        --------
        Decimal
            Realized P&L (positive = profit, negative = loss)

        Example:
        --------
        >>> position = Position(...)  # entry_price=150.00, shares=100
        >>> position.calculate_realized_pnl(Decimal("158.00"))
        Decimal('800.00')  # (158 - 150) × 100 = $800 profit
        """
        return (exit_price - self.entry_price) * self.shares
