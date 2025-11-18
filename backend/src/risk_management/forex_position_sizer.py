"""
Forex Position Sizing Module with Wyckoff Methodology Integration.

Purpose:
--------
Calculate forex position sizes using lot/pip mechanics integrated with Wyckoff
pattern-specific risk allocation, volume analysis, and session-based adjustments.

This module implements Story 7.2-FX, extending Story 7.1's Wyckoff risk framework
to forex markets using pip-based calculations, margin validation, and spread adjustments.

Key Differences from Stock Position Sizing:
--------------------------------------------
Stock: position_size = (account × risk%) / (entry - stop)
Forex: lot_size = (account × effective_risk%) / (stop_pips × pip_value)

Wyckoff Integration:
-------------------
1. Pattern-Specific Base Risk (from Story 7.1):
   - Spring (SPRING): 0.5% base risk (tight stops, high R:R)
   - Sign of Strength (SOS): 0.8% base risk (wider stops, breakout)
   - Last Point of Support (LPS): 0.7% base risk (confirmation entry)

2. Volume-Adjusted Risk (Law #3: Effort vs Result):
   - Tick volume ratio determines multiplier: 0.70x - 1.00x
   - Climactic volume (≥2.5x) = full allocation (1.00x)
   - Weak volume (<1.5x) = reduced allocation (0.70x)

3. Session-Based Risk (Institutional Participation):
   - London/NY overlap (12:00-16:00 UTC): 1.00x multiplier
   - Single major session: 0.90x multiplier
   - Asian session: 0.75x multiplier

4. Effective Risk Formula:
   effective_risk = base_risk × volume_multiplier × session_multiplier
   lot_size = (account × effective_risk) / (stop_pips × pip_value)

Forex Mechanics:
----------------
- Pip sizes: 4-decimal (0.0001) for majors, 2-decimal (0.01) for JPY pairs
- Spread adjustment: structural_stop + (spread/2) prevents premature stop-outs
- Pattern-specific pip stops: Spring 20-50 pips, SOS 50-100 pips, LPS 25-60 pips
- Margin validation: required_margin < 50% of account (over-leverage protection)
- Lot types: Standard (100k), Mini (10k), Micro (1k)

Usage:
------
>>> from decimal import Decimal
>>> from datetime import datetime, UTC
>>>
>>> # Calculate Wyckoff-integrated forex position size
>>> lot_size, details = calculate_forex_lot_size_with_wyckoff_adjustments(
...     account_balance=Decimal("10000.00"),
...     pattern_type="SPRING",
...     stop_loss_pips=Decimal("30.0"),
...     pip_value_per_lot=Decimal("1.00"),  # EUR/USD mini lot
...     tick_volume=2500,
...     avg_tick_volume=1000,
...     signal_timestamp=datetime(2025, 11, 16, 14, 0, tzinfo=UTC),
...     symbol="EUR/USD",
...     lot_type="mini"
... )
>>> print(f"Lot size: {lot_size} mini lots")
>>> print(f"Effective risk: {details['effective_risk_percent']}%")

Author: Story 7.2-FX
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_DOWN, Decimal
from typing import Literal, Optional

import structlog

logger = structlog.get_logger(__name__)

# =============================================================================
# Task 2: Pip Configuration & Spread Adjustment
# =============================================================================

# Pip sizes for major currency pairs (AC 2)
PIP_SIZES: dict[str, Decimal] = {
    # 4-decimal pairs (most majors)
    "EUR/USD": Decimal("0.0001"),
    "GBP/USD": Decimal("0.0001"),
    "AUD/USD": Decimal("0.0001"),
    "NZD/USD": Decimal("0.0001"),
    "EUR/GBP": Decimal("0.0001"),
    "EUR/AUD": Decimal("0.0001"),
    # 2-decimal pairs (JPY pairs)
    "USD/JPY": Decimal("0.01"),
    "EUR/JPY": Decimal("0.01"),
    "GBP/JPY": Decimal("0.01"),
    "AUD/JPY": Decimal("0.01"),
    "USD/CAD": Decimal("0.0001"),
    "USD/CHF": Decimal("0.0001"),
    "NZD/JPY": Decimal("0.01"),
}

# Typical broker spreads in pips (AC 10, Task 2)
TYPICAL_SPREADS: dict[str, Decimal] = {
    # Major pairs (low spread)
    "EUR/USD": Decimal("1.5"),
    "GBP/USD": Decimal("2.0"),
    "USD/JPY": Decimal("1.0"),
    "AUD/USD": Decimal("1.8"),
    "USD/CAD": Decimal("2.0"),
    "USD/CHF": Decimal("1.5"),
    # Cross pairs (higher spread)
    "EUR/JPY": Decimal("2.5"),
    "GBP/JPY": Decimal("3.0"),
    "EUR/GBP": Decimal("2.0"),
    "AUD/JPY": Decimal("2.5"),
    "NZD/USD": Decimal("2.2"),
    "NZD/JPY": Decimal("3.0"),
}


def get_pip_size(symbol: str) -> Decimal:
    """
    Get pip size for currency pair (AC 2).

    Args:
        symbol: Currency pair (e.g., "EUR/USD", "USD/JPY")

    Returns:
        Decimal: Pip size (0.0001 for 4-decimal, 0.01 for 2-decimal pairs)

    Example:
        >>> get_pip_size("EUR/USD")
        Decimal('0.0001')
        >>> get_pip_size("USD/JPY")
        Decimal('0.01')
    """
    if symbol in PIP_SIZES:
        return PIP_SIZES[symbol]

    # Default: 4 decimals for pairs with USD, 2 for JPY
    if "JPY" in symbol:
        return Decimal("0.01")
    return Decimal("0.0001")


def adjust_stop_for_spread(
    structural_stop: Decimal,
    entry_price: Decimal,
    symbol: str,
    direction: Literal["long", "short"],
) -> Decimal:
    """
    Adjust Wyckoff structural stop for forex broker spread (AC 10, Task 2).

    Wyckoff Principle: Stops must be at structural levels (support/resistance).
    Forex Reality: Broker spread can cause premature stop-outs.
    Solution: Widen stop by half the spread to create buffer zone.

    Args:
        structural_stop: Original structural stop level
        entry_price: Entry price level
        symbol: Currency pair (e.g., "EUR/USD")
        direction: Trade direction ("long" or "short")

    Returns:
        Decimal: Spread-adjusted stop level

    Example:
        >>> # EUR/USD long: structural stop 1.0820, spread 1.5 pips
        >>> adjust_stop_for_spread(
        ...     Decimal("1.0820"), Decimal("1.0850"), "EUR/USD", "long"
        ... )
        Decimal('1.08193')  # Widened by 0.75 pips (half of 1.5)
    """
    spread_pips = TYPICAL_SPREADS.get(symbol, Decimal("2.0"))
    pip_size = get_pip_size(symbol)
    spread_distance = spread_pips * pip_size
    spread_buffer = spread_distance / Decimal("2")

    if direction == "long":
        adjusted_stop = structural_stop - spread_buffer
    else:  # short
        adjusted_stop = structural_stop + spread_buffer

    return adjusted_stop


def calculate_stop_pips_with_spread(
    entry: Decimal,
    structural_stop: Decimal,
    symbol: str,
    direction: Literal["long", "short"],
) -> Decimal:
    """
    Calculate stop loss in pips including spread adjustment (AC 2, Task 2).

    Args:
        entry: Entry price
        structural_stop: Original structural stop level
        symbol: Currency pair
        direction: Trade direction

    Returns:
        Decimal: Stop distance in pips (rounded to 0.1 pip)

    Example:
        >>> # EUR/USD: entry 1.0850, structural stop 1.0820 (30 pips)
        >>> # Spread adjustment: +0.75 pips → 30.75 pips total
        >>> calculate_stop_pips_with_spread(
        ...     Decimal("1.0850"), Decimal("1.0820"), "EUR/USD", "long"
        ... )
        Decimal('30.8')  # 30 pips structural + 0.75 spread adjustment
    """
    adjusted_stop = adjust_stop_for_spread(structural_stop, entry, symbol, direction)
    stop_distance = abs(entry - adjusted_stop)
    pip_size = get_pip_size(symbol)
    stop_pips = stop_distance / pip_size
    return stop_pips.quantize(Decimal("0.1"), rounding=ROUND_DOWN)


# =============================================================================
# Task 3: Pip Value Calculation
# =============================================================================


def calculate_pip_value(
    symbol: str,
    lot_type: Literal["standard", "mini", "micro"],
    account_currency: str = "USD",
    exchange_rates: Optional[dict[str, Decimal]] = None,
) -> Decimal:
    """
    Calculate pip value in account currency (AC 3, Task 3).

    Pip Value Formula:
    ------------------
    For EUR/USD traded in USD account:
    - Standard lot (100k EUR): 1 pip = $10.00
    - Mini lot (10k EUR): 1 pip = $1.00
    - Micro lot (1k EUR): 1 pip = $0.10

    For USD/JPY traded in USD account:
    - Standard lot (100k USD): 1 pip = ~$9.20 (varies with price)
    - Pip value = (contract_size × pip_size) / current_rate

    Args:
        symbol: Currency pair (e.g., "EUR/USD")
        lot_type: Lot type ("standard", "mini", "micro")
        account_currency: Account currency (default "USD")
        exchange_rates: Current exchange rates for conversion

    Returns:
        Decimal: Pip value per lot in account currency

    Example:
        >>> calculate_pip_value("EUR/USD", "standard", "USD")
        Decimal('10.00')  # $10 per pip for standard lot
        >>> calculate_pip_value("EUR/USD", "mini", "USD")
        Decimal('1.00')   # $1 per pip for mini lot
    """
    if exchange_rates is None:
        exchange_rates = {}

    base_currency, quote_currency = symbol.split("/")

    # Contract sizes (AC 3)
    contract_sizes: dict[str, int] = {"standard": 100000, "mini": 10000, "micro": 1000}
    contract_size = contract_sizes[lot_type]

    pip_size = get_pip_size(symbol)

    # For pairs quoted in account currency (e.g., EUR/USD for USD account)
    if quote_currency == account_currency:
        pip_value = Decimal(contract_size) * pip_size

    # For pairs where account currency is base (e.g., USD/JPY for USD account)
    elif base_currency == account_currency:
        # Pip value varies with price
        current_rate = exchange_rates.get(symbol, Decimal("1.0"))
        if current_rate == Decimal("0"):
            current_rate = Decimal("1.0")
        pip_value = (Decimal(contract_size) * pip_size) / current_rate

    else:
        # Cross-currency conversion needed
        conversion_pair = f"{quote_currency}/{account_currency}"
        conversion_rate = exchange_rates.get(conversion_pair, Decimal("1.0"))
        pip_value = Decimal(contract_size) * pip_size * conversion_rate

    return pip_value.quantize(Decimal("0.01"), rounding=ROUND_DOWN)


# =============================================================================
# Task 4: Lot Size Calculation
# =============================================================================


def calculate_lot_size(
    account_balance: Decimal,
    risk_percent: Decimal,
    stop_loss_pips: Decimal,
    pip_value_per_lot: Decimal,
    lot_type: Literal["standard", "mini", "micro"] = "mini",
) -> Decimal:
    """
    Calculate position size in lots (AC 4, Task 4).

    Formula:
    --------
    lot_size = risk_dollars / (stop_pips × pip_value)

    Args:
        account_balance: Account equity
        risk_percent: Risk percentage (e.g., 0.5 for 0.5%)
        stop_loss_pips: Stop distance in pips
        pip_value_per_lot: Pip value per lot in account currency
        lot_type: Lot type for pip value reference

    Returns:
        Decimal: Position size in lots (rounded to 0.01 lots)

    Example:
        >>> # $10k account, 1% risk, 30 pip stop, $1/pip (mini lot)
        >>> calculate_lot_size(
        ...     Decimal("10000"), Decimal("1.0"), Decimal("30"),
        ...     Decimal("1.00"), "mini"
        ... )
        Decimal('3.33')  # 3.33 mini lots
    """
    risk_dollars = account_balance * (risk_percent / Decimal("100"))
    lot_size = risk_dollars / (stop_loss_pips * pip_value_per_lot)

    # Round to 2 decimals (0.01 lots)
    return lot_size.quantize(Decimal("0.01"), rounding=ROUND_DOWN)


# =============================================================================
# Task 5: Margin Validation
# =============================================================================


def calculate_required_margin(
    lot_size: Decimal,
    lot_type: Literal["standard", "mini", "micro"],
    symbol: str,
    leverage: Decimal,
    exchange_rates: dict[str, Decimal],
) -> Decimal:
    """
    Calculate margin requirement (AC 5, Task 5).

    Formula:
    --------
    margin = (lot_size × contract_size × current_price) / leverage

    Args:
        lot_size: Position size in lots
        lot_type: Lot type ("standard", "mini", "micro")
        symbol: Currency pair
        leverage: Account leverage (e.g., 50 for 50:1)
        exchange_rates: Current exchange rates

    Returns:
        Decimal: Required margin in account currency

    Example:
        >>> # 3.33 mini lots, EUR/USD 1.0850, 50:1 leverage
        >>> calculate_required_margin(
        ...     Decimal("3.33"), "mini", "EUR/USD", Decimal("50"),
        ...     {"EUR/USD": Decimal("1.0850")}
        ... )
        Decimal('723.11')  # $723.11 margin required
    """
    contract_sizes: dict[str, int] = {"standard": 100000, "mini": 10000, "micro": 1000}
    contract_size = contract_sizes[lot_type]

    # Get current market price
    current_price = exchange_rates.get(symbol, Decimal("1.0"))

    # Total position value in quote currency
    position_value = lot_size * Decimal(contract_size) * current_price

    # Margin required
    required_margin = position_value / leverage

    return required_margin.quantize(Decimal("0.01"), rounding=ROUND_DOWN)


def validate_margin(
    required_margin: Decimal, available_margin: Decimal
) -> tuple[bool, Optional[str]]:
    """
    Validate sufficient margin available (AC 5, Task 5).

    Args:
        required_margin: Margin required for position
        available_margin: Available account margin

    Returns:
        tuple[bool, Optional[str]]: (is_valid, warning_message)

    Example:
        >>> validate_margin(Decimal("723"), Decimal("10000"))
        (True, None)
        >>> validate_margin(Decimal("7500"), Decimal("10000"))
        (False, 'Over-leveraged: using 75.0% of margin')
    """
    if required_margin > available_margin:
        return False, f"Insufficient margin: need ${required_margin}, have ${available_margin}"

    # AC 10: Reject if margin > 50% of account (over-leveraged)
    if required_margin > (available_margin * Decimal("0.5")):
        margin_pct = (required_margin / available_margin * Decimal("100")).quantize(Decimal("0.1"))
        return False, f"Over-leveraged: using {margin_pct}% of margin (max 50%)"

    # Warning if > 20%
    if required_margin > (available_margin * Decimal("0.2")):
        margin_pct = (required_margin / available_margin * Decimal("100")).quantize(Decimal("0.1"))
        return True, f"WARNING: Using {margin_pct}% of available margin"

    return True, None


# =============================================================================
# Task 6: Lot Type Optimization
# =============================================================================


def optimize_lot_type(
    target_lot_size: Decimal, initial_lot_type: Literal["standard", "mini", "micro"] = "standard"
) -> tuple[Decimal, Literal["standard", "mini", "micro"]]:
    """
    Convert to smallest practical lot type (AC 6, Task 6).

    Example: 0.05 standard lots → 5 mini lots (cleaner)

    Args:
        target_lot_size: Calculated lot size
        initial_lot_type: Initial lot type used

    Returns:
        tuple[Decimal, str]: (optimized_lot_size, optimized_lot_type)

    Example:
        >>> optimize_lot_type(Decimal("0.05"), "standard")
        (Decimal('5.00'), 'mini')
        >>> optimize_lot_type(Decimal("0.08"), "mini")
        (Decimal('8.00'), 'micro')
    """
    if initial_lot_type == "standard":
        # If less than 0.1 standard, convert to mini
        if target_lot_size < Decimal("0.1"):
            return (target_lot_size * Decimal("10")).quantize(Decimal("0.01")), "mini"

    if initial_lot_type == "mini":
        # If less than 0.1 mini, convert to micro
        if target_lot_size < Decimal("0.1"):
            return (target_lot_size * Decimal("10")).quantize(Decimal("0.01")), "micro"

    return target_lot_size, initial_lot_type


# =============================================================================
# Task 7: Currency Conversion
# =============================================================================


def convert_to_account_currency(
    amount: Decimal, from_currency: str, to_currency: str, exchange_rates: dict[str, Decimal]
) -> Decimal:
    """
    Convert amount between currencies (AC 7, Task 7).

    Args:
        amount: Amount to convert
        from_currency: Source currency (e.g., "EUR")
        to_currency: Target currency (e.g., "USD")
        exchange_rates: Available exchange rates

    Returns:
        Decimal: Converted amount in target currency

    Raises:
        ValueError: If no exchange rate found

    Example:
        >>> convert_to_account_currency(
        ...     Decimal("100"), "EUR", "USD",
        ...     {"EUR/USD": Decimal("1.0850")}
        ... )
        Decimal('108.50')
    """
    if from_currency == to_currency:
        return amount

    # Try direct rate
    pair = f"{from_currency}/{to_currency}"
    if pair in exchange_rates:
        return (amount * exchange_rates[pair]).quantize(Decimal("0.01"), rounding=ROUND_DOWN)

    # Try inverse rate
    inverse_pair = f"{to_currency}/{from_currency}"
    if inverse_pair in exchange_rates:
        return (amount / exchange_rates[inverse_pair]).quantize(
            Decimal("0.01"), rounding=ROUND_DOWN
        )

    # Fallback: convert through USD
    if from_currency != "USD" and to_currency != "USD":
        usd_amount = convert_to_account_currency(amount, from_currency, "USD", exchange_rates)
        return convert_to_account_currency(usd_amount, "USD", to_currency, exchange_rates)

    raise ValueError(f"No exchange rate found for {from_currency}/{to_currency}")


# =============================================================================
# Task 10: Pattern-Specific Validation (Wyckoff Pip Stop Ranges)
# =============================================================================

# Wyckoff pattern-specific pip stop ranges (AC 10, Task 10)
WYCKOFF_PIP_STOP_RANGES: dict[str, dict[str, dict[str, int]]] = {
    "SPRING": {
        "EUR/USD": {"min": 20, "max": 50, "typical": 30},
        "GBP/USD": {"min": 30, "max": 70, "typical": 45},
        "USD/JPY": {"min": 25, "max": 60, "typical": 35},
        "AUD/USD": {"min": 25, "max": 60, "typical": 35},
        "USD/CAD": {"min": 25, "max": 60, "typical": 35},
        "NZD/USD": {"min": 30, "max": 70, "typical": 40},
    },
    "SOS": {
        "EUR/USD": {"min": 50, "max": 100, "typical": 70},
        "GBP/USD": {"min": 70, "max": 150, "typical": 100},
        "USD/JPY": {"min": 60, "max": 120, "typical": 85},
        "AUD/USD": {"min": 55, "max": 110, "typical": 75},
        "USD/CAD": {"min": 55, "max": 110, "typical": 75},
        "NZD/USD": {"min": 60, "max": 120, "typical": 85},
    },
    "LPS": {
        "EUR/USD": {"min": 25, "max": 60, "typical": 40},
        "GBP/USD": {"min": 35, "max": 80, "typical": 55},
        "USD/JPY": {"min": 30, "max": 70, "typical": 45},
        "AUD/USD": {"min": 30, "max": 70, "typical": 45},
        "USD/CAD": {"min": 30, "max": 70, "typical": 45},
        "NZD/USD": {"min": 35, "max": 75, "typical": 50},
    },
}


def validate_wyckoff_stop_pips(
    pattern_type: str, symbol: str, stop_pips: Decimal
) -> tuple[bool, Optional[str]]:
    """
    Validate stop is within Wyckoff structural range for pattern (AC 10, Task 10).

    Wyckoff Principle: Stops must be structural (below support/resistance),
    not arbitrary pip counts. Different patterns require different stop widths.

    Args:
        pattern_type: Pattern type ("SPRING", "SOS", "LPS")
        symbol: Currency pair
        stop_pips: Stop distance in pips

    Returns:
        tuple[bool, Optional[str]]: (is_valid, error_message)

    Example:
        >>> validate_wyckoff_stop_pips("SPRING", "EUR/USD", Decimal("30"))
        (True, None)  # 30 pips within 20-50 range
        >>> validate_wyckoff_stop_pips("SPRING", "EUR/USD", Decimal("10"))
        (False, 'SPRING stop too tight: 10 pips...')
    """
    ranges = WYCKOFF_PIP_STOP_RANGES.get(pattern_type, {})
    range_data = ranges.get(symbol)

    if range_data is None:
        # Fallback for unlisted pairs: conservative range
        min_pips, max_pips, typical = 15, 150, 50
    else:
        min_pips = range_data["min"]
        max_pips = range_data["max"]
        typical = range_data["typical"]

    if stop_pips < Decimal(str(min_pips)):
        return (
            False,
            f"{pattern_type} stop too tight: {stop_pips} pips < {min_pips} pip minimum "
            f"for {symbol} (typical: {typical} pips). Wyckoff principle: stops must be "
            f"below structural support.",
        )

    if stop_pips > Decimal(str(max_pips)):
        return (
            False,
            f"{pattern_type} stop too wide: {stop_pips} pips > {max_pips} pip maximum "
            f"for {symbol} (typical: {typical} pips). Giving market too much room.",
        )

    return True, None


def validate_forex_position(
    stop_pips: Decimal,
    required_margin: Decimal,
    available_margin: Decimal,
    position_units: int,
    pattern_type: Optional[str] = None,
    symbol: Optional[str] = None,
    min_lot_size: int = 1000,
) -> tuple[bool, Optional[str]]:
    """
    Validate forex position meets requirements (AC 10, Task 10).

    Combines Wyckoff pattern validation with forex mechanics validation.

    Args:
        stop_pips: Stop distance in pips
        required_margin: Required margin for position
        available_margin: Available account margin
        position_units: Position size in units (lot_size × contract_size)
        pattern_type: Wyckoff pattern type (optional, for validation)
        symbol: Currency pair (optional, for validation)
        min_lot_size: Minimum lot size (default 1000 units = 1 micro lot)

    Returns:
        tuple[bool, Optional[str]]: (is_valid, error_message)
    """
    # Pattern-specific stop validation
    if pattern_type and symbol:
        is_valid, error = validate_wyckoff_stop_pips(pattern_type, symbol, stop_pips)
        if not is_valid:
            return False, error

    # Check margin requirement
    if required_margin > available_margin:
        return False, f"Insufficient margin: need ${required_margin}, have ${available_margin}"

    # Check over-leverage (AC 10)
    if required_margin > (available_margin * Decimal("0.5")):
        margin_pct = (required_margin / available_margin * Decimal("100")).quantize(Decimal("0.1"))
        return False, f"Over-leveraged: using {margin_pct}% of margin (max 50%)"

    # Check minimum position size
    if position_units < min_lot_size:
        return False, f"Position too small: {position_units} units < {min_lot_size} minimum"

    return True, None


# =============================================================================
# Task 11: Wyckoff Volume/Session Integration
# =============================================================================


def get_forex_volume_multiplier(tick_volume: int, avg_tick_volume: int) -> Decimal:
    """
    Calculate volume-adjusted risk multiplier using tick volume (AC 11, Task 11).

    Wyckoff Law #3: "Effort (volume) must validate Result (price movement)."
    Higher tick volume = stronger institutional participation = higher confidence.

    Volume Tiers (Story 7.1 compliance):
    - ≥2.5x: 1.00x multiplier (climactic volume, full commitment)
    - ≥2.3x: 0.95x multiplier (very strong volume)
    - ≥2.0x: 0.90x multiplier (ideal professional volume)
    - ≥1.8x: 0.85x multiplier (strong volume)
    - ≥1.5x: 0.75x multiplier (adequate volume)
    - <1.5x: 0.70x multiplier (weak volume, reduce risk)

    Args:
        tick_volume: Tick volume on pattern formation bar
        avg_tick_volume: Average tick volume over last 20 bars

    Returns:
        Decimal: Risk multiplier (0.70 - 1.00)

    Example:
        >>> get_forex_volume_multiplier(2500, 1000)  # 2.5x ratio
        Decimal('1.00')  # Climactic volume, full allocation
        >>> get_forex_volume_multiplier(1200, 1000)  # 1.2x ratio
        Decimal('0.70')  # Weak volume, reduce risk
    """
    if avg_tick_volume == 0:
        return Decimal("1.0")  # No volume data, use full allocation

    volume_ratio = Decimal(str(tick_volume)) / Decimal(str(avg_tick_volume))

    # 5-tier volume system (Story 7.1 compliance)
    if volume_ratio >= Decimal("2.5"):
        return Decimal("1.00")  # Climactic volume
    elif volume_ratio >= Decimal("2.3"):
        return Decimal("0.95")  # Very strong volume
    elif volume_ratio >= Decimal("2.0"):
        return Decimal("0.90")  # Ideal professional volume
    elif volume_ratio >= Decimal("1.8"):
        return Decimal("0.85")  # Strong volume
    elif volume_ratio >= Decimal("1.5"):
        return Decimal("0.75")  # Adequate volume
    else:
        return Decimal("0.70")  # Weak volume (reduce risk)


def get_forex_session_multiplier(symbol: str, timestamp: datetime) -> Decimal:
    """
    Adjust risk based on forex trading session (AC 11, Task 11).

    Wyckoff Principle: Composite Operator (institutional banks) most active
    during major session overlaps. Springs/SOS during high-volume sessions
    have higher probability of success.

    Trading Sessions (UTC):
    - Asian (Tokyo): 0:00-9:00 UTC - Lower volume, ranging markets
    - London: 7:00-16:00 UTC - High volume, trend initiation
    - New York: 12:00-21:00 UTC - High volume, trend continuation
    - London/NY overlap: 12:00-16:00 UTC - HIGHEST institutional activity

    Args:
        symbol: Currency pair (e.g., "EUR/USD")
        timestamp: Signal timestamp (UTC)

    Returns:
        Decimal: Session multiplier (0.75 - 1.00)

    Example:
        >>> from datetime import datetime, UTC
        >>> # London/NY overlap
        >>> get_forex_session_multiplier("EUR/USD", datetime(2025, 11, 16, 14, 0, tzinfo=UTC))
        Decimal('1.00')  # Full allocation
        >>> # Asian session
        >>> get_forex_session_multiplier("EUR/USD", datetime(2025, 11, 16, 3, 0, tzinfo=UTC))
        Decimal('0.75')  # Reduced allocation
    """
    hour_utc = timestamp.hour

    # London/NY overlap (12:00-16:00 UTC) - HIGHEST volume
    if 12 <= hour_utc < 16:
        return Decimal("1.00")  # Full risk allocation (Composite Operator active)

    # London session (7:00-16:00 UTC) or NY session (12:00-21:00 UTC)
    if (7 <= hour_utc < 16) or (12 <= hour_utc < 21):
        return Decimal("0.90")  # Slight reduction (single-session activity)

    # Asian session (0:00-9:00 UTC) - Lower volume, ranging markets
    return Decimal("0.75")  # Conservative sizing (retail-dominated)


def calculate_forex_lot_size_with_wyckoff_adjustments(
    account_balance: Decimal,
    pattern_type: str,
    stop_loss_pips: Decimal,
    pip_value_per_lot: Decimal,
    tick_volume: int,
    avg_tick_volume: int,
    signal_timestamp: datetime,
    symbol: str,
    lot_type: Literal["standard", "mini", "micro"] = "mini",
) -> tuple[Decimal, dict[str, str]]:
    """
    Calculate forex lot size with full Wyckoff methodology integration (AC 11, Task 11).

    Combines:
    - Story 7.1 pattern-specific base risk (Spring 0.5%, SOS 0.8%, LPS 0.7%)
    - Story 7.1 volume-adjusted multipliers (0.70x - 1.00x)
    - Forex session multipliers (0.75x - 1.00x)

    Formula:
        effective_risk = base_risk × volume_multiplier × session_multiplier
        lot_size = (account × effective_risk) / (stop_pips × pip_value)

    Args:
        account_balance: Account equity
        pattern_type: Pattern type ("SPRING", "SOS", "LPS")
        stop_loss_pips: Stop distance in pips
        pip_value_per_lot: Pip value per lot in account currency
        tick_volume: Tick volume on pattern bar
        avg_tick_volume: Average tick volume (20 bars)
        signal_timestamp: Signal timestamp (UTC)
        symbol: Currency pair
        lot_type: Lot type for pip value

    Returns:
        tuple[Decimal, dict]: (lot_size, adjustment_details)

    Example:
        >>> from datetime import datetime, UTC
        >>> lot_size, details = calculate_forex_lot_size_with_wyckoff_adjustments(
        ...     account_balance=Decimal("10000.00"),
        ...     pattern_type="SPRING",
        ...     stop_loss_pips=Decimal("30.0"),
        ...     pip_value_per_lot=Decimal("1.00"),
        ...     tick_volume=2500,
        ...     avg_tick_volume=1000,
        ...     signal_timestamp=datetime(2025, 11, 16, 14, 0, tzinfo=UTC),
        ...     symbol="EUR/USD",
        ...     lot_type="mini"
        ... )
        >>> print(f"Lot size: {lot_size}")
        1.67  # 1.67 mini lots
        >>> print(details['effective_risk_percent'])
        '0.5'  # 0.5% effective risk (Spring base 0.5% × 1.00 volume × 1.00 session)
    """
    # Get base risk from Story 7.1 pattern allocations (AC 11)
    BASE_RISK_PCT: dict[str, Decimal] = {
        "SPRING": Decimal("0.5"),  # 0.5% (tight stops, high R:R)
        "SOS": Decimal("0.8"),  # 0.8% (wider stops, breakout risk)
        "LPS": Decimal("0.7"),  # 0.7% (medium stops, confirmation entry)
    }
    base_risk_pct = BASE_RISK_PCT.get(pattern_type, Decimal("0.5"))

    # Get volume multiplier (Story 7.1 integration)
    volume_multiplier = get_forex_volume_multiplier(tick_volume, avg_tick_volume)

    # Get session multiplier (forex-specific)
    session_multiplier = get_forex_session_multiplier(symbol, signal_timestamp)

    # Calculate effective risk
    effective_risk_pct = base_risk_pct * volume_multiplier * session_multiplier

    # Calculate lot size
    risk_dollars = account_balance * (effective_risk_pct / Decimal("100"))
    lot_size = risk_dollars / (stop_loss_pips * pip_value_per_lot)
    lot_size = lot_size.quantize(Decimal("0.01"), rounding=ROUND_DOWN)

    # Calculate volume ratio for logging
    volume_ratio_str = (
        str((Decimal(str(tick_volume)) / Decimal(str(avg_tick_volume))).quantize(Decimal("0.01")))
        if avg_tick_volume > 0
        else "N/A"
    )

    # Return lot size + adjustment details for logging
    adjustment_details = {
        "base_risk_percent": str(base_risk_pct),
        "volume_multiplier": str(volume_multiplier),
        "session_multiplier": str(session_multiplier),
        "effective_risk_percent": str(effective_risk_pct),
        "risk_dollars": str(risk_dollars.quantize(Decimal("0.01"))),
        "volume_ratio": volume_ratio_str,
    }

    logger.info(
        "forex_wyckoff_lot_size_calculated",
        symbol=symbol,
        pattern_type=pattern_type,
        lot_size=str(lot_size),
        lot_type=lot_type,
        base_risk_pct=str(base_risk_pct),
        volume_multiplier=str(volume_multiplier),
        session_multiplier=str(session_multiplier),
        effective_risk_pct=str(effective_risk_pct),
        volume_ratio=volume_ratio_str,
        tick_volume=tick_volume,
        avg_tick_volume=avg_tick_volume,
        signal_hour_utc=signal_timestamp.hour,
    )

    return lot_size, adjustment_details


# =============================================================================
# Task 8: ForexPositionSize Data Model
# =============================================================================


@dataclass
class ForexPositionSize:
    """
    Forex-specific position sizing result with Wyckoff methodology integration (AC 8, Task 8).

    This model represents a complete forex position size calculation including:
    - Forex mechanics (lots, pips, margin, leverage)
    - Wyckoff context (pattern, phase, base risk)
    - Volume analysis (tick volume, ratio, multiplier)
    - Session analysis (timestamp, session, multiplier)
    - Effective risk (after all adjustments)
    - R-multiple (risk/reward validation)
    - Spread adjustment (broker spread buffer)

    Attributes:
        # Forex Mechanics
        symbol: Currency pair (e.g., "EUR/USD")
        lot_size: Position size in lots (e.g., 3.33)
        lot_type: Lot type ("standard", "mini", "micro")
        contract_size: Units per lot (100000, 10000, 1000)
        position_units: Total units (lot_size × contract_size)
        stop_loss_pips: Stop distance in pips
        pip_value: Pip value per standard lot in account currency
        risk_dollars: Dollar risk amount
        required_margin: Margin required for position
        leverage: Account leverage (e.g., 50 for 50:1)
        account_currency: Account currency (e.g., "USD")
        entry_price: Entry price level
        stop_price: Stop loss price level
        margin_warning: Margin warning message if applicable
        created_at: Creation timestamp

        # Wyckoff Context
        pattern_type: Pattern type ("SPRING", "SOS", "LPS")
        wyckoff_phase: Wyckoff phase ("C", "D", "E")
        base_risk_percent: Base risk % from pattern (0.5%, 0.7%, 0.8%)

        # Volume Analysis
        tick_volume: Tick volume on signal bar
        avg_tick_volume: 20-bar average tick volume
        volume_ratio: tick_volume / avg_tick_volume
        volume_multiplier: Volume-based risk adjustment (0.70 - 1.00)

        # Session Analysis
        signal_timestamp: Signal generation timestamp (UTC)
        trading_session: Trading session name
        session_multiplier: Session-based risk adjustment (0.75 - 1.00)

        # Effective Risk
        effective_risk_percent: Final risk % (base × volume × session)

        # R-Multiple
        target_price: Target price level (optional)
        r_multiple: Risk/reward ratio (optional)

        # Spread Adjustment
        broker_spread_pips: Typical spread for pair
        spread_adjusted_stop: Stop after spread buffer

    Example:
        >>> from datetime import datetime, UTC
        >>> position = ForexPositionSize(
        ...     symbol="EUR/USD",
        ...     lot_size=Decimal("1.67"),
        ...     lot_type="mini",
        ...     contract_size=10000,
        ...     position_units=16700,
        ...     stop_loss_pips=Decimal("30.8"),
        ...     pip_value=Decimal("1.00"),
        ...     risk_dollars=Decimal("50.00"),
        ...     required_margin=Decimal("362.00"),
        ...     leverage=Decimal("50"),
        ...     account_currency="USD",
        ...     entry_price=Decimal("1.0850"),
        ...     stop_price=Decimal("1.08193"),
        ...     pattern_type="SPRING",
        ...     wyckoff_phase="C",
        ...     base_risk_percent=Decimal("0.5"),
        ...     tick_volume=2500,
        ...     avg_tick_volume=1000,
        ...     volume_ratio=Decimal("2.5"),
        ...     volume_multiplier=Decimal("1.00"),
        ...     signal_timestamp=datetime(2025, 11, 16, 14, 0, tzinfo=UTC),
        ...     trading_session="London/NY Overlap",
        ...     session_multiplier=Decimal("1.00"),
        ...     effective_risk_percent=Decimal("0.5"),
        ...     broker_spread_pips=Decimal("1.5"),
        ...     spread_adjusted_stop=Decimal("1.08193")
        ... )
    """

    # Forex Mechanics
    symbol: str
    lot_size: Decimal
    lot_type: Literal["standard", "mini", "micro"]
    contract_size: int
    position_units: int
    stop_loss_pips: Decimal
    pip_value: Decimal
    risk_dollars: Decimal
    required_margin: Decimal
    leverage: Decimal
    account_currency: str
    entry_price: Decimal
    stop_price: Decimal
    margin_warning: Optional[str] = None
    created_at: Optional[datetime] = None

    # Wyckoff Context
    pattern_type: Optional[str] = None
    wyckoff_phase: Optional[str] = None
    base_risk_percent: Optional[Decimal] = None

    # Volume Analysis
    tick_volume: Optional[int] = None
    avg_tick_volume: Optional[int] = None
    volume_ratio: Optional[Decimal] = None
    volume_multiplier: Optional[Decimal] = None

    # Session Analysis
    signal_timestamp: Optional[datetime] = None
    trading_session: Optional[str] = None
    session_multiplier: Optional[Decimal] = None

    # Effective Risk
    effective_risk_percent: Optional[Decimal] = None

    # R-Multiple
    target_price: Optional[Decimal] = None
    r_multiple: Optional[Decimal] = None

    # Spread Adjustment
    broker_spread_pips: Optional[Decimal] = None
    spread_adjusted_stop: Optional[Decimal] = None

    def __post_init__(self) -> None:
        """Initialize computed fields."""
        if self.created_at is None:
            self.created_at = datetime.now()

        # Calculate position_units if not set
        contract_sizes: dict[str, int] = {"standard": 100000, "mini": 10000, "micro": 1000}
        if self.contract_size not in contract_sizes.values():
            self.contract_size = contract_sizes[self.lot_type]
        self.position_units = int(self.lot_size * Decimal(str(self.contract_size)))

    def to_dict(self) -> dict[str, str | int | None]:
        """
        Convert to dictionary for JSON serialization and audit trail.

        Returns:
            dict: Dictionary representation with string values for Decimals
        """
        return {
            # Forex Mechanics
            "symbol": self.symbol,
            "lot_size": str(self.lot_size),
            "lot_type": self.lot_type,
            "contract_size": self.contract_size,
            "position_units": self.position_units,
            "stop_loss_pips": str(self.stop_loss_pips),
            "pip_value": str(self.pip_value),
            "risk_dollars": str(self.risk_dollars),
            "required_margin": str(self.required_margin),
            "leverage": str(self.leverage),
            "account_currency": self.account_currency,
            "entry_price": str(self.entry_price),
            "stop_price": str(self.stop_price),
            "margin_warning": self.margin_warning,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            # Wyckoff Context
            "pattern_type": self.pattern_type,
            "wyckoff_phase": self.wyckoff_phase,
            "base_risk_percent": str(self.base_risk_percent) if self.base_risk_percent else None,
            # Volume Analysis
            "tick_volume": self.tick_volume,
            "avg_tick_volume": self.avg_tick_volume,
            "volume_ratio": str(self.volume_ratio) if self.volume_ratio else None,
            "volume_multiplier": str(self.volume_multiplier) if self.volume_multiplier else None,
            # Session Analysis
            "signal_timestamp": self.signal_timestamp.isoformat()
            if self.signal_timestamp
            else None,
            "trading_session": self.trading_session,
            "session_multiplier": str(self.session_multiplier) if self.session_multiplier else None,
            # Effective Risk
            "effective_risk_percent": (
                str(self.effective_risk_percent) if self.effective_risk_percent else None
            ),
            # R-Multiple
            "target_price": str(self.target_price) if self.target_price else None,
            "r_multiple": str(self.r_multiple) if self.r_multiple else None,
            # Spread Adjustment
            "broker_spread_pips": str(self.broker_spread_pips) if self.broker_spread_pips else None,
            "spread_adjusted_stop": (
                str(self.spread_adjusted_stop) if self.spread_adjusted_stop else None
            ),
        }
