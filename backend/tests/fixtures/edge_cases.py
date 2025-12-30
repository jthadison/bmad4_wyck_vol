"""
Edge case fixtures for testing.

Provides fixtures for edge case scenarios that should be handled gracefully.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from src.models.ohlcv import OHLCVBar
from tests.fixtures.ohlcv_bars import create_ohlcv_bar


def zero_volume_bar(symbol: str = "AAPL") -> OHLCVBar:
    """
    Create a bar with zero volume.

    Edge case: Should be handled gracefully (e.g., skip or use previous volume).
    """
    return create_ohlcv_bar(
        symbol=symbol,
        timestamp=datetime(2024, 1, 15, 13, 0, 0, tzinfo=UTC),
        open_price=100.0,
        high=100.5,
        low=99.5,
        close=100.25,
        volume=0,  # ZERO volume
    )


def gap_up_bar(previous_close: float = 100.0, symbol: str = "AAPL") -> OHLCVBar:
    """
    Create a bar with gap up (previous close < current open).

    Edge case: Should be detected for gap analysis.
    """
    return create_ohlcv_bar(
        symbol=symbol,
        timestamp=datetime(2024, 1, 16, 9, 30, 0, tzinfo=UTC),
        open_price=previous_close + 3.0,  # Gap up
        high=previous_close + 4.0,
        low=previous_close + 2.5,
        close=previous_close + 3.5,
        volume=1200000,
    )


def gap_down_bar(previous_close: float = 100.0, symbol: str = "AAPL") -> OHLCVBar:
    """
    Create a bar with gap down (previous close > current open).

    Edge case: Should be detected for gap analysis.
    """
    return create_ohlcv_bar(
        symbol=symbol,
        timestamp=datetime(2024, 1, 16, 9, 30, 0, tzinfo=UTC),
        open_price=previous_close - 3.0,  # Gap down
        high=previous_close - 2.0,
        low=previous_close - 4.0,
        close=previous_close - 2.5,
        volume=1500000,
    )


def extreme_spread_bar(avg_spread: float = 0.5, symbol: str = "AAPL") -> OHLCVBar:
    """
    Create a bar with extreme spread (> 5x average).

    Edge case: Should be detected as climactic action.
    """
    return create_ohlcv_bar(
        symbol=symbol,
        timestamp=datetime(2024, 1, 17, 10, 30, 0, tzinfo=UTC),
        open_price=100.0,
        high=106.0,  # Spread = 6.0 (12x average of 0.5)
        low=100.0,
        close=105.5,
        volume=2500000,  # High volume
    )


def missing_bars_sequence(symbol: str = "AAPL") -> list[OHLCVBar]:
    """
    Create a sequence with missing timestamps (data gaps).

    Edge case: Should detect gaps and handle appropriately.

    Returns:
        List of 10 bars with gaps at indices 3 and 7
    """
    bars = []
    base_time = datetime(2024, 1, 1, 9, 30, 0, tzinfo=UTC)

    for i in range(10):
        # Skip indices 3 and 7 (create gaps)
        if i in (3, 7):
            continue

        timestamp = base_time + timedelta(days=i)
        bars.append(
            create_ohlcv_bar(
                symbol=symbol,
                timestamp=timestamp,
                open_price=100.0 + i,
                high=101.0 + i,
                low=99.0 + i,
                close=100.5 + i,
                volume=1000000,
            )
        )

    return bars


def doji_bar(symbol: str = "AAPL") -> OHLCVBar:
    """
    Create a Doji bar (open == close).

    Edge case: Indecision pattern.
    """
    return create_ohlcv_bar(
        symbol=symbol,
        timestamp=datetime(2024, 1, 18, 11, 0, 0, tzinfo=UTC),
        open_price=100.0,
        high=101.0,
        low=99.0,
        close=100.0,  # Same as open (Doji)
        volume=900000,
    )


def narrow_spread_bar(symbol: str = "AAPL") -> OHLCVBar:
    """
    Create a bar with very narrow spread (high - low < 0.1).

    Edge case: No trading range.
    """
    return create_ohlcv_bar(
        symbol=symbol,
        timestamp=datetime(2024, 1, 19, 12, 0, 0, tzinfo=UTC),
        open_price=100.0,
        high=100.05,
        low=99.95,
        close=100.03,
        volume=800000,
    )


def extreme_volume_bar(avg_volume: int = 1000000, symbol: str = "AAPL") -> OHLCVBar:
    """
    Create a bar with extreme volume (> 10x average).

    Edge case: Climactic volume.
    """
    return create_ohlcv_bar(
        symbol=symbol,
        timestamp=datetime(2024, 1, 20, 13, 0, 0, tzinfo=UTC),
        open_price=100.0,
        high=102.0,
        low=99.5,
        close=101.5,
        volume=avg_volume * 12,  # 12x average
    )
