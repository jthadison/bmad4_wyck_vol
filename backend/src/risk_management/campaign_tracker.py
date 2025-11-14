"""
Campaign Risk Tracking - Wyckoff BMAD Allocation Enforcement

Purpose:
--------
Implements campaign-level risk tracking and validation to enforce the 5%
maximum campaign risk limit (FR18) with BMAD allocation percentages for
Wyckoff entry sequences (Spring → SOS → LPS).

Core Functions:
---------------
1. calculate_campaign_risk: Calculate total risk for a campaign
2. validate_campaign_risk_capacity: Validate new position won't exceed 5% limit
3. validate_bmad_allocation: Enforce pattern-specific allocation limits
4. check_campaign_proximity_warning: Warn when approaching 80% of limit
5. build_campaign_risk_report: Generate comprehensive CampaignRisk report
6. check_campaign_completion: Detect when all positions closed

BMAD Allocation (AC 4):
-----------------------
Authentic Wyckoff 3-Entry Model - Volume-Aligned & Risk-Optimized:
- Spring: 40% of campaign budget (2.00% max) - HIGHEST allocation
- SOS: 35% of campaign budget (1.75% max) - Primary confirmation entry
- LPS: 25% of campaign budget (1.25% max) - Secondary entry

Campaign Flow:
--------------
1. Spring occurs (optional test position taken - 40% allocation)
2. ST confirms Spring on low volume (NO position - observation only)
3. SOS breakout (PRIMARY CONFIRMATION ENTRY - 35% allocation)
4. LPS pullback (SECONDARY ENTRY - optional add-on - 25% allocation)

Note: Secondary Test (ST) is a confirmation event, NOT an entry pattern.

Integration:
------------
- Story 7.1: Uses pattern risk percentages
- Story 7.2: Uses position_risk_pct from PositionSizing
- Story 7.3: Campaign risk is subset of portfolio heat
- Story 7.4: Core implementation

Author: Story 7.4
"""

from decimal import Decimal
from typing import Optional
from uuid import UUID

import structlog

from src.models.campaign import (
    CAMPAIGN_LPS_ALLOCATION,
    CAMPAIGN_SOS_ALLOCATION,
    CAMPAIGN_SPRING_ALLOCATION,
    CAMPAIGN_WARNING_THRESHOLD_PCT,
    MAX_CAMPAIGN_RISK_PCT,
    MAX_LPS_RISK,
    MAX_SOS_RISK,
    MAX_SPRING_RISK,
    CampaignEntry,
    CampaignRisk,
)
from src.models.portfolio import Position

logger = structlog.get_logger()


def calculate_campaign_risk(campaign_id: UUID, open_positions: list[Position]) -> Decimal:
    """
    Calculate total risk for a campaign (AC 1, 5).

    Sums position_risk_pct for all positions with matching campaign_id
    and status="OPEN". Uses Decimal arithmetic with 8 decimal places
    for precision (NFR20 compliance).

    Parameters:
    -----------
    campaign_id : UUID
        Campaign identifier to filter positions
    open_positions : list[Position]
        All open positions in portfolio

    Returns:
    --------
    Decimal
        Total campaign risk as percentage (e.g., Decimal("3.5") for 3.5%)

    Example:
    --------
    >>> from decimal import Decimal
    >>> from uuid import uuid4
    >>> campaign_id = uuid4()
    >>> positions = [
    ...     Position(symbol="AAPL", position_risk_pct=Decimal("2.0"), status="OPEN", campaign_id=campaign_id),
    ...     Position(symbol="MSFT", position_risk_pct=Decimal("1.5"), status="OPEN", campaign_id=campaign_id),
    ... ]
    >>> risk = calculate_campaign_risk(campaign_id, positions)
    >>> print(risk)  # Decimal("3.5")
    """
    if campaign_id is None:
        logger.debug("calculate_campaign_risk: campaign_id is None, returning 0")
        return Decimal("0")

    # Filter positions by campaign_id and status="OPEN"
    campaign_positions = [
        pos
        for pos in open_positions
        if hasattr(pos, "campaign_id") and pos.campaign_id == campaign_id and pos.status == "OPEN"
    ]

    # Calculate sum of position_risk_pct
    total_risk = sum((pos.position_risk_pct for pos in campaign_positions), start=Decimal("0"))

    logger.info(
        "campaign_risk_calculated",
        campaign_id=str(campaign_id),
        total_risk=str(total_risk),
        position_count=len(campaign_positions),
    )

    return total_risk


def validate_campaign_risk_capacity(
    campaign_id: UUID, current_risk: Decimal, new_position_risk: Decimal
) -> tuple[bool, Optional[str]]:
    """
    Validate new position won't exceed 5% campaign risk limit (AC 2, 6).

    Parameters:
    -----------
    campaign_id : UUID
        Campaign identifier (None = no campaign constraint)
    current_risk : Decimal
        Current campaign risk percentage
    new_position_risk : Decimal
        Risk percentage for new position

    Returns:
    --------
    tuple[bool, Optional[str]]
        (True, None) if validation passes
        (False, error_message) if validation fails

    Example:
    --------
    >>> from decimal import Decimal
    >>> from uuid import uuid4
    >>> valid, msg = validate_campaign_risk_capacity(
    ...     uuid4(), Decimal("4.0"), Decimal("0.5")
    ... )
    >>> print(valid)  # True
    >>> valid, msg = validate_campaign_risk_capacity(
    ...     uuid4(), Decimal("4.8"), Decimal("0.3")
    ... )
    >>> print(valid)  # False
    """
    # Edge case: if campaign_id is None, allow position (no campaign constraint)
    if campaign_id is None:
        logger.debug("validate_campaign_risk_capacity: campaign_id is None, allowing position")
        return (True, None)

    # Calculate projected risk
    projected_risk = current_risk + new_position_risk

    # Check if projected risk exceeds 5% limit
    if projected_risk > MAX_CAMPAIGN_RISK_PCT:
        error_msg = (
            f"Campaign risk limit exceeded (5%): current {current_risk}%, "
            f"new position {new_position_risk}%, projected {projected_risk}%"
        )
        logger.error(
            "campaign_risk_limit_exceeded",
            campaign_id=str(campaign_id),
            current_risk=str(current_risk),
            new_position_risk=str(new_position_risk),
            projected_risk=str(projected_risk),
            limit=str(MAX_CAMPAIGN_RISK_PCT),
        )
        return (False, error_msg)

    logger.debug(
        "campaign_risk_capacity_validated",
        campaign_id=str(campaign_id),
        current_risk=str(current_risk),
        new_position_risk=str(new_position_risk),
        projected_risk=str(projected_risk),
    )

    return (True, None)


def validate_bmad_allocation(
    campaign_positions: list[Position],
    new_entry_pattern: str,
    new_entry_risk: Decimal,
) -> tuple[bool, Optional[str]]:
    """
    Validate BMAD allocation limits for pattern type (AC 4, 11, 12).

    BMAD Allocation:
    ----------------
    - Spring: 40% of 5% = 2.00% max (HIGHEST - climactic volume + tightest stops)
    - SOS: 35% of 5% = 1.75% max (Primary confirmation entry)
    - LPS: 25% of 5% = 1.25% max (Secondary entry, optional)
    - ST: NOT A VALID ENTRY PATTERN (confirmation event only)

    Parameters:
    -----------
    campaign_positions : list[Position]
        Existing positions in campaign
    new_entry_pattern : str
        Pattern type for new position (SPRING | SOS | LPS)
    new_entry_risk : Decimal
        Risk percentage for new position

    Returns:
    --------
    tuple[bool, Optional[str]]
        (True, None) if allocation is within bounds
        (False, error_message) if allocation would be exceeded

    Example:
    --------
    >>> from decimal import Decimal
    >>> positions = [
    ...     Position(symbol="AAPL", position_risk_pct=Decimal("1.5"), pattern_type="SPRING", status="OPEN"),
    ... ]
    >>> valid, msg = validate_bmad_allocation(positions, "SPRING", Decimal("0.6"))
    >>> print(valid)  # False (1.5 + 0.6 = 2.1 > 2.0 max)
    """
    # Reject ST pattern immediately (AC 4)
    if new_entry_pattern == "ST":
        error_msg = (
            "ST (Secondary Test) is a confirmation event, not an entry pattern. "
            "Valid entry patterns: SPRING, SOS, LPS"
        )
        logger.error(
            "bmad_allocation_st_rejected",
            pattern_type=new_entry_pattern,
        )
        return (False, error_msg)

    # Define pattern-specific limits
    pattern_limits = {
        "SPRING": MAX_SPRING_RISK,  # 2.00%
        "SOS": MAX_SOS_RISK,  # 1.75%
        "LPS": MAX_LPS_RISK,  # 1.25%
    }

    pattern_allocations = {
        "SPRING": CAMPAIGN_SPRING_ALLOCATION,  # 40%
        "SOS": CAMPAIGN_SOS_ALLOCATION,  # 35%
        "LPS": CAMPAIGN_LPS_ALLOCATION,  # 25%
    }

    if new_entry_pattern not in pattern_limits:
        error_msg = f"Invalid pattern type: {new_entry_pattern}. Valid: SPRING, SOS, LPS"
        logger.error(
            "bmad_allocation_invalid_pattern",
            pattern_type=new_entry_pattern,
        )
        return (False, error_msg)

    # Sum existing risk for the same pattern type
    existing_pattern_risk = sum(
        (
            pos.position_risk_pct
            for pos in campaign_positions
            if hasattr(pos, "pattern_type")
            and pos.pattern_type == new_entry_pattern
            and pos.status == "OPEN"
        ),
        start=Decimal("0"),
    )

    # Calculate projected pattern risk
    projected_pattern_risk = existing_pattern_risk + new_entry_risk
    max_pattern_risk = pattern_limits[new_entry_pattern]

    # Check if adding new entry would exceed pattern allocation
    if projected_pattern_risk > max_pattern_risk:
        allocation_pct = pattern_allocations[new_entry_pattern] * Decimal("100")
        error_msg = (
            f"{new_entry_pattern} allocation exceeded: {projected_pattern_risk}% "
            f"exceeds max {max_pattern_risk}% ({allocation_pct}% of 5% campaign budget)"
        )
        logger.error(
            "bmad_allocation_exceeded",
            pattern_type=new_entry_pattern,
            existing_risk=str(existing_pattern_risk),
            new_position_risk=str(new_entry_risk),
            projected_risk=str(projected_pattern_risk),
            max_allocation=str(max_pattern_risk),
            allocation_percentage=str(allocation_pct),
        )
        return (False, error_msg)

    logger.debug(
        "bmad_allocation_validated",
        pattern_type=new_entry_pattern,
        existing_risk=str(existing_pattern_risk),
        new_position_risk=str(new_entry_risk),
        projected_risk=str(projected_pattern_risk),
        max_allocation=str(max_pattern_risk),
    )

    return (True, None)


def check_campaign_proximity_warning(total_risk: Decimal) -> Optional[str]:
    """
    Check if campaign risk is approaching 80% of 5% limit (AC 10).

    Parameters:
    -----------
    total_risk : Decimal
        Current total campaign risk percentage

    Returns:
    --------
    Optional[str]
        Warning message if total_risk >= 4.0% (80% of 5% limit)
        None if below warning threshold

    Example:
    --------
    >>> from decimal import Decimal
    >>> warning = check_campaign_proximity_warning(Decimal("4.2"))
    >>> print(warning)  # "Campaign risk at 4.2% (80% of 5% limit)"
    >>> warning = check_campaign_proximity_warning(Decimal("3.5"))
    >>> print(warning)  # None
    """
    if total_risk >= CAMPAIGN_WARNING_THRESHOLD_PCT:
        warning_msg = f"Campaign risk at {total_risk}% (80% of 5% limit)"
        logger.warning(
            "campaign_risk_proximity_warning",
            total_risk=str(total_risk),
            threshold=str(CAMPAIGN_WARNING_THRESHOLD_PCT),
            limit=str(MAX_CAMPAIGN_RISK_PCT),
        )
        return warning_msg

    return None


def build_campaign_risk_report(campaign_id: UUID, open_positions: list[Position]) -> CampaignRisk:
    """
    Generate comprehensive CampaignRisk report (AC 1, 4, 7).

    Builds a complete CampaignRisk dataclass with:
    - total_risk: Sum of all position risks in campaign
    - available_capacity: Remaining capacity before 5% limit
    - position_count: Number of open positions
    - entry_breakdown: Details for each position (pattern type, risk, allocation)

    Parameters:
    -----------
    campaign_id : UUID
        Campaign identifier
    open_positions : list[Position]
        All open positions in portfolio

    Returns:
    --------
    CampaignRisk
        Comprehensive campaign risk report

    Example:
    --------
    >>> from decimal import Decimal
    >>> from uuid import uuid4
    >>> campaign_id = uuid4()
    >>> positions = [
    ...     Position(
    ...         symbol="AAPL",
    ...         position_risk_pct=Decimal("2.0"),
    ...         pattern_type="SPRING",
    ...         status="OPEN",
    ...         campaign_id=campaign_id,
    ...     ),
    ... ]
    >>> report = build_campaign_risk_report(campaign_id, positions)
    >>> print(report.total_risk)  # Decimal("2.0")
    >>> print(report.available_capacity)  # Decimal("3.0")
    """
    # Calculate total_risk
    total_risk = calculate_campaign_risk(campaign_id, open_positions)

    # Calculate available_capacity
    available_capacity = MAX_CAMPAIGN_RISK_PCT - total_risk

    # Filter campaign positions
    campaign_positions = [
        pos
        for pos in open_positions
        if hasattr(pos, "campaign_id") and pos.campaign_id == campaign_id and pos.status == "OPEN"
    ]

    # Set position_count
    position_count = len(campaign_positions)

    # Build entry_breakdown
    entry_breakdown = {}
    pattern_allocation_map = {
        "SPRING": CAMPAIGN_SPRING_ALLOCATION * Decimal("100"),  # 40.0%
        "SOS": CAMPAIGN_SOS_ALLOCATION * Decimal("100"),  # 35.0%
        "LPS": CAMPAIGN_LPS_ALLOCATION * Decimal("100"),  # 25.0%
    }

    for pos in campaign_positions:
        pattern_type = getattr(pos, "pattern_type", None)

        # Skip positions without pattern_type (invalid for campaign tracking)
        if pattern_type is None or pattern_type not in pattern_allocation_map:
            logger.warning(
                "position_missing_pattern_type",
                symbol=pos.symbol,
                pattern_type=pattern_type,
                message="Skipping position without valid pattern_type in campaign report",
            )
            continue

        allocation_pct = pattern_allocation_map[pattern_type]

        entry = CampaignEntry(
            pattern_type=pattern_type,
            position_risk_pct=pos.position_risk_pct,
            allocation_percentage=allocation_pct,
            symbol=pos.symbol,
            status=pos.status,
        )

        # Use symbol as entry_id (could use position_id if available)
        entry_breakdown[pos.symbol] = entry

    # Create CampaignRisk instance
    campaign_risk = CampaignRisk(
        campaign_id=campaign_id,
        total_risk=total_risk,
        available_capacity=available_capacity,
        position_count=position_count,
        entry_breakdown=entry_breakdown,
    )

    logger.info(
        "campaign_risk_report_built",
        campaign_id=str(campaign_id),
        total_risk=str(total_risk),
        available_capacity=str(available_capacity),
        position_count=position_count,
    )

    return campaign_risk


def check_campaign_completion(campaign_id: UUID, positions: list[Position]) -> bool:
    """
    Check if campaign is complete (all positions closed) (AC 7).

    A campaign is complete when all positions have status in:
    ["CLOSED", "STOPPED", "TARGET_HIT", "EXPIRED"]

    When complete, campaign.current_risk should be 0%.

    Parameters:
    -----------
    campaign_id : UUID
        Campaign identifier
    positions : list[Position]
        All positions in portfolio (open and closed)

    Returns:
    --------
    bool
        True if all positions closed (campaign complete)
        False if any positions still open

    Example:
    --------
    >>> from uuid import uuid4
    >>> campaign_id = uuid4()
    >>> positions = [
    ...     Position(symbol="AAPL", status="CLOSED", campaign_id=campaign_id),
    ...     Position(symbol="MSFT", status="STOPPED", campaign_id=campaign_id),
    ... ]
    >>> complete = check_campaign_completion(campaign_id, positions)
    >>> print(complete)  # True
    """
    # Filter positions by campaign_id
    campaign_positions = [
        pos for pos in positions if hasattr(pos, "campaign_id") and pos.campaign_id == campaign_id
    ]

    # Empty campaign is considered complete
    if not campaign_positions:
        logger.debug(
            "campaign_completion_check_empty",
            campaign_id=str(campaign_id),
        )
        return True

    # Check if all positions have closed status
    closed_statuses = {"CLOSED", "STOPPED", "TARGET_HIT", "EXPIRED"}
    all_closed = all(pos.status in closed_statuses for pos in campaign_positions)

    if all_closed:
        logger.info(
            "campaign_completed",
            campaign_id=str(campaign_id),
            positions_closed=len(campaign_positions),
        )
    else:
        open_count = sum(1 for pos in campaign_positions if pos.status == "OPEN")
        logger.debug(
            "campaign_incomplete",
            campaign_id=str(campaign_id),
            open_positions=open_count,
            total_positions=len(campaign_positions),
        )

    return all_closed
