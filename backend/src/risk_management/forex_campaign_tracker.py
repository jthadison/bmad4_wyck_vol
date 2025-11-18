"""
Forex Campaign Risk Tracking (Currency Trends).

This module implements campaign risk tracking for forex currency trends, adapting
Wyckoff accumulation campaign principles to forex market dynamics.

Story: 7.4-FX - Forex Campaign Risk Tracking
Dependencies: Story 7.2-FX (Forex Position Sizing), Story 7.3-FX (Weekend Gap Risk)

Key Differences from Stock Campaigns:
- Campaign = Currency trend (EUR strength) not trading range (AAPL $140-150)
- Multi-pair campaigns: EUR/USD + EUR/GBP + EUR/JPY = single EUR_LONG campaign
- BMAD allocation inverted: 25%/45%/30% (confirmation = largest position)
- Volume validation required for multi-pair additions
- Trend completion = all positions closed, reversal, or 14-day duration

CRITICAL REVISION (Wyckoff Team Review 2025-11-17):
- BMAD allocation changed from 40%/35%/25% to 25%/45%/30%
- Volume validation added for multi-pair campaign additions
- Rationale: Forex trends have inverted risk vs stocks - largest position at
  CONFIRMATION when multiple pairs show high-volume SOS validating trend,
  not at first unconfirmed entry.
"""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal, Optional

# Configure logging
logger = logging.getLogger(__name__)


# =============================================================================
# BMAD ALLOCATION CONSTANTS (WYCKOFF TEAM REVISED - 2025-11-17)
# =============================================================================

# Forex currency trend BMAD allocation (volume-validated)
# CRITICAL: Inverted from stock allocation (40%/35%/25%)
# In forex trends, largest position at CONFIRMATION, not first entry

FOREX_TREND_FIRST_ENTRY_ALLOC = Decimal("0.25")  # 25% - 1st leg (unconfirmed trend)
FOREX_TREND_CONFIRM_ALLOC = Decimal("0.45")  # 45% - Trend confirmation (PRIMARY entry)
FOREX_TREND_ADDON_ALLOC = Decimal("0.30")  # 30% - Trend continuation

MAX_FOREX_CAMPAIGN_RISK = Decimal("5.0")  # 5% max per currency trend (same as stocks)

# Maximum risk per entry type (of 5% campaign budget)
MAX_FIRST_ENTRY_RISK = Decimal("1.25")  # 25% of 5% = 1.25%
MAX_CONFIRM_RISK = Decimal("2.25")  # 45% of 5% = 2.25%
MAX_ADDON_RISK = Decimal("1.50")  # 30% of 5% = 1.50%

# Campaign duration defaults
DEFAULT_CAMPAIGN_DURATION_DAYS = 14  # Forex trends shorter than stock accumulation

# Volume validation thresholds (per entry type)
# CRITICAL: Required per Wyckoff team review
FIRST_ENTRY_MAX_VOLUME = Decimal("0.8")  # Spring: low volume test (<0.8x avg)
CONFIRM_MIN_VOLUME = Decimal("1.5")  # SOS: high volume breakout (≥1.5x avg)
ADDON_MIN_VOLUME = Decimal("1.2")  # Continuation: above-average (≥1.2x avg)


# =============================================================================
# DATA MODELS
# =============================================================================


@dataclass
class ForexPosition:
    """
    Represents an open forex position.

    Extended from Story 7.2-FX with campaign tracking fields.
    """

    symbol: str  # "EUR/USD", "GBP/JPY", etc.
    entry: Decimal
    stop: Decimal
    lot_size: Decimal
    lot_type: Literal["standard", "mini", "micro"]
    position_value_usd: Decimal
    account_balance: Decimal
    pattern_type: str = "SPRING"  # "SPRING", "LPS", "SOS"
    wyckoff_phase: str = "D"  # "C", "D", "E"
    direction: Literal["long", "short"] = "long"
    entry_type: str = "FIRST"  # "FIRST", "CONFIRM", "ADDON"
    campaign_id: Optional[str] = None  # "EUR_LONG_2024_03_15"
    status: str = "OPEN"  # "OPEN", "CLOSED"
    position_risk_pct: Decimal = field(default_factory=lambda: Decimal("0"))
    volume_ratio: Decimal = field(
        default_factory=lambda: Decimal("1.0")
    )  # Current vol / 20-bar avg

    def __post_init__(self) -> None:
        """Calculate position risk percentage if not provided."""
        if self.position_risk_pct == Decimal("0"):
            stop_distance = abs(self.entry - self.stop)
            risk_dollars = (stop_distance / self.entry) * self.position_value_usd
            self.position_risk_pct = (
                (risk_dollars / self.account_balance) * Decimal("100")
            ).quantize(Decimal("0.01"))


@dataclass
class ForexCurrencyCampaign:
    """
    Forex currency trend campaign tracking.

    Tracks directional exposure to single currency across multiple pairs.
    Example: EUR_LONG campaign includes EUR/USD long, EUR/GBP long, EUR/JPY long.
    """

    campaign_id: str  # "EUR_LONG_2024_03_15"
    currency: str  # "EUR", "USD", "GBP", "JPY", "CHF", "AUD", "NZD", "CAD"
    direction: Literal["LONG", "SHORT"]
    total_risk_pct: Decimal
    position_count: int
    positions: list[ForexPosition]
    started_at: datetime
    status: Literal["ACTIVE", "COMPLETED", "REVERSED"] = "ACTIVE"
    expected_completion: Optional[datetime] = None
    created_at: Optional[datetime] = None
    available_capacity_pct: Decimal = field(init=False)

    def __post_init__(self) -> None:
        """Initialize calculated fields."""
        if self.created_at is None:
            self.created_at = datetime.now(UTC)

        # Calculate available capacity
        self.available_capacity_pct = (MAX_FOREX_CAMPAIGN_RISK - self.total_risk_pct).quantize(
            Decimal("0.01")
        )

        # Set expected completion (14 days default)
        if self.expected_completion is None:
            self.expected_completion = self.started_at + timedelta(
                days=DEFAULT_CAMPAIGN_DURATION_DAYS
            )

    @property
    def is_expired(self) -> bool:
        """Check if campaign exceeded max duration."""
        return datetime.now(UTC) > self.expected_completion  # type: ignore

    @property
    def days_active(self) -> int:
        """Calculate campaign duration in days."""
        return (datetime.now(UTC) - self.started_at).days

    @property
    def risk_utilization_pct(self) -> Decimal:
        """Calculate percentage of campaign budget used."""
        if MAX_FOREX_CAMPAIGN_RISK == Decimal("0"):
            return Decimal("0")
        utilization = (self.total_risk_pct / MAX_FOREX_CAMPAIGN_RISK) * Decimal("100")
        return utilization.quantize(Decimal("0.1"))


# =============================================================================
# CURRENCY TREND IDENTIFICATION
# =============================================================================


def extract_currency_exposure(symbol: str, direction: Literal["long", "short"]) -> tuple[str, str]:
    """
    Extract which currency is being bought/sold.

    Args:
        symbol: "EUR/USD", "GBP/JPY", etc.
        direction: "long" or "short"

    Returns:
        (bought_currency, sold_currency)

    Examples:
        >>> extract_currency_exposure("EUR/USD", "long")
        ("EUR", "USD")  # Buy EUR, sell USD

        >>> extract_currency_exposure("EUR/USD", "short")
        ("USD", "EUR")  # Buy USD, sell EUR

        >>> extract_currency_exposure("GBP/JPY", "long")
        ("GBP", "JPY")  # Buy GBP, sell JPY
    """
    if "/" not in symbol:
        raise ValueError(
            f"Invalid forex symbol format: {symbol}. Expected format: BASE/QUOTE (e.g., EUR/USD)"
        )

    base, quote = symbol.split("/")

    if direction.upper() == "LONG":
        return base, quote  # Buy base, sell quote
    else:  # SHORT
        return quote, base  # Buy quote, sell base


def get_campaign_id(
    currency: str, direction: Literal["LONG", "SHORT"], start_date: Optional[datetime] = None
) -> str:
    """
    Generate campaign ID for currency trend.

    Format: {CURRENCY}_{DIRECTION}_{YYYY_MM_DD}

    Args:
        currency: "EUR", "USD", "GBP", etc.
        direction: "LONG" or "SHORT"
        start_date: Campaign start date (defaults to now)

    Returns:
        Campaign ID string

    Examples:
        >>> get_campaign_id("EUR", "LONG", datetime(2024, 3, 15))
        "EUR_LONG_2024_03_15"

        >>> get_campaign_id("USD", "SHORT", datetime(2024, 4, 1))
        "USD_SHORT_2024_04_01"
    """
    if start_date is None:
        start_date = datetime.now(UTC)

    date_str = start_date.strftime("%Y_%m_%d")
    return f"{currency.upper()}_{direction.upper()}_{date_str}"


# =============================================================================
# CAMPAIGN RISK CALCULATION
# =============================================================================


def calculate_currency_campaign_risk(
    campaign_id: str, open_positions: list[ForexPosition]
) -> Decimal:
    """
    Calculate total risk for currency trend campaign.

    Sums position_risk_pct across all positions in campaign.

    Args:
        campaign_id: Campaign identifier
        open_positions: List of open forex positions

    Returns:
        Total campaign risk percentage

    Example:
        >>> positions = [
        ...     ForexPosition(..., campaign_id="EUR_LONG_2024_03_15", position_risk_pct=Decimal("1.5")),
        ...     ForexPosition(..., campaign_id="EUR_LONG_2024_03_15", position_risk_pct=Decimal("1.5")),
        ...     ForexPosition(..., campaign_id="EUR_LONG_2024_03_15", position_risk_pct=Decimal("1.0")),
        ... ]
        >>> calculate_currency_campaign_risk("EUR_LONG_2024_03_15", positions)
        Decimal("4.0")
    """
    total_risk = Decimal("0")

    for position in open_positions:
        # Skip positions without campaign_id or different campaign
        if not hasattr(position, "campaign_id") or position.campaign_id != campaign_id:
            continue

        # Only count open positions
        if hasattr(position, "status") and position.status != "OPEN":
            continue

        total_risk += position.position_risk_pct

    return total_risk.quantize(Decimal("0.01"))


# =============================================================================
# BMAD ALLOCATION VALIDATION (WYCKOFF TEAM REVISED)
# =============================================================================


def validate_forex_bmad_allocation(
    campaign: ForexCurrencyCampaign,
    new_entry_type: Literal["FIRST", "CONFIRM", "ADDON"],
    new_entry_risk: Decimal,
) -> tuple[bool, Optional[str]]:
    """
    Validate BMAD allocation for forex trend entries.

    CRITICAL REVISION (Wyckoff Team 2025-11-17):
    - FIRST:   25% of 5% = 1.25% max (exploratory, unconfirmed trend)
    - CONFIRM: 45% of 5% = 2.25% max (PRIMARY entry, multi-pair validation)
    - ADDON:   30% of 5% = 1.50% max (continuation, established trend)

    Args:
        campaign: Existing forex currency campaign
        new_entry_type: "FIRST", "CONFIRM", or "ADDON"
        new_entry_risk: Risk percentage of new position

    Returns:
        (is_valid, error_message)

    Example:
        >>> campaign = ForexCurrencyCampaign(..., positions=[
        ...     ForexPosition(entry_type="FIRST", position_risk_pct=Decimal("1.0")),
        ...     ForexPosition(entry_type="CONFIRM", position_risk_pct=Decimal("2.0")),
        ... ])
        >>> validate_forex_bmad_allocation(campaign, "CONFIRM", Decimal("0.25"))
        (True, None)  # 2.0 + 0.25 = 2.25 (at limit)

        >>> validate_forex_bmad_allocation(campaign, "CONFIRM", Decimal("0.26"))
        (False, "CONFIRM allocation exceeded: 2.26% > 2.25% (max 45% of campaign budget)")
    """
    # Calculate existing risk for this entry type
    entry_type_risk = Decimal("0")
    for position in campaign.positions:
        if hasattr(position, "entry_type") and position.entry_type == new_entry_type:
            # Only count open positions
            if hasattr(position, "status") and position.status == "OPEN":
                entry_type_risk += position.position_risk_pct

    # Check entry type limits
    if new_entry_type == "FIRST":
        max_risk = MAX_FIRST_ENTRY_RISK
        allocation = "25%"
    elif new_entry_type == "CONFIRM":
        max_risk = MAX_CONFIRM_RISK
        allocation = "45%"
    elif new_entry_type == "ADDON":
        max_risk = MAX_ADDON_RISK
        allocation = "30%"
    else:
        return False, f"Invalid entry type: {new_entry_type}"

    total_entry_type_risk = entry_type_risk + new_entry_risk

    if total_entry_type_risk > max_risk:
        return False, (
            f"{new_entry_type} allocation exceeded: "
            f"{total_entry_type_risk}% > {max_risk}% "
            f"(max {allocation} of campaign budget)"
        )

    return True, None


# =============================================================================
# TREND COMPLETION DETECTION
# =============================================================================


def detect_trend_reversal(
    campaign: ForexCurrencyCampaign,
    new_signal_currency: str,
    new_signal_direction: Literal["LONG", "SHORT"],
) -> bool:
    """
    Detect if new signal reverses existing trend.

    Args:
        campaign: Active forex currency campaign
        new_signal_currency: Currency of new signal
        new_signal_direction: Direction of new signal ("LONG" or "SHORT")

    Returns:
        True if reversal detected, False otherwise

    Examples:
        >>> campaign = ForexCurrencyCampaign(
        ...     campaign_id="EUR_LONG_2024_03_15",
        ...     currency="EUR",
        ...     direction="LONG",
        ...     ...
        ... )
        >>> detect_trend_reversal(campaign, "EUR", "SHORT")
        True  # EUR long campaign + EUR short signal = reversal

        >>> detect_trend_reversal(campaign, "USD", "SHORT")
        False  # Different currency, not a reversal

        >>> detect_trend_reversal(campaign, "EUR", "LONG")
        False  # Same direction, trend continuation
    """
    if new_signal_currency != campaign.currency:
        return False  # Different currency, not a reversal

    # Opposite direction = reversal
    if campaign.direction == "LONG" and new_signal_direction == "SHORT":
        logger.warning(
            f"TREND REVERSAL: {campaign.campaign_id} (long {campaign.currency}) "
            f"reversed by {new_signal_currency} short signal"
        )
        return True

    if campaign.direction == "SHORT" and new_signal_direction == "LONG":
        logger.warning(
            f"TREND REVERSAL: {campaign.campaign_id} (short {campaign.currency}) "
            f"reversed by {new_signal_currency} long signal"
        )
        return True

    return False


def check_campaign_completion(campaign: ForexCurrencyCampaign) -> tuple[bool, str]:
    """
    Check if currency trend campaign should complete.

    Completion conditions:
    1. All positions closed
    2. Maximum duration exceeded (14 days default)

    Args:
        campaign: Forex currency campaign

    Returns:
        (is_complete, reason)

    Examples:
        >>> campaign = ForexCurrencyCampaign(..., positions=[
        ...     ForexPosition(status="CLOSED"),
        ...     ForexPosition(status="CLOSED"),
        ... ])
        >>> check_campaign_completion(campaign)
        (True, "ALL_POSITIONS_CLOSED")

        >>> campaign = ForexCurrencyCampaign(
        ...     started_at=datetime.now(timezone.utc) - timedelta(days=15),
        ...     expected_completion=datetime.now(timezone.utc) - timedelta(days=1),
        ...     positions=[ForexPosition(status="OPEN")]
        ... )
        >>> check_campaign_completion(campaign)
        (True, "MAX_DURATION_EXCEEDED")
    """
    # All positions closed
    open_positions = [p for p in campaign.positions if p.status == "OPEN"]
    if len(open_positions) == 0:
        logger.info(f"{campaign.campaign_id}: All positions closed")
        return True, "ALL_POSITIONS_CLOSED"

    # Maximum duration exceeded (14 days default)
    if campaign.is_expired:
        logger.warning(
            f"{campaign.campaign_id}: Max duration exceeded ({campaign.days_active} days active)"
        )
        return True, "MAX_DURATION_EXCEEDED"

    # Campaign active
    return False, "ACTIVE"


# =============================================================================
# MULTI-PAIR VALIDATION (WYCKOFF TEAM REQUIRED)
# =============================================================================


def validate_position_matches_campaign(
    campaign: ForexCurrencyCampaign,
    new_position_symbol: str,
    new_position_direction: Literal["long", "short"],
) -> tuple[bool, Optional[str]]:
    """
    Validate new position matches campaign currency direction.

    EUR_LONG campaign can include:
    - EUR/USD long (buy EUR, sell USD) ✅
    - EUR/GBP long (buy EUR, sell GBP) ✅
    - EUR/JPY long (buy EUR, sell JPY) ✅

    EUR_LONG campaign CANNOT include:
    - EUR/USD short (sell EUR, buy USD) ❌ opposite direction
    - GBP/USD long (buy GBP, sell USD) ❌ different currency

    Args:
        campaign: Active forex currency campaign
        new_position_symbol: Forex pair symbol
        new_position_direction: Position direction

    Returns:
        (is_valid, error_message)

    Examples:
        >>> campaign = ForexCurrencyCampaign(currency="EUR", direction="LONG", ...)
        >>> validate_position_matches_campaign(campaign, "EUR/USD", "long")
        (True, None)  # Buys EUR

        >>> validate_position_matches_campaign(campaign, "EUR/USD", "short")
        (False, "Position mismatch: EUR_LONG_2024_03_15 is long EUR, but EUR/USD short buys USD")

        >>> validate_position_matches_campaign(campaign, "GBP/USD", "long")
        (False, "Position mismatch: EUR_LONG_2024_03_15 is long EUR, but GBP/USD long buys GBP")
    """
    try:
        bought_currency, sold_currency = extract_currency_exposure(
            new_position_symbol, new_position_direction
        )
    except ValueError as e:
        return False, str(e)

    # Check if position matches campaign direction
    if campaign.direction == "LONG":
        # Campaign is long {currency}, new position must buy {currency}
        if bought_currency == campaign.currency:
            return True, None
        else:
            return False, (
                f"Position mismatch: {campaign.campaign_id} is long {campaign.currency}, "
                f"but {new_position_symbol} {new_position_direction} buys {bought_currency}"
            )

    else:  # SHORT
        # Campaign is short {currency}, new position must sell {currency}
        if sold_currency == campaign.currency:
            return True, None
        else:
            return False, (
                f"Position mismatch: {campaign.campaign_id} is short {campaign.currency}, "
                f"but {new_position_symbol} {new_position_direction} sells {sold_currency}"
            )


def validate_volume_for_campaign_addition(
    campaign: ForexCurrencyCampaign, new_position: ForexPosition, new_position_volume_ratio: Decimal
) -> tuple[bool, Optional[str]]:
    """
    Validate new position has volume confirmation matching campaign trend.

    CRITICAL ADDITION (Wyckoff Team Review 2025-11-17):
    Volume requirements by entry type prevent adding positions without
    proper volume confirmation.

    Volume requirements:
    - FIRST (Spring):  <0.8x avg (low volume test)
    - CONFIRM (SOS):   ≥1.5x avg (high volume breakout) ← CRITICAL
    - ADDON:           ≥1.2x avg (above-average continuation)

    Args:
        campaign: Active forex currency campaign
        new_position: Position to add to campaign
        new_position_volume_ratio: Current bar volume / 20-bar avg volume

    Returns:
        (is_valid, error_message)

    Examples:
        >>> campaign = ForexCurrencyCampaign(...)
        >>> position = ForexPosition(symbol="EUR/USD", entry_type="CONFIRM", ...)
        >>> validate_volume_for_campaign_addition(campaign, position, Decimal("1.6"))
        (True, None)  # 1.6x avg volume >= 1.5x requirement

        >>> validate_volume_for_campaign_addition(campaign, position, Decimal("0.9"))
        (False, "Insufficient volume for SOS entry in EUR/USD: 0.9x avg (minimum 1.5x required for confirmation)")

        >>> position_spring = ForexPosition(symbol="EUR/GBP", entry_type="FIRST", ...)
        >>> validate_volume_for_campaign_addition(campaign, position_spring, Decimal("0.9"))
        (False, "Spring entry volume too high for EUR/GBP: 0.9x avg (should be <0.8x for test)")
    """
    entry_type = new_position.entry_type

    # Volume requirements by entry type
    if entry_type == "FIRST":  # Spring entry
        if new_position_volume_ratio > FIRST_ENTRY_MAX_VOLUME:
            return False, (
                f"Spring entry volume too high for {new_position.symbol}: "
                f"{new_position_volume_ratio}x avg (should be <{FIRST_ENTRY_MAX_VOLUME}x for test)"
            )

    elif entry_type == "CONFIRM":  # SOS entry
        if new_position_volume_ratio < CONFIRM_MIN_VOLUME:
            return False, (
                f"Insufficient volume for SOS entry in {new_position.symbol}: "
                f"{new_position_volume_ratio}x avg (minimum {CONFIRM_MIN_VOLUME}x required for confirmation)"
            )

    elif entry_type == "ADDON":  # Continuation entry
        if new_position_volume_ratio < ADDON_MIN_VOLUME:
            return False, (
                f"Insufficient volume for continuation entry in {new_position.symbol}: "
                f"{new_position_volume_ratio}x avg (minimum {ADDON_MIN_VOLUME}x required)"
            )

    else:
        return False, f"Invalid entry type: {entry_type}"

    return True, None


# =============================================================================
# CAMPAIGN LIFECYCLE MANAGEMENT
# =============================================================================


def add_position_to_campaign(
    campaign: ForexCurrencyCampaign, new_position: ForexPosition, volume_ratio: Decimal
) -> tuple[bool, Optional[str]]:
    """
    Add position to existing campaign with validation.

    Validates:
    1. Currency direction matches campaign
    2. Volume confirmation for entry type (CRITICAL: Wyckoff team required)
    3. BMAD allocation limits not exceeded
    4. Campaign risk limit not exceeded

    Args:
        campaign: Active forex currency campaign
        new_position: Position to add
        volume_ratio: Current bar volume / 20-bar avg volume

    Returns:
        (is_valid, error_message)

    Example:
        >>> campaign = ForexCurrencyCampaign(
        ...     currency="EUR",
        ...     direction="LONG",
        ...     total_risk_pct=Decimal("3.0"),
        ...     positions=[...]
        ... )
        >>> position = ForexPosition(
        ...     symbol="EUR/USD",
        ...     direction="long",
        ...     entry_type="CONFIRM",
        ...     position_risk_pct=Decimal("1.5"),
        ...     ...
        ... )
        >>> add_position_to_campaign(campaign, position, Decimal("1.8"))
        (True, None)  # Currency matches, volume confirmed (1.8x >= 1.5x), within limits
    """
    # 1. Currency direction validation
    is_valid, error_msg = validate_position_matches_campaign(
        campaign, new_position.symbol, new_position.direction
    )
    if not is_valid:
        return False, error_msg

    # 2. Volume validation (CRITICAL: Wyckoff team required)
    is_valid, error_msg = validate_volume_for_campaign_addition(
        campaign, new_position, volume_ratio
    )
    if not is_valid:
        return False, error_msg

    # 3. BMAD allocation validation
    is_valid, error_msg = validate_forex_bmad_allocation(
        campaign,
        new_position.entry_type,  # type: ignore
        new_position.position_risk_pct,
    )
    if not is_valid:
        return False, error_msg

    # 4. Campaign risk limit validation
    new_total_risk = campaign.total_risk_pct + new_position.position_risk_pct
    if new_total_risk > MAX_FOREX_CAMPAIGN_RISK:
        return False, (
            f"Campaign risk limit exceeded: {new_total_risk}% > {MAX_FOREX_CAMPAIGN_RISK}% "
            f"(campaign {campaign.campaign_id})"
        )

    # All validations passed - add position
    new_position.campaign_id = campaign.campaign_id
    campaign.positions.append(new_position)
    campaign.total_risk_pct = new_total_risk
    campaign.position_count += 1
    campaign.available_capacity_pct = (MAX_FOREX_CAMPAIGN_RISK - new_total_risk).quantize(
        Decimal("0.01")
    )

    logger.info(
        f"{campaign.campaign_id}: Added {new_position.symbol} {new_position.direction} "
        f"({new_position.entry_type}, {new_position.position_risk_pct}% risk, "
        f"{volume_ratio}x volume). Total risk: {new_total_risk}%"
    )

    return True, None


def create_new_campaign(
    currency: str,
    direction: Literal["LONG", "SHORT"],
    first_position: ForexPosition,
    start_date: Optional[datetime] = None,
) -> ForexCurrencyCampaign:
    """
    Create new forex currency trend campaign.

    Args:
        currency: Currency being traded ("EUR", "USD", "GBP", etc.)
        direction: "LONG" (buying currency) or "SHORT" (selling currency)
        first_position: Initial position for campaign
        start_date: Campaign start date (defaults to now)

    Returns:
        New ForexCurrencyCampaign instance

    Example:
        >>> position = ForexPosition(
        ...     symbol="EUR/USD",
        ...     direction="long",
        ...     entry_type="FIRST",
        ...     position_risk_pct=Decimal("1.0"),
        ...     ...
        ... )
        >>> campaign = create_new_campaign("EUR", "LONG", position)
        >>> campaign.campaign_id
        "EUR_LONG_2024_03_15"
        >>> campaign.total_risk_pct
        Decimal("1.0")
    """
    if start_date is None:
        start_date = datetime.now(UTC)

    campaign_id = get_campaign_id(currency, direction, start_date)

    # Set campaign_id on first position
    first_position.campaign_id = campaign_id

    campaign = ForexCurrencyCampaign(
        campaign_id=campaign_id,
        currency=currency.upper(),
        direction=direction,
        total_risk_pct=first_position.position_risk_pct,
        position_count=1,
        positions=[first_position],
        started_at=start_date,
        status="ACTIVE",
    )

    logger.info(
        f"Created {campaign_id}: {first_position.symbol} {first_position.direction} "
        f"({first_position.entry_type}, {first_position.position_risk_pct}% risk)"
    )

    return campaign
