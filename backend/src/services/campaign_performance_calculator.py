"""
Campaign Performance Calculator Service - Story 9.6

Purpose:
--------
Calculates comprehensive performance metrics for completed campaigns including
R-multiples, win rates, drawdown analysis, phase-specific performance, and
P&L curve generation for visualization.

Core Functions:
---------------
1. calculate_campaign_performance: Main metrics calculation engine
2. calculate_max_drawdown_from_equity_curve: Drawdown analysis
3. get_aggregated_performance: Multi-campaign aggregations
4. generate_pnl_curve: P&L visualization data

Integration:
------------
- Story 9.4: Uses Position model and CampaignPositions
- Story 9.5: Requires campaigns with status = COMPLETED
- Story 9.6: Core performance tracking implementation

Author: Story 9.6
"""

import logging
from datetime import UTC, datetime
from decimal import Decimal
from statistics import median
from uuid import UUID

from src.models.campaign import (
    MAX_CAMPAIGN_RISK_PCT,
    AggregatedMetrics,
    CampaignMetrics,
    MetricsFilter,
    PnLCurve,
    PnLPoint,
    PositionMetrics,
    WinLossStatus,
)
from src.models.position import Position, PositionStatus

logger = logging.getLogger(__name__)


def calculate_campaign_performance(
    campaign_id: UUID,
    symbol: str,
    positions: list[Position],
    started_at: datetime,
    completed_at: datetime,
    initial_capital: Decimal,
    jump_target: Decimal | None = None,
    actual_high_reached: Decimal | None = None,
) -> CampaignMetrics:
    """
    Calculate comprehensive performance metrics for a completed campaign.

    This is the main calculation engine that computes all campaign-level and
    position-level metrics including R-multiples, win rates, drawdown analysis,
    and phase-specific performance.

    Parameters:
    -----------
    campaign_id : UUID
        Campaign identifier
    symbol : str
        Trading symbol
    positions : list[Position]
        All positions (OPEN + CLOSED) for the campaign
    started_at : datetime
        Campaign start timestamp
    completed_at : datetime
        Campaign completion timestamp
    initial_capital : Decimal
        Initial campaign capital for return % calculation
    jump_target : Decimal | None
        Expected Jump target from trading range
    actual_high_reached : Decimal | None
        Highest price reached during campaign

    Returns:
    --------
    CampaignMetrics
        Comprehensive campaign performance metrics

    Raises:
    -------
    ValueError
        If campaign has no closed positions or invalid data

    Example:
    --------
    >>> from decimal import Decimal
    >>> from datetime import datetime, UTC
    >>> from uuid import uuid4
    >>> metrics = calculate_campaign_performance(
    ...     campaign_id=uuid4(),
    ...     symbol="AAPL",
    ...     positions=[position1, position2, position3],
    ...     started_at=datetime.now(UTC),
    ...     completed_at=datetime.now(UTC),
    ...     initial_capital=Decimal("10000.00"),
    ...     jump_target=Decimal("175.00"),
    ...     actual_high_reached=Decimal("178.50")
    ... )
    """
    # Separate closed positions (only closed positions have realized metrics)
    closed_positions = [p for p in positions if p.status == PositionStatus.CLOSED]

    if not closed_positions:
        raise ValueError(
            f"Campaign {campaign_id} has no closed positions to calculate metrics from"
        )

    # Calculate position-level metrics for each closed position
    position_details: list[PositionMetrics] = []
    for position in closed_positions:
        # Calculate individual R-multiple
        # R = (exit_price - entry_price) / (entry_price - stop_loss)
        risk_per_share = position.entry_price - position.stop_loss
        if risk_per_share <= Decimal("0"):
            raise ValueError(
                f"Position {position.id} has invalid risk (entry {position.entry_price} "
                f"<= stop {position.stop_loss})"
            )

        profit_per_share = position.exit_price - position.entry_price  # type: ignore
        individual_r = (profit_per_share / risk_per_share).quantize(Decimal("0.0001"))

        # Determine win/loss status
        if position.realized_pnl is None:
            raise ValueError(f"Position {position.id} is CLOSED but has no realized_pnl")

        if position.realized_pnl > Decimal("0"):
            win_loss_status = WinLossStatus.WIN
        elif position.realized_pnl < Decimal("0"):
            win_loss_status = WinLossStatus.LOSS
        else:
            win_loss_status = WinLossStatus.BREAKEVEN

        # Calculate duration in bars (simplified - using days for now)
        if position.closed_date is None:
            raise ValueError(f"Position {position.id} is CLOSED but has no closed_date")

        duration_days = (position.closed_date - position.entry_date).days
        duration_bars = max(1, duration_days)  # At least 1 bar

        # Determine entry phase (Phase C = SPRING/LPS, Phase D = SOS)
        entry_phase = "Phase C" if position.pattern_type in ["SPRING", "LPS"] else "Phase D"

        position_metrics = PositionMetrics(
            position_id=position.id,
            pattern_type=position.pattern_type,
            individual_r=individual_r,
            entry_price=position.entry_price,
            exit_price=position.exit_price,  # type: ignore
            shares=position.shares,
            realized_pnl=position.realized_pnl,
            win_loss_status=win_loss_status,
            duration_bars=duration_bars,
            entry_date=position.entry_date,
            exit_date=position.closed_date,
            entry_phase=entry_phase,
        )
        position_details.append(position_metrics)

    # Calculate campaign-level aggregations
    total_positions = len(closed_positions)
    winning_positions = sum(1 for p in position_details if p.win_loss_status == WinLossStatus.WIN)
    losing_positions = sum(1 for p in position_details if p.win_loss_status == WinLossStatus.LOSS)

    # Win rate
    win_rate = (
        (Decimal(winning_positions) / Decimal(total_positions) * Decimal("100")).quantize(
            Decimal("0.01")
        )
        if total_positions > 0
        else Decimal("0.00")
    )

    # Total R achieved
    total_r_achieved = sum((p.individual_r for p in position_details), Decimal("0")).quantize(
        Decimal("0.0001")
    )

    # Total return %
    total_realized_pnl = sum(
        (p.realized_pnl for p in closed_positions),
        Decimal("0"),  # type: ignore
    )
    total_return_pct = (
        (total_realized_pnl / initial_capital * Decimal("100")).quantize(Decimal("0.00000001"))
        if initial_capital > Decimal("0")
        else Decimal("0.00000000")
    )

    # Duration in days
    duration_days = (completed_at - started_at).days

    # Weighted average entry price
    total_shares = sum((p.shares for p in closed_positions), Decimal("0"))
    if total_shares > Decimal("0"):
        weighted_avg_entry = (
            sum((p.entry_price * p.shares for p in closed_positions), Decimal("0")) / total_shares
        ).quantize(Decimal("0.00000001"))
    else:
        weighted_avg_entry = Decimal("0.00000000")

    # Weighted average exit price
    if total_shares > Decimal("0"):
        weighted_avg_exit = (
            sum(
                (p.exit_price * p.shares for p in closed_positions),  # type: ignore
                Decimal("0"),
            )
            / total_shares
        ).quantize(Decimal("0.00000001"))
    else:
        weighted_avg_exit = Decimal("0.00000000")

    # Max drawdown
    max_drawdown = calculate_max_drawdown_from_equity_curve(closed_positions, initial_capital)

    # Comparison metrics (expected vs actual)
    target_achievement_pct = None
    expected_r = None
    if (
        jump_target is not None
        and actual_high_reached is not None
        and weighted_avg_entry > Decimal("0")
    ):
        target_range = jump_target - weighted_avg_entry
        if target_range > Decimal("0"):
            actual_range = actual_high_reached - weighted_avg_entry
            target_achievement_pct = (actual_range / target_range * Decimal("100")).quantize(
                Decimal("0.01")
            )

            # Expected R based on Jump target
            avg_risk = weighted_avg_entry - sum(
                (p.stop_loss for p in closed_positions), Decimal("0")
            ) / Decimal(total_positions)
            if avg_risk > Decimal("0"):
                expected_r = (target_range / avg_risk).quantize(Decimal("0.0001"))

    # Phase-specific metrics (AC #11)
    phase_c_positions_list = [p for p in position_details if p.entry_phase == "Phase C"]
    phase_d_positions_list = [p for p in position_details if p.entry_phase == "Phase D"]

    phase_c_positions = len(phase_c_positions_list)
    phase_d_positions = len(phase_d_positions_list)

    # Phase C average R
    phase_c_avg_r = None
    if phase_c_positions > 0:
        phase_c_avg_r = (
            sum((p.individual_r for p in phase_c_positions_list), Decimal("0"))
            / Decimal(phase_c_positions)
        ).quantize(Decimal("0.0001"))

    # Phase D average R
    phase_d_avg_r = None
    if phase_d_positions > 0:
        phase_d_avg_r = (
            sum((p.individual_r for p in phase_d_positions_list), Decimal("0"))
            / Decimal(phase_d_positions)
        ).quantize(Decimal("0.0001"))

    # Phase C win rate
    phase_c_win_rate = None
    if phase_c_positions > 0:
        phase_c_wins = sum(
            1 for p in phase_c_positions_list if p.win_loss_status == WinLossStatus.WIN
        )
        phase_c_win_rate = (
            Decimal(phase_c_wins) / Decimal(phase_c_positions) * Decimal("100")
        ).quantize(Decimal("0.01"))

    # Phase D win rate
    phase_d_win_rate = None
    if phase_d_positions > 0:
        phase_d_wins = sum(
            1 for p in phase_d_positions_list if p.win_loss_status == WinLossStatus.WIN
        )
        phase_d_win_rate = (
            Decimal(phase_d_wins) / Decimal(phase_d_positions) * Decimal("100")
        ).quantize(Decimal("0.01"))

    # Check if campaign exceeded 5% risk limit (FR18) and log warning
    # Calculate total risk as sum of (entry_price - stop_loss) * shares for all positions
    total_campaign_risk_dollars = sum(
        ((p.entry_price - p.stop_loss) * p.shares for p in closed_positions),
        Decimal("0"),
    )
    total_campaign_risk_pct = (
        total_campaign_risk_dollars / initial_capital * Decimal("100")
    ).quantize(Decimal("0.01"))

    if total_campaign_risk_pct > MAX_CAMPAIGN_RISK_PCT:
        logger.warning(
            f"Campaign {campaign_id} ({symbol}) exceeded maximum risk limit. "
            f"Campaign risk: {total_campaign_risk_pct}% (limit: {MAX_CAMPAIGN_RISK_PCT}%). "
            f"Total risk: ${total_campaign_risk_dollars}, Initial capital: ${initial_capital}. "
            f"This violates FR18 risk management policy. "
            f"Positions: {total_positions} ({', '.join(p.pattern_type for p in closed_positions)})"
        )

    return CampaignMetrics(
        campaign_id=campaign_id,
        symbol=symbol,
        total_return_pct=total_return_pct,
        total_r_achieved=total_r_achieved,
        duration_days=duration_days,
        max_drawdown=max_drawdown,
        total_positions=total_positions,
        winning_positions=winning_positions,
        losing_positions=losing_positions,
        win_rate=win_rate,
        average_entry_price=weighted_avg_entry,
        average_exit_price=weighted_avg_exit,
        expected_jump_target=jump_target,
        actual_high_reached=actual_high_reached,
        target_achievement_pct=target_achievement_pct,
        expected_r=expected_r,
        actual_r_achieved=total_r_achieved,  # Same as total_r_achieved
        phase_c_avg_r=phase_c_avg_r,
        phase_d_avg_r=phase_d_avg_r,
        phase_c_positions=phase_c_positions,
        phase_d_positions=phase_d_positions,
        phase_c_win_rate=phase_c_win_rate,
        phase_d_win_rate=phase_d_win_rate,
        position_details=position_details,
        calculation_timestamp=datetime.now(UTC),
        completed_at=completed_at,
    )


def calculate_max_drawdown_from_equity_curve(
    positions: list[Position], initial_capital: Decimal
) -> Decimal:
    """
    Calculate maximum drawdown percentage from equity curve.

    Builds an equity curve from positions in chronological order and
    calculates the maximum drawdown percentage encountered.

    Algorithm:
    ----------
    1. Build equity curve from positions ordered by closed_date
    2. Track running maximum equity
    3. At each point, calculate drawdown = (current_equity - running_max) / running_max
    4. Return the largest negative drawdown percentage

    Parameters:
    -----------
    positions : list[Position]
        List of closed positions (must have exit_date and realized_pnl)
    initial_capital : Decimal
        Starting capital for equity curve

    Returns:
    --------
    Decimal
        Maximum drawdown percentage (positive value, e.g., 8.33 for 8.33% drawdown)

    Example:
    --------
    >>> from decimal import Decimal
    >>> max_dd = calculate_max_drawdown_from_equity_curve(
    ...     positions=[pos1, pos2, pos3],
    ...     initial_capital=Decimal("10000.00")
    ... )
    >>> # Equity curve: [10000, 11000, 10500, 12000, 11500]
    >>> # Max DD = (11000 - 10500) / 11000 = 4.55%
    """
    if not positions:
        return Decimal("0.00000000")

    # Sort positions by closed_date
    sorted_positions = sorted(
        positions,
        key=lambda p: p.closed_date if p.closed_date else datetime.min.replace(tzinfo=UTC),
    )

    # Build equity curve
    equity = initial_capital
    running_max_equity = initial_capital
    max_drawdown_pct = Decimal("0.00000000")

    for position in sorted_positions:
        # Add realized P&L to equity
        if position.realized_pnl is not None:
            equity += position.realized_pnl

        # Update running max
        if equity > running_max_equity:
            running_max_equity = equity

        # Calculate current drawdown
        if running_max_equity > Decimal("0"):
            current_drawdown_pct = (
                (running_max_equity - equity) / running_max_equity * Decimal("100")
            ).quantize(Decimal("0.00000001"))

            # Update max drawdown
            if current_drawdown_pct > max_drawdown_pct:
                max_drawdown_pct = current_drawdown_pct

    return max_drawdown_pct


def generate_pnl_curve(
    campaign_id: UUID, positions: list[Position], initial_capital: Decimal
) -> PnLCurve:
    """
    Generate P&L curve data for campaign visualization.

    Creates time-series data of cumulative P&L and drawdown for rendering
    equity curves and performance charts.

    Parameters:
    -----------
    campaign_id : UUID
        Campaign identifier
    positions : list[Position]
        List of closed positions ordered chronologically
    initial_capital : Decimal
        Starting capital for P&L calculations

    Returns:
    --------
    PnLCurve
        Time-series P&L data with drawdown overlay

    Example:
    --------
    >>> pnl_curve = generate_pnl_curve(
    ...     campaign_id=uuid4(),
    ...     positions=[pos1, pos2, pos3],
    ...     initial_capital=Decimal("10000.00")
    ... )
    """
    if not positions:
        return PnLCurve(campaign_id=campaign_id, data_points=[], max_drawdown_point=None)

    # Sort positions by closed_date
    sorted_positions = sorted(
        positions,
        key=lambda p: p.closed_date if p.closed_date else datetime.min.replace(tzinfo=UTC),
    )

    # Build P&L curve
    data_points: list[PnLPoint] = []
    cumulative_pnl = Decimal("0.00000000")
    running_max_equity = initial_capital
    max_drawdown_pct = Decimal("0.00000000")
    max_drawdown_point: PnLPoint | None = None

    for position in sorted_positions:
        if position.realized_pnl is None or position.closed_date is None:
            continue

        # Update cumulative P&L
        cumulative_pnl += position.realized_pnl

        # Calculate cumulative return %
        current_equity = initial_capital + cumulative_pnl
        cumulative_return_pct = (
            (cumulative_pnl / initial_capital * Decimal("100")).quantize(Decimal("0.00000001"))
            if initial_capital > Decimal("0")
            else Decimal("0.00000000")
        )

        # Update running max equity
        if current_equity > running_max_equity:
            running_max_equity = current_equity

        # Calculate current drawdown
        drawdown_pct = Decimal("0.00000000")
        if running_max_equity > Decimal("0"):
            drawdown_pct = (
                (running_max_equity - current_equity) / running_max_equity * Decimal("100")
            ).quantize(Decimal("0.00000001"))

        # Create P&L point
        pnl_point = PnLPoint(
            timestamp=position.closed_date,
            cumulative_pnl=cumulative_pnl.quantize(Decimal("0.00000001")),
            cumulative_return_pct=cumulative_return_pct,
            drawdown_pct=drawdown_pct,
        )
        data_points.append(pnl_point)

        # Track max drawdown point
        if drawdown_pct > max_drawdown_pct:
            max_drawdown_pct = drawdown_pct
            max_drawdown_point = pnl_point

    return PnLCurve(
        campaign_id=campaign_id, data_points=data_points, max_drawdown_point=max_drawdown_point
    )


def get_aggregated_performance(
    campaigns_metrics: list[CampaignMetrics], filters: MetricsFilter | None = None
) -> AggregatedMetrics:
    """
    Calculate aggregated performance statistics across all completed campaigns.

    Provides system-wide performance analytics aggregated from all completed
    campaigns, with optional filtering.

    Parameters:
    -----------
    campaigns_metrics : list[CampaignMetrics]
        List of campaign metrics to aggregate
    filters : MetricsFilter | None
        Optional filters (for metadata tracking only, filtering should be done before calling)

    Returns:
    --------
    AggregatedMetrics
        Aggregated performance statistics

    Example:
    --------
    >>> aggregated = get_aggregated_performance(
    ...     campaigns_metrics=[metrics1, metrics2, metrics3],
    ...     filters=MetricsFilter(symbol="AAPL")
    ... )
    """
    if not campaigns_metrics:
        # Return empty aggregated metrics
        return AggregatedMetrics(
            total_campaigns_completed=0,
            overall_win_rate=Decimal("0.00"),
            average_campaign_return_pct=Decimal("0.00000000"),
            average_r_achieved_per_campaign=Decimal("0.0000"),
            best_campaign=None,
            worst_campaign=None,
            median_duration_days=None,
            average_max_drawdown=Decimal("0.00000000"),
            calculation_timestamp=datetime.now(UTC),
            filter_criteria=filters.model_dump() if filters else {},
        )

    total_campaigns = len(campaigns_metrics)

    # Overall win rate (campaigns with positive return)
    winning_campaigns = sum(1 for c in campaigns_metrics if c.total_return_pct > Decimal("0"))
    overall_win_rate = (
        (Decimal(winning_campaigns) / Decimal(total_campaigns) * Decimal("100")).quantize(
            Decimal("0.01")
        )
        if total_campaigns > 0
        else Decimal("0.00")
    )

    # Average campaign return %
    total_return = sum((c.total_return_pct for c in campaigns_metrics), Decimal("0"))
    average_campaign_return_pct = (total_return / Decimal(total_campaigns)).quantize(
        Decimal("0.00000001")
    )

    # Average R achieved per campaign
    total_r = sum((c.total_r_achieved for c in campaigns_metrics), Decimal("0"))
    average_r_achieved_per_campaign = (total_r / Decimal(total_campaigns)).quantize(
        Decimal("0.0001")
    )

    # Best campaign
    best_campaign_metrics = max(campaigns_metrics, key=lambda c: c.total_return_pct)
    best_campaign = {
        "campaign_id": str(best_campaign_metrics.campaign_id),
        "return_pct": str(best_campaign_metrics.total_return_pct),
    }

    # Worst campaign
    worst_campaign_metrics = min(campaigns_metrics, key=lambda c: c.total_return_pct)
    worst_campaign = {
        "campaign_id": str(worst_campaign_metrics.campaign_id),
        "return_pct": str(worst_campaign_metrics.total_return_pct),
    }

    # Median duration
    durations = [c.duration_days for c in campaigns_metrics]
    median_duration_days = int(median(durations)) if durations else None

    # Average max drawdown
    total_drawdown = sum((c.max_drawdown for c in campaigns_metrics), Decimal("0"))
    average_max_drawdown = (total_drawdown / Decimal(total_campaigns)).quantize(
        Decimal("0.00000001")
    )

    return AggregatedMetrics(
        total_campaigns_completed=total_campaigns,
        overall_win_rate=overall_win_rate,
        average_campaign_return_pct=average_campaign_return_pct,
        average_r_achieved_per_campaign=average_r_achieved_per_campaign,
        best_campaign=best_campaign,
        worst_campaign=worst_campaign,
        median_duration_days=median_duration_days,
        average_max_drawdown=average_max_drawdown,
        calculation_timestamp=datetime.now(UTC),
        filter_criteria=filters.model_dump() if filters else {},
    )
