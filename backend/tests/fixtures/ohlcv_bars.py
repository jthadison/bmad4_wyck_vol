"""
OHLCV bar fixtures for testing.

Provides factory functions and predefined scenarios for OHLCV bar data.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from src.models.ohlcv import OHLCVBar


def create_ohlcv_bar(
    symbol: str = "AAPL",
    timestamp: datetime | None = None,
    open_price: float = 100.0,
    high: float = 105.0,
    low: float = 99.0,
    close: float = 102.0,
    volume: int = 1000000,
    **overrides: Any,
) -> OHLCVBar:
    """
    Create an OHLCV bar with sensible defaults.

    Args:
        symbol: Stock symbol
        timestamp: Bar timestamp (defaults to 2024-01-15 13:00:00 UTC)
        open_price: Opening price
        high: High price
        low: Low price
        close: Closing price
        volume: Trading volume
        **overrides: Additional fields to override

    Returns:
        OHLCVBar instance
    """
    if timestamp is None:
        timestamp = datetime(2024, 1, 15, 13, 0, 0, tzinfo=UTC)

    from decimal import Decimal

    quantize_precision = Decimal("0.00000001")
    open_decimal = Decimal(str(open_price)).quantize(quantize_precision)
    high_decimal = Decimal(str(high)).quantize(quantize_precision)
    low_decimal = Decimal(str(low)).quantize(quantize_precision)
    close_decimal = Decimal(str(close)).quantize(quantize_precision)
    spread = (high_decimal - low_decimal).quantize(quantize_precision)

    bar_data = {
        "symbol": symbol,
        "timestamp": timestamp,
        "open": open_decimal,
        "high": high_decimal,
        "low": low_decimal,
        "close": close_decimal,
        "volume": volume,
        "timeframe": "1d",
        "spread": spread,
    }
    bar_data.update(overrides)

    return OHLCVBar(**bar_data)


def spring_pattern_bars(symbol: str = "AAPL") -> list[OHLCVBar]:
    """
    Generate 100 OHLCV bars with a Spring pattern at bar 50.

    Spring characteristics:
    - Bar 50: Low-volume breakdown below Creek level
    - Bar 51-55: Recovery with expanding volume
    - Bar 56: Sign of Strength (SOS) breakout

    Returns:
        List of 100 OHLCVBar instances
    """
    bars = []
    base_time = datetime(2024, 1, 1, 9, 30, 0, tzinfo=UTC)
    base_price = 100.0

    for i in range(100):
        timestamp = base_time + timedelta(days=i)

        # Build up phase (bars 0-40)
        if i < 40:
            open_price = base_price + (i * 0.1)
            close = open_price + 0.2
            high = close + 0.3
            low = open_price - 0.1
            volume = 800000 + (i * 5000)

        # Trading range (bars 40-49)
        elif i < 50:
            open_price = 104.0
            close = 104.5
            high = 105.0
            low = 103.5
            volume = 900000

        # SPRING (bar 50) - LOW VOLUME breakdown
        elif i == 50:
            open_price = 104.0
            close = 102.5  # Breakdown below Creek (103.5)
            high = 104.0
            low = 102.0
            volume = 500000  # LOW volume (0.5x average)

        # Recovery (bars 51-55)
        elif i < 56:
            recovery_days = i - 50
            open_price = 102.5 + (recovery_days * 0.5)
            close = open_price + 0.5
            high = close + 0.3
            low = open_price - 0.2
            volume = 1000000 + (recovery_days * 100000)  # Expanding volume

        # SOS breakout (bar 56)
        elif i == 56:
            open_price = 105.0
            close = 108.0  # Strong breakout
            high = 108.5
            low = 104.5
            volume = 1800000  # HIGH volume (1.8x average)

        # Markup (bars 57-99)
        else:
            markup_days = i - 56
            open_price = 108.0 + (markup_days * 0.3)
            close = open_price + 0.4
            high = close + 0.3
            low = open_price - 0.2
            volume = 1100000

        bars.append(
            create_ohlcv_bar(
                symbol=symbol,
                timestamp=timestamp,
                open_price=open_price,
                high=high,
                low=low,
                close=close,
                volume=volume,
            )
        )

    return bars


def sos_pattern_bars(symbol: str = "AAPL") -> list[OHLCVBar]:
    """
    Generate 100 OHLCV bars with a SOS (Sign of Strength) pattern at bar 60.

    SOS characteristics:
    - Bar 60: High-volume breakout above Ice level
    - Wide spread (close - open > 2x average)
    - Volume > 1.5x average

    Returns:
        List of 100 OHLCVBar instances
    """
    bars = []
    base_time = datetime(2024, 1, 1, 9, 30, 0, tzinfo=UTC)

    for i in range(100):
        timestamp = base_time + timedelta(days=i)

        # Accumulation (bars 0-59)
        if i < 60:
            open_price = 100.0 + (i * 0.05)
            close = open_price + 0.3
            high = close + 0.2
            low = open_price - 0.2
            volume = 900000

        # SOS breakout (bar 60)
        elif i == 60:
            open_price = 103.0
            close = 107.0  # Wide spread (4.0 vs avg 0.3)
            high = 107.5
            low = 102.5
            volume = 1600000  # 1.78x average

        # Markup continuation (bars 61-99)
        else:
            markup_days = i - 60
            open_price = 107.0 + (markup_days * 0.2)
            close = open_price + 0.3
            high = close + 0.2
            low = open_price - 0.1
            volume = 1000000

        bars.append(
            create_ohlcv_bar(
                symbol=symbol,
                timestamp=timestamp,
                open_price=open_price,
                high=high,
                low=low,
                close=close,
                volume=volume,
            )
        )

    return bars


def utad_pattern_bars(symbol: str = "AAPL") -> list[OHLCVBar]:
    """
    Generate 100 OHLCV bars with a UTAD (Upthrust After Distribution) pattern at bar 70.

    UTAD characteristics:
    - Bar 70: Low-volume upthrust above Ice level
    - Bar 71-75: Reversal with expanding volume
    - Bar 76: Sign of Weakness (SOW) breakdown

    Returns:
        List of 100 OHLCVBar instances
    """
    bars = []
    base_time = datetime(2024, 1, 1, 9, 30, 0, tzinfo=UTC)

    for i in range(100):
        timestamp = base_time + timedelta(days=i)

        # Markup (bars 0-69)
        if i < 70:
            open_price = 80.0 + (i * 0.3)
            close = open_price + 0.2
            high = close + 0.2
            low = open_price - 0.1
            volume = 900000

        # UTAD (bar 70) - LOW VOLUME upthrust
        elif i == 70:
            open_price = 101.0
            close = 103.5  # Upthrust above Ice (102.0)
            high = 104.0
            low = 100.5
            volume = 550000  # LOW volume (0.61x average)

        # Reversal (bars 71-75)
        elif i < 76:
            reversal_days = i - 70
            open_price = 103.0 - (reversal_days * 0.5)
            close = open_price - 0.4
            high = open_price + 0.1
            low = close - 0.3
            volume = 1100000 + (reversal_days * 100000)

        # SOW breakdown (bar 76)
        elif i == 76:
            open_price = 100.0
            close = 96.0  # Strong breakdown
            high = 100.5
            low = 95.5
            volume = 1900000  # HIGH volume (2.1x average)

        # Markdown (bars 77-99)
        else:
            markdown_days = i - 76
            open_price = 96.0 - (markdown_days * 0.25)
            close = open_price - 0.3
            high = open_price + 0.1
            low = close - 0.2
            volume = 1100000

        bars.append(
            create_ohlcv_bar(
                symbol=symbol,
                timestamp=timestamp,
                open_price=open_price,
                high=high,
                low=low,
                close=close,
                volume=volume,
            )
        )

    return bars


def false_spring_bars(symbol: str = "AAPL") -> list[OHLCVBar]:
    """
    Generate 100 OHLCV bars with a FALSE Spring pattern (high-volume breakdown).

    False Spring characteristics:
    - Bar 50: HIGH-volume breakdown (not a valid Spring)
    - Continues markdown (no recovery)

    Returns:
        List of 100 OHLCVBar instances
    """
    bars = []
    base_time = datetime(2024, 1, 1, 9, 30, 0, tzinfo=UTC)

    for i in range(100):
        timestamp = base_time + timedelta(days=i)

        # Accumulation (bars 0-49)
        if i < 50:
            open_price = 100.0 + (i * 0.08)
            close = open_price + 0.2
            high = close + 0.2
            low = open_price - 0.1
            volume = 900000

        # FALSE SPRING (bar 50) - HIGH VOLUME breakdown (invalid)
        elif i == 50:
            open_price = 104.0
            close = 101.0  # Breakdown
            high = 104.0
            low = 100.5
            volume = 1700000  # HIGH volume (1.89x average) - invalid Spring

        # Markdown continuation (bars 51-99)
        else:
            markdown_days = i - 50
            open_price = 101.0 - (markdown_days * 0.15)
            close = open_price - 0.2
            high = open_price + 0.1
            low = close - 0.2
            volume = 1000000

        bars.append(
            create_ohlcv_bar(
                symbol=symbol,
                timestamp=timestamp,
                open_price=open_price,
                high=high,
                low=low,
                close=close,
                volume=volume,
            )
        )

    return bars
