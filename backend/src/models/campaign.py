"""
Campaign Risk Tracking Data Models - Wyckoff BMAD Allocation System

Purpose:
--------
Provides Pydantic models for tracking campaign-level risk (Spring → SOS → LPS
entry sequences within a single trading range) with BMAD allocation enforcement
and the 5% maximum campaign risk limit (FR18).

Data Models:
------------
1. CampaignEntry: Individual position entry within a campaign
2. CampaignRisk: Campaign risk tracking with BMAD allocation breakdown

Wyckoff BMAD Allocation (AC 4):
--------------------------------
Authentic Wyckoff 3-Entry Model - Volume-Aligned & Risk-Optimized:

- Spring: 40% of campaign budget (HIGHEST - maximum accumulation opportunity)
- SOS: 35% of campaign budget (Phase D breakout - primary confirmation entry)
- LPS: 25% of campaign budget (Phase D pullback - secondary entry, optional)

Wyckoff Rationale:
------------------
- Secondary Test (ST) is a CONFIRMATION EVENT, not an entry pattern
- ST validates that Spring was successful (holds on reduced volume) - NO capital deployed
- Entry occurs at SOS AFTER ST confirms accumulation is complete

Volume Analysis (Victoria - Volume Specialist):
------------------------------------------------
- Spring receives HIGHEST allocation (40%) due to climactic volume at shake-out
- Climactic volume = maximum institutional accumulation (Composite Operator fills bulk of position)
- By SOS, accumulation is essentially complete - professionals already positioned from Spring

Risk Management (Rachel - Risk Manager):
-----------------------------------------
- Spring has tightest stops (2-3% below Spring low) = lowest risk
- Spring has best R:R ratio (8-12R to target) = highest reward
- Fundamental principle: Allocate MORE capital to LOWER-risk, HIGHER-reward opportunities
- SOS has wider stops (5-7% below range) = higher risk, moderate allocation appropriate

Campaign Flexibility (AC 11, 12):
----------------------------------
- Not all campaigns include all entries (e.g., SOS-only campaigns common)
- Allocations adjust proportionally based on which entries are taken
- Spring is optional but offers best risk/reward when available

Integration:
------------
- Story 7.1: Uses pattern risk percentages
- Story 7.2: Uses position_risk_pct from PositionSizing
- Story 7.3: Campaign risk is subset of portfolio heat
- Story 7.4: Core data models for campaign tracking

Author: Story 7.4
"""

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class CampaignEntry(BaseModel):
    """
    Individual position entry within a campaign.

    Represents a single position (Spring, SOS, or LPS entry) within
    a campaign's entry sequence. Note: ST (Secondary Test) is a
    confirmation event, not an entry pattern.

    Fields:
    -------
    - pattern_type: SPRING | SOS | LPS (ST is NOT a valid entry pattern)
    - position_risk_pct: Risk % for this position
    - allocation_percentage: % of campaign budget used
    - symbol: Trading symbol
    - status: OPEN | CLOSED | STOPPED | TARGET_HIT | EXPIRED

    Example:
    --------
    >>> from decimal import Decimal
    >>> entry = CampaignEntry(
    ...     pattern_type="SPRING",
    ...     position_risk_pct=Decimal("2.0"),
    ...     allocation_percentage=Decimal("40.0"),
    ...     symbol="AAPL",
    ...     status="OPEN"
    ... )
    """

    pattern_type: str = Field(
        ...,
        description="SPRING | SOS | LPS (ST is confirmation event, not entry)",
    )

    position_risk_pct: Decimal = Field(
        ...,
        decimal_places=4,
        max_digits=6,
        description="Risk % for this position",
    )

    allocation_percentage: Decimal = Field(
        ...,
        decimal_places=4,
        max_digits=6,
        description="% of campaign budget used",
    )

    symbol: str = Field(..., max_length=20, description="Trading symbol")

    status: str = Field(..., description="OPEN | CLOSED | STOPPED | TARGET_HIT | EXPIRED")

    @field_validator("pattern_type")
    @classmethod
    def validate_pattern_type(cls, v: str) -> str:
        """
        Validate pattern type is valid entry pattern.

        ST (Secondary Test) is a confirmation event in Phase C that validates
        the Spring was successful. It is NOT an entry point for deploying capital.

        Valid entry patterns: SPRING, SOS, LPS

        Raises:
        -------
        ValueError
            If pattern_type is ST or invalid
        """
        valid_patterns = {"SPRING", "SOS", "LPS"}
        if v == "ST":
            raise ValueError(
                "ST (Secondary Test) is a confirmation event, not an entry pattern. "
                "Valid entry patterns: SPRING, SOS, LPS"
            )
        if v not in valid_patterns:
            raise ValueError(
                f"Invalid pattern type: {v}. Valid entry patterns: {', '.join(valid_patterns)}"
            )
        return v


class CampaignRisk(BaseModel):
    """
    Campaign risk tracking for Wyckoff BMAD sequence.

    A campaign represents a Spring → SOS → LPS entry sequence within a single
    trading range, with a combined 5% risk limit (FR18). Secondary Test (ST) is
    a confirmation event between Spring and SOS, not an entry pattern.

    BMAD Allocation (AC 4) - Authentic Wyckoff 3-Entry Model
    Volume-Aligned & Risk-Optimized:
    -------------------------------------------------
    - Spring: 40% of campaign budget (HIGHEST allocation - maximum accumulation opportunity)
    - SOS: 35% of campaign budget (Phase D breakout - primary confirmation entry)
    - LPS: 25% of campaign budget (Phase D pullback - secondary entry, optional)

    Wyckoff Rationale:
    ------------------
    - Secondary Test (ST) is a CONFIRMATION EVENT, not an entry pattern
    - ST validates that Spring was successful (holds on reduced volume) - NO capital deployed
    - Entry occurs at SOS AFTER ST confirms accumulation is complete

    Volume Analysis (Victoria - Volume Specialist):
    ------------------------------------------------
    - Spring receives HIGHEST allocation (40%) due to climactic volume at shake-out
    - Climactic volume = maximum institutional accumulation (Composite Operator fills bulk of position)
    - By SOS, accumulation is essentially complete - professionals already positioned from Spring

    Risk Management (Rachel - Risk Manager):
    -----------------------------------------
    - Spring has tightest stops (2-3% below Spring low) = lowest risk
    - Spring has best R:R ratio (8-12R to target) = highest reward
    - Fundamental principle: Allocate MORE capital to LOWER-risk, HIGHER-reward opportunities
    - SOS has wider stops (5-7% below range) = higher risk, moderate allocation appropriate

    Campaign Flexibility:
    ---------------------
    - Not all campaigns include all entries (e.g., SOS-only campaigns common)
    - Allocations adjust proportionally based on which entries are taken
    - Spring is optional but offers best risk/reward when available

    Fields:
    -------
    - campaign_id: Campaign identifier (UUID)
    - total_risk: Total campaign risk percentage (≤ 5.0%)
    - available_capacity: Remaining capacity before 5% limit
    - position_count: Number of open positions in campaign
    - entry_breakdown: Position details by entry ID

    Example:
    --------
    >>> from decimal import Decimal
    >>> from uuid import uuid4
    >>> campaign_risk = CampaignRisk(
    ...     campaign_id=uuid4(),
    ...     total_risk=Decimal("5.0"),
    ...     available_capacity=Decimal("0.0"),
    ...     position_count=3,
    ...     entry_breakdown={
    ...         "entry1": CampaignEntry(
    ...             pattern_type="SPRING",
    ...             position_risk_pct=Decimal("2.0"),
    ...             allocation_percentage=Decimal("40.0"),
    ...             symbol="AAPL",
    ...             status="OPEN"
    ...         )
    ...     }
    ... )
    """

    campaign_id: UUID = Field(..., description="Campaign identifier")

    total_risk: Decimal = Field(
        ...,
        decimal_places=4,
        max_digits=6,
        description="Total campaign risk percentage (≤ 5.0%)",
    )

    available_capacity: Decimal = Field(
        ...,
        decimal_places=4,
        max_digits=6,
        description="Remaining capacity before 5% limit",
    )

    position_count: int = Field(..., ge=0, description="Number of open positions in campaign")

    entry_breakdown: dict[str, CampaignEntry] = Field(
        default_factory=dict, description="Position details by entry ID"
    )

    @field_validator("total_risk")
    @classmethod
    def validate_total_risk(cls, v: Decimal) -> Decimal:
        """
        Validate total risk does not exceed 5% limit.

        FR18: Maximum campaign risk is 5.0%

        Raises:
        -------
        ValueError
            If total_risk > 5.0
        """
        if v > Decimal("5.0"):
            raise ValueError(f"Campaign risk {v}% exceeds maximum limit of 5.0% (FR18 violation)")
        return v

    class Config:
        """Pydantic configuration for JSON encoding."""

        json_encoders = {
            Decimal: str,  # Serialize Decimal as string to preserve precision
            UUID: str,
        }


# BMAD Allocation Constants (AC 4, 11, 12)
# Campaign allocation percentages - Authentic Wyckoff 3-Entry Model
# Aligned with volume analysis and risk management principles
CAMPAIGN_SPRING_ALLOCATION = Decimal("0.40")  # 40% - Maximum accumulation opportunity (LARGEST)
CAMPAIGN_SOS_ALLOCATION = Decimal("0.35")  # 35% - Primary confirmation entry
CAMPAIGN_LPS_ALLOCATION = Decimal("0.25")  # 25% - Secondary entry (campaign completion)

# Total = 100% of 5% campaign budget

# Maximum campaign risk (FR18)
MAX_CAMPAIGN_RISK_PCT = Decimal("5.0")

# Proximity warning threshold (80% of limit)
CAMPAIGN_WARNING_THRESHOLD_PCT = Decimal("4.0")

# Maximum risk per pattern type (pattern_allocation × MAX_CAMPAIGN_RISK_PCT)
MAX_SPRING_RISK = Decimal("2.00")  # 40% of 5% = 2.00% (HIGHEST - best risk/reward)
MAX_SOS_RISK = Decimal("1.75")  # 35% of 5% = 1.75%
MAX_LPS_RISK = Decimal("1.25")  # 25% of 5% = 1.25%
# Note: Secondary Test (ST) is a confirmation event, not an entry pattern
