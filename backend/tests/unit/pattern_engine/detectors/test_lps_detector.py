"""
Unit tests for lps_detector module.

Tests LPS (Last Point of Support) pattern detection with synthetic data covering
all acceptance criteria:
- AC 3: Pullback timing window (within 10 bars after SOS)
- AC 4: Distance from Ice validation (tiered: 1%, 2%, 3% max)
- AC 5: CRITICAL support hold (must hold above Ice - 2%)
- AC 6: Volume reduction vs range average (NEW baseline)
- AC 6B: Spread analysis and Effort vs Result (Wyckoff's Third Law)
- AC 7: Bounce confirmation required
- AC 9: Valid LPS detection with synthetic pullback
- AC 12: ATR-based stop placement
- AC 14: Volume trend analysis during pullback
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from src.models.ohlcv import OHLCVBar
from src.models.sos_breakout import SOSBreakout
from src.models.trading_range import TradingRange, RangeStatus
from src.models.price_cluster import PriceCluster
from src.models.ice_level import IceLevel
from src.models.creek_level import CreekLevel
from src.models.pivot import Pivot, PivotType
from src.models.touch_detail import TouchDetail
from src.pattern_engine.detectors.lps_detector import (
    detect_lps,
    calculate_range_average_volume,
    calculate_range_average_spread,
    calculate_atr,
    analyze_pullback_volume_trend,
    calculate_lps_position_size,
)


def create_test_bar(
    timestamp: datetime,
    low: Decimal,
    high: Decimal,
    close: Decimal,
    volume: int,
    symbol: str = "AAPL",
) -> OHLCVBar:
    """
    Create test OHLCV bar with specified parameters.

    Args:
        timestamp: Bar timestamp
        low: Low price
        high: High price
        close: Close price
        volume: Volume
        symbol: Stock symbol (default: AAPL)

    Returns:
        OHLCVBar instance for testing
    """
    spread = high - low
    open_price = (high + low) / 2

    return OHLCVBar(
        id=uuid4(),
        symbol=symbol,
        timeframe="1d",
        timestamp=timestamp,
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=volume,
        spread=spread,
        spread_ratio=Decimal("1.0"),
        volume_ratio=Decimal("1.0"),
    )


def create_trading_range(
    ice_level: Decimal,
    creek_level: Decimal = None,
    symbol: str = "AAPL",
    start_timestamp: datetime = None,
    end_timestamp: datetime = None,
) -> TradingRange:
    """
    Create test trading range with Ice level.

    Args:
        ice_level: Ice price level (resistance)
        creek_level: Creek price level (support) - optional
        symbol: Stock symbol (default: AAPL)
        start_timestamp: Range start time
        end_timestamp: Range end time

    Returns:
        TradingRange instance for testing
    """
    support = creek_level if creek_level else ice_level * Decimal("0.90")
    resistance = ice_level
    midpoint = (support + resistance) / 2
    range_width = resistance - support
    # Round to 4 decimal places to avoid precision issues
    range_width_pct = ((range_width / support) * Decimal("100")).quantize(Decimal("0.0001"))

    # Use default timestamps if not provided
    base_timestamp = start_timestamp if start_timestamp else datetime(2024, 1, 1, tzinfo=UTC)
    end_ts = end_timestamp if end_timestamp else base_timestamp + timedelta(days=30)

    # Create pivot bars for support cluster (minimum 2 pivots required)
    support_pivots = []
    for i, idx in enumerate([10, 20]):
        bar = create_test_bar(
            timestamp=base_timestamp + timedelta(days=idx),
            low=support,
            high=support + Decimal("3.00"),
            close=support + Decimal("1.50"),
            volume=150000,
            symbol=symbol,
        )
        pivot = Pivot(
            bar=bar,
            price=bar.low,
            type=PivotType.LOW,
            strength=5,
            timestamp=bar.timestamp,
            index=idx,
        )
        support_pivots.append(pivot)

    support_cluster = PriceCluster(
        pivots=support_pivots,
        average_price=support,
        min_price=support - Decimal("0.50"),
        max_price=support + Decimal("0.50"),
        price_range=Decimal("1.00"),
        touch_count=2,
        cluster_type=PivotType.LOW,
        std_deviation=Decimal("0.25"),
        timestamp_range=(support_pivots[0].timestamp, support_pivots[-1].timestamp),
    )

    # Create pivot bars for resistance cluster (minimum 2 pivots required)
    resistance_pivots = []
    for i, idx in enumerate([15, 25]):
        bar = create_test_bar(
            timestamp=base_timestamp + timedelta(days=idx),
            low=resistance - Decimal("2.00"),
            high=resistance,
            close=resistance - Decimal("1.00"),
            volume=150000,
            symbol=symbol,
        )
        pivot = Pivot(
            bar=bar,
            price=bar.high,
            type=PivotType.HIGH,
            strength=5,
            timestamp=bar.timestamp,
            index=idx,
        )
        resistance_pivots.append(pivot)

    resistance_cluster = PriceCluster(
        pivots=resistance_pivots,
        average_price=resistance,
        min_price=resistance - Decimal("0.50"),
        max_price=resistance + Decimal("0.50"),
        price_range=Decimal("1.00"),
        touch_count=2,
        cluster_type=PivotType.HIGH,
        std_deviation=Decimal("0.25"),
        timestamp_range=(resistance_pivots[0].timestamp, resistance_pivots[-1].timestamp),
    )

    # Create Ice level with all required fields
    ice = IceLevel(
        price=ice_level,
        absolute_high=ice_level + Decimal("1.00"),
        touch_count=2,
        touch_details=[
            TouchDetail(
                index=i,
                price=ice_level,
                volume=150000,
                volume_ratio=Decimal("1.0"),
                close_position=Decimal("0.3"),
                rejection_wick=Decimal("0.5"),
                timestamp=base_timestamp + timedelta(days=idx),
            )
            for i, idx in enumerate([15, 25])
        ],
        strength_score=75,
        strength_rating="STRONG",
        last_test_timestamp=base_timestamp + timedelta(days=25),
        first_test_timestamp=base_timestamp + timedelta(days=15),
        hold_duration=10,
        confidence="HIGH",
        volume_trend="DECREASING",
    )

    # Create Creek level if specified
    creek = None
    if creek_level:
        creek = CreekLevel(
            price=creek_level,
            absolute_low=creek_level - Decimal("1.00"),
            touch_count=2,
            touch_details=[
                TouchDetail(
                    index=i,
                    price=creek_level,
                    volume=150000,
                    volume_ratio=Decimal("1.0"),
                    close_position=Decimal("0.7"),
                    rejection_wick=Decimal("0.5"),
                    timestamp=base_timestamp + timedelta(days=idx),
                )
                for i, idx in enumerate([10, 20])
            ],
            strength_score=70,
            strength_rating="STRONG",
            last_test_timestamp=base_timestamp + timedelta(days=20),
            first_test_timestamp=base_timestamp + timedelta(days=10),
            hold_duration=10,
            confidence="HIGH",
            volume_trend="DECREASING",
        )

    trading_range = TradingRange(
        id=uuid4(),
        symbol=symbol,
        timeframe="1d",
        support_cluster=support_cluster,
        resistance_cluster=resistance_cluster,
        support=support,
        resistance=resistance,
        midpoint=midpoint,
        range_width=range_width,
        range_width_pct=range_width_pct,
        start_index=0,
        end_index=30,
        duration=31,
        quality_score=75,
        ice=ice,
        creek=creek,
        status=RangeStatus.ACTIVE,
        start_timestamp=base_timestamp,
        end_timestamp=end_ts,
    )

    return trading_range


def create_sos_breakout(
    bar_timestamp: datetime,
    breakout_price: Decimal,
    ice_reference: Decimal,
    volume: int,
    trading_range_id: str = None,
) -> SOSBreakout:
    """
    Create test SOS breakout.

    Args:
        bar_timestamp: Timestamp of SOS bar
        breakout_price: Close price that broke above Ice
        ice_reference: Ice level at detection
        volume: SOS bar volume
        trading_range_id: Associated trading range UUID

    Returns:
        SOSBreakout instance for testing
    """
    bar = create_test_bar(
        timestamp=bar_timestamp,
        low=ice_reference * Decimal("1.005"),
        high=breakout_price * Decimal("1.01"),
        close=breakout_price,
        volume=volume,
    )

    breakout_pct = ((breakout_price - ice_reference) / ice_reference) * Decimal("100")

    return SOSBreakout(
        id=uuid4(),
        bar=bar,
        breakout_pct=breakout_pct,
        volume_ratio=Decimal("2.0"),  # High volume for SOS
        ice_reference=ice_reference,
        breakout_price=breakout_price,
        detection_timestamp=datetime.now(UTC),
        trading_range_id=uuid4() if not trading_range_id else trading_range_id,
        spread_ratio=Decimal("1.5"),
        close_position=Decimal("0.8"),
        spread=bar.spread,
    )


# AC 9: Valid LPS detection with synthetic pullback
def test_detect_lps_valid_pullback():
    """
    Test AC 9: Synthetic pullback to Ice with reduced volume detected.

    Scenario:
    - SOS breaks out at $102 (2% above Ice = $100)
    - Pullback to $100.50 (0.5% above Ice - PREMIUM tier)
    - Reduced volume: 120k vs 150k range avg (0.8x - GOOD)
    - Bounce confirmed: $101.20 next bar
    - All validation passes
    """
    # Arrange: Create trading range with Ice at $100
    start_time = datetime.now(UTC) - timedelta(days=30)
    end_time = datetime.now(UTC) - timedelta(days=5)
    trading_range = create_trading_range(
        ice_level=Decimal("100.00"),
        creek_level=Decimal("95.00"),
        start_timestamp=start_time,
        end_timestamp=end_time,
    )

    # Create SOS at bar index 25
    sos_timestamp = datetime.now(UTC) - timedelta(days=4)
    sos = create_sos_breakout(
        bar_timestamp=sos_timestamp,
        breakout_price=Decimal("102.00"),
        ice_reference=Decimal("100.00"),
        volume=200000,  # High volume for SOS
        trading_range_id=str(trading_range.id),
    )

    # Create bars: range bars + SOS + pullback + bounce
    bars = []

    # Range bars (30 days, average volume 150k, average spread $3)
    for i in range(30):
        bar_time = start_time + timedelta(days=i)
        bars.append(
            create_test_bar(
                timestamp=bar_time,
                low=Decimal("95.00"),
                high=Decimal("98.00"),  # $3 spread
                close=Decimal("96.50"),
                volume=150000,  # Range average
            )
        )

    # SOS bar (bar 30)
    bars.append(sos.bar)

    # Pullback bars
    # Bar 31: $101.50 (pullback starts, volume 140k)
    bars.append(
        create_test_bar(
            timestamp=sos_timestamp + timedelta(days=1),
            low=Decimal("101.20"),
            high=Decimal("101.80"),  # $0.60 spread (narrow)
            close=Decimal("101.50"),
            volume=140000,
        )
    )

    # Bar 32: $101.00 (continuing pullback, volume 130k - declining)
    bars.append(
        create_test_bar(
            timestamp=sos_timestamp + timedelta(days=2),
            low=Decimal("100.70"),
            high=Decimal("101.20"),  # $0.50 spread (narrow)
            close=Decimal("101.00"),
            volume=130000,
        )
    )

    # Bar 33: $100.50 (pullback low - tests Ice, volume 120k - excellent reduced)
    bars.append(
        create_test_bar(
            timestamp=sos_timestamp + timedelta(days=3),
            low=Decimal("100.50"),  # 0.5% above Ice (PREMIUM)
            high=Decimal("101.00"),  # $0.50 spread (narrow)
            close=Decimal("100.70"),
            volume=120000,  # 0.8x range avg (GOOD volume)
        )
    )

    # Bar 34: $101.60 (bounce confirmation - 1.09% above pullback low)
    bars.append(
        create_test_bar(
            timestamp=sos_timestamp + timedelta(days=4),
            low=Decimal("101.00"),
            high=Decimal("102.00"),
            close=Decimal("101.60"),  # Confirms bounce (>= 101.505)
            volume=135000,
        )
    )

    volume_analysis = {}

    # Act
    lps = detect_lps(trading_range, sos, bars, volume_analysis)

    # Assert
    assert lps is not None, "LPS should be detected"
    assert lps.pullback_low == Decimal("100.50"), "Pullback low at $100.50"
    assert lps.distance_from_ice < Decimal("1.0"), "0.5% above Ice (PREMIUM)"
    assert lps.distance_quality == "PREMIUM", "Should be PREMIUM tier"
    assert lps.distance_confidence_bonus == 10, "Should get +10 bonus"
    assert lps.held_support is True, "Support held above Ice - 2%"
    assert lps.range_avg_volume == 150000, "Range avg volume should be 150k"
    assert lps.volume_ratio_vs_avg == Decimal("0.8000"), "0.8x range avg (GOOD)"
    assert lps.bars_after_sos == 3, "LPS 3 bars after SOS"
    assert lps.bounce_confirmed is True, "Bounce confirmed"
    assert lps.sos_reference == sos.id, "References correct SOS"
    assert lps.get_support_quality() == "EXCELLENT", "Support quality EXCELLENT"
    assert lps.get_volume_quality() == "GOOD", "Volume quality GOOD"
    assert lps.volume_trend == "DECLINING", "Volume trend should be declining"


# AC 5: Breaking Ice - 2% invalidates LPS
def test_lps_breaks_ice_support_rejected():
    """
    Test AC 5: Breaking Ice - 2% invalidates LPS.

    Scenario:
    - Ice at $100
    - Ice - 2% = $98 (minimum support level)
    - Pullback low at $97.50 (breaks minimum support)
    - LPS REJECTED (false breakout)
    """
    # Arrange
    start_time = datetime.now(UTC) - timedelta(days=30)
    end_time = datetime.now(UTC) - timedelta(days=5)
    trading_range = create_trading_range(
        ice_level=Decimal("100.00"),
        start_timestamp=start_time,
        end_timestamp=end_time,
    )

    sos_timestamp = datetime.now(UTC) - timedelta(days=4)
    sos = create_sos_breakout(
        bar_timestamp=sos_timestamp,
        breakout_price=Decimal("102.00"),
        ice_reference=Decimal("100.00"),
        volume=200000,
    )

    bars = []

    # Range bars
    for i in range(30):
        bars.append(
            create_test_bar(
                timestamp=start_time + timedelta(days=i),
                low=Decimal("95.00"),
                high=Decimal("98.00"),
                close=Decimal("96.50"),
                volume=150000,
            )
        )

    bars.append(sos.bar)

    # Pullback breaks Ice - 2% = $98.00
    bars.append(
        create_test_bar(
            timestamp=sos_timestamp + timedelta(days=1),
            low=Decimal("97.50"),  # Below $98 minimum support
            high=Decimal("99.00"),
            close=Decimal("98.00"),
            volume=120000,
        )
    )

    volume_analysis = {}

    # Act
    lps = detect_lps(trading_range, sos, bars, volume_analysis)

    # Assert
    assert lps is None, "LPS should be rejected - broke Ice support (false breakout)"


# AC 3: Pullback timing window validation
def test_lps_within_10_bars_accepted():
    """
    Test AC 3: LPS at exactly 10 bars after SOS should be accepted.
    """
    start_time = datetime.now(UTC) - timedelta(days=30)
    end_time = datetime.now(UTC) - timedelta(days=15)
    trading_range = create_trading_range(
        ice_level=Decimal("100.00"),
        start_timestamp=start_time,
        end_timestamp=end_time,
    )

    sos_timestamp = datetime.now(UTC) - timedelta(days=14)
    sos = create_sos_breakout(
        bar_timestamp=sos_timestamp,
        breakout_price=Decimal("102.00"),
        ice_reference=Decimal("100.00"),
        volume=200000,
    )

    bars = []

    # Range bars
    for i in range(30):
        bars.append(
            create_test_bar(
                timestamp=start_time + timedelta(days=i),
                low=Decimal("95.00"),
                high=Decimal("98.00"),
                close=Decimal("96.50"),
                volume=150000,
            )
        )

    bars.append(sos.bar)

    # 9 bars after SOS (stay above Ice)
    for i in range(1, 10):
        bars.append(
            create_test_bar(
                timestamp=sos_timestamp + timedelta(days=i),
                low=Decimal("101.50"),
                high=Decimal("103.00"),
                close=Decimal("102.00"),
                volume=140000,
            )
        )

    # Bar 10: Pullback low (exactly 10 bars after SOS)
    bars.append(
        create_test_bar(
            timestamp=sos_timestamp + timedelta(days=10),
            low=Decimal("100.50"),
            high=Decimal("101.50"),
            close=Decimal("101.00"),
            volume=120000,
        )
    )

    # Bounce confirmation
    bars.append(
        create_test_bar(
            timestamp=sos_timestamp + timedelta(days=11),
            low=Decimal("101.00"),
            high=Decimal("102.00"),
            close=Decimal("101.50"),
            volume=135000,
        )
    )

    volume_analysis = {}

    # Act
    lps = detect_lps(trading_range, sos, bars, volume_analysis)

    # Assert
    assert lps is not None, "LPS within 10 bars should be accepted"
    assert lps.bars_after_sos == 10, "Should be exactly 10 bars after SOS"


def test_lps_after_10_bars_rejected():
    """
    Test AC 3: LPS after 10 bars should be rejected.
    """
    start_time = datetime.now(UTC) - timedelta(days=30)
    end_time = datetime.now(UTC) - timedelta(days=16)
    trading_range = create_trading_range(
        ice_level=Decimal("100.00"),
        start_timestamp=start_time,
        end_timestamp=end_time,
    )

    sos_timestamp = datetime.now(UTC) - timedelta(days=15)
    sos = create_sos_breakout(
        bar_timestamp=sos_timestamp,
        breakout_price=Decimal("102.00"),
        ice_reference=Decimal("100.00"),
        volume=200000,
    )

    bars = []

    # Range bars
    for i in range(30):
        bars.append(
            create_test_bar(
                timestamp=start_time + timedelta(days=i),
                low=Decimal("95.00"),
                high=Decimal("98.00"),
                close=Decimal("96.50"),
                volume=150000,
            )
        )

    bars.append(sos.bar)

    # 10 bars after SOS
    for i in range(1, 11):
        bars.append(
            create_test_bar(
                timestamp=sos_timestamp + timedelta(days=i),
                low=Decimal("101.50"),
                high=Decimal("103.00"),
                close=Decimal("102.00"),
                volume=140000,
            )
        )

    # Bar 11: Pullback low (11 bars after SOS - too late)
    bars.append(
        create_test_bar(
            timestamp=sos_timestamp + timedelta(days=11),
            low=Decimal("100.50"),
            high=Decimal("101.50"),
            close=Decimal("101.00"),
            volume=120000,
        )
    )

    volume_analysis = {}

    # Act
    lps = detect_lps(trading_range, sos, bars, volume_analysis)

    # Assert
    assert lps is None, "LPS >10 bars after SOS should be rejected"


# AC 4: Distance tier tests
@pytest.mark.parametrize(
    "pullback_low,expected_tier,expected_bonus",
    [
        (Decimal("100.80"), "PREMIUM", 10),  # 0.8% above Ice
        (Decimal("101.50"), "QUALITY", 5),  # 1.5% above Ice
        (Decimal("102.50"), "ACCEPTABLE", 0),  # 2.5% above Ice
    ],
)
def test_lps_distance_tiers(pullback_low, expected_tier, expected_bonus):
    """
    Test AC 4: Distance tier validation with bonuses.

    Tests PREMIUM (<=1%), QUALITY (<=2%), ACCEPTABLE (<=3%) tiers.
    """
    start_time = datetime.now(UTC) - timedelta(days=30)
    end_time = datetime.now(UTC) - timedelta(days=5)
    trading_range = create_trading_range(
        ice_level=Decimal("100.00"),
        start_timestamp=start_time,
        end_timestamp=end_time,
    )

    sos_timestamp = datetime.now(UTC) - timedelta(days=4)
    sos = create_sos_breakout(
        bar_timestamp=sos_timestamp,
        breakout_price=Decimal("102.00"),
        ice_reference=Decimal("100.00"),
        volume=200000,
    )

    bars = []

    # Range bars
    for i in range(30):
        bars.append(
            create_test_bar(
                timestamp=start_time + timedelta(days=i),
                low=Decimal("95.00"),
                high=Decimal("98.00"),
                close=Decimal("96.50"),
                volume=150000,
            )
        )

    bars.append(sos.bar)

    # Pullback with specified low
    bars.append(
        create_test_bar(
            timestamp=sos_timestamp + timedelta(days=1),
            low=pullback_low,
            high=pullback_low + Decimal("1.00"),
            close=pullback_low + Decimal("0.50"),
            volume=120000,
        )
    )

    # Bounce
    bars.append(
        create_test_bar(
            timestamp=sos_timestamp + timedelta(days=2),
            low=pullback_low + Decimal("0.50"),
            high=pullback_low + Decimal("1.50"),
            close=pullback_low + Decimal("1.20"),
            volume=135000,
        )
    )

    volume_analysis = {}

    # Act
    lps = detect_lps(trading_range, sos, bars, volume_analysis)

    # Assert
    assert lps is not None, f"LPS should be detected for {expected_tier} tier"
    assert lps.distance_quality == expected_tier, f"Should be {expected_tier} tier"
    assert lps.distance_confidence_bonus == expected_bonus, f"Should get +{expected_bonus} bonus"


def test_lps_too_far_from_ice_rejected():
    """
    Test AC 4: Pullback >3% above Ice should be rejected (not testing support).
    """
    start_time = datetime.now(UTC) - timedelta(days=30)
    end_time = datetime.now(UTC) - timedelta(days=5)
    trading_range = create_trading_range(
        ice_level=Decimal("100.00"),
        start_timestamp=start_time,
        end_timestamp=end_time,
    )

    sos_timestamp = datetime.now(UTC) - timedelta(days=4)
    sos = create_sos_breakout(
        bar_timestamp=sos_timestamp,
        breakout_price=Decimal("102.00"),
        ice_reference=Decimal("100.00"),
        volume=200000,
    )

    bars = []

    # Range bars
    for i in range(30):
        bars.append(
            create_test_bar(
                timestamp=start_time + timedelta(days=i),
                low=Decimal("95.00"),
                high=Decimal("98.00"),
                close=Decimal("96.50"),
                volume=150000,
            )
        )

    bars.append(sos.bar)

    # Pullback low at $103.50 (3.5% above Ice - too far)
    bars.append(
        create_test_bar(
            timestamp=sos_timestamp + timedelta(days=1),
            low=Decimal("103.50"),
            high=Decimal("104.50"),
            close=Decimal("104.00"),
            volume=120000,
        )
    )

    volume_analysis = {}

    # Act
    lps = detect_lps(trading_range, sos, bars, volume_analysis)

    # Assert
    assert lps is None, "Pullback >3% above Ice rejected - not testing support"


# AC 6: Volume quality tests (range average baseline)
@pytest.mark.parametrize(
    "pullback_volume,expected_quality",
    [
        (80000, "EXCELLENT"),  # 0.53x range avg (< 0.6x)
        (120000, "GOOD"),  # 0.8x range avg (0.6-0.9x)
        (150000, "ACCEPTABLE"),  # 1.0x range avg (0.9-1.1x)
        (180000, "POOR"),  # 1.2x range avg (> 1.1x)
    ],
)
def test_lps_volume_quality_tiers(pullback_volume, expected_quality):
    """
    Test AC 6: Volume quality assessment using range average baseline.

    Tests EXCELLENT (<0.6x), GOOD (0.6-0.9x), ACCEPTABLE (0.9-1.1x), POOR (>1.1x).
    """
    start_time = datetime.now(UTC) - timedelta(days=30)
    end_time = datetime.now(UTC) - timedelta(days=5)
    trading_range = create_trading_range(
        ice_level=Decimal("100.00"),
        start_timestamp=start_time,
        end_timestamp=end_time,
    )

    sos_timestamp = datetime.now(UTC) - timedelta(days=4)
    sos = create_sos_breakout(
        bar_timestamp=sos_timestamp,
        breakout_price=Decimal("102.00"),
        ice_reference=Decimal("100.00"),
        volume=200000,  # Climactic SOS volume
    )

    bars = []

    # Range bars with 150k average volume
    for i in range(30):
        bars.append(
            create_test_bar(
                timestamp=start_time + timedelta(days=i),
                low=Decimal("95.00"),
                high=Decimal("98.00"),
                close=Decimal("96.50"),
                volume=150000,  # Range average
            )
        )

    bars.append(sos.bar)

    # Pullback with specified volume
    bars.append(
        create_test_bar(
            timestamp=sos_timestamp + timedelta(days=1),
            low=Decimal("100.50"),
            high=Decimal("101.50"),
            close=Decimal("101.00"),
            volume=pullback_volume,
        )
    )

    # Bounce
    bars.append(
        create_test_bar(
            timestamp=sos_timestamp + timedelta(days=2),
            low=Decimal("101.00"),
            high=Decimal("102.00"),
            close=Decimal("101.50"),
            volume=135000,
        )
    )

    volume_analysis = {}

    # Act
    lps = detect_lps(trading_range, sos, bars, volume_analysis)

    # Assert
    assert lps is not None, f"LPS should be detected for {expected_quality} volume"
    assert lps.get_volume_quality() == expected_quality, f"Volume quality should be {expected_quality}"


# AC 6B: Spread analysis and Effort vs Result tests
def test_lps_no_supply_pattern():
    """
    Test AC 6B: No Supply pattern (low volume + narrow spread = +10 bonus).

    This is the BEST case: lack of selling pressure with minimal price movement.
    """
    start_time = datetime.now(UTC) - timedelta(days=30)
    end_time = datetime.now(UTC) - timedelta(days=5)
    trading_range = create_trading_range(
        ice_level=Decimal("100.00"),
        start_timestamp=start_time,
        end_timestamp=end_time,
    )

    sos_timestamp = datetime.now(UTC) - timedelta(days=4)
    sos = create_sos_breakout(
        bar_timestamp=sos_timestamp,
        breakout_price=Decimal("102.00"),
        ice_reference=Decimal("100.00"),
        volume=200000,
    )

    bars = []

    # Range bars with $3 average spread
    for i in range(30):
        bars.append(
            create_test_bar(
                timestamp=start_time + timedelta(days=i),
                low=Decimal("95.00"),
                high=Decimal("98.00"),  # $3 spread
                close=Decimal("96.50"),
                volume=150000,
            )
        )

    bars.append(sos.bar)

    # Pullback: Low volume (80k = 0.53x) + Narrow spread ($2 = 0.67x)
    bars.append(
        create_test_bar(
            timestamp=sos_timestamp + timedelta(days=1),
            low=Decimal("100.50"),
            high=Decimal("102.50"),  # $2 spread (narrow)
            close=Decimal("101.00"),
            volume=80000,  # Low volume (EXCELLENT)
        )
    )

    # Bounce
    bars.append(
        create_test_bar(
            timestamp=sos_timestamp + timedelta(days=2),
            low=Decimal("101.00"),
            high=Decimal("102.00"),
            close=Decimal("101.50"),
            volume=135000,
        )
    )

    volume_analysis = {}

    # Act
    lps = detect_lps(trading_range, sos, bars, volume_analysis)

    # Assert
    assert lps is not None, "LPS should be detected"
    assert lps.spread_quality == "NARROW", "Spread should be NARROW"
    assert lps.effort_result == "NO_SUPPLY", "Should detect NO_SUPPLY pattern"
    assert lps.effort_result_bonus == 10, "Should get +10 bonus"


def test_lps_selling_pressure_pattern():
    """
    Test AC 6B: Selling Pressure pattern (high volume + wide spread = -15 penalty).

    This is concerning: active selling with significant price movement.
    """
    start_time = datetime.now(UTC) - timedelta(days=30)
    end_time = datetime.now(UTC) - timedelta(days=5)
    trading_range = create_trading_range(
        ice_level=Decimal("100.00"),
        start_timestamp=start_time,
        end_timestamp=end_time,
    )

    sos_timestamp = datetime.now(UTC) - timedelta(days=4)
    sos = create_sos_breakout(
        bar_timestamp=sos_timestamp,
        breakout_price=Decimal("102.00"),
        ice_reference=Decimal("100.00"),
        volume=200000,
    )

    bars = []

    # Range bars with $3 average spread
    for i in range(30):
        bars.append(
            create_test_bar(
                timestamp=start_time + timedelta(days=i),
                low=Decimal("95.00"),
                high=Decimal("98.00"),  # $3 spread
                close=Decimal("96.50"),
                volume=150000,
            )
        )

    bars.append(sos.bar)

    # Pullback: High volume (180k = 1.2x) + Wide spread ($4 = 1.33x)
    bars.append(
        create_test_bar(
            timestamp=sos_timestamp + timedelta(days=1),
            low=Decimal("100.50"),
            high=Decimal("104.50"),  # $4 spread (wide)
            close=Decimal("101.00"),
            volume=180000,  # High volume (POOR)
        )
    )

    # Bounce
    bars.append(
        create_test_bar(
            timestamp=sos_timestamp + timedelta(days=2),
            low=Decimal("101.00"),
            high=Decimal("102.00"),
            close=Decimal("101.50"),
            volume=135000,
        )
    )

    volume_analysis = {}

    # Act
    lps = detect_lps(trading_range, sos, bars, volume_analysis)

    # Assert
    assert lps is not None, "LPS should be detected"
    assert lps.spread_quality == "WIDE", "Spread should be WIDE"
    assert lps.effort_result == "SELLING_PRESSURE", "Should detect SELLING_PRESSURE"
    assert lps.effort_result_bonus == -15, "Should get -15 penalty"


# AC 7: Bounce confirmation tests
def test_lps_bounce_confirmed():
    """
    Test AC 7: Bounce confirmation required.

    Price must rebound 1%+ above pullback low within 1-3 bars.
    """
    start_time = datetime.now(UTC) - timedelta(days=30)
    end_time = datetime.now(UTC) - timedelta(days=5)
    trading_range = create_trading_range(
        ice_level=Decimal("100.00"),
        start_timestamp=start_time,
        end_timestamp=end_time,
    )

    sos_timestamp = datetime.now(UTC) - timedelta(days=4)
    sos = create_sos_breakout(
        bar_timestamp=sos_timestamp,
        breakout_price=Decimal("102.00"),
        ice_reference=Decimal("100.00"),
        volume=200000,
    )

    bars = []

    # Range bars
    for i in range(30):
        bars.append(
            create_test_bar(
                timestamp=start_time + timedelta(days=i),
                low=Decimal("95.00"),
                high=Decimal("98.00"),
                close=Decimal("96.50"),
                volume=150000,
            )
        )

    bars.append(sos.bar)

    # Pullback low at $100.50
    bars.append(
        create_test_bar(
            timestamp=sos_timestamp + timedelta(days=1),
            low=Decimal("100.50"),
            high=Decimal("101.50"),
            close=Decimal("101.00"),
            volume=120000,
        )
    )

    # Bounce to $101.70 (1.2% above pullback low - confirms bounce)
    bars.append(
        create_test_bar(
            timestamp=sos_timestamp + timedelta(days=2),
            low=Decimal("101.20"),
            high=Decimal("102.00"),
            close=Decimal("101.70"),  # 1.2% above $100.50
            volume=135000,
        )
    )

    volume_analysis = {}

    # Act
    lps = detect_lps(trading_range, sos, bars, volume_analysis)

    # Assert
    assert lps is not None, "LPS should be detected"
    assert lps.bounce_confirmed is True, "Bounce should be confirmed"
    assert lps.bounce_bar_timestamp is not None, "Bounce timestamp should be set"


def test_lps_no_bounce_not_confirmed():
    """
    Test AC 7: No bounce = LPS not confirmed.

    Price continues lower without bouncing.
    """
    start_time = datetime.now(UTC) - timedelta(days=30)
    end_time = datetime.now(UTC) - timedelta(days=5)
    trading_range = create_trading_range(
        ice_level=Decimal("100.00"),
        start_timestamp=start_time,
        end_timestamp=end_time,
    )

    sos_timestamp = datetime.now(UTC) - timedelta(days=4)
    sos = create_sos_breakout(
        bar_timestamp=sos_timestamp,
        breakout_price=Decimal("102.00"),
        ice_reference=Decimal("100.00"),
        volume=200000,
    )

    bars = []

    # Range bars
    for i in range(30):
        bars.append(
            create_test_bar(
                timestamp=start_time + timedelta(days=i),
                low=Decimal("95.00"),
                high=Decimal("98.00"),
                close=Decimal("96.50"),
                volume=150000,
            )
        )

    bars.append(sos.bar)

    # Pullback low at $100.50
    bars.append(
        create_test_bar(
            timestamp=sos_timestamp + timedelta(days=1),
            low=Decimal("100.50"),
            high=Decimal("101.50"),
            close=Decimal("101.00"),
            volume=120000,
        )
    )

    # Continues lower - NO BOUNCE
    bars.append(
        create_test_bar(
            timestamp=sos_timestamp + timedelta(days=2),
            low=Decimal("100.00"),
            high=Decimal("100.70"),
            close=Decimal("100.20"),  # Below pullback low - no bounce
            volume=135000,
        )
    )

    volume_analysis = {}

    # Act
    lps = detect_lps(trading_range, sos, bars, volume_analysis)

    # Assert
    assert lps is None, "LPS without bounce should not be confirmed"


# AC 14: Volume trend analysis tests
def test_lps_declining_volume_trend():
    """
    Test AC 14: Declining volume trend during pullback (+5 bonus).

    Healthy pullback: volume decreases as price falls (supply drying up).
    """
    pullback_bars = [
        create_test_bar(datetime.now(UTC), Decimal("100.00"), Decimal("103.00"), Decimal("102.00"), 150000),
        create_test_bar(datetime.now(UTC), Decimal("100.00"), Decimal("102.00"), Decimal("101.00"), 130000),
        create_test_bar(datetime.now(UTC), Decimal("100.00"), Decimal("101.50"), Decimal("100.70"), 110000),
        create_test_bar(datetime.now(UTC), Decimal("100.00"), Decimal("101.00"), Decimal("100.50"), 90000),
    ]

    result = analyze_pullback_volume_trend(pullback_bars)

    assert result["trend"] == "DECLINING", "Trend should be DECLINING"
    assert result["trend_quality"] == "EXCELLENT", "Quality should be EXCELLENT"
    assert result["confidence_bonus"] == 5, "Should get +5 bonus"


def test_lps_increasing_volume_trend():
    """
    Test AC 14: Increasing volume trend during pullback (-5 penalty).

    Unhealthy pullback: volume increases as price falls (supply building).
    """
    pullback_bars = [
        create_test_bar(datetime.now(UTC), Decimal("100.00"), Decimal("103.00"), Decimal("102.00"), 90000),
        create_test_bar(datetime.now(UTC), Decimal("100.00"), Decimal("102.00"), Decimal("101.00"), 110000),
        create_test_bar(datetime.now(UTC), Decimal("100.00"), Decimal("101.50"), Decimal("100.70"), 130000),
        create_test_bar(datetime.now(UTC), Decimal("100.00"), Decimal("101.00"), Decimal("100.50"), 150000),
    ]

    result = analyze_pullback_volume_trend(pullback_bars)

    assert result["trend"] == "INCREASING", "Trend should be INCREASING"
    assert result["trend_quality"] == "WARNING", "Quality should be WARNING"
    assert result["confidence_bonus"] == -5, "Should get -5 penalty"


# AC 12: ATR-based stop tests
def test_calculate_atr():
    """
    Test AC 12: ATR calculation for volatility-adjusted stops.
    """
    bars = []
    base_time = datetime.now(UTC)

    # Create 20 bars with varying volatility
    for i in range(20):
        bars.append(
            create_test_bar(
                timestamp=base_time + timedelta(days=i),
                low=Decimal("95.00") + Decimal(str(i * 0.5)),
                high=Decimal("98.00") + Decimal(str(i * 0.5)),  # $3 average TR
                close=Decimal("96.50") + Decimal(str(i * 0.5)),
                volume=150000,
            )
        )

    atr = calculate_atr(bars, period=14)

    assert atr > Decimal("0"), "ATR should be positive"
    assert atr >= Decimal("2.5"), "ATR should be around $2.5-3 for $3 range"
    assert atr <= Decimal("4.0"), "ATR should be reasonable"


# AC 13: Position sizing tests
def test_calculate_lps_position_size():
    """
    Test AC 13: LPS position sizing with campaign phases and quality adjustments.
    """
    # Test LPS entry (phase 2) with EXCELLENT quality
    result = calculate_lps_position_size(
        account_equity=Decimal("100000"),  # $100k account
        risk_per_trade=Decimal("0.01"),  # 1% risk
        entry_price=Decimal("101.00"),
        stop_price=Decimal("97.00"),  # $4 risk per share
        lps_quality="EXCELLENT",
        campaign_phase=2,  # LPS entry
    )

    # Risk amount = $100k * 1% = $1000
    # Risk per share = $101 - $97 = $4
    # Base position = $1000 / $4 = 250 shares
    # Campaign multiplier (phase 2) = 0.50
    # Quality multiplier (EXCELLENT) = 1.0
    # Final = 250 * 0.50 * 1.0 = 125 shares

    assert result["position_size"] == 125, "Position size should be 125 shares"
    assert result["risk_amount"] == Decimal("1000"), "Risk amount should be $1000"
    assert result["campaign_multiplier"] == Decimal("0.50"), "LPS phase multiplier"
    assert result["quality_multiplier"] == Decimal("1.0"), "EXCELLENT multiplier"


def test_calculate_lps_position_size_acceptable_quality():
    """
    Test AC 13: Position sizing with ACCEPTABLE quality (50% reduction).
    """
    result = calculate_lps_position_size(
        account_equity=Decimal("100000"),
        risk_per_trade=Decimal("0.01"),
        entry_price=Decimal("101.00"),
        stop_price=Decimal("97.00"),
        lps_quality="ACCEPTABLE",
        campaign_phase=2,
    )

    # Base = 250, Campaign = 0.50, Quality = 0.50
    # Final = 250 * 0.50 * 0.50 = 62.5 → 62 shares

    assert result["position_size"] == 62, "Position size should be 62 shares (50% quality reduction)"
    assert result["quality_multiplier"] == Decimal("0.50"), "ACCEPTABLE multiplier"


# Edge cases
def test_insufficient_bars_after_sos():
    """
    Test edge case: Insufficient bars after SOS (need 3+ for pullback).
    """
    start_time = datetime.now(UTC) - timedelta(days=30)
    end_time = datetime.now(UTC) - timedelta(days=5)
    trading_range = create_trading_range(
        ice_level=Decimal("100.00"),
        start_timestamp=start_time,
        end_timestamp=end_time,
    )

    sos_timestamp = datetime.now(UTC) - timedelta(days=4)
    sos = create_sos_breakout(
        bar_timestamp=sos_timestamp,
        breakout_price=Decimal("102.00"),
        ice_reference=Decimal("100.00"),
        volume=200000,
    )

    bars = []

    # Range bars
    for i in range(30):
        bars.append(
            create_test_bar(
                timestamp=start_time + timedelta(days=i),
                low=Decimal("95.00"),
                high=Decimal("98.00"),
                close=Decimal("96.50"),
                volume=150000,
            )
        )

    bars.append(sos.bar)

    # Only 2 bars after SOS (insufficient)
    bars.append(
        create_test_bar(
            timestamp=sos_timestamp + timedelta(days=1),
            low=Decimal("101.50"),
            high=Decimal("103.00"),
            close=Decimal("102.00"),
            volume=140000,
        )
    )

    volume_analysis = {}

    # Act
    lps = detect_lps(trading_range, sos, bars, volume_analysis)

    # Assert
    assert lps is None, "Insufficient bars for LPS detection"


def test_sos_bar_not_found():
    """
    Test edge case: SOS bar not in bars list.
    """
    start_time = datetime.now(UTC) - timedelta(days=30)
    end_time = datetime.now(UTC) - timedelta(days=5)
    trading_range = create_trading_range(
        ice_level=Decimal("100.00"),
        start_timestamp=start_time,
        end_timestamp=end_time,
    )

    sos_timestamp = datetime.now(UTC) - timedelta(days=100)  # Old timestamp
    sos = create_sos_breakout(
        bar_timestamp=sos_timestamp,
        breakout_price=Decimal("102.00"),
        ice_reference=Decimal("100.00"),
        volume=200000,
    )

    bars = []

    # Bars from different time period (don't include SOS)
    for i in range(35):
        bars.append(
            create_test_bar(
                timestamp=start_time + timedelta(days=i),
                low=Decimal("95.00"),
                high=Decimal("98.00"),
                close=Decimal("96.50"),
                volume=150000,
            )
        )

    volume_analysis = {}

    # Act
    lps = detect_lps(trading_range, sos, bars, volume_analysis)

    # Assert
    assert lps is None, "Should handle SOS bar not in bars list"


def test_no_pullback_after_sos():
    """
    Test edge case: Price continues higher (no pullback occurred).
    """
    start_time = datetime.now(UTC) - timedelta(days=30)
    end_time = datetime.now(UTC) - timedelta(days=5)
    trading_range = create_trading_range(
        ice_level=Decimal("100.00"),
        start_timestamp=start_time,
        end_timestamp=end_time,
    )

    sos_timestamp = datetime.now(UTC) - timedelta(days=4)
    sos = create_sos_breakout(
        bar_timestamp=sos_timestamp,
        breakout_price=Decimal("102.00"),
        ice_reference=Decimal("100.00"),
        volume=200000,
    )

    bars = []

    # Range bars
    for i in range(30):
        bars.append(
            create_test_bar(
                timestamp=start_time + timedelta(days=i),
                low=Decimal("95.00"),
                high=Decimal("98.00"),
                close=Decimal("96.50"),
                volume=150000,
            )
        )

    bars.append(sos.bar)

    # Bars continue higher (no pullback to Ice)
    for i in range(1, 5):
        bars.append(
            create_test_bar(
                timestamp=sos_timestamp + timedelta(days=i),
                low=Decimal("102.00") + Decimal(str(i)),
                high=Decimal("105.00") + Decimal(str(i)),
                close=Decimal("104.00") + Decimal(str(i)),
                volume=140000,
            )
        )

    volume_analysis = {}

    # Act
    lps = detect_lps(trading_range, sos, bars, volume_analysis)

    # Assert
    assert lps is None, "No LPS if no pullback occurred"
