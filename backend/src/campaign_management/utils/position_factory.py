"""
Position Factory Utility (Story 18.5)

Provides centralized position creation from trade signals.
Extracted from duplicate implementation in service.py.

This module creates CampaignPosition objects from TradeSignal objects,
using allocation information from AllocationPlan when available.
"""

from decimal import Decimal

from src.models.allocation import AllocationPlan
from src.models.campaign_lifecycle import CampaignPosition
from src.models.signal import TradeSignal


def create_position_from_signal(
    signal: TradeSignal,
    allocation_plan: AllocationPlan,
) -> CampaignPosition:
    """
    Create CampaignPosition from TradeSignal with AllocationPlan.

    Maps signal fields to position fields using BMAD allocation from AllocationPlan.
    Uses actual_risk_pct from allocation plan for precise allocation tracking.

    Args:
        signal: TradeSignal to convert to position
        allocation_plan: Approved allocation plan with BMAD percentages

    Returns:
        CampaignPosition ready to add to campaign with correct allocation

    Example:
        >>> position = create_position_from_signal(signal, allocation_plan)
        >>> assert position.signal_id == signal.id
        >>> assert position.allocation_percent == allocation_plan.actual_risk_pct
    """
    # Use actual_risk_pct from allocation plan
    allocation_percent = allocation_plan.actual_risk_pct

    return CampaignPosition(
        signal_id=signal.id,
        pattern_type=signal.pattern_type,  # type: ignore
        entry_date=signal.timestamp,
        entry_price=signal.entry_price,
        shares=signal.position_size,
        stop_loss=signal.stop_loss,
        target_price=signal.target_levels.primary_target,
        current_price=signal.entry_price,  # Initially same as entry
        current_pnl=Decimal("0.00"),  # Not yet filled
        status="OPEN",
        allocation_percent=allocation_percent,
        risk_amount=signal.risk_amount,
    )
