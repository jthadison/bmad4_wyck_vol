"""
Unit tests for Spring Signal Generator (Story 5.5).

Tests cover:
- Signal generation with all required fields (AC 9)
- FR13 test requirement enforcement (AC 1)
- FR19 R-multiple requirement (2.0R minimum) (AC 7)
- Entry/stop/target calculations (AC 2, 3, 4)
- R-multiple calculation (AC 6)
- Adaptive stop loss tiers (AC 3, Task 18A)
- Position sizing calculation (AC 11, Task 18B)
- Urgency determination (AC 12, Task 18C)
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, ROUND_DOWN
from uuid import uuid4

import pytest

from src.models.creek_level import CreekLevel
from src.models.jump_level import JumpLevel
from src.models.ohlcv import OHLCVBar
from src.models.phase_classification import WyckoffPhase
from src.models.spring import Spring
from src.models.test import Test
from src.models.trading_range import TradingRange, RangeStatus
from src.signal_generator.spring_signal_generator import (
    calculate_adaptive_stop_buffer,
    calculate_position_size,
    determine_urgency,
    generate_spring_signal,
)


# ============================================================================
# Test Fixtures
# ============================================================================


def create_test_range():
    """Helper to create trading range with Creek=$100, Jump=$110."""
    creek = CreekLevel(
        price=Decimal("100.00"),
        timestamp=datetime.now(UTC),
        bar_count=20,
        volume_weight=Decimal("0.8"),
        test_count=3,
        strength=Decimal("85.0"),
    )
    jump = JumpLevel(
        price=Decimal("110.00"),
        timestamp=datetime.now(UTC),
        bar_count=15,
        volume_weight=Decimal("0.75"),
        rally_count=2,
        strength=Decimal("80.0"),
    )
    return TradingRange(
        id=uuid4(),
        symbol="TEST",
        timeframe="1d",
        start_timestamp=datetime.now(UTC),
        end_timestamp=None,
        bar_count=45,
        creek=creek,
        ice=creek,
        jump=jump,
        status=RangeStatus.ACTIVE,
    )


def create_test_spring(range_id, penetration=Decimal("0.02"), recovery_bars=2, volume=Decimal("0.45")):
    """Helper to create Spring with customizable parameters."""
    bar = OHLCVBar(
        symbol="TEST",
        timestamp=datetime.now(UTC),
        open=Decimal("99.00"),
        high=Decimal("99.50"),
        low=Decimal("98.00"),
        close=Decimal("99.00"),
        volume=1000000,
        spread=Decimal("1.50"),
        timeframe="1d",
    )
    return Spring(
        bar=bar,
        spring_low=Decimal("98.00"),
        penetration_pct=penetration,
        volume_ratio=volume,
        recovery_bars=recovery_bars,
        creek_reference=Decimal("100.00"),
        recovery_price=Decimal("100.50"),
        detection_timestamp=datetime.now(UTC),
        trading_range_id=range_id,
    )


def create_test_test(spring):
    """Helper to create Test confirmation."""
    bar = OHLCVBar(
        symbol="TEST",
        timestamp=datetime.now(UTC),
        open=Decimal("99.00"),
        high=Decimal("99.50"),
        low=Decimal("98.50"),
        close=Decimal("99.20"),
        volume=600000,
        spread=Decimal("1.00"),
        timeframe="1d",
    )
    return Test(
        bar=bar,
        spring_reference=spring,
        distance_from_spring_low=Decimal("0.0051"),
        volume_ratio=Decimal("0.30"),
        volume_decrease_pct=Decimal("0.33"),
        holds_spring_low=True,
    )


# ============================================================================
# Task 11: Test signal generation with all required fields (AC 9)
# ============================================================================


def test_generate_spring_signal_all_fields():
    """Test AC 9: Generate signal with all required fields."""
    # Arrange
    range_obj = create_test_range()
    spring = create_test_spring(range_obj.id)
    test = create_test_test(spring)
    confidence = 85
    phase = WyckoffPhase.C
    account_size = Decimal("100000")

    # Act
    signal = generate_spring_signal(
        spring=spring,
        test=test,
        range=range_obj,
        confidence=confidence,
        phase=phase,
        account_size=account_size,
    )

    # Assert
    assert signal is not None, "Signal should be generated"
    assert signal.symbol == "TEST"
    assert signal.entry_price > Decimal("100")
    assert signal.stop_loss < Decimal("98.00")
    assert signal.target_price == Decimal("110")
    assert signal.confidence == 85
    assert signal.r_multiple >= Decimal("2.0")
    assert signal.recommended_position_size > 0
    assert signal.urgency in ["IMMEDIATE", "MODERATE", "LOW"]


# ============================================================================
# Task 12: Test FR13 test requirement (AC 1)
# ============================================================================


def test_spring_signal_rejected_no_test():
    """Test AC 1: Signal rejected when test=None (FR13)."""
    # Arrange
    range_obj = create_test_range()
    spring = create_test_spring(range_obj.id)

    # Act
    signal = generate_spring_signal(
        spring=spring,
        test=None,  # No test
        range=range_obj,
        confidence=85,
        phase=WyckoffPhase.C,
        account_size=Decimal("100000"),
    )

    # Assert
    assert signal is None, "FR13: Signal rejected without test"


# ============================================================================
# Task 18A: Test adaptive stop loss tiers (AC 3)
# ============================================================================


def test_adaptive_stop_shallow_spring():
    """Test shallow spring (1-2% penetration) → 2% stop buffer."""
    # Arrange
    range_obj = create_test_range()
    spring = create_test_spring(range_obj.id, penetration=Decimal("0.015"))  # 1.5%
    spring.spring_low = Decimal("98.50")
    test = create_test_test(spring)

    # Act
    signal = generate_spring_signal(
        spring=spring,
        test=test,
        range=range_obj,
        confidence=85,
        phase=WyckoffPhase.C,
        account_size=Decimal("100000"),
    )

    # Assert
    assert signal is not None
    expected_stop = Decimal("98.50") * Decimal("0.98")  # 2% buffer
    assert signal.stop_loss == expected_stop


def test_adaptive_stop_medium_spring():
    """Test medium spring (2-3% penetration) → 1.5% stop buffer."""
    # Arrange
    range_obj = create_test_range()
    spring = create_test_spring(range_obj.id, penetration=Decimal("0.025"))  # 2.5%
    test = create_test_test(spring)

    # Act
    signal = generate_spring_signal(
        spring=spring,
        test=test,
        range=range_obj,
        confidence=85,
        phase=WyckoffPhase.C,
        account_size=Decimal("100000"),
    )

    # Assert
    assert signal is not None
    expected_stop = Decimal("98.00") * Decimal("0.985")  # 1.5% buffer
    assert signal.stop_loss == expected_stop


def test_adaptive_stop_deep_spring():
    """Test deep spring (3-5% penetration) → 1% stop buffer."""
    # Arrange
    range_obj = create_test_range()
    spring = create_test_spring(range_obj.id, penetration=Decimal("0.045"))  # 4.5%
    spring.spring_low = Decimal("96.00")
    test = create_test_test(spring)

    # Act
    signal = generate_spring_signal(
        spring=spring,
        test=test,
        range=range_obj,
        confidence=85,
        phase=WyckoffPhase.C,
        account_size=Decimal("100000"),
    )

    # Assert
    assert signal is not None
    expected_stop = Decimal("96.00") * Decimal("0.99")  # 1% buffer
    assert signal.stop_loss == expected_stop


def test_calculate_adaptive_stop_buffer():
    """Test adaptive stop buffer calculation."""
    assert calculate_adaptive_stop_buffer(Decimal("0.015")) == Decimal("0.02")  # Shallow → 2%
    assert calculate_adaptive_stop_buffer(Decimal("0.025")) == Decimal("0.015")  # Medium → 1.5%
    assert calculate_adaptive_stop_buffer(Decimal("0.045")) == Decimal("0.01")  # Deep → 1%


# ============================================================================
# Task 18B: Test position sizing (AC 11)
# ============================================================================


def test_position_size_scales_with_account():
    """Test position size scales with account size."""
    # Arrange
    range_obj = create_test_range()
    spring = create_test_spring(range_obj.id)
    test = create_test_test(spring)

    # Act: $50k vs $100k account
    signal_50k = generate_spring_signal(
        spring=spring,
        test=test,
        range=range_obj,
        confidence=85,
        phase=WyckoffPhase.C,
        account_size=Decimal("50000"),
    )
    signal_100k = generate_spring_signal(
        spring=spring,
        test=test,
        range=range_obj,
        confidence=85,
        phase=WyckoffPhase.C,
        account_size=Decimal("100000"),
    )

    # Assert: 2x account → 2x position
    assert signal_100k.recommended_position_size == signal_50k.recommended_position_size * 2


def test_calculate_position_size_direct():
    """Test calculate_position_size helper function."""
    # Arrange
    entry = Decimal("100.50")
    stop = Decimal("96.53")
    account = Decimal("100000")
    risk_pct = Decimal("0.01")

    # Act
    position_size = calculate_position_size(entry, stop, account, risk_pct)

    # Assert
    risk_per_share = entry - stop  # $3.97
    dollar_risk = account * risk_pct  # $1,000
    expected_raw = dollar_risk / risk_per_share  # ~251.89 shares
    expected = expected_raw.quantize(Decimal("1"), rounding=ROUND_DOWN)  # 251 shares
    assert position_size == expected


def test_calculate_position_size_invalid_stop():
    """Test position sizing raises error if stop >= entry."""
    with pytest.raises(ValueError, match="Stop must be below entry"):
        calculate_position_size(
            Decimal("100.00"),
            Decimal("105.00"),  # Invalid
            Decimal("100000"),
            Decimal("0.01"),
        )


# ============================================================================
# Task 18C: Test urgency determination (AC 12)
# ============================================================================


def test_urgency_immediate():
    """Test IMMEDIATE urgency (1-bar recovery)."""
    # Arrange
    range_obj = create_test_range()
    spring = create_test_spring(range_obj.id, recovery_bars=1)
    test = create_test_test(spring)

    # Act
    signal = generate_spring_signal(
        spring=spring,
        test=test,
        range=range_obj,
        confidence=85,
        phase=WyckoffPhase.C,
        account_size=Decimal("100000"),
    )

    # Assert
    assert signal.urgency == "IMMEDIATE"


def test_urgency_moderate():
    """Test MODERATE urgency (2-3 bar recovery)."""
    # Arrange
    range_obj = create_test_range()
    spring = create_test_spring(range_obj.id, recovery_bars=2)
    test = create_test_test(spring)

    # Act
    signal = generate_spring_signal(
        spring=spring,
        test=test,
        range=range_obj,
        confidence=85,
        phase=WyckoffPhase.C,
        account_size=Decimal("100000"),
    )

    # Assert
    assert signal.urgency == "MODERATE"


def test_urgency_low():
    """Test LOW urgency (4-5 bar recovery)."""
    # Arrange
    range_obj = create_test_range()
    spring = create_test_spring(range_obj.id, recovery_bars=4)
    test = create_test_test(spring)

    # Act
    signal = generate_spring_signal(
        spring=spring,
        test=test,
        range=range_obj,
        confidence=85,
        phase=WyckoffPhase.C,
        account_size=Decimal("100000"),
    )

    # Assert
    assert signal.urgency == "LOW"


def test_determine_urgency_direct():
    """Test determine_urgency helper."""
    assert determine_urgency(1) == "IMMEDIATE"
    assert determine_urgency(2) == "MODERATE"
    assert determine_urgency(3) == "MODERATE"
    assert determine_urgency(4) == "LOW"
    assert determine_urgency(5) == "LOW"


# ============================================================================
# Additional edge case tests
# ============================================================================


def test_spring_signal_rejected_low_confidence():
    """Test signal rejected when confidence < 70%."""
    range_obj = create_test_range()
    spring = create_test_spring(range_obj.id)
    test = create_test_test(spring)

    signal = generate_spring_signal(
        spring=spring,
        test=test,
        range=range_obj,
        confidence=65,  # Too low
        phase=WyckoffPhase.C,
        account_size=Decimal("100000"),
    )

    assert signal is None


def test_spring_signal_entry_stop_target_relationships():
    """Test entry/stop/target are properly ordered."""
    range_obj = create_test_range()
    spring = create_test_spring(range_obj.id)
    test = create_test_test(spring)

    signal = generate_spring_signal(
        spring=spring,
        test=test,
        range=range_obj,
        confidence=85,
        phase=WyckoffPhase.C,
        account_size=Decimal("100000"),
    )

    assert signal is not None
    assert signal.stop_loss < signal.entry_price < signal.target_price
    assert signal.r_multiple >= Decimal("2.0")


# ============================================================================
# FR19 Rejection Test (R-multiple < 2.0R)
# ============================================================================


def test_spring_signal_rejected_low_r_multiple():
    """Test AC 7: Signal rejected when R < 2.0 (FR19 Updated)."""
    # Arrange: Create range with Jump too close to Creek for 2.0R
    creek = CreekLevel(
        price=Decimal("100.00"),
        timestamp=datetime.now(UTC),
        absolute_low=Decimal("99.00"),
        touch_count=5,
        touch_details=[],
        strength_score=Decimal("85.0"),
        strength_rating="STRONG",
        last_test_timestamp=datetime.now(UTC),
        first_test_timestamp=datetime.now(UTC),
        hold_duration=10,
        confidence=Decimal("0.85"),
        volume_trend="DECLINING",
        bar_count=20,
        volume_weight=Decimal("0.8"),
        test_count=3,
        strength=Decimal("85.0"),
    )

    # Jump only $2 above Creek (too close for 2.0R with adaptive stop)
    jump = JumpLevel(
        price=Decimal("102.00"),
        timestamp=datetime.now(UTC),
        absolute_high=Decimal("103.00"),
        touch_count=3,
        touch_details=[],
        strength_score=Decimal("70.0"),
        strength_rating="MODERATE",
        last_rally_timestamp=datetime.now(UTC),
        first_rally_timestamp=datetime.now(UTC),
        hold_duration=8,
        confidence=Decimal("0.70"),
        volume_trend="INCREASING",
        bar_count=15,
        volume_weight=Decimal("0.75"),
        rally_count=2,
        strength=Decimal("70.0"),
    )

    range_low_r = TradingRange(
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

    spring = create_test_spring(range_low_r.id)
    test = create_test_test(spring)

    # Act
    signal = generate_spring_signal(
        spring=spring,
        test=test,
        range=range_low_r,
        confidence=85,
        phase=WyckoffPhase.C,
        account_size=Decimal("100000"),
    )

    # Assert
    # Entry ~$100.50, Stop ~$96.53 (1.5% buffer for 2% penetration), Target $102
    # Risk: ~$3.97, Reward: ~$1.50, R-multiple: ~0.38R (well below 2.0R)
    assert signal is None, "FR19 (Updated): Signal rejected when R-multiple < 2.0R"


# ============================================================================
# Signal Serialization Test
# ============================================================================


def test_spring_signal_serialization():
    """Test SpringSignal JSON serialization/deserialization."""
    # Arrange
    range_obj = create_test_range()
    spring = create_test_spring(range_obj.id)
    test = create_test_test(spring)

    signal = generate_spring_signal(
        spring=spring,
        test=test,
        range=range_obj,
        confidence=85,
        phase=WyckoffPhase.C,
        account_size=Decimal("100000"),
    )

    assert signal is not None

    # Act: Serialize to JSON
    signal_json = signal.model_dump_json()

    # Deserialize back
    from src.models.spring_signal import SpringSignal
    signal_restored = SpringSignal.model_validate_json(signal_json)

    # Assert: All critical fields preserved
    assert signal_restored.id == signal.id
    assert signal_restored.symbol == signal.symbol
    assert signal_restored.entry_price == signal.entry_price
    assert signal_restored.stop_loss == signal.stop_loss
    assert signal_restored.target_price == signal.target_price
    assert signal_restored.confidence == signal.confidence
    assert signal_restored.r_multiple == signal.r_multiple
    assert signal_restored.recommended_position_size == signal.recommended_position_size
    assert signal_restored.urgency == signal.urgency
    assert signal_restored.phase == signal.phase

    # Verify Decimal fields serialized as strings in JSON
    import json
    signal_dict = json.loads(signal_json)
    assert isinstance(signal_dict["entry_price"], str), "Decimal should serialize as string"
    assert isinstance(signal_dict["stop_loss"], str), "Decimal should serialize as string"
    assert isinstance(signal_dict["target_price"], str), "Decimal should serialize as string"
    assert isinstance(signal_dict["recommended_position_size"], str), "Decimal should serialize as string"
