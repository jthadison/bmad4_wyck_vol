"""
Forex Portfolio Heat Module with Weekend Gap Risk Management.

Purpose:
--------
Calculate forex portfolio heat with Wyckoff-enhanced weekend gap risk adjustments,
recognizing that forex markets close Friday 5pm ET and reopen Sunday 5pm ET (48-hour gap).

This module implements Story 7.3-FX, extending Story 7.2-FX's forex position sizing
to handle weekend gap risk with pattern/phase/volatility awareness.

Key Differences from Stock Portfolio Heat:
-------------------------------------------
Stock Markets:
- Closed overnight and weekends (predictable)
- Gaps rare (earnings announcements, major news)
- Portfolio heat = sum of individual position risks
- No weekend adjustment needed

Forex Weekend Gap Risk:
- Markets close Friday 5pm ET, reopen Sunday 5pm ET (48-hour gap)
- Major news can occur during weekend (central bank interventions, geopolitical events)
- Sunday open can gap significantly from Friday close
- Historical examples:
  - Swiss National Bank unpegging (Jan 2015): EUR/CHF gapped -29.2%
  - Brexit referendum (June 2016): GBP/USD gapped -9.4%
  - Trump election (Nov 2016): USD/MXN gapped +12.4%
  - COVID-19 outbreak (March 2020): Multiple pairs gapped 3-5%

Wyckoff-Enhanced Weekend Risk Adjustment:
------------------------------------------
Formula: weekend_adjustment = pattern_buffer × phase_multiplier × volatility_multiplier

1. Pattern-weighted buffers (reflects structural quality):
   - Spring: 0.3% (tested support → lower gap risk)
   - LPS: 0.4% (confirmed pullback)
   - SOS: 0.6% (breakout level → higher gap vulnerability)

2. Phase-aware multipliers (reflects trend stage):
   - Phase C: 1.2x (testing phase → higher uncertainty)
   - Phase D: 1.0x (strong markup → normal risk)
   - Phase E: 1.3x (trend exhaustion → elevated reversal risk)

3. Volatility-adjusted multipliers (reflects historical gap data):
   - Major pairs: 1.0x (EUR/USD, USD/JPY)
   - Cross pairs: 1.2x-1.3x (EUR/GBP, GBP/JPY)
   - EM pairs: 1.8x-2.5x (USD/MXN, USD/TRY, EUR/CHF)

Heat Limits:
------------
- Monday-Thursday: 6% maximum portfolio heat
- Friday (after 12pm ET): 5.5% maximum portfolio heat
- Saturday-Sunday: 5.5% maximum

Selective Auto-Close Friday Option (Pattern-Aware):
----------------------------------------------------
Honors "let winners run, cut losers short" with Wyckoff context:
- CLOSE: Losing SOS trades (high gap risk, failed breakout)
- CLOSE: Any Phase E position (trend exhaustion)
- CLOSE: All losing positions (<0R)
- KEEP: Spring winners >2R (high-quality winners at tested support)
- KEEP: Default (don't close on time alone)

Usage:
------
>>> from decimal import Decimal
>>> from datetime import datetime, timezone
>>>
>>> # Create position with Wyckoff context
>>> position = ForexPosition(
...     symbol="EUR/USD",
...     entry=Decimal("1.0850"),
...     stop=Decimal("1.0820"),
...     lot_size=Decimal("1.67"),
...     lot_type="mini",
...     position_value_usd=Decimal("18134.50"),
...     account_balance=Decimal("10000.00"),
...     pattern_type="SPRING",
...     wyckoff_phase="D"
... )
>>>
>>> # Calculate weekend-adjusted portfolio heat
>>> heat = calculate_portfolio_heat(
...     positions=[position],
...     current_time=datetime(2025, 11, 16, 16, 30, tzinfo=timezone.utc)  # Friday 4:30pm UTC
... )
>>> print(f"Base heat: {heat.base_heat_pct}%")
>>> print(f"Weekend adjustment: {heat.weekend_adjustment_pct}%")
>>> print(f"Total heat: {heat.total_heat_pct}%")

Author: Story 7.3-FX
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal, Optional

import pytz
import structlog

logger = structlog.get_logger(__name__)

# =============================================================================
# Pattern-Weighted Weekend Buffers (Task 11)
# =============================================================================

PATTERN_WEEKEND_BUFFERS: dict[str, Decimal] = {
    "SPRING": Decimal("0.3"),  # Tested support → lower gap risk
    "LPS": Decimal("0.4"),  # Pullback to confirmed support
    "SOS": Decimal("0.6"),  # Breakout level → higher gap risk
}

# =============================================================================
# Phase-Aware Multipliers (Task 12)
# =============================================================================

PHASE_WEEKEND_MULTIPLIERS: dict[str, Decimal] = {
    "C": Decimal("1.2"),  # Testing phase → higher uncertainty
    "D": Decimal("1.0"),  # Strong markup → normal risk
    "E": Decimal("1.3"),  # Trend exhaustion → elevated reversal risk
}

# =============================================================================
# Volatility-Adjusted Multipliers (Task 14)
# =============================================================================

PAIR_VOLATILITY_WEEKEND_MULTIPLIERS: dict[str, Decimal] = {
    # Tier 1: Major pairs (low weekend gap volatility)
    "EUR/USD": Decimal("1.0"),
    "USD/JPY": Decimal("1.0"),
    "GBP/USD": Decimal("1.1"),  # Brexit 2016 elevated
    "AUD/USD": Decimal("1.0"),
    "USD/CAD": Decimal("1.0"),
    # Tier 2: Cross pairs (moderate weekend gap volatility)
    "EUR/GBP": Decimal("1.2"),
    "EUR/JPY": Decimal("1.2"),
    "GBP/JPY": Decimal("1.3"),
    # Tier 3: Exotic/EM pairs (high weekend gap volatility)
    "USD/MXN": Decimal("1.8"),  # Trump election +12.4% gap
    "USD/TRY": Decimal("2.0"),  # EM political risk
    "EUR/CHF": Decimal("2.5"),  # Swiss SNB -29.2% gap
    "USD/ZAR": Decimal("1.8"),  # EM commodity risk
}

# =============================================================================
# Dynamic Heat Limits (Task 5)
# =============================================================================

WEEKDAY_HEAT_LIMIT = Decimal("6.0")  # 6% max Mon-Thu
WEEKEND_HEAT_LIMIT = Decimal("5.5")  # 5.5% max Fri-Sun

# =============================================================================
# Task 2: ForexPosition Data Model
# =============================================================================


@dataclass
class ForexPosition:
    """
    Represents an open forex position with Wyckoff context.

    Attributes:
        symbol: Currency pair (e.g., "EUR/USD")
        entry: Entry price level
        stop: Stop loss price level
        lot_size: Position size in lots (e.g., 1.67)
        lot_type: Lot type ("standard", "mini", "micro")
        position_value_usd: Total position value in USD
        account_balance: Account balance for risk% calculation
        pattern_type: Wyckoff pattern ("SPRING", "LPS", "SOS")
        wyckoff_phase: Wyckoff phase ("C", "D", "E")
        direction: Trade direction ("long" or "short")
    """

    symbol: str
    entry: Decimal
    stop: Decimal
    lot_size: Decimal
    lot_type: Literal["standard", "mini", "micro"]
    position_value_usd: Decimal
    account_balance: Decimal
    pattern_type: str = "SPRING"
    wyckoff_phase: str = "D"
    direction: Literal["long", "short"] = "long"

    @property
    def risk_pct(self) -> Decimal:
        """
        Position risk as % of account (Task 2).

        Formula:
            risk_pct = (stop_distance / entry) × (position_value / account) × 100
        """
        stop_distance = abs(self.entry - self.stop)
        risk_dollars = (stop_distance / self.entry) * self.position_value_usd
        return ((risk_dollars / self.account_balance) * Decimal("100")).quantize(Decimal("0.01"))


# =============================================================================
# Task 2: Base Portfolio Heat Calculation
# =============================================================================


def calculate_base_heat(positions: list[ForexPosition]) -> Decimal:
    """
    Calculate total portfolio heat without adjustments (AC 2, Task 2).

    Formula:
        base_heat = sum(position.risk_pct for all positions)

    Args:
        positions: List of open forex positions

    Returns:
        Decimal: Base portfolio heat % (sum of individual position risks)

    Example:
        >>> pos1 = ForexPosition(...)  # 1.5% risk
        >>> pos2 = ForexPosition(...)  # 2.0% risk
        >>> calculate_base_heat([pos1, pos2])
        Decimal('3.50')  # 3.5% total heat
    """
    total_heat = Decimal("0")
    for position in positions:
        total_heat += position.risk_pct
    return total_heat.quantize(Decimal("0.01"))


# =============================================================================
# Task 3: Weekend Gap Risk Detection
# =============================================================================


def is_friday_close_approaching(current_time: Optional[datetime] = None) -> bool:
    """
    Check if within 5 hours of Friday market close (AC 3, Task 3).

    Forex markets close Friday 5pm ET. This function returns True if:
    - Current day is Friday AND
    - Current time is after 12pm ET (within 5 hours of close)

    Args:
        current_time: Current time (UTC). If None, uses datetime.now(UTC)

    Returns:
        bool: True if Friday after 12pm ET, False otherwise

    Example:
        >>> # Friday 1pm ET (18:00 UTC)
        >>> is_friday_close_approaching(datetime(2025, 11, 14, 18, 0, tzinfo=timezone.utc))
        True
        >>> # Thursday 3pm ET
        >>> is_friday_close_approaching(datetime(2025, 11, 13, 20, 0, tzinfo=timezone.utc))
        False
    """
    if current_time is None:
        current_time = datetime.now(timezone.utc)

    # Convert to ET
    et = pytz.timezone("America/New_York")
    et_time = current_time.astimezone(et)

    # Friday (weekday == 4) after 12pm ET
    if et_time.weekday() == 4 and et_time.hour >= 12:
        return True
    return False


def is_weekend(current_time: Optional[datetime] = None) -> bool:
    """
    Check if currently weekend (AC 3, Task 3).

    Weekend defined as:
    - Saturday (all day)
    - Sunday before 5pm ET (market opens 5pm)

    Args:
        current_time: Current time (UTC). If None, uses datetime.now(UTC)

    Returns:
        bool: True if weekend, False otherwise

    Example:
        >>> # Saturday 10am ET
        >>> is_weekend(datetime(2025, 11, 15, 15, 0, tzinfo=timezone.utc))
        True
        >>> # Sunday 6pm ET (market open)
        >>> is_weekend(datetime(2025, 11, 16, 23, 0, tzinfo=timezone.utc))
        False
    """
    if current_time is None:
        current_time = datetime.now(timezone.utc)

    et = pytz.timezone("America/New_York")
    et_time = current_time.astimezone(et)

    # Saturday (weekday == 5, all day)
    if et_time.weekday() == 5:
        return True

    # Sunday (weekday == 6) before 5pm ET (market opens 5pm)
    if et_time.weekday() == 6 and et_time.hour < 17:
        return True

    return False


def positions_held_over_weekend(
    positions: list[ForexPosition], current_time: Optional[datetime] = None
) -> bool:
    """
    Check if positions will be held over weekend (AC 3, Task 3).

    Args:
        positions: List of open positions
        current_time: Current time (UTC)

    Returns:
        bool: True if positions exist AND (Friday close approaching OR weekend)

    Example:
        >>> positions = [ForexPosition(...)]
        >>> # Friday 4pm ET
        >>> positions_held_over_weekend(positions, datetime(2025, 11, 14, 21, 0, tzinfo=timezone.utc))
        True
    """
    return len(positions) > 0 and (
        is_friday_close_approaching(current_time) or is_weekend(current_time)
    )


# =============================================================================
# Task 11-14: Pattern/Phase/Volatility-Aware Weekend Adjustment
# =============================================================================


def calculate_weekend_adjustment_volatility_aware(
    positions: list[ForexPosition], current_time: Optional[datetime] = None
) -> tuple[Decimal, dict[str, Decimal], dict[str, Decimal], dict[str, Decimal]]:
    """
    Calculate full pattern/phase/volatility-aware weekend adjustment (AC 4, Tasks 11-14).

    Formula:
        position_adjustment = pattern_buffer × phase_multiplier × volatility_multiplier
        weekend_adjusted_heat = base_heat + sum(position_adjustments)

    Args:
        positions: List of open forex positions
        current_time: Current time (UTC)

    Returns:
        tuple[Decimal, dict, dict, dict]: (
            total_weekend_adjustment,
            pattern_breakdown,
            phase_breakdown,
            volatility_breakdown
        )

    Example:
        >>> # 3 positions held over weekend
        >>> adj, pattern_bd, phase_bd, vol_bd = calculate_weekend_adjustment_volatility_aware(positions)
        >>> # EUR/USD Spring Phase D: 0.3% × 1.0 × 1.0 = 0.30%
        >>> # GBP/USD SOS Phase E: 0.6% × 1.3 × 1.1 = 0.86%
        >>> # USD/MXN LPS Phase D: 0.4% × 1.0 × 1.8 = 0.72%
        >>> # Total: 1.88%
    """
    if not positions_held_over_weekend(positions, current_time):
        return Decimal("0"), {}, {}, {}

    total_adjustment = Decimal("0")
    pattern_breakdown: dict[str, Decimal] = {}
    phase_breakdown: dict[str, Decimal] = {}
    volatility_breakdown: dict[str, Decimal] = {}

    for position in positions:
        # Pattern buffer (Task 11)
        pattern_buffer = PATTERN_WEEKEND_BUFFERS.get(position.pattern_type, Decimal("0.5"))

        # Phase multiplier (Task 12)
        phase_multiplier = PHASE_WEEKEND_MULTIPLIERS.get(position.wyckoff_phase, Decimal("1.0"))

        # Volatility multiplier (Task 14)
        volatility_multiplier = PAIR_VOLATILITY_WEEKEND_MULTIPLIERS.get(
            position.symbol, Decimal("1.0")
        )

        # Calculate position adjustment
        position_adjustment = pattern_buffer * phase_multiplier * volatility_multiplier
        total_adjustment += position_adjustment

        # Track breakdowns for transparency
        pattern_key = f"{position.symbol}_{position.pattern_type}"
        pattern_breakdown[pattern_key] = position_adjustment

        phase_key = f"{position.wyckoff_phase}"
        phase_breakdown[phase_key] = phase_breakdown.get(phase_key, Decimal("0")) + position_adjustment

        vol_key = position.symbol
        volatility_breakdown[vol_key] = position_adjustment

    return (
        total_adjustment.quantize(Decimal("0.01")),
        pattern_breakdown,
        phase_breakdown,
        volatility_breakdown,
    )


# =============================================================================
# Task 5: Dynamic Heat Limits
# =============================================================================


def get_max_heat_limit(current_time: Optional[datetime] = None) -> Decimal:
    """
    Get maximum allowed portfolio heat based on day of week (AC 5, Task 5).

    Args:
        current_time: Current time (UTC)

    Returns:
        Decimal: 6.0% (Mon-Thu) or 5.5% (Fri-Sun)

    Example:
        >>> # Monday
        >>> get_max_heat_limit(datetime(2025, 11, 10, 15, 0, tzinfo=timezone.utc))
        Decimal('6.0')
        >>> # Friday 4pm ET
        >>> get_max_heat_limit(datetime(2025, 11, 14, 21, 0, tzinfo=timezone.utc))
        Decimal('5.5')
    """
    if is_friday_close_approaching(current_time) or is_weekend(current_time):
        return WEEKEND_HEAT_LIMIT
    return WEEKDAY_HEAT_LIMIT


def validate_heat_limit(
    total_heat: Decimal, current_time: Optional[datetime] = None
) -> tuple[bool, Optional[str]]:
    """
    Validate portfolio heat within limits (AC 5, Task 5).

    Args:
        total_heat: Total portfolio heat %
        current_time: Current time (UTC)

    Returns:
        tuple[bool, Optional[str]]: (is_valid, error_message)

    Example:
        >>> # Monday 4% heat
        >>> validate_heat_limit(Decimal("4.0"))
        (True, None)
        >>> # Friday 5.8% heat
        >>> validate_heat_limit(Decimal("5.8"), friday_time)
        (False, 'Portfolio heat 5.8% exceeds limit 5.5%')
    """
    max_limit = get_max_heat_limit(current_time)

    if total_heat > max_limit:
        return False, f"Portfolio heat {total_heat}% exceeds limit {max_limit}%"

    return True, None


# =============================================================================
# Task 6: Weekend Hold Warnings
# =============================================================================


def generate_weekend_warning(
    base_heat: Decimal,
    total_heat: Decimal,
    num_positions: int,
    current_time: Optional[datetime] = None,
) -> Optional[str]:
    """
    Generate warning if holding positions into weekend (AC 6, Task 6).

    Args:
        base_heat: Base portfolio heat %
        total_heat: Total portfolio heat % (with weekend adjustment)
        num_positions: Number of open positions
        current_time: Current time (UTC)

    Returns:
        Optional[str]: Warning message if applicable

    Example:
        >>> # Friday 4pm, 4.5% base heat → 6.0% adjusted
        >>> generate_weekend_warning(Decimal("4.5"), Decimal("6.0"), 3, friday_4pm)
        'WARNING: Holding 3 positions into weekend (4.5% base heat → 6.0% weekend-adjusted)...'
    """
    if not is_friday_close_approaching(current_time):
        return None

    et = pytz.timezone("America/New_York")
    et_time = current_time.astimezone(et) if current_time else datetime.now(timezone.utc).astimezone(et)

    # Warning after 3pm if heat >4%
    if et_time.hour >= 15 and base_heat > Decimal("4.0"):
        return (
            f"WARNING: Holding {num_positions} positions into weekend "
            f"({base_heat}% base heat → {total_heat}% weekend-adjusted). "
            f"Consider closing positions or reducing size."
        )

    # Block new positions if adjusted heat >5.5%
    if total_heat > WEEKEND_HEAT_LIMIT:
        return (
            f"BLOCKED: Cannot open new position. Weekend-adjusted heat "
            f"({total_heat}%) exceeds Friday limit ({WEEKEND_HEAT_LIMIT}%)."
        )

    return None


# =============================================================================
# Task 13: Selective Auto-Close (Pattern-Aware)
# =============================================================================


@dataclass
class SelectiveAutoCloseConfig:
    """
    Configuration for selective auto-close Friday option (AC 7, Task 13).

    Attributes:
        enabled: Enable selective auto-close
        close_time_et: Hour in ET to close positions (default 16 = 4pm)
        always_close_patterns: Pattern types always closed (default ["SOS"])
        never_close_patterns: Pattern types never closed if profitable (default ["SPRING"])
        close_losers_below_r: Close positions below this R-multiple (default 0.0)
        keep_winners_above_r: Keep positions above this R-multiple (default 2.0)
    """

    enabled: bool = False
    close_time_et: int = 16  # 4:30pm ET (30 min before close)
    always_close_patterns: list[str] = field(default_factory=lambda: ["SOS"])
    never_close_patterns: list[str] = field(default_factory=lambda: ["SPRING"])
    close_losers_below_r: Decimal = Decimal("0.0")
    keep_winners_above_r: Decimal = Decimal("2.0")


def calculate_r_multiple(position: ForexPosition, current_price: Decimal) -> Decimal:
    """
    Calculate position's R-multiple (AC 7, Task 13).

    R-multiple = current_pnl / initial_risk

    Args:
        position: Open forex position
        current_price: Current market price

    Returns:
        Decimal: R-multiple (e.g., +2.5R for 2.5× initial risk profit)

    Example:
        >>> # Long EUR/USD: entry 1.0850, stop 1.0820, current 1.0910
        >>> # Initial risk: 30 pips, Current profit: 60 pips → 2.0R
        >>> calculate_r_multiple(position, Decimal("1.0910"))
        Decimal('2.0')
    """
    entry = position.entry
    stop = position.stop
    initial_risk = abs(entry - stop)

    if position.direction == "long":
        current_pnl = current_price - entry
    else:  # short
        current_pnl = entry - current_price

    if initial_risk > 0:
        r_multiple = current_pnl / initial_risk
        return r_multiple.quantize(Decimal("0.1"))
    return Decimal("0")


def should_auto_close_position(
    position: ForexPosition,
    config: SelectiveAutoCloseConfig,
    current_price: Decimal,
    current_time: Optional[datetime] = None,
) -> tuple[bool, str]:
    """
    Selective Friday close based on Wyckoff criteria (AC 7, Task 13).

    Decision Rules (honors "let winners run, cut losers short"):
    1. Always close: Losing SOS trades (high gap risk, failed breakout)
    2. Never close: Spring trades >2R (high-quality winners at tested support)
    3. Always close: Any Phase E position (trend exhaustion risk)
    4. Always close: Any losing position <0R (reduce weekend risk)
    5. Default: Keep position (don't close on time alone)

    Args:
        position: Open forex position
        config: Selective auto-close configuration
        current_price: Current market price
        current_time: Current time (UTC)

    Returns:
        tuple[bool, str]: (should_close, reason)

    Example:
        >>> # Losing SOS
        >>> should_auto_close_position(sos_position, config, current_price, friday_4pm)
        (True, "Losing SOS (high gap risk)")
        >>> # Spring winner +5R
        >>> should_auto_close_position(spring_position, config, current_price, friday_4pm)
        (False, "Spring winner >2R (let run)")
    """
    if not config.enabled:
        return False, ""

    if current_time is None:
        current_time = datetime.now(timezone.utc)

    et = pytz.timezone("America/New_York")
    et_time = current_time.astimezone(et)

    # Check if Friday at close time
    if et_time.weekday() != 4 or et_time.hour < config.close_time_et:
        return False, ""

    # Additional check: must be after 4:30pm ET if close_time_et == 16
    if config.close_time_et == 16 and et_time.minute < 30:
        return False, ""

    r_multiple = calculate_r_multiple(position, current_price)

    # Rule 1: Always close losing SOS trades
    if position.pattern_type == "SOS" and r_multiple < Decimal("0.0"):
        return True, "Losing SOS (high gap risk)"

    # Rule 2: Never close profitable Spring trades >2R
    if position.pattern_type == "SPRING" and r_multiple > config.keep_winners_above_r:
        return False, "Spring winner >2R (let run)"

    # Rule 3: Close all Phase E positions
    if position.wyckoff_phase == "E":
        return True, "Phase E exhaustion risk"

    # Rule 4: Close any losing position
    if r_multiple < config.close_losers_below_r:
        return True, "Losing position"

    return False, "Keep position"


# =============================================================================
# Task 10: Historical Gap Analysis Logging
# =============================================================================


@dataclass
class WeekendGapEvent:
    """
    Record of weekend gap occurrence (AC 10, Task 10).

    Attributes:
        symbol: Currency pair
        friday_close: Friday closing price
        sunday_open: Sunday opening price
        gap_pips: Gap size in pips
        gap_pct: Gap size as percentage
        timestamp: Event timestamp
    """

    symbol: str
    friday_close: Decimal
    sunday_open: Decimal
    gap_pips: Decimal
    gap_pct: Decimal
    timestamp: datetime


def get_pip_size(symbol: str) -> Decimal:
    """
    Get pip size for currency pair.

    Args:
        symbol: Currency pair

    Returns:
        Decimal: Pip size (0.0001 for 4-decimal, 0.01 for JPY pairs)
    """
    if "JPY" in symbol:
        return Decimal("0.01")
    return Decimal("0.0001")


def log_weekend_gap(
    symbol: str, friday_close: Decimal, sunday_open: Decimal
) -> Optional[WeekendGapEvent]:
    """
    Log weekend gap if >1% (AC 10, Task 10).

    Args:
        symbol: Currency pair
        friday_close: Friday closing price
        sunday_open: Sunday opening price

    Returns:
        Optional[WeekendGapEvent]: Gap event if >1%, None otherwise

    Example:
        >>> # EUR/USD: Friday 1.0850 → Sunday 1.0790 (-60 pips, -0.55%)
        >>> log_weekend_gap("EUR/USD", Decimal("1.0850"), Decimal("1.0790"))
        WeekendGapEvent(...)
        >>> # Small gap <1% → None
        >>> log_weekend_gap("EUR/USD", Decimal("1.0850"), Decimal("1.0848"))
        None
    """
    gap = sunday_open - friday_close
    gap_pct = (gap / friday_close) * Decimal("100")

    # Only log significant gaps (>1%)
    if abs(gap_pct) < Decimal("1.0"):
        return None

    # Calculate pips
    pip_size = get_pip_size(symbol)
    gap_pips = gap / pip_size

    event = WeekendGapEvent(
        symbol=symbol,
        friday_close=friday_close,
        sunday_open=sunday_open,
        gap_pips=gap_pips,
        gap_pct=gap_pct,
        timestamp=datetime.now(timezone.utc),
    )

    # Log to system
    logger.warning(
        "WEEKEND GAP",
        symbol=symbol,
        friday_close=str(friday_close),
        sunday_open=str(sunday_open),
        gap_pips=f"{gap_pips:+.0f}",
        gap_pct=f"{gap_pct:+.2f}%",
    )

    return event


# =============================================================================
# Task 8: ForexPortfolioHeat Data Model
# =============================================================================


@dataclass
class ForexPortfolioHeat:
    """
    Forex portfolio heat calculation with weekend adjustment (AC 8, Task 8).

    Attributes:
        base_heat_pct: Base heat % (without weekend adjustment)
        weekend_adjustment_pct: Weekend adjustment % (pattern/phase/volatility-weighted)
        total_heat_pct: Total heat % (base + weekend adjustment)
        max_heat_limit_pct: Maximum heat limit % (6.0% or 5.5% depending on day)
        num_positions: Number of open positions
        positions_held_over_weekend: True if positions held over weekend
        is_friday_close_approaching: True if Friday after 12pm ET
        is_weekend: True if Saturday/Sunday
        warning: Warning message if applicable
        created_at: Creation timestamp
        pattern_breakdown: Pattern-level breakdown for transparency
        phase_breakdown: Phase-level breakdown for transparency
        volatility_breakdown: Volatility-level breakdown for transparency
    """

    base_heat_pct: Decimal
    weekend_adjustment_pct: Decimal
    total_heat_pct: Decimal
    max_heat_limit_pct: Decimal
    num_positions: int
    positions_held_over_weekend: bool
    is_friday_close_approaching: bool
    is_weekend: bool
    warning: Optional[str] = None
    created_at: Optional[datetime] = None
    pattern_breakdown: Optional[dict[str, Decimal]] = None
    phase_breakdown: Optional[dict[str, Decimal]] = None
    volatility_breakdown: Optional[dict[str, Decimal]] = None

    def __post_init__(self) -> None:
        """Initialize computed fields."""
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)

    @property
    def heat_utilization_pct(self) -> Decimal:
        """
        Percentage of max heat limit used.

        Returns:
            Decimal: Heat utilization % (e.g., 81.8% if 4.5% / 5.5%)
        """
        if self.max_heat_limit_pct == 0:
            return Decimal("0")
        return ((self.total_heat_pct / self.max_heat_limit_pct) * Decimal("100")).quantize(
            Decimal("0.1")
        )

    @property
    def can_add_position(self) -> bool:
        """
        Check if room to add another position.

        Assumes new position adds ~2% risk + 0.5% weekend buffer.

        Returns:
            bool: True if room for new position, False otherwise
        """
        # Assume new position adds ~2% risk + 0.5% weekend buffer
        estimated_new_heat = self.total_heat_pct + Decimal("2.5")
        return estimated_new_heat <= self.max_heat_limit_pct


# =============================================================================
# Task 9: Integration with Position Opening
# =============================================================================


def calculate_portfolio_heat(
    positions: list[ForexPosition], current_time: Optional[datetime] = None
) -> ForexPortfolioHeat:
    """
    Calculate current portfolio heat with weekend adjustment.

    Args:
        positions: List of open forex positions
        current_time: Current time (UTC)

    Returns:
        ForexPortfolioHeat: Portfolio heat calculation result

    Example:
        >>> heat = calculate_portfolio_heat(positions, friday_4pm)
        >>> print(f"Total heat: {heat.total_heat_pct}%")
        >>> print(f"Heat utilization: {heat.heat_utilization_pct}%")
    """
    # Calculate base heat
    base_heat = calculate_base_heat(positions)

    # Calculate weekend adjustment
    is_weekend_hold = positions_held_over_weekend(positions, current_time)
    weekend_adj, pattern_bd, phase_bd, vol_bd = calculate_weekend_adjustment_volatility_aware(
        positions, current_time
    )

    # Calculate total heat
    total_heat = base_heat + weekend_adj

    # Get max limit
    max_limit = get_max_heat_limit(current_time)

    # Generate warning
    warning = generate_weekend_warning(base_heat, total_heat, len(positions), current_time)

    return ForexPortfolioHeat(
        base_heat_pct=base_heat,
        weekend_adjustment_pct=weekend_adj,
        total_heat_pct=total_heat,
        max_heat_limit_pct=max_limit,
        num_positions=len(positions),
        positions_held_over_weekend=is_weekend_hold,
        is_friday_close_approaching=is_friday_close_approaching(current_time),
        is_weekend=is_weekend(current_time),
        warning=warning,
        pattern_breakdown=pattern_bd,
        phase_breakdown=phase_bd,
        volatility_breakdown=vol_bd,
    )


def calculate_portfolio_heat_after_new_position(
    current_positions: list[ForexPosition],
    new_position_risk_pct: Decimal,
    new_position: Optional[ForexPosition] = None,
    current_time: Optional[datetime] = None,
) -> ForexPortfolioHeat:
    """
    Calculate portfolio heat including proposed new position (AC 9, Task 9).

    Args:
        current_positions: List of current open positions
        new_position_risk_pct: Risk % of new position
        new_position: Optional new position object (for pattern/phase context)
        current_time: Current time (UTC)

    Returns:
        ForexPortfolioHeat: Portfolio heat with new position included

    Example:
        >>> # 2 positions (4%), new position (2%), Friday
        >>> heat = calculate_portfolio_heat_after_new_position(positions, Decimal("2.0"), friday)
        >>> # 6% base + 1.5% weekend adj = 7.5% > 5.5% → REJECTED
    """
    # Calculate current heat
    base_heat = calculate_base_heat(current_positions)

    # Add new position risk
    new_base_heat = base_heat + new_position_risk_pct

    # Check weekend adjustment
    # Create a temporary position list including new position
    temp_positions = current_positions.copy()
    if new_position:
        temp_positions.append(new_position)

    num_positions = len(current_positions) + 1
    is_weekend_hold = positions_held_over_weekend(current_positions, current_time)

    # Calculate weekend adjustment with new position
    weekend_adj, pattern_bd, phase_bd, vol_bd = calculate_weekend_adjustment_volatility_aware(
        temp_positions, current_time
    )

    total_heat = new_base_heat + weekend_adj
    max_limit = get_max_heat_limit(current_time)

    warning = None
    if total_heat > max_limit:
        warning = (
            f"REJECTED: New position would increase weekend heat to {total_heat}% "
            f"(limit: {max_limit}%)"
        )

    return ForexPortfolioHeat(
        base_heat_pct=new_base_heat,
        weekend_adjustment_pct=weekend_adj,
        total_heat_pct=total_heat,
        max_heat_limit_pct=max_limit,
        num_positions=num_positions,
        positions_held_over_weekend=is_weekend_hold,
        is_friday_close_approaching=is_friday_close_approaching(current_time),
        is_weekend=is_weekend(current_time),
        warning=warning,
        pattern_breakdown=pattern_bd,
        phase_breakdown=phase_bd,
        volatility_breakdown=vol_bd,
    )


def can_open_new_position(
    current_positions: list[ForexPosition],
    new_position_risk_pct: Decimal,
    new_position: Optional[ForexPosition] = None,
    current_time: Optional[datetime] = None,
) -> tuple[bool, Optional[str]]:
    """
    Validate if new position can be opened (AC 9, Task 9).

    Args:
        current_positions: List of current open positions
        new_position_risk_pct: Risk % of new position
        new_position: Optional new position object
        current_time: Current time (UTC)

    Returns:
        tuple[bool, Optional[str]]: (can_open, warning_message)

    Example:
        >>> # 2 positions (4%), new position (2%), Friday
        >>> can_open, msg = can_open_new_position(positions, Decimal("2.0"), None, friday)
        >>> print(can_open)
        False
        >>> print(msg)
        'REJECTED: New position would increase weekend heat to 7.5% (limit: 5.5%)'
    """
    heat = calculate_portfolio_heat_after_new_position(
        current_positions, new_position_risk_pct, new_position, current_time
    )

    if heat.warning:
        return False, heat.warning

    return True, None
