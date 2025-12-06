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
3. CampaignPositions: Campaign-level position aggregation with totals (Story 9.4)

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
- Story 9.4: Campaign position tracking with real-time updates

Author: Story 7.4, Story 9.4
"""

from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_serializer

if TYPE_CHECKING:
    from src.models.position import Position


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

    model_config = ConfigDict()  # Pydantic V2+ configuration

    @model_serializer
    def serialize_model(self) -> dict[str, Any]:
        """Serialize model with Decimal and UUID as strings."""
        return {
            "campaign_id": str(self.campaign_id),
            "total_risk": str(self.total_risk),
            "available_capacity": str(self.available_capacity),
            "position_count": self.position_count,
            "entry_breakdown": {
                key: {
                    "pattern_type": entry.pattern_type,
                    "position_risk_pct": str(entry.position_risk_pct),
                    "allocation_percentage": str(entry.allocation_percentage),
                    "symbol": entry.symbol,
                    "status": entry.status,
                }
                for key, entry in self.entry_breakdown.items()
            },
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


class CampaignPositions(BaseModel):
    """
    Campaign-level position aggregation with calculated totals (Story 9.4).

    Provides a complete view of all positions within a campaign with aggregated
    metrics for portfolio monitoring, risk management, and performance analysis.

    Aggregation Calculations:
    -------------------------
    - total_shares: Sum of shares across all OPEN positions
    - weighted_avg_entry: (sum(entry_price × shares) / sum(shares)) for OPEN positions only
    - total_risk: sum((entry_price - stop_loss) × shares) for OPEN positions only
    - total_pnl: sum(current_pnl) for OPEN + sum(realized_pnl) for CLOSED positions

    Fields:
    -------
    - campaign_id: Campaign identifier (UUID)
    - positions: List of all positions (OPEN and CLOSED)
    - total_shares: Total shares across all open positions
    - weighted_avg_entry: Weighted average entry price (open positions)
    - total_risk: Total risk exposure (open positions)
    - total_pnl: Combined unrealized + realized P&L
    - open_positions_count: Number of currently open positions
    - closed_positions_count: Number of closed positions

    Example:
    --------
    >>> from decimal import Decimal
    >>> from uuid import uuid4
    >>> campaign_positions = CampaignPositions(
    ...     campaign_id=uuid4(),
    ...     positions=[position1, position2, position3],
    ...     total_shares=Decimal("175"),
    ...     weighted_avg_entry=Decimal("150.86"),
    ...     total_risk=Decimal("350.00"),
    ...     total_pnl=Decimal("1300.00"),
    ...     open_positions_count=2,
    ...     closed_positions_count=1
    ... )
    """

    campaign_id: UUID = Field(..., description="Campaign identifier")

    positions: list["Position"] = Field(
        default_factory=list, description="List of all positions (OPEN and CLOSED)"
    )

    total_shares: Decimal = Field(
        default=Decimal("0"),
        decimal_places=8,
        max_digits=18,
        description="Total shares across all open positions",
    )

    weighted_avg_entry: Decimal = Field(
        default=Decimal("0"),
        decimal_places=8,
        max_digits=18,
        description="Weighted average entry price (open positions only)",
    )

    total_risk: Decimal = Field(
        default=Decimal("0"),
        decimal_places=8,
        max_digits=18,
        description="Total risk exposure (open positions only)",
    )

    total_pnl: Decimal = Field(
        default=Decimal("0"),
        decimal_places=8,
        max_digits=18,
        description="Combined unrealized + realized P&L",
    )

    open_positions_count: int = Field(
        default=0, ge=0, description="Number of currently open positions"
    )

    closed_positions_count: int = Field(default=0, ge=0, description="Number of closed positions")

    model_config = ConfigDict(
        json_encoders={Decimal: str},
        arbitrary_types_allowed=True,  # Allow Position type
    )

    @classmethod
    def from_positions(cls, campaign_id: UUID, positions: list["Position"]) -> "CampaignPositions":
        """
        Create CampaignPositions from a list of Position objects.

        Automatically calculates all aggregated metrics from the position list.

        Parameters:
        -----------
        campaign_id : UUID
            Campaign identifier
        positions : list[Position]
            List of all positions (OPEN and CLOSED)

        Returns:
        --------
        CampaignPositions
            Campaign positions with calculated aggregations

        Example:
        --------
        >>> campaign_positions = CampaignPositions.from_positions(
        ...     campaign_id=uuid4(),
        ...     positions=[position1, position2, position3]
        ... )
        """
        from src.models.position import PositionStatus

        # Separate open and closed positions
        open_positions = [p for p in positions if p.status == PositionStatus.OPEN]
        closed_positions = [p for p in positions if p.status == PositionStatus.CLOSED]

        # Calculate total_shares (open positions only)
        total_shares = sum((p.shares for p in open_positions), Decimal("0"))

        # Calculate weighted_avg_entry (open positions only)
        # Round to 8 decimal places to fit DECIMAL(18,8) constraint
        if total_shares > Decimal("0"):
            weighted_avg_entry = (
                sum((p.entry_price * p.shares for p in open_positions), Decimal("0")) / total_shares
            ).quantize(Decimal("0.00000001"))
        else:
            weighted_avg_entry = Decimal("0")

        # Calculate total_risk (open positions only)
        total_risk = sum(
            ((p.entry_price - p.stop_loss) * p.shares for p in open_positions),
            Decimal("0"),
        )

        # Calculate total_pnl (unrealized from open + realized from closed)
        unrealized_pnl = sum(
            (p.current_pnl for p in open_positions if p.current_pnl is not None),
            Decimal("0"),
        )
        realized_pnl = sum(
            (p.realized_pnl for p in closed_positions if p.realized_pnl is not None),
            Decimal("0"),
        )
        total_pnl = unrealized_pnl + realized_pnl

        return cls(
            campaign_id=campaign_id,
            positions=positions,
            total_shares=total_shares,
            weighted_avg_entry=weighted_avg_entry,
            total_risk=total_risk,
            total_pnl=total_pnl,
            open_positions_count=len(open_positions),
            closed_positions_count=len(closed_positions),
        )

    @model_serializer
    def serialize_model(self) -> dict[str, Any]:
        """
        Serialize model with Decimal as strings and UUID as strings.

        Returns:
        --------
        dict[str, Any]
            Serialized model data
        """
        return {
            "campaign_id": str(self.campaign_id),
            "positions": [p.serialize_model() for p in self.positions],
            "total_shares": str(self.total_shares),
            "weighted_avg_entry": str(self.weighted_avg_entry),
            "total_risk": str(self.total_risk),
            "total_pnl": str(self.total_pnl),
            "open_positions_count": self.open_positions_count,
            "closed_positions_count": self.closed_positions_count,
        }


class ExitRule(BaseModel):
    """
    Campaign exit strategy configuration with target levels and partial exit percentages.

    Defines the complete exit strategy for a campaign, including three target price
    levels (T1, T2, T3), partial exit percentages at each target, trailing stop
    configuration, and invalidation levels for emergency exits.

    Target Levels (AC #1):
    -----------------------
    - T1: Ice level (for pre-breakout entries) or Jump (for post-breakout entries)
    - T2: Jump target (calculated from trading range using cause factor)
    - T3: Jump × 1.5 (extended target for momentum continuation)

    Partial Exit Percentages (AC #2):
    ----------------------------------
    - Default: 50% at T1, 30% at T2, 20% at T3 (configurable)
    - Validator ensures percentages sum to 100%

    Trailing Stop Configuration (AC #3):
    -------------------------------------
    - trail_to_breakeven_on_t1: Move stop to entry_price when T1 hit
    - trail_to_t1_on_t2: Move stop to T1 level when T2 hit

    Invalidation Levels (AC #4):
    -----------------------------
    - spring_low: Exit if price < spring_low (Spring low break)
    - ice_level: Exit if price < ice_level after SOS (Ice break post-breakout)
    - creek_level: Exit if price < creek_level after Jump achieved (Creek break post-Jump)
    - utad_high: Exit if price > utad_high (UTAD high exceeded for shorts)

    Fields:
    -------
    - id: Exit rule identifier (UUID)
    - campaign_id: Parent campaign (FK to campaigns.id)
    - target_1_level, target_2_level, target_3_level: Target prices (NUMERIC(18,8))
    - t1_exit_pct, t2_exit_pct, t3_exit_pct: Partial exit percentages (default 50/30/20)
    - trail_to_breakeven_on_t1, trail_to_t1_on_t2: Trailing stop config (bool)
    - spring_low, ice_level, creek_level, utad_high: Invalidation price levels
    - jump_target: Jump price for tracking jump achievement (Creek break detection)

    Example:
    --------
    >>> from decimal import Decimal
    >>> from uuid import uuid4
    >>> exit_rule = ExitRule(
    ...     campaign_id=uuid4(),
    ...     target_1_level=Decimal("160.00"),
    ...     target_2_level=Decimal("175.00"),
    ...     target_3_level=Decimal("187.50"),
    ...     t1_exit_pct=Decimal("50.00"),
    ...     t2_exit_pct=Decimal("30.00"),
    ...     t3_exit_pct=Decimal("20.00"),
    ...     trail_to_breakeven_on_t1=True,
    ...     trail_to_t1_on_t2=True,
    ...     spring_low=Decimal("145.00"),
    ...     ice_level=Decimal("160.00"),
    ...     creek_level=Decimal("145.00"),
    ...     jump_target=Decimal("175.00")
    ... )
    """

    id: UUID = Field(
        default_factory=lambda: __import__("uuid").uuid4(), description="Exit rule identifier"
    )
    campaign_id: UUID = Field(..., description="Parent campaign (FK to campaigns.id)")

    # Target levels (NUMERIC(18,8) precision)
    target_1_level: Decimal = Field(
        ...,
        decimal_places=8,
        max_digits=18,
        gt=Decimal("0"),
        description="T1 target price (Ice for pre-breakout, Jump for post-breakout)",
    )
    target_2_level: Decimal = Field(
        ...,
        decimal_places=8,
        max_digits=18,
        gt=Decimal("0"),
        description="T2 target price (Jump)",
    )
    target_3_level: Decimal = Field(
        ...,
        decimal_places=8,
        max_digits=18,
        gt=Decimal("0"),
        description="T3 target price (Jump × 1.5 extended target)",
    )

    # Partial exit percentages (NUMERIC(5,2) precision)
    t1_exit_pct: Decimal = Field(
        default=Decimal("50.00"),
        decimal_places=2,
        max_digits=5,
        ge=Decimal("0"),
        le=Decimal("100.00"),
        description="Percentage to exit at T1 (default 50%)",
    )
    t2_exit_pct: Decimal = Field(
        default=Decimal("30.00"),
        decimal_places=2,
        max_digits=5,
        ge=Decimal("0"),
        le=Decimal("100.00"),
        description="Percentage to exit at T2 (default 30%)",
    )
    t3_exit_pct: Decimal = Field(
        default=Decimal("20.00"),
        decimal_places=2,
        max_digits=5,
        ge=Decimal("0"),
        le=Decimal("100.00"),
        description="Percentage to exit at T3 (default 20%)",
    )

    # Trailing stop configuration
    trail_to_breakeven_on_t1: bool = Field(
        default=True, description="Move stop to entry_price when T1 hit"
    )
    trail_to_t1_on_t2: bool = Field(default=True, description="Move stop to T1 level when T2 hit")

    # Invalidation levels (NUMERIC(18,8) precision)
    spring_low: Decimal | None = Field(
        None,
        decimal_places=8,
        max_digits=18,
        description="Spring low invalidation level",
    )
    ice_level: Decimal | None = Field(
        None,
        decimal_places=8,
        max_digits=18,
        description="Ice level for post-SOS invalidation",
    )
    creek_level: Decimal | None = Field(
        None,
        decimal_places=8,
        max_digits=18,
        description="Creek level for post-Jump invalidation",
    )
    utad_high: Decimal | None = Field(
        None,
        decimal_places=8,
        max_digits=18,
        description="UTAD high invalidation level (for shorts)",
    )
    jump_target: Decimal | None = Field(
        None,
        decimal_places=8,
        max_digits=18,
        description="Jump target price for tracking jump achievement",
    )

    # Timestamps
    created_at: Any = Field(
        default_factory=lambda: __import__("datetime").datetime.now(__import__("datetime").UTC),
        description="Record creation timestamp",
    )
    updated_at: Any = Field(
        default_factory=lambda: __import__("datetime").datetime.now(__import__("datetime").UTC),
        description="Record last update timestamp",
    )

    @__import__("pydantic").model_validator(mode="after")
    def validate_exit_percentages_sum(self) -> "ExitRule":
        """
        Validate that exit percentages sum to 100%.

        This validator runs after all fields are set and ensures
        the total equals 100% to guarantee the entire position is eventually closed.

        Returns:
        --------
        ExitRule
            Validated exit rule

        Raises:
        -------
        ValueError
            If sum of percentages != 100%
        """
        total = self.t1_exit_pct + self.t2_exit_pct + self.t3_exit_pct
        if total != Decimal("100.00"):
            raise ValueError(
                f"Exit percentages must sum to 100%. Current sum: {total}% "
                f"(T1: {self.t1_exit_pct}%, T2: {self.t2_exit_pct}%, T3: {self.t3_exit_pct}%)"
            )
        return self

    model_config = ConfigDict(json_encoders={Decimal: str})

    @model_serializer
    def serialize_model(self) -> dict[str, Any]:
        """Serialize model with Decimal and UUID as strings."""
        return {
            "id": str(self.id),
            "campaign_id": str(self.campaign_id),
            "target_1_level": str(self.target_1_level),
            "target_2_level": str(self.target_2_level),
            "target_3_level": str(self.target_3_level),
            "t1_exit_pct": str(self.t1_exit_pct),
            "t2_exit_pct": str(self.t2_exit_pct),
            "t3_exit_pct": str(self.t3_exit_pct),
            "trail_to_breakeven_on_t1": self.trail_to_breakeven_on_t1,
            "trail_to_t1_on_t2": self.trail_to_t1_on_t2,
            "spring_low": str(self.spring_low) if self.spring_low else None,
            "ice_level": str(self.ice_level) if self.ice_level else None,
            "creek_level": str(self.creek_level) if self.creek_level else None,
            "utad_high": str(self.utad_high) if self.utad_high else None,
            "jump_target": str(self.jump_target) if self.jump_target else None,
            "created_at": self.created_at.isoformat()
            if hasattr(self.created_at, "isoformat")
            else str(self.created_at),
            "updated_at": self.updated_at.isoformat()
            if hasattr(self.updated_at, "isoformat")
            else str(self.updated_at),
        }


# Rebuild CampaignPositions to resolve forward reference to Position
from src.models.position import Position  # noqa: E402, F401

CampaignPositions.model_rebuild()
