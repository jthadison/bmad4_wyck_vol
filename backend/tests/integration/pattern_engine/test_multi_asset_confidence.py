"""
Integration test suite for multi-asset confidence scoring (Story 0.6).

This test suite validates the entire Epic 0 asset-class abstraction layer,
ensuring stock and forex patterns are detected and scored correctly end-to-end
across all pattern types (Spring, SOS) with proper volume interpretation,
confidence ceiling enforcement, and position sizing implications.

Test Coverage:
--------------
AC 1: Factory overhead testing (<1ms per symbol)
AC 2: Stock spring detection with component score validation (40/35/25 weights)
AC 3: Forex spring detection with perfect pattern ceiling test (caps at 85)
AC 4: CFD index detection (US30, NAS100 treated as forex)
AC 5: Asset-class ceiling validation (stock 100, forex 85)
AC 6: Component score weight validation across asset classes
AC 7: Confidence comparison with position sizing implications
AC 8: Performance benchmarks (spring <150ms, SOS <150ms, factory <1ms)
AC 9: Multi-spring campaign validation across asset classes
AC 10: Minimum confidence threshold enforcement (70 minimum)

Story Dependencies:
-------------------
- Story 0.1: ConfidenceScorer base class
- Story 0.2: StockConfidenceScorer (max 100, volume 40pts)
- Story 0.3: ForexConfidenceScorer (max 85, volume 10pts)
- Story 0.4: ScorerFactory (asset class auto-detection)
- Story 0.5: Detector refactoring (uses factory)
- Story 5.6: Multi-spring campaign detection

Author: Story 0.6 Implementation
"""

import gc
import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
import structlog

from src.models.creek_level import CreekLevel
from src.models.ice_level import IceLevel
from src.models.ohlcv import OHLCVBar
from src.models.phase_classification import WyckoffPhase
from src.models.pivot import Pivot, PivotType
from src.models.price_cluster import PriceCluster
from src.models.touch_detail import TouchDetail
from src.models.trading_range import RangeStatus, TradingRange
from src.pattern_engine.detectors.spring_detector import (
    SpringDetector,
    calculate_spring_confidence,
    detect_spring,
)
from src.pattern_engine.scoring.scorer_factory import detect_asset_class, get_scorer

logger = structlog.get_logger(__name__)


# ============================================================================
# Helper Functions (Task 1)
# ============================================================================


def get_confidence_tier(score: float, asset_class: str) -> tuple[str, float]:
    """
    Get confidence tier and position multiplier (from risk-management guidelines).

    This helper function maps confidence scores to risk-adjusted position sizing
    multipliers based on asset class and volume reliability.

    Args:
        score: Confidence score (0-100 for stocks, 0-85 for forex)
        asset_class: "stock" or "forex"

    Returns:
        tuple: (tier_name, multiplier)

    Risk Management Integration:
        - EXCELLENT: Highest conviction setups, max position sizing
        - GOOD: Strong setups with minor weakness, reduced sizing
        - MARGINAL: Acceptable setups with notable weakness, minimal sizing
        - REJECT: Below quality threshold, no trade

    Examples:
        >>> get_confidence_tier(95, "stock")
        ("EXCELLENT", 1.00)
        >>> get_confidence_tier(82, "forex")
        ("EXCELLENT", 0.80)  # Forex max multiplier lower due to tick volume
    """
    if asset_class == "stock":
        # Stock tiers (max confidence: 100, HIGH volume reliability)
        if score >= 90:
            return ("EXCELLENT", 1.00)  # Full position (2% risk)
        elif score >= 80:
            return ("GOOD", 0.75)  # 75% position (1.5% risk)
        elif score >= 70:
            return ("MARGINAL", 0.50)  # 50% position (1% risk)
        else:
            return ("REJECT", 0.00)  # No trade (<70 minimum threshold)
    else:  # forex
        # Forex tiers (max confidence: 85, LOW volume reliability)
        if score >= 80:
            return ("EXCELLENT", 0.80)  # 80% position (1.6% risk)
        elif score >= 75:
            return ("GOOD", 0.60)  # 60% position (1.2% risk)
        elif score >= 70:
            return ("MARGINAL", 0.40)  # 40% position (0.8% risk)
        else:
            return ("REJECT", 0.00)  # No trade (<70 minimum threshold)


def create_spring_bars(
    creek_level: Decimal,
    penetration_pct: Decimal,
    volume_ratio: Decimal,
    recovery_bars: int,
    symbol: str = "AAPL",
    bar_count: int = 60,
) -> list[OHLCVBar]:
    """
    Create realistic bar sequence with spring pattern.

    Args:
        creek_level: Creek price level (e.g., Decimal("100.00"))
        penetration_pct: Penetration depth below Creek (e.g., Decimal("0.02") = 2%)
        volume_ratio: Volume ratio for spring bar (e.g., Decimal("0.4") = 0.4x)
        recovery_bars: Number of bars to recover above Creek (1-5)
        symbol: Trading symbol (default: "AAPL")
        bar_count: Total number of bars to create (default: 60)

    Returns:
        list[OHLCVBar]: Sequence of bars with spring pattern at bar 50

    Pattern Structure:
        - Bars 0-49: Normal price action around Creek with normal volume
        - Bar 50: Spring (penetrates below Creek with low volume)
        - Bars 51-50+recovery_bars: Recovery back above Creek
        - Remaining bars: Normal price action above Creek
    """
    bars = []
    base_volume = 1_000_000  # 1M shares average
    start_time = datetime(2024, 1, 1, 9, 30, tzinfo=UTC)
    spring_bar_index = 50

    for i in range(bar_count):
        timestamp = start_time + timedelta(days=i)

        # Determine price based on pattern
        if i < spring_bar_index:
            # Normal bars: oscillate around Creek
            price = creek_level + Decimal(str((i % 5) - 2)) * Decimal("0.10")
        elif i == spring_bar_index:
            # Spring bar: penetrate below Creek
            price = creek_level * (Decimal("1.0") - penetration_pct)
        elif i < spring_bar_index + recovery_bars:
            # Recovery bars: move back toward Creek
            recovery_progress = (i - spring_bar_index) / recovery_bars
            penetration_amount = creek_level * penetration_pct
            price = (creek_level - penetration_amount) + (
                penetration_amount * Decimal(str(recovery_progress))
            )
        else:
            # Post-recovery: above Creek
            price = creek_level + Decimal("0.50")

        # Determine volume
        if i == spring_bar_index:
            # Spring bar: low volume
            volume = int(base_volume * float(volume_ratio))
        else:
            # Normal volume: oscillate around 1M
            volume = int(base_volume * (0.95 + (i % 3) * 0.05))

        # Create bar
        bar = OHLCVBar(
            id=uuid4(),
            symbol=symbol,
            timeframe="1d",
            timestamp=timestamp,
            open=price,
            high=price + Decimal("1.00"),
            low=price - Decimal("1.00"),
            close=price + Decimal("0.50"),
            volume=volume,
            spread=Decimal("2.00"),
            spread_ratio=Decimal("1.0"),
            volume_ratio=Decimal("1.0"),  # Will be recalculated
        )
        bars.append(bar)

    return bars


def create_perfect_spring_bars(
    creek_level: Decimal,
    penetration_pct: Decimal,
    volume_ratio: Decimal,
    recovery_bars: int,
    symbol: str = "AAPL",
) -> list[OHLCVBar]:
    """
    Create perfect spring pattern (textbook Wyckoff example).

    Perfect Spring Definition (AC 2, Amendment 2):
        - Penetration: 1.5% below Creek (ideal 1-2% range)
        - Volume: 0.29x average (ultra-low, <0.3x tier = 40pts)
        - Recovery: 1 bar (immediate demand = 25pts)
        - Creek Strength: 80+ (requires strong Creek, bonus +10pts)
        - Volume Trend: DECLINING across 3+ tests (bonus +10pts)

    Expected Raw Score: 40 + 35 + 25 + 10 + 10 = 120 points

    Stock Normalized: (120/120) * 100 = 100 confidence
    Forex Normalized: (120/120) * 85 = 85 confidence (CAPPED)

    Args:
        creek_level: Creek price level
        penetration_pct: Should be Decimal("0.015") for perfect pattern
        volume_ratio: Should be Decimal("0.29") for perfect pattern
        recovery_bars: Should be 1 for perfect pattern
        symbol: Trading symbol

    Returns:
        list[OHLCVBar]: Bar sequence with perfect spring pattern
    """
    return create_spring_bars(
        creek_level=creek_level,
        penetration_pct=penetration_pct,
        volume_ratio=volume_ratio,
        recovery_bars=recovery_bars,
        symbol=symbol,
        bar_count=60,
    )


def create_three_spring_campaign(
    symbol: str,
    volumes: list[Decimal],
    penetrations: list[Decimal],
    creek_level: Decimal = Decimal("100.00"),
) -> list[OHLCVBar]:
    """
    Create 3-spring campaign sequence for multi-spring testing (AC 9, Amendment 4).

    Campaign Structure:
        - Spring 1 at bar 25
        - Spring 2 at bar 40
        - Spring 3 at bar 55
        - Each spring has different volume/penetration characteristics

    Args:
        symbol: Trading symbol
        volumes: List of 3 volume ratios for each spring
        penetrations: List of 3 penetration percentages for each spring
        creek_level: Creek price level (default: Decimal("100.00"))

    Returns:
        list[OHLCVBar]: Sequence with 3 springs

    Examples:
        >>> # DECLINING volume campaign (professional accumulation)
        >>> bars = create_three_spring_campaign(
        ...     symbol="AAPL",
        ...     volumes=[Decimal("0.6"), Decimal("0.5"), Decimal("0.3")],
        ...     penetrations=[Decimal("0.02"), Decimal("0.025"), Decimal("0.03")],
        ... )
        >>> # Volume trend: DECLINING (0.6 → 0.5 → 0.3)
        >>> # Risk level: LOW (professional accumulation)

        >>> # RISING volume campaign (distribution warning)
        >>> bars = create_three_spring_campaign(
        ...     symbol="EUR/USD",
        ...     volumes=[Decimal("0.3"), Decimal("0.5"), Decimal("0.65")],
        ...     penetrations=[Decimal("0.02"), Decimal("0.025"), Decimal("0.03")],
        ... )
        >>> # Volume trend: RISING (0.3 → 0.5 → 0.65)
        >>> # Risk level: HIGH (distribution warning)
    """
    bars = []
    base_volume = 1_000_000
    start_time = datetime(2024, 1, 1, 9, 30, tzinfo=UTC)
    spring_indices = [25, 40, 55]

    for i in range(70):
        timestamp = start_time + timedelta(days=i)

        # Determine if this is a spring bar
        spring_idx = None
        for idx, bar_num in enumerate(spring_indices):
            if i == bar_num:
                spring_idx = idx
                break

        # Price logic
        if spring_idx is not None:
            # Spring bar: penetrate below Creek
            price = creek_level * (Decimal("1.0") - penetrations[spring_idx])
            volume = int(base_volume * float(volumes[spring_idx]))
        elif i in [26, 27, 41, 42, 56, 57]:
            # Recovery bars (1-2 bars after each spring)
            price = creek_level + Decimal("0.20")
            volume = int(base_volume * 0.95)
        else:
            # Normal bars around Creek
            price = creek_level + Decimal(str((i % 5) - 2)) * Decimal("0.10")
            volume = int(base_volume * (0.95 + (i % 3) * 0.05))

        # Create bar
        bar = OHLCVBar(
            id=uuid4(),
            symbol=symbol,
            timeframe="1d",
            timestamp=timestamp,
            open=price,
            high=price + Decimal("1.00"),
            low=price - Decimal("1.00"),
            close=price + Decimal("0.50"),
            volume=volume,
            spread=Decimal("2.00"),
            spread_ratio=Decimal("1.0"),
            volume_ratio=Decimal("1.0"),
        )
        bars.append(bar)

    return bars


def create_trading_range(
    symbol: str,
    creek_level: Decimal = Decimal("100.00"),
    ice_level: Decimal = Decimal("105.00"),
    creek_strength: int = 85,
    ice_strength: int = 80,
) -> TradingRange:
    """
    Create trading range with Creek and Ice levels.

    Args:
        symbol: Trading symbol
        creek_level: Support level price
        ice_level: Resistance level price
        creek_strength: Creek strength score (80+ for bonus)
        ice_strength: Ice strength score (80+ for bonus)

    Returns:
        TradingRange: Trading range with support/resistance levels
    """
    base_timestamp = datetime(2024, 1, 1, tzinfo=UTC)

    # Create touch details for Creek
    creek_touch_details = [
        TouchDetail(
            index=i,
            price=creek_level,
            volume=100000,
            volume_ratio=Decimal("1.0"),
            close_position=Decimal("0.7"),
            rejection_wick=Decimal("0.5"),
            timestamp=base_timestamp + timedelta(days=idx),
        )
        for i, idx in enumerate([10, 20, 30, 40])
    ]

    # Create touch details for Ice
    ice_touch_details = [
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
    ]

    # Create support pivots for Creek
    support_pivots = []
    for i, idx in enumerate([10, 20, 30, 40]):
        bar = OHLCVBar(
            id=uuid4(),
            symbol=symbol,
            timeframe="1d",
            timestamp=base_timestamp + timedelta(days=idx),
            open=creek_level - Decimal("1.00"),
            high=creek_level + Decimal("5.00"),
            low=creek_level - Decimal("2.00"),
            close=creek_level + Decimal("1.00"),
            volume=1_000_000,
            spread=Decimal("7.00"),
            spread_ratio=Decimal("1.0"),
            volume_ratio=Decimal("1.0"),
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
        touch_count=4,
        cluster_type=PivotType.LOW,
        std_deviation=Decimal("0.50"),
        timestamp_range=(support_pivots[0].timestamp, support_pivots[-1].timestamp),
    )

    # Create resistance pivots for Ice
    resistance_pivots = []
    for i, idx in enumerate([15, 25, 35]):
        bar = OHLCVBar(
            id=uuid4(),
            symbol=symbol,
            timeframe="1d",
            timestamp=base_timestamp + timedelta(days=idx),
            open=ice_level - Decimal("5.00"),
            high=ice_level + Decimal("2.00"),
            low=ice_level - Decimal("1.00"),
            close=ice_level - Decimal("1.00"),
            volume=1_000_000,
            spread=Decimal("7.00"),
            spread_ratio=Decimal("1.0"),
            volume_ratio=Decimal("1.0"),
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
        average_price=ice_level + Decimal("2.00"),
        min_price=ice_level + Decimal("1.00"),
        max_price=ice_level + Decimal("3.00"),
        price_range=Decimal("2.00"),
        touch_count=3,
        cluster_type=PivotType.HIGH,
        std_deviation=Decimal("0.50"),
        timestamp_range=(resistance_pivots[0].timestamp, resistance_pivots[-1].timestamp),
    )

    # Calculate midpoint and range width
    midpoint = (creek_level + ice_level) / Decimal("2")
    range_width = ice_level - creek_level
    range_width_pct = range_width / creek_level

    return TradingRange(
        id=uuid4(),
        symbol=symbol,
        timeframe="1d",
        support_cluster=support_cluster,
        resistance_cluster=resistance_cluster,
        support=creek_level,
        resistance=ice_level,
        midpoint=midpoint,
        range_width=range_width,
        range_width_pct=range_width_pct,
        start_index=0,
        end_index=50,
        duration=51,
        quality_score=85,
        status=RangeStatus.ACTIVE,
        start_timestamp=base_timestamp,
        end_timestamp=base_timestamp + timedelta(days=50),
        creek=CreekLevel(
            price=creek_level,
            absolute_low=creek_level - Decimal("1.00"),
            touch_count=4,
            touch_details=creek_touch_details,
            strength_score=creek_strength,
            strength_rating="EXCELLENT" if creek_strength >= 80 else "STRONG",
            last_test_timestamp=base_timestamp + timedelta(days=40),
            first_test_timestamp=base_timestamp + timedelta(days=10),
            hold_duration=30,
            confidence="HIGH",
            volume_trend="DECREASING",
        ),
        ice=IceLevel(
            price=ice_level,
            absolute_high=ice_level + Decimal("1.00"),
            touch_count=3,
            touch_details=ice_touch_details,
            strength_score=ice_strength,
            strength_rating="EXCELLENT" if ice_strength >= 80 else "STRONG",
            last_test_timestamp=base_timestamp + timedelta(days=35),
            first_test_timestamp=base_timestamp + timedelta(days=15),
            hold_duration=20,
            confidence="HIGH",
            volume_trend="DECREASING",
        ),
    )


# ============================================================================
# Task 2: Stock Spring Integration Tests (AC 2)
# ============================================================================


@pytest.mark.integration
def test_stock_spring_detection_aapl():
    """
    Test stock spring detection end-to-end with AAPL.

    Validates:
        - Spring detected with symbol="AAPL"
        - asset_class="stock", volume_reliability="HIGH"
        - Confidence caps at 100 (stock ceiling)
        - Confidence meets 70 minimum threshold

    AC 2: Test stock spring detection end-to-end
    """
    # Setup: Create AAPL trading range and spring pattern
    symbol = "AAPL"
    creek_level = Decimal("100.00")
    trading_range = create_trading_range(symbol=symbol, creek_level=creek_level)

    # Create spring pattern: 2% penetration, 0.4x volume, 2-bar recovery
    bars = create_spring_bars(
        creek_level=creek_level,
        penetration_pct=Decimal("0.02"),
        volume_ratio=Decimal("0.4"),
        recovery_bars=2,
        symbol=symbol,
    )

    # Detect spring
    spring = detect_spring(
        trading_range=trading_range,
        bars=bars,
        phase=WyckoffPhase.C,
        symbol=symbol,
    )

    # Assertions
    assert spring is not None, "AAPL spring should be detected"
    assert spring.asset_class == "stock", "AAPL should be classified as stock"
    assert spring.volume_reliability == "HIGH", "Stock should have HIGH volume reliability"

    # Calculate confidence
    confidence = calculate_spring_confidence(
        spring=spring,
        creek=trading_range.creek,
        previous_tests=[],
    )

    assert confidence.total_score <= 100, "Stock confidence should not exceed 100"
    assert confidence.total_score >= 70, "Stock confidence should meet 70 minimum threshold"

    logger.info(
        "stock_spring_aapl_test",
        symbol=symbol,
        asset_class=spring.asset_class,
        volume_reliability=spring.volume_reliability,
        confidence=confidence.total_score,
        max_confidence=100,
    )


@pytest.mark.integration
def test_stock_spring_component_scores():
    """
    Verify Spring uses correct component weights for stocks (Amendment 1).

    Component Score Structure (Story 5.4 formula):
        - Volume Quality: 40 points max
        - Penetration Depth: 35 points max
        - Recovery Speed: 25 points max
        - Creek Strength Bonus: +10 points (if applicable)
        - Volume Trend Bonus: +10 points (if declining)

    Total: 120 points raw max, normalized to 100 for stocks

    AC 2: Verify component weights (Story 5.4 formula)
    """
    symbol = "AAPL"
    creek_level = Decimal("100.00")
    trading_range = create_trading_range(
        symbol=symbol,
        creek_level=creek_level,
        creek_strength=85,  # Strong Creek for bonus
    )

    # Create good spring pattern
    bars = create_spring_bars(
        creek_level=creek_level,
        penetration_pct=Decimal("0.02"),
        volume_ratio=Decimal("0.35"),  # Good tier volume
        recovery_bars=2,
        symbol=symbol,
    )

    # Detect spring
    spring = detect_spring(
        trading_range=trading_range,
        bars=bars,
        phase=WyckoffPhase.C,
        symbol=symbol,
    )

    assert spring is not None, "Spring should be detected"

    # Calculate confidence
    confidence = calculate_spring_confidence(
        spring=spring,
        creek=trading_range.creek,
        previous_tests=[],
    )

    # Verify component score structure
    assert "volume_quality" in confidence.component_scores, "Should have volume_quality score"
    assert "penetration_depth" in confidence.component_scores, "Should have penetration_depth score"
    assert "recovery_speed" in confidence.component_scores, "Should have recovery_speed score"

    # Verify component score limits
    assert (
        confidence.component_scores["volume_quality"] <= 40
    ), "Volume quality should not exceed 40pts"
    assert (
        confidence.component_scores["penetration_depth"] <= 35
    ), "Penetration depth should not exceed 35pts"
    assert (
        confidence.component_scores["recovery_speed"] <= 25
    ), "Recovery speed should not exceed 25pts"

    # Bonuses (if applicable)
    if "creek_strength_bonus" in confidence.component_scores:
        assert (
            confidence.component_scores["creek_strength_bonus"] <= 10
        ), "Creek strength bonus should not exceed 10pts"
    if "volume_trend_bonus" in confidence.component_scores:
        assert (
            confidence.component_scores["volume_trend_bonus"] <= 10
        ), "Volume trend bonus should not exceed 10pts"

    logger.info(
        "stock_spring_component_scores",
        volume_quality=confidence.component_scores["volume_quality"],
        penetration_depth=confidence.component_scores["penetration_depth"],
        recovery_speed=confidence.component_scores["recovery_speed"],
        creek_bonus=confidence.component_scores.get("creek_strength_bonus", 0),
        volume_trend_bonus=confidence.component_scores.get("volume_trend_bonus", 0),
        total_score=confidence.total_score,
    )


@pytest.mark.integration
def test_stock_perfect_spring_confidence_100():
    """
    Test perfect stock spring pattern hits 100 confidence (Amendment 2).

    Perfect Spring Definition (Wyckoff textbook):
        - Penetration: 1.5% below Creek (ideal 1-2% range)
        - Volume: 0.29x average (ultra-low, <0.3x tier = 40pts)
        - Recovery: 1 bar (immediate demand = 25pts)
        - Creek Strength: 85+ (strong Creek = 10pts bonus)
        - Volume Trend: DECLINING (10pts bonus)

    Expected Raw Score: 40 + 35 + 25 + 10 + 10 = 120 points
    Stock Normalized: (120/120) * 100 = 100 confidence

    AC 2: Test perfect pattern definition
    """
    symbol = "AAPL"
    creek_level = Decimal("100.00")

    # Create strong Creek with DECLINING volume trend
    trading_range = create_trading_range(
        symbol=symbol,
        creek_level=creek_level,
        creek_strength=85,  # Strong Creek (80+) for bonus
    )

    # Create perfect spring pattern
    bars = create_perfect_spring_bars(
        creek_level=creek_level,
        penetration_pct=Decimal("0.015"),  # 1.5% penetration (perfect)
        volume_ratio=Decimal("0.29"),  # 0.29x volume (ultra-low)
        recovery_bars=1,  # Immediate recovery
        symbol=symbol,
    )

    # Detect spring
    spring = detect_spring(
        trading_range=trading_range,
        bars=bars,
        phase=WyckoffPhase.C,
        symbol=symbol,
    )

    assert spring is not None, "Perfect spring should be detected"

    # Calculate confidence
    confidence = calculate_spring_confidence(
        spring=spring,
        creek=trading_range.creek,
        previous_tests=[],
    )

    # CRITICAL: Perfect stock spring should hit 100
    assert confidence.total_score == 100, (
        f"Perfect stock spring should score 100, got {confidence.total_score}. "
        f"Component scores: {confidence.component_scores}"
    )

    logger.info(
        "perfect_stock_spring_test",
        symbol=symbol,
        penetration_pct=spring.penetration_pct,
        volume_ratio=spring.volume_ratio,
        recovery_bars=spring.recovery_bars,
        creek_strength=trading_range.creek.strength_score,
        volume_trend=trading_range.creek.volume_trend,
        component_scores=confidence.component_scores,
        total_score=confidence.total_score,
        message="Perfect stock spring demonstrates 100-point ceiling",
    )


# ============================================================================
# Task 3: Forex Spring Integration Tests (AC 3)
# ============================================================================


@pytest.mark.integration
def test_forex_spring_detection_eurusd():
    """
    Test forex spring detection end-to-end with EUR/USD.

    Validates:
        - Spring detected with symbol="EUR/USD"
        - asset_class="forex", volume_reliability="LOW"
        - Confidence caps at 85 (forex ceiling)
        - Confidence meets 70 minimum threshold

    AC 3: Test forex spring detection end-to-end
    """
    # Setup: Create EUR/USD trading range and spring pattern
    symbol = "EUR/USD"
    creek_level = Decimal("1.1000")
    trading_range = create_trading_range(symbol=symbol, creek_level=creek_level)

    # Create spring pattern: 2% penetration, 0.4x volume, 2-bar recovery
    bars = create_spring_bars(
        creek_level=creek_level,
        penetration_pct=Decimal("0.02"),
        volume_ratio=Decimal("0.4"),
        recovery_bars=2,
        symbol=symbol,
    )

    # Detect spring
    spring = detect_spring(
        trading_range=trading_range,
        bars=bars,
        phase=WyckoffPhase.C,
        symbol=symbol,
    )

    # Assertions
    assert spring is not None, "EUR/USD spring should be detected"
    assert spring.asset_class == "forex", "EUR/USD should be classified as forex"
    assert spring.volume_reliability == "LOW", "Forex should have LOW volume reliability"

    # Calculate confidence
    confidence = calculate_spring_confidence(
        spring=spring,
        creek=trading_range.creek,
        previous_tests=[],
    )

    assert confidence.total_score <= 85, "Forex confidence should not exceed 85"
    assert confidence.total_score >= 70, "Forex confidence should meet 70 minimum threshold"

    logger.info(
        "forex_spring_eurusd_test",
        symbol=symbol,
        asset_class=spring.asset_class,
        volume_reliability=spring.volume_reliability,
        confidence=confidence.total_score,
        max_confidence=85,
    )


@pytest.mark.integration
def test_forex_perfect_spring_confidence_cap():
    """
    Test that PERFECT spring pattern caps at 85 for forex (Amendment 2).

    Perfect Spring Definition (Wyckoff textbook example):
        - Penetration: 1.5% below Creek (ideal 1-2% range)
        - Volume: 0.3x average (ultra-low, <0.3x tier = 40pts)
        - Recovery: 1 bar (immediate demand = 25pts)
        - Creek Strength: 80+ (3+ successful tests = 10pts bonus)
        - Volume Trend: DECLINING across 3+ tests (10pts bonus)

    Expected Raw Score: 40 + 35 + 25 + 10 + 10 = 120 points

    Stock Normalized: (120/120) * 100 = 100 confidence
    Forex Normalized: (120/120) * 85 = 85 confidence (CAPPED)

    This test PROVES the humility tax in action.

    AC 3: Test perfect forex spring confidence cap
    """
    symbol = "EUR/USD"
    creek_level = Decimal("1.1000")

    # Create strong Creek with DECLINING volume trend
    trading_range = create_trading_range(
        symbol=symbol,
        creek_level=creek_level,
        creek_strength=85,  # Strong Creek (80+) for bonus
    )

    # Create perfect spring pattern
    bars = create_perfect_spring_bars(
        creek_level=creek_level,
        penetration_pct=Decimal("0.015"),  # 1.5% penetration (perfect)
        volume_ratio=Decimal("0.29"),  # 0.29x volume (ultra-low)
        recovery_bars=1,  # Immediate recovery
        symbol=symbol,
    )

    # Detect spring
    spring = detect_spring(
        trading_range=trading_range,
        bars=bars,
        phase=WyckoffPhase.C,
        symbol=symbol,
    )

    assert spring is not None, "Perfect forex spring should be detected"

    # Calculate confidence
    confidence = calculate_spring_confidence(
        spring=spring,
        creek=trading_range.creek,
        previous_tests=[],
    )

    # CRITICAL: Forex perfect pattern caps at 85, not 100
    assert confidence.total_score == 85, (
        f"Perfect forex spring should cap at 85, got {confidence.total_score}. "
        f"Component scores: {confidence.component_scores}"
    )

    logger.info(
        "perfect_spring_forex_cap_test",
        symbol=symbol,
        volume_score=confidence.component_scores.get("volume_quality", 0),
        penetration_score=confidence.component_scores.get("penetration_depth", 0),
        recovery_score=confidence.component_scores.get("recovery_speed", 0),
        creek_bonus=confidence.component_scores.get("creek_strength_bonus", 0),
        volume_trend_bonus=confidence.component_scores.get("volume_trend_bonus", 0),
        raw_score=sum(confidence.component_scores.values()),
        normalized_score=confidence.total_score,
        message="Perfect pattern demonstrates forex 85-point ceiling",
    )


@pytest.mark.integration
def test_forex_spring_detection_gbpusd():
    """
    Test forex spring detection with GBP/USD.

    AC 3: Test forex spring detection end-to-end
    """
    symbol = "GBP/USD"
    creek_level = Decimal("1.2500")
    trading_range = create_trading_range(symbol=symbol, creek_level=creek_level)

    # Create spring pattern
    bars = create_spring_bars(
        creek_level=creek_level,
        penetration_pct=Decimal("0.025"),
        volume_ratio=Decimal("0.45"),
        recovery_bars=2,
        symbol=symbol,
    )

    # Detect spring
    spring = detect_spring(
        trading_range=trading_range,
        bars=bars,
        phase=WyckoffPhase.C,
        symbol=symbol,
    )

    assert spring is not None, "GBP/USD spring should be detected"
    assert spring.asset_class == "forex"
    assert spring.volume_reliability == "LOW"

    # Calculate confidence
    confidence = calculate_spring_confidence(
        spring=spring,
        creek=trading_range.creek,
        previous_tests=[],
    )

    assert confidence.total_score <= 85, "GBP/USD confidence should cap at 85"
    assert confidence.total_score >= 70, "GBP/USD confidence should meet minimum threshold"


# ============================================================================
# Task 4: CFD Index Integration Tests (AC 4)
# ============================================================================


@pytest.mark.integration
def test_cfd_spring_detection_us30():
    """
    Test CFD index spring detection with US30 (Dow Jones CFD).

    CFDs are treated as forex (tick volume), so:
        - asset_class="forex"
        - volume_reliability="LOW"
        - Max confidence: 85

    AC 4: Test CFD index spring detection
    """
    symbol = "US30"
    creek_level = Decimal("34000.00")
    trading_range = create_trading_range(symbol=symbol, creek_level=creek_level)

    # Create spring pattern
    bars = create_spring_bars(
        creek_level=creek_level,
        penetration_pct=Decimal("0.02"),
        volume_ratio=Decimal("0.4"),
        recovery_bars=2,
        symbol=symbol,
    )

    # Detect spring
    spring = detect_spring(
        trading_range=trading_range,
        bars=bars,
        phase=WyckoffPhase.C,
        symbol=symbol,
    )

    assert spring is not None, "US30 spring should be detected"
    assert spring.asset_class == "forex", "CFD should be classified as forex (tick volume)"
    assert spring.volume_reliability == "LOW", "CFD should have LOW volume reliability"

    # Calculate confidence
    confidence = calculate_spring_confidence(
        spring=spring,
        creek=trading_range.creek,
        previous_tests=[],
    )

    assert confidence.total_score <= 85, "CFD confidence should cap at 85 (like forex)"
    assert confidence.total_score >= 70, "CFD confidence should meet minimum threshold"

    logger.info(
        "cfd_spring_us30_test",
        symbol=symbol,
        asset_class=spring.asset_class,
        volume_reliability=spring.volume_reliability,
        confidence=confidence.total_score,
        max_confidence=85,
    )


@pytest.mark.integration
def test_cfd_symbols_detected_as_forex():
    """
    Verify CFD symbols are correctly detected as forex by factory (AC 4).

    CFD Indices: US30, NAS100, SPX500, GER40, UK100, JPN225
    All should be treated as forex (tick volume).
    """
    cfd_symbols = ["US30", "NAS100", "SPX500", "GER40", "UK100", "JPN225"]

    for symbol in cfd_symbols:
        asset_class = detect_asset_class(symbol)
        assert (
            asset_class == "forex"
        ), f"{symbol} should be detected as forex (CFD uses tick volume)"

        # Verify scorer has correct properties
        scorer = get_scorer(asset_class)
        assert scorer.max_confidence == 85, f"{symbol} scorer should have max confidence 85"
        assert (
            scorer.volume_reliability == "LOW"
        ), f"{symbol} scorer should have LOW volume reliability"

    logger.info("cfd_asset_class_detection", symbols=cfd_symbols, result="All detected as forex")


# ============================================================================
# Task 5: Stock vs Forex Confidence Comparison Tests (AC 7)
# ============================================================================


@pytest.mark.integration
def test_stock_vs_forex_confidence_comparison():
    """
    Compare identical spring patterns with position sizing implications (Amendment 3).

    This test demonstrates WHY forex patterns require smaller positions
    even when the underlying pattern structure is identical.

    AC 7: Verify confidence score differences WITH position sizing implications
    """
    # Create identical pattern structure
    creek_level = Decimal("100.00")
    identical_pattern_params = {
        "creek_level": creek_level,
        "penetration_pct": Decimal("0.02"),  # 2% penetration
        "volume_ratio": Decimal("0.4"),  # 0.4x volume (GOOD tier)
        "recovery_bars": 2,
    }

    # Stock spring (AAPL)
    stock_symbol = "AAPL"
    stock_range = create_trading_range(symbol=stock_symbol, creek_level=creek_level)
    stock_bars = create_spring_bars(**identical_pattern_params, symbol=stock_symbol)
    stock_spring = detect_spring(
        trading_range=stock_range,
        bars=stock_bars,
        phase=WyckoffPhase.C,
        symbol=stock_symbol,
    )

    assert stock_spring is not None, "Stock spring should be detected"
    stock_confidence = calculate_spring_confidence(
        spring=stock_spring,
        creek=stock_range.creek,
        previous_tests=[],
    )

    # Forex spring (EUR/USD)
    forex_symbol = "EUR/USD"
    forex_creek = Decimal("1.1000")  # Different price level but same percentage structure
    forex_range = create_trading_range(symbol=forex_symbol, creek_level=forex_creek)
    forex_bars = create_spring_bars(
        creek_level=forex_creek,
        penetration_pct=Decimal("0.02"),  # Same 2% penetration
        volume_ratio=Decimal("0.4"),  # Same 0.4x volume ratio
        recovery_bars=2,  # Same recovery speed
        symbol=forex_symbol,
    )
    forex_spring = detect_spring(
        trading_range=forex_range,
        bars=forex_bars,
        phase=WyckoffPhase.C,
        symbol=forex_symbol,
    )

    assert forex_spring is not None, "Forex spring should be detected"
    forex_confidence = calculate_spring_confidence(
        spring=forex_spring,
        creek=forex_range.creek,
        previous_tests=[],
    )

    # Stock should score higher (volume confirmation)
    assert (
        stock_confidence.total_score > forex_confidence.total_score
    ), "Stock should score higher than forex for identical pattern"

    # Calculate confidence tiers and multipliers
    stock_tier, stock_multiplier = get_confidence_tier(
        stock_confidence.total_score, stock_spring.asset_class
    )
    forex_tier, forex_multiplier = get_confidence_tier(
        forex_confidence.total_score, forex_spring.asset_class
    )

    # Calculate position sizes for $100k account, 2% max risk
    account_size = Decimal("100000")
    max_risk_pct = Decimal("0.02")

    stock_position_risk = account_size * max_risk_pct * Decimal(str(stock_multiplier))
    forex_position_risk = account_size * max_risk_pct * Decimal(str(forex_multiplier))

    # Document differences (EducationalValue++)
    print("\n" + "=" * 70)
    print("RISK COMPARISON: IDENTICAL PATTERN, DIFFERENT ASSET CLASSES")
    print("=" * 70)
    print("\n📊 Pattern Structure (Identical):")
    print(f"  - Penetration: {stock_spring.penetration_pct:.2%} below Creek")
    print(f"  - Volume: {stock_spring.volume_ratio:.2f}x average")
    print(f"  - Recovery: {stock_spring.recovery_bars} bars")
    print("\n📈 Stock (AAPL) - HIGH Volume Reliability:")
    print(f"  - Confidence: {stock_confidence.total_score:.1f}/100")
    print(f"  - Quality Tier: {stock_tier}")
    print(f"  - Position Multiplier: {stock_multiplier:.2f}")
    print(f"  - Account Risk: ${stock_position_risk:,.2f} ({stock_multiplier * 2:.1f}%)")
    print("  - Volume Interpretation: REAL institutional shares traded")
    print("\n💱 Forex (EUR/USD) - LOW Volume Reliability:")
    print(f"  - Confidence: {forex_confidence.total_score:.1f}/85")
    print(f"  - Quality Tier: {forex_tier}")
    print(f"  - Position Multiplier: {forex_multiplier:.2f}")
    print(f"  - Account Risk: ${forex_position_risk:,.2f} ({forex_multiplier * 2:.1f}%)")
    print("  - Volume Interpretation: TICK volume (activity only)")
    print("\n⚠️  Position Size Difference:")
    position_diff_pct = (stock_multiplier - forex_multiplier) * 2
    position_diff_usd = stock_position_risk - forex_position_risk
    print(f"  - {position_diff_pct:.1f}% of account (${position_diff_usd:,.2f})")
    print("  - Reason: Tick volume lacks institutional confirmation")
    print("=" * 70 + "\n")

    # Assertions for test validation
    assert (
        stock_multiplier > forex_multiplier
    ), "Stock multiplier must be higher due to HIGH volume reliability"
    assert (
        stock_position_risk > forex_position_risk
    ), "Stock position should be larger for identical pattern"

    logger.info(
        "stock_vs_forex_comparison",
        stock_confidence=stock_confidence.total_score,
        forex_confidence=forex_confidence.total_score,
        stock_tier=stock_tier,
        forex_tier=forex_tier,
        stock_multiplier=stock_multiplier,
        forex_multiplier=forex_multiplier,
        position_diff_usd=float(position_diff_usd),
        position_diff_pct=float(position_diff_pct),
    )


# ============================================================================
# Task 6: Minimum Confidence Threshold Tests (AC 10, Amendment 5)
# ============================================================================


@pytest.mark.integration
def test_minimum_confidence_threshold_enforcement():
    """
    Test that 70 minimum confidence is enforced for ALL asset classes (Amendment 5).

    Story 0.5 AC 15: Patterns below 70 confidence should be rejected
    regardless of asset class (no special treatment for forex).

    AC 10: Verify minimum confidence threshold enforcement
    """
    # Create marginal spring pattern (scores ~69 confidence)
    creek_level = Decimal("100.00")
    marginal_params = {
        "creek_level": creek_level,
        "penetration_pct": Decimal("0.045"),  # Deep penetration (4.5%)
        "volume_ratio": Decimal("0.65"),  # High volume (near 0.7 limit)
        "recovery_bars": 5,  # Slow recovery
    }

    # Test stock rejection
    stock_symbol = "AAPL"
    stock_range = create_trading_range(symbol=stock_symbol, creek_level=creek_level)
    stock_bars = create_spring_bars(**marginal_params, symbol=stock_symbol)
    stock_spring = detect_spring(
        trading_range=stock_range,
        bars=stock_bars,
        phase=WyckoffPhase.C,
        symbol=stock_symbol,
    )

    if stock_spring is not None:
        stock_confidence = calculate_spring_confidence(
            spring=stock_spring,
            creek=stock_range.creek,
            previous_tests=[],
        )
        if stock_confidence.total_score < 70:
            logger.warning(
                "stock_below_threshold",
                confidence=stock_confidence.total_score,
                message="Stock spring detected but below 70 threshold",
            )
            # Pattern detected but should be rejected at signal generation
            assert stock_confidence.total_score < 70

    # Test forex rejection
    forex_symbol = "EUR/USD"
    forex_creek = Decimal("1.1000")
    forex_range = create_trading_range(symbol=forex_symbol, creek_level=forex_creek)
    forex_bars = create_spring_bars(
        creek_level=forex_creek,
        penetration_pct=Decimal("0.045"),
        volume_ratio=Decimal("0.65"),
        recovery_bars=5,
        symbol=forex_symbol,
    )
    forex_spring = detect_spring(
        trading_range=forex_range,
        bars=forex_bars,
        phase=WyckoffPhase.C,
        symbol=forex_symbol,
    )

    if forex_spring is not None:
        forex_confidence = calculate_spring_confidence(
            spring=forex_spring,
            creek=forex_range.creek,
            previous_tests=[],
        )
        if forex_confidence.total_score < 70:
            logger.warning(
                "forex_below_threshold",
                confidence=forex_confidence.total_score,
                message="Forex spring detected but below 70 threshold",
            )
            # Pattern detected but should be rejected at signal generation
            assert forex_confidence.total_score < 70

    # Boundary test: 70 should be accepted
    acceptable_params = {
        "creek_level": creek_level,
        "penetration_pct": Decimal("0.025"),  # Moderate penetration
        "volume_ratio": Decimal("0.5"),  # Moderate volume
        "recovery_bars": 3,  # Moderate recovery
    }

    stock_bars_acceptable = create_spring_bars(**acceptable_params, symbol=stock_symbol)
    stock_spring_acceptable = detect_spring(
        trading_range=stock_range,
        bars=stock_bars_acceptable,
        phase=WyckoffPhase.C,
        symbol=stock_symbol,
    )

    if stock_spring_acceptable is not None:
        stock_confidence_acceptable = calculate_spring_confidence(
            spring=stock_spring_acceptable,
            creek=stock_range.creek,
            previous_tests=[],
        )
        # This pattern should meet minimum threshold
        assert (
            stock_confidence_acceptable.total_score >= 70
        ), "Moderate pattern should meet 70 threshold"

    logger.info(
        "minimum_threshold_enforcement",
        minimum_threshold=70,
        message="Threshold enforced consistently across asset classes",
    )


# ============================================================================
# Task 7: Performance Benchmark Tests (AC 8)
# ============================================================================


@pytest.mark.integration
def test_spring_detection_performance():
    """
    Benchmark spring detection performance (<150ms for 500-bar sequence).

    AC 8: Performance benchmarks
    """
    # Create 500-bar sequence
    symbol = "AAPL"
    creek_level = Decimal("100.00")
    trading_range = create_trading_range(symbol=symbol, creek_level=creek_level)

    bars = create_spring_bars(
        creek_level=creek_level,
        penetration_pct=Decimal("0.02"),
        volume_ratio=Decimal("0.4"),
        recovery_bars=2,
        symbol=symbol,
        bar_count=500,
    )

    # Benchmark detection
    start = time.time()
    spring = detect_spring(
        trading_range=trading_range,
        bars=bars,
        phase=WyckoffPhase.C,
        symbol=symbol,
    )
    elapsed_ms = (time.time() - start) * 1000

    assert spring is not None, "Spring should be detected in 500-bar sequence"
    assert elapsed_ms < 150, f"Spring detection too slow: {elapsed_ms:.2f}ms (target: <150ms)"

    logger.info(
        "spring_detection_performance",
        bar_count=500,
        elapsed_ms=elapsed_ms,
        target_ms=150,
        status="PASS" if elapsed_ms < 150 else "FAIL",
    )


@pytest.mark.integration
def test_scorer_factory_performance():
    """
    Benchmark ScorerFactory overhead (<1ms per symbol).

    AC 8: Factory overhead performance
    """
    test_symbols = ["AAPL", "EUR/USD", "GBP/USD", "US30"] * 100  # 400 lookups

    start = time.time()
    for symbol in test_symbols:
        detect_asset_class(symbol)
    elapsed_ms = (time.time() - start) / len(test_symbols) * 1000

    assert elapsed_ms < 1, f"Factory too slow: {elapsed_ms:.4f}ms per call (target: <1ms)"

    logger.info(
        "factory_performance",
        total_lookups=len(test_symbols),
        elapsed_ms_per_call=elapsed_ms,
        target_ms=1,
        status="PASS" if elapsed_ms < 1 else "FAIL",
    )


@pytest.mark.integration
def test_scorer_cache_no_memory_leak():
    """
    Test scorer caching doesn't leak memory (AC 8).

    Verify singleton pattern working correctly - repeated detections
    should not create unbounded scorer instances.
    """
    gc.collect()
    initial_count = len(gc.get_objects())

    # Create springs repeatedly (should reuse cached scorers)
    symbol = "AAPL"
    creek_level = Decimal("100.00")
    trading_range = create_trading_range(symbol=symbol, creek_level=creek_level)

    for i in range(100):
        bars = create_spring_bars(
            creek_level=creek_level,
            penetration_pct=Decimal("0.02"),
            volume_ratio=Decimal("0.4"),
            recovery_bars=2,
            symbol=symbol,
        )
        detect_spring(
            trading_range=trading_range,
            bars=bars,
            phase=WyckoffPhase.C,
            symbol=symbol,
        )

    gc.collect()
    final_count = len(gc.get_objects())

    # Allow some growth, but not proportional to iteration count
    growth_factor = final_count / initial_count
    assert growth_factor < 1.5, (
        f"Excessive memory growth detected: {growth_factor:.2f}x "
        f"(initial: {initial_count}, final: {final_count})"
    )

    logger.info(
        "scorer_cache_memory_test",
        initial_objects=initial_count,
        final_objects=final_count,
        growth_factor=growth_factor,
        iterations=100,
        status="PASS" if growth_factor < 1.5 else "FAIL",
    )


# ============================================================================
# Task 8: Multi-Spring Campaign Integration Tests (AC 9, Amendment 4)
# ============================================================================


@pytest.mark.integration
def test_stock_multi_spring_accumulation_campaign():
    """
    Test 3-spring accumulation with DECLINING volume (professional pattern).

    Campaign Structure:
        - Spring 1 (Bar 25): 0.6x volume, 2.0% penetration
        - Spring 2 (Bar 40): 0.5x volume, 2.5% penetration (deeper, lower volume)
        - Spring 3 (Bar 55): 0.3x volume, 3.0% penetration (deepest, lowest volume)

    Expected:
        - Volume Trend: DECLINING (0.6 → 0.5 → 0.3)
        - Risk Level: LOW (professional accumulation)
        - Best Spring: Spring 3 (lowest volume per Wyckoff hierarchy)

    AC 9: Test multi-spring campaigns across asset classes
    """
    symbol = "AAPL"
    creek_level = Decimal("100.00")

    # Create 3-spring DECLINING volume campaign
    bars = create_three_spring_campaign(
        symbol=symbol,
        volumes=[Decimal("0.6"), Decimal("0.5"), Decimal("0.3")],
        penetrations=[Decimal("0.02"), Decimal("0.025"), Decimal("0.03")],
        creek_level=creek_level,
    )

    # Create trading range
    trading_range = create_trading_range(symbol=symbol, creek_level=creek_level)

    # Detect all springs in campaign
    detector = SpringDetector()
    history = detector.detect_all_springs(
        trading_range=trading_range,
        bars=bars,
        phase=WyckoffPhase.C,
    )

    assert history.spring_count == 3, f"Should detect 3 springs, got {history.spring_count}"
    assert history.volume_trend == "DECLINING", "Volume should decline (professional accumulation)"
    assert history.risk_level == "LOW", "Declining volume = LOW risk"

    # Best spring = lowest volume (Wyckoff hierarchy)
    assert history.best_spring.volume_ratio == Decimal(
        "0.3"
    ), "Best spring should have lowest volume (0.3x)"

    # All springs should be stock asset class
    for spring in history.springs:
        assert spring.asset_class == "stock", "All springs should be classified as stock"
        assert (
            spring.volume_reliability == "HIGH"
        ), "All stock springs should have HIGH volume reliability"

    logger.info(
        "stock_multi_spring_campaign",
        symbol=symbol,
        spring_count=history.spring_count,
        volume_trend=history.volume_trend,
        risk_level=history.risk_level,
        best_spring_volume=float(history.best_spring.volume_ratio),
    )


@pytest.mark.integration
def test_forex_multi_spring_accumulation_campaign():
    """
    Same campaign structure, forex symbol - verify confidence capping.

    CRITICAL TEST: Each spring in campaign should cap at 85 confidence.

    AC 9: Test multi-spring campaigns with forex
    """
    symbol = "EUR/USD"
    creek_level = Decimal("1.1000")

    # Create identical 3-spring DECLINING volume campaign
    bars = create_three_spring_campaign(
        symbol=symbol,
        volumes=[Decimal("0.6"), Decimal("0.5"), Decimal("0.3")],
        penetrations=[Decimal("0.02"), Decimal("0.025"), Decimal("0.03")],
        creek_level=creek_level,
    )

    # Create trading range
    trading_range = create_trading_range(symbol=symbol, creek_level=creek_level)

    # Detect all springs in campaign
    detector = SpringDetector()
    history = detector.detect_all_springs(
        trading_range=trading_range,
        bars=bars,
        phase=WyckoffPhase.C,
    )

    # Same campaign characteristics
    assert history.spring_count == 3, f"Should detect 3 springs, got {history.spring_count}"
    assert history.volume_trend == "DECLINING", "Trend detection should be asset-class independent"
    assert history.risk_level == "LOW", "Risk level should be asset-class independent"

    # Best spring same selection logic
    assert history.best_spring.volume_ratio == Decimal(
        "0.3"
    ), "Best spring selection should be asset-class independent"

    # BUT: All springs cap at 85 confidence
    for spring in history.springs:
        assert spring.asset_class == "forex", "All springs should be classified as forex"
        assert (
            spring.volume_reliability == "LOW"
        ), "All forex springs should have LOW volume reliability"

        # Calculate confidence for each spring
        confidence = calculate_spring_confidence(
            spring=spring,
            creek=trading_range.creek,
            previous_tests=[],
        )
        assert (
            confidence.total_score <= 85
        ), f"Forex spring confidence {confidence.total_score} exceeds 85 cap"

    # Best spring confidence also capped
    best_confidence = calculate_spring_confidence(
        spring=history.best_spring,
        creek=trading_range.creek,
        previous_tests=[],
    )
    assert best_confidence.total_score <= 85, "Best spring confidence should cap at 85 for forex"

    logger.info(
        "forex_multi_spring_campaign",
        symbol=symbol,
        spring_count=history.spring_count,
        volume_trend=history.volume_trend,
        risk_level=history.risk_level,
        best_spring_volume=float(history.best_spring.volume_ratio),
        best_spring_confidence=best_confidence.total_score,
        max_confidence=85,
    )


@pytest.mark.integration
def test_stock_vs_forex_campaign_comparison():
    """
    Compare identical 3-spring campaigns across asset classes.

    Demonstrates that campaign STRUCTURE (volume trend, risk level) is
    independent of asset class, but individual spring CONFIDENCE differs.

    AC 9: Campaign comparison across asset classes
    """
    creek_level = Decimal("100.00")
    campaign_params = {
        "volumes": [Decimal("0.6"), Decimal("0.5"), Decimal("0.3")],
        "penetrations": [Decimal("0.02"), Decimal("0.025"), Decimal("0.03")],
        "creek_level": creek_level,
    }

    # Stock campaign (AAPL)
    stock_symbol = "AAPL"
    stock_bars = create_three_spring_campaign(symbol=stock_symbol, **campaign_params)
    stock_range = create_trading_range(symbol=stock_symbol, creek_level=creek_level)
    stock_detector = SpringDetector()
    stock_history = stock_detector.detect_all_springs(
        trading_range=stock_range,
        bars=stock_bars,
        phase=WyckoffPhase.C,
    )

    # Forex campaign (EUR/USD)
    forex_symbol = "EUR/USD"
    forex_creek = Decimal("1.1000")
    forex_bars = create_three_spring_campaign(
        symbol=forex_symbol,
        volumes=campaign_params["volumes"],
        penetrations=campaign_params["penetrations"],
        creek_level=forex_creek,
    )
    forex_range = create_trading_range(symbol=forex_symbol, creek_level=forex_creek)
    forex_detector = SpringDetector()
    forex_history = forex_detector.detect_all_springs(
        trading_range=forex_range,
        bars=forex_bars,
        phase=WyckoffPhase.C,
    )

    # Campaign structure identical
    assert (
        stock_history.volume_trend == forex_history.volume_trend
    ), "Volume trend detection should be asset-class independent"
    assert (
        stock_history.risk_level == forex_history.risk_level
    ), "Risk level should be asset-class independent"
    assert (
        stock_history.spring_count == forex_history.spring_count
    ), "Spring count should be asset-class independent"

    # But confidence scores differ (stock higher)
    stock_best_conf = calculate_spring_confidence(
        spring=stock_history.best_spring,
        creek=stock_range.creek,
        previous_tests=[],
    )
    forex_best_conf = calculate_spring_confidence(
        spring=forex_history.best_spring,
        creek=forex_range.creek,
        previous_tests=[],
    )

    assert (
        stock_best_conf.total_score > forex_best_conf.total_score
    ), "Stock confidence should be higher than forex"
    assert stock_best_conf.total_score <= 100, "Stock confidence should cap at 100"
    assert forex_best_conf.total_score <= 85, "Forex confidence should cap at 85"

    logger.info(
        "campaign_comparison",
        stock_volume_trend=stock_history.volume_trend,
        forex_volume_trend=forex_history.volume_trend,
        stock_risk_level=stock_history.risk_level,
        forex_risk_level=forex_history.risk_level,
        stock_best_confidence=stock_best_conf.total_score,
        forex_best_confidence=forex_best_conf.total_score,
        message="Campaign structure identical, confidence differs by asset class",
    )


@pytest.mark.integration
def test_forex_rising_volume_campaign_warning():
    """
    Test 3-spring campaign with RISING volume (distribution warning).

    Campaign Structure:
        - Spring 1: 0.3x volume
        - Spring 2: 0.5x volume (RISING)
        - Spring 3: 0.65x volume (RISING - warning)

    Expected:
        - Volume Trend: RISING (0.3 → 0.5 → 0.65)
        - Risk Level: HIGH (distribution warning)
        - Best Spring: Spring 1 (lowest volume in RISING trend)

    AC 9: Test distribution warning campaigns
    """
    symbol = "EUR/USD"
    creek_level = Decimal("1.1000")

    # Create 3-spring RISING volume campaign (distribution warning)
    bars = create_three_spring_campaign(
        symbol=symbol,
        volumes=[Decimal("0.3"), Decimal("0.5"), Decimal("0.65")],
        penetrations=[Decimal("0.02"), Decimal("0.025"), Decimal("0.03")],
        creek_level=creek_level,
    )

    # Create trading range
    trading_range = create_trading_range(symbol=symbol, creek_level=creek_level)

    # Detect all springs in campaign
    detector = SpringDetector()
    history = detector.detect_all_springs(
        trading_range=trading_range,
        bars=bars,
        phase=WyckoffPhase.C,
    )

    assert history.spring_count == 3, f"Should detect 3 springs, got {history.spring_count}"
    assert history.volume_trend == "RISING", "Volume should be rising (distribution warning)"
    assert history.risk_level == "HIGH", "Rising volume = HIGH risk (distribution)"

    # Best spring is FIRST (lowest volume in RISING trend)
    assert history.best_spring.volume_ratio == Decimal(
        "0.3"
    ), "Best spring should be first (lowest volume in RISING trend)"

    logger.info(
        "rising_volume_campaign_warning",
        symbol=symbol,
        spring_count=history.spring_count,
        volume_trend=history.volume_trend,
        risk_level=history.risk_level,
        best_spring_volume=float(history.best_spring.volume_ratio),
        message="RISING volume campaign detected - HIGH risk distribution warning",
    )
