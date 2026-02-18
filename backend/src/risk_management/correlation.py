"""
Stock Sector Correlation Risk Management - Campaign-Level Tracking

Purpose:
--------
Implements campaign-level correlation tracking for stock sector risk management
with tiered limits (sector 6%, asset class 15%, geography 20%) to prevent
over-concentration while respecting Wyckoff campaign methodology.

Core Functions:
---------------
1. calculate_correlated_risk: Calculate total risk for a correlation group
2. validate_sector_campaign_count: Validate campaign count per sector
3. validate_correlated_risk: Multi-level correlation validation
4. calculate_all_correlations: Calculate correlations at all levels
5. build_correlation_report: Generate correlation risk report
6. check_correlation_proximity_warnings: Proximity alert generation
7. override_correlation_limit: Manual override with audit logging

Wyckoff Context - Campaign-Level Correlation:
----------------------------------------------
Wyckoff methodology manages CAMPAIGNS (accumulation cycles), not individual positions.

Key Distinction:
----------------
- Campaign scaling: Spring → LPS add #1 → LPS add #2 = ONE correlation risk unit
- New campaigns: AAPL campaign + MSFT campaign = TWO correlation risk units

Tiered Correlation Limits (AC 14, 15):
---------------------------------------
- Sector: 6% max (strictest - sectors rotate together)
- Asset class: 15% max (moderate - cross-sector diversification allowed)
- Geography: 20% max or None (loosest - optional macro risk control)

Validation checks ALL levels independently - strictest failure wins.

Example: 6% Tech + 6% Healthcare = 12% stocks → PASSES (under 15% asset class limit)

Integration:
------------
- Story 7.4: Uses Campaign model for campaign-level tracking
- Story 7.5: Core correlation risk calculation and validation

Author: Story 7.5
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.audit_trail import AuditTrailCreate
from src.models.correlation_campaign import CampaignForCorrelation
from src.models.risk import (
    CorrelatedRisk,
    CorrelationConfig,
    SectorMapping,
)

logger = structlog.get_logger(__name__)


def calculate_correlated_risk(
    correlation_key: str,
    correlation_type: str,
    open_campaigns: list[CampaignForCorrelation],
    sector_mappings: dict[str, SectorMapping],
) -> Decimal:
    """
    Calculate total correlated risk for a correlation group (AC 2, 4, 11).

    Calculates campaign-level correlation by filtering campaigns that match
    the correlation_key for the given correlation_type, then summing their
    total_campaign_risk values.

    Campaign vs Position Distinction:
    ----------------------------------
    - Filters CAMPAIGNS (not positions) by correlation_key
    - Sums campaign.total_campaign_risk (not individual position_risk_pct)
    - Campaign with 3 positions = 1 correlation unit with campaign's total risk

    Parameters:
    -----------
    correlation_key : str
        The correlation group to calculate (e.g., "Technology", "stock", "US")
    correlation_type : str
        Type of correlation: "sector", "asset_class", or "geography"
    open_campaigns : list[CampaignForCorrelation]
        All active campaigns with correlation metadata
    sector_mappings : dict[str, SectorMapping]
        Symbol → sector mapping lookup

    Returns:
    --------
    Decimal
        Total correlated risk percentage with 4 decimal places

    Example:
    --------
    >>> from decimal import Decimal
    >>> from uuid import uuid4
    >>> campaigns = [
    ...     CampaignForCorrelation(
    ...         campaign_id=uuid4(),
    ...         symbol="AAPL",
    ...         sector="Technology",
    ...         asset_class="stock",
    ...         geography="US",
    ...         total_campaign_risk=Decimal("1.5"),
    ...         positions=[],
    ...         status="ACTIVE"
    ...     ),
    ...     CampaignForCorrelation(
    ...         campaign_id=uuid4(),
    ...         symbol="MSFT",
    ...         sector="Technology",
    ...         asset_class="stock",
    ...         geography="US",
    ...         total_campaign_risk=Decimal("1.5"),
    ...         positions=[],
    ...         status="ACTIVE"
    ...     )
    ... ]
    >>> total = calculate_correlated_risk("Technology", "sector", campaigns, {})
    >>> total
    Decimal('3.0000')
    """
    # Filter campaigns by correlation type and key
    matching_campaigns = []
    for campaign in open_campaigns:
        if correlation_type == "sector" and campaign.sector == correlation_key:
            matching_campaigns.append(campaign)
        elif correlation_type == "asset_class" and campaign.asset_class == correlation_key:
            matching_campaigns.append(campaign)
        elif correlation_type == "geography" and campaign.geography == correlation_key:
            matching_campaigns.append(campaign)

    # Sum campaign-level risk (NOT position-level risk)
    total_risk = sum(
        (campaign.total_campaign_risk for campaign in matching_campaigns),
        start=Decimal("0.0000"),
    )

    logger.info(
        "correlated_risk_calculated",
        correlation_type=correlation_type,
        correlation_key=correlation_key,
        total_risk=str(total_risk),
        campaign_count=len(matching_campaigns),
    )

    return total_risk


def validate_sector_campaign_count(
    sector: str,
    campaigns: list[CampaignForCorrelation],
    max_campaigns: int = 3,
) -> tuple[bool, str | None]:
    """
    Validate campaign count per sector limit (AC 12).

    Prevents over-fragmentation of sector exposure by limiting the number
    of simultaneous campaigns per sector.

    Parameters:
    -----------
    sector : str
        Sector to validate (e.g., "Technology")
    campaigns : list[CampaignForCorrelation]
        All open campaigns
    max_campaigns : int
        Maximum campaigns allowed per sector (default 3)

    Returns:
    --------
    tuple[bool, str | None]
        - is_valid: True if campaign count <= max_campaigns
        - error_message: Error message if validation fails, None otherwise

    Example:
    --------
    >>> from uuid import uuid4
    >>> campaigns = [
    ...     CampaignForCorrelation(campaign_id=uuid4(), symbol="AAPL", sector="Technology", ...),
    ...     CampaignForCorrelation(campaign_id=uuid4(), symbol="MSFT", sector="Technology", ...),
    ...     CampaignForCorrelation(campaign_id=uuid4(), symbol="GOOGL", sector="Technology", ...)
    ... ]
    >>> is_valid, error = validate_sector_campaign_count("Technology", campaigns, max_campaigns=3)
    >>> is_valid
    True
    """
    # Count campaigns in sector
    sector_campaigns = [c for c in campaigns if c.sector == sector]
    campaign_count = len(sector_campaigns)

    if campaign_count >= max_campaigns:
        error_message = (
            f"Sector campaign limit exceeded: {sector} sector has {campaign_count} campaigns "
            f"(maximum {max_campaigns} allowed). Cannot add new campaign to this sector."
        )
        logger.warning(
            "sector_campaign_count_exceeded",
            sector=sector,
            current_count=campaign_count,
            max_campaigns=max_campaigns,
        )
        return False, error_message

    return True, None


def validate_correlated_risk(
    new_campaign: CampaignForCorrelation,
    open_campaigns: list[CampaignForCorrelation],
    config: CorrelationConfig,
) -> tuple[bool, str | None, list[str]]:
    """
    Validate correlated risk at campaign level with tiered limits (AC 5, 6, 14, 15).

    Validates correlation at ALL levels (sector, asset_class, geography) independently
    using tiered limits. In strict mode, ANY level exceeding its specific limit causes
    rejection. In permissive mode, warnings are returned but validation passes.

    Tiered Limits:
    --------------
    - Sector: 6% (strictest)
    - Asset class: 15% (moderate)
    - Geography: 20% or None (loosest, optional)

    Validation Logic:
    -----------------
    - Strict mode: Reject if ANY level > its specific limit
    - Permissive mode: Warn but allow if ANY level > its specific limit
    - Campaign count: Validate max campaigns per sector (AC 12)

    Parameters:
    -----------
    new_campaign : CampaignForCorrelation
        Campaign to validate
    open_campaigns : list[CampaignForCorrelation]
        Currently open campaigns (excludes new_campaign)
    config : CorrelationConfig
        Correlation configuration with tiered limits

    Returns:
    --------
    tuple[bool, str | None, list[str]]
        - is_valid: True if validation passes (or permissive mode)
        - rejection_reason: Error message if validation fails in strict mode
        - warnings: List of warning messages (permissive mode or proximity alerts)

    Example:
    --------
    >>> from decimal import Decimal
    >>> from uuid import uuid4
    >>> new = CampaignForCorrelation(
    ...     campaign_id=uuid4(),
    ...     symbol="NVDA",
    ...     sector="Technology",
    ...     asset_class="stock",
    ...     geography="US",
    ...     total_campaign_risk=Decimal("0.6"),
    ...     positions=[],
    ...     status="ACTIVE"
    ... )
    >>> config = CorrelationConfig(
    ...     max_sector_correlation=Decimal("6.0"),
    ...     max_asset_class_correlation=Decimal("15.0"),
    ...     enforcement_mode="strict"
    ... )
    >>> is_valid, reason, warnings = validate_correlated_risk(new, [], config)
    >>> is_valid
    True
    """
    warnings: list[str] = []

    # Validate campaign count per sector (AC 12)
    is_count_valid, count_error = validate_sector_campaign_count(
        new_campaign.sector,
        open_campaigns,
        config.max_campaigns_per_sector,
    )
    if not is_count_valid:
        if config.enforcement_mode == "strict":
            return False, count_error, warnings
        else:
            warnings.append(count_error or "Campaign count warning")

    # Calculate projected risk for each correlation level
    correlation_checks: list[tuple[str, str, Decimal, Decimal]] = []

    # Sector correlation (6% limit)
    sector_current = calculate_correlated_risk(
        new_campaign.sector, "sector", open_campaigns, config.sector_mappings
    )
    sector_projected = sector_current + new_campaign.total_campaign_risk
    correlation_checks.append(
        ("sector", new_campaign.sector, sector_projected, config.max_sector_correlation)
    )

    # Asset class correlation (15% limit)
    asset_class_current = calculate_correlated_risk(
        new_campaign.asset_class, "asset_class", open_campaigns, config.sector_mappings
    )
    asset_class_projected = asset_class_current + new_campaign.total_campaign_risk
    correlation_checks.append(
        (
            "asset_class",
            new_campaign.asset_class,
            asset_class_projected,
            config.max_asset_class_correlation,
        )
    )

    # Geography correlation (20% limit or None)
    if config.max_geography_correlation is not None and new_campaign.geography is not None:
        geography_current = calculate_correlated_risk(
            new_campaign.geography, "geography", open_campaigns, config.sector_mappings
        )
        geography_projected = geography_current + new_campaign.total_campaign_risk
        correlation_checks.append(
            (
                "geography",
                new_campaign.geography,
                geography_projected,
                config.max_geography_correlation,
            )
        )

    # Check all correlation levels
    for corr_type, corr_key, projected_risk, limit in correlation_checks:
        if projected_risk > limit:
            error_message = (
                f"Correlated risk limit exceeded: {corr_key} {corr_type} would reach "
                f"{projected_risk:.2f}% (limit: {limit:.2f}%)"
            )

            logger.error(
                "correlated_risk_limit_exceeded",
                correlation_type=corr_type,
                correlation_key=corr_key,
                current_risk=str(projected_risk - new_campaign.total_campaign_risk),
                new_campaign_risk=str(new_campaign.total_campaign_risk),
                projected_risk=str(projected_risk),
                limit=str(limit),
                enforcement_mode=config.enforcement_mode,
            )

            if config.enforcement_mode == "strict":
                return False, error_message, warnings
            else:
                warnings.append(error_message)

    return True, None, warnings


def calculate_all_correlations(
    open_campaigns: list[CampaignForCorrelation],
    sector_mappings: dict[str, SectorMapping],
    config: CorrelationConfig,
) -> dict[str, list[CorrelatedRisk]]:
    """
    Calculate correlations at all levels (sector, asset_class, geography) (AC 7).

    Calculates campaign-level correlations across all three correlation types,
    returning CorrelatedRisk objects with utilization percentages.

    Parameters:
    -----------
    open_campaigns : list[CampaignForCorrelation]
        All active campaigns
    sector_mappings : dict[str, SectorMapping]
        Symbol → sector mapping lookup
    config : CorrelationConfig
        Correlation configuration with limits

    Returns:
    --------
    dict[str, list[CorrelatedRisk]]
        Dictionary keyed by correlation_type with list of CorrelatedRisk objects

    Example:
    --------
    >>> correlations = calculate_all_correlations(campaigns, mappings, config)
    >>> tech_sector = [c for c in correlations["sector"] if c.correlation_key == "Technology"][0]
    >>> tech_sector.utilization_pct
    Decimal('75.00')
    """
    results: dict[str, list[CorrelatedRisk]] = {
        "sector": [],
        "asset_class": [],
        "geography": [],
    }

    # Collect unique correlation keys for each type
    sectors = {c.sector for c in open_campaigns}
    asset_classes = {c.asset_class for c in open_campaigns}
    geographies = {c.geography for c in open_campaigns if c.geography is not None}

    # Calculate sector correlations
    for sector in sectors:
        total_risk = calculate_correlated_risk(sector, "sector", open_campaigns, sector_mappings)
        if total_risk > Decimal("0"):
            campaigns_in_group = [c for c in open_campaigns if c.sector == sector]
            campaign_breakdown = {
                str(c.campaign_id): c.total_campaign_risk for c in campaigns_in_group
            }
            risk_breakdown = {}
            position_count = 0
            for campaign in campaigns_in_group:
                risk_breakdown[campaign.symbol] = campaign.total_campaign_risk
                position_count += len(campaign.positions)

            utilization_pct = (
                (total_risk / config.max_sector_correlation) * Decimal("100")
            ).quantize(Decimal("0.01"))

            results["sector"].append(
                CorrelatedRisk(
                    correlation_type="sector",
                    correlation_key=sector,
                    total_risk=total_risk,
                    campaign_count=len(campaigns_in_group),
                    campaign_breakdown=campaign_breakdown,
                    position_count=position_count,
                    risk_breakdown=risk_breakdown,
                    limit=config.max_sector_correlation,
                    utilization_pct=utilization_pct,
                )
            )

    # Calculate asset class correlations
    for asset_class in asset_classes:
        total_risk = calculate_correlated_risk(
            asset_class, "asset_class", open_campaigns, sector_mappings
        )
        if total_risk > Decimal("0"):
            campaigns_in_group = [c for c in open_campaigns if c.asset_class == asset_class]
            campaign_breakdown = {
                str(c.campaign_id): c.total_campaign_risk for c in campaigns_in_group
            }
            risk_breakdown = {}
            position_count = 0
            for campaign in campaigns_in_group:
                risk_breakdown[campaign.symbol] = campaign.total_campaign_risk
                position_count += len(campaign.positions)

            utilization_pct = (
                (total_risk / config.max_asset_class_correlation) * Decimal("100")
            ).quantize(Decimal("0.01"))

            results["asset_class"].append(
                CorrelatedRisk(
                    correlation_type="asset_class",
                    correlation_key=asset_class,
                    total_risk=total_risk,
                    campaign_count=len(campaigns_in_group),
                    campaign_breakdown=campaign_breakdown,
                    position_count=position_count,
                    risk_breakdown=risk_breakdown,
                    limit=config.max_asset_class_correlation,
                    utilization_pct=utilization_pct,
                )
            )

    # Calculate geography correlations (if enabled)
    if config.max_geography_correlation is not None:
        for geography in geographies:
            total_risk = calculate_correlated_risk(
                geography, "geography", open_campaigns, sector_mappings
            )
            if total_risk > Decimal("0"):
                campaigns_in_group = [c for c in open_campaigns if c.geography == geography]
                campaign_breakdown = {
                    str(c.campaign_id): c.total_campaign_risk for c in campaigns_in_group
                }
                risk_breakdown = {}
                position_count = 0
                for campaign in campaigns_in_group:
                    risk_breakdown[campaign.symbol] = campaign.total_campaign_risk
                    position_count += len(campaign.positions)

                utilization_pct = (
                    (total_risk / config.max_geography_correlation) * Decimal("100")
                ).quantize(Decimal("0.01"))

                results["geography"].append(
                    CorrelatedRisk(
                        correlation_type="geography",
                        correlation_key=geography,
                        total_risk=total_risk,
                        campaign_count=len(campaigns_in_group),
                        campaign_breakdown=campaign_breakdown,
                        position_count=position_count,
                        risk_breakdown=risk_breakdown,
                        limit=config.max_geography_correlation,
                        utilization_pct=utilization_pct,
                    )
                )

    return results


def build_correlation_report(
    open_campaigns: list[CampaignForCorrelation],
    sector_mappings: dict[str, SectorMapping],
    config: CorrelationConfig,
) -> dict[str, list[CorrelatedRisk]]:
    """
    Build correlation risk report (AC 4).

    Generates comprehensive correlation report with correlations sorted by
    total_risk descending (highest risk first). Filters out empty correlation
    groups (total_risk = 0).

    Parameters:
    -----------
    open_campaigns : list[CampaignForCorrelation]
        All active campaigns
    sector_mappings : dict[str, SectorMapping]
        Symbol → sector mapping lookup
    config : CorrelationConfig
        Correlation configuration with limits

    Returns:
    --------
    dict[str, list[CorrelatedRisk]]
        Correlation report sorted by risk (highest first), empty groups filtered

    Example:
    --------
    >>> report = build_correlation_report(campaigns, mappings, config)
    >>> for sector_corr in report["sector"]:
    ...     print(f"{sector_corr.correlation_key}: {sector_corr.total_risk}%")
    Technology: 4.5%
    Healthcare: 3.0%
    """
    correlations = calculate_all_correlations(open_campaigns, sector_mappings, config)

    # Sort each correlation type by total_risk descending
    for corr_type in correlations:
        correlations[corr_type] = sorted(
            correlations[corr_type],
            key=lambda c: c.total_risk,
            reverse=True,
        )

    return correlations


def check_correlation_proximity_warnings(
    correlations: dict[str, list[CorrelatedRisk]],
) -> list[str]:
    """
    Check for correlation proximity warnings (≥80% of limit).

    Generates early warning alerts when correlation utilization reaches 80%
    of the limit for any correlation level.

    Proximity Thresholds:
    ---------------------
    - Sector: 4.8% (80% of 6.0%)
    - Asset class: 12.0% (80% of 15.0%)
    - Geography: 16.0% (80% of 20.0%)

    Parameters:
    -----------
    correlations : dict[str, list[CorrelatedRisk]]
        Correlation report from build_correlation_report

    Returns:
    --------
    list[str]
        List of proximity warning messages

    Example:
    --------
    >>> warnings = check_correlation_proximity_warnings(correlations)
    >>> warnings
    ['Correlation proximity alert: Technology sector at 4.9% (81.7% of limit)']
    """
    warnings: list[str] = []
    proximity_threshold = Decimal("80.0")  # 80%

    for corr_type, corr_list in correlations.items():
        for corr in corr_list:
            if corr.utilization_pct >= proximity_threshold:
                warning = (
                    f"Correlation proximity alert: {corr.correlation_key} {corr_type} "
                    f"at {corr.total_risk:.2f}% ({corr.utilization_pct:.1f}% of limit)"
                )
                warnings.append(warning)

                logger.warning(
                    "correlated_risk_proximity_warning",
                    correlation_type=corr_type,
                    correlation_key=corr.correlation_key,
                    total_risk=str(corr.total_risk),
                    limit=str(corr.limit),
                    utilization_pct=str(corr.utilization_pct),
                )

    return warnings


async def override_correlation_limit(
    signal_id: UUID,
    approver: str,
    reason: str,
    session: AsyncSession | None = None,
) -> bool:
    """
    Manual override of correlation limit with audit logging (AC 10).

    Allows manual approval to bypass correlation limit rejection in strict mode.
    Persists override to audit_trail table for compliance. Falls back to
    structured logging if no database session is provided.

    Parameters:
    -----------
    signal_id : UUID
        Signal identifier being approved
    approver : str
        Name/ID of person approving override
    reason : str
        Justification for override
    session : AsyncSession | None
        Database session for audit persistence (optional for backward compat)

    Returns:
    --------
    bool
        True if override succeeds. False if session is provided but
        audit write fails (compliance policy: no unaudited overrides).

    Raises:
    -------
    No exceptions raised -- returns False on audit write failure.

    Example:
    --------
    >>> from uuid import uuid4
    >>> await override_correlation_limit(
    ...     signal_id=uuid4(),
    ...     approver="john.doe@example.com",
    ...     reason="Exceptional Wyckoff setup with strong volume confirmation",
    ...     session=db_session,
    ... )
    True
    """
    logger.warning(
        "correlation_limit_override",
        signal_id=str(signal_id),
        approver=approver,
        reason=reason,
        event_type="CORRELATION_OVERRIDE",
    )

    if session is not None:
        # Compliance policy: if a session is provided, the audit write MUST succeed.
        # An unaudited override is not permitted -- return False to block the override.
        try:
            from src.repositories.audit_trail_repository import AuditTrailRepository

            repo = AuditTrailRepository(session)
            await repo.insert(
                AuditTrailCreate(
                    event_type="CORRELATION_OVERRIDE",
                    entity_type="SIGNAL",
                    entity_id=str(signal_id),
                    actor=approver,
                    action="Manual override of correlation limit",
                    metadata={
                        "reason": reason,
                        "timestamp": datetime.now(UTC).isoformat(),
                    },
                )
            )
        except Exception:
            logger.error(
                "correlation_override_audit_write_failed",
                signal_id=str(signal_id),
                approver=approver,
                reason=reason,
            )
            return False

    return True
