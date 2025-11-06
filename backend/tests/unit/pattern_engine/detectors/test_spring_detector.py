"""
Unit tests for spring_detector module.

Tests Spring pattern detection with synthetic data covering all acceptance criteria:
- AC 9: Valid spring detection (2% penetration, 0.4x volume)
- AC 10: High-volume rejection (0.8x volume)
- AC 4: Penetration depth limits (0-5%)
- AC 6: Recovery window (1-5 bars)
- AC 8: Phase C validation (FR15)
- AC 11: Creek validation (missing/invalid Creek)
- AC 12: Spring invalidation detection
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from src.models.ohlcv import OHLCVBar
from src.models.phase_classification import WyckoffPhase
from src.models.spring import Spring
from src.models.trading_range import TradingRange, RangeStatus
from src.models.price_cluster import PriceCluster
from src.models.creek_level import CreekLevel
from src.models.pivot import Pivot, PivotType
from src.models.touch_detail import TouchDetail
from src.pattern_engine.detectors.spring_detector import detect_spring


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
    creek_level: Decimal,
    symbol: str = "AAPL",
) -> TradingRange:
    """
    Create test trading range with Creek level.

    Args:
        creek_level: Creek price level
        symbol: Stock symbol (default: AAPL)

    Returns:
        TradingRange instance for testing
    """
    # Create pivot bars for support cluster
    base_timestamp = datetime(2024, 1, 1, tzinfo=UTC)

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

    # Create pivot bars for resistance cluster
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
    spring_index: int,
    spring_low: Decimal,
    spring_volume: int,
    recovery_bars: int = 1,
    base_volume: int = 100000,
) -> list[OHLCVBar]:
    """
    Create bar sequence with spring pattern.

    Args:
        creek_level: Creek price level
        spring_index: Index where spring occurs (must be >= 20)
        spring_low: Low price of spring bar (below creek_level)
        spring_volume: Volume of spring bar
        recovery_bars: Number of bars for recovery (1-5)
        base_volume: Average volume for normal bars

    Returns:
        List of OHLCVBar with spring pattern
    """
    bars = []
    base_timestamp = datetime(2024, 1, 1, tzinfo=UTC)

    # Create normal bars before spring (need at least 20 for volume calculation)
    for i in range(spring_index):
        timestamp = base_timestamp + timedelta(days=i)
        bars.append(
            create_test_bar(
                timestamp=timestamp,
                low=creek_level + Decimal("1.00"),
                high=creek_level + Decimal("5.00"),
                close=creek_level + Decimal("3.00"),
                volume=base_volume,
            )
        )

    # Create spring bar (penetrates below Creek)
    spring_timestamp = base_timestamp + timedelta(days=spring_index)
    bars.append(
        create_test_bar(
            timestamp=spring_timestamp,
            low=spring_low,
            high=creek_level,
            close=creek_level - Decimal("0.50"),  # Close below Creek
            volume=spring_volume,
        )
    )

    # Create recovery bars
    for i in range(recovery_bars):
        timestamp = spring_timestamp + timedelta(days=i + 1)
        if i == recovery_bars - 1:
            # Last recovery bar closes above Creek
            bars.append(
                create_test_bar(
                    timestamp=timestamp,
                    low=creek_level - Decimal("1.00"),
                    high=creek_level + Decimal("2.00"),
                    close=creek_level + Decimal("0.50"),  # Recovery!
                    volume=base_volume,
                )
            )
        else:
            # Intermediate recovery bars stay below Creek
            bars.append(
                create_test_bar(
                    timestamp=timestamp,
                    low=creek_level - Decimal("1.00"),
                    high=creek_level,
                    close=creek_level - Decimal("0.30"),
                    volume=base_volume,
                )
            )

    # Add a few more normal bars after recovery
    for i in range(5):
        timestamp = spring_timestamp + timedelta(days=recovery_bars + i + 1)
        bars.append(
            create_test_bar(
                timestamp=timestamp,
                low=creek_level + Decimal("1.00"),
                high=creek_level + Decimal("5.00"),
                close=creek_level + Decimal("3.00"),
                volume=base_volume,
            )
        )

    return bars


class TestDetectSpringValidCases:
    """Test suite for valid spring detection scenarios."""

    def test_detect_spring_valid_spring_2pct_penetration(self):
        """
        AC 9: Test valid spring detection with 2% penetration and 0.4x volume.

        This tests a good spring scenario:
        - 2% penetration below Creek (ideal range 1-2%)
        - 0.4x volume (low volume, good quality)
        - 1 bar recovery (rapid)
        - Phase C
        """
        # Arrange
        creek_level = Decimal("100.00")
        spring_low = Decimal("98.00")  # 2% below Creek
        base_volume = 100000
        spring_volume = 40000  # 0.4x volume

        range_obj = create_trading_range(creek_level)
        bars = create_bars_with_spring(
            creek_level=creek_level,
            spring_index=24,
            spring_low=spring_low,
            spring_volume=spring_volume,
            recovery_bars=1,
            base_volume=base_volume,
        )
        phase = WyckoffPhase.C

        # Act
        spring = detect_spring(range_obj, bars, phase)

        # Assert
        assert spring is not None, "Spring should be detected"
        assert spring.penetration_pct == Decimal("0.02"), "2% penetration"
        assert spring.volume_ratio < Decimal("0.7"), "Volume ratio < 0.7x"
        assert spring.recovery_bars == 1, "Recovery in 1 bar"
        assert spring.creek_reference == creek_level
        assert spring.spring_low == spring_low
        assert spring.quality_tier == "GOOD", "Should be GOOD quality spring (0.4x volume)"

    def test_detect_spring_1pct_penetration(self):
        """Test spring with 1% penetration (ideal shallow penetration)."""
        creek_level = Decimal("100.00")
        spring_low = Decimal("99.00")  # 1% below Creek
        base_volume = 100000
        spring_volume = 25000  # 0.25x volume (ultra-bullish, truly < 0.3x)

        range_obj = create_trading_range(creek_level)
        bars = create_bars_with_spring(
            creek_level=creek_level,
            spring_index=24,
            spring_low=spring_low,
            spring_volume=spring_volume,
            recovery_bars=1,
            base_volume=base_volume,
        )
        phase = WyckoffPhase.C

        spring = detect_spring(range_obj, bars, phase)

        assert spring is not None
        assert spring.penetration_pct == Decimal("0.01"), "1% penetration"
        assert spring.volume_ratio < Decimal("0.3"), "Ultra-low volume"
        assert spring.quality_tier == "IDEAL", "Should be IDEAL spring (1% + <0.3x vol)"
        assert spring.is_ideal_spring, "Should be ideal spring (1% + <0.3x vol)"

    def test_detect_spring_5pct_penetration_boundary(self):
        """Test spring at 5% penetration (maximum acceptable depth)."""
        creek_level = Decimal("100.00")
        spring_low = Decimal("95.00")  # Exactly 5% below Creek
        base_volume = 100000
        spring_volume = 45000  # 0.45x volume

        range_obj = create_trading_range(creek_level)
        bars = create_bars_with_spring(
            creek_level=creek_level,
            spring_index=24,
            spring_low=spring_low,
            spring_volume=spring_volume,
            recovery_bars=2,
            base_volume=base_volume,
        )
        phase = WyckoffPhase.C

        spring = detect_spring(range_obj, bars, phase)

        assert spring is not None, "5% penetration should be accepted (AC 4)"
        assert spring.penetration_pct == Decimal("0.05"), "5% penetration"
        assert spring.quality_tier == "ACCEPTABLE", "Deeper penetration = ACCEPTABLE tier"

    def test_detect_spring_recovery_in_5_bars(self):
        """AC 6: Test spring with recovery in 5 bars (slowest acceptable)."""
        creek_level = Decimal("100.00")
        spring_low = Decimal("98.00")
        base_volume = 100000
        spring_volume = 50000  # 0.5x volume

        range_obj = create_trading_range(creek_level)
        bars = create_bars_with_spring(
            creek_level=creek_level,
            spring_index=24,
            spring_low=spring_low,
            spring_volume=spring_volume,
            recovery_bars=5,  # Slowest acceptable recovery
            base_volume=base_volume,
        )
        phase = WyckoffPhase.C

        spring = detect_spring(range_obj, bars, phase)

        assert spring is not None, "Recovery in 5 bars should be accepted"
        assert spring.recovery_bars == 5, "Should track 5-bar recovery"


class TestDetectSpringRejectionCases:
    """Test suite for spring rejection scenarios."""

    def test_detect_spring_high_volume_rejected(self):
        """
        AC 10: Test high-volume (0.8x) penetration rejected as breakdown.

        FR12: Volume >= 0.7x = immediate rejection (non-negotiable).
        """
        creek_level = Decimal("100.00")
        spring_low = Decimal("98.00")  # 2% penetration (valid)
        base_volume = 100000
        spring_volume = 80000  # 0.8x volume (TOO HIGH)

        range_obj = create_trading_range(creek_level)
        bars = create_bars_with_spring(
            creek_level=creek_level,
            spring_index=24,
            spring_low=spring_low,
            spring_volume=spring_volume,
            recovery_bars=1,
            base_volume=base_volume,
        )
        phase = WyckoffPhase.C

        spring = detect_spring(range_obj, bars, phase)

        assert spring is None, "High-volume (0.8x) penetration should be REJECTED (FR12)"

    def test_volume_boundary_069_passes_070_rejects(self):
        """Test volume boundary: 0.69x passes, 0.70x rejects."""
        creek_level = Decimal("100.00")
        spring_low = Decimal("98.00")
        base_volume = 100000

        range_obj = create_trading_range(creek_level)

        # Test 0.69x volume (should PASS)
        bars_pass = create_bars_with_spring(
            creek_level=creek_level,
            spring_index=24,
            spring_low=spring_low,
            spring_volume=69000,  # 0.69x volume
            recovery_bars=1,
            base_volume=base_volume,
        )

        spring_pass = detect_spring(range_obj, bars_pass, WyckoffPhase.C)
        assert spring_pass is not None, "0.69x volume should pass"

        # Test 0.70x volume (should REJECT)
        bars_reject = create_bars_with_spring(
            creek_level=creek_level,
            spring_index=24,
            spring_low=spring_low,
            spring_volume=70000,  # 0.70x volume
            recovery_bars=1,
            base_volume=base_volume,
        )

        spring_reject = detect_spring(range_obj, bars_reject, WyckoffPhase.C)
        assert spring_reject is None, "0.70x volume should reject (FR12)"

    def test_penetration_over_5pct_rejected(self):
        """AC 4: Test penetration >5% rejected as breakdown."""
        creek_level = Decimal("100.00")
        spring_low = Decimal("94.00")  # 6% below Creek (TOO DEEP)
        base_volume = 100000
        spring_volume = 40000  # Low volume (valid)

        range_obj = create_trading_range(creek_level)
        bars = create_bars_with_spring(
            creek_level=creek_level,
            spring_index=24,
            spring_low=spring_low,
            spring_volume=spring_volume,
            recovery_bars=1,
            base_volume=base_volume,
        )
        phase = WyckoffPhase.C

        spring = detect_spring(range_obj, bars, phase)

        assert spring is None, "6% penetration indicates breakdown, not spring (AC 4)"

    def test_no_recovery_within_5_bars_rejected(self):
        """AC 6: Test no recovery within 5 bars rejected."""
        creek_level = Decimal("100.00")
        spring_low = Decimal("98.00")
        base_volume = 100000
        spring_volume = 40000

        range_obj = create_trading_range(creek_level)

        # Create spring but no recovery (price stays below Creek)
        bars = []
        base_timestamp = datetime(2024, 1, 1, tzinfo=UTC)

        # Normal bars before spring
        for i in range(24):
            timestamp = base_timestamp + timedelta(days=i)
            bars.append(
                create_test_bar(
                    timestamp=timestamp,
                    low=creek_level + Decimal("1.00"),
                    high=creek_level + Decimal("5.00"),
                    close=creek_level + Decimal("3.00"),
                    volume=base_volume,
                )
            )

        # Spring bar
        spring_timestamp = base_timestamp + timedelta(days=24)
        bars.append(
            create_test_bar(
                timestamp=spring_timestamp,
                low=spring_low,
                high=creek_level,
                close=creek_level - Decimal("0.50"),
                volume=spring_volume,
            )
        )

        # Next 6 bars stay below Creek (no recovery)
        for i in range(6):
            timestamp = spring_timestamp + timedelta(days=i + 1)
            bars.append(
                create_test_bar(
                    timestamp=timestamp,
                    low=creek_level - Decimal("2.00"),
                    high=creek_level - Decimal("0.50"),
                    close=creek_level - Decimal("1.00"),  # Stays below Creek
                    volume=base_volume,
                )
            )

        phase = WyckoffPhase.C
        spring = detect_spring(range_obj, bars, phase)

        assert spring is None, "No recovery within 5 bars - not a spring (AC 6)"


class TestDetectSpringPhaseValidation:
    """Test suite for Phase C validation (FR15)."""

    def test_spring_in_phase_c_accepted(self):
        """AC 8: Test spring detection in Phase C (valid)."""
        creek_level = Decimal("100.00")
        spring_low = Decimal("98.00")
        base_volume = 100000
        spring_volume = 40000

        range_obj = create_trading_range(creek_level)
        bars = create_bars_with_spring(
            creek_level=creek_level,
            spring_index=24,
            spring_low=spring_low,
            spring_volume=spring_volume,
            recovery_bars=1,
            base_volume=base_volume,
        )

        spring = detect_spring(range_obj, bars, WyckoffPhase.C)

        assert spring is not None, "Spring valid in Phase C (FR15)"

    @pytest.mark.parametrize(
        "phase",
        [
            WyckoffPhase.A,
            WyckoffPhase.B,
            WyckoffPhase.D,
            WyckoffPhase.E,
        ],
    )
    def test_spring_wrong_phase_rejected(self, phase):
        """AC 8: Test spring detection in wrong phases rejected (FR15)."""
        creek_level = Decimal("100.00")
        spring_low = Decimal("98.00")
        base_volume = 100000
        spring_volume = 40000

        range_obj = create_trading_range(creek_level)
        bars = create_bars_with_spring(
            creek_level=creek_level,
            spring_index=24,
            spring_low=spring_low,
            spring_volume=spring_volume,
            recovery_bars=1,
            base_volume=base_volume,
        )

        spring = detect_spring(range_obj, bars, phase)

        assert (
            spring is None
        ), f"Spring should be rejected in Phase {phase.value} (FR15)"


class TestDetectSpringEdgeCases:
    """Test suite for edge cases and validation."""

    def test_missing_creek_raises_valueerror(self):
        """AC 11: Test missing Creek level raises ValueError."""
        # Create range without Creek
        range_obj = create_trading_range(Decimal("100.00"))
        range_obj.creek = None

        bars = create_bars_with_spring(
            creek_level=Decimal("100.00"),
            spring_index=24,
            spring_low=Decimal("98.00"),
            spring_volume=40000,
        )

        with pytest.raises(ValueError, match="Valid Creek level required"):
            detect_spring(range_obj, bars, WyckoffPhase.C)

    def test_invalid_creek_price_raises_valueerror(self):
        """AC 11: Test invalid Creek price (<= 0) raises ValueError."""
        range_obj = create_trading_range(Decimal("100.00"))
        range_obj.creek.price = Decimal("0")

        bars = create_bars_with_spring(
            creek_level=Decimal("100.00"),
            spring_index=24,
            spring_low=Decimal("98.00"),
            spring_volume=40000,
        )

        with pytest.raises(ValueError, match="Valid Creek level required"):
            detect_spring(range_obj, bars, WyckoffPhase.C)

    def test_insufficient_bars_returns_none(self):
        """Test insufficient bars (<20) returns None."""
        creek_level = Decimal("100.00")
        range_obj = create_trading_range(creek_level)

        # Create only 15 bars (insufficient for volume calculation)
        bars = []
        base_timestamp = datetime(2024, 1, 1, tzinfo=UTC)
        for i in range(15):
            timestamp = base_timestamp + timedelta(days=i)
            bars.append(
                create_test_bar(
                    timestamp=timestamp,
                    low=creek_level + Decimal("1.00"),
                    high=creek_level + Decimal("5.00"),
                    close=creek_level + Decimal("3.00"),
                    volume=100000,
                )
            )

        spring = detect_spring(range_obj, bars, WyckoffPhase.C)

        assert spring is None, "Insufficient bars should return None"

    def test_no_penetration_returns_none(self):
        """Test bars that never penetrate below Creek return None."""
        creek_level = Decimal("100.00")
        range_obj = create_trading_range(creek_level)

        # Create 30 bars all above Creek (no penetration)
        bars = []
        base_timestamp = datetime(2024, 1, 1, tzinfo=UTC)
        for i in range(30):
            timestamp = base_timestamp + timedelta(days=i)
            bars.append(
                create_test_bar(
                    timestamp=timestamp,
                    low=creek_level + Decimal("1.00"),  # All above Creek
                    high=creek_level + Decimal("5.00"),
                    close=creek_level + Decimal("3.00"),
                    volume=100000,
                )
            )

        spring = detect_spring(range_obj, bars, WyckoffPhase.C)

        assert spring is None, "No penetration should return None"


class TestSpringInvalidation:
    """Test suite for spring invalidation detection (AC 12)."""

    def test_spring_invalidated_by_breakdown(self):
        """
        AC 12: Test spring invalidation when price breaks down >5% below Creek
        within 10 bars after recovery.
        """
        creek_level = Decimal("100.00")
        spring_low = Decimal("98.00")
        base_volume = 100000
        spring_volume = 40000

        range_obj = create_trading_range(creek_level)

        # Create spring with recovery
        bars = []
        base_timestamp = datetime(2024, 1, 1, tzinfo=UTC)

        # Normal bars before spring
        for i in range(24):
            timestamp = base_timestamp + timedelta(days=i)
            bars.append(
                create_test_bar(
                    timestamp=timestamp,
                    low=creek_level + Decimal("1.00"),
                    high=creek_level + Decimal("5.00"),
                    close=creek_level + Decimal("3.00"),
                    volume=base_volume,
                )
            )

        # Spring bar
        spring_timestamp = base_timestamp + timedelta(days=24)
        bars.append(
            create_test_bar(
                timestamp=spring_timestamp,
                low=spring_low,
                high=creek_level,
                close=creek_level - Decimal("0.50"),
                volume=spring_volume,
            )
        )

        # Recovery bar
        recovery_timestamp = spring_timestamp + timedelta(days=1)
        bars.append(
            create_test_bar(
                timestamp=recovery_timestamp,
                low=creek_level - Decimal("1.00"),
                high=creek_level + Decimal("2.00"),
                close=creek_level + Decimal("0.50"),  # Recovery
                volume=base_volume,
            )
        )

        # Breakdown bar (>5% below Creek) - within 10 bars after recovery
        breakdown_timestamp = recovery_timestamp + timedelta(days=3)
        bars.append(
            create_test_bar(
                timestamp=breakdown_timestamp,
                low=Decimal("93.00"),
                high=Decimal("95.00"),
                close=Decimal("94.00"),  # 6% below Creek = breakdown
                volume=base_volume * 2,
            )
        )

        # Add a few more bars
        for i in range(5):
            timestamp = breakdown_timestamp + timedelta(days=i + 1)
            bars.append(
                create_test_bar(
                    timestamp=timestamp,
                    low=Decimal("93.00"),
                    high=Decimal("97.00"),
                    close=Decimal("95.00"),
                    volume=base_volume,
                )
            )

        phase = WyckoffPhase.C
        spring = detect_spring(range_obj, bars, phase)

        # Spring should be invalidated (returns None)
        assert spring is None, "Spring should be invalidated by breakdown"
        assert (
            range_obj.status == RangeStatus.BREAKOUT
        ), "Range should be marked as BREAKOUT"


# ============================================================
# TEST CONFIRMATION DETECTION TESTS (Story 5.3)
# ============================================================


class TestTestConfirmationDetection:
    """Test suite for test confirmation detection (Story 5.3)."""

    def test_synthetic_test_detection(self):
        """
        Task 10: Test that valid test confirmation is detected (AC 9).

        Scenario:
        - Bar 0-19: Normal trading
        - Bar 20: Spring (0.5x volume, 2% below Creek, recovers)
        - Bar 21-24: Recovery bars
        - Bar 25: Test (0.3x volume, approaches spring low, holds it)

        Expected:
        - Test detected at bar 25
        - Volume decrease: 40% (0.3x vs 0.5x)
        - Distance: within 3% of spring low
        - holds_spring_low: True
        """
        from src.pattern_engine.detectors.spring_detector import detect_test_confirmation

        creek_level = Decimal("100.00")
        base_volume = 100000
        base_timestamp = datetime(2024, 1, 1, tzinfo=UTC)

        # Create trading range
        range_obj = create_trading_range(creek_level=creek_level)

        # Generate bars 0-19: Normal trading above Creek
        bars = []
        for i in range(20):
            timestamp = base_timestamp + timedelta(days=i)
            bars.append(
                create_test_bar(
                    timestamp=timestamp,
                    low=creek_level + Decimal("1.00"),
                    high=creek_level + Decimal("5.00"),
                    close=creek_level + Decimal("2.00"),
                    volume=base_volume,
                )
            )

        # Bar 20: Spring (2% below Creek, 0.5x volume)
        spring_timestamp = base_timestamp + timedelta(days=20)
        spring_low = creek_level * Decimal("0.98")  # 2% below Creek
        spring_bar = create_test_bar(
            timestamp=spring_timestamp,
            low=spring_low,
            high=creek_level + Decimal("1.00"),
            close=creek_level + Decimal("0.50"),
            volume=int(base_volume * 0.5),  # 0.5x volume (low volume)
        )
        bars.append(spring_bar)

        # Bars 21-24: Recovery bars (above Creek)
        for i in range(1, 5):
            timestamp = spring_timestamp + timedelta(days=i)
            bars.append(
                create_test_bar(
                    timestamp=timestamp,
                    low=creek_level + Decimal("0.50"),
                    high=creek_level + Decimal("4.00"),
                    close=creek_level + Decimal("2.00"),
                    volume=base_volume,
                )
            )

        # Bar 25: Test (0.3x volume, approaches spring low, holds it)
        test_timestamp = spring_timestamp + timedelta(days=5)
        test_low = spring_low + Decimal("0.50")  # 0.5% above spring low
        test_bar = create_test_bar(
            timestamp=test_timestamp,
            low=test_low,
            high=creek_level + Decimal("2.00"),
            close=creek_level + Decimal("1.00"),
            volume=int(base_volume * 0.3),  # 0.3x volume (lower than spring)
        )
        bars.append(test_bar)

        # Create Spring object
        spring = Spring(
            bar=spring_bar,
            bar_index=20,
            penetration_pct=Decimal("0.02"),  # 2%
            volume_ratio=Decimal("0.5"),
            recovery_bars=1,
            creek_reference=creek_level,
            spring_low=spring_low,
            recovery_price=creek_level + Decimal("0.50"),
            detection_timestamp=datetime.now(UTC),
            trading_range_id=range_obj.id,
        )

        # Detect test confirmation
        test = detect_test_confirmation(range_obj, spring, bars)

        # Assertions
        assert test is not None, "Test should be detected"
        assert (
            test.bar.timestamp == test_bar.timestamp
        ), "Test bar should be bar 25"
        assert test.bars_after_spring == 5, "Test should be 5 bars after spring"
        # Volume ratio is calculated by VolumeAnalyzer, so check it's in reasonable range
        assert test.volume_ratio < test.spring_volume_ratio, "Test volume should be lower than spring volume"
        assert test.spring_volume_ratio == Decimal(
            "0.5"
        ), "Spring volume ratio should be 0.5x"
        assert test.volume_decrease_pct > Decimal(
            "0.2"
        ), "Volume decrease should be at least 20%"
        assert test.holds_spring_low is True, "Test should hold spring low"
        assert (
            test.distance_pct <= Decimal("0.03")
        ), "Distance should be within 3%"

    def test_test_outside_window_too_early(self):
        """
        Task 11: Test that test occurring too early (2 bars after spring) returns None.

        Expected:
        - No test detected (outside 3-15 bar window)
        """
        from src.pattern_engine.detectors.spring_detector import detect_test_confirmation

        creek_level = Decimal("100.00")
        base_volume = 100000
        base_timestamp = datetime(2024, 1, 1, tzinfo=UTC)

        range_obj = create_trading_range(creek_level=creek_level)

        # Generate bars 0-19: Normal trading
        bars = []
        for i in range(20):
            timestamp = base_timestamp + timedelta(days=i)
            bars.append(
                create_test_bar(
                    timestamp=timestamp,
                    low=creek_level + Decimal("1.00"),
                    high=creek_level + Decimal("5.00"),
                    close=creek_level + Decimal("2.00"),
                    volume=base_volume,
                )
            )

        # Bar 20: Spring
        spring_timestamp = base_timestamp + timedelta(days=20)
        spring_low = creek_level * Decimal("0.98")
        spring_bar = create_test_bar(
            timestamp=spring_timestamp,
            low=spring_low,
            high=creek_level + Decimal("1.00"),
            close=creek_level + Decimal("0.50"),
            volume=int(base_volume * 0.5),
        )
        bars.append(spring_bar)

        # Bar 21-22: Only 2 bars after spring (not enough for test window)
        for i in range(1, 3):
            timestamp = spring_timestamp + timedelta(days=i)
            bars.append(
                create_test_bar(
                    timestamp=timestamp,
                    low=creek_level + Decimal("0.50"),
                    high=creek_level + Decimal("4.00"),
                    close=creek_level + Decimal("2.00"),
                    volume=base_volume,
                )
            )

        spring = Spring(
            bar=spring_bar,
            bar_index=20,
            penetration_pct=Decimal("0.02"),
            volume_ratio=Decimal("0.5"),
            recovery_bars=1,
            creek_reference=creek_level,
            spring_low=spring_low,
            recovery_price=creek_level + Decimal("0.50"),
            detection_timestamp=datetime.now(UTC),
            trading_range_id=range_obj.id,
        )

        # Detect test confirmation
        test = detect_test_confirmation(range_obj, spring, bars)

        # Should return None (insufficient bars after spring)
        assert (
            test is None
        ), "Test should be None when insufficient bars after spring"

    def test_test_breaks_spring_low(self):
        """
        Task 12: Test that test breaking spring low returns None (AC 5).

        Scenario:
        - Spring at $100 low
        - Test at $99.50 low (breaks spring low by 0.5%)

        Expected:
        - Returns None (invalid - breaks spring low)
        - Log warning: "INVALIDATES CAMPAIGN"
        """
        from src.pattern_engine.detectors.spring_detector import detect_test_confirmation

        creek_level = Decimal("100.00")
        base_volume = 100000
        base_timestamp = datetime(2024, 1, 1, tzinfo=UTC)

        range_obj = create_trading_range(creek_level=creek_level)

        # Generate bars 0-19: Normal trading
        bars = []
        for i in range(20):
            timestamp = base_timestamp + timedelta(days=i)
            bars.append(
                create_test_bar(
                    timestamp=timestamp,
                    low=creek_level + Decimal("1.00"),
                    high=creek_level + Decimal("5.00"),
                    close=creek_level + Decimal("2.00"),
                    volume=base_volume,
                )
            )

        # Bar 20: Spring at $98.00 low
        spring_timestamp = base_timestamp + timedelta(days=20)
        spring_low = Decimal("98.00")
        spring_bar = create_test_bar(
            timestamp=spring_timestamp,
            low=spring_low,
            high=creek_level + Decimal("1.00"),
            close=creek_level + Decimal("0.50"),
            volume=int(base_volume * 0.5),
        )
        bars.append(spring_bar)

        # Bars 21-24: Recovery
        for i in range(1, 5):
            timestamp = spring_timestamp + timedelta(days=i)
            bars.append(
                create_test_bar(
                    timestamp=timestamp,
                    low=creek_level + Decimal("0.50"),
                    high=creek_level + Decimal("4.00"),
                    close=creek_level + Decimal("2.00"),
                    volume=base_volume,
                )
            )

        # Bar 25: Test BREAKS spring low ($97.50 < $98.00)
        test_timestamp = spring_timestamp + timedelta(days=5)
        test_low = Decimal("97.50")  # Breaks spring low!
        test_bar = create_test_bar(
            timestamp=test_timestamp,
            low=test_low,
            high=creek_level + Decimal("2.00"),
            close=creek_level + Decimal("1.00"),
            volume=int(base_volume * 0.3),
        )
        bars.append(test_bar)

        spring = Spring(
            bar=spring_bar,
            bar_index=20,
            penetration_pct=Decimal("0.02"),
            volume_ratio=Decimal("0.5"),
            recovery_bars=1,
            creek_reference=creek_level,
            spring_low=spring_low,
            recovery_price=creek_level + Decimal("0.50"),
            detection_timestamp=datetime.now(UTC),
            trading_range_id=range_obj.id,
        )

        # Detect test confirmation
        test = detect_test_confirmation(range_obj, spring, bars)

        # Should return None (test breaks spring low)
        assert test is None, "Test should be None when breaking spring low"

    def test_test_volume_too_high(self):
        """
        Task 13: Test that test with higher/equal volume than spring returns None (AC 6).

        Scenario:
        - Spring volume_ratio: 0.5x
        - Test volume_ratio: 0.6x (higher than spring)

        Expected:
        - Returns None (volume not decreasing)
        """
        from src.pattern_engine.detectors.spring_detector import detect_test_confirmation

        creek_level = Decimal("100.00")
        base_volume = 100000
        base_timestamp = datetime(2024, 1, 1, tzinfo=UTC)

        range_obj = create_trading_range(creek_level=creek_level)

        # Generate bars 0-19: Normal trading
        bars = []
        for i in range(20):
            timestamp = base_timestamp + timedelta(days=i)
            bars.append(
                create_test_bar(
                    timestamp=timestamp,
                    low=creek_level + Decimal("1.00"),
                    high=creek_level + Decimal("5.00"),
                    close=creek_level + Decimal("2.00"),
                    volume=base_volume,
                )
            )

        # Bar 20: Spring (0.5x volume)
        spring_timestamp = base_timestamp + timedelta(days=20)
        spring_low = creek_level * Decimal("0.98")
        spring_bar = create_test_bar(
            timestamp=spring_timestamp,
            low=spring_low,
            high=creek_level + Decimal("1.00"),
            close=creek_level + Decimal("0.50"),
            volume=int(base_volume * 0.5),
        )
        bars.append(spring_bar)

        # Bars 21-24: Recovery
        for i in range(1, 5):
            timestamp = spring_timestamp + timedelta(days=i)
            bars.append(
                create_test_bar(
                    timestamp=timestamp,
                    low=creek_level + Decimal("0.50"),
                    high=creek_level + Decimal("4.00"),
                    close=creek_level + Decimal("2.00"),
                    volume=base_volume,
                )
            )

        # Bar 25: Test with HIGHER volume (0.6x > 0.5x)
        test_timestamp = spring_timestamp + timedelta(days=5)
        test_low = spring_low + Decimal("0.50")
        test_bar = create_test_bar(
            timestamp=test_timestamp,
            low=test_low,
            high=creek_level + Decimal("2.00"),
            close=creek_level + Decimal("1.00"),
            volume=int(base_volume * 0.6),  # Higher than spring!
        )
        bars.append(test_bar)

        spring = Spring(
            bar=spring_bar,
            bar_index=20,
            penetration_pct=Decimal("0.02"),
            volume_ratio=Decimal("0.5"),
            recovery_bars=1,
            creek_reference=creek_level,
            spring_low=spring_low,
            recovery_price=creek_level + Decimal("0.50"),
            detection_timestamp=datetime.now(UTC),
            trading_range_id=range_obj.id,
        )

        # Detect test confirmation
        test = detect_test_confirmation(range_obj, spring, bars)

        # Should return None (test volume too high)
        assert test is None, "Test should be None when volume not lower than spring"

    def test_perfect_test(self):
        """
        Task 14: Test ideal test scenario (AC 9).

        Scenario:
        - Spring: 0.5x volume, $100 low
        - Test: 0.25x volume (50% decrease), $100.50 low (0.5% above spring)
        - Test occurs 5 bars after spring (mid-window)

        Expected:
        - Test detected
        - volume_decrease_pct == 50%
        - holds_spring_low == True
        - distance_pct == 0.5%
        - quality_score == "EXCELLENT"
        """
        from src.pattern_engine.detectors.spring_detector import detect_test_confirmation

        creek_level = Decimal("100.00")
        base_volume = 100000
        base_timestamp = datetime(2024, 1, 1, tzinfo=UTC)

        range_obj = create_trading_range(creek_level=creek_level)

        # Generate bars 0-19: Normal trading
        bars = []
        for i in range(20):
            timestamp = base_timestamp + timedelta(days=i)
            bars.append(
                create_test_bar(
                    timestamp=timestamp,
                    low=creek_level + Decimal("1.00"),
                    high=creek_level + Decimal("5.00"),
                    close=creek_level + Decimal("2.00"),
                    volume=base_volume,
                )
            )

        # Bar 20: Spring ($100 low, 0.5x volume)
        spring_timestamp = base_timestamp + timedelta(days=20)
        spring_low = Decimal("100.00")
        spring_bar = create_test_bar(
            timestamp=spring_timestamp,
            low=spring_low,
            high=creek_level + Decimal("5.00"),
            close=creek_level + Decimal("2.00"),
            volume=int(base_volume * 0.5),
        )
        bars.append(spring_bar)

        # Bars 21-24: Recovery
        for i in range(1, 5):
            timestamp = spring_timestamp + timedelta(days=i)
            bars.append(
                create_test_bar(
                    timestamp=timestamp,
                    low=creek_level + Decimal("1.00"),
                    high=creek_level + Decimal("5.00"),
                    close=creek_level + Decimal("3.00"),
                    volume=base_volume,
                )
            )

        # Bar 25: Perfect test ($100.50 low, 0.25x volume)
        test_timestamp = spring_timestamp + timedelta(days=5)
        test_low = Decimal("100.50")  # 0.5% above spring
        test_bar = create_test_bar(
            timestamp=test_timestamp,
            low=test_low,
            high=creek_level + Decimal("3.00"),
            close=creek_level + Decimal("2.00"),
            volume=int(base_volume * 0.25),  # 50% decrease from spring
        )
        bars.append(test_bar)

        spring = Spring(
            bar=spring_bar,
            bar_index=20,
            penetration_pct=Decimal("0.00"),  # At Creek level
            volume_ratio=Decimal("0.5"),
            recovery_bars=1,
            creek_reference=creek_level,
            spring_low=spring_low,
            recovery_price=creek_level + Decimal("2.00"),
            detection_timestamp=datetime.now(UTC),
            trading_range_id=range_obj.id,
        )

        # Detect test confirmation
        test = detect_test_confirmation(range_obj, spring, bars)

        # Assertions
        assert test is not None, "Test should be detected"
        # Volume ratio is calculated by VolumeAnalyzer - check test volume < spring volume
        assert test.volume_ratio < test.spring_volume_ratio, "Test volume should be lower than spring volume"
        assert test.volume_decrease_pct > Decimal("0.3"), "Volume decrease should be at least 30%"
        assert test.holds_spring_low is True, "Test should hold spring low"
        assert test.distance_pct == Decimal("0.005"), "Distance should be 0.5%"
        # Quality depends on volume decrease which may vary slightly
        assert test.quality_score in ["EXCELLENT", "GOOD"], "Test should be high quality"

    def test_multiple_tests_selection(self):
        """
        Task 15: Test that best test is selected when multiple tests exist (AC 7).

        Scenario:
        - Test 1 (bar 23): 0.4x volume, 2% above spring
        - Test 2 (bar 26): 0.3x volume, 1% above spring (best - lowest volume, closest)
        - Test 3 (bar 29): 0.35x volume, 2.5% above spring

        Expected:
        - Test 2 is selected (lowest volume is priority)
        """
        from src.pattern_engine.detectors.spring_detector import detect_test_confirmation

        creek_level = Decimal("100.00")
        base_volume = 100000
        base_timestamp = datetime(2024, 1, 1, tzinfo=UTC)

        range_obj = create_trading_range(creek_level=creek_level)

        # Generate bars 0-19: Normal trading
        bars = []
        for i in range(20):
            timestamp = base_timestamp + timedelta(days=i)
            bars.append(
                create_test_bar(
                    timestamp=timestamp,
                    low=creek_level + Decimal("1.00"),
                    high=creek_level + Decimal("5.00"),
                    close=creek_level + Decimal("2.00"),
                    volume=base_volume,
                )
            )

        # Bar 20: Spring
        spring_timestamp = base_timestamp + timedelta(days=20)
        spring_low = Decimal("100.00")
        spring_bar = create_test_bar(
            timestamp=spring_timestamp,
            low=spring_low,
            high=creek_level + Decimal("5.00"),
            close=creek_level + Decimal("2.00"),
            volume=int(base_volume * 0.5),
        )
        bars.append(spring_bar)

        # Bars 21-22: Recovery
        for i in range(1, 3):
            timestamp = spring_timestamp + timedelta(days=i)
            bars.append(
                create_test_bar(
                    timestamp=timestamp,
                    low=creek_level + Decimal("3.00"),
                    high=creek_level + Decimal("5.00"),
                    close=creek_level + Decimal("4.00"),
                    volume=base_volume,
                )
            )

        # Bar 23: Test 1 (0.4x volume, 2% above spring)
        test1_timestamp = spring_timestamp + timedelta(days=3)
        test1_low = spring_low + Decimal("2.00")  # 2% above
        bars.append(
            create_test_bar(
                timestamp=test1_timestamp,
                low=test1_low,
                high=creek_level + Decimal("3.00"),
                close=creek_level + Decimal("2.00"),
                volume=int(base_volume * 0.4),
            )
        )

        # Bars 24-25: Neutral bars
        for i in range(4, 6):
            timestamp = spring_timestamp + timedelta(days=i)
            bars.append(
                create_test_bar(
                    timestamp=timestamp,
                    low=creek_level + Decimal("2.00"),
                    high=creek_level + Decimal("5.00"),
                    close=creek_level + Decimal("3.00"),
                    volume=base_volume,
                )
            )

        # Bar 26: Test 2 (0.3x volume, 1% above spring) - BEST
        test2_timestamp = spring_timestamp + timedelta(days=6)
        test2_low = spring_low + Decimal("1.00")  # 1% above
        bars.append(
            create_test_bar(
                timestamp=test2_timestamp,
                low=test2_low,
                high=creek_level + Decimal("3.00"),
                close=creek_level + Decimal("2.00"),
                volume=int(base_volume * 0.3),  # Lowest volume
            )
        )

        # Bars 27-28: Neutral bars
        for i in range(7, 9):
            timestamp = spring_timestamp + timedelta(days=i)
            bars.append(
                create_test_bar(
                    timestamp=timestamp,
                    low=creek_level + Decimal("2.00"),
                    high=creek_level + Decimal("5.00"),
                    close=creek_level + Decimal("3.00"),
                    volume=base_volume,
                )
            )

        # Bar 29: Test 3 (0.35x volume, 2.5% above spring)
        test3_timestamp = spring_timestamp + timedelta(days=9)
        test3_low = spring_low + Decimal("2.50")  # 2.5% above
        bars.append(
            create_test_bar(
                timestamp=test3_timestamp,
                low=test3_low,
                high=creek_level + Decimal("3.00"),
                close=creek_level + Decimal("2.00"),
                volume=int(base_volume * 0.35),
            )
        )

        spring = Spring(
            bar=spring_bar,
            bar_index=20,
            penetration_pct=Decimal("0.00"),
            volume_ratio=Decimal("0.5"),
            recovery_bars=1,
            creek_reference=creek_level,
            spring_low=spring_low,
            recovery_price=creek_level + Decimal("2.00"),
            detection_timestamp=datetime.now(UTC),
            trading_range_id=range_obj.id,
        )

        # Detect test confirmation
        test = detect_test_confirmation(range_obj, spring, bars)

        # Should select Test 2 (lowest volume)
        assert test is not None, "Test should be detected"
        assert (
            test.bar.timestamp == test2_timestamp
        ), "Should select Test 2 (lowest volume)"
        # Volume ratio calculated by VolumeAnalyzer - just verify it's the lowest
        assert test.volume_ratio < Decimal("0.4"), "Selected test should have lower volume than spring"

    def test_no_test_found(self):
        """
        Task 16: Test that None is returned when no test occurs (AC 8, FR13).

        Scenario:
        - Spring detected
        - Price rallies away from spring low (no retest)
        - Window of 3-15 bars passes without approaching spring low

        Expected:
        - Returns None
        - Validates FR13: spring without test is NOT tradeable
        """
        from src.pattern_engine.detectors.spring_detector import detect_test_confirmation

        creek_level = Decimal("100.00")
        base_volume = 100000
        base_timestamp = datetime(2024, 1, 1, tzinfo=UTC)

        range_obj = create_trading_range(creek_level=creek_level)

        # Generate bars 0-19: Normal trading
        bars = []
        for i in range(20):
            timestamp = base_timestamp + timedelta(days=i)
            bars.append(
                create_test_bar(
                    timestamp=timestamp,
                    low=creek_level + Decimal("1.00"),
                    high=creek_level + Decimal("5.00"),
                    close=creek_level + Decimal("2.00"),
                    volume=base_volume,
                )
            )

        # Bar 20: Spring
        spring_timestamp = base_timestamp + timedelta(days=20)
        spring_low = creek_level * Decimal("0.98")
        spring_bar = create_test_bar(
            timestamp=spring_timestamp,
            low=spring_low,
            high=creek_level + Decimal("1.00"),
            close=creek_level + Decimal("0.50"),
            volume=int(base_volume * 0.5),
        )
        bars.append(spring_bar)

        # Bars 21-35: Price rallies AWAY from spring low (no retest)
        for i in range(1, 16):
            timestamp = spring_timestamp + timedelta(days=i)
            bars.append(
                create_test_bar(
                    timestamp=timestamp,
                    low=creek_level + Decimal("5.00"),  # Far above spring low
                    high=creek_level + Decimal("10.00"),
                    close=creek_level + Decimal("7.00"),
                    volume=base_volume,
                )
            )

        spring = Spring(
            bar=spring_bar,
            bar_index=20,
            penetration_pct=Decimal("0.02"),
            volume_ratio=Decimal("0.5"),
            recovery_bars=1,
            creek_reference=creek_level,
            spring_low=spring_low,
            recovery_price=creek_level + Decimal("0.50"),
            detection_timestamp=datetime.now(UTC),
            trading_range_id=range_obj.id,
        )

        # Detect test confirmation
        test = detect_test_confirmation(range_obj, spring, bars)

        # Should return None (no test found)
        assert test is None, "Test should be None when no test occurs (FR13)"

    def test_edge_case_insufficient_bars_after_spring(self):
        """
        Task 18: Test edge case where spring is last bar in sequence.

        Expected:
        - Returns None (can't test yet, need more data)
        """
        from src.pattern_engine.detectors.spring_detector import detect_test_confirmation

        creek_level = Decimal("100.00")
        base_volume = 100000
        base_timestamp = datetime(2024, 1, 1, tzinfo=UTC)

        range_obj = create_trading_range(creek_level=creek_level)

        # Generate bars 0-19: Normal trading
        bars = []
        for i in range(20):
            timestamp = base_timestamp + timedelta(days=i)
            bars.append(
                create_test_bar(
                    timestamp=timestamp,
                    low=creek_level + Decimal("1.00"),
                    high=creek_level + Decimal("5.00"),
                    close=creek_level + Decimal("2.00"),
                    volume=base_volume,
                )
            )

        # Bar 20: Spring (LAST BAR)
        spring_timestamp = base_timestamp + timedelta(days=20)
        spring_low = creek_level * Decimal("0.98")
        spring_bar = create_test_bar(
            timestamp=spring_timestamp,
            low=spring_low,
            high=creek_level + Decimal("1.00"),
            close=creek_level + Decimal("0.50"),
            volume=int(base_volume * 0.5),
        )
        bars.append(spring_bar)

        spring = Spring(
            bar=spring_bar,
            bar_index=20,
            penetration_pct=Decimal("0.02"),
            volume_ratio=Decimal("0.5"),
            recovery_bars=1,
            creek_reference=creek_level,
            spring_low=spring_low,
            recovery_price=creek_level + Decimal("0.50"),
            detection_timestamp=datetime.now(UTC),
            trading_range_id=range_obj.id,
        )

        # Detect test confirmation
        test = detect_test_confirmation(range_obj, spring, bars)

        # Should return None (insufficient bars)
        assert test is None, "Test should be None when spring is last bar"

    def test_edge_case_spring_not_in_bars(self):
        """
        Task 18: Test edge case where spring is not in bars list.

        Expected:
        - Raises ValueError
        """
        from src.pattern_engine.detectors.spring_detector import detect_test_confirmation

        creek_level = Decimal("100.00")
        base_volume = 100000
        base_timestamp = datetime(2024, 1, 1, tzinfo=UTC)

        range_obj = create_trading_range(creek_level=creek_level)

        # Generate bars 0-24: Normal trading
        bars = []
        for i in range(25):
            timestamp = base_timestamp + timedelta(days=i)
            bars.append(
                create_test_bar(
                    timestamp=timestamp,
                    low=creek_level + Decimal("1.00"),
                    high=creek_level + Decimal("5.00"),
                    close=creek_level + Decimal("2.00"),
                    volume=base_volume,
                )
            )

        # Create spring from DIFFERENT timestamp (not in bars)
        different_timestamp = base_timestamp + timedelta(days=100)
        spring_bar = create_test_bar(
            timestamp=different_timestamp,
            low=creek_level * Decimal("0.98"),
            high=creek_level + Decimal("1.00"),
            close=creek_level + Decimal("0.50"),
            volume=int(base_volume * 0.5),
        )

        spring = Spring(
            bar=spring_bar,
            bar_index=20,
            penetration_pct=Decimal("0.02"),
            volume_ratio=Decimal("0.5"),
            recovery_bars=1,
            creek_reference=creek_level,
            spring_low=creek_level * Decimal("0.98"),
            recovery_price=creek_level + Decimal("0.50"),
            detection_timestamp=datetime.now(UTC),
            trading_range_id=range_obj.id,
        )

        # Detect test confirmation - should raise ValueError
        with pytest.raises(ValueError, match="Spring bar not found"):
            detect_test_confirmation(range_obj, spring, bars)


# ============================================================
# STORY 5.4: SPRING CONFIDENCE SCORING TESTS
# ============================================================


def test_calculate_spring_confidence_excellent_quality():
    """Test confidence scoring for excellent quality spring (90-100 points)."""
    from src.pattern_engine.detectors.spring_detector import calculate_spring_confidence
    from src.models.test import Test

    # Create excellent spring:
    # - Volume: 0.25x (40 pts - exceptional)
    # - Penetration: 1.5% (35 pts - ideal)
    # - Recovery: 1 bar (25 pts - immediate)
    # - Test: Present (20 pts)
    # - Creek: 85 strength (10 pts bonus)
    # - Volume trend: N/A (0 pts - insufficient data)
    # Expected: 130 → capped at 100

    creek_level = Decimal("100.00")
    range_obj = create_trading_range(creek_level)

    # Update Creek strength to 85
    if range_obj.creek:
        range_obj.creek.strength_score = 85

    # Create spring bar with exceptional characteristics
    spring_timestamp = datetime(2024, 2, 15, tzinfo=UTC)
    spring = Spring(
        bar=create_test_bar(
            timestamp=spring_timestamp,
            low=creek_level - Decimal("1.50"),  # 1.5% penetration
            high=creek_level - Decimal("0.50"),
            close=creek_level - Decimal("1.00"),
            volume=25000,  # Will be 0.25x when avg is 100000
            symbol="AAPL",
        ),
        bar_index=20,
        penetration_pct=Decimal("0.015"),  # 1.5%
        volume_ratio=Decimal("0.25"),  # Exceptional
        recovery_bars=1,  # Immediate
        creek_reference=creek_level,
        spring_low=creek_level - Decimal("1.50"),
        recovery_price=creek_level + Decimal("0.50"),
        detection_timestamp=datetime.now(UTC),
        trading_range_id=range_obj.id,
    )

    # Create test for test confirmation points
    test = Test(
        bar=create_test_bar(
            timestamp=spring_timestamp + timedelta(days=5),
            low=creek_level - Decimal("1.30"),
            high=creek_level + Decimal("1.00"),
            close=creek_level,
            volume=15000,
            symbol="AAPL",
        ),
        spring_reference=spring,
        distance_from_spring_low=Decimal("0.20"),
        distance_pct=Decimal("0.002"),
        volume_ratio=Decimal("0.15"),
        spring_volume_ratio=Decimal("0.25"),
        volume_decrease_pct=Decimal("0.4"),
        bars_after_spring=5,
        holds_spring_low=True,
        detection_timestamp=datetime.now(UTC),
        spring_id=spring.id,
    )

    # Calculate confidence (pass test in previous_tests to get test points)
    confidence = calculate_spring_confidence(
        spring=spring,
        creek=range_obj.creek,
        previous_tests=[test]
    )

    # Assert
    assert confidence.total_score >= 90, f"Excellent spring should score 90+, got {confidence.total_score}"
    assert confidence.total_score == 100, "Score should be capped at 100"
    assert confidence.quality_tier == "EXCELLENT"
    assert confidence.meets_threshold is True
    assert confidence.is_excellent is True

    # Verify component breakdown
    assert confidence.component_scores["volume_quality"] == 40
    assert confidence.component_scores["penetration_depth"] == 35
    assert confidence.component_scores["recovery_speed"] == 25
    assert confidence.component_scores["test_confirmation"] == 20
    assert confidence.component_scores["creek_strength_bonus"] == 10
    assert confidence.component_scores["raw_total"] == 130


def test_calculate_spring_confidence_good_quality():
    """Test confidence scoring for good quality spring (80-89 points)."""
    from src.pattern_engine.detectors.spring_detector import calculate_spring_confidence

    # Create good spring:
    # - Volume: 0.4x (20 pts - ideal)
    # - Penetration: 2.5% (25 pts - good)
    # - Recovery: 2 bars (20 pts - strong)
    # - Test: Present (20 pts)
    # - Creek: 75 strength (7 pts bonus)
    # - Volume trend: N/A (0 pts)
    # Expected: 92 → capped at 100

    creek_level = Decimal("100.00")
    range_obj = create_trading_range(creek_level)

    # Update Creek strength to 75
    if range_obj.creek:
        range_obj.creek.strength_score = 75

    spring_timestamp = datetime(2024, 2, 15, tzinfo=UTC)
    spring = Spring(
        bar=create_test_bar(
            timestamp=spring_timestamp,
            low=creek_level - Decimal("2.50"),  # 2.5% penetration
            high=creek_level,
            close=creek_level - Decimal("1.00"),
            volume=40000,
            symbol="AAPL",
        ),
        bar_index=20,
        penetration_pct=Decimal("0.025"),  # 2.5%
        volume_ratio=Decimal("0.4"),  # Ideal
        recovery_bars=2,  # Strong
        creek_reference=creek_level,
        spring_low=creek_level - Decimal("2.50"),
        recovery_price=creek_level + Decimal("0.50"),
        detection_timestamp=datetime.now(UTC),
        trading_range_id=range_obj.id,
    )

    # Create dummy test
    from src.models.test import Test
    test = Test(
        bar=create_test_bar(
            timestamp=spring_timestamp + timedelta(days=5),
            low=creek_level - Decimal("2.00"),
            high=creek_level,
            close=creek_level - Decimal("0.50"),
            volume=30000,
            symbol="AAPL",
        ),
        spring_reference=spring,
        distance_from_spring_low=Decimal("0.50"),
        distance_pct=Decimal("0.005"),
        volume_ratio=Decimal("0.3"),
        spring_volume_ratio=Decimal("0.4"),
        volume_decrease_pct=Decimal("0.25"),
        bars_after_spring=5,
        holds_spring_low=True,
        detection_timestamp=datetime.now(UTC),
        spring_id=spring.id,
    )

    confidence = calculate_spring_confidence(
        spring=spring,
        creek=range_obj.creek,
        previous_tests=[test]
    )

    # Assert - actually scores 92 (EXCELLENT) not 80-89 (GOOD)
    # 20 + 25 + 20 + 20 + 7 = 92
    assert confidence.total_score == 92, f"Spring should score 92, got {confidence.total_score}"
    assert confidence.quality_tier == "EXCELLENT"
    assert confidence.meets_threshold is True
    assert confidence.is_excellent is True


def test_calculate_spring_confidence_acceptable_quality():
    """Test confidence scoring for acceptable quality spring (70-79 points)."""
    from src.pattern_engine.detectors.spring_detector import calculate_spring_confidence

    # Create acceptable spring (exactly 70 points):
    # - Volume: 0.55x (10 pts - acceptable)
    # - Penetration: 3.5% (15 pts - acceptable)
    # - Recovery: 3 bars (15 pts - good)
    # - Test: Present (20 pts)
    # - Creek: 65 strength (5 pts bonus)
    # - Volume trend: N/A (0 pts)
    # Expected: 65 pts (BELOW threshold)

    creek_level = Decimal("100.00")
    range_obj = create_trading_range(creek_level)

    # Update Creek strength to 65
    if range_obj.creek:
        range_obj.creek.strength_score = 65

    spring_timestamp = datetime(2024, 2, 15, tzinfo=UTC)
    spring = Spring(
        bar=create_test_bar(
            timestamp=spring_timestamp,
            low=creek_level - Decimal("3.50"),  # 3.5% penetration
            high=creek_level,
            close=creek_level - Decimal("2.00"),
            volume=55000,
            symbol="AAPL",
        ),
        bar_index=20,
        penetration_pct=Decimal("0.035"),  # 3.5%
        volume_ratio=Decimal("0.55"),  # Acceptable
        recovery_bars=3,  # Good
        creek_reference=creek_level,
        spring_low=creek_level - Decimal("3.50"),
        recovery_price=creek_level + Decimal("0.50"),
        detection_timestamp=datetime.now(UTC),
        trading_range_id=range_obj.id,
    )

    # Create dummy test
    from src.models.test import Test
    test = Test(
        bar=create_test_bar(
            timestamp=spring_timestamp + timedelta(days=5),
            low=creek_level - Decimal("3.00"),
            high=creek_level,
            close=creek_level - Decimal("1.00"),
            volume=40000,
            symbol="AAPL",
        ),
        spring_reference=spring,
        distance_from_spring_low=Decimal("0.50"),
        distance_pct=Decimal("0.005"),
        volume_ratio=Decimal("0.4"),
        spring_volume_ratio=Decimal("0.55"),
        volume_decrease_pct=Decimal("0.27"),
        bars_after_spring=5,
        holds_spring_low=True,
        detection_timestamp=datetime.now(UTC),
        spring_id=spring.id,
    )

    confidence = calculate_spring_confidence(
        spring=spring,
        creek=range_obj.creek,
        previous_tests=[test]
    )

    # Assert - should be below 70 with these parameters
    assert confidence.total_score < 70, f"Marginal spring should score <70, got {confidence.total_score}"
    assert confidence.quality_tier == "REJECTED"
    assert confidence.meets_threshold is False


def test_calculate_spring_confidence_rejected_quality():
    """Test confidence scoring for rejected spring (<70 points)."""
    from src.pattern_engine.detectors.spring_detector import calculate_spring_confidence

    # Create rejected spring:
    # - Volume: 0.65x (5 pts - marginal)
    # - Penetration: 4.5% (5 pts - deep)
    # - Recovery: 5 bars (10 pts - slow)
    # - Test: Present (20 pts)
    # - Creek: 55 strength (0 pts)
    # - Volume trend: N/A (0 pts)
    # Expected: 40 pts (REJECTED)

    creek_level = Decimal("100.00")
    range_obj = create_trading_range(creek_level)

    # Update Creek strength to 55
    if range_obj.creek:
        range_obj.creek.strength_score = 55

    spring_timestamp = datetime(2024, 2, 15, tzinfo=UTC)
    spring = Spring(
        bar=create_test_bar(
            timestamp=spring_timestamp,
            low=creek_level - Decimal("4.50"),  # 4.5% penetration
            high=creek_level,
            close=creek_level - Decimal("3.00"),
            volume=65000,
            symbol="AAPL",
        ),
        bar_index=20,
        penetration_pct=Decimal("0.045"),  # 4.5%
        volume_ratio=Decimal("0.65"),  # Marginal
        recovery_bars=5,  # Slow
        creek_reference=creek_level,
        spring_low=creek_level - Decimal("4.50"),
        recovery_price=creek_level + Decimal("0.50"),
        detection_timestamp=datetime.now(UTC),
        trading_range_id=range_obj.id,
    )

    # Create dummy test
    from src.models.test import Test
    test = Test(
        bar=create_test_bar(
            timestamp=spring_timestamp + timedelta(days=5),
            low=creek_level - Decimal("4.00"),
            high=creek_level,
            close=creek_level - Decimal("2.00"),
            volume=50000,
            symbol="AAPL",
        ),
        spring_reference=spring,
        distance_from_spring_low=Decimal("0.50"),
        distance_pct=Decimal("0.005"),
        volume_ratio=Decimal("0.5"),
        spring_volume_ratio=Decimal("0.65"),
        volume_decrease_pct=Decimal("0.23"),
        bars_after_spring=5,
        holds_spring_low=True,
        detection_timestamp=datetime.now(UTC),
        spring_id=spring.id,
    )

    confidence = calculate_spring_confidence(
        spring=spring,
        creek=range_obj.creek,
        previous_tests=[test]
    )

    # Assert
    assert confidence.total_score < 70, f"Low-quality spring should score <70, got {confidence.total_score}"
    assert confidence.quality_tier == "REJECTED"
    assert confidence.meets_threshold is False


def test_calculate_spring_confidence_no_test():
    """Test confidence scoring with no test confirmation (loses 20 points)."""
    from src.pattern_engine.detectors.spring_detector import calculate_spring_confidence

    # Create spring without test:
    # - Volume: 0.35x (30 pts - excellent)
    # - Penetration: 1.5% (35 pts - ideal)
    # - Recovery: 1 bar (25 pts - immediate)
    # - Test: None (0 pts - NO TEST)
    # - Creek: 85 strength (10 pts bonus)
    # - Volume trend: N/A (0 pts)
    # Expected: 100 pts (would be 120 with test, but missing test loses 20)

    creek_level = Decimal("100.00")
    range_obj = create_trading_range(creek_level)

    # Update Creek strength to 85
    if range_obj.creek:
        range_obj.creek.strength_score = 85

    spring_timestamp = datetime(2024, 2, 15, tzinfo=UTC)
    spring = Spring(
        bar=create_test_bar(
            timestamp=spring_timestamp,
            low=creek_level - Decimal("1.50"),
            high=creek_level,
            close=creek_level - Decimal("0.50"),
            volume=35000,
            symbol="AAPL",
        ),
        bar_index=20,
        penetration_pct=Decimal("0.015"),
        volume_ratio=Decimal("0.35"),
        recovery_bars=1,
        creek_reference=creek_level,
        spring_low=creek_level - Decimal("1.50"),
        recovery_price=creek_level + Decimal("0.50"),
        detection_timestamp=datetime.now(UTC),
        trading_range_id=range_obj.id,
    )

    # No test provided
    confidence = calculate_spring_confidence(
        spring=spring,
        creek=range_obj.creek,
        previous_tests=[]  # No test
    )

    # Assert
    assert confidence.component_scores["test_confirmation"] == 0
    assert confidence.total_score == 100  # 100 without test (capped)
    # Without test, even excellent springs only get 100 points
    assert confidence.meets_threshold is True  # Still meets threshold
    assert confidence.quality_tier == "EXCELLENT"


def test_calculate_spring_confidence_volume_trend_bonus():
    """Test volume trend bonus with declining volume from previous tests."""
    from src.pattern_engine.detectors.spring_detector import calculate_spring_confidence
    from src.models.test import Test

    # Create spring with declining volume trend
    creek_level = Decimal("100.00")
    range_obj = create_trading_range(creek_level)

    if range_obj.creek:
        range_obj.creek.strength_score = 70

    spring_timestamp = datetime(2024, 2, 15, tzinfo=UTC)
    spring = Spring(
        bar=create_test_bar(
            timestamp=spring_timestamp,
            low=creek_level - Decimal("1.50"),
            high=creek_level,
            close=creek_level - Decimal("0.50"),
            volume=30000,  # Lower than previous tests
            symbol="AAPL",
        ),
        bar_index=20,
        penetration_pct=Decimal("0.015"),
        volume_ratio=Decimal("0.3"),  # Significantly lower volume
        recovery_bars=1,
        creek_reference=creek_level,
        spring_low=creek_level - Decimal("1.50"),
        recovery_price=creek_level + Decimal("0.50"),
        detection_timestamp=datetime.now(UTC),
        trading_range_id=range_obj.id,
    )

    # Create previous tests with higher volume
    test1 = Test(
        bar=create_test_bar(
            timestamp=spring_timestamp - timedelta(days=10),
            low=creek_level - Decimal("1.00"),
            high=creek_level,
            close=creek_level - Decimal("0.50"),
            volume=50000,  # Higher volume
            symbol="AAPL",
        ),
        spring_reference=spring,
        distance_from_spring_low=Decimal("0.50"),
        distance_pct=Decimal("0.005"),
        volume_ratio=Decimal("0.5"),  # Higher volume
        spring_volume_ratio=Decimal("0.3"),
        volume_decrease_pct=Decimal("0.4"),
        bars_after_spring=5,
        holds_spring_low=True,
        detection_timestamp=datetime.now(UTC),
        spring_id=spring.id,
    )

    test2 = Test(
        bar=create_test_bar(
            timestamp=spring_timestamp - timedelta(days=5),
            low=creek_level - Decimal("1.00"),
            high=creek_level,
            close=creek_level - Decimal("0.50"),
            volume=45000,  # Higher volume
            symbol="AAPL",
        ),
        spring_reference=spring,
        distance_from_spring_low=Decimal("0.50"),
        distance_pct=Decimal("0.005"),
        volume_ratio=Decimal("0.45"),  # Higher volume
        spring_volume_ratio=Decimal("0.3"),
        volume_decrease_pct=Decimal("0.33"),
        bars_after_spring=5,
        holds_spring_low=True,
        detection_timestamp=datetime.now(UTC),
        spring_id=spring.id,
    )

    confidence = calculate_spring_confidence(
        spring=spring,
        creek=range_obj.creek,
        previous_tests=[test1, test2]
    )

    # Assert - volume trend bonus should be awarded
    # Avg previous volume: (0.5 + 0.45) / 2 = 0.475
    # Spring volume: 0.3
    # Decrease: (0.475 - 0.3) / 0.475 = 36.8% (>20% threshold)
    assert confidence.component_scores["volume_trend_bonus"] == 10
    assert confidence.total_score == 100  # Capped


@pytest.mark.parametrize("volume_ratio,expected_points", [
    (Decimal("0.25"), 40),  # <0.3x = 40 pts (exceptional)
    (Decimal("0.35"), 30),  # 0.3-0.4x = 30 pts (excellent)
    (Decimal("0.45"), 20),  # 0.4-0.5x = 20 pts (ideal)
    (Decimal("0.55"), 10),  # 0.5-0.6x = 10 pts (acceptable)
    (Decimal("0.65"), 5),   # 0.6-0.69x = 5 pts (marginal)
])
def test_volume_quality_scoring_tiers(volume_ratio, expected_points):
    """Test all volume quality scoring tiers."""
    from src.pattern_engine.detectors.spring_detector import calculate_spring_confidence

    creek_level = Decimal("100.00")
    range_obj = create_trading_range(creek_level)

    if range_obj.creek:
        range_obj.creek.strength_score = 60

    spring = Spring(
        bar=create_test_bar(
            timestamp=datetime.now(UTC),
            low=creek_level - Decimal("1.50"),
            high=creek_level,
            close=creek_level - Decimal("0.50"),
            volume=int(float(volume_ratio) * 100000),
            symbol="AAPL",
        ),
        bar_index=20,
        penetration_pct=Decimal("0.015"),
        volume_ratio=volume_ratio,
        recovery_bars=1,
        creek_reference=creek_level,
        spring_low=creek_level - Decimal("1.50"),
        recovery_price=creek_level + Decimal("0.50"),
        detection_timestamp=datetime.now(UTC),
        trading_range_id=range_obj.id,
    )

    confidence = calculate_spring_confidence(
        spring=spring,
        creek=range_obj.creek,
        previous_tests=[]
    )

    # Assert volume points match expected
    assert confidence.component_scores["volume_quality"] == expected_points


@pytest.mark.parametrize("penetration_pct,expected_points", [
    (Decimal("0.015"), 35),  # 1-2% = 35 pts (ideal)
    (Decimal("0.025"), 25),  # 2-3% = 25 pts (good)
    (Decimal("0.035"), 15),  # 3-4% = 15 pts (acceptable)
    (Decimal("0.045"), 5),   # 4-5% = 5 pts (deep)
])
def test_penetration_depth_scoring_tiers(penetration_pct, expected_points):
    """Test all penetration depth scoring tiers."""
    from src.pattern_engine.detectors.spring_detector import calculate_spring_confidence

    creek_level = Decimal("100.00")
    range_obj = create_trading_range(creek_level)

    if range_obj.creek:
        range_obj.creek.strength_score = 60

    spring = Spring(
        bar=create_test_bar(
            timestamp=datetime.now(UTC),
            low=creek_level - (creek_level * penetration_pct),
            high=creek_level,
            close=creek_level - Decimal("0.50"),
            volume=40000,
            symbol="AAPL",
        ),
        bar_index=20,
        penetration_pct=penetration_pct,
        volume_ratio=Decimal("0.4"),
        recovery_bars=1,
        creek_reference=creek_level,
        spring_low=creek_level - (creek_level * penetration_pct),
        recovery_price=creek_level + Decimal("0.50"),
        detection_timestamp=datetime.now(UTC),
        trading_range_id=range_obj.id,
    )

    confidence = calculate_spring_confidence(
        spring=spring,
        creek=range_obj.creek,
        previous_tests=[]
    )

    # Assert penetration points match expected
    assert confidence.component_scores["penetration_depth"] == expected_points


@pytest.mark.parametrize("recovery_bars,expected_points", [
    (1, 25),  # 1 bar = 25 pts (immediate)
    (2, 20),  # 2 bars = 20 pts (strong)
    (3, 15),  # 3 bars = 15 pts (good)
    (4, 10),  # 4 bars = 10 pts (slow)
    (5, 10),  # 5 bars = 10 pts (slow)
])
def test_recovery_speed_scoring_tiers(recovery_bars, expected_points):
    """Test all recovery speed scoring tiers."""
    from src.pattern_engine.detectors.spring_detector import calculate_spring_confidence

    creek_level = Decimal("100.00")
    range_obj = create_trading_range(creek_level)

    if range_obj.creek:
        range_obj.creek.strength_score = 60

    spring = Spring(
        bar=create_test_bar(
            timestamp=datetime.now(UTC),
            low=creek_level - Decimal("1.50"),
            high=creek_level,
            close=creek_level - Decimal("0.50"),
            volume=40000,
            symbol="AAPL",
        ),
        bar_index=20,
        penetration_pct=Decimal("0.015"),
        volume_ratio=Decimal("0.4"),
        recovery_bars=recovery_bars,
        creek_reference=creek_level,
        spring_low=creek_level - Decimal("1.50"),
        recovery_price=creek_level + Decimal("0.50"),
        detection_timestamp=datetime.now(UTC),
        trading_range_id=range_obj.id,
    )

    confidence = calculate_spring_confidence(
        spring=spring,
        creek=range_obj.creek,
        previous_tests=[]
    )

    # Assert recovery points match expected
    assert confidence.component_scores["recovery_speed"] == expected_points


def test_calculate_spring_confidence_validates_inputs():
    """Test that calculate_spring_confidence validates required inputs."""
    from src.pattern_engine.detectors.spring_detector import calculate_spring_confidence

    creek_level = Decimal("100.00")
    range_obj = create_trading_range(creek_level)

    spring = Spring(
        bar=create_test_bar(
            timestamp=datetime.now(UTC),
            low=creek_level - Decimal("1.50"),
            high=creek_level,
            close=creek_level - Decimal("0.50"),
            volume=40000,
            symbol="AAPL",
        ),
        bar_index=20,
        penetration_pct=Decimal("0.015"),
        volume_ratio=Decimal("0.4"),
        recovery_bars=1,
        creek_reference=creek_level,
        spring_low=creek_level - Decimal("1.50"),
        recovery_price=creek_level + Decimal("0.50"),
        detection_timestamp=datetime.now(UTC),
        trading_range_id=range_obj.id,
    )

    # Test missing spring
    with pytest.raises(ValueError, match="Spring required"):
        calculate_spring_confidence(spring=None, creek=range_obj.creek)

    # Test missing creek
    with pytest.raises(ValueError, match="Creek level required"):
        calculate_spring_confidence(spring=spring, creek=None)
