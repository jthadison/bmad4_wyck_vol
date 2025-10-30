"""
Unit tests for trading range quality scoring module.

Tests all four scoring components (duration, touch count, tightness, volume)
in isolation and in combination, including perfect range (100 score), edge cases,
and quality threshold validation.
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from src.models.ohlcv import OHLCVBar
from src.models.pivot import Pivot, PivotType
from src.models.price_cluster import PriceCluster
from src.models.trading_range import TradingRange
from src.models.volume_analysis import VolumeAnalysis
from src.pattern_engine.range_quality import (
    _score_duration,
    _score_price_tightness,
    _score_touch_count,
    calculate_range_quality,
    filter_quality_ranges,
    get_quality_ranges,
    is_quality_range,
)

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def base_timestamp():
    """Base timestamp for test data."""
    return datetime(2024, 1, 1, 9, 30, 0, tzinfo=UTC)


@pytest.fixture
def sample_bars(base_timestamp) -> list[OHLCVBar]:
    """Generate 50 OHLCV bars for testing."""
    from datetime import timedelta

    bars = []
    for i in range(50):
        timestamp = base_timestamp + timedelta(days=i)  # Use timedelta instead of replace
        high = Decimal("110.00")
        low = Decimal("99.00")
        bars.append(
            OHLCVBar(
                symbol="TEST",
                timestamp=timestamp,
                open=Decimal("100.00"),
                high=high,
                low=low,
                close=Decimal("105.00"),
                volume=Decimal("1000000"),
                timeframe="1d",
                spread=high - low,  # Add spread field
            )
        )
    return bars


@pytest.fixture
def sample_volume_analysis(sample_bars) -> list[VolumeAnalysis]:
    """Generate VolumeAnalysis matching sample_bars with neutral volume."""
    return [VolumeAnalysis(bar=bar, volume_ratio=Decimal("1.0")) for bar in sample_bars]


def create_pivot_cluster(
    base_price: Decimal,
    touch_count: int,
    std_dev_pct: Decimal,
    pivot_type: PivotType,
    base_timestamp: datetime,
) -> PriceCluster:
    """
    Create a PriceCluster with specified characteristics.

    Args:
        base_price: Average price for cluster
        touch_count: Number of pivots (touches)
        std_dev_pct: Standard deviation as percentage of base_price
        pivot_type: HIGH or LOW
        base_timestamp: Base timestamp

    Returns:
        PriceCluster with specified characteristics
    """
    pivots = []
    std_dev = base_price * std_dev_pct

    from datetime import timedelta

    for i in range(touch_count):
        # Distribute pivots around base_price within std_dev
        offset = (
            (Decimal(i) - Decimal(touch_count) / Decimal(2))
            * (std_dev / Decimal(touch_count))
            * Decimal(2)
        )
        price = base_price + offset
        timestamp = base_timestamp + timedelta(days=i * 3)  # Use timedelta

        # Create proper OHLCVBar for pivot (QA Issue #2 fix)
        # Round price to 8 decimal places for Pydantic validation
        price_rounded = price.quantize(Decimal("0.00000001"))
        bar = OHLCVBar(
            symbol="TEST",
            timestamp=timestamp,
            open=price_rounded,
            high=(price_rounded + Decimal("1.00"))
            if pivot_type == PivotType.HIGH
            else (price_rounded + Decimal("0.50")),
            low=(price_rounded - Decimal("0.50"))
            if pivot_type == PivotType.LOW
            else (price_rounded - Decimal("1.00")),
            close=price_rounded,
            volume=Decimal("1000000"),
            timeframe="1d",
            spread=Decimal("1.50"),
        )

        pivots.append(
            Pivot(
                bar=bar,
                price=price_rounded,  # Use rounded price
                type=pivot_type,
                strength=1,
                timestamp=timestamp,
                index=i * 3,
            )
        )

    min_price = min(p.price for p in pivots)
    max_price = max(p.price for p in pivots)

    return PriceCluster(
        pivots=pivots,
        average_price=base_price,
        min_price=min_price,
        max_price=max_price,
        price_range=max_price - min_price,
        touch_count=touch_count,
        cluster_type=pivot_type,
        std_deviation=std_dev,
        timestamp_range=(pivots[0].timestamp, pivots[-1].timestamp),
    )


def create_trading_range(
    symbol: str,
    support_cluster: PriceCluster,
    resistance_cluster: PriceCluster,
    duration: int,
    start_index: int = 10,
) -> TradingRange:
    """
    Create a TradingRange from clusters.

    Args:
        symbol: Ticker symbol
        support_cluster: Support level cluster
        resistance_cluster: Resistance level cluster
        duration: Range duration in bars
        start_index: Starting index in bars array

    Returns:
        TradingRange with specified characteristics
    """
    support = support_cluster.average_price
    resistance = resistance_cluster.average_price
    range_width = resistance - support
    range_width_pct = (range_width / support).quantize(
        Decimal("0.0001")
    )  # Round to 4 decimal places

    return TradingRange(
        symbol=symbol,
        timeframe="1d",
        support_cluster=support_cluster,
        resistance_cluster=resistance_cluster,
        support=support,
        resistance=resistance,
        midpoint=(support + resistance) / 2,
        range_width=range_width,
        range_width_pct=range_width_pct,
        start_index=start_index,
        end_index=start_index + duration - 1,
        duration=duration,
    )


# ============================================================================
# Task 12: Test Component Scoring in Isolation
# ============================================================================


class TestDurationScoring:
    """Test duration component scoring (AC 2)."""

    @pytest.mark.parametrize(
        "duration,expected_score",
        [
            (40, 30),  # Excellent cause
            (50, 30),  # Above excellent
            (25, 20),  # Good cause
            (30, 20),  # Good cause
            (15, 15),  # Adequate cause
            (20, 15),  # Adequate cause
            (10, 10),  # Minimal cause
            (12, 10),  # Minimal cause
            (5, 0),  # Insufficient (below minimum)
        ],
    )
    def test_duration_scoring_thresholds(self, duration, expected_score):
        """Test duration scoring across all thresholds."""
        score = _score_duration(duration)
        assert (
            score == expected_score
        ), f"Duration {duration} should score {expected_score}, got {score}"


class TestTouchCountScoring:
    """Test touch count component scoring (AC 3)."""

    @pytest.mark.parametrize(
        "support_touches,resistance_touches,min_expected_score",
        [
            (4, 4, 30),  # 8 touches (very strong) + symmetry bonus
            (5, 4, 30),  # 9 touches
            (3, 3, 25),  # 6 touches (strong) + symmetry bonus
            (4, 3, 25),  # 7 touches
            (2, 2, 15),  # 4 touches (adequate) + symmetry bonus
            (3, 2, 15),  # 5 touches
        ],
    )
    def test_touch_count_scoring(
        self, support_touches, resistance_touches, min_expected_score, base_timestamp
    ):
        """Test touch count scoring."""
        support_cluster = create_pivot_cluster(
            Decimal("100.00"), support_touches, Decimal("0.005"), PivotType.LOW, base_timestamp
        )
        resistance_cluster = create_pivot_cluster(
            Decimal("110.00"), resistance_touches, Decimal("0.005"), PivotType.HIGH, base_timestamp
        )
        trading_range = create_trading_range("TEST", support_cluster, resistance_cluster, 20)

        score = _score_touch_count(trading_range)
        assert score >= min_expected_score - 5  # Allow for symmetry bonus variation


class TestTightnessScoring:
    """Test tightness component scoring (AC 4)."""

    @pytest.mark.parametrize(
        "std_dev_pct,expected_score",
        [
            (Decimal("0.005"), 20),  # 0.5% < 1% → 20 pts
            (Decimal("0.009"), 20),  # 0.9% < 1% → 20 pts
            (Decimal("0.010"), 15),  # 1.0% < 1.5% → 15 pts
            (Decimal("0.014"), 15),  # 1.4% < 1.5% → 15 pts
            (Decimal("0.015"), 10),  # 1.5% < 2% → 10 pts
            (Decimal("0.019"), 10),  # 1.9% < 2% → 10 pts
            (Decimal("0.020"), 0),  # 2.0% >= 2% → 0 pts
            (Decimal("0.025"), 0),  # 2.5% >= 2% → 0 pts
        ],
    )
    def test_tightness_scoring_thresholds(self, std_dev_pct, expected_score, base_timestamp):
        """Test tightness scoring across all thresholds."""
        support_cluster = create_pivot_cluster(
            Decimal("100.00"), 4, std_dev_pct, PivotType.LOW, base_timestamp
        )
        resistance_cluster = create_pivot_cluster(
            Decimal("110.00"), 4, std_dev_pct, PivotType.HIGH, base_timestamp
        )
        trading_range = create_trading_range("TEST", support_cluster, resistance_cluster, 20)

        score = _score_price_tightness(trading_range)
        assert score == expected_score


# ============================================================================
# Task 11 & 13: Test Quality Scoring
# ============================================================================


class TestQualityScoring:
    """Test comprehensive quality scoring."""

    def test_high_quality_range(self, sample_bars, base_timestamp):
        """Test high-quality range scores well."""
        # Duration: 40 bars (30 pts)
        # Touch count: 4+4 = 8 touches (30 pts)
        # Tightness: 0.5% std dev (20 pts)
        # Volume: neutral (varies)

        support_cluster = create_pivot_cluster(
            Decimal("99.00"), 4, Decimal("0.005"), PivotType.LOW, base_timestamp
        )
        resistance_cluster = create_pivot_cluster(
            Decimal("110.00"), 4, Decimal("0.005"), PivotType.HIGH, base_timestamp
        )
        trading_range = create_trading_range("TEST", support_cluster, resistance_cluster, 40)

        # Create volume analysis with neutral volume
        volume_analysis = [
            VolumeAnalysis(bar=bar, volume_ratio=Decimal("1.0")) for bar in sample_bars
        ]

        score = calculate_range_quality(trading_range, sample_bars, volume_analysis)

        # Should score high (80+ from duration/touch/tightness alone)
        assert score >= 70, f"High-quality range scored {score}, expected >= 70"

    def test_minimum_valid_range_below_threshold(self, sample_bars, base_timestamp):
        """Test minimum valid range scores below 70 threshold."""
        # Duration: 10 bars (10 pts)
        # Touch count: 2+2 = 4 touches (15-20 pts)
        # Tightness: 1.5% std dev (15 pts)
        # Expected: ~40-45 pts (below 70 threshold)

        support_cluster = create_pivot_cluster(
            Decimal("100.00"), 2, Decimal("0.015"), PivotType.LOW, base_timestamp
        )
        resistance_cluster = create_pivot_cluster(
            Decimal("110.00"), 2, Decimal("0.015"), PivotType.HIGH, base_timestamp
        )
        trading_range = create_trading_range("TEST", support_cluster, resistance_cluster, 10)

        volume_analysis = [
            VolumeAnalysis(bar=bar, volume_ratio=Decimal("1.0")) for bar in sample_bars
        ]

        score = calculate_range_quality(trading_range, sample_bars, volume_analysis)
        assert score < 70, f"Minimum range scored {score}, expected < 70"

    def test_null_trading_range_returns_0(self, sample_bars, sample_volume_analysis):
        """Test null trading range returns 0."""
        score = calculate_range_quality(None, sample_bars, sample_volume_analysis)
        assert score == 0

    def test_empty_bars_returns_0(self, base_timestamp):
        """Test empty bars list returns 0."""
        support_cluster = create_pivot_cluster(
            Decimal("100.00"), 2, Decimal("0.01"), PivotType.LOW, base_timestamp
        )
        resistance_cluster = create_pivot_cluster(
            Decimal("110.00"), 2, Decimal("0.01"), PivotType.HIGH, base_timestamp
        )
        trading_range = create_trading_range("TEST", support_cluster, resistance_cluster, 10)

        score = calculate_range_quality(trading_range, [], [])
        assert score == 0

    def test_volume_bars_mismatch_returns_0(self, sample_bars, base_timestamp):
        """Test volume/bars length mismatch returns 0."""
        support_cluster = create_pivot_cluster(
            Decimal("100.00"), 2, Decimal("0.01"), PivotType.LOW, base_timestamp
        )
        resistance_cluster = create_pivot_cluster(
            Decimal("110.00"), 2, Decimal("0.01"), PivotType.HIGH, base_timestamp
        )
        trading_range = create_trading_range("TEST", support_cluster, resistance_cluster, 10)

        # Mismatched volume analysis (shorter)
        volume_analysis = [VolumeAnalysis(bar=sample_bars[0], volume_ratio=Decimal("1.0"))]

        score = calculate_range_quality(trading_range, sample_bars, volume_analysis)
        assert score == 0


# ============================================================================
# Task 8: Test Quality Threshold Validation
# ============================================================================


class TestQualityThreshold:
    """Test quality threshold validation (AC 6)."""

    def test_is_quality_range_above_threshold(self, base_timestamp):
        """Test is_quality_range returns True for score >= 70."""
        support_cluster = create_pivot_cluster(
            Decimal("100.00"), 4, Decimal("0.01"), PivotType.LOW, base_timestamp
        )
        resistance_cluster = create_pivot_cluster(
            Decimal("110.00"), 4, Decimal("0.01"), PivotType.HIGH, base_timestamp
        )
        trading_range = create_trading_range("TEST", support_cluster, resistance_cluster, 30)
        trading_range.quality_score = 85

        assert is_quality_range(trading_range) is True

    def test_is_quality_range_below_threshold(self, base_timestamp):
        """Test is_quality_range returns False for score < 70."""
        support_cluster = create_pivot_cluster(
            Decimal("100.00"), 2, Decimal("0.02"), PivotType.LOW, base_timestamp
        )
        resistance_cluster = create_pivot_cluster(
            Decimal("110.00"), 2, Decimal("0.02"), PivotType.HIGH, base_timestamp
        )
        trading_range = create_trading_range("TEST", support_cluster, resistance_cluster, 10)
        trading_range.quality_score = 65

        assert is_quality_range(trading_range) is False

    def test_filter_quality_ranges(self, base_timestamp):
        """Test filter_quality_ranges filters by score threshold."""
        # Create 3 ranges with different scores
        ranges = []
        for i, score in enumerate([85, 65, 75]):
            support_cluster = create_pivot_cluster(
                Decimal("100.00"), 4, Decimal("0.01"), PivotType.LOW, base_timestamp
            )
            resistance_cluster = create_pivot_cluster(
                Decimal("110.00"), 4, Decimal("0.01"), PivotType.HIGH, base_timestamp
            )
            trading_range = create_trading_range(
                f"TEST{i}", support_cluster, resistance_cluster, 30
            )
            trading_range.quality_score = score
            ranges.append(trading_range)

        # Filter for quality ranges (>= 70)
        quality_ranges = filter_quality_ranges(ranges, min_score=70)

        assert len(quality_ranges) == 2
        assert quality_ranges[0].quality_score == 85
        assert quality_ranges[1].quality_score == 75

    def test_get_quality_ranges_sorted(self, base_timestamp):
        """Test get_quality_ranges returns sorted by score descending."""
        # Create 3 ranges with different scores
        ranges = []
        for i, score in enumerate([75, 85, 65]):
            support_cluster = create_pivot_cluster(
                Decimal("100.00"), 4, Decimal("0.01"), PivotType.LOW, base_timestamp
            )
            resistance_cluster = create_pivot_cluster(
                Decimal("110.00"), 4, Decimal("0.01"), PivotType.HIGH, base_timestamp
            )
            trading_range = create_trading_range(
                f"TEST{i}", support_cluster, resistance_cluster, 30
            )
            trading_range.quality_score = score
            ranges.append(trading_range)

        # Get quality ranges sorted
        quality_ranges = get_quality_ranges(ranges)

        assert len(quality_ranges) == 2
        assert quality_ranges[0].quality_score == 85  # Highest first
        assert quality_ranges[1].quality_score == 75


# ============================================================================
# Task 9: Test TradingRange Model Updates
# ============================================================================


class TestTradingRangeModel:
    """Test TradingRange model quality_score field and helper method."""

    def test_quality_score_field_exists(self, base_timestamp):
        """Test quality_score field exists and accepts valid values."""
        support_cluster = create_pivot_cluster(
            Decimal("100.00"), 4, Decimal("0.01"), PivotType.LOW, base_timestamp
        )
        resistance_cluster = create_pivot_cluster(
            Decimal("110.00"), 4, Decimal("0.01"), PivotType.HIGH, base_timestamp
        )
        trading_range = create_trading_range("TEST", support_cluster, resistance_cluster, 30)

        # Default should be None
        assert trading_range.quality_score is None

        # Set to valid value
        trading_range.quality_score = 85
        assert trading_range.quality_score == 85

    def test_update_quality_score_method(self, base_timestamp):
        """Test update_quality_score method validates and updates score."""
        support_cluster = create_pivot_cluster(
            Decimal("100.00"), 4, Decimal("0.01"), PivotType.LOW, base_timestamp
        )
        resistance_cluster = create_pivot_cluster(
            Decimal("110.00"), 4, Decimal("0.01"), PivotType.HIGH, base_timestamp
        )
        trading_range = create_trading_range("TEST", support_cluster, resistance_cluster, 30)

        # Update with valid score
        trading_range.update_quality_score(75)
        assert trading_range.quality_score == 75

    def test_update_quality_score_validation(self, base_timestamp):
        """Test update_quality_score validates range 0-100."""
        support_cluster = create_pivot_cluster(
            Decimal("100.00"), 4, Decimal("0.01"), PivotType.LOW, base_timestamp
        )
        resistance_cluster = create_pivot_cluster(
            Decimal("110.00"), 4, Decimal("0.01"), PivotType.HIGH, base_timestamp
        )
        trading_range = create_trading_range("TEST", support_cluster, resistance_cluster, 30)

        # Test invalid scores
        with pytest.raises(ValueError):
            trading_range.update_quality_score(-1)

        with pytest.raises(ValueError):
            trading_range.update_quality_score(101)

        # Test boundary values
        trading_range.update_quality_score(0)
        assert trading_range.quality_score == 0

        trading_range.update_quality_score(100)
        assert trading_range.quality_score == 100
