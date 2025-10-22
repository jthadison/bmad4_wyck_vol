"""
OHLCV data validation logic.

This module provides validation functions for OHLCV bars to ensure data quality
before insertion into the database.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

import structlog

from src.models.ohlcv import OHLCVBar

logger = structlog.get_logger(__name__)


def validate_bar(
    bar: OHLCVBar,
    previous_bar: Optional[OHLCVBar] = None,
) -> tuple[bool, Optional[str]]:
    """
    Validate an OHLCV bar for data quality.

    Validation checks:
    1. Volume > 0 (reject zero volume bars)
    2. All OHLC values present (no None/null)
    3. OHLC relationships: low <= open/close <= high
    4. Timestamp gaps: if previous_bar exists, gap <= 1 bar period

    Args:
        bar: OHLCV bar to validate
        previous_bar: Previous bar in sequence (for gap detection)

    Returns:
        Tuple of (is_valid, rejection_reason)
        - is_valid: True if bar passes all validations
        - rejection_reason: String describing why bar was rejected (None if valid)

    Example:
        ```python
        is_valid, reason = validate_bar(bar, previous_bar)
        if not is_valid:
            logger.warning("bar_rejected", symbol=bar.symbol, reason=reason)
        ```
    """
    # Validation 1: Check volume > 0
    if bar.volume <= 0:
        return False, f"Zero volume: {bar.volume}"

    # Validation 2: Check all OHLC values present
    if bar.open is None or bar.high is None or bar.low is None or bar.close is None:
        return False, "Missing OHLC values"

    # Validation 3: Check OHLC relationships
    # low <= open <= high
    if not (bar.low <= bar.open <= bar.high):
        return False, f"Invalid open: {bar.low} <= {bar.open} <= {bar.high} failed"

    # low <= close <= high
    if not (bar.low <= bar.close <= bar.high):
        return False, f"Invalid close: {bar.low} <= {bar.close} <= {bar.high} failed"

    # Validation 4: Check timestamp gaps (if previous bar provided)
    if previous_bar is not None:
        gap_valid, gap_reason = _validate_timestamp_gap(bar, previous_bar)
        if not gap_valid:
            return False, gap_reason

    # All validations passed
    return True, None


def _validate_timestamp_gap(
    bar: OHLCVBar,
    previous_bar: OHLCVBar,
) -> tuple[bool, Optional[str]]:
    """
    Validate timestamp gap between consecutive bars.

    Gap tolerance varies by timeframe:
    - 1d (daily): Allow gaps up to 3 days (weekends)
    - 1h (hourly): Allow gaps up to 2 hours (market close to open)
    - 5m, 15m (intraday): Allow gaps up to 1 hour
    - 1m (minute): Allow gaps up to 5 minutes

    Args:
        bar: Current bar
        previous_bar: Previous bar

    Returns:
        Tuple of (is_valid, rejection_reason)
    """
    # Calculate time gap
    gap = bar.timestamp - previous_bar.timestamp

    # Define max allowed gaps by timeframe
    max_gaps = {
        "1d": timedelta(days=3),  # Allow weekends
        "1h": timedelta(hours=2),  # Allow market close to open
        "15m": timedelta(hours=1),  # Allow small gaps
        "5m": timedelta(hours=1),  # Allow small gaps
        "1m": timedelta(minutes=5),  # Very strict for minute bars
    }

    # Get max allowed gap for this timeframe
    max_gap = max_gaps.get(bar.timeframe)
    if max_gap is None:
        # Unknown timeframe, skip gap validation
        logger.warning(
            "unknown_timeframe",
            timeframe=bar.timeframe,
            message="Unknown timeframe for gap validation",
        )
        return True, None

    # Check if gap exceeds maximum
    if gap > max_gap:
        return (
            False,
            f"Timestamp gap too large: {gap} exceeds max {max_gap} for {bar.timeframe}",
        )

    # Check for negative gaps (bars out of order)
    if gap < timedelta(0):
        return False, f"Negative timestamp gap: {gap} (bars out of order)"

    return True, None


def validate_bar_batch(
    bars: list[OHLCVBar],
) -> tuple[list[OHLCVBar], list[tuple[OHLCVBar, str]]]:
    """
    Validate a batch of bars, checking each bar and gaps between them.

    Args:
        bars: List of bars to validate (assumed to be sorted by timestamp)

    Returns:
        Tuple of (valid_bars, rejected_bars)
        - valid_bars: List of bars that passed validation
        - rejected_bars: List of (bar, rejection_reason) tuples

    Example:
        ```python
        valid, rejected = validate_bar_batch(bars)
        logger.info(
            "batch_validated",
            total=len(bars),
            valid=len(valid),
            rejected=len(rejected),
        )
        ```
    """
    valid_bars: list[OHLCVBar] = []
    rejected_bars: list[tuple[OHLCVBar, str]] = []

    previous_bar: Optional[OHLCVBar] = None

    for bar in bars:
        is_valid, reason = validate_bar(bar, previous_bar)

        if is_valid:
            valid_bars.append(bar)
            previous_bar = bar  # Update for next iteration
        else:
            rejected_bars.append((bar, reason or "Unknown validation error"))
            logger.warning(
                "bar_rejected",
                symbol=bar.symbol,
                timestamp=bar.timestamp.isoformat(),
                reason=reason,
            )

    return valid_bars, rejected_bars


def get_validation_stats(
    total_bars: int,
    valid_bars: int,
    rejected_bars: int,
) -> dict[str, int | float]:
    """
    Calculate validation statistics.

    Args:
        total_bars: Total number of bars processed
        valid_bars: Number of valid bars
        rejected_bars: Number of rejected bars

    Returns:
        Dictionary with validation statistics

    Example:
        ```python
        stats = get_validation_stats(1000, 985, 15)
        # {
        #     "total": 1000,
        #     "valid": 985,
        #     "rejected": 15,
        #     "valid_percentage": 98.5,
        #     "rejected_percentage": 1.5
        # }
        ```
    """
    valid_pct = (valid_bars / total_bars * 100) if total_bars > 0 else 0.0
    rejected_pct = (rejected_bars / total_bars * 100) if total_bars > 0 else 0.0

    return {
        "total": total_bars,
        "valid": valid_bars,
        "rejected": rejected_bars,
        "valid_percentage": round(valid_pct, 2),
        "rejected_percentage": round(rejected_pct, 2),
    }
