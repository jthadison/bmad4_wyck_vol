"""
Risk Dashboard API Routes - Real-Time Risk Monitoring (Story 10.6)

Purpose:
--------
Provides REST API endpoints for risk dashboard visualization, aggregating
portfolio heat, campaign risks, correlated risks, and proximity warnings.

Endpoints:
----------
GET /api/v1/risk/dashboard - Get complete risk dashboard data

Integration:
------------
- Calls Risk Management Service (Epic 7: Stories 7.3-7.5)
- Aggregates portfolio heat, campaign risk, and correlated risk
- Generates proximity warnings at 80% thresholds
- Provides 7-day heat history for trend visualization

Author: Story 10.6
"""

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import structlog
from fastapi import APIRouter, HTTPException
from fastapi import status as http_status

from src.models.portfolio import Position
from src.models.risk_dashboard import (
    CampaignRiskSummary,
    CorrelatedRiskSummary,
    HeatHistoryPoint,
    RiskDashboardData,
)
from src.risk_management.portfolio import calculate_portfolio_heat

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/risk", tags=["risk"])


# ============================================================================
# Mock Data Functions (Replace with actual repository calls in production)
# ============================================================================


async def get_open_positions() -> list[Position]:
    """
    Fetch all open positions from database.

    TODO: Replace with actual repository call when position repository is implemented.

    Returns:
    --------
    list[Position]
        List of all open positions
    """
    # PLACEHOLDER: Return mock data
    # In production, replace with:
    # from backend.src.repositories.position_repository import PositionRepository
    # repo = PositionRepository()
    # return await repo.get_open_positions()

    logger.debug("get_open_positions_called", note="Using mock data")

    # Mock data for demonstration (Story 10.6 AC 1-10)
    mock_positions = [
        Position(
            symbol="AAPL",
            position_risk_pct=Decimal("2.3"),
            status="OPEN",
            wyckoff_phase="D",
            volume_confirmation_score=Decimal("35.0"),
            sector="Technology",
            campaign_id=UUID("12345678-1234-5678-1234-567812345678"),
        ),
        Position(
            symbol="MSFT",
            position_risk_pct=Decimal("1.8"),
            status="OPEN",
            wyckoff_phase="C",
            volume_confirmation_score=Decimal("28.0"),
            sector="Technology",
            campaign_id=UUID("12345678-1234-5678-1234-567812345678"),
        ),
        Position(
            symbol="JNJ",
            position_risk_pct=Decimal("1.5"),
            status="OPEN",
            wyckoff_phase="D",
            volume_confirmation_score=Decimal("30.0"),
            sector="Healthcare",
            campaign_id=UUID("87654321-4321-8765-4321-876543218765"),
        ),
        Position(
            symbol="PFE",
            position_risk_pct=Decimal("1.6"),
            status="OPEN",
            wyckoff_phase="C",
            volume_confirmation_score=Decimal("25.0"),
            sector="Healthcare",
            campaign_id=UUID("87654321-4321-8765-4321-876543218765"),
        ),
    ]

    return mock_positions


async def get_heat_history_7d() -> list[HeatHistoryPoint]:
    """
    Fetch 7-day portfolio heat history from time-series data.

    TODO: Replace with actual time-series query when heat history tracking is implemented.

    Returns:
    --------
    list[HeatHistoryPoint]
        Last 7 days of portfolio heat measurements
    """
    # PLACEHOLDER: Generate mock 7-day history
    # In production, replace with:
    # from backend.src.repositories.heat_history_repository import HeatHistoryRepository
    # repo = HeatHistoryRepository()
    # return await repo.get_last_n_days(7)

    logger.debug("get_heat_history_7d_called", note="Using mock data")

    # Generate mock 7-day history (showing upward trend)
    history = []
    base_date = datetime.now(UTC) - timedelta(days=6)

    heat_values = [
        Decimal("4.5"),
        Decimal("5.2"),
        Decimal("5.8"),
        Decimal("6.3"),
        Decimal("6.8"),
        Decimal("7.0"),
        Decimal("7.2"),
    ]

    for day_offset, heat_value in enumerate(heat_values):
        point = HeatHistoryPoint(
            timestamp=base_date + timedelta(days=day_offset), heat_percentage=heat_value
        )
        history.append(point)

    return history


def get_campaign_id_label(campaign_id: UUID) -> str:
    """
    Generate human-readable campaign label from UUID.

    TODO: Replace with actual campaign lookup when campaign repository is implemented.

    Parameters:
    -----------
    campaign_id : UUID
        Campaign identifier

    Returns:
    --------
    str
        Human-readable campaign label
    """
    # PLACEHOLDER: Generate simple label from UUID
    # In production, replace with:
    # from backend.src.repositories.campaign_repository import CampaignRepository
    # repo = CampaignRepository()
    # campaign = await repo.get_by_id(campaign_id)
    # return campaign.display_name

    short_id = str(campaign_id)[:8]
    return f"C-{short_id}"


def calculate_campaign_risks(positions: list[Position]) -> list[CampaignRiskSummary]:
    """
    Calculate per-campaign risk allocation with Wyckoff phase distribution.

    Aggregates positions by campaign_id and calculates:
    - Total risk allocated to campaign
    - Position count
    - Wyckoff phase distribution (MVP CRITICAL)

    Parameters:
    -----------
    positions : list[Position]
        List of open positions

    Returns:
    --------
    list[CampaignRiskSummary]
        Per-campaign risk summaries with phase distribution
    """
    if not positions:
        return []

    # Group positions by campaign_id
    campaign_map: dict[UUID | None, list[Position]] = defaultdict(list)
    for pos in positions:
        campaign_map[pos.campaign_id].append(pos)

    campaign_risks = []

    for campaign_id, campaign_positions in campaign_map.items():
        if campaign_id is None:
            continue  # Skip non-campaign positions

        # Calculate total risk for this campaign
        risk_allocated = sum(pos.position_risk_pct for pos in campaign_positions)

        # Calculate Wyckoff phase distribution (MVP CRITICAL - AC 4, 5)
        phase_distribution: dict[str, int] = defaultdict(int)
        for pos in campaign_positions:
            phase = pos.wyckoff_phase if pos.wyckoff_phase else "unknown"
            phase_distribution[phase] += 1

        summary = CampaignRiskSummary(
            campaign_id=get_campaign_id_label(campaign_id),
            risk_allocated=risk_allocated,
            positions_count=len(campaign_positions),
            campaign_limit=Decimal("5.0"),  # Fixed campaign limit (FR18)
            phase_distribution=dict(phase_distribution),
        )
        campaign_risks.append(summary)

    # Sort by risk allocated (descending)
    campaign_risks.sort(key=lambda c: c.risk_allocated, reverse=True)

    logger.debug(
        "campaign_risks_calculated", campaign_count=len(campaign_risks), campaigns=campaign_risks
    )

    return campaign_risks


def calculate_correlated_risks(positions: list[Position]) -> list[CorrelatedRiskSummary]:
    """
    Calculate per-sector correlated risk allocation.

    Aggregates positions by sector to track correlated risk exposure.

    Parameters:
    -----------
    positions : list[Position]
        List of open positions

    Returns:
    --------
    list[CorrelatedRiskSummary]
        Per-sector risk summaries
    """
    if not positions:
        return []

    # Group positions by sector
    sector_map: dict[str, list[Position]] = defaultdict(list)
    for pos in positions:
        sector = pos.sector if pos.sector else "Unknown"
        sector_map[sector].append(pos)

    correlated_risks = []

    for sector, sector_positions in sector_map.items():
        # Calculate total risk for this sector
        risk_allocated = sum(pos.position_risk_pct for pos in sector_positions)

        summary = CorrelatedRiskSummary(
            sector=sector,
            risk_allocated=risk_allocated,
            sector_limit=Decimal("6.0"),  # Fixed sector limit (FR18)
        )
        correlated_risks.append(summary)

    # Sort by risk allocated (descending)
    correlated_risks.sort(key=lambda c: c.risk_allocated, reverse=True)

    logger.debug(
        "correlated_risks_calculated", sector_count=len(correlated_risks), sectors=correlated_risks
    )

    return correlated_risks


def generate_proximity_warnings(
    total_heat: Decimal,
    campaign_risks: list[CampaignRiskSummary],
    correlated_risks: list[CorrelatedRiskSummary],
) -> list[str]:
    """
    Generate proximity warnings for limits approaching 80% capacity (AC 6).

    Warning thresholds:
    - Portfolio heat > 8.0% (80% of 10% limit)
    - Campaign risk > 4.0% (80% of 5% limit)
    - Sector risk > 4.8% (80% of 6% limit)

    Parameters:
    -----------
    total_heat : Decimal
        Current portfolio heat percentage
    campaign_risks : list[CampaignRiskSummary]
        Per-campaign risk summaries
    correlated_risks : list[CorrelatedRiskSummary]
        Per-sector risk summaries

    Returns:
    --------
    list[str]
        List of warning messages
    """
    warnings = []

    # Portfolio heat warning (80% of 10% = 8%)
    portfolio_limit = Decimal("10.0")
    portfolio_threshold = Decimal("8.0")

    if total_heat >= portfolio_threshold:
        capacity_pct = (total_heat / portfolio_limit * 100).quantize(Decimal("0.1"))
        warnings.append(f"Portfolio heat at {capacity_pct}% capacity")
        logger.warning(
            "proximity_warning_portfolio_heat",
            total_heat=str(total_heat),
            capacity_pct=str(capacity_pct),
        )

    # Campaign risk warnings (80% of 5% = 4%)
    campaign_threshold = Decimal("4.0")

    for campaign in campaign_risks:
        if campaign.risk_allocated >= campaign_threshold:
            capacity_pct = (campaign.risk_allocated / campaign.campaign_limit * 100).quantize(
                Decimal("0.1")
            )
            warnings.append(f"Campaign {campaign.campaign_id} at {capacity_pct}% capacity")
            logger.warning(
                "proximity_warning_campaign_risk",
                campaign_id=campaign.campaign_id,
                risk=str(campaign.risk_allocated),
                capacity_pct=str(capacity_pct),
            )

    # Sector risk warnings (80% of 6% = 4.8%)
    sector_threshold = Decimal("4.8")

    for sector in correlated_risks:
        if sector.risk_allocated >= sector_threshold:
            capacity_pct = (sector.risk_allocated / sector.sector_limit * 100).quantize(
                Decimal("0.1")
            )
            warnings.append(f"{sector.sector} sector at {capacity_pct}% capacity")
            logger.warning(
                "proximity_warning_sector_risk",
                sector=sector.sector,
                risk=str(sector.risk_allocated),
                capacity_pct=str(capacity_pct),
            )

    return warnings


# ============================================================================
# API Endpoints
# ============================================================================


@router.get("/dashboard", response_model=RiskDashboardData, status_code=http_status.HTTP_200_OK)
async def get_risk_dashboard() -> RiskDashboardData:
    """
    Get complete risk dashboard data for visualization (AC 1-10).

    Returns comprehensive risk metrics:
    - Portfolio heat and available capacity
    - Campaign risk allocation with Wyckoff phase distribution
    - Correlated sector risk allocation
    - Proximity warnings (limits >80%)
    - 7-day heat history for trend sparkline

    Integration:
    ------------
    - Calls Risk Management Service (Epic 7) for heat calculations
    - Aggregates campaign and sector risks
    - Generates proximity warnings at 80% thresholds

    Returns:
    --------
    RiskDashboardData
        Complete risk dashboard aggregation

    Raises:
    -------
    HTTPException (503)
        If Risk Management Service unavailable
    HTTPException (500)
        If portfolio heat calculation fails

    Example Response:
    -----------------
    {
        "total_heat": "7.2",
        "total_heat_limit": "10.0",
        "available_capacity": "2.8",
        "estimated_signals_capacity": 3,
        "per_trade_risk_range": "0.5-1.0% per signal",
        "campaign_risks": [...],
        "correlated_risks": [...],
        "proximity_warnings": ["Portfolio heat at 72% capacity"],
        "heat_history_7d": [...],
        "last_updated": "2024-03-15T14:30:00Z"
    }
    """
    logger.info("risk_dashboard_requested")

    try:
        # 1. Fetch open positions
        positions = await get_open_positions()

        # 2. Calculate portfolio heat using Risk Management Service (Story 7.3)
        total_heat = calculate_portfolio_heat(positions)

        # 3. Calculate campaign risks with phase distribution (AC 4, 5)
        campaign_risks = calculate_campaign_risks(positions)

        # 4. Calculate correlated risks by sector (AC 4)
        correlated_risks = calculate_correlated_risks(positions)

        # 5. Calculate available capacity (AC 3)
        total_heat_limit = Decimal("10.0")  # MVP fixed limit (FR18)
        available_capacity = total_heat_limit - total_heat

        # 6. Estimate signal capacity (AC 3)
        # Use average per-trade risk of 0.5-1.0% (pattern-specific from FR18)
        avg_per_trade_risk = Decimal("0.75")  # Midpoint of range
        estimated_signals_capacity = (
            int(available_capacity / avg_per_trade_risk) if available_capacity > 0 else 0
        )

        # 7. Generate proximity warnings (AC 6)
        proximity_warnings = generate_proximity_warnings(
            total_heat, campaign_risks, correlated_risks
        )

        # 8. Fetch 7-day heat history (AC 7)
        heat_history_7d = await get_heat_history_7d()

        # 9. Build response
        dashboard_data = RiskDashboardData(
            total_heat=total_heat,
            total_heat_limit=total_heat_limit,
            available_capacity=available_capacity,
            estimated_signals_capacity=estimated_signals_capacity,
            per_trade_risk_range="0.5-1.0% per signal",  # Pattern-specific (FR18)
            campaign_risks=campaign_risks,
            correlated_risks=correlated_risks,
            proximity_warnings=proximity_warnings,
            heat_history_7d=heat_history_7d,
            last_updated=datetime.now(UTC),
        )

        logger.info(
            "risk_dashboard_generated",
            total_heat=str(total_heat),
            campaign_count=len(campaign_risks),
            sector_count=len(correlated_risks),
            warning_count=len(proximity_warnings),
        )

        return dashboard_data

    except Exception as e:
        logger.error("risk_dashboard_error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate risk dashboard: {str(e)}",
        ) from e
