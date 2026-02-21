"""
Timeframe Configuration for Pattern Detection

Purpose:
--------
Provides timeframe-specific multipliers for scaling pattern detection thresholds
to accommodate different price movement characteristics across timeframes.

Background:
-----------
Intraday price movements are proportionally smaller than daily movements. A 2% Ice
distance that works on daily charts would miss all patterns on 15m charts where
typical range is 0.05-0.10%.

Timeframe Multipliers:
----------------------
Based on empirical observation of EUR/USD price action:

| Timeframe | Multiplier | Avg Range  | Ice (2% base) | Creek (5% base) |
|-----------|------------|------------|---------------|-----------------|
| 1m        | 0.15       | 0.02-0.04% | 0.3%  (~3 pips)  | 0.75% (~7 pips)   |
| 5m        | 0.20       | 0.03-0.06% | 0.4%  (~4 pips)  | 1.0%  (~10 pips)  |
| 15m       | 0.30       | 0.05-0.10% | 0.6%  (~6 pips)  | 1.5%  (~15 pips)  |
| 1h        | 0.70       | 0.15-0.25% | 1.4% (~14 pips)  | 3.5%  (~35 pips)  |
| 1d        | 1.00       | 0.50-0.80% | 2.0% (~20 pips)  | 5.0%  (~50 pips)  |

These multipliers ensure pattern thresholds align with actual intraday price movement,
not arbitrary percentages.

Important Notes:
----------------
- Multipliers are empirically derived for EUR/USD and similar forex majors
- Future stories will add asset-class-specific configuration
- Volume thresholds (0.7x, 2.0x) do NOT scale - they are ratios and remain meaningful
  across all timeframes

Author: Story 13.1
"""

from decimal import Decimal
from typing import Final

# Base thresholds (daily timeframe)
# These represent the "1d" timeframe as 100% (multiplier = 1.00)
ICE_DISTANCE_BASE: Final[Decimal] = Decimal("0.02")  # 2% penetration for Ice level
CREEK_MIN_RALLY_BASE: Final[Decimal] = Decimal("0.05")  # 5% minimum rally for Creek level
MAX_PENETRATION_BASE: Final[Decimal] = Decimal("0.05")  # 5% max spring penetration

# Timeframe multipliers for scaling price-based thresholds
# Story 13.1 AC1.2, AC1.3
TIMEFRAME_MULTIPLIERS: Final[dict[str, Decimal]] = {
    "1m": Decimal("0.15"),  # 1-minute: 15% of daily thresholds
    "5m": Decimal("0.20"),  # 5-minute: 20% of daily thresholds
    "15m": Decimal("0.30"),  # 15-minute: 30% of daily thresholds
    "1h": Decimal("0.70"),  # 1-hour: 70% of daily thresholds
    "1d": Decimal("1.00"),  # Daily: 100% (baseline)
}

# Volume thresholds - CONSTANT across all timeframes (Story 13.1 AC1.7)
# These are ratios and do NOT scale by timeframe
SPRING_VOLUME_THRESHOLD: Final[Decimal] = Decimal("0.7")  # <0.7x for Spring patterns
SOS_VOLUME_THRESHOLD: Final[Decimal] = Decimal("1.5")  # >1.5x for SOS patterns


def get_scaled_threshold(base_threshold: Decimal, timeframe: str) -> Decimal:
    """
    Calculate scaled threshold based on timeframe multiplier.

    Args:
        base_threshold: Base threshold value (daily timeframe)
        timeframe: Timeframe identifier ("1m", "5m", "15m", "1h", "1d")

    Returns:
        Decimal: Scaled threshold value

    Raises:
        ValueError: If timeframe is not supported

    Example:
        >>> ice_threshold = get_scaled_threshold(ICE_DISTANCE_BASE, "15m")
        >>> assert ice_threshold == Decimal("0.006")  # 2% * 0.30 = 0.6%
    """
    if timeframe not in TIMEFRAME_MULTIPLIERS:
        supported = ", ".join(TIMEFRAME_MULTIPLIERS.keys())
        raise ValueError(f"Unsupported timeframe: '{timeframe}'. " f"Must be one of: {supported}")

    multiplier = TIMEFRAME_MULTIPLIERS[timeframe]
    return base_threshold * multiplier


def validate_timeframe(timeframe: str) -> str:
    """
    Validate and normalize timeframe string.

    Args:
        timeframe: Timeframe identifier (case-insensitive)

    Returns:
        str: Normalized timeframe in lowercase

    Raises:
        ValueError: If timeframe is not supported

    Example:
        >>> validate_timeframe("15M")
        '15m'
        >>> validate_timeframe("1d")
        '1d'
    """
    normalized = timeframe.lower()
    if normalized not in TIMEFRAME_MULTIPLIERS:
        supported = ", ".join(TIMEFRAME_MULTIPLIERS.keys())
        raise ValueError(f"Unsupported timeframe: '{timeframe}'. " f"Must be one of: {supported}")
    return normalized
