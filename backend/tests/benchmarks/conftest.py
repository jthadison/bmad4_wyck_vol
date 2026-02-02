"""
Benchmark fixtures and utilities (Story 22.15).

Provides shared fixtures for performance benchmarking:
- OHLCV data generation (500, 1000 bars)
- Baseline metrics for regression comparison
- Memory profiling utilities
"""

from datetime import UTC
from decimal import Decimal

import numpy as np
import pandas as pd
import pytest


def generate_ohlcv_dataframe(num_bars: int, seed: int = 42) -> pd.DataFrame:
    """
    Generate OHLCV data for benchmarking.

    Creates realistic price/volume data with random walk characteristics.

    Args:
        num_bars: Number of bars to generate
        seed: Random seed for reproducibility

    Returns:
        DataFrame with columns: timestamp, open, high, low, close, volume
    """
    np.random.seed(seed)
    dates = pd.date_range(start="2025-01-01", periods=num_bars, freq="1h", tz=UTC)
    base_price = 100.0
    returns = np.random.normal(0.0001, 0.01, num_bars)
    prices = base_price * np.exp(np.cumsum(returns))

    return pd.DataFrame(
        {
            "timestamp": dates,
            "open": prices * (1 + np.random.uniform(-0.005, 0.005, num_bars)),
            "high": prices * (1 + np.random.uniform(0, 0.01, num_bars)),
            "low": prices * (1 - np.random.uniform(0, 0.01, num_bars)),
            "close": prices,
            "volume": np.random.randint(1000, 10000, num_bars),
        }
    )


@pytest.fixture
def benchmark_ohlcv_500() -> pd.DataFrame:
    """
    Generate 500 bars of OHLCV data for benchmarking.

    Creates realistic price/volume data with random walk characteristics.
    Seed is fixed for deterministic results across runs.

    Returns:
        DataFrame with columns: timestamp, open, high, low, close, volume
    """
    return generate_ohlcv_dataframe(500)


@pytest.fixture
def benchmark_ohlcv_1000() -> pd.DataFrame:
    """
    Generate 1000 bars of OHLCV data for benchmarking.

    Creates realistic price/volume data with random walk characteristics.
    Seed is fixed for deterministic results across runs.

    Returns:
        DataFrame with columns: timestamp, open, high, low, close, volume
    """
    return generate_ohlcv_dataframe(1000)


@pytest.fixture
def benchmark_ohlcv_bars_list(benchmark_ohlcv_1000: pd.DataFrame) -> list:
    """
    Convert DataFrame to list of OHLCVBar objects for benchmarking.

    Used for campaign detection benchmarks that require OHLCVBar instances.

    Returns:
        List of OHLCVBar instances
    """
    from src.models.ohlcv import OHLCVBar

    bars = []
    for _, row in benchmark_ohlcv_1000.iterrows():
        bars.append(
            OHLCVBar(
                symbol="BENCH",
                timeframe="1h",
                timestamp=row["timestamp"].to_pydatetime(),
                open=Decimal(str(row["open"])),
                high=Decimal(str(row["high"])),
                low=Decimal(str(row["low"])),
                close=Decimal(str(row["close"])),
                volume=int(row["volume"]),
                spread=Decimal(str(row["high"] - row["low"])),
            )
        )
    return bars


# Baseline metrics (update after initial benchmark run)
BASELINE_METRICS = {
    "phase_detection_500_bars_ms": 100,
    "campaign_detection_per_bar_ms": 0.1,
    "api_preview_p95_ms": 50,
    "api_campaign_list_p95_ms": 30,
    "memory_1000_bars_mb": 50,
}

# Performance targets from Story 22.15
PERFORMANCE_TARGETS = {
    "phase_detection_500_bars_ms": 100,  # AC2: <100ms for 500 bars
    "campaign_detection_per_bar_ms": 0.1,  # AC1: <10ms per pattern (0.01ms per bar)
    "memory_operation_mb": 50,  # AC1: <50MB for operation
    "api_preview_p95_ms": 50,  # AC3: p95 <50ms
    "api_campaign_list_p95_ms": 30,  # AC3: p95 <30ms
    "event_detection_individual_ms": 50,  # Individual event detector target
}


def compare_to_baseline(
    metric_name: str,
    measured_value: float,
    tolerance_pct: float = 5.0,
) -> tuple[bool, str]:
    """
    Compare measured value to baseline with tolerance.

    Args:
        metric_name: Key in BASELINE_METRICS
        measured_value: Measured performance value
        tolerance_pct: Acceptable variance percentage (default 5%)

    Returns:
        Tuple of (passed, message)
    """
    if metric_name not in BASELINE_METRICS:
        return True, f"No baseline for {metric_name} - skipping comparison"

    baseline = BASELINE_METRICS[metric_name]
    variance_pct = ((measured_value - baseline) / baseline) * 100

    if variance_pct > tolerance_pct:
        return (
            False,
            f"{metric_name}: {measured_value:.2f} is {variance_pct:.1f}% worse than baseline {baseline}",
        )

    return (
        True,
        f"{metric_name}: {measured_value:.2f} is within {tolerance_pct}% of baseline {baseline}",
    )
