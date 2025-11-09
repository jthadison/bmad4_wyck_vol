"""
Portfolio Heat Tracking - Wyckoff-Adaptive Risk Management

Purpose:
--------
Implements portfolio-level heat tracking (aggregate risk across all open
positions) with phase-adaptive limits, volume-based multipliers, and campaign
correlation adjustments per Wyckoff methodology (Story 7.3).

Core Functions:
---------------
1. calculate_portfolio_heat: Sum position_risk_pct (AC 1-2)
2. get_phase_adjusted_heat_limit: Phase-based limits (AC 11-12)
3. calculate_volume_risk_multiplier: Volume-based adjustment (AC 13-15)
4. identify_campaign_clusters: Correlation analysis (AC 16-17)
5. calculate_correlation_adjusted_heat: Apply cluster penalties (AC 16)
6. check_campaign_stage_warnings: Context-aware warnings (AC 7 revised)
7. build_portfolio_heat_report: Orchestrator (AC 5)
8. validate_portfolio_heat_capacity: Pre-trade validation (AC 4)

Wyckoff Integration:
--------------------
- Phase-adaptive limits: 8% (A/B), 12% (C/D), 15% (E)
- Volume multipliers: 0.70x (≥30pts), 0.85x (20-30pts), 1.0x (<20pts)
- Correlation penalties: 0.90x (2 pos), 0.85x (3 pos), 0.80x (4+ pos)
- Absolute maximum: 15.0% (never exceeded)

Author: Story 7.3
"""

from collections import defaultdict
from decimal import Decimal

import structlog

from src.models.portfolio import (
    CampaignCluster,
    PortfolioHeat,
    PortfolioWarning,
    Position,
)

logger = structlog.get_logger()


def calculate_portfolio_heat(open_positions: list[Position]) -> Decimal:
    """
    Calculate total portfolio heat as sum of position risk percentages.

    AC 1-2: Simple sum of position_risk_pct across all open positions.
    Uses Decimal arithmetic to prevent floating-point precision errors.

    Args:
        open_positions: List of open Position objects

    Returns:
        Total portfolio heat as percentage (e.g., Decimal("8.5") for 8.5%)

    Example:
    --------
    >>> positions = [
    ...     Position(symbol="AAPL", position_risk_pct=Decimal("2.0"), status="OPEN"),
    ...     Position(symbol="MSFT", position_risk_pct=Decimal("1.5"), status="OPEN"),
    ... ]
    >>> calculate_portfolio_heat(positions)
    Decimal('3.5')
    """
    if not open_positions:
        return Decimal("0.0")

    total_heat = sum(pos.position_risk_pct for pos in open_positions if pos.status == "OPEN")

    logger.debug(
        "portfolio_heat_calculated",
        position_count=len(open_positions),
        total_heat=str(total_heat),
    )

    return total_heat


def get_phase_adjusted_heat_limit(
    positions: list[Position],
) -> tuple[Decimal, str]:
    """
    Calculate phase-adaptive heat limit based on Wyckoff phase distribution.

    Enhancement 1 (AC 11-12): Heat limits adapt to structural confidence
    of the accumulation campaign phase.

    Phase-Adjusted Limits:
    ----------------------
    - Phase A/B majority: 8.0% (conservative - operator testing)
    - Phase C/D majority: 12.0% (building - operator shaking out)
    - Phase E/SOS majority: 15.0% (aggressive - operator ready for markup)
    - Distribution/uncertain: 10.0% (default - standard discipline)

    Args:
        positions: List of open Position objects with wyckoff_phase attribute

    Returns:
        Tuple of (limit: Decimal, basis: str)
        - limit: Phase-adjusted heat limit percentage
        - basis: Explanation string (e.g., "Phase D majority (3/4)")

    Example:
    --------
    >>> positions = [
    ...     Position(symbol="AAPL", wyckoff_phase="D", ...),
    ...     Position(symbol="MSFT", wyckoff_phase="D", ...),
    ...     Position(symbol="GOOGL", wyckoff_phase="C", ...),
    ... ]
    >>> get_phase_adjusted_heat_limit(positions)
    (Decimal('12.0'), 'Phase D majority (2/3)')
    """
    if not positions:
        return Decimal("10.0"), "no positions (default)"

    # Calculate phase distribution
    phase_counts = defaultdict(int)
    for pos in positions:
        phase = pos.wyckoff_phase if pos.wyckoff_phase else "unknown"
        phase_counts[phase] += 1

    total_positions = len(positions)
    majority_phase = max(phase_counts, key=phase_counts.get)
    majority_count = phase_counts[majority_phase]

    # Determine limit based on majority phase
    if majority_phase in ["A", "B"]:
        limit = Decimal("8.0")
        basis = f"Phase {majority_phase} majority ({majority_count}/{total_positions})"
    elif majority_phase in ["C", "D"]:
        limit = Decimal("12.0")
        basis = f"Phase {majority_phase} majority ({majority_count}/{total_positions})"
    elif majority_phase == "E":
        # Check if ≥60% in markup (Phase E)
        markup_count = phase_counts.get("E", 0)
        if markup_count / total_positions >= 0.6:
            limit = Decimal("15.0")
            basis = f"Phase E majority ({markup_count}/{total_positions})"
        else:
            limit = Decimal("12.0")
            basis = f"Phase E plurality ({markup_count}/{total_positions})"
    else:
        # Mixed phases or unknown
        limit = Decimal("10.0")
        basis = "mixed phases (default)"

    logger.info(
        "phase_adjusted_limit_calculated",
        limit=str(limit),
        basis=basis,
        phase_distribution=dict(phase_counts),
    )

    return limit, basis


def calculate_volume_risk_multiplier(positions: list[Position]) -> Decimal:
    """
    Calculate volume-based risk multiplier using weighted average volume score.

    Enhancement 2 (AC 13-15): Portfolio heat capacity increases based on
    weighted average volume confirmation (Wyckoff Law #3: strong volume =
    Composite Operator participation = lower effective risk).

    Volume Multipliers:
    -------------------
    - ≥30 points: 0.70x (allows ~14.3% heat: 10% / 0.7)
    - 20-30 points: 0.85x (allows ~11.8% heat: 10% / 0.85)
    - <20 points: 1.0x (no adjustment)

    Calculation:
    ------------
    Weighted avg = Σ(volume_score × position_risk_pct) / Σ(position_risk_pct)

    Args:
        positions: List of open Position objects with volume_confirmation_score

    Returns:
        Volume-based risk multiplier (0.70-1.0)

    Example:
    --------
    >>> positions = [
    ...     Position(symbol="AAPL", position_risk_pct=Decimal("3.0"),
    ...              volume_confirmation_score=Decimal("35.0"), ...),
    ...     Position(symbol="MSFT", position_risk_pct=Decimal("2.0"),
    ...              volume_confirmation_score=Decimal("25.0"), ...),
    ... ]
    >>> calculate_volume_risk_multiplier(positions)
    Decimal('0.70')  # Weighted avg = (35*3 + 25*2) / (3+2) = 31
    """
    if not positions:
        return Decimal("1.0")

    # Calculate weighted average volume score
    total_weighted_score = Decimal("0.0")
    total_risk = Decimal("0.0")

    for pos in positions:
        volume_score = (
            pos.volume_confirmation_score
            if pos.volume_confirmation_score is not None
            else Decimal("15.0")  # Default weak volume
        )
        total_weighted_score += volume_score * pos.position_risk_pct
        total_risk += pos.position_risk_pct

    if total_risk == Decimal("0.0"):
        return Decimal("1.0")

    weighted_avg_score = total_weighted_score / total_risk

    # Apply multiplier based on thresholds
    if weighted_avg_score >= Decimal("30.0"):
        multiplier = Decimal("0.70")
    elif weighted_avg_score >= Decimal("20.0"):
        multiplier = Decimal("0.85")
    else:
        multiplier = Decimal("1.0")

    logger.debug(
        "volume_risk_multiplier_calculated",
        weighted_avg_score=str(weighted_avg_score),
        multiplier=str(multiplier),
    )

    return multiplier


def identify_campaign_clusters(
    positions: list[Position],
) -> list[CampaignCluster]:
    """
    Identify campaign clusters (positions in same sector + phase).

    Enhancement 3 (AC 16-17): Positions sharing the same sector and
    Wyckoff phase represent correlated risks in the same accumulation
    campaign. Apply correlation penalties to prevent over-concentration.

    Correlation Multipliers:
    -------------------------
    - 2 positions: 0.90x (10% penalty)
    - 3 positions: 0.85x (15% penalty)
    - 4+ positions: 0.80x (20% penalty)

    Args:
        positions: List of open Position objects with sector and wyckoff_phase

    Returns:
        List of CampaignCluster objects (only clusters with ≥2 positions)

    Example:
    --------
    >>> positions = [
    ...     Position(symbol="AAPL", sector="Technology", wyckoff_phase="D",
    ...              position_risk_pct=Decimal("3.0"), ...),
    ...     Position(symbol="MSFT", sector="Technology", wyckoff_phase="D",
    ...              position_risk_pct=Decimal("2.5"), ...),
    ...     Position(symbol="JNJ", sector="Healthcare", wyckoff_phase="C",
    ...              position_risk_pct=Decimal("2.0"), ...),
    ... ]
    >>> clusters = identify_campaign_clusters(positions)
    >>> len(clusters)
    1
    >>> clusters[0].sector
    'Technology'
    >>> clusters[0].correlation_multiplier
    Decimal('0.90')
    """
    if not positions:
        return []

    # Group positions by (sector, wyckoff_phase)
    cluster_map = defaultdict(list)
    for pos in positions:
        sector = pos.sector if pos.sector else "unknown"
        phase = pos.wyckoff_phase if pos.wyckoff_phase else "unknown"
        key = (sector, phase)
        cluster_map[key].append(pos)

    # Build CampaignCluster objects for clusters with ≥2 positions
    clusters = []
    for (sector, phase), cluster_positions in cluster_map.items():
        if len(cluster_positions) < 2:
            continue  # Not a cluster

        position_count = len(cluster_positions)

        # Calculate correlation multiplier
        if position_count == 2:
            correlation_multiplier = Decimal("0.90")
        elif position_count == 3:
            correlation_multiplier = Decimal("0.85")
        else:  # 4+
            correlation_multiplier = Decimal("0.80")

        # Calculate raw and adjusted heat
        raw_heat = sum(pos.position_risk_pct for pos in cluster_positions)
        adjusted_heat = raw_heat * correlation_multiplier

        cluster = CampaignCluster(
            sector=sector,
            wyckoff_phase=phase,
            position_count=position_count,
            raw_heat=raw_heat,
            adjusted_heat=adjusted_heat,
            correlation_multiplier=correlation_multiplier,
            positions=[pos.symbol for pos in cluster_positions],
        )
        clusters.append(cluster)

    logger.debug("campaign_clusters_identified", cluster_count=len(clusters), clusters=clusters)

    return clusters


def calculate_correlation_adjusted_heat(
    positions: list[Position], clusters: list[CampaignCluster]
) -> Decimal:
    """
    Calculate correlation-adjusted heat applying cluster penalties.

    Enhancement 3 (AC 16): Calculates total portfolio heat with correlation
    adjustments for clustered positions. Unclustered positions count at 1.0x,
    clustered positions count at their correlation_multiplier.

    Args:
        positions: List of all open Position objects
        clusters: List of CampaignCluster objects from identify_campaign_clusters

    Returns:
        Correlation-adjusted portfolio heat percentage

    Example:
    --------
    >>> # 3 positions: 2 in Tech/D cluster (3% + 2.5%), 1 isolated (2%)
    >>> # Cluster penalty: (3 + 2.5) * 0.90 = 4.95
    >>> # Isolated: 2.0 * 1.0 = 2.0
    >>> # Total: 4.95 + 2.0 = 6.95
    """
    if not positions:
        return Decimal("0.0")

    # Build set of clustered symbols
    clustered_symbols = set()
    for cluster in clusters:
        clustered_symbols.update(cluster.positions)

    # Calculate adjusted heat
    adjusted_heat = Decimal("0.0")

    # Add unclustered positions at 1.0x
    for pos in positions:
        if pos.symbol not in clustered_symbols:
            adjusted_heat += pos.position_risk_pct

    # Add clustered positions using adjusted_heat from clusters
    for cluster in clusters:
        adjusted_heat += cluster.adjusted_heat

    logger.debug(
        "correlation_adjusted_heat_calculated",
        raw_clustered_symbols=len(clustered_symbols),
        adjusted_heat=str(adjusted_heat),
    )

    return adjusted_heat


def check_campaign_stage_warnings(
    portfolio_heat: "PortfolioHeat",
) -> list[PortfolioWarning]:
    """
    Generate context-aware warnings based on Wyckoff phase and volume analysis.

    Enhancement 4 (AC 7 revised): Replaces fixed 80% threshold with 4
    context-aware warning types that account for campaign stage, volume
    confirmation, and structural confidence.

    Warning Types:
    --------------
    1. underutilized_opportunity (INFO): Phase D/E majority, <8% heat
    2. premature_commitment (WARNING): Phase A/B majority, >6% heat
    3. capacity_limit (WARNING): ≥90% of phase-adjusted limit
    4. volume_quality_mismatch (WARNING): >8% heat, volume score <20

    Args:
        portfolio_heat: PortfolioHeat object with all calculated fields

    Returns:
        List of PortfolioWarning objects (0-N warnings)

    Example:
    --------
    >>> # Phase D majority, 7% heat
    >>> warnings = check_campaign_stage_warnings(portfolio_heat)
    >>> warnings[0].warning_type
    'underutilized_opportunity'
    >>> warnings[0].severity
    'INFO'
    """
    warnings = []

    # Determine majority phase
    if not portfolio_heat.phase_distribution:
        return warnings

    majority_phase = max(
        portfolio_heat.phase_distribution,
        key=portfolio_heat.phase_distribution.get,
    )

    # 1. Underutilized Opportunity Warning (INFO)
    if majority_phase in ["D", "E"] and portfolio_heat.total_heat < Decimal("8.0"):
        warnings.append(
            PortfolioWarning(
                warning_type="underutilized_opportunity",
                message=f"Portfolio underutilized: {portfolio_heat.total_heat}% heat with confirmed markup positions (consider scaling)",
                severity="INFO",
                context={
                    "heat": str(portfolio_heat.total_heat),
                    "majority_phase": majority_phase,
                    "threshold": "8.0",
                },
            )
        )
        logger.info(
            "portfolio_warning_underutilized",
            heat=str(portfolio_heat.total_heat),
            majority_phase=majority_phase,
        )

    # 2. Premature Commitment Warning (WARNING)
    if majority_phase in ["A", "B"] and portfolio_heat.total_heat > Decimal("6.0"):
        warnings.append(
            PortfolioWarning(
                warning_type="premature_commitment",
                message=f"Premature commitment: {portfolio_heat.total_heat}% heat in early-stage accumulation (reduce sizing)",
                severity="WARNING",
                context={
                    "heat": str(portfolio_heat.total_heat),
                    "majority_phase": majority_phase,
                    "threshold": "6.0",
                },
            )
        )
        logger.warning(
            "portfolio_warning_premature_commitment",
            heat=str(portfolio_heat.total_heat),
            majority_phase=majority_phase,
        )

    # 3. Capacity Limit Warning (WARNING)
    capacity_threshold = portfolio_heat.applied_heat_limit * Decimal("0.90")
    if portfolio_heat.total_heat >= capacity_threshold:
        warnings.append(
            PortfolioWarning(
                warning_type="capacity_limit",
                message=f"Portfolio heat approaching limit: {portfolio_heat.total_heat}% of {portfolio_heat.applied_heat_limit}% capacity ({portfolio_heat.limit_basis})",
                severity="WARNING",
                context={
                    "heat": str(portfolio_heat.total_heat),
                    "limit": str(portfolio_heat.applied_heat_limit),
                    "basis": portfolio_heat.limit_basis,
                    "threshold_pct": "90",
                },
            )
        )
        logger.warning(
            "portfolio_warning_capacity_limit",
            heat=str(portfolio_heat.total_heat),
            limit=str(portfolio_heat.applied_heat_limit),
            basis=portfolio_heat.limit_basis,
        )

    # 4. Volume Quality Mismatch Warning (WARNING)
    if portfolio_heat.total_heat > Decimal(
        "8.0"
    ) and portfolio_heat.weighted_volume_score < Decimal("20.0"):
        warnings.append(
            PortfolioWarning(
                warning_type="volume_quality_mismatch",
                message=f"High heat with weak volume confirmation: {portfolio_heat.total_heat}% heat, avg volume score {portfolio_heat.weighted_volume_score}",
                severity="WARNING",
                context={
                    "heat": str(portfolio_heat.total_heat),
                    "volume_score": str(portfolio_heat.weighted_volume_score),
                    "heat_threshold": "8.0",
                    "volume_threshold": "20.0",
                },
            )
        )
        logger.warning(
            "portfolio_warning_volume_quality_mismatch",
            heat=str(portfolio_heat.total_heat),
            volume_score=str(portfolio_heat.weighted_volume_score),
        )

    return warnings


def build_portfolio_heat_report(open_positions: list[Position]) -> PortfolioHeat:
    """
    Build comprehensive PortfolioHeat report with all enhancements.

    Orchestrator function (AC 5) that combines all heat calculations:
    1. Calculate raw heat (simple sum)
    2. Get phase-adjusted limit and basis
    3. Calculate volume multiplier
    4. Calculate effective limit (min of phase/volume-adjusted and 15% absolute max)
    5. Identify campaign clusters
    6. Calculate correlation-adjusted heat
    7. Generate context-aware warnings
    8. Populate PortfolioHeat dataclass

    Args:
        open_positions: List of open Position objects

    Returns:
        Fully populated PortfolioHeat object

    Example:
    --------
    >>> positions = [...]  # List of Position objects
    >>> report = build_portfolio_heat_report(positions)
    >>> report.total_heat
    Decimal('11.5')
    >>> report.applied_heat_limit
    Decimal('12.0')
    >>> report.warnings
    []  # No warnings if appropriate sizing
    """
    if not open_positions:
        # Empty portfolio
        return PortfolioHeat(
            position_count=0,
            risk_breakdown={},
            raw_heat=Decimal("0.0"),
            correlation_adjusted_heat=Decimal("0.0"),
            total_heat=Decimal("0.0"),
            available_capacity=Decimal("10.0"),  # Default limit
            phase_distribution={},
            applied_heat_limit=Decimal("10.0"),
            limit_basis="no positions (default)",
            weighted_volume_score=Decimal("0.0"),
            volume_multiplier=Decimal("1.0"),
            volume_adjusted_limit=None,
            campaign_clusters=[],
            warnings=[],
        )

    # 1. Calculate raw heat
    raw_heat = calculate_portfolio_heat(open_positions)

    # 2. Get phase-adjusted limit
    phase_limit, limit_basis = get_phase_adjusted_heat_limit(open_positions)

    # 3. Calculate volume multiplier
    volume_multiplier = calculate_volume_risk_multiplier(open_positions)

    # 4. Calculate effective limit
    if volume_multiplier < Decimal("1.0"):
        volume_adjusted_limit = phase_limit / volume_multiplier
        effective_limit = min(volume_adjusted_limit, Decimal("15.0"))
    else:
        volume_adjusted_limit = None
        effective_limit = phase_limit

    # Enforce absolute maximum
    applied_limit = min(effective_limit, Decimal("15.0"))

    # 5. Identify campaign clusters
    clusters = identify_campaign_clusters(open_positions)

    # 6. Calculate correlation-adjusted heat
    correlation_adjusted_heat = calculate_correlation_adjusted_heat(open_positions, clusters)

    # 7. Build risk breakdown and phase distribution
    risk_breakdown = {pos.symbol: pos.position_risk_pct for pos in open_positions}

    phase_distribution = defaultdict(int)
    for pos in open_positions:
        phase = pos.wyckoff_phase if pos.wyckoff_phase else "unknown"
        phase_distribution[phase] += 1

    # 8. Calculate weighted volume score
    total_weighted_score = Decimal("0.0")
    total_risk = Decimal("0.0")
    for pos in open_positions:
        volume_score = (
            pos.volume_confirmation_score
            if pos.volume_confirmation_score is not None
            else Decimal("15.0")
        )
        total_weighted_score += volume_score * pos.position_risk_pct
        total_risk += pos.position_risk_pct

    weighted_volume_score = (
        total_weighted_score / total_risk if total_risk > Decimal("0.0") else Decimal("0.0")
    )

    # 9. Create preliminary PortfolioHeat object
    portfolio_heat = PortfolioHeat(
        position_count=len(open_positions),
        risk_breakdown=risk_breakdown,
        raw_heat=raw_heat,
        correlation_adjusted_heat=correlation_adjusted_heat,
        total_heat=correlation_adjusted_heat,  # Use correlation-adjusted for validation
        available_capacity=applied_limit - correlation_adjusted_heat,
        phase_distribution=dict(phase_distribution),
        applied_heat_limit=applied_limit,
        limit_basis=limit_basis,
        weighted_volume_score=weighted_volume_score,
        volume_multiplier=volume_multiplier,
        volume_adjusted_limit=volume_adjusted_limit,
        campaign_clusters=clusters,
        warnings=[],  # Will be populated next
    )

    # 10. Generate warnings
    warnings = check_campaign_stage_warnings(portfolio_heat)
    portfolio_heat.warnings = warnings

    logger.info(
        "portfolio_heat_report_built",
        position_count=len(open_positions),
        total_heat=str(correlation_adjusted_heat),
        applied_limit=str(applied_limit),
        warning_count=len(warnings),
    )

    return portfolio_heat


def validate_portfolio_heat_capacity(
    current_heat: Decimal,
    new_position_risk: Decimal,
    positions: list[Position],
) -> tuple[bool, str | None]:
    """
    Validate that adding a new position won't exceed portfolio heat limits.

    AC 4: Pre-trade validation that checks if current_heat + new_position_risk
    exceeds the effective limit (phase-adjusted + volume-adjusted, capped at 15%).

    Args:
        current_heat: Current portfolio heat percentage
        new_position_risk: Risk percentage of proposed new position
        positions: List of current open Position objects (for phase/volume context)

    Returns:
        Tuple of (is_valid: bool, error_message: Optional[str])
        - (True, None) if validation passes
        - (False, error_message) if validation fails

    Example:
    --------
    >>> # Phase D portfolio (12% limit), current 10%, proposing 1.5%
    >>> is_valid, error = validate_portfolio_heat_capacity(
    ...     Decimal("10.0"), Decimal("1.5"), positions
    ... )
    >>> is_valid
    True

    >>> # Phase A portfolio (8% limit), current 7%, proposing 2%
    >>> is_valid, error = validate_portfolio_heat_capacity(
    ...     Decimal("7.0"), Decimal("2.0"), positions
    ... )
    >>> is_valid
    False
    >>> error
    'Portfolio heat limit exceeded: projected 9.0% exceeds Phase A limit of 8.0%'
    """
    projected_heat = current_heat + new_position_risk

    # Get phase-adjusted limit
    phase_limit, limit_basis = get_phase_adjusted_heat_limit(positions)

    # Apply volume multiplier
    volume_multiplier = calculate_volume_risk_multiplier(positions)
    if volume_multiplier < Decimal("1.0"):
        volume_adjusted_limit = phase_limit / volume_multiplier
        effective_limit = min(volume_adjusted_limit, Decimal("15.0"))
    else:
        effective_limit = phase_limit

    # Enforce absolute maximum
    effective_limit = min(effective_limit, Decimal("15.0"))

    # Validate projected heat
    if projected_heat > effective_limit:
        # Build error message
        error_parts = [
            f"Portfolio heat limit exceeded: projected {projected_heat}% exceeds",
            f"{limit_basis} limit of {effective_limit}%",
        ]

        if effective_limit == Decimal("15.0") and phase_limit > Decimal("15.0"):
            error_parts.append("(absolute maximum enforced)")

        error_message = " ".join(error_parts)

        logger.error(
            "portfolio_heat_limit_exceeded",
            current_heat=str(current_heat),
            new_position_risk=str(new_position_risk),
            projected_heat=str(projected_heat),
            effective_limit=str(effective_limit),
            limit_basis=limit_basis,
        )

        return False, error_message

    logger.debug(
        "portfolio_heat_capacity_validated",
        current_heat=str(current_heat),
        new_position_risk=str(new_position_risk),
        projected_heat=str(projected_heat),
        effective_limit=str(effective_limit),
    )

    return True, None
