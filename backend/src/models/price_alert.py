"""
Price Alert Pydantic Models.

Defines request/response models for the price alert system.
Supports Wyckoff-specific alert types aligned with accumulation/distribution methodology.
"""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AlertType(StrEnum):
    """
    Types of price alerts supported.

    - PRICE_LEVEL: Trigger when price crosses a user-defined level
    - CREEK: Trigger when price breaks above Ice/Creek resistance (SOS signal)
    - ICE: Trigger when price tests Ice from above (LPS zone)
    - SPRING: Trigger when price dips below Spring support level (Phase C shakeout)
    - PHASE_CHANGE: Trigger when Wyckoff phase changes for the symbol
    """

    PRICE_LEVEL = "price_level"
    CREEK = "creek"
    ICE = "ice"
    SPRING = "spring"
    PHASE_CHANGE = "phase_change"


class AlertDirection(StrEnum):
    """Direction for price level crossing."""

    ABOVE = "above"
    BELOW = "below"


class WyckoffLevelType(StrEnum):
    """
    Wyckoff structural level types.

    Used with Creek/Ice/Spring alert types to specify which
    structural level to monitor.
    """

    CREEK = "creek"  # Resistance line above accumulation range
    ICE = "ice"  # Resistance/support line within accumulation range (becomes support after SOS breakout)
    SPRING = "spring"  # Below-support shakeout level (Phase C)
    SUPPLY = "supply"  # Supply zone / selling pressure
    DEMAND = "demand"  # Demand zone / buying pressure


class PriceAlertCreate(BaseModel):
    """Request model for creating a new price alert."""

    symbol: str = Field(..., min_length=1, max_length=20, description="Trading symbol (e.g., AAPL)")
    alert_type: AlertType = Field(..., description="Type of alert")
    price_level: Decimal | None = Field(
        None,
        ge=Decimal("0"),
        description="Price level to trigger at (required for PRICE_LEVEL, CREEK, ICE, SPRING)",
    )
    direction: AlertDirection | None = Field(
        None,
        description="Direction for price crossing (required for PRICE_LEVEL)",
    )
    wyckoff_level_type: WyckoffLevelType | None = Field(
        None,
        description="Wyckoff level type (optional context for Creek/Ice/Spring alerts)",
    )
    notes: str | None = Field(None, max_length=500, description="Optional trader notes")


class PriceAlertUpdate(BaseModel):
    """Request model for updating an existing price alert (all fields optional)."""

    price_level: Decimal | None = Field(None, ge=Decimal("0"))
    direction: AlertDirection | None = None
    wyckoff_level_type: WyckoffLevelType | None = None
    is_active: bool | None = None
    notes: str | None = Field(None, max_length=500)


class PriceAlert(BaseModel):
    """Response model for a price alert."""

    id: UUID
    user_id: UUID
    symbol: str
    alert_type: AlertType
    price_level: Decimal | None
    direction: AlertDirection | None
    wyckoff_level_type: WyckoffLevelType | None
    is_active: bool
    notes: str | None
    created_at: datetime
    triggered_at: datetime | None

    model_config = ConfigDict(
        json_encoders={
            Decimal: str,
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
        }
    )


class PriceAlertListResponse(BaseModel):
    """Paginated list of price alerts."""

    data: list[PriceAlert]
    total: int
    active_count: int

    model_config = ConfigDict(
        json_encoders={
            Decimal: str,
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
        }
    )
