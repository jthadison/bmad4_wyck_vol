"""
Portfolio Heat Tracking Data Models - Wyckoff-Adaptive Risk Management

Purpose:
--------
Provides Pydantic models for tracking portfolio-level heat (aggregate risk)
with phase-adaptive limits, volume-based multipliers, and campaign correlation
adjustments per Wyckoff methodology (Story 7.3).

Data Models:
------------
1. Position: Open position with risk and Wyckoff context
2. CampaignCluster: Correlated positions (same sector + phase)
3. PortfolioWarning: Context-aware portfolio warnings
4. PortfolioHeat: Comprehensive portfolio heat report

Wyckoff Integration:
--------------------
- Phase-adaptive limits (AC 11): 8% (A/B), 12% (C/D), 15% (E)
- Volume-based multipliers (AC 13): 0.70x (≥30pts), 0.85x (20-30pts)
- Campaign correlation (AC 16): Penalties for clustered positions
- Context-aware warnings (AC 7 revised): 4 warning types

Author: Story 7.3
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


@dataclass
class Position:
    """
    Open position with risk percentage and Wyckoff context.

    This model extends PositionSizing (Story 7.2) with additional
    fields required for portfolio-level heat tracking and Wyckoff
    phase/volume analysis.

    Required for Enhancements:
    ---------------------------
    - wyckoff_phase: From PhaseDetector (Epic 4) - "A"|"B"|"C"|"D"|"E"|"unknown"
    - volume_confirmation_score: From Story 6.5 - 0-40 points
    - sector: Sector classification for correlation analysis
    - position_risk_pct: From Story 7.2 - actual_risk / account_equity

    Example:
    --------
    >>> from decimal import Decimal
    >>> pos = Position(
    ...     symbol="AAPL",
    ...     position_risk_pct=Decimal("2.0"),
    ...     wyckoff_phase="D",
    ...     volume_confirmation_score=Decimal("35.0"),
    ...     sector="Technology",
    ...     status="OPEN"
    ... )
    """

    symbol: str
    position_risk_pct: Decimal  # Percentage of account at risk (e.g., 2.0 for 2%)
    status: str  # "OPEN", "CLOSED", etc.

    # Wyckoff context (required for enhancements)
    wyckoff_phase: str = "unknown"  # "A"|"B"|"C"|"D"|"E"|"unknown"
    volume_confirmation_score: Decimal = Decimal("15.0")  # 0-40 points, default weak
    sector: str = "unknown"  # Sector/industry classification


@dataclass
class CampaignCluster:
    """
    Positions clustered in same sector/phase (correlated risk).

    Enhancement 3 (AC 16-17): Applies correlation penalties to positions
    that share the same sector and Wyckoff phase, as they represent
    correlated risks in the same accumulation campaign.

    Correlation Multipliers:
    -------------------------
    - 2 positions: 0.90x (10% penalty)
    - 3 positions: 0.85x (15% penalty)
    - 4+ positions: 0.80x (20% penalty)

    Example:
    --------
    >>> cluster = CampaignCluster(
    ...     sector="Technology",
    ...     wyckoff_phase="D",
    ...     position_count=3,
    ...     raw_heat=Decimal("12.0"),
    ...     adjusted_heat=Decimal("10.2"),  # 12.0 * 0.85
    ...     correlation_multiplier=Decimal("0.85"),
    ...     positions=["AAPL", "MSFT", "GOOGL"]
    ... )
    """

    sector: str
    wyckoff_phase: str
    position_count: int
    raw_heat: Decimal  # Unadjusted sum of position_risk_pct
    adjusted_heat: Decimal  # raw_heat * correlation_multiplier
    correlation_multiplier: Decimal  # 0.80-0.90 based on cluster size
    positions: list[str]  # Symbols in cluster


@dataclass
class PortfolioWarning:
    """
    Context-aware portfolio warning based on Wyckoff phase analysis.

    Enhancement 4 (AC 7 revised): Replaces fixed 80% threshold with
    4 context-aware warning types that account for Wyckoff phase,
    volume confirmation, and campaign stage.

    Warning Types:
    --------------
    1. underutilized_opportunity (INFO): Phase D/E majority, <8% heat
    2. premature_commitment (WARNING): Phase A/B majority, >6% heat
    3. capacity_limit (WARNING): ≥90% of phase-adjusted limit
    4. volume_quality_mismatch (WARNING): >8% heat, volume score <20

    Example:
    --------
    >>> warning = PortfolioWarning(
    ...     warning_type="premature_commitment",
    ...     message="Premature commitment: 7.5% heat in early-stage accumulation",
    ...     severity="WARNING",
    ...     context={"heat": "7.5", "majority_phase": "A"}
    ... )
    """

    warning_type: Literal[
        "underutilized_opportunity",
        "premature_commitment",
        "capacity_limit",
        "volume_quality_mismatch",
    ]
    message: str
    severity: Literal["INFO", "WARNING"]
    context: dict[str, Any]


class PortfolioHeat(BaseModel):
    """
    Enhanced portfolio heat tracking with Wyckoff context.

    Comprehensive portfolio heat report that combines:
    - Core heat calculation (AC 1-2)
    - Phase-adaptive limits (AC 11-12)
    - Volume-based multipliers (AC 13-15)
    - Campaign correlation (AC 16-17)
    - Context-aware warnings (AC 7 revised)

    Heat Calculation Flow:
    ----------------------
    1. Calculate raw_heat: Σ(position_risk_pct)
    2. Apply correlation adjustment: identify clusters, apply penalties
    3. Set total_heat = correlation_adjusted_heat
    4. Determine phase-adjusted limit based on majority phase
    5. Apply volume multiplier if weighted score ≥20
    6. Enforce absolute maximum: 15.0%
    7. Generate context-aware warnings

    Example:
    --------
    >>> from decimal import Decimal
    >>> heat = PortfolioHeat(
    ...     position_count=4,
    ...     risk_breakdown={"AAPL": Decimal("3.0"), "MSFT": Decimal("2.5")},
    ...     raw_heat=Decimal("12.0"),
    ...     correlation_adjusted_heat=Decimal("11.0"),
    ...     total_heat=Decimal("11.0"),
    ...     available_capacity=Decimal("4.0"),
    ...     phase_distribution={"D": 3, "C": 1},
    ...     applied_heat_limit=Decimal("15.0"),
    ...     limit_basis="Phase D majority (3/4)",
    ...     weighted_volume_score=Decimal("32.0"),
    ...     volume_multiplier=Decimal("0.70"),
    ...     volume_adjusted_limit=Decimal("21.4"),
    ...     campaign_clusters=[],
    ...     warnings=[]
    ... )
    """

    # Core fields (original AC 5)
    position_count: int = Field(
        ..., ge=0, description="Number of open positions"
    )
    risk_breakdown: dict[str, Decimal] = Field(
        default_factory=dict, description="Symbol -> risk_pct mapping"
    )

    # Heat calculations
    raw_heat: Decimal = Field(
        ...,
        description="Unadjusted sum of position risks",
    )
    correlation_adjusted_heat: Decimal = Field(
        ...,
        description="Heat adjusted for campaign correlation",
    )
    total_heat: Decimal = Field(
        ...,
        description="Final portfolio heat (correlation-adjusted)",
    )
    available_capacity: Decimal = Field(
        ...,
        description="Remaining heat capacity",
    )

    # Phase context (Enhancement 1: AC 11-12)
    phase_distribution: dict[str, int] = Field(
        default_factory=dict, description="Wyckoff phase -> position count"
    )
    applied_heat_limit: Decimal = Field(
        ..., description="Heat limit actually used (phase-adjusted)"
    )
    limit_basis: str = Field(
        ..., description="Explanation of limit (e.g., 'Phase D majority (3/4)')"
    )

    # Volume context (Enhancement 2: AC 13-15)
    weighted_volume_score: Decimal = Field(
        ..., description="Portfolio avg volume confirmation score (0-40)"
    )
    volume_multiplier: Decimal = Field(
        ..., description="Volume-based risk multiplier (0.70-1.0)"
    )
    volume_adjusted_limit: Optional[Decimal] = Field(
        default=None, description="Limit after volume adjustment (if applied)"
    )

    # Correlation context (Enhancement 3: AC 16-17)
    campaign_clusters: list[CampaignCluster] = Field(
        default_factory=list, description="Positions clustered by sector/phase"
    )

    # Warnings (Enhancement 4: AC 7 revised)
    warnings: list[PortfolioWarning] = Field(
        default_factory=list, description="Context-aware warnings"
    )

    class Config:
        """Pydantic configuration for JSON encoding."""

        json_encoders = {
            Decimal: str  # Serialize Decimal as string to preserve precision
        }
