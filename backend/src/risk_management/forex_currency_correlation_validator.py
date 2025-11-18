"""
Forex Currency Correlation Risk Limits with Phase-Weighted Exposure.

This module implements phase-weighted currency correlation limits for forex portfolios,
adapted from Wyckoff accumulation campaign methodology to recognize that Phase E
(confirmed campaigns) carry lower risk than Phase C (unconfirmed tests).

Story: 7.5-FX - Forex Currency Correlation Risk Limits (REVISED 2025-11-18)
Dependencies: Story 7.4-FX (Campaign Tracking), Story 4.x (Phase Detection)

MAJOR WYCKOFF REVISION (2025-11-18):
-------------------------------------
REMOVED (Contradicts Wyckoff):
- 8% directional limit (blocked legitimate multi-campaign setups)
- Currency correlation matrix (statistical correlation ≠ campaign correlation)

ADDED (Wyckoff-Aligned):
- Phase-weighted currency exposure (Phase E = 0.5x, Phase D = 0.75x, Phase C/B/A = 1.0x)
- Campaign count limit (max 3 concurrent campaigns)
- Integration with Story 4.x phase detection

Key Concepts:
------------
1. **Phase-Weighted Currency Limits (6% max per currency):**
   - Phase E (markup): 0.5x weight (confirmed campaign, SOS complete, low risk)
   - Phase D (LPS): 0.75x weight (progressing campaign, medium risk)
   - Phase C/B/A/None: 1.0x weight (unconfirmed campaign, full risk)
   - Example: EUR Phase E (4% raw) = 2% weighted exposure

2. **Campaign Count Limit (max 3 campaigns):**
   - Prevents portfolio complexity while allowing proper Wyckoff diversification
   - Example: EUR/USD Phase E + GBP/USD Phase E + AUD/USD Phase D = 3 campaigns (at limit)

3. **Currency Group Detection (ADVISORY ONLY):**
   - Tracks commodity (AUD, NZD, CAD), majors (USD, EUR, GBP, JPY, CHF)
   - Warns if group exposure > 10% (informational only, does NOT reject)

4. **Why Phase Weighting Matters:**
   - EUR/USD Phase E (6% raw) + GBP/USD Phase C (6% raw) = 12% raw USD exposure
   - Phase-weighted: (6% × 0.5) + (6% × 1.0) = 9% weighted USD exposure
   - Without weighting: REJECTED (12% > 6%)
   - With weighting: Needs evaluation against phase-weighted 6% limit
   - Wyckoff reality: Phase E confirmed campaigns are lower risk

Usage:
------
>>> from decimal import Decimal
>>> from datetime import datetime, UTC
>>>
>>> # Validate phase-weighted currency limits
>>> is_valid, error = validate_currency_limit_phase_weighted(
...     currency="USD",
...     current_positions=[
...         ForexPosition(symbol="EUR/USD", direction="long", position_risk_pct=Decimal("4.0"),
...                      wyckoff_phase="E", ...),  # Phase E: 4% × 0.5 = 2% weighted
...         ForexPosition(symbol="GBP/USD", direction="long", position_risk_pct=Decimal("2.0"),
...                      wyckoff_phase="C", ...),  # Phase C: 2% × 1.0 = 2% weighted
...     ],
...     new_position=ForexPosition(symbol="AUD/USD", direction="long",
...                               position_risk_pct=Decimal("2.0"), wyckoff_phase="D", ...)
... )
>>> # Weighted USD: -2% (EUR Phase E) - 2% (GBP Phase C) - 1.5% (AUD Phase D new) = -5.5%
>>> # Result: APPROVED (5.5% < 6% limit)

>>> # Validate campaign count limit
>>> is_valid, error = validate_campaign_count_limit(
...     current_campaigns=[
...         ForexCurrencyCampaign(campaign_id="EUR_LONG", ...),
...         ForexCurrencyCampaign(campaign_id="GBP_LONG", ...),
...         ForexCurrencyCampaign(campaign_id="AUD_LONG", ...),
...     ],
...     new_position_symbol="NZD/USD"  # Would start 4th campaign
... )
>>> # Result: REJECTED (exceeds 3 campaign limit)

Author: Story 7.5-FX (Revised per Wyckoff Team Review)
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

import structlog

from src.risk_management.forex_campaign_tracker import (
    ForexCurrencyCampaign,
    ForexPosition,
)

logger = structlog.get_logger(__name__)

# =============================================================================
# CONSTANTS
# =============================================================================

# Currency exposure limits (AC #3)
MAX_CURRENCY_EXPOSURE_PCT = Decimal("6.0")  # 6% max per currency (phase-weighted)
CURRENCY_WARNING_THRESHOLD_PCT = Decimal("5.0")  # Warn at 5.0% (83% of limit) for proximity

# Campaign limits (AC #4)
MAX_CONCURRENT_CAMPAIGNS = 3  # Max 3 concurrent campaigns

# Currency group concentration (AC #6 - ADVISORY ONLY)
CURRENCY_GROUP_WARNING_THRESHOLD_PCT = Decimal("10.0")  # Warn at 10% group exposure (advisory)

# Currency group classifications (AC #6)
CURRENCY_GROUPS = {
    "majors": ["USD", "EUR", "GBP", "JPY", "CHF"],
    "commodity": ["AUD", "NZD", "CAD"],
    "emerging": ["MXN", "BRL", "TRY", "ZAR", "PLN"],
    "european": ["EUR", "GBP", "CHF", "SEK", "NOK"],
}


# =============================================================================
# TASK 3: PHASE-WEIGHTED EXPOSURE CALCULATION (AC #3, #9)
# =============================================================================


def get_phase_weight(phase: Optional[str]) -> Decimal:
    """
    Return risk weighting multiplier by Wyckoff phase.

    Phase Weighting Rationale:
    --------------------------
    - Phase E: 0.5x weight - Campaign confirmed (Spring + SOS complete), markup validated,
               professional accumulation finished, lowest risk
    - Phase D: 0.75x weight - LPS confirmed, campaign progressing, medium risk
    - Phase C/B/A: 1.0x weight - Unconfirmed campaign, test phase, full risk
    - None: 1.0x weight - Unknown phase treated as full risk (conservative)

    Args:
        phase: Wyckoff phase ("A", "B", "C", "D", "E", or None)

    Returns:
        Decimal: Risk weight multiplier (0.50, 0.75, or 1.00)

    Examples:
        >>> get_phase_weight("E")
        Decimal('0.50')
        >>> get_phase_weight("D")
        Decimal('0.75')
        >>> get_phase_weight("C")
        Decimal('1.00')
        >>> get_phase_weight(None)
        Decimal('1.00')
    """
    PHASE_WEIGHTS: dict[Optional[str], Decimal] = {
        "E": Decimal("0.50"),  # Confirmed markup - lowest risk
        "D": Decimal("0.75"),  # LPS confirmed - medium risk
        "C": Decimal("1.00"),  # Test phase - full risk
        "B": Decimal("1.00"),  # Early accumulation - full risk
        "A": Decimal("1.00"),  # Preliminary support - full risk
        None: Decimal("1.00"),  # Unknown phase - full risk (conservative)
    }
    return PHASE_WEIGHTS.get(phase, Decimal("1.00"))


def calculate_currency_exposure_for_position(position: ForexPosition, currency: str) -> Decimal:
    """
    Calculate raw currency exposure for a single position.

    Forex Mechanics:
    ---------------
    - EUR/USD long: +EUR exposure, -USD exposure
    - EUR/USD short: -EUR exposure, +USD exposure
    - GBP/USD long: +GBP exposure, -USD exposure

    Args:
        position: Forex position to analyze
        currency: Currency to calculate exposure for ("EUR", "USD", "GBP", etc.)

    Returns:
        Decimal: Currency exposure as percentage (positive = long, negative = short)
                Returns 0.0 if currency not in position's symbol

    Examples:
        >>> pos = ForexPosition(symbol="EUR/USD", direction="long",
        ...                     position_risk_pct=Decimal("2.0"), ...)
        >>> calculate_currency_exposure_for_position(pos, "EUR")
        Decimal('2.0')  # Long EUR
        >>> calculate_currency_exposure_for_position(pos, "USD")
        Decimal('-2.0')  # Short USD
        >>> calculate_currency_exposure_for_position(pos, "GBP")
        Decimal('0')  # GBP not in EUR/USD
    """
    if "/" not in position.symbol:
        return Decimal("0")

    base, quote = position.symbol.split("/")

    if currency not in (base, quote):
        return Decimal("0")  # Currency not involved in this position

    risk_pct = position.position_risk_pct

    # Calculate exposure based on base/quote and direction
    if position.direction.upper() == "LONG":
        if currency == base:
            return risk_pct  # Long base currency
        else:  # currency == quote
            return -risk_pct  # Short quote currency
    else:  # SHORT
        if currency == base:
            return -risk_pct  # Short base currency
        else:  # currency == quote
            return risk_pct  # Long quote currency


def calculate_phase_weighted_exposure(
    positions: list[ForexPosition], currency: str
) -> tuple[Decimal, Decimal, dict[str, Decimal]]:
    """
    Calculate both raw and phase-weighted currency exposure.

    This is the CORE Wyckoff innovation - recognizing that Phase E confirmed
    campaigns carry lower risk than Phase C unconfirmed tests.

    Args:
        positions: List of open forex positions
        currency: Currency to calculate exposure for

    Returns:
        Tuple of:
        - raw_exposure: Total raw currency exposure (for reporting)
        - weighted_exposure: Phase-weighted exposure (for limit validation)
        - phase_breakdown: Dict of phase -> exposure for that phase

    Examples:
        >>> positions = [
        ...     ForexPosition(symbol="EUR/USD", direction="long", position_risk_pct=Decimal("4.0"),
        ...                  wyckoff_phase="E", ...),  # 4% EUR Phase E
        ...     ForexPosition(symbol="EUR/GBP", direction="long", position_risk_pct=Decimal("2.0"),
        ...                  wyckoff_phase="C", ...),  # 2% EUR Phase C
        ... ]
        >>> raw, weighted, breakdown = calculate_phase_weighted_exposure(positions, "EUR")
        >>> raw
        Decimal('6.0')  # 4% + 2% = 6% raw EUR
        >>> weighted
        Decimal('4.0')  # (4% × 0.5) + (2% × 1.0) = 2% + 2% = 4% weighted EUR
        >>> breakdown
        {'E': Decimal('4.0'), 'C': Decimal('2.0')}
    """
    raw_exposure = Decimal("0")
    weighted_exposure = Decimal("0")
    phase_breakdown: dict[str, Decimal] = {}

    for position in positions:
        if position.status != "OPEN":
            continue  # Skip closed positions

        # Calculate raw currency exposure for this position
        currency_exposure = calculate_currency_exposure_for_position(position, currency)

        if currency_exposure == Decimal("0"):
            continue  # Currency not involved in this position

        # Add to raw exposure
        raw_exposure += currency_exposure

        # Apply phase weighting
        phase_weight = get_phase_weight(position.wyckoff_phase)
        weighted_currency_exposure = currency_exposure * phase_weight
        weighted_exposure += weighted_currency_exposure

        # Track phase breakdown
        phase_key = position.wyckoff_phase or "None"
        phase_breakdown[phase_key] = (
            phase_breakdown.get(phase_key, Decimal("0")) + currency_exposure
        )

    logger.info(
        "calculated_phase_weighted_exposure",
        currency=currency,
        raw_exposure=str(raw_exposure),
        weighted_exposure=str(weighted_exposure),
        phase_breakdown={k: str(v) for k, v in phase_breakdown.items()},
    )

    return raw_exposure, weighted_exposure, phase_breakdown


def validate_currency_limit_phase_weighted(
    currency: str,
    current_positions: list[ForexPosition],
    new_position: ForexPosition,
) -> tuple[bool, Optional[str]]:
    """
    Validate currency exposure against 6% limit using phase-weighted calculation.

    This replaces the old flat 6% limit with phase-aware risk management.

    Key Change:
    ----------
    OLD: Reject if abs(raw_exposure) > 6%
    NEW: Reject if abs(weighted_exposure) > 6%

    Why This Matters:
    ----------------
    - EUR Phase E (4% raw) + EUR Phase C (4% raw) = 8% raw (OLD: REJECTED)
    - Phase-weighted: (4% × 0.5) + (4% × 1.0) = 4% weighted (NEW: APPROVED)
    - Wyckoff: Phase E confirmed campaigns are lower risk than Phase C tests

    Args:
        currency: Currency to validate ("EUR", "USD", "GBP", etc.)
        current_positions: List of currently open positions
        new_position: New position being considered

    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if position passes limit check
        - error_message: Rejection reason with actionable guidance (if rejected)

    Examples:
        >>> current = [
        ...     ForexPosition(symbol="EUR/USD", direction="long", position_risk_pct=Decimal("4.0"),
        ...                  wyckoff_phase="E", ...),
        ... ]
        >>> new = ForexPosition(symbol="EUR/GBP", direction="long",
        ...                     position_risk_pct=Decimal("3.0"), wyckoff_phase="C", ...)
        >>> is_valid, error = validate_currency_limit_phase_weighted("EUR", current, new)
        >>> is_valid
        True  # (4% × 0.5) + (3% × 1.0) = 5% weighted < 6% limit
    """
    # Calculate current phase-weighted exposure
    current_raw, current_weighted, phase_breakdown = calculate_phase_weighted_exposure(
        current_positions, currency
    )

    # Calculate new position's currency exposure
    new_exposure_raw = calculate_currency_exposure_for_position(new_position, currency)

    if new_exposure_raw == Decimal("0"):
        return True, None  # Currency not affected by this position

    # Apply phase weighting to new position
    new_phase_weight = get_phase_weight(new_position.wyckoff_phase)
    new_exposure_weighted = new_exposure_raw * new_phase_weight

    # Calculate projected totals
    projected_raw = current_raw + new_exposure_raw
    projected_weighted = current_weighted + new_exposure_weighted

    # Validate against phase-weighted limit
    abs_weighted = abs(projected_weighted)

    if abs_weighted > MAX_CURRENCY_EXPOSURE_PCT:
        # Build rejection message with phase context
        direction_label = "long" if projected_weighted > 0 else "short"
        error_msg = (
            f"REJECTED: {currency} phase-weighted exposure would reach "
            f"{projected_weighted:+.1f}% (limit: ±{MAX_CURRENCY_EXPOSURE_PCT}%)\n\n"
            f"Raw {currency} exposure: {projected_raw:+.1f}%\n"
            f"Phase-weighted exposure: {projected_weighted:+.1f}%\n\n"
            f"Current {currency} {direction_label} positions:\n"
        )

        # List current positions with phase context
        for pos in current_positions:
            pos_exposure = calculate_currency_exposure_for_position(pos, currency)
            if pos_exposure == Decimal("0"):
                continue

            phase_weight = get_phase_weight(pos.wyckoff_phase)
            weighted = pos_exposure * phase_weight
            error_msg += (
                f"- {pos.symbol} {pos.direction} @ {pos.entry} "
                f"({pos_exposure:+.1f}% raw, {weighted:+.1f}% weighted - Phase {pos.wyckoff_phase})\n"
            )

        error_msg += (
            "\nSuggestion: Close a Phase C/B/A position (1.0x weight) to free capacity, "
            "OR wait for positions to progress to Phase E (0.5x weight)"
        )

        logger.warning(
            "currency_limit_exceeded",
            currency=currency,
            current_raw=str(current_raw),
            current_weighted=str(current_weighted),
            new_raw=str(new_exposure_raw),
            new_weighted=str(new_exposure_weighted),
            projected_raw=str(projected_raw),
            projected_weighted=str(projected_weighted),
            limit=str(MAX_CURRENCY_EXPOSURE_PCT),
        )

        return False, error_msg

    # Check for proximity warning (>= 5.0%)
    if abs_weighted >= CURRENCY_WARNING_THRESHOLD_PCT:
        logger.info(
            "currency_limit_proximity_warning",
            currency=currency,
            projected_weighted=str(projected_weighted),
            threshold=str(CURRENCY_WARNING_THRESHOLD_PCT),
            limit=str(MAX_CURRENCY_EXPOSURE_PCT),
        )

    return True, None


# =============================================================================
# TASK 4: CAMPAIGN COUNT LIMIT VALIDATION (AC #4)
# =============================================================================


def validate_campaign_count_limit(
    current_campaigns: list[ForexCurrencyCampaign],
    new_position_symbol: str,
    max_campaigns: int = MAX_CONCURRENT_CAMPAIGNS,
) -> tuple[bool, Optional[str]]:
    """
    Validate campaign count limit (max 3 concurrent campaigns).

    IMPORTANT: ForexCurrencyCampaign tracks CURRENCY trends (e.g., "EUR_LONG"),
    not specific currency pairs. A campaign like "EUR_LONG" can include
    EUR/USD + EUR/GBP + EUR/JPY positions.

    Campaign Count Replaces Directional Limit:
    ------------------------------------------
    OLD (WRONG): 8% directional limit blocked EUR Phase E (6%) + GBP Phase E (3%) = 9% long
    NEW (WYCKOFF): Campaign count limit allows multiple Phase E campaigns, blocks complexity

    Why Campaign Count > Directional Limit:
    ---------------------------------------
    - Two Phase E confirmed campaigns = structurally valid (volume-validated accumulation)
    - 8% directional cap = arbitrary limit that ignores campaign phase/structure
    - Campaign count = prevents over-complexity while allowing proper diversification

    Args:
        current_campaigns: List of active currency campaigns (e.g., EUR_LONG, GBP_SHORT)
        new_position_symbol: Symbol of new position being considered ("EUR/USD", "GBP/USD", etc.)
        max_campaigns: Maximum concurrent campaigns allowed (default 3)

    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if adding position doesn't exceed campaign count
        - error_message: Rejection reason with campaign details (if rejected)

    Examples:
        >>> campaigns = [
        ...     ForexCurrencyCampaign(campaign_id="EUR_LONG", currency="EUR", direction="LONG", ...),
        ...     ForexCurrencyCampaign(campaign_id="GBP_LONG", currency="GBP", direction="LONG", ...),
        ...     ForexCurrencyCampaign(campaign_id="AUD_LONG", currency="AUD", direction="LONG", ...),
        ... ]
        >>> is_valid, error = validate_campaign_count_limit(campaigns, "NZD/USD")
        >>> is_valid
        False  # Would start 4th campaign (NZD_LONG), exceeds limit of 3
    """
    # Extract base and quote currencies from symbol
    if "/" not in new_position_symbol:
        return True, None  # Invalid symbol, skip validation

    base, quote = new_position_symbol.split("/")

    # Check if new position adds to existing campaign
    # A position adds to existing campaign if its currency (base or quote) matches
    # an existing campaign's currency AND direction aligns
    # NOTE: We can't determine direction from just the symbol, so we check if ANY
    # active campaign involves this currency pair
    existing_campaign = False
    for camp in current_campaigns:
        if camp.status != "ACTIVE":
            continue

        # Check if any position in this campaign uses the same symbol
        if any(pos.symbol == new_position_symbol for pos in camp.positions):
            existing_campaign = True
            break

    if existing_campaign:
        logger.info(
            "campaign_count_check_existing_campaign",
            new_symbol=new_position_symbol,
            result="approved_existing_campaign",
        )
        return True, None  # Adding to existing campaign - OK

    # Count active campaigns
    active_campaigns = [camp for camp in current_campaigns if camp.status == "ACTIVE"]
    active_count = len(active_campaigns)

    if active_count >= max_campaigns:
        # Build rejection message
        error_msg = (
            f"REJECTED: Maximum {max_campaigns} concurrent campaigns exceeded\n\n"
            f"Active campaigns: {active_count}\n"
            f"New position {new_position_symbol} would start campaign #{active_count + 1}\n\n"
            f"Current active campaigns:\n"
        )

        for i, camp in enumerate(active_campaigns, 1):
            # Get phase info from first position if available
            phase_info = ""
            if camp.positions:
                phases = {pos.wyckoff_phase for pos in camp.positions if pos.status == "OPEN"}
                if phases:
                    phase_info = f" - Phase {'/'.join(sorted(str(p) for p in phases if p))}"

            # Get symbols from campaign positions
            symbols = {pos.symbol for pos in camp.positions if pos.status == "OPEN"}
            symbols_str = ", ".join(sorted(symbols)) if symbols else "no active positions"

            error_msg += (
                f"{i}. {camp.campaign_id} ({camp.total_risk_pct:.1f}% risk across "
                f"{camp.position_count} positions: {symbols_str}{phase_info})\n"
            )

        error_msg += (
            "\nSuggestion: Close an existing campaign to free capacity, "
            "OR wait for a campaign to complete"
        )

        logger.warning(
            "campaign_count_limit_exceeded",
            active_count=active_count,
            max_campaigns=max_campaigns,
            new_symbol=new_position_symbol,
        )

        return False, error_msg

    logger.info(
        "campaign_count_check_new_campaign",
        new_symbol=new_position_symbol,
        active_count=active_count,
        max_campaigns=max_campaigns,
        result="approved_new_campaign",
    )

    return True, None


# =============================================================================
# TASK 6: CURRENCY GROUP DETECTION (AC #6 - ADVISORY ONLY)
# =============================================================================


def calculate_currency_group_exposure(
    positions: list[ForexPosition],
) -> dict[str, Decimal]:
    """
    Calculate absolute exposure per currency group (ADVISORY ONLY).

    CRITICAL: Group detection is INFORMATIONAL, NOT ENFORCED.
    - AUD Phase E + NZD Phase C = both commodity currencies but different risk
    - Statistical group correlation ≠ campaign correlation
    - Warnings are advisory - trader discretion to manage

    Args:
        positions: List of open forex positions

    Returns:
        Dict of group_name -> total_absolute_exposure_pct

    Examples:
        >>> positions = [
        ...     ForexPosition(symbol="AUD/USD", direction="long", position_risk_pct=Decimal("3.0"), ...),
        ...     ForexPosition(symbol="NZD/USD", direction="long", position_risk_pct=Decimal("2.0"), ...),
        ...     ForexPosition(symbol="CAD/JPY", direction="long", position_risk_pct=Decimal("1.5"), ...),
        ... ]
        >>> groups = calculate_currency_group_exposure(positions)
        >>> groups["commodity"]
        Decimal('6.5')  # AUD 3% + NZD 2% + CAD 1.5% = 6.5%
    """
    group_exposure: dict[str, Decimal] = {group: Decimal("0") for group in CURRENCY_GROUPS}

    for position in positions:
        if position.status != "OPEN":
            continue

        base, quote = position.symbol.split("/")
        risk_pct = position.position_risk_pct

        # Add absolute exposure to each currency's group
        for currency in (base, quote):
            for group_name, currencies in CURRENCY_GROUPS.items():
                if currency in currencies:
                    group_exposure[group_name] += risk_pct

    return group_exposure


def check_currency_group_concentration(
    group_exposure: dict[str, Decimal],
) -> list[tuple[str, Decimal]]:
    """
    Detect concentrated exposure in currency groups (ADVISORY ONLY - no rejections).

    Returns informational warnings if group exposure >= 10%.

    Args:
        group_exposure: Dict of group_name -> exposure_pct

    Returns:
        List of (group_name, exposure_pct) tuples for groups >= 10% threshold

    Examples:
        >>> group_exposure = {"commodity": Decimal("12.0"), "majors": Decimal("8.0")}
        >>> warnings = check_currency_group_concentration(group_exposure)
        >>> warnings
        [('commodity', Decimal('12.0'))]  # Only commodity >= 10%
    """
    concentrated: list[tuple[str, Decimal]] = []

    for group, exposure in group_exposure.items():
        if exposure >= CURRENCY_GROUP_WARNING_THRESHOLD_PCT:
            concentrated.append((group, exposure))
            logger.info(
                "currency_group_concentration_advisory",
                group=group,
                exposure=str(exposure),
                threshold=str(CURRENCY_GROUP_WARNING_THRESHOLD_PCT),
                message="ADVISORY ONLY - not enforced",
            )

    return concentrated


# =============================================================================
# TASK 5: FOREX CURRENCY EXPOSURE DATA MODEL (AC #5)
# =============================================================================


@dataclass
class ForexCurrencyExposure:
    """
    Forex currency exposure report with phase-weighted validation data.

    REVISED Data Model (Post-Wyckoff Review):
    -----------------------------------------
    ADDED:
    - currency_exposure_raw: Raw exposure (for reporting)
    - currency_exposure_weighted: Phase-weighted exposure (for validation)
    - phase_breakdown: Phase breakdown per currency
    - active_campaigns: List of campaign symbols
    - campaign_count: Number of active campaigns
    - campaign_limit_warning: Campaign count proximity warning

    REMOVED:
    - total_long_exposure: Removed (directional limit removed)
    - total_short_exposure: Removed (directional limit removed)
    - directional_limit_warning: Removed (directional limit removed)
    """

    # Raw exposure (for reporting) - AC #5
    currency_exposure_raw: dict[str, Decimal]

    # Phase-weighted exposure (for limit validation) - AC #5
    currency_exposure_weighted: dict[str, Decimal]

    # Phase breakdown per currency - AC #5
    # Format: {"EUR": {"E": Decimal("4.0"), "C": Decimal("2.0")}, ...}
    phase_breakdown: dict[str, dict[str, Decimal]]

    # Max currency exposure (by weighted exposure)
    max_currency_exposure: tuple[str, Decimal]

    # Currencies approaching limit (weighted >= 5.0%)
    currencies_at_limit: list[str]

    # Campaign tracking - AC #5
    active_campaigns: list[str]  # ["EUR/USD", "GBP/USD", "AUD/USD"]
    campaign_count: int
    campaign_limit_warning: Optional[str] = None

    # Currency group warnings (ADVISORY ONLY) - AC #6
    currency_group_warnings: list[tuple[str, Decimal]] = None  # type: ignore

    def __post_init__(self) -> None:
        """Initialize mutable default fields."""
        if self.currency_group_warnings is None:
            self.currency_group_warnings = []


def calculate_forex_currency_exposure(
    positions: list[ForexPosition], campaigns: list[ForexCurrencyCampaign]
) -> ForexCurrencyExposure:
    """
    Calculate comprehensive forex currency exposure with phase weighting.

    This is the main reporting function that shows both raw and weighted exposure.

    Args:
        positions: List of open forex positions
        campaigns: List of active campaigns

    Returns:
        ForexCurrencyExposure with raw, weighted, and phase breakdown data

    Examples:
        >>> positions = [
        ...     ForexPosition(symbol="EUR/USD", direction="long", position_risk_pct=Decimal("4.0"),
        ...                  wyckoff_phase="E", ...),
        ...     ForexPosition(symbol="EUR/GBP", direction="long", position_risk_pct=Decimal("2.0"),
        ...                  wyckoff_phase="C", ...),
        ... ]
        >>> campaigns = [ForexCurrencyCampaign(symbol="EUR/USD", status="ACTIVE", ...)]
        >>> exposure = calculate_forex_currency_exposure(positions, campaigns)
        >>> exposure.currency_exposure_raw["EUR"]
        Decimal('6.0')  # 4% + 2% = 6% raw
        >>> exposure.currency_exposure_weighted["EUR"]
        Decimal('4.0')  # (4% × 0.5) + (2% × 1.0) = 4% weighted
    """
    all_currencies = set()
    currency_exposure_raw: dict[str, Decimal] = {}
    currency_exposure_weighted: dict[str, Decimal] = {}
    phase_breakdown: dict[str, dict[str, Decimal]] = {}

    # Extract unique currencies
    for pos in positions:
        if pos.status != "OPEN":
            continue
        base, quote = pos.symbol.split("/")
        all_currencies.update([base, quote])

    # Calculate exposure for each currency
    for currency in all_currencies:
        raw, weighted, breakdown = calculate_phase_weighted_exposure(positions, currency)
        currency_exposure_raw[currency] = raw
        currency_exposure_weighted[currency] = weighted
        phase_breakdown[currency] = breakdown

    # Find max currency exposure (by weighted)
    max_currency = ("", Decimal("0"))
    for currency, weighted_exp in currency_exposure_weighted.items():
        if abs(weighted_exp) > abs(max_currency[1]):
            max_currency = (currency, weighted_exp)

    # Find currencies at limit (weighted >= 5.0%)
    currencies_at_limit = [
        currency
        for currency, weighted_exp in currency_exposure_weighted.items()
        if abs(weighted_exp) >= CURRENCY_WARNING_THRESHOLD_PCT
    ]

    # Campaign tracking
    # Extract symbols from campaign positions (campaigns track currency, not pairs)
    active_campaigns_list = [camp for camp in campaigns if camp.status == "ACTIVE"]
    active_campaign_symbols: list[str] = []
    for camp in active_campaigns_list:
        symbols = {pos.symbol for pos in camp.positions if pos.status == "OPEN"}
        active_campaign_symbols.extend(sorted(symbols))

    campaign_count = len(active_campaigns_list)

    # Campaign limit warning (at 3 campaigns)
    campaign_limit_warning = None
    if campaign_count >= MAX_CONCURRENT_CAMPAIGNS:
        campaign_limit_warning = (
            f"Campaign count at limit: {campaign_count}/{MAX_CONCURRENT_CAMPAIGNS} campaigns active"
        )

    # Currency group warnings (ADVISORY ONLY)
    group_exposure = calculate_currency_group_exposure(positions)
    currency_group_warnings = check_currency_group_concentration(group_exposure)

    return ForexCurrencyExposure(
        currency_exposure_raw=currency_exposure_raw,
        currency_exposure_weighted=currency_exposure_weighted,
        phase_breakdown=phase_breakdown,
        max_currency_exposure=max_currency,
        currencies_at_limit=currencies_at_limit,
        active_campaigns=active_campaign_symbols,
        campaign_count=campaign_count,
        campaign_limit_warning=campaign_limit_warning,
        currency_group_warnings=currency_group_warnings,
    )
