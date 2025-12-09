"""
Risk Dashboard Data Models - Portfolio Risk Visualization (Story 10.6)

Purpose:
--------
Provides Pydantic models for the Risk Dashboard API endpoint, aggregating
portfolio heat, campaign risks, correlated risks, and proximity warnings
for real-time risk monitoring visualization.

Data Models:
------------
1. HeatHistoryPoint: Single point in 7-day heat history
2. CampaignRiskSummary: Per-campaign risk allocation with Wyckoff phase distribution
3. CorrelatedRiskSummary: Per-sector risk allocation
4. RiskDashboardData: Complete risk dashboard aggregation

Wyckoff Integration:
--------------------
- Phase distribution tracking: Shows which Wyckoff phase each position is in
- Campaign progression context: Helps traders understand risk maturity
- Strategic risk allocation: Different phases require different risk management

Author: Story 10.6
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class HeatHistoryPoint(BaseModel):
    """
    Single point in portfolio heat history time series.

    Used for 7-day trend sparkline visualization (AC 7).

    Attributes:
    -----------
    timestamp : datetime
        UTC timestamp for this heat measurement
    heat_percentage : Decimal
        Portfolio heat percentage at this timestamp
    """

    model_config = ConfigDict(json_encoders={Decimal: str}, str_strip_whitespace=True)

    timestamp: datetime = Field(..., description="UTC timestamp for this heat measurement")
    heat_percentage: Decimal = Field(
        ..., description="Portfolio heat percentage at this timestamp", ge=0, le=100
    )


class CampaignRiskSummary(BaseModel):
    """
    Per-campaign risk allocation summary with Wyckoff phase distribution.

    **MVP REQUIREMENT**: phase_distribution field is critical for understanding
    WHERE in the Wyckoff accumulation cycle campaign risk is allocated.
    Early-phase risk (C) has different characteristics than markup-phase risk (D/E).

    Attributes:
    -----------
    campaign_id : str
        Campaign identifier (e.g., "C-2024-03-15-AAPL")
    risk_allocated : Decimal
        Risk allocated to this campaign as percentage (e.g., 2.3 for 2.3%)
    positions_count : int
        Number of open positions in this campaign
    campaign_limit : Decimal
        Campaign risk limit (always 5.0% for MVP)
    phase_distribution : dict[str, int]
        **MVP CRITICAL**: Distribution of positions across Wyckoff phases
        Example: {"C": 1, "D": 1} = 1 position in Phase C (testing), 1 in Phase D (markup)

    Example:
    --------
    >>> summary = CampaignRiskSummary(
    ...     campaign_id="C-AAPL-001",
    ...     risk_allocated=Decimal("2.3"),
    ...     positions_count=2,
    ...     campaign_limit=Decimal("5.0"),
    ...     phase_distribution={"C": 1, "D": 1}
    ... )
    """

    model_config = ConfigDict(json_encoders={Decimal: str}, str_strip_whitespace=True)

    campaign_id: str = Field(..., description="Campaign identifier")
    risk_allocated: Decimal = Field(
        ..., description="Risk allocated to this campaign as percentage", ge=0, le=100
    )
    positions_count: int = Field(..., description="Number of open positions in this campaign", ge=0)
    campaign_limit: Decimal = Field(
        ..., description="Campaign risk limit percentage (always 5.0 for MVP)", ge=0, le=100
    )
    phase_distribution: dict[str, int] = Field(
        ...,
        description="Distribution of positions across Wyckoff phases (e.g., {'C': 1, 'D': 1})",
    )


class CorrelatedRiskSummary(BaseModel):
    """
    Per-sector correlated risk allocation summary.

    Tracks risk concentration within specific market sectors to prevent
    over-exposure to correlated assets (AC 4).

    Attributes:
    -----------
    sector : str
        Sector name (e.g., "Technology", "Healthcare", "Financials")
    risk_allocated : Decimal
        Risk allocated to this sector as percentage
    sector_limit : Decimal
        Sector correlation limit (always 6.0% for MVP)

    Example:
    --------
    >>> summary = CorrelatedRiskSummary(
    ...     sector="Technology",
    ...     risk_allocated=Decimal("4.1"),
    ...     sector_limit=Decimal("6.0")
    ... )
    """

    model_config = ConfigDict(json_encoders={Decimal: str}, str_strip_whitespace=True)

    sector: str = Field(..., description="Sector name (e.g., Technology, Healthcare)")
    risk_allocated: Decimal = Field(
        ..., description="Risk allocated to this sector as percentage", ge=0, le=100
    )
    sector_limit: Decimal = Field(
        ..., description="Sector correlation limit percentage (always 6.0 for MVP)", ge=0, le=100
    )


class RiskDashboardData(BaseModel):
    """
    Complete risk dashboard data aggregation.

    Primary response model for GET /api/v1/risk/dashboard endpoint (AC 1-10).
    Aggregates portfolio heat, campaign risks, correlated risks, and proximity
    warnings for real-time visualization.

    Attributes:
    -----------
    total_heat : Decimal
        Current portfolio heat percentage (sum of all position risks)
    total_heat_limit : Decimal
        Portfolio heat limit (always 10.0% for MVP)
    available_capacity : Decimal
        Available risk capacity (total_heat_limit - total_heat)
    estimated_signals_capacity : int
        Estimated number of signals that can be taken with available capacity
    per_trade_risk_range : str
        Expected per-trade risk range (e.g., "0.5-1.0% per signal")
    campaign_risks : list[CampaignRiskSummary]
        List of active campaigns with risk allocation and phase distribution
    correlated_risks : list[CorrelatedRiskSummary]
        List of sectors with risk allocation
    proximity_warnings : list[str]
        List of proximity warning messages (AC 6)
    heat_history_7d : list[HeatHistoryPoint]
        Last 7 days of portfolio heat history for sparkline
    last_updated : datetime
        UTC timestamp of this data snapshot

    Example:
    --------
    >>> data = RiskDashboardData(
    ...     total_heat=Decimal("7.2"),
    ...     total_heat_limit=Decimal("10.0"),
    ...     available_capacity=Decimal("2.8"),
    ...     estimated_signals_capacity=3,
    ...     per_trade_risk_range="0.5-1.0% per signal",
    ...     campaign_risks=[...],
    ...     correlated_risks=[...],
    ...     proximity_warnings=["Portfolio heat at 72% capacity"],
    ...     heat_history_7d=[...],
    ...     last_updated=datetime.utcnow()
    ... )
    """

    model_config = ConfigDict(json_encoders={Decimal: str}, str_strip_whitespace=True)

    total_heat: Decimal = Field(..., description="Current portfolio heat percentage", ge=0, le=100)
    total_heat_limit: Decimal = Field(
        ..., description="Portfolio heat limit percentage (always 10.0 for MVP)", ge=0, le=100
    )
    available_capacity: Decimal = Field(
        ..., description="Available risk capacity (limit - total_heat)", ge=0, le=100
    )
    estimated_signals_capacity: int = Field(
        ..., description="Estimated number of signals that can be taken", ge=0
    )
    per_trade_risk_range: str = Field(
        ..., description="Expected per-trade risk range (e.g., '0.5-1.0% per signal')"
    )
    campaign_risks: list[CampaignRiskSummary] = Field(
        ..., description="List of active campaigns with risk allocation"
    )
    correlated_risks: list[CorrelatedRiskSummary] = Field(
        ..., description="List of sectors with risk allocation"
    )
    proximity_warnings: list[str] = Field(
        ..., description="List of proximity warning messages (e.g., 'Portfolio at 82% capacity')"
    )
    heat_history_7d: list[HeatHistoryPoint] = Field(
        ..., description="Last 7 days of portfolio heat history"
    )
    last_updated: datetime = Field(..., description="UTC timestamp of this data snapshot")
