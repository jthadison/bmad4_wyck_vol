"""
Test Data Fixtures for Summary Repository (Story 10.3.1)

Purpose:
--------
Provides reusable database fixtures for testing daily summary queries.
Generates realistic OHLCV bars, patterns, and signals with proper timestamps.

Fixtures:
---------
- ohlcv_bars_fixture: Generates OHLCV bars across multiple symbols and timeframes
- patterns_fixture: Generates pattern detection records
- signals_fixture: Generates signals with various statuses
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from src.orm.models import Pattern, Signal
from src.repositories.models import OHLCVBarModel


def create_ohlcv_bars_fixture(
    symbols: list[str],
    timeframe: str = "1h",
    hours_back: int = 48,
    recent_count: int = 10,
) -> list[OHLCVBarModel]:
    """
    Create OHLCV bar fixtures for testing.

    Parameters:
    -----------
    symbols : list[str]
        List of symbol names
    timeframe : str
        Bar timeframe (default: 1h)
    hours_back : int
        Hours to go back for old data
    recent_count : int
        Number of recent symbols (within last 24h)

    Returns:
    --------
    list[OHLCVBarModel]
        List of OHLCV bar fixtures
    """
    bars = []
    now = datetime.now(UTC)

    # Create recent bars (within last 24 hours) for subset of symbols
    for i, symbol in enumerate(symbols[:recent_count]):
        timestamp = now - timedelta(hours=i)  # Stagger timestamps
        bars.append(
            OHLCVBarModel(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=timestamp,
                open=Decimal("1.1000"),
                high=Decimal("1.1050"),
                low=Decimal("1.0950"),
                close=Decimal("1.1025"),
                volume=1000000,
                spread=Decimal("0.0100"),
                spread_ratio=Decimal("1.2"),
                volume_ratio=Decimal("1.5"),
            )
        )

    # Create old bars (> 24 hours ago) for remaining symbols
    for i, symbol in enumerate(symbols[recent_count:]):
        timestamp = now - timedelta(hours=hours_back + i)
        bars.append(
            OHLCVBarModel(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=timestamp,
                open=Decimal("1.1000"),
                high=Decimal("1.1050"),
                low=Decimal("1.0950"),
                close=Decimal("1.1025"),
                volume=1000000,
                spread=Decimal("0.0100"),
                spread_ratio=Decimal("1.2"),
                volume_ratio=Decimal("1.5"),
            )
        )

    return bars


def create_patterns_fixture(
    count: int = 15,
    symbol: str = "EURUSD",
    timeframe: str = "1h",
    hours_back_start: int = 23,
) -> list[Pattern]:
    """
    Create pattern fixtures for testing.

    Parameters:
    -----------
    count : int
        Number of patterns to create
    symbol : str
        Symbol for patterns
    timeframe : str
        Pattern timeframe
    hours_back_start : int
        Hours back to start creating patterns (default: 23 hours ago)

    Returns:
    --------
    list[Pattern]
        List of pattern fixtures
    """
    patterns = []
    now = datetime.now(UTC)

    for i in range(count):
        # Create patterns from 23 hours ago to recent, spaced evenly
        hours_ago = hours_back_start - (i * (hours_back_start / count))
        timestamp = now - timedelta(hours=hours_ago)
        patterns.append(
            Pattern(
                id=uuid4(),
                pattern_type="SPRING" if i % 2 == 0 else "SOS",
                symbol=symbol,
                timeframe=timeframe,
                detection_time=timestamp,
                pattern_bar_timestamp=timestamp - timedelta(hours=1),
                confidence_score=85,
                phase="C",
                entry_price=Decimal("1.1000"),
                stop_loss=Decimal("1.0950"),
                invalidation_level=Decimal("1.0940"),
                volume_ratio=Decimal("1.8"),
                spread_ratio=Decimal("1.5"),
                test_confirmed=False,
                pattern_metadata={},
            )
        )

    return patterns


def create_signals_fixture(
    executed_count: int = 5,
    rejected_count: int = 3,
    pending_count: int = 2,
    symbol: str = "EURUSD",
    timeframe: str = "1h",
) -> list[Signal]:
    """
    Create signal fixtures for testing.

    Parameters:
    -----------
    executed_count : int
        Number of executed signals
    rejected_count : int
        Number of rejected signals
    pending_count : int
        Number of pending signals
    symbol : str
        Symbol for signals
    timeframe : str
        Signal timeframe

    Returns:
    --------
    list[Signal]
        List of signal fixtures
    """
    signals = []
    now = datetime.now(UTC)

    # Create executed signals - space evenly from 22 hours ago to recent
    total_signals = executed_count + rejected_count + pending_count
    for i in range(executed_count):
        hours_ago = 22 - (i * (22 / total_signals if total_signals > 0 else 1))
        timestamp = now - timedelta(hours=hours_ago)
        signals.append(
            Signal(
                id=uuid4(),
                signal_type="LONG",
                symbol=symbol,
                timeframe=timeframe,
                generated_at=timestamp,
                entry_price=Decimal("1.1000"),
                stop_loss=Decimal("1.0950"),
                target_1=Decimal("1.1100"),
                target_2=Decimal("1.1200"),
                position_size=Decimal("10000"),
                risk_amount=Decimal("50.00"),
                r_multiple=Decimal("2.0"),
                confidence_score=85,
                status="EXECUTED",
                approval_chain={},
            )
        )

    # Create rejected signals
    for i in range(rejected_count):
        hours_ago = 22 - ((executed_count + i) * (22 / total_signals if total_signals > 0 else 1))
        timestamp = now - timedelta(hours=hours_ago)
        signals.append(
            Signal(
                id=uuid4(),
                signal_type="LONG",
                symbol=symbol,
                timeframe=timeframe,
                generated_at=timestamp,
                entry_price=Decimal("1.1000"),
                stop_loss=Decimal("1.0950"),
                target_1=Decimal("1.1100"),
                target_2=Decimal("1.1200"),
                position_size=Decimal("10000"),
                risk_amount=Decimal("50.00"),
                r_multiple=Decimal("2.0"),
                confidence_score=70,
                status="REJECTED",
                approval_chain={},
            )
        )

    # Create pending signals
    for i in range(pending_count):
        hours_ago = 22 - (
            (executed_count + rejected_count + i) * (22 / total_signals if total_signals > 0 else 1)
        )
        timestamp = now - timedelta(hours=hours_ago)
        signals.append(
            Signal(
                id=uuid4(),
                signal_type="LONG",
                symbol=symbol,
                timeframe=timeframe,
                generated_at=timestamp,
                entry_price=Decimal("1.1000"),
                stop_loss=Decimal("1.0950"),
                target_1=Decimal("1.1100"),
                target_2=Decimal("1.1200"),
                position_size=Decimal("10000"),
                risk_amount=Decimal("50.00"),
                r_multiple=Decimal("2.0"),
                confidence_score=80,
                status="PENDING",
                approval_chain={},
            )
        )

    return signals
