"""
Risk Dashboard API Routes - Real-Time Risk Monitoring (Story 10.6)

Purpose:
--------
Provides REST API endpoints for risk dashboard visualization, aggregating
portfolio heat, campaign risks, correlated risks, and proximity warnings.

Endpoints:
----------
GET /api/v1/risk/dashboard        - Get complete risk dashboard data
GET /api/v1/risk/correlation-matrix - Get NxN campaign correlation matrix

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

import numpy as np
import pandas as pd
import structlog
from fastapi import APIRouter, HTTPException
from fastapi import status as http_status

from src.models.correlation_matrix import BlockedPair, CorrelationMatrixResponse
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
    # from src.repositories.position_repository import PositionRepository
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
    # from src.repositories.heat_history_repository import HeatHistoryRepository
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
    # from src.repositories.campaign_repository import CampaignRepository
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


# ============================================================================
# Correlation Matrix Support Functions
# ============================================================================

# Correlation threshold above which Rachel (Risk Manager) blocks entries.
# Per CLAUDE.md: Max correlated risk = 6.0%; threshold for Pearson correlation
# is 0.6 (two positions are "highly correlated" if r > 0.6).
CORRELATION_BLOCK_THRESHOLD = 0.6


def _build_mock_price_series(campaigns: list[str]) -> dict[str, list[float]]:
    """
    Build synthetic daily price series for active campaigns.

    In a production system this would query historical OHLCV data from the
    market data service for each campaign's underlying symbol. We stub this
    with deterministic pseudo-random series that produce realistic correlations:

    - Tech symbols (AAPL, MSFT, GOOGL, META, NVDA, AMZN) are seeded so they
      yield high pairwise correlations (~0.65-0.82), reflecting real sector
      co-movement.
    - Non-tech symbols (JNJ, PFE, XOM, etc.) produce low correlations with tech.

    Returns:
    --------
    dict[str, list[float]]
        Map from campaign name to list of 60 daily closing prices.
    """
    # Seed map: symbol abbreviation -> numpy seed.
    # Tech symbols share a similar base seed so their returns co-vary.
    tech_seed_base = 42
    tech_symbols = {"AAPL", "MSFT", "GOOGL", "GOOG", "META", "NVDA", "AMZN", "TSLA"}

    series: dict[str, list[float]] = {}
    n_days = 60

    # Shared market factor for tech sector (drives co-movement)
    rng_market = np.random.default_rng(tech_seed_base)
    market_factor = rng_market.normal(0, 0.01, n_days)

    for campaign in campaigns:
        # Extract symbol from campaign name (e.g., "AAPL-2024-01" -> "AAPL")
        symbol = campaign.split("-")[0].upper()

        if symbol in tech_symbols:
            # Tech: 70% market factor + 30% idiosyncratic -> high correlation
            seed_offset = sum(ord(c) for c in symbol) % 100
            rng = np.random.default_rng(tech_seed_base + seed_offset)
            idio = rng.normal(0, 0.008, n_days)
            daily_returns = 0.7 * market_factor + 0.3 * idio
        else:
            # Non-tech: 10% market factor + 90% idiosyncratic -> low correlation
            seed_offset = sum(ord(c) for c in symbol) % 1000 + 200
            rng = np.random.default_rng(seed_offset)
            idio = rng.normal(0, 0.012, n_days)
            daily_returns = 0.1 * market_factor + 0.9 * idio

        # Build price series from returns starting at 100.0
        prices = [100.0]
        for r in daily_returns:
            prices.append(prices[-1] * (1.0 + float(r)))

        series[campaign] = prices

    return series


def compute_correlation_matrix(
    campaigns: list[str],
    price_series: dict[str, list[float]],
    threshold: float = CORRELATION_BLOCK_THRESHOLD,
) -> tuple[list[list[float]], list[BlockedPair]]:
    """
    Compute pairwise Pearson correlation matrix from daily price return series.

    Why returns, not prices?
    ------------------------
    Price series are non-stationary (they have a trend / unit root), which makes
    Pearson correlation on raw prices spurious. Daily returns (percentage change)
    are stationary and are the correct input for correlation analysis per standard
    quantitative finance practice.

    Parameters:
    -----------
    campaigns : list[str]
        Ordered list of campaign names.
    price_series : dict[str, list[float]]
        Map from campaign name to list of daily closing prices.
    threshold : float
        Pearson correlation above which a pair is flagged as "blocked".

    Returns:
    --------
    tuple[list[list[float]], list[BlockedPair]]
        - NxN correlation matrix (symmetric, diagonal = 1.0)
        - List of blocked pairs where correlation > threshold
    """
    n = len(campaigns)

    if n == 0:
        return [], []

    if n == 1:
        return [[1.0]], []

    # Build DataFrame of daily returns for all campaigns.
    # Determine the expected return length from the first available price series
    # so all columns have equal length (required by pd.DataFrame).
    first_prices = next(iter(price_series.values())) if price_series else []
    expected_len = max(len(first_prices) - 1, 1)

    returns_data: dict[str, list[float]] = {}
    for campaign in campaigns:
        prices = price_series.get(campaign, [])
        if len(prices) < 2:
            # Fallback for missing or single-price series: flat (zero) returns
            returns_data[campaign] = [0.0] * expected_len
            continue
        prices_series = pd.Series(prices, dtype=float)
        # pct_change() computes (P_t - P_{t-1}) / P_{t-1}; drop the first NaN
        returns = prices_series.pct_change().dropna().tolist()
        # Pad or trim to expected length to ensure rectangular DataFrame
        if len(returns) < expected_len:
            returns = returns + [0.0] * (expected_len - len(returns))
        elif len(returns) > expected_len:
            returns = returns[:expected_len]
        returns_data[campaign] = returns

    returns_df = pd.DataFrame(returns_data)

    # Pearson correlation matrix on returns
    corr_df = returns_df.corr(method="pearson")

    # Build nested list (round to 4 decimal places for clean JSON)
    matrix: list[list[float]] = []
    for i in range(n):
        row = []
        for j in range(n):
            val = corr_df.iloc[i, j]
            # Handle NaN (e.g., constant series) by defaulting to 0.0 or 1.0
            if pd.isna(val):
                row.append(1.0 if i == j else 0.0)
            else:
                row.append(round(float(val), 4))
        matrix.append(row)

    # Identify blocked pairs (upper triangle only to avoid duplicates)
    blocked_pairs: list[BlockedPair] = []
    for i in range(n):
        for j in range(i + 1, n):
            corr_val = matrix[i][j]
            if corr_val > threshold:
                blocked_pairs.append(
                    BlockedPair(
                        campaign_a=campaigns[i],
                        campaign_b=campaigns[j],
                        correlation=corr_val,
                        reason=(
                            f"Correlation {corr_val:.2f} exceeds {threshold:.1f} threshold. "
                            f"Rachel (Risk Manager) blocks {campaigns[j]} entry because "
                            f"{campaigns[i]} is already in portfolio and combined correlated "
                            f"risk would exceed the 6% limit."
                        ),
                    )
                )

    return matrix, blocked_pairs


# ============================================================================
# Correlation Matrix Endpoint
# ============================================================================


@router.get(
    "/correlation-matrix",
    response_model=CorrelationMatrixResponse,
    status_code=http_status.HTTP_200_OK,
)
async def get_correlation_matrix() -> CorrelationMatrixResponse:
    """
    Get NxN pairwise correlation matrix for active campaigns.

    Returns Pearson correlation coefficients computed on daily return series
    (not prices - returns are stationary and the correct input for correlation).

    Color interpretation for UI heatmap:
    - Green  (< 0.3):  Low correlation - safe to hold both positions
    - Yellow (0.3-0.6): Moderate - monitor combined sector exposure
    - Red    (> 0.6):  HIGH - Rachel (Risk Manager) blocks new entry due to
                       correlated risk exceeding the 6% portfolio limit

    Returns:
    --------
    CorrelationMatrixResponse
        - campaigns: ordered list of active campaign names
        - matrix: NxN float matrix (symmetric, diagonal = 1.0)
        - blocked_pairs: pairs where correlation > 0.6
        - heat_threshold: 0.6 (the blocking threshold)
        - last_updated: computation timestamp

    Raises:
    -------
    HTTPException (500)
        If correlation computation fails.
    """
    logger.info("correlation_matrix_requested")

    try:
        # 1. Fetch active campaigns from mock positions
        positions = await get_open_positions()

        # Build unique campaign labels (one per symbol for this feature)
        # In production, this would come from the campaign repository
        campaign_labels: list[str] = []
        seen: set[str] = set()
        for pos in positions:
            label = f"{pos.symbol}-2024-01"
            if label not in seen:
                campaign_labels.append(label)
                seen.add(label)

        # If no positions, return an empty matrix
        if not campaign_labels:
            logger.info("correlation_matrix_no_campaigns")
            return CorrelationMatrixResponse(
                campaigns=[],
                matrix=[],
                blocked_pairs=[],
                heat_threshold=CORRELATION_BLOCK_THRESHOLD,
                last_updated=datetime.now(UTC),
            )

        # 2. Build synthetic price series (stub - replace with real market data in production)
        price_series = _build_mock_price_series(campaign_labels)

        # 3. Compute Pearson correlation on returns
        matrix, blocked_pairs = compute_correlation_matrix(
            campaign_labels, price_series, CORRELATION_BLOCK_THRESHOLD
        )

        response = CorrelationMatrixResponse(
            campaigns=campaign_labels,
            matrix=matrix,
            blocked_pairs=blocked_pairs,
            heat_threshold=CORRELATION_BLOCK_THRESHOLD,
            last_updated=datetime.now(UTC),
        )

        logger.info(
            "correlation_matrix_generated",
            campaign_count=len(campaign_labels),
            blocked_pairs=len(blocked_pairs),
        )

        return response

    except Exception as e:
        logger.error("correlation_matrix_error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to compute correlation matrix: {str(e)}",
        ) from e
