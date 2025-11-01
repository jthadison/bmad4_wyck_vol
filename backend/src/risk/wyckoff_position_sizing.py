"""
Wyckoff Position Size Calculator with risk adjustments.

This module implements Rachel's risk management requirements for Story 4.7:
- Base position size calculation (account risk / trade risk)
- Wyckoff-specific risk adjustments (Phase B duration, Phase E exhaustion, invalidations)
- Complete position size with rationale

Author: Rachel (Risk & Position Manager)
Story 4.7: PhaseDetector Module Integration - Task 37
"""

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from src.models.phase_classification import WyckoffPhase
from src.models.phase_info import PhaseESubState

if TYPE_CHECKING:
    from src.models.phase_info import PhaseInfo


class WyckoffPositionSize(BaseModel):
    """
    Position size calculator with Wyckoff-specific adjustments.

    Base Calculation:
        Risk amount = account_size * risk_per_trade
        Position size = risk_amount / (entry_price - stop_price)

    Wyckoff Adjustments:
        1. Phase B short: multiply by phase_b_risk_profile.risk_adjustment_factor
        2. Phase E exhaustion: multiply by 0.25 (only 25% position)
        3. Recent invalidation: multiply by 0.75 (reduce 25%)

    Example:

        Account: $100,000
        Risk per trade: 2% ($2,000)
        Entry: $50.00
        Stop: $48.00 (risk = $2.00/share)
        Base size: $2,000 / $2.00 = 1,000 shares

        Adjustments:
        - Phase B short (0.75x): 750 shares
        - Recent invalidation (0.75x): 562 shares
        Final size: 562 shares ($28,125 position value)

    Attributes:
        account_size: Total account value
        risk_per_trade: Risk percentage (0.02 = 2%)
        entry_price: Entry price per share
        stop_price: Stop loss price per share
        phase: Current Wyckoff phase
        sub_phase: Current sub-phase (if any)
        base_position_size: Base calculation (shares)
        risk_adjusted_size: After Wyckoff adjustments (shares)
        final_position_size: Final position (shares)
        risk_reduction_factors: Dict of adjustments applied

    Usage:
        phase_info = detector.detect_phase(range, bars, volume_analysis)
        position_size = calculate_wyckoff_position_size(
            account_size=100000,
            risk_per_trade=0.02,
            entry_price=50.00,
            stop_price=48.00,
            phase_info=phase_info
        )
        print(f"Position: {position_size.final_position_size} shares")
        print(f"Adjustments: {position_size.risk_reduction_factors}")
    """

    account_size: float = Field(..., gt=0)
    risk_per_trade: float = Field(..., gt=0, le=1.0)  # 0.02 = 2%
    entry_price: float = Field(..., gt=0)
    stop_price: float = Field(..., gt=0)
    phase: WyckoffPhase | None
    sub_phase: str | None

    # Calculated fields
    base_position_size: float = Field(..., ge=0)
    risk_adjusted_size: float = Field(..., ge=0)
    final_position_size: float = Field(..., ge=0)
    risk_reduction_factors: dict = Field(default_factory=dict)


def calculate_wyckoff_position_size(
    account_size: float,
    risk_per_trade: float,
    entry_price: float,
    stop_price: float,
    phase_info: "PhaseInfo",
) -> WyckoffPositionSize:
    """
    Calculate position size with Wyckoff risk adjustments.

    Base Calculation:
        - Risk amount = account_size * risk_per_trade
        - Risk per share = entry_price - stop_price
        - Base position = risk_amount / risk_per_share

    Wyckoff Adjustments (applied sequentially):
        1. Phase B duration: If short Phase B, reduce by phase_b_risk_profile.risk_adjustment_factor
        2. Phase E exhaustion: If exhaustion detected, reduce to 25%
        3. Recent invalidation: If invalidation in last 10 bars, reduce by 25%

    Args:
        account_size: Total account value ($)
        risk_per_trade: Risk per trade (0.02 = 2%)
        entry_price: Entry price per share
        stop_price: Stop loss price per share
        phase_info: PhaseInfo from PhaseDetector

    Returns:
        WyckoffPositionSize with all adjustments

    Raises:
        ValueError: If stop_price >= entry_price (invalid risk)

    Example:

        # Normal Phase C trade
        position = calculate_wyckoff_position_size(
            account_size=100000,
            risk_per_trade=0.02,
            entry_price=50.00,
            stop_price=48.50,
            phase_info=phase_info
        )
        # position.final_position_size = 1333 shares (normal)

        # Phase B short duration trade
        position = calculate_wyckoff_position_size(
            account_size=100000,
            risk_per_trade=0.02,
            entry_price=50.00,
            stop_price=48.50,
            phase_info=phase_info_short_b
        )
        # position.final_position_size = 1000 shares (reduced to 75%)

        # Phase E exhaustion trade
        position = calculate_wyckoff_position_size(
            account_size=100000,
            risk_per_trade=0.02,
            entry_price=50.00,
            stop_price=48.50,
            phase_info=phase_info_exhaustion
        )
        # position.final_position_size = 333 shares (reduced to 25%)

    Integration:
        - Phase B: Uses phase_b_risk_profile.risk_adjustment_factor (0.5-1.0)
        - Phase E: Uses sub_phase to detect EXHAUSTION
        - Invalidations: Uses invalidations list from PhaseInfo

    Teaching Point (Rachel):
        "Position sizing isn't just account risk. In Wyckoff, phase context
        matters. Short Phase B means less cause built = smaller effect expected.
        Phase E exhaustion means distribution forming = exit time, not entry."
    """
    # Validate inputs
    if stop_price >= entry_price:
        raise ValueError(
            f"Stop price ({stop_price}) must be below entry price ({entry_price})"
        )

    # Base position size calculation
    risk_amount = account_size * risk_per_trade
    risk_per_share = entry_price - stop_price
    base_size = risk_amount / risk_per_share

    # Apply Wyckoff adjustments
    adjustments: dict = {}
    final_size = base_size

    # Adjustment 1: Phase B duration
    if (
        phase_info.phase == WyckoffPhase.B
        and phase_info.phase_b_risk_profile is not None
    ):
        factor = phase_info.phase_b_risk_profile.risk_adjustment_factor
        final_size *= factor
        adjustments["phase_b_duration"] = factor

    # Adjustment 2: Phase E exhaustion
    if phase_info.sub_phase == PhaseESubState.EXHAUSTION:
        final_size *= 0.25  # Only 25% position in exhaustion
        adjustments["phase_e_exhaustion"] = 0.25

    # Adjustment 3: Recent invalidations (within last 10 bars)
    recent_invalidations = [
        inv
        for inv in phase_info.invalidations
        if inv.bar_index > phase_info.current_bar_index - 10
    ]
    if recent_invalidations:
        final_size *= 0.75  # Reduce 25% after recent invalidation
        adjustments["recent_invalidation"] = 0.75

    return WyckoffPositionSize(
        account_size=account_size,
        risk_per_trade=risk_per_trade,
        entry_price=entry_price,
        stop_price=stop_price,
        phase=phase_info.phase,
        sub_phase=str(phase_info.sub_phase) if phase_info.sub_phase else None,
        base_position_size=base_size,
        risk_adjusted_size=final_size,
        final_position_size=final_size,
        risk_reduction_factors=adjustments,
    )


def get_position_value(position: WyckoffPositionSize) -> float:
    """
    Calculate total position value.

    Args:
        position: WyckoffPositionSize result

    Returns:
        Total position value ($)

    Example:
        value = get_position_value(position)
        # 562 shares * $50.00 = $28,100
    """
    return position.final_position_size * position.entry_price


def get_risk_amount(position: WyckoffPositionSize) -> float:
    """
    Calculate total risk amount.

    Args:
        position: WyckoffPositionSize result

    Returns:
        Total risk ($)

    Example:
        risk = get_risk_amount(position)
        # 562 shares * ($50.00 - $48.00) = $1,124
    """
    return position.final_position_size * (position.entry_price - position.stop_price)


def get_position_summary(position: WyckoffPositionSize) -> str:
    """
    Generate human-readable position summary.

    Args:
        position: WyckoffPositionSize result

    Returns:
        Formatted summary string

    Example:
        summary = get_position_summary(position)
        print(summary)

        Output:
            Position Size Summary:
            Account: $100,000.00
            Risk: 2.00% ($2,000.00)
            Entry: $50.00, Stop: $48.00 (Risk: $2.00/share)

            Base Position: 1,000 shares
            Adjustments:
              - Phase B duration: 0.75x (750 shares)
              - Recent invalidation: 0.75x (562 shares)

            Final Position: 562 shares ($28,100.00)
            Final Risk: $1,124.00 (1.12%)
    """
    position_value = get_position_value(position)
    risk_amount = get_risk_amount(position)
    actual_risk_pct = (risk_amount / position.account_size) * 100

    lines = [
        "Position Size Summary:",
        f"Account: ${position.account_size:,.2f}",
        f"Risk: {position.risk_per_trade * 100:.2f}% "
        f"(${position.account_size * position.risk_per_trade:,.2f})",
        f"Entry: ${position.entry_price:.2f}, Stop: ${position.stop_price:.2f} "
        f"(Risk: ${position.entry_price - position.stop_price:.2f}/share)",
        "",
        f"Base Position: {position.base_position_size:,.0f} shares",
    ]

    if position.risk_reduction_factors:
        lines.append("Adjustments:")
        for factor_name, factor_value in position.risk_reduction_factors.items():
            lines.append(f"  - {factor_name.replace('_', ' ').title()}: {factor_value:.2f}x")

    lines.extend(
        [
            "",
            f"Final Position: {position.final_position_size:,.0f} shares "
            f"(${position_value:,.2f})",
            f"Final Risk: ${risk_amount:,.2f} ({actual_risk_pct:.2f}%)",
        ]
    )

    return "\n".join(lines)
