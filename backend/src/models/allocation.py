"""
AllocationPlan data model for BMAD position allocation.

This module defines the AllocationPlan model which tracks how campaign budget
is allocated according to BMAD 40/30/30 methodology (Story 9.2, FR23).
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class AllocationPlan(BaseModel):
    """
    BMAD allocation plan for a single signal within a campaign.

    Tracks how campaign budget is allocated according to BMAD 40/30/30 methodology:
    - Spring: 40% of campaign budget (2.0% of 5% max)
    - SOS: 30% of campaign budget (1.5% of 5% max)
    - LPS: 30% of campaign budget (1.5% of 5% max)

    The plan captures both the target allocation (BMAD) and actual risk (FR16),
    enabling audit trail and rebalancing when earlier entries are skipped.

    Attributes
    ----------
    id : UUID
        Unique identifier for this allocation plan
    campaign_id : UUID
        Campaign this allocation is for
    signal_id : UUID
        Signal being allocated
    pattern_type : Literal["SPRING", "SOS", "LPS"]
        Pattern type for this allocation
    bmad_allocation_pct : Decimal
        BMAD allocation percentage (0.40 for Spring, 0.30 for SOS/LPS)
    target_risk_pct : Decimal
        Target risk as % of campaign budget (e.g., 2.0% for Spring 40% of 5%)
    actual_risk_pct : Decimal
        Actual risk calculated from position sizing (from FR16: 0.5%, 1.0%, 0.6%)
    position_size_shares : Decimal
        Number of shares calculated for this position
    allocation_used : Decimal
        Actual % of campaign budget consumed
    remaining_budget : Decimal
        Remaining campaign budget after this allocation
    is_rebalanced : bool
        True if allocation was rebalanced due to skipped earlier entry
    rebalance_reason : Optional[str]
        Explanation of why rebalancing occurred
    approved : bool
        True if allocation approved, False if rejected
    rejection_reason : Optional[str]
        If rejected, explanation of why
    timestamp : datetime
        When this allocation plan was created (UTC)

    Examples
    --------
    >>> # Normal Spring allocation (40% of 5% = 2.0%)
    >>> plan = AllocationPlan(
    ...     campaign_id=UUID("..."),
    ...     signal_id=UUID("..."),
    ...     pattern_type="SPRING",
    ...     bmad_allocation_pct=Decimal("0.40"),
    ...     target_risk_pct=Decimal("2.0"),
    ...     actual_risk_pct=Decimal("0.5"),
    ...     position_size_shares=Decimal("100"),
    ...     allocation_used=Decimal("0.5"),
    ...     remaining_budget=Decimal("4.5"),
    ...     approved=True
    ... )
    >>> assert plan.validate_within_campaign_budget()

    >>> # Rebalanced SOS allocation (Spring skipped, SOS gets 70%)
    >>> plan = AllocationPlan(
    ...     campaign_id=UUID("..."),
    ...     signal_id=UUID("..."),
    ...     pattern_type="SOS",
    ...     bmad_allocation_pct=Decimal("0.70"),
    ...     target_risk_pct=Decimal("3.5"),
    ...     actual_risk_pct=Decimal("1.0"),
    ...     position_size_shares=Decimal("50"),
    ...     allocation_used=Decimal("1.0"),
    ...     remaining_budget=Decimal("4.0"),
    ...     is_rebalanced=True,
    ...     rebalance_reason="Spring entry not taken, reallocating 40% to SOS",
    ...     approved=True
    ... )
    """

    id: UUID = Field(default_factory=uuid4)
    campaign_id: UUID
    signal_id: UUID
    pattern_type: Literal["SPRING", "SOS", "LPS"]

    # BMAD allocation (FR23)
    bmad_allocation_pct: Decimal  # 0.40 (40%), 0.30 (30%), or rebalanced value
    target_risk_pct: Decimal  # Target risk as % of campaign budget

    # Actual risk (FR16)
    actual_risk_pct: Decimal  # Actual risk from position sizing
    position_size_shares: Decimal  # Number of shares calculated

    # Budget tracking
    allocation_used: Decimal  # Actual % of campaign budget consumed
    remaining_budget: Decimal  # Remaining campaign budget after allocation

    # Rebalancing (AC: 5)
    is_rebalanced: bool = False
    rebalance_reason: Optional[str] = None

    # Approval/Rejection (AC: 7)
    approved: bool
    rejection_reason: Optional[str] = None

    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def validate_within_campaign_budget(self) -> bool:
        """
        Check if allocation stays within 5% campaign maximum.

        Returns
        -------
        bool
            True if allocation_used <= 5.0%, False otherwise
        """
        from src.config import CAMPAIGN_MAX_RISK_PCT

        return self.allocation_used <= CAMPAIGN_MAX_RISK_PCT

    model_config = {
        "json_encoders": {
            Decimal: str,
            datetime: lambda v: v.isoformat(),
            UUID: str,
        },
        "json_schema_extra": {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "campaign_id": "123e4567-e89b-12d3-a456-426614174001",
                "signal_id": "123e4567-e89b-12d3-a456-426614174002",
                "pattern_type": "SPRING",
                "bmad_allocation_pct": "0.4000",
                "target_risk_pct": "2.00",
                "actual_risk_pct": "0.50",
                "position_size_shares": "100.00000000",
                "allocation_used": "0.50",
                "remaining_budget": "4.50",
                "is_rebalanced": False,
                "rebalance_reason": None,
                "approved": True,
                "rejection_reason": None,
                "timestamp": "2024-10-15T10:30:00Z",
            }
        },
    }
