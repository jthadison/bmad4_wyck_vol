"""
Unit tests for shared validation helpers.

Story 18.1: Extract Duplicate Validation Logic (CF-007)

Tests all validation scenarios for the shared validation helper used by
Creek and Ice level calculations in level_calculator.py.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from src.models.ohlcv import OHLCVBar
from src.models.pivot import Pivot, PivotType
from src.models.price_cluster import PriceCluster
from src.models.trading_range import TradingRange
from src.models.volume_analysis import VolumeAnalysis
from src.shared.validation_helpers import (
    MIN_CLUSTER_TOUCHES,
    MIN_QUALITY_SCORE,
    validate_level_calculator_inputs,
)

# ============================================================================
# Test Fixtures and Helpers
# ============================================================================


def create_test_bar(
    symbol: str = "TEST",
    timeframe: str = "1d",
    open_price: Decimal = Decimal("100.00"),
    high: Decimal = Decimal("105.00"),
    low: Decimal = Decimal("95.00"),
    close: Decimal = Decimal("100.00"),
    volume: int = 1000000,
    timestamp: datetime | None = None,
    index: int = 0,
) -> OHLCVBar:
    """Create test OHLCV bar."""
    if timestamp is None:
        timestamp = datetime.now(UTC) + timedelta(days=index)

    return OHLCVBar(
        symbol=symbol,
        timeframe=timeframe,
        timestamp=timestamp,
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=volume,
        spread=high - low,
    )


def create_test_pivot(price: Decimal, index: int, pivot_type: PivotType = PivotType.LOW) -> Pivot:
    """Create test Pivot object."""
    bar = create_test_bar(
        high=price + Decimal("5.00"),
        low=price,
        close=price + Decimal("3.50"),
        timestamp=datetime.now(UTC) + timedelta(days=index),
        index=index,
    )
    return Pivot(
        bar=bar,
        price=price,
        type=pivot_type,
        strength=5,
        timestamp=bar.timestamp,
        index=index,
    )


def create_price_cluster(
    pivots: list[Pivot], cluster_type: PivotType = PivotType.LOW
) -> PriceCluster:
    """Create a PriceCluster from pivots."""
    prices = [p.price for p in pivots]
    avg_price = sum(prices) / len(prices)
    min_price = min(prices)
    max_price = max(prices)

    return PriceCluster(
        pivots=pivots,
        average_price=avg_price,
        min_price=min_price,
        max_price=max_price,
        price_range=max_price - min_price,
        touch_count=len(pivots),
        cluster_type=cluster_type,
        std_deviation=Decimal("0.50"),
        timestamp_range=(
            min(p.timestamp for p in pivots),
            max(p.timestamp for p in pivots),
        ),
    )


def create_test_trading_range(
    quality_score: int = 80,
    support_touch_count: int = 3,
    resistance_touch_count: int = 3,
) -> TradingRange:
    """Create test TradingRange with configurable quality and clusters."""
    # Create support pivots
    support_pivots = [
        create_test_pivot(Decimal("100.00") + Decimal(str(i * 0.2)), i * 5, PivotType.LOW)
        for i in range(support_touch_count)
    ]
    support_cluster = create_price_cluster(support_pivots, PivotType.LOW)

    # Create resistance pivots
    resistance_pivots = [
        create_test_pivot(Decimal("110.00") + Decimal(str(i * 0.2)), i * 5 + 2, PivotType.HIGH)
        for i in range(resistance_touch_count)
    ]
    resistance_cluster = create_price_cluster(resistance_pivots, PivotType.HIGH)

    return TradingRange(
        symbol="TEST",
        timeframe="1d",
        support_cluster=support_cluster,
        resistance_cluster=resistance_cluster,
        support=support_cluster.average_price,
        resistance=resistance_cluster.average_price,
        midpoint=Decimal("105.00"),
        range_width=Decimal("10.00"),
        range_width_pct=Decimal("0.10"),
        start_index=0,
        end_index=20,
        duration=21,
        quality_score=quality_score,
    )


def create_test_bars_and_volume(count: int = 30) -> tuple[list[OHLCVBar], list[VolumeAnalysis]]:
    """Create matching bars and volume analysis lists."""
    bars = [create_test_bar(index=i) for i in range(count)]
    volume_analysis = [
        VolumeAnalysis(
            bar=bars[i],
            volume_ratio=Decimal("1.0"),
            spread_ratio=Decimal("1.0"),
            close_position=Decimal("0.5"),
            effort_result=None,
        )
        for i in range(count)
    ]
    return bars, volume_analysis


# ============================================================================
# Test: None trading_range
# ============================================================================


def test_validate_rejects_none_trading_range():
    """Should raise ValueError for None trading range."""
    bars, volume_analysis = create_test_bars_and_volume(30)

    with pytest.raises(ValueError, match="trading_range cannot be None"):
        validate_level_calculator_inputs(
            None,
            bars,
            volume_analysis,
            level_type="Creek",
            cluster_attr="support_cluster",
        )


def test_validate_rejects_none_trading_range_ice():
    """Should raise ValueError for None trading range (Ice variant)."""
    bars, volume_analysis = create_test_bars_and_volume(30)

    with pytest.raises(ValueError, match="trading_range cannot be None"):
        validate_level_calculator_inputs(
            None,
            bars,
            volume_analysis,
            level_type="Ice",
            cluster_attr="resistance_cluster",
        )


# ============================================================================
# Test: Low quality score
# ============================================================================


def test_validate_rejects_low_quality_score():
    """Should raise ValueError for quality below 70 threshold."""
    trading_range = create_test_trading_range(quality_score=50)
    bars, volume_analysis = create_test_bars_and_volume(30)

    with pytest.raises(ValueError, match="quality score 50.*minimum 70"):
        validate_level_calculator_inputs(
            trading_range,
            bars,
            volume_analysis,
            level_type="Creek",
            cluster_attr="support_cluster",
        )


def test_validate_rejects_none_quality_score():
    """Should raise ValueError for None quality score."""
    trading_range = create_test_trading_range(quality_score=80)
    trading_range.quality_score = None  # Simulate None quality
    bars, volume_analysis = create_test_bars_and_volume(30)

    with pytest.raises(ValueError, match="quality score None.*minimum 70"):
        validate_level_calculator_inputs(
            trading_range,
            bars,
            volume_analysis,
            level_type="Ice",
            cluster_attr="resistance_cluster",
        )


def test_validate_accepts_exactly_70_quality():
    """Should accept quality score exactly at threshold (70)."""
    trading_range = create_test_trading_range(quality_score=70)
    bars, volume_analysis = create_test_bars_and_volume(30)

    # Should not raise - boundary condition passes
    validate_level_calculator_inputs(
        trading_range,
        bars,
        volume_analysis,
        level_type="Creek",
        cluster_attr="support_cluster",
    )


def test_validate_accepts_custom_min_quality():
    """Should accept custom minimum quality threshold."""
    trading_range = create_test_trading_range(quality_score=50)
    bars, volume_analysis = create_test_bars_and_volume(30)

    # Should pass with lowered threshold
    validate_level_calculator_inputs(
        trading_range,
        bars,
        volume_analysis,
        level_type="Creek",
        cluster_attr="support_cluster",
        min_quality=50,
    )


# ============================================================================
# Test: Missing or insufficient cluster
# ============================================================================


def test_validate_rejects_missing_support_cluster():
    """Should raise ValueError for missing support cluster."""
    trading_range = create_test_trading_range(quality_score=80)
    trading_range.support_cluster = None
    bars, volume_analysis = create_test_bars_and_volume(30)

    with pytest.raises(ValueError, match="Invalid support cluster.*minimum 2 touches"):
        validate_level_calculator_inputs(
            trading_range,
            bars,
            volume_analysis,
            level_type="Creek",
            cluster_attr="support_cluster",
        )


def test_validate_rejects_missing_resistance_cluster():
    """Should raise ValueError for missing resistance cluster."""
    trading_range = create_test_trading_range(quality_score=80)
    trading_range.resistance_cluster = None
    bars, volume_analysis = create_test_bars_and_volume(30)

    with pytest.raises(ValueError, match="Invalid resistance cluster.*minimum 2 touches"):
        validate_level_calculator_inputs(
            trading_range,
            bars,
            volume_analysis,
            level_type="Ice",
            cluster_attr="resistance_cluster",
        )


def test_validate_rejects_insufficient_cluster_touches():
    """Should raise ValueError for cluster with < 2 touches."""
    # Create valid trading range, then mock touch_count to 1
    trading_range = create_test_trading_range(quality_score=80)
    # Mock the cluster's touch_count to simulate insufficient touches
    trading_range.support_cluster.touch_count = 1
    bars, volume_analysis = create_test_bars_and_volume(30)

    with pytest.raises(ValueError, match="Invalid support cluster.*minimum 2 touches"):
        validate_level_calculator_inputs(
            trading_range,
            bars,
            volume_analysis,
            level_type="Creek",
            cluster_attr="support_cluster",
        )


def test_validate_accepts_exactly_2_touches():
    """Should accept cluster with exactly 2 touches (boundary)."""
    trading_range = create_test_trading_range(quality_score=80, support_touch_count=2)
    bars, volume_analysis = create_test_bars_and_volume(30)

    # Should not raise
    validate_level_calculator_inputs(
        trading_range,
        bars,
        volume_analysis,
        level_type="Creek",
        cluster_attr="support_cluster",
    )


# ============================================================================
# Test: Empty bars list
# ============================================================================


def test_validate_rejects_empty_bars():
    """Should raise ValueError for empty bars list."""
    trading_range = create_test_trading_range(quality_score=80)

    with pytest.raises(ValueError, match="Bars list cannot be empty"):
        validate_level_calculator_inputs(
            trading_range,
            [],
            [],
            level_type="Creek",
            cluster_attr="support_cluster",
        )


# ============================================================================
# Test: Bars/volume_analysis length mismatch
# ============================================================================


def test_validate_rejects_length_mismatch():
    """Should raise ValueError for bars/volume_analysis length mismatch."""
    trading_range = create_test_trading_range(quality_score=80)
    bars, _ = create_test_bars_and_volume(30)
    _, volume_analysis = create_test_bars_and_volume(20)  # Different length

    with pytest.raises(ValueError, match="length mismatch.*30 vs 20"):
        validate_level_calculator_inputs(
            trading_range,
            bars,
            volume_analysis,
            level_type="Ice",
            cluster_attr="resistance_cluster",
        )


# ============================================================================
# Test: Valid inputs (success cases)
# ============================================================================


def test_validate_accepts_valid_creek_inputs():
    """Should not raise for valid Creek inputs."""
    trading_range = create_test_trading_range(quality_score=80)
    bars, volume_analysis = create_test_bars_and_volume(30)

    # Should not raise
    validate_level_calculator_inputs(
        trading_range,
        bars,
        volume_analysis,
        level_type="Creek",
        cluster_attr="support_cluster",
    )


def test_validate_accepts_valid_ice_inputs():
    """Should not raise for valid Ice inputs."""
    trading_range = create_test_trading_range(quality_score=80)
    bars, volume_analysis = create_test_bars_and_volume(30)

    # Should not raise
    validate_level_calculator_inputs(
        trading_range,
        bars,
        volume_analysis,
        level_type="Ice",
        cluster_attr="resistance_cluster",
    )


def test_validate_accepts_high_quality_score():
    """Should accept high quality scores."""
    trading_range = create_test_trading_range(quality_score=95)
    bars, volume_analysis = create_test_bars_and_volume(30)

    # Should not raise
    validate_level_calculator_inputs(
        trading_range,
        bars,
        volume_analysis,
        level_type="Creek",
        cluster_attr="support_cluster",
    )


# ============================================================================
# Test: Constants are exported
# ============================================================================


def test_constants_are_exported():
    """Verify module constants are exported and have expected values."""
    assert MIN_QUALITY_SCORE == 70
    assert MIN_CLUSTER_TOUCHES == 2


# ============================================================================
# Test: Level type appears in error messages
# ============================================================================


def test_error_message_contains_level_type_creek():
    """Error message should contain 'creek' for Creek level type."""
    trading_range = create_test_trading_range(quality_score=50)
    bars, volume_analysis = create_test_bars_and_volume(30)

    with pytest.raises(ValueError) as excinfo:
        validate_level_calculator_inputs(
            trading_range,
            bars,
            volume_analysis,
            level_type="Creek",
            cluster_attr="support_cluster",
        )

    assert "creek" in str(excinfo.value).lower()


def test_error_message_contains_level_type_ice():
    """Error message should contain 'ice' for Ice level type."""
    trading_range = create_test_trading_range(quality_score=50)
    bars, volume_analysis = create_test_bars_and_volume(30)

    with pytest.raises(ValueError) as excinfo:
        validate_level_calculator_inputs(
            trading_range,
            bars,
            volume_analysis,
            level_type="Ice",
            cluster_attr="resistance_cluster",
        )

    assert "ice" in str(excinfo.value).lower()
