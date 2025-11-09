"""
Shared test fixtures for SOS/LPS signal generator tests.
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import Mock
from uuid import uuid4

import pytest

from src.models.lps import LPS
from src.models.ohlcv import OHLCVBar
from src.models.pivot import Pivot, PivotType
from src.models.price_cluster import PriceCluster
from src.models.sos_breakout import SOSBreakout
from src.models.trading_range import RangeStatus, TradingRange


@pytest.fixture
def ohlcv_bar():
    """Create test OHLCV bar."""
    return OHLCVBar(
        symbol="AAPL",
        timestamp=datetime(2024, 1, 15, 14, 30, tzinfo=UTC),
        open=Decimal("101.00"),
        high=Decimal("102.50"),
        low=Decimal("100.50"),
        close=Decimal("102.00"),
        volume=200000,
        spread=Decimal("2.00"),  # high - low
        timeframe="1d",
    )


@pytest.fixture
def trading_range():
    """Create test trading range with Ice=$100, Jump=$120."""
    # Create support pivots (lows at $95)
    support_bar = OHLCVBar(
        symbol="AAPL",
        timestamp=datetime(2024, 1, 10, 14, 30, tzinfo=UTC),
        open=Decimal("96.00"),
        high=Decimal("96.50"),
        low=Decimal("95.00"),
        close=Decimal("95.50"),
        volume=150000,
        spread=Decimal("1.50"),
        timeframe="1d",
    )

    support_pivot1 = Pivot(
        bar=support_bar,
        price=Decimal("95.00"),
        type=PivotType.LOW,
        strength=5,
        timestamp=support_bar.timestamp,
        index=10,
    )
    support_pivot2 = Pivot(
        bar=support_bar,
        price=Decimal("95.00"),
        type=PivotType.LOW,
        strength=5,
        timestamp=support_bar.timestamp,
        index=20,
    )

    support_cluster = PriceCluster(
        pivots=[support_pivot1, support_pivot2],
        average_price=Decimal("95.00"),
        min_price=Decimal("95.00"),
        max_price=Decimal("95.00"),
        price_range=Decimal("0.00"),
        touch_count=2,
        cluster_type=PivotType.LOW,
        std_deviation=Decimal("0.00"),
        timestamp_range=(support_bar.timestamp, support_bar.timestamp),
    )

    # Create resistance pivots (highs at $100)
    resistance_bar = OHLCVBar(
        symbol="AAPL",
        timestamp=datetime(2024, 1, 15, 14, 30, tzinfo=UTC),
        open=Decimal("99.00"),
        high=Decimal("100.00"),
        low=Decimal("98.50"),
        close=Decimal("99.50"),
        volume=150000,
        spread=Decimal("1.50"),
        timeframe="1d",
    )

    resistance_pivot1 = Pivot(
        bar=resistance_bar,
        price=Decimal("100.00"),
        type=PivotType.HIGH,
        strength=5,
        timestamp=resistance_bar.timestamp,
        index=15,
    )
    resistance_pivot2 = Pivot(
        bar=resistance_bar,
        price=Decimal("100.00"),
        type=PivotType.HIGH,
        strength=5,
        timestamp=resistance_bar.timestamp,
        index=25,
    )

    resistance_cluster = PriceCluster(
        pivots=[resistance_pivot1, resistance_pivot2],
        average_price=Decimal("100.00"),
        min_price=Decimal("100.00"),
        max_price=Decimal("100.00"),
        price_range=Decimal("0.00"),
        touch_count=2,
        cluster_type=PivotType.HIGH,
        std_deviation=Decimal("0.00"),
        timestamp_range=(resistance_bar.timestamp, resistance_bar.timestamp),
    )

    range_obj = TradingRange(
        symbol="AAPL",
        timeframe="1d",
        support_cluster=support_cluster,
        resistance_cluster=resistance_cluster,
        support=Decimal("95.00"),
        resistance=Decimal("100.00"),
        midpoint=Decimal("97.50"),
        range_width=Decimal("5.00"),
        range_width_pct=Decimal("0.0526"),
        start_index=10,
        end_index=50,
        duration=41,
        status=RangeStatus.ACTIVE,
    )

    # Mock Creek, Ice, and Jump levels
    creek_mock = Mock()
    creek_mock.price = Decimal("95.00")
    range_obj.creek = creek_mock

    ice_mock = Mock()
    ice_mock.price = Decimal("100.00")
    range_obj.ice = ice_mock

    jump_mock = Mock()
    jump_mock.price = Decimal("120.00")
    range_obj.jump = jump_mock

    return range_obj


@pytest.fixture
def sos_breakout(ohlcv_bar):
    """Create test SOS breakout at $102 (2% above Ice)."""
    return SOSBreakout(
        bar=ohlcv_bar,
        breakout_pct=Decimal("0.02"),  # 2% above Ice
        volume_ratio=Decimal("2.5"),  # 2.5x average
        ice_reference=Decimal("100.00"),
        breakout_price=Decimal("102.00"),
        detection_timestamp=datetime.now(UTC),
        trading_range_id=uuid4(),
        spread_ratio=Decimal("1.6"),
        close_position=Decimal("0.75"),
        spread=Decimal("2.00"),
    )


@pytest.fixture
def lps_pattern(sos_breakout):
    """Create test LPS pattern with pullback to $100.50."""
    lps_bar = OHLCVBar(
        symbol="AAPL",
        timestamp=datetime(2024, 1, 16, 10, 0, tzinfo=UTC),
        open=Decimal("101.50"),
        high=Decimal("101.80"),
        low=Decimal("100.50"),
        close=Decimal("101.00"),
        volume=120000,
        spread=Decimal("1.30"),  # high - low
        timeframe="1d",
    )

    return LPS(
        bar=lps_bar,
        distance_from_ice=Decimal("0.005"),  # 0.5% above Ice
        distance_quality="PREMIUM",
        distance_confidence_bonus=10,
        volume_ratio=Decimal("0.6"),
        range_avg_volume=150000,
        volume_ratio_vs_avg=Decimal("0.8"),
        volume_ratio_vs_sos=Decimal("0.6"),
        pullback_spread=Decimal("1.30"),
        range_avg_spread=Decimal("2.00"),
        spread_ratio=Decimal("0.65"),
        spread_quality="NARROW",
        effort_result="NO_SUPPLY",
        effort_result_bonus=10,
        sos_reference=sos_breakout.id,
        held_support=True,
        pullback_low=Decimal("100.50"),
        ice_level=Decimal("100.00"),
        sos_volume=200000,
        pullback_volume=120000,
        bars_after_sos=5,
        bounce_confirmed=True,
        bounce_bar_timestamp=datetime.now(UTC),
        detection_timestamp=datetime.now(UTC),
        trading_range_id=uuid4(),
        is_double_bottom=False,
        second_test_timestamp=None,
        atr_14=Decimal("2.50"),
        stop_distance=Decimal("3.00"),
        stop_distance_pct=Decimal("3.0"),
        stop_price=Decimal("97.00"),
        volume_trend="DECLINING",
        volume_trend_quality="EXCELLENT",
        volume_trend_bonus=5,
    )
