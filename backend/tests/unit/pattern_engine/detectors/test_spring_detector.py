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
