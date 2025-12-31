"""
Campaign Tracker Service - Business Logic for Campaign Visualization (Story 11.4)

Purpose:
--------
Provides business logic for calculating campaign progression, health status,
P&L calculations, and preparing campaign data for frontend visualization.

Key Functions:
--------------
1. calculate_progression: Determine completed/pending phases and next expected entry
2. calculate_health: Assess campaign health (green/yellow/red)
3. calculate_pnl: Compute current P&L for each entry
4. calculate_quality_score: Score campaign based on preliminary events
5. build_campaign_response: Construct complete CampaignResponse for API

Integration:
------------
- Story 11.4 Tasks 2, 3: Progression and health logic
- Story 11.4 Task 13: Preliminary events and quality scoring
- Uses CampaignRepository for data access
- Uses Decimal for all financial calculations

Author: Story 11.4
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

import structlog

from src.models.campaign_tracker import (
    CampaignEntryDetail,
    CampaignHealthStatus,
    CampaignProgressionModel,
    CampaignQualityScore,
    CampaignResponse,
    ExitPlanDisplay,
    PreliminaryEvent,
    TradingRangeLevels,
)
from src.models.position import Position as PositionModel
from src.repositories.models import CampaignModel

logger = structlog.get_logger(__name__)


def calculate_progression(campaign: CampaignModel) -> CampaignProgressionModel:
    """
    Calculate campaign progression through BMAD phases (Story 11.4 Task 2).

    Analyzes completed entries to determine:
    - Which phases have been completed (Spring, SOS, LPS)
    - Which phases are pending
    - Next expected entry with human-readable description
    - Current Wyckoff phase

    Progression Logic:
    ------------------
    - Phase C: Spring expected (first entry)
    - Phase D: SOS expected (after Spring, breakout confirmation)
    - Phase E: LPS expected (after SOS, pullback entry)
    - Sequence must follow: Spring → SOS → LPS

    Parameters:
    -----------
    campaign : CampaignModel
        Campaign database model

    Returns:
    --------
    CampaignProgressionModel
        Progression state with completed/pending phases

    Example:
    --------
    >>> progression = calculate_progression(campaign)
    >>> print(progression.completed_phases)  # ["SPRING", "SOS"]
    >>> print(progression.next_expected)  # "Phase E watch - monitoring for LPS"
    """
    # Extract completed pattern types from campaign positions
    completed_phases = []
    if campaign.positions:
        for position in campaign.positions:
            pattern = position.entry_pattern.upper()
            if pattern in ["SPRING", "SOS", "LPS"] and pattern not in completed_phases:
                # Only include FILLED or CLOSED positions
                if position.status in ["FILLED", "CLOSED"]:
                    completed_phases.append(pattern)

    # Sort by Wyckoff sequence order
    sequence_order = {"SPRING": 1, "SOS": 2, "LPS": 3}
    completed_phases.sort(key=lambda x: sequence_order.get(x, 99))

    # Determine pending phases based on Wyckoff progression
    pending_phases = []
    next_expected = ""
    current_phase = campaign.phase or "C"

    if "SPRING" not in completed_phases:
        pending_phases = ["SPRING", "SOS", "LPS"]
        next_expected = "Phase C watch - monitoring for Spring"
        current_phase = "C"
    elif "SOS" not in completed_phases:
        pending_phases = ["SOS", "LPS"]
        next_expected = "Phase D watch - monitoring for SOS"
        current_phase = "D"
    elif "LPS" not in completed_phases:
        pending_phases = ["LPS"]
        next_expected = "Phase E watch - monitoring for LPS"
        current_phase = "E"
    else:
        # All entries completed
        pending_phases = []
        next_expected = "Campaign complete - all entries filled"
        current_phase = "E"

    return CampaignProgressionModel(
        completed_phases=completed_phases,
        pending_phases=pending_phases,
        next_expected=next_expected,
        current_phase=current_phase,
    )


def calculate_health(
    campaign: CampaignModel, total_allocation: Decimal, any_stop_hit: bool = False
) -> CampaignHealthStatus:
    """
    Calculate campaign health status indicator (Story 11.4 Task 3).

    Health Criteria:
    ----------------
    GREEN (healthy):
    - total_allocation < 4%
    - No stop hits
    - Positive or neutral P&L
    - No invalidation level breaches

    YELLOW (caution):
    - total_allocation 4-5%
    - Approaching risk limits
    - Negative P&L but no stops hit

    RED (invalidated):
    - Stop hit on any entry
    - total_allocation > 5%
    - Creek level breached (Spring invalidation)
    - Ice level breached after SOS (post-breakout failure)

    Parameters:
    -----------
    campaign : CampaignModel
        Campaign database model
    total_allocation : Decimal
        Current total allocation percentage
    any_stop_hit : bool
        Whether any position has been stopped out

    Returns:
    --------
    CampaignHealthStatus
        Health status: GREEN, YELLOW, or RED

    Example:
    --------
    >>> health = calculate_health(campaign, Decimal("3.5"), any_stop_hit=False)
    >>> print(health)  # CampaignHealthStatus.GREEN
    """
    # RED conditions (critical)
    if any_stop_hit:
        logger.info(
            "campaign_health_red_stop_hit",
            campaign_id=str(campaign.id),
            reason="stop_hit",
        )
        return CampaignHealthStatus.RED

    if total_allocation > Decimal("5.0"):
        logger.info(
            "campaign_health_red_allocation",
            campaign_id=str(campaign.id),
            total_allocation=str(total_allocation),
            reason="allocation_exceeded",
        )
        return CampaignHealthStatus.RED

    if campaign.status == "INVALIDATED":
        logger.info(
            "campaign_health_red_invalidated",
            campaign_id=str(campaign.id),
            reason="invalidated_status",
        )
        return CampaignHealthStatus.RED

    # YELLOW conditions (caution)
    if total_allocation >= Decimal("4.0"):
        logger.info(
            "campaign_health_yellow",
            campaign_id=str(campaign.id),
            total_allocation=str(total_allocation),
            reason="approaching_limit",
        )
        return CampaignHealthStatus.YELLOW

    # Check negative P&L
    if campaign.total_pnl and campaign.total_pnl < Decimal("0"):
        pnl_percent = (
            (campaign.total_pnl / campaign.current_risk * Decimal("100"))
            if campaign.current_risk > Decimal("0")
            else Decimal("0")
        )
        if pnl_percent < Decimal("-10.0"):  # More than 10% loss
            logger.info(
                "campaign_health_yellow_pnl",
                campaign_id=str(campaign.id),
                pnl_percent=str(pnl_percent),
                reason="negative_pnl",
            )
            return CampaignHealthStatus.YELLOW

    # GREEN (healthy) - default
    logger.debug(
        "campaign_health_green",
        campaign_id=str(campaign.id),
        total_allocation=str(total_allocation),
    )
    return CampaignHealthStatus.GREEN


def calculate_entry_pnl(
    position: PositionModel, current_price: Optional[Decimal] = None
) -> tuple[Decimal, Decimal]:
    """
    Calculate P&L for a single campaign entry (Story 11.4 Subtask 1.8).

    Calculates both absolute P&L and percentage P&L for a position.
    For open positions, uses current_price if provided, otherwise uses
    position.current_price. For closed positions, uses realized_pnl.

    Parameters:
    -----------
    position : PositionModel
        Position database model
    current_price : Optional[Decimal]
        Latest market price (for open positions)

    Returns:
    --------
    tuple[Decimal, Decimal]
        (pnl, pnl_percent) - Absolute P&L and percentage

    Example:
    --------
    >>> pnl, pnl_pct = calculate_entry_pnl(position, Decimal("155.00"))
    >>> print(f"P&L: ${pnl}, {pnl_pct}%")
    """
    if position.status in ["CLOSED", "STOPPED"]:
        # Use realized P&L
        pnl = position.realized_pnl or Decimal("0")
        if position.entry_price and position.entry_price > Decimal("0"):
            pnl_percent = (pnl / (position.entry_price * position.shares)) * Decimal("100")
        else:
            pnl_percent = Decimal("0")
    else:
        # Calculate unrealized P&L
        price = current_price or position.current_price or position.entry_price
        pnl = (
            (price - position.entry_price) * position.shares
            if position.entry_price
            else Decimal("0")
        )
        if position.entry_price and position.entry_price > Decimal("0"):
            pnl_percent = ((price - position.entry_price) / position.entry_price) * Decimal("100")
        else:
            pnl_percent = Decimal("0")

    return pnl, pnl_percent


def calculate_quality_score(preliminary_events: list[PreliminaryEvent]) -> CampaignQualityScore:
    """
    Calculate campaign quality score based on preliminary events (Story 11.4 Task 13).

    Quality Scoring:
    ----------------
    - COMPLETE: All 4 events detected (PS, SC, AR, ST) - highest reliability
    - PARTIAL: 2-3 events detected - standard quality
    - MINIMAL: 0-1 events detected - lower quality

    A complete PS → SC → AR → ST sequence before Spring entry indicates
    proper Wyckoff accumulation with all phases completed, providing
    higher confidence in the setup.

    Parameters:
    -----------
    preliminary_events : list[PreliminaryEvent]
        List of detected preliminary events

    Returns:
    --------
    CampaignQualityScore
        Quality score: COMPLETE, PARTIAL, or MINIMAL

    Example:
    --------
    >>> events = [PS_event, SC_event, AR_event, ST_event]
    >>> score = calculate_quality_score(events)
    >>> print(score)  # CampaignQualityScore.COMPLETE
    """
    event_count = len(preliminary_events)

    if event_count >= 4:
        return CampaignQualityScore.COMPLETE
    elif event_count >= 2:
        return CampaignQualityScore.PARTIAL
    else:
        return CampaignQualityScore.MINIMAL


def build_campaign_response(
    campaign: CampaignModel,
    trading_range_levels: TradingRangeLevels,
    exit_plan: ExitPlanDisplay,
    preliminary_events: list[PreliminaryEvent],
    current_prices: dict[UUID, Decimal],
) -> CampaignResponse:
    """
    Build complete CampaignResponse for API (Story 11.4 Task 1).

    Constructs comprehensive campaign data including:
    - Campaign identification and status
    - All entries with P&L calculations
    - Progression and health status
    - Exit plan and trading range levels
    - Preliminary events and quality score

    Parameters:
    -----------
    campaign : CampaignModel
        Campaign database model
    trading_range_levels : TradingRangeLevels
        Creek/Ice/Jump price levels
    exit_plan : ExitPlanDisplay
        Exit strategy with targets
    preliminary_events : list[PreliminaryEvent]
        PS, SC, AR, ST events before Spring
    current_prices : dict[UUID, Decimal]
        Map of position_id to current market price

    Returns:
    --------
    CampaignResponse
        Complete campaign data for frontend

    Example:
    --------
    >>> response = build_campaign_response(
    ...     campaign,
    ...     TradingRangeLevels(...),
    ...     ExitPlanDisplay(...),
    ...     preliminary_events,
    ...     current_prices
    ... )
    """
    # Build entry details with P&L calculations
    entries: list[CampaignEntryDetail] = []
    total_pnl = Decimal("0")
    any_stop_hit = False

    if campaign.positions:
        for position in campaign.positions:
            current_price = current_prices.get(position.id, position.current_price)
            pnl, pnl_percent = calculate_entry_pnl(position, current_price)
            total_pnl += pnl

            if position.status == "STOPPED":
                any_stop_hit = True

            entry = CampaignEntryDetail(
                pattern_type=position.entry_pattern,
                signal_id=position.signal_id,
                entry_price=position.entry_price or Decimal("0"),
                position_size=position.shares or Decimal("0"),
                shares=int(position.shares) if position.shares else 0,
                status=position.status,
                pnl=pnl,
                pnl_percent=pnl_percent,
                entry_timestamp=position.entry_date or datetime.now(UTC),
                exit_timestamp=position.closed_date,
            )
            entries.append(entry)

    # Calculate total P&L percentage
    total_investment = sum((e.entry_price * e.position_size for e in entries), Decimal("0"))
    total_pnl_percent = (
        (total_pnl / total_investment * Decimal("100"))
        if total_investment > Decimal("0")
        else Decimal("0")
    )

    # Calculate progression
    progression = calculate_progression(campaign)

    # Calculate health status
    health = calculate_health(
        campaign,
        campaign.total_allocation or Decimal("0"),
        any_stop_hit=any_stop_hit,
    )

    # Calculate quality score
    quality_score = calculate_quality_score(preliminary_events)

    return CampaignResponse(
        id=campaign.id,
        symbol=campaign.symbol,
        timeframe=campaign.timeframe,
        trading_range_id=campaign.trading_range_id,
        status=campaign.status,
        total_allocation=campaign.total_allocation or Decimal("0"),
        current_risk=campaign.current_risk or Decimal("0"),
        entries=entries,
        average_entry=campaign.weighted_avg_entry,
        total_pnl=total_pnl,
        total_pnl_percent=total_pnl_percent,
        progression=progression,
        health=health,
        exit_plan=exit_plan,
        trading_range_levels=trading_range_levels,
        preliminary_events=preliminary_events,
        campaign_quality_score=quality_score,
        started_at=campaign.start_date or campaign.created_at,
        completed_at=campaign.completed_at,
    )
