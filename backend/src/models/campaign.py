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
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_serializer

if TYPE_CHECKING:
    from src.models.position import Position


class AssetCategory(str, Enum):
    """
    Asset class categories for correlation tracking (Story 16.1a).

    Used to categorize trading instruments by asset class for:
    - Correlation group assignment
    - Sector mapping (equities)
    - Risk management diversification

    Values:
    -------
    - FOREX: Foreign exchange pairs (e.g., EURUSD, GBPUSD)
    - EQUITY: Individual stocks (e.g., AAPL, MSFT)
    - CRYPTO: Cryptocurrencies (e.g., BTCUSD, ETHUSD)
    - COMMODITY: Commodities (e.g., GOLD, OIL)
    - INDEX: Market indices (e.g., SPX, NAS100)
    - UNKNOWN: Unclassified assets (default)
    """

    FOREX = "FOREX"
    EQUITY = "EQUITY"
    CRYPTO = "CRYPTO"
    COMMODITY = "COMMODITY"
    INDEX = "INDEX"
    UNKNOWN = "UNKNOWN"


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


# ==================================================================================
# Campaign Performance Tracking Models (Story 9.6)
# ==================================================================================


class WinLossStatus(str, Enum):
    """
    Position win/loss status for performance tracking.

    Values:
    -------
    - WIN: Position realized P&L > 0
    - LOSS: Position realized P&L < 0
    - BREAKEVEN: Position realized P&L == 0
    """

    WIN = "WIN"
    LOSS = "LOSS"
    BREAKEVEN = "BREAKEVEN"


class PositionMetrics(BaseModel):
    """
    Position-level performance metrics for individual campaign entries.

    Provides detailed performance analytics for a single position within
    a campaign, including R-multiple achieved, win/loss status, and
    duration metrics.

    Fields:
    -------
    - position_id: Position identifier (FK to positions.id)
    - pattern_type: SPRING | SOS | LPS
    - individual_r: R-multiple achieved = (exit_price - entry_price) / (entry_price - stop_loss)
    - entry_price: Actual entry fill price
    - exit_price: Actual exit fill price
    - shares: Position size
    - realized_pnl: Final P&L = (exit_price - entry_price) × shares
    - win_loss_status: WIN | LOSS | BREAKEVEN
    - duration_bars: Number of bars position was held
    - entry_date: Position entry timestamp (UTC)
    - exit_date: Position exit timestamp (UTC)
    - entry_phase: Phase C (SPRING/LPS) or Phase D (SOS)

    Example:
    --------
    >>> from decimal import Decimal
    >>> from datetime import datetime, UTC
    >>> from uuid import uuid4
    >>> position_metrics = PositionMetrics(
    ...     position_id=uuid4(),
    ...     pattern_type="SPRING",
    ...     individual_r=Decimal("2.5"),
    ...     entry_price=Decimal("100.00"),
    ...     exit_price=Decimal("105.00"),
    ...     shares=Decimal("50"),
    ...     realized_pnl=Decimal("250.00"),
    ...     win_loss_status=WinLossStatus.WIN,
    ...     duration_bars=120,
    ...     entry_date=datetime.now(UTC),
    ...     exit_date=datetime.now(UTC),
    ...     entry_phase="Phase C"
    ... )
    """

    position_id: UUID = Field(..., description="Position identifier (FK to positions.id)")

    pattern_type: str = Field(..., max_length=10, description="SPRING | SOS | LPS")

    individual_r: Decimal = Field(
        ...,
        decimal_places=4,
        max_digits=8,
        description="R-multiple achieved",
    )

    entry_price: Decimal = Field(
        ...,
        decimal_places=8,
        max_digits=18,
        description="Actual entry fill price",
    )

    exit_price: Decimal = Field(
        ...,
        decimal_places=8,
        max_digits=18,
        description="Actual exit fill price",
    )

    shares: Decimal = Field(
        ...,
        decimal_places=8,
        max_digits=18,
        description="Position size (shares/lots)",
    )

    realized_pnl: Decimal = Field(
        ...,
        decimal_places=8,
        max_digits=18,
        description="Final P&L",
    )

    win_loss_status: WinLossStatus = Field(..., description="WIN | LOSS | BREAKEVEN")

    duration_bars: int = Field(..., ge=0, description="Number of bars position was held")

    entry_date: Any = Field(..., description="Position entry timestamp (UTC)")

    exit_date: Any = Field(..., description="Position exit timestamp (UTC)")

    entry_phase: str = Field(
        ..., max_length=20, description="Phase C (SPRING/LPS) or Phase D (SOS)"
    )

    model_config = ConfigDict(json_encoders={Decimal: str})

    @model_serializer
    def serialize_model(self) -> dict[str, Any]:
        """Serialize model with Decimal and UUID as strings."""
        return {
            "position_id": str(self.position_id),
            "pattern_type": self.pattern_type,
            "individual_r": str(self.individual_r),
            "entry_price": str(self.entry_price),
            "exit_price": str(self.exit_price),
            "shares": str(self.shares),
            "realized_pnl": str(self.realized_pnl),
            "win_loss_status": self.win_loss_status.value,
            "duration_bars": self.duration_bars,
            "entry_date": self.entry_date.isoformat()
            if hasattr(self.entry_date, "isoformat")
            else str(self.entry_date),
            "exit_date": self.exit_date.isoformat()
            if hasattr(self.exit_date, "isoformat")
            else str(self.exit_date),
            "entry_phase": self.entry_phase,
        }


class CampaignMetrics(BaseModel):
    """
    Campaign-level performance metrics calculated from completed campaigns.

    Provides comprehensive performance analytics including campaign-level
    aggregates (total return %, total R achieved, win rate, max drawdown),
    position-level details, phase-specific metrics, and comparison between
    expected vs actual performance.

    Fields:
    -------
    Campaign-level metrics:
    - campaign_id: Campaign identifier (FK to campaigns.id)
    - symbol: Trading symbol
    - total_return_pct: Total campaign return percentage
    - total_r_achieved: Sum of R-multiples across all positions
    - duration_days: Campaign duration in days
    - max_drawdown: Maximum drawdown percentage
    - total_positions: Total number of positions (open + closed)
    - winning_positions: Number of winning positions
    - losing_positions: Number of losing positions
    - win_rate: Percentage of winning positions
    - average_entry_price: Weighted average entry price
    - average_exit_price: Weighted average exit price

    Comparison metrics:
    - expected_jump_target: Projected Jump target from trading range
    - actual_high_reached: Highest price reached during campaign
    - target_achievement_pct: % of Jump target achieved
    - expected_r: Expected R-multiple based on Jump target
    - actual_r_achieved: Actual R-multiple achieved

    Phase-specific metrics (AC #11):
    - phase_c_avg_r: Average R-multiple for Phase C entries (SPRING + LPS)
    - phase_d_avg_r: Average R-multiple for Phase D entries (SOS)
    - phase_c_positions: Count of Phase C entries
    - phase_d_positions: Count of Phase D entries
    - phase_c_win_rate: Win rate for Phase C entries
    - phase_d_win_rate: Win rate for Phase D entries

    Position details:
    - position_details: List of PositionMetrics for all positions

    Metadata:
    - calculation_timestamp: When metrics were calculated
    - completed_at: When campaign was completed

    Example:
    --------
    >>> from decimal import Decimal
    >>> from datetime import datetime, UTC
    >>> from uuid import uuid4
    >>> campaign_metrics = CampaignMetrics(
    ...     campaign_id=uuid4(),
    ...     symbol="AAPL",
    ...     total_return_pct=Decimal("15.50"),
    ...     total_r_achieved=Decimal("8.2"),
    ...     duration_days=45,
    ...     max_drawdown=Decimal("5.25"),
    ...     total_positions=3,
    ...     winning_positions=2,
    ...     losing_positions=1,
    ...     win_rate=Decimal("66.67"),
    ...     average_entry_price=Decimal("150.00"),
    ...     average_exit_price=Decimal("173.25"),
    ...     expected_jump_target=Decimal("175.00"),
    ...     actual_high_reached=Decimal("178.50"),
    ...     target_achievement_pct=Decimal("114.00"),
    ...     expected_r=Decimal("10.0"),
    ...     actual_r_achieved=Decimal("8.2"),
    ...     phase_c_avg_r=Decimal("3.5"),
    ...     phase_d_avg_r=Decimal("2.1"),
    ...     phase_c_positions=2,
    ...     phase_d_positions=1,
    ...     phase_c_win_rate=Decimal("100.00"),
    ...     phase_d_win_rate=Decimal("100.00"),
    ...     position_details=[],
    ...     calculation_timestamp=datetime.now(UTC),
    ...     completed_at=datetime.now(UTC)
    ... )
    """

    # Campaign identification
    campaign_id: UUID = Field(..., description="Campaign identifier (FK to campaigns.id)")
    symbol: str = Field(..., max_length=20, description="Trading symbol")

    # Campaign-level metrics
    total_return_pct: Decimal = Field(
        ...,
        decimal_places=8,
        max_digits=18,
        description="Total campaign return percentage",
    )

    total_r_achieved: Decimal = Field(
        ...,
        decimal_places=4,
        max_digits=8,
        description="Sum of R-multiples across all positions",
    )

    duration_days: int = Field(..., ge=0, description="Campaign duration in days")

    max_drawdown: Decimal = Field(
        ...,
        decimal_places=8,
        max_digits=18,
        description="Maximum drawdown percentage",
    )

    total_positions: int = Field(..., ge=0, description="Total number of positions")

    winning_positions: int = Field(..., ge=0, description="Number of winning positions")

    losing_positions: int = Field(..., ge=0, description="Number of losing positions")

    win_rate: Decimal = Field(
        ...,
        decimal_places=2,
        max_digits=5,
        ge=Decimal("0"),
        le=Decimal("100.00"),
        description="Percentage of winning positions",
    )

    average_entry_price: Decimal = Field(
        ...,
        decimal_places=8,
        max_digits=18,
        description="Weighted average entry price",
    )

    average_exit_price: Decimal = Field(
        ...,
        decimal_places=8,
        max_digits=18,
        description="Weighted average exit price",
    )

    # Comparison metrics
    expected_jump_target: Decimal | None = Field(
        None,
        decimal_places=8,
        max_digits=18,
        description="Projected Jump target from trading range",
    )

    actual_high_reached: Decimal | None = Field(
        None,
        decimal_places=8,
        max_digits=18,
        description="Highest price reached during campaign",
    )

    target_achievement_pct: Decimal | None = Field(
        None,
        decimal_places=2,
        max_digits=7,
        description="Percentage of Jump target achieved",
    )

    expected_r: Decimal | None = Field(
        None,
        decimal_places=4,
        max_digits=8,
        description="Expected R-multiple based on Jump target",
    )

    actual_r_achieved: Decimal | None = Field(
        None,
        decimal_places=4,
        max_digits=8,
        description="Actual R-multiple achieved (same as total_r_achieved)",
    )

    # Phase-specific metrics (AC #11)
    phase_c_avg_r: Decimal | None = Field(
        None,
        decimal_places=4,
        max_digits=8,
        description="Average R-multiple for Phase C entries (SPRING + LPS)",
    )

    phase_d_avg_r: Decimal | None = Field(
        None,
        decimal_places=4,
        max_digits=8,
        description="Average R-multiple for Phase D entries (SOS)",
    )

    phase_c_positions: int = Field(
        default=0, ge=0, description="Count of Phase C entries (SPRING + LPS)"
    )

    phase_d_positions: int = Field(default=0, ge=0, description="Count of Phase D entries (SOS)")

    phase_c_win_rate: Decimal | None = Field(
        None,
        decimal_places=2,
        max_digits=5,
        description="Win rate for Phase C entries",
    )

    phase_d_win_rate: Decimal | None = Field(
        None,
        decimal_places=2,
        max_digits=5,
        description="Win rate for Phase D entries",
    )

    # Position details
    position_details: list[PositionMetrics] = Field(
        default_factory=list, description="List of PositionMetrics for all positions"
    )

    # Metadata
    calculation_timestamp: Any = Field(
        default_factory=lambda: __import__("datetime").datetime.now(__import__("datetime").UTC),
        description="When metrics were calculated",
    )

    completed_at: Any = Field(..., description="When campaign was completed")

    model_config = ConfigDict(json_encoders={Decimal: str})

    @model_serializer
    def serialize_model(self) -> dict[str, Any]:
        """Serialize model with Decimal and UUID as strings."""
        return {
            "campaign_id": str(self.campaign_id),
            "symbol": self.symbol,
            "total_return_pct": str(self.total_return_pct),
            "total_r_achieved": str(self.total_r_achieved),
            "duration_days": self.duration_days,
            "max_drawdown": str(self.max_drawdown),
            "total_positions": self.total_positions,
            "winning_positions": self.winning_positions,
            "losing_positions": self.losing_positions,
            "win_rate": str(self.win_rate),
            "average_entry_price": str(self.average_entry_price),
            "average_exit_price": str(self.average_exit_price),
            "expected_jump_target": str(self.expected_jump_target)
            if self.expected_jump_target
            else None,
            "actual_high_reached": str(self.actual_high_reached)
            if self.actual_high_reached
            else None,
            "target_achievement_pct": str(self.target_achievement_pct)
            if self.target_achievement_pct
            else None,
            "expected_r": str(self.expected_r) if self.expected_r else None,
            "actual_r_achieved": str(self.actual_r_achieved) if self.actual_r_achieved else None,
            "phase_c_avg_r": str(self.phase_c_avg_r) if self.phase_c_avg_r else None,
            "phase_d_avg_r": str(self.phase_d_avg_r) if self.phase_d_avg_r else None,
            "phase_c_positions": self.phase_c_positions,
            "phase_d_positions": self.phase_d_positions,
            "phase_c_win_rate": str(self.phase_c_win_rate) if self.phase_c_win_rate else None,
            "phase_d_win_rate": str(self.phase_d_win_rate) if self.phase_d_win_rate else None,
            "position_details": [p.serialize_model() for p in self.position_details],
            "calculation_timestamp": self.calculation_timestamp.isoformat()
            if hasattr(self.calculation_timestamp, "isoformat")
            else str(self.calculation_timestamp),
            "completed_at": self.completed_at.isoformat()
            if hasattr(self.completed_at, "isoformat")
            else str(self.completed_at),
        }


class PnLPoint(BaseModel):
    """
    Single point in campaign P&L curve time-series.

    Fields:
    -------
    - timestamp: Point in time (UTC)
    - cumulative_pnl: Cumulative P&L at this point
    - cumulative_return_pct: Cumulative return percentage
    - drawdown_pct: Drawdown percentage at this point
    """

    timestamp: Any = Field(..., description="Point in time (UTC)")

    cumulative_pnl: Decimal = Field(
        ...,
        decimal_places=8,
        max_digits=18,
        description="Cumulative P&L at this point",
    )

    cumulative_return_pct: Decimal = Field(
        ...,
        decimal_places=8,
        max_digits=18,
        description="Cumulative return percentage",
    )

    drawdown_pct: Decimal = Field(
        ...,
        decimal_places=8,
        max_digits=18,
        description="Drawdown percentage at this point",
    )

    model_config = ConfigDict(json_encoders={Decimal: str})

    @model_serializer
    def serialize_model(self) -> dict[str, Any]:
        """Serialize model with Decimal as strings."""
        return {
            "timestamp": self.timestamp.isoformat()
            if hasattr(self.timestamp, "isoformat")
            else str(self.timestamp),
            "cumulative_pnl": str(self.cumulative_pnl),
            "cumulative_return_pct": str(self.cumulative_return_pct),
            "drawdown_pct": str(self.drawdown_pct),
        }


class PnLCurve(BaseModel):
    """
    Campaign P&L curve data for visualization.

    Provides time-series data of campaign cumulative P&L and drawdown
    for rendering equity curves and performance charts.

    Fields:
    -------
    - campaign_id: Campaign identifier
    - data_points: List of PnLPoint time-series data
    - max_drawdown_point: PnLPoint where maximum drawdown occurred

    Example:
    --------
    >>> from decimal import Decimal
    >>> from datetime import datetime, UTC
    >>> from uuid import uuid4
    >>> pnl_curve = PnLCurve(
    ...     campaign_id=uuid4(),
    ...     data_points=[
    ...         PnLPoint(
    ...             timestamp=datetime.now(UTC),
    ...             cumulative_pnl=Decimal("500.00"),
    ...             cumulative_return_pct=Decimal("5.00"),
    ...             drawdown_pct=Decimal("0.00")
    ...         )
    ...     ],
    ...     max_drawdown_point=PnLPoint(...)
    ... )
    """

    campaign_id: UUID = Field(..., description="Campaign identifier")

    data_points: list[PnLPoint] = Field(
        default_factory=list, description="List of PnLPoint time-series data"
    )

    max_drawdown_point: PnLPoint | None = Field(
        None, description="PnLPoint where maximum drawdown occurred"
    )

    model_config = ConfigDict(json_encoders={Decimal: str})

    @model_serializer
    def serialize_model(self) -> dict[str, Any]:
        """Serialize model with Decimal and UUID as strings."""
        return {
            "campaign_id": str(self.campaign_id),
            "data_points": [p.serialize_model() for p in self.data_points],
            "max_drawdown_point": self.max_drawdown_point.serialize_model()
            if self.max_drawdown_point
            else None,
        }


class AggregatedMetrics(BaseModel):
    """
    Aggregated performance statistics across all completed campaigns.

    Provides system-wide performance analytics aggregated from all
    completed campaigns, with optional filtering by symbol, timeframe,
    and date range.

    Fields:
    -------
    - total_campaigns_completed: Total number of completed campaigns
    - overall_win_rate: Percentage of winning campaigns
    - average_campaign_return_pct: Average return across all campaigns
    - average_r_achieved_per_campaign: Average R-multiple per campaign
    - best_campaign: Campaign with highest return (campaign_id, return_pct)
    - worst_campaign: Campaign with lowest return (campaign_id, return_pct)
    - median_duration_days: Median campaign duration
    - average_max_drawdown: Average maximum drawdown across campaigns
    - calculation_timestamp: When aggregation was calculated
    - filter_criteria: Filters applied (symbol, timeframe, date_range)

    Example:
    --------
    >>> from decimal import Decimal
    >>> from datetime import datetime, UTC
    >>> aggregated = AggregatedMetrics(
    ...     total_campaigns_completed=25,
    ...     overall_win_rate=Decimal("72.00"),
    ...     average_campaign_return_pct=Decimal("12.50"),
    ...     average_r_achieved_per_campaign=Decimal("6.8"),
    ...     best_campaign={"campaign_id": "uuid", "return_pct": "35.50"},
    ...     worst_campaign={"campaign_id": "uuid", "return_pct": "-5.25"},
    ...     median_duration_days=38,
    ...     average_max_drawdown=Decimal("6.75"),
    ...     calculation_timestamp=datetime.now(UTC),
    ...     filter_criteria={}
    ... )
    """

    total_campaigns_completed: int = Field(
        ..., ge=0, description="Total number of completed campaigns"
    )

    overall_win_rate: Decimal = Field(
        ...,
        decimal_places=2,
        max_digits=5,
        ge=Decimal("0"),
        le=Decimal("100.00"),
        description="Percentage of winning campaigns",
    )

    average_campaign_return_pct: Decimal = Field(
        ...,
        decimal_places=8,
        max_digits=18,
        description="Average return across all campaigns",
    )

    average_r_achieved_per_campaign: Decimal = Field(
        ...,
        decimal_places=4,
        max_digits=8,
        description="Average R-multiple per campaign",
    )

    best_campaign: dict[str, str] | None = Field(
        None, description="Campaign with highest return (campaign_id, return_pct)"
    )

    worst_campaign: dict[str, str] | None = Field(
        None, description="Campaign with lowest return (campaign_id, return_pct)"
    )

    median_duration_days: int | None = Field(None, ge=0, description="Median campaign duration")

    average_max_drawdown: Decimal = Field(
        ...,
        decimal_places=8,
        max_digits=18,
        description="Average maximum drawdown across campaigns",
    )

    calculation_timestamp: Any = Field(
        default_factory=lambda: __import__("datetime").datetime.now(__import__("datetime").UTC),
        description="When aggregation was calculated",
    )

    filter_criteria: dict[str, Any] = Field(
        default_factory=dict, description="Filters applied (symbol, timeframe, date_range)"
    )

    model_config = ConfigDict(json_encoders={Decimal: str})

    @model_serializer
    def serialize_model(self) -> dict[str, Any]:
        """Serialize model with Decimal as strings."""
        return {
            "total_campaigns_completed": self.total_campaigns_completed,
            "overall_win_rate": str(self.overall_win_rate),
            "average_campaign_return_pct": str(self.average_campaign_return_pct),
            "average_r_achieved_per_campaign": str(self.average_r_achieved_per_campaign),
            "best_campaign": self.best_campaign,
            "worst_campaign": self.worst_campaign,
            "median_duration_days": self.median_duration_days,
            "average_max_drawdown": str(self.average_max_drawdown),
            "calculation_timestamp": self.calculation_timestamp.isoformat()
            if hasattr(self.calculation_timestamp, "isoformat")
            else str(self.calculation_timestamp),
            "filter_criteria": self.filter_criteria,
        }


class MetricsFilter(BaseModel):
    """
    Filter criteria for historical campaign metrics queries.

    Fields:
    -------
    - symbol: Filter by trading symbol
    - timeframe: Filter by timeframe
    - start_date: Filter campaigns completed after this date
    - end_date: Filter campaigns completed before this date
    - min_return: Filter campaigns with return >= min_return
    - min_r_achieved: Filter campaigns with total R >= min_r_achieved
    - limit: Maximum number of results (pagination)
    - offset: Skip first N results (pagination)
    """

    symbol: str | None = Field(None, max_length=20, description="Filter by trading symbol")

    timeframe: str | None = Field(None, max_length=10, description="Filter by timeframe")

    start_date: Any = Field(None, description="Filter campaigns completed after this date")

    end_date: Any = Field(None, description="Filter campaigns completed before this date")

    min_return: Decimal | None = Field(
        None,
        decimal_places=8,
        max_digits=18,
        description="Filter campaigns with return >= min_return",
    )

    min_r_achieved: Decimal | None = Field(
        None,
        decimal_places=4,
        max_digits=8,
        description="Filter campaigns with total R >= min_r_achieved",
    )

    limit: int = Field(default=100, ge=1, le=1000, description="Maximum number of results")

    offset: int = Field(default=0, ge=0, description="Skip first N results")

    model_config = ConfigDict(json_encoders={Decimal: str})


class SequencePerformance(BaseModel):
    """
    Pattern sequence performance metrics (Story 16.5a).

    Analyzes performance of specific pattern sequences (e.g., Spring→SOS,
    Spring→AR→SOS, Spring→SOS→LPS) to identify which sequences have the
    highest win rates and profitability.

    Fields:
    -------
    - sequence: Pattern sequence string (e.g., "Spring→SOS")
    - campaign_count: Number of campaigns with this sequence
    - win_rate: Percentage of winning campaigns (R > 0)
    - avg_r_multiple: Average R-multiple across all campaigns
    - median_r_multiple: Median R-multiple
    - total_r_multiple: Cumulative R-multiple (total profit in R)
    - exit_reasons: Distribution of exit reasons
    - best_campaign_id: Campaign ID with highest R-multiple
    - worst_campaign_id: Campaign ID with lowest R-multiple

    Example:
    --------
    >>> from decimal import Decimal
    >>> from uuid import uuid4
    >>> sequence_perf = SequencePerformance(
    ...     sequence="Spring→SOS",
    ...     campaign_count=25,
    ...     win_rate=Decimal("72.00"),
    ...     avg_r_multiple=Decimal("3.5"),
    ...     median_r_multiple=Decimal("2.8"),
    ...     total_r_multiple=Decimal("87.5"),
    ...     exit_reasons={"TARGET_HIT": 18, "STOPPED": 7},
    ...     best_campaign_id=uuid4(),
    ...     worst_campaign_id=uuid4()
    ... )
    """

    sequence: str = Field(..., description="Pattern sequence string (e.g., 'Spring→SOS')")

    campaign_count: int = Field(..., ge=0, description="Number of campaigns with this sequence")

    win_rate: Decimal = Field(
        ...,
        decimal_places=2,
        max_digits=5,
        ge=Decimal("0"),
        le=Decimal("100.00"),
        description="Percentage of winning campaigns (R > 0)",
    )

    avg_r_multiple: Decimal = Field(
        ...,
        decimal_places=4,
        max_digits=8,
        description="Average R-multiple across all campaigns",
    )

    median_r_multiple: Decimal = Field(
        ...,
        decimal_places=4,
        max_digits=8,
        description="Median R-multiple",
    )

    total_r_multiple: Decimal = Field(
        ...,
        decimal_places=4,
        max_digits=12,
        description="Cumulative R-multiple (total profit in R)",
    )

    exit_reasons: dict[str, int] = Field(
        default_factory=dict, description="Distribution of exit reasons"
    )

    best_campaign_id: UUID | None = Field(None, description="Campaign ID with highest R-multiple")

    worst_campaign_id: UUID | None = Field(None, description="Campaign ID with lowest R-multiple")

    model_config = ConfigDict(json_encoders={Decimal: str})

    @model_serializer
    def serialize_model(self) -> dict[str, Any]:
        """Serialize model with Decimal and UUID as strings."""
        return {
            "sequence": self.sequence,
            "campaign_count": self.campaign_count,
            "win_rate": str(self.win_rate),
            "avg_r_multiple": str(self.avg_r_multiple),
            "median_r_multiple": str(self.median_r_multiple),
            "total_r_multiple": str(self.total_r_multiple),
            "exit_reasons": self.exit_reasons,
            "best_campaign_id": str(self.best_campaign_id) if self.best_campaign_id else None,
            "worst_campaign_id": str(self.worst_campaign_id) if self.worst_campaign_id else None,
        }


class SequencePerformanceResponse(BaseModel):
    """
    Response model for pattern sequence performance analysis API (Story 16.5a).

    Returns a list of sequence performance metrics with filtering metadata.

    Fields:
    -------
    - sequences: List of sequence performance metrics
    - total_sequences: Total number of unique sequences analyzed
    - filters_applied: Filters that were applied (symbol, timeframe)
    - total_campaigns: Total number of campaigns analyzed

    Example:
    --------
    >>> from decimal import Decimal
    >>> from uuid import uuid4
    >>> response = SequencePerformanceResponse(
    ...     sequences=[
    ...         SequencePerformance(
    ...             sequence="Spring→SOS",
    ...             campaign_count=25,
    ...             win_rate=Decimal("72.00"),
    ...             avg_r_multiple=Decimal("3.5"),
    ...             median_r_multiple=Decimal("2.8"),
    ...             total_r_multiple=Decimal("87.5"),
    ...             exit_reasons={"TARGET_HIT": 18, "STOPPED": 7},
    ...             best_campaign_id=uuid4(),
    ...             worst_campaign_id=uuid4()
    ...         )
    ...     ],
    ...     total_sequences=5,
    ...     filters_applied={"symbol": "AAPL", "timeframe": None},
    ...     total_campaigns=100
    ... )
    """

    sequences: list[SequencePerformance] = Field(
        ..., description="List of sequence performance metrics sorted by total R-multiple"
    )

    total_sequences: int = Field(..., ge=0, description="Total number of unique sequences analyzed")

    filters_applied: dict[str, str | None] = Field(
        default_factory=dict, description="Filters applied (symbol, timeframe)"
    )

    total_campaigns: int = Field(..., ge=0, description="Total number of campaigns analyzed")

    model_config = ConfigDict(json_encoders={Decimal: str})


class QualityTierPerformance(BaseModel):
    """
    Performance metrics for a specific quality tier (Story 16.5b).

    Analyzes campaign performance grouped by quality tier (based on strength scores
    of initial entry patterns) to identify optimal quality thresholds for filtering.

    Quality Tiers:
    --------------
    - EXCEPTIONAL: strength_score >= 90 (highest quality)
    - STRONG: 80 <= strength_score < 90
    - ACCEPTABLE: 70 <= strength_score < 80
    - WEAK: strength_score < 70

    Fields:
    -------
    - tier: Quality tier name (EXCEPTIONAL, STRONG, ACCEPTABLE, WEAK)
    - campaign_count: Number of campaigns in this tier
    - win_rate: Percentage of winning campaigns (R > 0)
    - avg_r_multiple: Average R-multiple across campaigns
    - median_r_multiple: Median R-multiple
    - total_r_multiple: Cumulative R-multiple

    Example:
    --------
    >>> from decimal import Decimal
    >>> tier_perf = QualityTierPerformance(
    ...     tier="EXCEPTIONAL",
    ...     campaign_count=15,
    ...     win_rate=Decimal("86.67"),
    ...     avg_r_multiple=Decimal("4.2"),
    ...     median_r_multiple=Decimal("3.5"),
    ...     total_r_multiple=Decimal("63.0")
    ... )
    """

    tier: str = Field(..., description="Quality tier (EXCEPTIONAL, STRONG, ACCEPTABLE, WEAK)")

    campaign_count: int = Field(..., ge=0, description="Number of campaigns in this tier")

    win_rate: Decimal = Field(
        ...,
        decimal_places=2,
        max_digits=5,
        ge=Decimal("0"),
        le=Decimal("100.00"),
        description="Percentage of winning campaigns (R > 0)",
    )

    avg_r_multiple: Decimal = Field(
        ...,
        decimal_places=4,
        max_digits=8,
        description="Average R-multiple across campaigns",
    )

    median_r_multiple: Decimal = Field(
        ...,
        decimal_places=4,
        max_digits=8,
        description="Median R-multiple",
    )

    total_r_multiple: Decimal = Field(
        ...,
        decimal_places=4,
        max_digits=12,
        description="Cumulative R-multiple",
    )

    model_config = ConfigDict(json_encoders={Decimal: str})

    @model_serializer
    def serialize_model(self) -> dict[str, Any]:
        """Serialize model with Decimal as strings."""
        return {
            "tier": self.tier,
            "campaign_count": self.campaign_count,
            "win_rate": str(self.win_rate),
            "avg_r_multiple": str(self.avg_r_multiple),
            "median_r_multiple": str(self.median_r_multiple),
            "total_r_multiple": str(self.total_r_multiple),
        }


class QualityCorrelationReport(BaseModel):
    """
    Quality correlation analysis report (Story 16.5b AC #1-2).

    Analyzes correlation between strength scores and R-multiples to identify
    optimal quality thresholds for signal filtering.

    Metrics:
    --------
    - correlation_coefficient: Pearson correlation between strength_score and R-multiple
    - performance_by_tier: Performance metrics grouped by quality tier
    - optimal_threshold: Recommended minimum strength_score threshold
    - sample_size: Total number of campaigns analyzed

    Example:
    --------
    >>> from decimal import Decimal
    >>> report = QualityCorrelationReport(
    ...     correlation_coefficient=Decimal("0.62"),
    ...     performance_by_tier=[...],
    ...     optimal_threshold=80,
    ...     sample_size=100
    ... )
    """

    correlation_coefficient: Decimal = Field(
        ...,
        decimal_places=4,
        max_digits=5,
        ge=Decimal("-1"),
        le=Decimal("1"),
        description="Pearson correlation coefficient (-1 to +1)",
    )

    performance_by_tier: list[QualityTierPerformance] = Field(
        ..., description="Performance metrics by quality tier"
    )

    optimal_threshold: int = Field(
        ...,
        ge=0,
        le=100,
        description="Recommended minimum strength_score threshold",
    )

    sample_size: int = Field(..., ge=0, description="Total number of campaigns analyzed")

    warnings: list[str] = Field(
        default_factory=list,
        description="Statistical validity warnings (e.g., low sample size)",
    )

    model_config = ConfigDict(json_encoders={Decimal: str})

    @model_serializer
    def serialize_model(self) -> dict[str, Any]:
        """Serialize model with Decimal as strings."""
        return {
            "correlation_coefficient": str(self.correlation_coefficient),
            "performance_by_tier": [tier.serialize_model() for tier in self.performance_by_tier],
            "optimal_threshold": self.optimal_threshold,
            "sample_size": self.sample_size,
            "warnings": self.warnings,
        }


class CampaignDurationMetrics(BaseModel):
    """
    Campaign duration metrics by pattern sequence (Story 16.5b AC #2).

    Analyzes campaign duration patterns to understand typical timeframes
    for different pattern sequences.

    Fields:
    -------
    - sequence: Pattern sequence string (e.g., "Spring→SOS")
    - avg_duration_days: Average campaign duration in days
    - median_duration_days: Median campaign duration
    - min_duration_days: Shortest campaign duration
    - max_duration_days: Longest campaign duration
    - campaign_count: Number of campaigns with this sequence

    Example:
    --------
    >>> from decimal import Decimal
    >>> duration = CampaignDurationMetrics(
    ...     sequence="Spring→SOS",
    ...     avg_duration_days=Decimal("15.5"),
    ...     median_duration_days=Decimal("14.0"),
    ...     min_duration_days=5,
    ...     max_duration_days=32,
    ...     campaign_count=25
    ... )
    """

    sequence: str = Field(..., description="Pattern sequence string (e.g., 'Spring→SOS')")

    avg_duration_days: Decimal = Field(
        ...,
        decimal_places=2,
        max_digits=8,
        ge=Decimal("0"),
        description="Average campaign duration in days",
    )

    median_duration_days: Decimal = Field(
        ...,
        decimal_places=2,
        max_digits=8,
        ge=Decimal("0"),
        description="Median campaign duration in days",
    )

    min_duration_days: int = Field(..., ge=0, description="Shortest campaign duration")

    max_duration_days: int = Field(..., ge=0, description="Longest campaign duration")

    campaign_count: int = Field(..., ge=0, description="Number of campaigns with this sequence")

    model_config = ConfigDict(json_encoders={Decimal: str})

    @model_serializer
    def serialize_model(self) -> dict[str, Any]:
        """Serialize model with Decimal as strings."""
        return {
            "sequence": self.sequence,
            "avg_duration_days": str(self.avg_duration_days),
            "median_duration_days": str(self.median_duration_days),
            "min_duration_days": self.min_duration_days,
            "max_duration_days": self.max_duration_days,
            "campaign_count": self.campaign_count,
        }


class CampaignDurationReport(BaseModel):
    """
    Campaign duration analysis report (Story 16.5b AC #2).

    Provides comprehensive duration analysis across all campaign sequences
    to identify typical timeframes and outliers.

    Fields:
    -------
    - duration_by_sequence: Duration metrics grouped by pattern sequence
    - overall_avg_duration: Average duration across all campaigns
    - overall_median_duration: Median duration across all campaigns
    - total_campaigns: Total number of campaigns analyzed

    Example:
    --------
    >>> from decimal import Decimal
    >>> report = CampaignDurationReport(
    ...     duration_by_sequence=[...],
    ...     overall_avg_duration=Decimal("16.3"),
    ...     overall_median_duration=Decimal("15.0"),
    ...     total_campaigns=100
    ... )
    """

    duration_by_sequence: list[CampaignDurationMetrics] = Field(
        ..., description="Duration metrics by pattern sequence"
    )

    overall_avg_duration: Decimal = Field(
        ...,
        decimal_places=2,
        max_digits=8,
        ge=Decimal("0"),
        description="Average duration across all campaigns",
    )

    overall_median_duration: Decimal = Field(
        ...,
        decimal_places=2,
        max_digits=8,
        ge=Decimal("0"),
        description="Median duration across all campaigns",
    )

    total_campaigns: int = Field(..., ge=0, description="Total number of campaigns analyzed")

    model_config = ConfigDict(json_encoders={Decimal: str})

    @model_serializer
    def serialize_model(self) -> dict[str, Any]:
        """Serialize model with Decimal as strings."""
        return {
            "duration_by_sequence": [seq.serialize_model() for seq in self.duration_by_sequence],
            "overall_avg_duration": str(self.overall_avg_duration),
            "overall_median_duration": str(self.overall_median_duration),
            "total_campaigns": self.total_campaigns,
        }
