"""
Unit tests for Jump level calculation (Story 3.6).

Tests cause factor determination, jump calculation with different duration tiers,
edge cases, and validation with synthetic test data.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from src.models.creek_level import CreekLevel
from src.models.ice_level import IceLevel
from src.models.pivot import Pivot, PivotType
from src.models.price_cluster import PriceCluster
from src.models.touch_detail import TouchDetail
from src.models.trading_range import TradingRange
from src.pattern_engine.level_calculator import calculate_jump_level

# ============================================================================
# Test Fixtures
# ============================================================================

def create_test_pivot(price: Decimal, index: int, pivot_type: PivotType) -> Pivot:
    """Create test Pivot"""
    from src.models.ohlcv import OHLCVBar

    bar = OHLCVBar(
        symbol="TEST",
        timeframe="1d",
        timestamp=datetime.now(UTC),
        open=price,
        high=price + Decimal("1.00") if pivot_type == PivotType.LOW else price,
        low=price if pivot_type == PivotType.LOW else price - Decimal("1.00"),
        close=price,
        volume=1000000,
        spread=Decimal("1.00")
    )

    return Pivot(
        bar=bar,
        price=price,
        type=pivot_type,
        strength=5,
        timestamp=bar.timestamp,
        index=index
    )


def create_test_creek(
    price: Decimal = Decimal("100.00"),
    absolute_low: Decimal = Decimal("99.00")
) -> CreekLevel:
    """Create test CreekLevel"""
    return CreekLevel(
        price=price,
        absolute_low=absolute_low,
        touch_count=4,
        touch_details=[
            TouchDetail(
                index=i,
                price=price,
                volume=1000000,
                volume_ratio=Decimal("1.0"),
                close_position=Decimal("0.7"),
                rejection_wick=Decimal("0.7"),
                timestamp=datetime.now(UTC)
            )
            for i in range(4)
        ],
        strength_score=85,
        strength_rating="EXCELLENT",
        last_test_timestamp=datetime.now(UTC),
        first_test_timestamp=datetime.now(UTC),
        hold_duration=36,
        confidence="HIGH",
        volume_trend="DECREASING"
    )


def create_test_ice(
    price: Decimal = Decimal("110.00"),
    absolute_high: Decimal = Decimal("111.00")
) -> IceLevel:
    """Create test IceLevel"""
    return IceLevel(
        price=price,
        absolute_high=absolute_high,
        touch_count=4,
        touch_details=[
            TouchDetail(
                index=i,
                price=price,
                volume=1000000,
                volume_ratio=Decimal("1.0"),
                close_position=Decimal("0.3"),
                rejection_wick=Decimal("0.7"),
                timestamp=datetime.now(UTC)
            )
            for i in range(4)
        ],
        strength_score=85,
        strength_rating="EXCELLENT",
        last_test_timestamp=datetime.now(UTC),
        first_test_timestamp=datetime.now(UTC),
        hold_duration=37,
        confidence="HIGH",
        volume_trend="DECREASING"
    )


def create_test_trading_range(
    duration: int = 40,
    quality_score: int = 85,
    support_price: Decimal = Decimal("100.00"),
    resistance_price: Decimal = Decimal("110.00")
) -> TradingRange:
    """Create test TradingRange with required clusters"""
    # Create support pivots
    support_pivots = [
        create_test_pivot(support_price, i * 10, PivotType.LOW)
        for i in range(2)
    ]

    # Create resistance pivots
    resistance_pivots = [
        create_test_pivot(resistance_price, i * 10 + 5, PivotType.HIGH)
        for i in range(2)
    ]

    # Create support cluster
    support_cluster = PriceCluster(
        pivots=support_pivots,
        average_price=support_price,
        min_price=support_price,
        max_price=support_price,
        price_range=Decimal("0.00"),
        touch_count=len(support_pivots),
        cluster_type=PivotType.LOW,
        std_deviation=Decimal("0.50"),
        timestamp_range=(
            min(p.timestamp for p in support_pivots),
            max(p.timestamp for p in support_pivots)
        )
    )

    # Create resistance cluster
    resistance_cluster = PriceCluster(
        pivots=resistance_pivots,
        average_price=resistance_price,
        min_price=resistance_price,
        max_price=resistance_price,
        price_range=Decimal("0.00"),
        touch_count=len(resistance_pivots),
        cluster_type=PivotType.HIGH,
        std_deviation=Decimal("0.50"),
        timestamp_range=(
            min(p.timestamp for p in resistance_pivots),
            max(p.timestamp for p in resistance_pivots)
        )
    )

    # Calculate range metrics
    range_width = resistance_price - support_price
    range_width_pct = (range_width / support_price).quantize(Decimal("0.0001"))
    midpoint = ((support_price + resistance_price) / 2).quantize(Decimal("0.00000001"))

    return TradingRange(
        id=uuid4(),
        symbol="TEST",
        timeframe="1d",
        support_cluster=support_cluster,
        resistance_cluster=resistance_cluster,
        support=support_price,
        resistance=resistance_price,
        midpoint=midpoint,
        range_width=range_width,
        range_width_pct=range_width_pct,
        start_index=0,
        end_index=duration,
        duration=duration,
        quality_score=quality_score
    )


# ============================================================================
# Test: Cause Factor Determination (AC 2)
# ============================================================================

def test_cause_factor_long_accumulation():
    """Test scenario 1: Long accumulation (40+ bars) → 3.0x cause factor, HIGH confidence"""
    # Arrange
    trading_range = create_test_trading_range(duration=45)
    creek = create_test_creek(price=Decimal("100.00"))
    ice = create_test_ice(price=Decimal("110.00"))

    # Act
    jump = calculate_jump_level(trading_range, creek, ice)

    # Assert
    assert jump.cause_factor == Decimal("3.0"), "40+ bars should have 3.0x cause factor"
    assert jump.confidence == "HIGH", "40+ bars should have HIGH confidence"
    assert jump.range_duration == 45


def test_cause_factor_medium_accumulation():
    """Test scenario 2: Medium accumulation (25-39 bars) → 2.5x cause factor, MEDIUM confidence"""
    # Arrange
    trading_range = create_test_trading_range(duration=30)
    creek = create_test_creek(price=Decimal("100.00"))
    ice = create_test_ice(price=Decimal("110.00"))

    # Act
    jump = calculate_jump_level(trading_range, creek, ice)

    # Assert
    assert jump.cause_factor == Decimal("2.5"), "25-39 bars should have 2.5x cause factor"
    assert jump.confidence == "MEDIUM", "25-39 bars should have MEDIUM confidence"
    assert jump.range_duration == 30


def test_cause_factor_short_accumulation():
    """Test scenario 3: Short accumulation (15-24 bars) → 2.0x cause factor, LOW confidence"""
    # Arrange
    trading_range = create_test_trading_range(duration=20)
    creek = create_test_creek(price=Decimal("100.00"))
    ice = create_test_ice(price=Decimal("110.00"))

    # Act
    jump = calculate_jump_level(trading_range, creek, ice)

    # Assert
    assert jump.cause_factor == Decimal("2.0"), "15-24 bars should have 2.0x cause factor"
    assert jump.confidence == "LOW", "15-24 bars should have LOW confidence"
    assert jump.range_duration == 20


def test_cause_factor_insufficient_accumulation():
    """Test scenario 4: Insufficient cause (<15 bars) → raises ValueError"""
    # Arrange
    trading_range = create_test_trading_range(duration=10)
    creek = create_test_creek(price=Decimal("100.00"))
    ice = create_test_ice(price=Decimal("110.00"))

    # Act & Assert
    with pytest.raises(ValueError, match="Insufficient cause"):
        calculate_jump_level(trading_range, creek, ice)


# ============================================================================
# Test: Jump Calculation (AC 8)
# ============================================================================

def test_jump_calculation_40_bar_range():
    """Test AC 8: 40-bar range with $10 width calculates jump correctly (ice + $30)"""
    # Arrange
    trading_range = create_test_trading_range(duration=40)
    creek = create_test_creek(price=Decimal("100.00"))
    ice = create_test_ice(price=Decimal("110.00"))

    # Expected:
    # Range width: $110 - $100 = $10
    # Cause factor: 3.0x (40 bars)
    # Aggressive jump: $110 + (3.0 × $10) = $140
    # Conservative jump: $110 + (1.0 × $10) = $120

    # Act
    jump = calculate_jump_level(trading_range, creek, ice)

    # Assert
    assert jump.price == Decimal("140.00"), "Aggressive jump should be $140"
    assert jump.conservative_price == Decimal("120.00"), "Conservative jump should be $120"
    assert jump.range_width == Decimal("10.00"), "Range width should be $10"
    assert jump.cause_factor == Decimal("3.0"), "Cause factor should be 3.0x"
    assert jump.confidence == "HIGH", "Confidence should be HIGH"
    assert jump.risk_reward_ratio == Decimal("3.0"), "Risk-reward should be 3:1"
    assert jump.conservative_risk_reward == Decimal("1.0"), "Conservative RR should be 1:1"
    assert jump.ice_price == Decimal("110.00")
    assert jump.creek_price == Decimal("100.00")


# ============================================================================
# Test: All Duration Tiers (AC 2, 7)
# ============================================================================

def test_all_duration_tiers():
    """Test all cause factor tiers with same base range"""
    # Base: Creek $100, Ice $105, Width $5
    creek = create_test_creek(price=Decimal("100.00"))
    ice = create_test_ice(price=Decimal("105.00"))

    # Tier 1: 40+ bars (3.0x)
    range_40 = create_test_trading_range(duration=40)
    jump_40 = calculate_jump_level(range_40, creek, ice)
    assert jump_40.price == Decimal("120.00"), "40 bars: $105 + (3.0 × $5) = $120"
    assert jump_40.conservative_price == Decimal("110.00"), "Conservative: $105 + $5 = $110"
    assert jump_40.confidence == "HIGH"

    # Tier 2: 25-39 bars (2.5x)
    range_30 = create_test_trading_range(duration=30)
    jump_30 = calculate_jump_level(range_30, creek, ice)
    assert jump_30.price == Decimal("117.50"), "30 bars: $105 + (2.5 × $5) = $117.50"
    assert jump_30.conservative_price == Decimal("110.00"), "Conservative: $105 + $5 = $110"
    assert jump_30.confidence == "MEDIUM"

    # Tier 3: 15-24 bars (2.0x)
    range_20 = create_test_trading_range(duration=20)
    jump_20 = calculate_jump_level(range_20, creek, ice)
    assert jump_20.price == Decimal("115.00"), "20 bars: $105 + (2.0 × $5) = $115"
    assert jump_20.conservative_price == Decimal("110.00"), "Conservative: $105 + $5 = $110"
    assert jump_20.confidence == "LOW"


# ============================================================================
# Test: Edge Cases (AC all)
# ============================================================================

def test_edge_case_minimum_duration():
    """Test edge case 1: Minimum duration (15 bars exactly)"""
    # Arrange
    trading_range = create_test_trading_range(duration=15)
    creek = create_test_creek(price=Decimal("100.00"))
    ice = create_test_ice(price=Decimal("110.00"))

    # Act
    jump = calculate_jump_level(trading_range, creek, ice)

    # Assert
    assert jump.cause_factor == Decimal("2.0"), "15 bars (boundary) should have 2.0x"
    assert jump.confidence == "LOW", "15 bars should have LOW confidence"


def test_edge_case_duration_boundary_24_25():
    """Test edge case 2: Duration boundary 24/25 bars"""
    creek = create_test_creek(price=Decimal("100.00"))
    ice = create_test_ice(price=Decimal("110.00"))

    # 24 bars: LOW confidence, 2.0x
    range_24 = create_test_trading_range(duration=24)
    jump_24 = calculate_jump_level(range_24, creek, ice)
    assert jump_24.cause_factor == Decimal("2.0"), "24 bars should be 2.0x"
    assert jump_24.confidence == "LOW"

    # 25 bars: MEDIUM confidence, 2.5x
    range_25 = create_test_trading_range(duration=25)
    jump_25 = calculate_jump_level(range_25, creek, ice)
    assert jump_25.cause_factor == Decimal("2.5"), "25 bars should be 2.5x"
    assert jump_25.confidence == "MEDIUM"


def test_edge_case_duration_boundary_39_40():
    """Test edge case 3: Duration boundary 39/40 bars"""
    creek = create_test_creek(price=Decimal("100.00"))
    ice = create_test_ice(price=Decimal("110.00"))

    # 39 bars: MEDIUM confidence, 2.5x
    range_39 = create_test_trading_range(duration=39)
    jump_39 = calculate_jump_level(range_39, creek, ice)
    assert jump_39.cause_factor == Decimal("2.5"), "39 bars should be 2.5x"
    assert jump_39.confidence == "MEDIUM"

    # 40 bars: HIGH confidence, 3.0x
    range_40 = create_test_trading_range(duration=40)
    jump_40 = calculate_jump_level(range_40, creek, ice)
    assert jump_40.cause_factor == Decimal("3.0"), "40 bars should be 3.0x"
    assert jump_40.confidence == "HIGH"


def test_edge_case_very_long_accumulation():
    """Test edge case 4: Very long accumulation (100 bars)"""
    # Arrange
    trading_range = create_test_trading_range(duration=100)
    creek = create_test_creek(price=Decimal("100.00"))
    ice = create_test_ice(price=Decimal("110.00"))

    # Act
    jump = calculate_jump_level(trading_range, creek, ice)

    # Assert
    assert jump.cause_factor == Decimal("3.0"), "100 bars should cap at 3.0x"
    assert jump.confidence == "HIGH"


# ============================================================================
# Test: Validation (AC 10)
# ============================================================================

def test_validation_jump_above_ice():
    """Test validation: jump > ice (should always pass with correct math)"""
    # Arrange
    trading_range = create_test_trading_range(duration=40)
    creek = create_test_creek(price=Decimal("100.00"))
    ice = create_test_ice(price=Decimal("110.00"))

    # Act
    jump = calculate_jump_level(trading_range, creek, ice)

    # Assert
    assert jump.price > ice.price, "Aggressive jump must be above ice"
    assert jump.conservative_price > ice.price, "Conservative jump must be above ice"


def test_validation_ice_must_be_above_creek():
    """Test validation: ice > creek (defensive check)"""
    # Arrange: Ice BELOW Creek (invalid)
    trading_range = create_test_trading_range(duration=40)
    creek = create_test_creek(price=Decimal("110.00"))  # Higher
    ice = create_test_ice(price=Decimal("100.00"))  # Lower (invalid)

    # Act & Assert
    with pytest.raises(ValueError, match="Ice.*Creek"):
        calculate_jump_level(trading_range, creek, ice)


# ============================================================================
# Test: Risk-Reward Ratios
# ============================================================================

def test_risk_reward_calculation():
    """Test risk-reward ratio calculation for all tiers"""
    creek = create_test_creek(price=Decimal("100.00"))
    ice = create_test_ice(price=Decimal("110.00"))

    # 40 bars: 3:1 RR
    range_40 = create_test_trading_range(duration=40)
    jump_40 = calculate_jump_level(range_40, creek, ice)
    assert jump_40.risk_reward_ratio == Decimal("3.0"), "40 bars: 3:1 RR"

    # 30 bars: 2.5:1 RR
    range_30 = create_test_trading_range(duration=30)
    jump_30 = calculate_jump_level(range_30, creek, ice)
    assert jump_30.risk_reward_ratio == Decimal("2.5"), "30 bars: 2.5:1 RR"

    # 20 bars: 2:1 RR
    range_20 = create_test_trading_range(duration=20)
    jump_20 = calculate_jump_level(range_20, creek, ice)
    assert jump_20.risk_reward_ratio == Decimal("2.0"), "20 bars: 2:1 RR"

    # All conservative: 1:1 RR
    assert jump_40.conservative_risk_reward == Decimal("1.0"), "Conservative always 1:1"
    assert jump_30.conservative_risk_reward == Decimal("1.0"), "Conservative always 1:1"
    assert jump_20.conservative_risk_reward == Decimal("1.0"), "Conservative always 1:1"


# ============================================================================
# Test: JumpLevel Properties
# ============================================================================

def test_jump_level_properties():
    """Test JumpLevel model properties"""
    # Arrange
    trading_range = create_test_trading_range(duration=40)
    creek = create_test_creek(price=Decimal("100.00"))
    ice = create_test_ice(price=Decimal("110.00"))

    # Act
    jump = calculate_jump_level(trading_range, creek, ice)

    # Assert properties
    assert jump.is_high_confidence is True, "40 bars should be high confidence"
    assert jump.recommended_target == jump.price, "HIGH confidence recommends aggressive"

    # Test MEDIUM confidence
    range_30 = create_test_trading_range(duration=30)
    jump_30 = calculate_jump_level(range_30, creek, ice)
    assert jump_30.is_high_confidence is False
    assert jump_30.recommended_target == jump_30.conservative_price, "MEDIUM recommends conservative"

    # Test percentage moves
    expected_aggressive_pct = (Decimal("140.00") - Decimal("110.00")) / Decimal("110.00")
    expected_conservative_pct = (Decimal("120.00") - Decimal("110.00")) / Decimal("110.00")
    assert abs(jump.expected_move_pct - expected_aggressive_pct) < Decimal("0.0001")
    assert abs(jump.conservative_move_pct - expected_conservative_pct) < Decimal("0.0001")


# ============================================================================
# Test: Input Validation
# ============================================================================

def test_input_validation_none_inputs():
    """Test input validation: None inputs should raise ValueError"""
    trading_range = create_test_trading_range(duration=40)
    creek = create_test_creek()
    ice = create_test_ice()

    with pytest.raises(ValueError, match="trading_range cannot be None"):
        calculate_jump_level(None, creek, ice)

    with pytest.raises(ValueError, match="creek cannot be None"):
        calculate_jump_level(trading_range, None, ice)

    with pytest.raises(ValueError, match="ice cannot be None"):
        calculate_jump_level(trading_range, creek, None)


def test_calculated_at_timestamp():
    """Test that calculated_at timestamp is set"""
    # Arrange
    trading_range = create_test_trading_range(duration=40)
    creek = create_test_creek(price=Decimal("100.00"))
    ice = create_test_ice(price=Decimal("110.00"))

    # Act
    jump = calculate_jump_level(trading_range, creek, ice)

    # Assert
    assert jump.calculated_at is not None
    assert isinstance(jump.calculated_at, datetime)
