"""
Shared Benchmark Fixtures (Story 12.9 Task 1 Subtask 1.4).

Provides reusable pytest fixtures for performance benchmarking including:
- Synthetic OHLCV bar generation
- Pre-configured backtest engine instances
- Pattern detector instances
- Historical test data

Author: Story 12.9 Task 1
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest

from benchmarks.benchmark_config import SYNTHETIC_BARS_LARGE, SYNTHETIC_BARS_MEDIUM
from src.backtesting.backtest_engine import BacktestEngine
from src.models.backtest import BacktestConfig
from src.models.ohlcv import OHLCVBar


def _generate_synthetic_bars(
    count: int,
    symbol: str = "SYNTH",
    start_date: datetime | None = None,
    base_price: Decimal = Decimal("150.00"),
) -> list[OHLCVBar]:
    """
    Generate synthetic OHLCV bars for consistent benchmarking.

    Creates realistic price data with trending movement and noise to simulate
    real market conditions while maintaining reproducibility.

    Args:
        count: Number of bars to generate
        symbol: Trading symbol
        start_date: Starting timestamp (defaults to 2024-01-01)
        base_price: Base price for generation

    Returns:
        List of OHLCVBar objects with synthetic data
    """
    if start_date is None:
        start_date = datetime(2024, 1, 1, tzinfo=UTC)

    bars = []
    for i in range(count):
        # Simulate trending price movement with noise
        trend = Decimal(i) * Decimal("0.05")  # Slow uptrend
        noise = Decimal((i % 10) - 5)  # +/- 5 noise
        price = base_price + trend + noise

        daily_range = Decimal("5.00")
        volume = 1000000 + (i * 10000)  # Increasing volume trend

        bars.append(
            OHLCVBar(
                symbol=symbol,
                timeframe="1d",
                timestamp=start_date + timedelta(days=i),
                open=price,
                high=price + daily_range,
                low=price - daily_range,
                close=price + (daily_range * Decimal("0.3")),
                volume=volume,
                spread=daily_range,
            )
        )

    return bars


@pytest.fixture
def sample_ohlcv_bars() -> list[OHLCVBar]:
    """
    Generate 1000 synthetic OHLCV bars for benchmarking (Subtask 1.4).

    Provides medium-sized dataset suitable for component-level benchmarks.

    Returns:
        List of 1000 synthetic OHLCVBar objects
    """
    return _generate_synthetic_bars(SYNTHETIC_BARS_MEDIUM, symbol="BENCH")


@pytest.fixture
def sample_ohlcv_bars_large() -> list[OHLCVBar]:
    """
    Generate 10,000 synthetic OHLCV bars for integration benchmarks (Subtask 1.4).

    Provides large dataset for testing NFR7 backtest speed requirements.

    Returns:
        List of 10,000 synthetic OHLCVBar objects
    """
    return _generate_synthetic_bars(SYNTHETIC_BARS_LARGE, symbol="BENCH_LARGE")


@pytest.fixture
def backtest_engine() -> BacktestEngine:
    """
    Pre-configured BacktestEngine instance for benchmarking (Subtask 1.4).

    Returns engine with standard configuration for consistent benchmark results.

    Returns:
        Initialized BacktestEngine instance
    """
    config = BacktestConfig(
        symbol="BENCH",
        start_date=datetime(2024, 1, 1).date(),
        end_date=datetime(2024, 12, 31).date(),
        initial_capital=Decimal("100000"),
        max_position_size=Decimal("0.02"),
        commission_per_share=Decimal("0.005"),
    )
    return BacktestEngine(config)


@pytest.fixture
def pattern_detectors() -> dict[str, Any]:
    """
    All pattern detector functions for benchmarking (Subtask 1.4).

    Provides dictionary of detector function references for pattern detection benchmarks.

    Returns:
        Dict mapping pattern names to detector functions:
        - "spring": detect_spring function
        - "sos": detect_sos function
        - "utad": detect_utad function
    """
    from src.pattern_engine.detectors.sos_detector import detect_sos
    from src.pattern_engine.detectors.spring_detector import detect_spring
    from src.pattern_engine.detectors.utad_detector import detect_utad

    return {
        "spring": detect_spring,
        "sos": detect_sos,
        "utad": detect_utad,
    }


@pytest.fixture
def test_symbol_data() -> list[OHLCVBar]:
    """
    Historical data for AAPL 2020-2024 simulation (Subtask 1.4).

    Generates synthetic data simulating 4 years of daily bars (approximately 1000 bars).
    For realistic benchmarking of pattern detection and backtesting.

    Note: In production, this could load actual historical data from CSV/Parquet.

    Returns:
        List of ~1000 OHLCVBar objects simulating AAPL 2020-2024
    """
    start_date = datetime(2020, 1, 1, tzinfo=UTC)
    # 4 years × ~252 trading days = ~1008 bars
    return _generate_synthetic_bars(
        count=1008,
        symbol="AAPL",
        start_date=start_date,
        base_price=Decimal("120.00"),  # AAPL ~$120 in 2020
    )
