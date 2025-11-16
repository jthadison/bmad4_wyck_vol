"""
Forex Detector Integration Tests (Story 0.5 Task 7).

Purpose:
--------
Verify that spring and SOS detectors correctly route forex symbols to ForexConfidenceScorer
and apply forex-specific scoring rules (max confidence 85, volume interpretation logging).

Test Coverage:
--------------
1. Spring detector with EUR/USD (forex pair) → ForexConfidenceScorer
2. Spring detector with US30 (CFD index) → ForexConfidenceScorer
3. Verify asset_class="forex" and volume_reliability="LOW" attached to patterns
4. Stock vs forex comparison (AAPL vs EUR/USD)

Story 0.5 AC 12:
- Test detect_spring() with symbol="EUR/USD" → uses ForexConfidenceScorer
- Test with CFD indices: symbol="US30" → uses ForexConfidenceScorer
- Verify asset_class="forex" and volume_reliability="LOW" attached to models
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from src.models.creek_level import CreekLevel
from src.models.ice_level import IceLevel
from src.models.ohlcv import OHLCVBar
from src.models.phase_classification import PhaseClassification, PhaseEvents, WyckoffPhase
from src.models.pivot import Pivot, PivotType
from src.models.price_cluster import PriceCluster
from src.models.touch_detail import TouchDetail
from src.models.trading_range import RangeStatus, TradingRange
from src.pattern_engine.detectors.sos_detector import detect_sos_breakout
from src.pattern_engine.detectors.spring_detector import detect_spring
from src.pattern_engine.scoring.scorer_factory import detect_asset_class, get_scorer

# ============================================================
# HELPER FUNCTIONS (adapted from test_spring_detector.py)
# ============================================================


def create_test_bar(
    timestamp: datetime,
    low: Decimal,
    high: Decimal,
    close: Decimal,
    volume: int,
    symbol: str = "AAPL",
) -> OHLCVBar:
    """Create test OHLCV bar with all required fields."""
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
    creek_level: Decimal,
    symbol: str = "AAPL",
) -> TradingRange:
    """Create trading range with all required fields for testing."""
    base_timestamp = datetime(2024, 1, 1, tzinfo=UTC)

    # Create support cluster
    support_pivots = []
    for i, idx in enumerate([10, 20, 30]):
        bar = create_test_bar(
            timestamp=base_timestamp + timedelta(days=idx),
            low=creek_level - Decimal("2.00"),
            high=creek_level + Decimal("5.00"),
            close=creek_level + Decimal("1.00"),
            volume=100000,
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
        average_price=creek_level - Decimal("2.00"),
        min_price=creek_level - Decimal("3.00"),
        max_price=creek_level - Decimal("1.00"),
        price_range=Decimal("2.00"),
        touch_count=3,
        cluster_type=PivotType.LOW,
        std_deviation=Decimal("0.50"),
        timestamp_range=(support_pivots[0].timestamp, support_pivots[-1].timestamp),
    )

    # Create resistance cluster
    resistance_pivots = []
    for i, idx in enumerate([15, 25, 35]):
        bar = create_test_bar(
            timestamp=base_timestamp + timedelta(days=idx),
            low=creek_level + Decimal("5.00"),
            high=creek_level + Decimal("10.00"),
            close=creek_level + Decimal("7.00"),
            volume=100000,
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
        average_price=creek_level + Decimal("10.00"),
        min_price=creek_level + Decimal("9.00"),
        max_price=creek_level + Decimal("11.00"),
        price_range=Decimal("2.00"),
        touch_count=3,
        cluster_type=PivotType.HIGH,
        std_deviation=Decimal("0.50"),
        timestamp_range=(resistance_pivots[0].timestamp, resistance_pivots[-1].timestamp),
    )

    # Create Creek with all required fields
    creek = CreekLevel(
        price=creek_level,
        absolute_low=creek_level - Decimal("1.00"),
        touch_count=3,
        touch_details=[
            TouchDetail(
                index=i,
                price=creek_level,
                volume=100000,
                volume_ratio=Decimal("1.0"),
                close_position=Decimal("0.7"),
                rejection_wick=Decimal("0.5"),
                timestamp=base_timestamp + timedelta(days=idx),
            )
            for i, idx in enumerate([10, 20, 30])
        ],
        strength_score=75,
        strength_rating="STRONG",
        last_test_timestamp=base_timestamp + timedelta(days=30),
        first_test_timestamp=base_timestamp + timedelta(days=10),
        hold_duration=20,
        confidence="HIGH",
        volume_trend="DECREASING",
    )

    return TradingRange(
        id=uuid4(),
        symbol=symbol,
        timeframe="1d",
        support_cluster=support_cluster,
        resistance_cluster=resistance_cluster,
        support=creek_level - Decimal("2.00"),
        resistance=creek_level + Decimal("10.00"),
        midpoint=creek_level + Decimal("4.00"),
        range_width=Decimal("12.00"),
        range_width_pct=Decimal("0.12"),
        start_index=0,
        end_index=50,
        duration=51,
        creek=creek,
        status=RangeStatus.ACTIVE,
    )


def create_bars_with_spring(
    creek_level: Decimal,
    symbol: str = "AAPL",
) -> list[OHLCVBar]:
    """Create bar sequence with spring pattern."""
    bars = []
    base_timestamp = datetime(2024, 1, 1, tzinfo=UTC)

    # Bars 0-19: Range context (normal volume ~100000)
    for i in range(20):
        bars.append(
            create_test_bar(
                timestamp=base_timestamp + timedelta(days=i),
                low=creek_level,
                high=creek_level + Decimal("2.00"),
                close=creek_level + Decimal("1.00"),
                volume=100000,
                symbol=symbol,
            )
        )

    # Bars 20-24: Approach Creek
    for i in range(20, 25):
        bars.append(
            create_test_bar(
                timestamp=base_timestamp + timedelta(days=i),
                low=creek_level - Decimal("0.50"),
                high=creek_level + Decimal("1.00"),
                close=creek_level,
                volume=100000,
                symbol=symbol,
            )
        )

    # Bar 25: SPRING (2% penetration, 0.4x volume)
    spring_low = creek_level - (creek_level * Decimal("0.02"))
    bars.append(
        create_test_bar(
            timestamp=base_timestamp + timedelta(days=25),
            low=spring_low,
            high=creek_level,
            close=creek_level - Decimal("0.10"),
            volume=40000,  # 0.4x of 100000 average
            symbol=symbol,
        )
    )

    # Bar 26: RECOVERY (closes above Creek - 1 bar recovery)
    bars.append(
        create_test_bar(
            timestamp=base_timestamp + timedelta(days=26),
            low=creek_level - Decimal("0.10"),
            high=creek_level + Decimal("2.00"),
            close=creek_level + Decimal("1.50"),  # Above Creek
            volume=80000,
            symbol=symbol,
        )
    )

    # Bars 27-30: Continuation
    for i in range(27, 31):
        bars.append(
            create_test_bar(
                timestamp=base_timestamp + timedelta(days=i),
                low=creek_level,
                high=creek_level + Decimal("2.50"),
                close=creek_level + Decimal("2.00"),
                volume=100000,
                symbol=symbol,
            )
        )

    return bars


# ============================================================
# FOREX SPRING DETECTOR TESTS
# ============================================================


def test_spring_detector_forex_pair_eur_usd():
    """
    Test spring detector with EUR/USD forex pair.

    Verifies:
    - Asset class detection: "forex" (contains "/")
    - Scorer selection: ForexConfidenceScorer
    - Pattern metadata: asset_class="forex", volume_reliability="LOW"
    - Confidence capping: max 85 (not 100)

    Story 0.5 AC 12 (forex pair detection)
    """
    # ARRANGE: EUR/USD trading range (using price of 1.1000)
    symbol = "EUR/USD"
    creek_price = Decimal("1.1000")

    trading_range = create_trading_range(creek_price, symbol)
    bars = create_bars_with_spring(creek_price, symbol)
    phase = WyckoffPhase.C

    # ACT: Detect spring with forex symbol
    spring = detect_spring(trading_range, bars, phase, symbol)

    # ASSERT: Spring detected
    assert spring is not None, "Spring should be detected for EUR/USD"

    # ASSERT: Asset class metadata
    assert spring.asset_class == "forex", "EUR/USD should route to forex asset class"
    assert spring.volume_reliability == "LOW", "Forex uses tick volume (LOW reliability)"

    # ASSERT: Spring quality metrics
    assert spring.penetration_pct == Decimal("0.02"), "2% penetration below Creek"
    assert spring.volume_ratio < Decimal("0.7"), "Low volume spring"
    assert spring.recovery_bars == 1, "Rapid 1-bar recovery"

    # VERIFY: Asset class detection logic
    detected_class = detect_asset_class(symbol)
    assert detected_class == "forex", "EUR/USD contains '/' → forex"

    # VERIFY: Scorer selection
    scorer = get_scorer(detected_class)
    assert scorer.asset_class == "forex"
    assert scorer.volume_reliability == "LOW"
    assert scorer.max_confidence == 85, "Forex max confidence is 85 (humility tax)"


def test_spring_detector_cfd_index_us30():
    """
    Test spring detector with US30 CFD index.

    US30 is a CFD index that uses tick volume (treat as forex).

    Verifies:
    - Asset class detection: "forex" (CFD index in list)
    - Scorer selection: ForexConfidenceScorer
    - Pattern metadata: asset_class="forex", volume_reliability="LOW"

    Story 0.5 AC 12 (CFD index detection)
    """
    # ARRANGE: US30 trading range
    symbol = "US30"
    creek_price = Decimal("38000.00")

    trading_range = create_trading_range(creek_price, symbol)
    bars = create_bars_with_spring(creek_price, symbol)
    phase = WyckoffPhase.C

    # ACT: Detect spring with CFD symbol
    spring = detect_spring(trading_range, bars, phase, symbol)

    # ASSERT: Spring detected
    assert spring is not None, "Spring should be detected for US30"

    # ASSERT: Asset class metadata
    assert spring.asset_class == "forex", "US30 is CFD index → forex asset class"
    assert spring.volume_reliability == "LOW", "CFD uses tick volume"

    # VERIFY: Asset class detection logic
    detected_class = detect_asset_class(symbol)
    assert detected_class == "forex", "US30 in CFD index list → forex"


def test_spring_detector_stock_vs_forex_asset_class():
    """
    Compare stock (AAPL) vs forex (EUR/USD) asset class routing.

    Verifies that identical spring patterns route to different scorers
    based on symbol, resulting in different confidence caps.

    Story 0.5 integration test
    """
    creek_price = Decimal("100.00")

    # ARRANGE: Stock trading range (AAPL)
    stock_symbol = "AAPL"
    stock_range = create_trading_range(creek_price, stock_symbol)
    stock_bars = create_bars_with_spring(creek_price, stock_symbol)

    # ARRANGE: Forex trading range (EUR/USD - scaled to $100 for comparison)
    forex_symbol = "EUR/USD"
    forex_range = create_trading_range(creek_price, forex_symbol)
    forex_bars = create_bars_with_spring(creek_price, forex_symbol)

    phase = WyckoffPhase.C

    # ACT: Detect springs
    stock_spring = detect_spring(stock_range, stock_bars, phase, stock_symbol)
    forex_spring = detect_spring(forex_range, forex_bars, phase, forex_symbol)

    # ASSERT: Both detected
    assert stock_spring is not None, "Stock spring should be detected"
    assert forex_spring is not None, "Forex spring should be detected"

    # ASSERT: Different asset classes
    assert stock_spring.asset_class == "stock"
    assert forex_spring.asset_class == "forex"

    # ASSERT: Different volume reliability
    assert stock_spring.volume_reliability == "HIGH"  # Real volume
    assert forex_spring.volume_reliability == "LOW"  # Tick volume

    # ASSERT: Identical spring metrics
    assert stock_spring.penetration_pct == forex_spring.penetration_pct
    assert stock_spring.volume_ratio == forex_spring.volume_ratio
    assert stock_spring.recovery_bars == forex_spring.recovery_bars

    # VERIFY: Different scorers
    stock_scorer = get_scorer(stock_spring.asset_class)
    forex_scorer = get_scorer(forex_spring.asset_class)

    assert stock_scorer.max_confidence == 100
    assert forex_scorer.max_confidence == 85  # 15-point humility tax


def test_asset_class_detection_all_symbols():
    """
    Test asset class detection for all symbol types.

    Verifies the factory correctly routes:
    - Forex pairs (contains "/") → "forex"
    - CFD indices (in list) → "forex"
    - Default (stocks) → "stock"

    Story 0.5 AC 2
    """
    # Forex pairs
    assert detect_asset_class("EUR/USD") == "forex"
    assert detect_asset_class("GBP/JPY") == "forex"
    assert detect_asset_class("USD/CHF") == "forex"

    # CFD indices
    assert detect_asset_class("US30") == "forex"
    assert detect_asset_class("NAS100") == "forex"
    assert detect_asset_class("SPX500") == "forex"
    assert detect_asset_class("GER40") == "forex"
    assert detect_asset_class("UK100") == "forex"
    assert detect_asset_class("JPN225") == "forex"

    # Stocks (default)
    assert detect_asset_class("AAPL") == "stock"
    assert detect_asset_class("SPY") == "stock"
    assert detect_asset_class("MSFT") == "stock"
    assert detect_asset_class("QQQ") == "stock"


def test_scorer_cache_singleton_pattern():
    """
    Test scorer factory singleton pattern.

    Verifies that get_scorer() returns the SAME instance for repeated calls
    with the same asset class (caching for performance).

    Story 0.4 (Scorer Factory caching)
    """
    # Get stock scorer twice
    stock_scorer_1 = get_scorer("stock")
    stock_scorer_2 = get_scorer("stock")
    assert stock_scorer_1 is stock_scorer_2, "Stock scorer should be cached (same instance)"

    # Get forex scorer twice
    forex_scorer_1 = get_scorer("forex")
    forex_scorer_2 = get_scorer("forex")
    assert forex_scorer_1 is forex_scorer_2, "Forex scorer should be cached (same instance)"

    # Different asset classes should have different instances
    assert (
        stock_scorer_1 is not forex_scorer_1
    ), "Stock and forex scorers should be different instances"


# ============================================================
# SOS DETECTOR HELPER FUNCTIONS
# ============================================================


def create_trading_range_with_ice(
    ice_level: Decimal,
    symbol: str = "AAPL",
) -> TradingRange:
    """Create trading range with Ice level for SOS testing."""
    base_timestamp = datetime(2024, 1, 1, tzinfo=UTC)

    # Create support cluster
    support_pivots = []
    for i, idx in enumerate([10, 20, 30]):
        bar = create_test_bar(
            timestamp=base_timestamp + timedelta(days=idx),
            low=ice_level - Decimal("12.00"),
            high=ice_level - Decimal("5.00"),
            close=ice_level - Decimal("7.00"),
            volume=100000,
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
        average_price=ice_level - Decimal("12.00"),
        min_price=ice_level - Decimal("13.00"),
        max_price=ice_level - Decimal("11.00"),
        price_range=Decimal("2.00"),
        touch_count=3,
        cluster_type=PivotType.LOW,
        std_deviation=Decimal("0.50"),
        timestamp_range=(support_pivots[0].timestamp, support_pivots[-1].timestamp),
    )

    # Create resistance cluster
    resistance_pivots = []
    for i, idx in enumerate([15, 25, 35]):
        bar = create_test_bar(
            timestamp=base_timestamp + timedelta(days=idx),
            low=ice_level - Decimal("2.00"),
            high=ice_level + Decimal("1.00"),
            close=ice_level - Decimal("1.00"),
            volume=100000,
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
        average_price=ice_level + Decimal("1.00"),
        min_price=ice_level,
        max_price=ice_level + Decimal("2.00"),
        price_range=Decimal("2.00"),
        touch_count=3,
        cluster_type=PivotType.HIGH,
        std_deviation=Decimal("0.50"),
        timestamp_range=(resistance_pivots[0].timestamp, resistance_pivots[-1].timestamp),
    )

    # Create Ice with all required fields
    ice = IceLevel(
        price=ice_level,
        absolute_high=ice_level + Decimal("1.00"),
        touch_count=3,
        touch_details=[
            TouchDetail(
                index=i,
                price=ice_level,
                volume=100000,
                volume_ratio=Decimal("1.0"),
                close_position=Decimal("0.3"),
                rejection_wick=Decimal("0.5"),
                timestamp=base_timestamp + timedelta(days=idx),
            )
            for i, idx in enumerate([15, 25, 35])
        ],
        strength_score=75,
        strength_rating="STRONG",
        last_test_timestamp=base_timestamp + timedelta(days=35),
        first_test_timestamp=base_timestamp + timedelta(days=15),
        hold_duration=20,
        confidence="HIGH",
        volume_trend="DECREASING",
    )

    return TradingRange(
        id=uuid4(),
        symbol=symbol,
        timeframe="1d",
        support_cluster=support_cluster,
        resistance_cluster=resistance_cluster,
        support=ice_level - Decimal("12.00"),
        resistance=ice_level + Decimal("1.00"),
        midpoint=ice_level - Decimal("5.50"),
        range_width=Decimal("13.00"),
        range_width_pct=Decimal("0.13"),
        start_index=0,
        end_index=50,
        duration=51,
        ice=ice,
        status=RangeStatus.ACTIVE,
    )


def create_bars_with_sos_breakout(
    ice_level: Decimal,
    breakout_pct: Decimal,
    volume: int,
    symbol: str = "AAPL",
) -> list[OHLCVBar]:
    """Create synthetic bars with SOS breakout pattern."""
    base_timestamp = datetime(2024, 1, 1, tzinfo=UTC)
    bars = []

    # Create 24 normal bars trading within range
    for i in range(24):
        bar = create_test_bar(
            timestamp=base_timestamp + timedelta(days=i),
            low=ice_level - Decimal("5.00"),
            high=ice_level - Decimal("0.50"),
            close=ice_level - Decimal("2.00"),
            volume=100000,
            symbol=symbol,
        )
        bars.append(bar)

    # Create breakout bar (bar 25)
    breakout_price = ice_level * (Decimal("1") + breakout_pct)
    breakout_bar = create_test_bar(
        timestamp=base_timestamp + timedelta(days=24),
        low=ice_level - Decimal("1.00"),
        high=breakout_price + Decimal("1.00"),
        close=breakout_price,
        volume=volume,
        symbol=symbol,
    )
    bars.append(breakout_bar)

    return bars


def create_phase_classification(
    phase: WyckoffPhase,
    confidence: int,
) -> PhaseClassification:
    """Create test phase classification."""
    base_timestamp = datetime(2024, 1, 1, tzinfo=UTC)

    return PhaseClassification(
        phase=phase,
        confidence=confidence,
        duration=10,
        events_detected=PhaseEvents(),
        trading_allowed=True,
        phase_start_index=0,
        phase_start_timestamp=base_timestamp,
    )


# ============================================================
# FOREX SOS DETECTOR TESTS
# ============================================================


def test_sos_detector_forex_pair_gbp_usd():
    """
    Test SOS detector with GBP/USD forex pair.

    Verifies:
    - Asset class detection: "forex" (contains "/")
    - Scorer selection: ForexConfidenceScorer
    - Pattern metadata: asset_class="forex", volume_reliability="LOW"
    - Confidence capping: max 85 (not 100)

    Story 0.5 AC 12 (forex pair detection for SOS)
    """
    # ARRANGE: GBP/USD trading range (using price of 1.2500)
    symbol = "GBP/USD"
    ice_price = Decimal("1.2500")

    trading_range = create_trading_range_with_ice(ice_price, symbol)
    bars = create_bars_with_sos_breakout(
        ice_level=ice_price,
        breakout_pct=Decimal("0.02"),  # 2% breakout
        volume=200000,  # 2.0x volume
        symbol=symbol,
    )
    phase = create_phase_classification(WyckoffPhase.D, 85)

    # Create volume analysis (Story 6.1B requires spread_ratio)
    volume_analysis = {
        bars[-1].timestamp: {
            "volume_ratio": Decimal("2.0"),
            "spread_ratio": Decimal("1.2"),  # Story 6.1B: spread expansion
        }
    }

    # ACT: Detect SOS with forex symbol
    sos = detect_sos_breakout(trading_range, bars, volume_analysis, phase, symbol)

    # ASSERT: SOS detected
    assert sos is not None, "SOS should be detected for GBP/USD"

    # ASSERT: Asset class metadata
    assert sos.asset_class == "forex", "GBP/USD should route to forex asset class"
    assert sos.volume_reliability == "LOW", "Forex uses tick volume (LOW reliability)"

    # ASSERT: SOS quality metrics
    assert sos.breakout_pct == Decimal("0.02"), "2% breakout above Ice"
    assert sos.volume_ratio == Decimal("2.0"), "High volume breakout"

    # VERIFY: Asset class detection logic
    detected_class = detect_asset_class(symbol)
    assert detected_class == "forex", "GBP/USD contains '/' → forex"

    # VERIFY: Scorer selection
    scorer = get_scorer(detected_class)
    assert scorer.asset_class == "forex"
    assert scorer.volume_reliability == "LOW"
    assert scorer.max_confidence == 85, "Forex max confidence is 85 (humility tax)"


def test_sos_detector_stock_vs_forex_volume_interpretation():
    """
    Compare stock (AAPL) vs forex (EUR/USD) volume interpretation for SOS.

    Victoria's critical requirement: Prove that identical SOS patterns route to
    different scorers based on symbol, resulting in different confidence caps
    and volume reliability warnings.

    Story 0.5 integration test
    """
    ice_price = Decimal("100.00")

    # ARRANGE: Stock trading range (AAPL)
    stock_symbol = "AAPL"
    stock_range = create_trading_range_with_ice(ice_price, stock_symbol)
    stock_bars = create_bars_with_sos_breakout(
        ice_level=ice_price,
        breakout_pct=Decimal("0.02"),
        volume=200000,
        symbol=stock_symbol,
    )

    # ARRANGE: Forex trading range (EUR/USD - scaled to $100 for comparison)
    forex_symbol = "EUR/USD"
    forex_range = create_trading_range_with_ice(ice_price, forex_symbol)
    forex_bars = create_bars_with_sos_breakout(
        ice_level=ice_price,
        breakout_pct=Decimal("0.02"),
        volume=200000,
        symbol=forex_symbol,
    )

    phase = create_phase_classification(WyckoffPhase.D, 85)

    # Create volume analysis (identical for both - Story 6.1B requires spread_ratio)
    stock_volume_analysis = {
        stock_bars[-1].timestamp: {
            "volume_ratio": Decimal("2.0"),
            "spread_ratio": Decimal("1.2"),
        }
    }
    forex_volume_analysis = {
        forex_bars[-1].timestamp: {
            "volume_ratio": Decimal("2.0"),
            "spread_ratio": Decimal("1.2"),
        }
    }

    # ACT: Detect SOS patterns
    stock_sos = detect_sos_breakout(
        stock_range, stock_bars, stock_volume_analysis, phase, stock_symbol
    )
    forex_sos = detect_sos_breakout(
        forex_range, forex_bars, forex_volume_analysis, phase, forex_symbol
    )

    # ASSERT: Both detected
    assert stock_sos is not None, "Stock SOS should be detected"
    assert forex_sos is not None, "Forex SOS should be detected"

    # ASSERT: Different asset classes
    assert stock_sos.asset_class == "stock"
    assert forex_sos.asset_class == "forex"

    # ASSERT: Different volume reliability
    assert stock_sos.volume_reliability == "HIGH"  # Real volume
    assert forex_sos.volume_reliability == "LOW"  # Tick volume

    # ASSERT: Identical SOS metrics
    assert stock_sos.breakout_pct == forex_sos.breakout_pct
    assert stock_sos.volume_ratio == forex_sos.volume_ratio

    # VERIFY: Different scorers
    stock_scorer = get_scorer(stock_sos.asset_class)
    forex_scorer = get_scorer(forex_sos.asset_class)

    assert stock_scorer.max_confidence == 100
    assert forex_scorer.max_confidence == 85  # 15-point humility tax

    # VERIFY: Volume interpretation difference
    # Stock: 2.0x volume is REAL institutional volume (trustworthy)
    # Forex: 2.0x volume is TICK volume (lower reliability, hence lower max confidence)
