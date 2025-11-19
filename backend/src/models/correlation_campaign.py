"""
Campaign Model for Correlation Tracking - Story 7.5

Purpose:
--------
Provides enhanced Campaign model with sector/asset_class/geography fields
required for campaign-level correlation tracking in Story 7.5.

This extends the basic Campaign model from Story 7.4 with correlation metadata.

Data Model:
-----------
- CampaignForCorrelation: Campaign with correlation metadata

Integration:
------------
- Story 7.4: Basic Campaign model (id, symbol, current_risk, status)
- Story 7.5: Enhanced with sector, asset_class, geography for correlation

Author: Story 7.5
"""

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from src.models.portfolio import Position


class CampaignForCorrelation(BaseModel):
    """
    Campaign model for correlation tracking (Story 7.5 AC 11).

    Enhanced Campaign model with sector/asset_class/geography metadata
    required for campaign-level correlation risk calculations.

    Campaign vs Position Distinction:
    ----------------------------------
    - A campaign may have multiple positions (Spring, LPS add #1, LPS add #2)
    - For correlation purposes: 3 positions in same campaign = 1 correlation unit
    - New campaigns in same sector = separate correlation units

    Fields:
    -------
    - campaign_id: Campaign identifier (UUID)
    - symbol: Trading symbol
    - sector: Sector classification (from sector_mappings.yaml)
    - asset_class: Asset class (from sector_mappings.yaml)
    - geography: Optional geography (from sector_mappings.yaml)
    - total_campaign_risk: Sum of all position_risk_pct in this campaign
    - positions: All positions belonging to this campaign
    - status: Campaign status (ACTIVE, COMPLETED, etc.)

    Example:
    --------
    >>> from decimal import Decimal
    >>> from uuid import uuid4
    >>> campaign = CampaignForCorrelation(
    ...     campaign_id=uuid4(),
    ...     symbol="AAPL",
    ...     sector="Technology",
    ...     asset_class="stock",
    ...     geography="US",
    ...     total_campaign_risk=Decimal("3.5"),
    ...     positions=[],
    ...     status="ACTIVE"
    ... )
    """

    campaign_id: UUID = Field(..., description="Campaign identifier")
    symbol: str = Field(..., max_length=20, description="Trading symbol")
    sector: str = Field(..., description="Sector classification")
    asset_class: str = Field(..., description="Asset class (stock, futures, crypto, forex)")
    geography: str | None = Field(None, description="Optional geography (US, EU, ASIA, etc.)")
    total_campaign_risk: Decimal = Field(
        ..., decimal_places=4, max_digits=6, description="Sum of all positions in campaign"
    )
    positions: list[Position] = Field(
        default_factory=list, description="All positions in this campaign"
    )
    status: str = Field(..., description="Campaign status (ACTIVE, COMPLETED, etc.)")
