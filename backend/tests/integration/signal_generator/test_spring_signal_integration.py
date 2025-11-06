"""
Integration tests for Spring Signal Generator with realistic market scenarios.

These tests validate signal generation with realistic trading ranges that have
proper Creek/Jump levels, representing actual Wyckoff accumulation patterns.
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from src.models.creek_level import CreekLevel
from src.models.jump_level import JumpLevel
from src.models.ohlcv import OHLCVBar
from src.models.phase_classification import WyckoffPhase
from src.models.spring import Spring
from src.models.test import Test
from src.models.trading_range import TradingRange, RangeStatus
from src.signal_generator.spring_signal_generator import generate_spring_signal


@pytest.mark.integration
def test_spring_signal_realistic_aapl_accumulation():
    """
    Integration test: Spring signal generation with realistic AAPL accumulation range.

    Scenario: AAPL in 45-day accumulation range
    - Creek: $150.00 (strong support, 5 tests)
    - Jump: $165.00 (resistance, 3 rallies)
    - Spring: Penetrates to $147.00 (2% below Creek) on 0.4x volume
    - Test: Retests $148.00 (holds spring low) on 0.25x volume
    - Phase C: Final test before markup
    - Expected: Valid signal with 2.5R+ ratio
    """
    # Create realistic Creek level ($150 support)
    creek = CreekLevel(
        price=Decimal("150.00"),
        timestamp=datetime.now(UTC),
        absolute_low=Decimal("148.50"),
        touch_count=5,
        touch_details=[],
        strength_score=Decimal("88.0"),
        strength_rating="STRONG",
        last_test_timestamp=datetime.now(UTC),
        first_test_timestamp=datetime.now(UTC),
        hold_duration=15,
        confidence=Decimal("0.88"),
        volume_trend="DECLINING",
        bar_count=25,
        volume_weight=Decimal("0.85"),
        test_count=5,
        strength=Decimal("88.0"),
    )

    # Create realistic Jump level ($165 resistance)
    jump = JumpLevel(
        price=Decimal("165.00"),
        timestamp=datetime.now(UTC),
        absolute_high=Decimal("166.50"),
        touch_count=3,
        touch_details=[],
        strength_score=Decimal("82.0"),
        strength_rating="STRONG",
        last_rally_timestamp=datetime.now(UTC),
        first_rally_timestamp=datetime.now(UTC),
        hold_duration=12,
        confidence=Decimal("0.82"),
        volume_trend="INCREASING",
        bar_count=20,
        volume_weight=Decimal("0.78"),
        rally_count=3,
        strength=Decimal("82.0"),
    )

    # Create 45-day accumulation range
    trading_range = TradingRange(
        id=uuid4(),
        symbol="AAPL",
        timeframe="1d",
        start_timestamp=datetime.now(UTC),
        end_timestamp=None,
        bar_count=45,
        creek=creek,
        ice=creek,
        jump=jump,
        status=RangeStatus.ACTIVE,
    )

    # Create Spring bar (penetrates to $147, 2% below Creek)
    spring_bar = OHLCVBar(
        symbol="AAPL",
        timestamp=datetime.now(UTC),
        open=Decimal("149.50"),
        high=Decimal("150.00"),
        low=Decimal("147.00"),  # Spring low
        close=Decimal("149.00"),
        volume=8000000,  # Low volume
        spread=Decimal("3.00"),
        timeframe="1d",
    )

    # Create Spring pattern (2% penetration, 0.4x volume, 2-bar recovery)
    spring = Spring(
        bar=spring_bar,
        spring_low=Decimal("147.00"),
        penetration_pct=Decimal("0.02"),  # 2% below Creek
        volume_ratio=Decimal("0.40"),  # 40% of average (ideal)
        recovery_bars=2,  # Moderate recovery
        creek_reference=Decimal("150.00"),
        recovery_price=Decimal("151.00"),
        detection_timestamp=datetime.now(UTC),
        trading_range_id=trading_range.id,
    )

    # Create Test bar (retests $148, holds spring low)
    test_bar = OHLCVBar(
        symbol="AAPL",
        timestamp=datetime.now(UTC),
        open=Decimal("150.00"),
        high=Decimal("150.50"),
        low=Decimal("148.00"),  # Holds spring low
        close=Decimal("150.20"),
        volume=5000000,  # Lower than spring
        spread=Decimal("2.50"),
        timeframe="1d",
    )

    # Create Test confirmation
    test = Test(
        bar=test_bar,
        spring_reference=spring,
        distance_from_spring_low=Decimal("0.0068"),  # ~0.68% above spring low
        volume_ratio=Decimal("0.25"),  # 25% of average (excellent)
        volume_decrease_pct=Decimal("0.375"),  # 37.5% decrease from spring
        holds_spring_low=True,
    )

    # Generate signal
    signal = generate_spring_signal(
        spring=spring,
        test=test,
        range=trading_range,
        confidence=85,  # Good confidence from Story 5.4
        phase=WyckoffPhase.C,
        account_size=Decimal("100000"),  # $100k account
        risk_per_trade_pct=Decimal("0.01"),  # 1% risk
    )

    # Validate signal generated
    assert signal is not None, "Signal should be generated for valid spring"

    # Validate core fields
    assert signal.symbol == "AAPL"
    assert signal.timeframe == "1d"
    assert signal.confidence == 85
    assert signal.phase == "C"

    # Validate entry above Creek
    assert signal.entry_price > Decimal("150.00"), "Entry should be above Creek"
    assert signal.entry_price <= Decimal("150.75"), "Entry should be ~0.5% above Creek"

    # Validate adaptive stop (2% penetration → 1.5% buffer)
    expected_stop = Decimal("147.00") * Decimal("0.985")  # 1.5% buffer for 2% penetration
    assert signal.stop_loss == expected_stop, "Stop should use 1.5% buffer for medium spring"
    assert signal.stop_loss < Decimal("147.00"), "Stop must be below spring low"

    # Validate target at Jump
    assert signal.target_price == Decimal("165.00"), "Target should be at Jump level"

    # Validate R-multiple >= 2.0R
    risk = signal.entry_price - signal.stop_loss
    reward = signal.target_price - signal.entry_price
    r_multiple = reward / risk
    assert r_multiple >= Decimal("2.0"), f"R-multiple should be >= 2.0R (got {r_multiple:.2f}R)"
    assert signal.r_multiple == r_multiple.quantize(Decimal("0.01"))

    # Validate position sizing
    assert signal.recommended_position_size > 0, "Position size must be calculated"
    expected_dollar_risk = Decimal("100000") * Decimal("0.01")  # $1,000
    expected_position_raw = expected_dollar_risk / risk
    expected_position = int(expected_position_raw)  # Whole shares
    assert signal.recommended_position_size == expected_position, \
        f"Position size should be {expected_position} shares"

    # Validate urgency (2-bar recovery → MODERATE)
    assert signal.urgency == "MODERATE", "2-bar recovery should be MODERATE urgency"

    # Validate pattern data preserved
    assert signal.spring_bar_timestamp == spring.bar.timestamp
    assert signal.test_bar_timestamp == test.bar.timestamp
    assert signal.spring_volume_ratio == Decimal("0.40")
    assert signal.test_volume_ratio == Decimal("0.25")
    assert signal.penetration_pct == Decimal("0.02")
    assert signal.recovery_bars == 2
    assert signal.creek_level == Decimal("150.00")
    assert signal.jump_level == Decimal("165.00")


@pytest.mark.integration
def test_spring_signal_shallow_spring_wide_stop():
    """
    Integration test: Shallow spring (1.5% penetration) uses 2% stop buffer.

    Validates adaptive stop loss logic for shallow springs that need more room.
    """
    # Create range
    creek = CreekLevel(
        price=Decimal("200.00"),
        timestamp=datetime.now(UTC),
        absolute_low=Decimal("199.00"),
        touch_count=4,
        touch_details=[],
        strength_score=Decimal("85.0"),
        strength_rating="STRONG",
        last_test_timestamp=datetime.now(UTC),
        first_test_timestamp=datetime.now(UTC),
        hold_duration=12,
        confidence=Decimal("0.85"),
        volume_trend="DECLINING",
        bar_count=20,
        volume_weight=Decimal("0.80"),
        test_count=4,
        strength=Decimal("85.0"),
    )

    jump = JumpLevel(
        price=Decimal("220.00"),
        timestamp=datetime.now(UTC),
        absolute_high=Decimal("221.00"),
        touch_count=2,
        touch_details=[],
        strength_score=Decimal("78.0"),
        strength_rating="MODERATE",
        last_rally_timestamp=datetime.now(UTC),
        first_rally_timestamp=datetime.now(UTC),
        hold_duration=10,
        confidence=Decimal("0.78"),
        volume_trend="INCREASING",
        bar_count=15,
        volume_weight=Decimal("0.75"),
        rally_count=2,
        strength=Decimal("78.0"),
    )

    trading_range = TradingRange(
        id=uuid4(),
        symbol="TEST",
        timeframe="1d",
        start_timestamp=datetime.now(UTC),
        end_timestamp=None,
        bar_count=35,
        creek=creek,
        ice=creek,
        jump=jump,
        status=RangeStatus.ACTIVE,
    )

    # Shallow spring (1.5% penetration)
    spring_bar = OHLCVBar(
        symbol="TEST",
        timestamp=datetime.now(UTC),
        open=Decimal("199.50"),
        high=Decimal("200.00"),
        low=Decimal("197.00"),  # 1.5% below Creek
        close=Decimal("199.00"),
        volume=10000000,
        spread=Decimal("3.00"),
        timeframe="1d",
    )

    spring = Spring(
        bar=spring_bar,
        spring_low=Decimal("197.00"),
        penetration_pct=Decimal("0.015"),  # 1.5% (shallow)
        volume_ratio=Decimal("0.35"),
        recovery_bars=1,  # IMMEDIATE recovery
        creek_reference=Decimal("200.00"),
        recovery_price=Decimal("200.50"),
        detection_timestamp=datetime.now(UTC),
        trading_range_id=trading_range.id,
    )

    test_bar = OHLCVBar(
        symbol="TEST",
        timestamp=datetime.now(UTC),
        open=Decimal("199.00"),
        high=Decimal("200.00"),
        low=Decimal("197.50"),
        close=Decimal("199.50"),
        volume=6000000,
        spread=Decimal("2.50"),
        timeframe="1d",
    )

    test = Test(
        bar=test_bar,
        spring_reference=spring,
        distance_from_spring_low=Decimal("0.0025"),
        volume_ratio=Decimal("0.20"),
        volume_decrease_pct=Decimal("0.43"),
        holds_spring_low=True,
    )

    # Generate signal
    signal = generate_spring_signal(
        spring=spring,
        test=test,
        range=trading_range,
        confidence=82,
        phase=WyckoffPhase.C,
        account_size=Decimal("50000"),
    )

    assert signal is not None

    # Validate 2% stop buffer for shallow spring
    expected_stop = Decimal("197.00") * Decimal("0.98")  # 2% buffer
    assert signal.stop_loss == expected_stop, "Shallow spring should use 2% stop buffer"

    # Validate IMMEDIATE urgency (1-bar recovery)
    assert signal.urgency == "IMMEDIATE", "1-bar recovery should be IMMEDIATE urgency"


@pytest.mark.integration
def test_spring_signal_deep_spring_tight_stop():
    """
    Integration test: Deep spring (4% penetration) uses 1% stop buffer (tight).

    Validates adaptive stop loss logic for deep springs near breakdown threshold.
    """
    # Create range
    creek = CreekLevel(
        price=Decimal("100.00"),
        timestamp=datetime.now(UTC),
        absolute_low=Decimal("99.00"),
        touch_count=3,
        touch_details=[],
        strength_score=Decimal("80.0"),
        strength_rating="MODERATE",
        last_test_timestamp=datetime.now(UTC),
        first_test_timestamp=datetime.now(UTC),
        hold_duration=10,
        confidence=Decimal("0.80"),
        volume_trend="DECLINING",
        bar_count=18,
        volume_weight=Decimal("0.75"),
        test_count=3,
        strength=Decimal("80.0"),
    )

    jump = JumpLevel(
        price=Decimal("115.00"),
        timestamp=datetime.now(UTC),
        absolute_high=Decimal("116.00"),
        touch_count=2,
        touch_details=[],
        strength_score=Decimal("75.0"),
        strength_rating="MODERATE",
        last_rally_timestamp=datetime.now(UTC),
        first_rally_timestamp=datetime.now(UTC),
        hold_duration=8,
        confidence=Decimal("0.75"),
        volume_trend="INCREASING",
        bar_count=12,
        volume_weight=Decimal("0.70"),
        rally_count=2,
        strength=Decimal("75.0"),
    )

    trading_range = TradingRange(
        id=uuid4(),
        symbol="TEST",
        timeframe="1d",
        start_timestamp=datetime.now(UTC),
        end_timestamp=None,
        bar_count=30,
        creek=creek,
        ice=creek,
        jump=jump,
        status=RangeStatus.ACTIVE,
    )

    # Deep spring (4% penetration)
    spring_bar = OHLCVBar(
        symbol="TEST",
        timestamp=datetime.now(UTC),
        open=Decimal("99.00"),
        high=Decimal("99.50"),
        low=Decimal("96.00"),  # 4% below Creek (near breakdown)
        close=Decimal("98.00"),
        volume=12000000,
        spread=Decimal("3.50"),
        timeframe="1d",
    )

    spring = Spring(
        bar=spring_bar,
        spring_low=Decimal("96.00"),
        penetration_pct=Decimal("0.04"),  # 4% (deep)
        volume_ratio=Decimal("0.55"),
        recovery_bars=4,  # LOW urgency
        creek_reference=Decimal("100.00"),
        recovery_price=Decimal("100.20"),
        detection_timestamp=datetime.now(UTC),
        trading_range_id=trading_range.id,
    )

    test_bar = OHLCVBar(
        symbol="TEST",
        timestamp=datetime.now(UTC),
        open=Decimal("99.00"),
        high=Decimal("100.00"),
        low=Decimal("96.50"),
        close=Decimal("99.50"),
        volume=8000000,
        spread=Decimal("3.50"),
        timeframe="1d",
    )

    test = Test(
        bar=test_bar,
        spring_reference=spring,
        distance_from_spring_low=Decimal("0.0052"),
        volume_ratio=Decimal("0.35"),
        volume_decrease_pct=Decimal("0.36"),
        holds_spring_low=True,
    )

    # Generate signal
    signal = generate_spring_signal(
        spring=spring,
        test=test,
        range=trading_range,
        confidence=75,
        phase=WyckoffPhase.C,
        account_size=Decimal("100000"),
    )

    assert signal is not None

    # Validate 1% stop buffer for deep spring (tighter)
    expected_stop = Decimal("96.00") * Decimal("0.99")  # 1% buffer
    assert signal.stop_loss == expected_stop, "Deep spring should use 1% stop buffer (tight)"

    # Validate LOW urgency (4-bar recovery)
    assert signal.urgency == "LOW", "4-bar recovery should be LOW urgency"
