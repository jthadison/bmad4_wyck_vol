"""
Shared test fixtures for pattern detector tests.

Provides helper functions for creating test OHLCV bars and volume analysis objects.
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from src.models.ohlcv import OHLCVBar


def create_test_bar(
    symbol: str = "TEST",
    timeframe: str = "1d",
    timestamp: datetime | None = None,
    open_price: Decimal | float = 100.0,
    high: Decimal | float | None = None,
    low: Decimal | float | None = None,
    close: Decimal | float | None = None,
    volume: int = 1000,
) -> OHLCVBar:
    """
    Factory function for creating test OHLCV bars with sensible defaults.

    Args:
        symbol: Stock symbol (default: "TEST")
        timeframe: Bar timeframe (default: "1d")
        timestamp: Bar timestamp (default: 2024-01-01 UTC)
        open_price: Opening price (default: 100.0)
        high: High price (default: open + 2.0)
        low: Low price (default: open - 1.0)
        close: Closing price (default: open + 1.0)
        volume: Trading volume (default: 1000)

    Returns:
        OHLCVBar with all required fields populated

    Example:
        >>> bar = create_test_bar(volume=2000, close=95.0)
        >>> assert bar.volume == 2000
        >>> assert bar.close == Decimal("95.0")
    """
    if timestamp is None:
        timestamp = datetime(2024, 1, 1, tzinfo=UTC)

    open_decimal = Decimal(str(open_price))

    if high is None:
        high_decimal = open_decimal + Decimal("2.0")
    else:
        high_decimal = Decimal(str(high))

    if low is None:
        low_decimal = open_decimal - Decimal("1.0")
    else:
        low_decimal = Decimal(str(low))

    if close is None:
        close_decimal = open_decimal + Decimal("1.0")
    else:
        close_decimal = Decimal(str(close))

    spread = high_decimal - low_decimal

    return OHLCVBar(
        symbol=symbol,
        timeframe=timeframe,
        timestamp=timestamp,
        open=open_decimal,
        high=high_decimal,
        low=low_decimal,
        close=close_decimal,
        volume=volume,
        spread=spread,
    )


@pytest.fixture
def base_timestamp() -> datetime:
    """Base timestamp for test bars (2024-01-01 UTC)."""
    return datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
