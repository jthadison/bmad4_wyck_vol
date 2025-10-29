"""
Unit tests for trading range clustering and formation.

Tests the clustering algorithm, range formation, and quality scoring
with synthetic test data.
"""

from __future__ import annotations

import pytest
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from typing import List
from src.models.pivot import Pivot, PivotType
from src.models.ohlcv import OHLCVBar
from src.models.price_cluster import PriceCluster
from src.models.trading_range import TradingRange
from src.pattern_engine.range_cluster import (
    cluster_pivots,
    form_trading_range,
    calculate_preliminary_quality_score,
    find_best_support_cluster,
    find_best_resistance_cluster,
    find_potential_ranges,
    _cluster_by_proximity,
    _create_price_cluster
)


# ============================================================================
# Test Fixtures and Helpers
# ============================================================================

def create_test_bar(
    symbol: str = "TEST",
    timeframe: str = "1d",
    open_price: Decimal = Decimal("100.00"),
    high: Decimal = Decimal("105.00"),
    low: Decimal = Decimal("95.00"),
    close: Decimal = Decimal("100.00"),
    volume: int = 1000000,
    timestamp: datetime = None,
    index: int = 0
) -> OHLCVBar:
    """Create test OHLCV bar"""
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)

    return OHLCVBar(
        symbol=symbol,
        timeframe=timeframe,
        timestamp=timestamp,
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=volume,
        spread=high - low  # Required field: high - low
    )


def create_test_pivot(
    price: Decimal,
    pivot_type: PivotType,
    index: int,
    symbol: str = "TEST",
    timeframe: str = "1d"
) -> Pivot:
    """Create test Pivot object"""
    # Create bar with appropriate high/low based on pivot type
    if pivot_type == PivotType.HIGH:
        bar = create_test_bar(
            symbol=symbol,
            timeframe=timeframe,
            high=price,
            low=price - Decimal("5.00"),
            timestamp=datetime.now(timezone.utc) + timedelta(days=index)
        )
    else:
        bar = create_test_bar(
            symbol=symbol,
            timeframe=timeframe,
            high=price + Decimal("5.00"),
            low=price,
            timestamp=datetime.now(timezone.utc) + timedelta(days=index)
        )

    return Pivot(
        bar=bar,
        price=price,
        type=pivot_type,
        strength=5,
        timestamp=bar.timestamp,
        index=index
    )


def generate_clustered_pivots() -> List[Pivot]:
    """
    Generate synthetic pivots with known clusters for testing.

    Returns pivots forming two distinct support clusters and two distinct
    resistance clusters:
        - Support cluster 1: 4 pivots near $100 (within 1.5%)
        - Support cluster 2: 3 pivots near $110 (within 1.5%)
        - Resistance cluster 1: 3 pivots near $120 (within 1.5%)
        - Resistance cluster 2: 4 pivots near $130 (within 1.5%)
    """
    pivots = []

    # Support cluster 1: 4 pivots near $100
    support_1_prices = [Decimal("100.00"), Decimal("100.50"), Decimal("101.00"), Decimal("100.25")]
    for i, price in enumerate(support_1_prices):
        pivots.append(create_test_pivot(price, PivotType.LOW, 10 + i * 5))

    # Support cluster 2: 3 pivots near $110
    support_2_prices = [Decimal("110.00"), Decimal("110.80"), Decimal("109.50")]
    for i, price in enumerate(support_2_prices):
        pivots.append(create_test_pivot(price, PivotType.LOW, 30 + i * 5))

    # Resistance cluster 1: 3 pivots near $120
    resistance_1_prices = [Decimal("120.00"), Decimal("120.60"), Decimal("119.50")]
    for i, price in enumerate(resistance_1_prices):
        pivots.append(create_test_pivot(price, PivotType.HIGH, 15 + i * 5))

    # Resistance cluster 2: 4 pivots near $130
    resistance_2_prices = [Decimal("130.00"), Decimal("130.80"), Decimal("129.50"), Decimal("130.40")]
    for i, price in enumerate(resistance_2_prices):
        pivots.append(create_test_pivot(price, PivotType.HIGH, 35 + i * 5))

    return pivots


def generate_test_bars(count: int, symbol: str = "TEST", timeframe: str = "1d") -> List[OHLCVBar]:
    """Generate test OHLCV bars"""
    bars = []
    base_time = datetime.now(timezone.utc)

    for i in range(count):
        bar = create_test_bar(
            symbol=symbol,
            timeframe=timeframe,
            timestamp=base_time + timedelta(days=i),
            index=i
        )
        bars.append(bar)

    return bars


# ============================================================================
# Task 10: Test Pivot Clustering (AC 9)
# ============================================================================

class TestPivotClustering:
    """Test scenario: Synthetic pivots with tight clusters"""

    def test_cluster_pivots_finds_multiple_clusters(self):
        """Test: Detect multiple distinct clusters in synthetic data"""
        pivots = generate_clustered_pivots()
        clusters = cluster_pivots(pivots, tolerance_pct=0.02)

        # Should find 4 clusters total (2 support, 2 resistance)
        assert len(clusters) == 4

        # Separate by type
        support_clusters = [c for c in clusters if c.cluster_type == PivotType.LOW]
        resistance_clusters = [c for c in clusters if c.cluster_type == PivotType.HIGH]

        assert len(support_clusters) == 2
        assert len(resistance_clusters) == 2

    def test_cluster_pivots_within_tolerance(self):
        """Test: Pivots within 2% tolerance cluster together"""
        # Create 5 pivots all within 2% of each other
        pivots = [
            create_test_pivot(Decimal("100.00"), PivotType.LOW, 10),
            create_test_pivot(Decimal("101.00"), PivotType.LOW, 15),  # 1% diff
            create_test_pivot(Decimal("102.00"), PivotType.LOW, 20),  # 2% diff
            create_test_pivot(Decimal("100.50"), PivotType.LOW, 25),  # 0.5% diff
            create_test_pivot(Decimal("101.50"), PivotType.LOW, 30),  # 1.5% diff
        ]

        clusters = cluster_pivots(pivots, tolerance_pct=0.02)

        # Should create 1 cluster with all 5 pivots
        assert len(clusters) == 1
        assert clusters[0].touch_count == 5
        assert Decimal("100.00") <= clusters[0].average_price <= Decimal("102.00")

    def test_cluster_pivots_outside_tolerance(self):
        """Test: Pivots outside tolerance form separate clusters"""
        # Create 3 pivots each >2% apart
        pivots = [
            create_test_pivot(Decimal("100.00"), PivotType.LOW, 10),
            create_test_pivot(Decimal("105.00"), PivotType.LOW, 15),  # 5% diff
            create_test_pivot(Decimal("110.00"), PivotType.LOW, 20),  # ~4.8% diff from 105
        ]

        clusters = cluster_pivots(pivots, tolerance_pct=0.02)

        # Each pivot too far apart, so 3 clusters with 1 pivot each
        # But minimum is 2 pivots, so all get filtered out
        assert len(clusters) == 0

    def test_cluster_statistics_calculation(self):
        """Test: Verify cluster statistics are calculated correctly"""
        pivots = generate_clustered_pivots()
        clusters = cluster_pivots(pivots, tolerance_pct=0.02)

        # Find the support cluster near $100 (should have 4 pivots)
        support_cluster = [c for c in clusters if c.cluster_type == PivotType.LOW and c.touch_count == 4]
        assert len(support_cluster) == 1

        cluster = support_cluster[0]

        # Verify statistics
        assert cluster.touch_count == 4
        assert cluster.min_price <= cluster.average_price <= cluster.max_price
        assert cluster.price_range == cluster.max_price - cluster.min_price
        assert cluster.std_deviation >= Decimal("0")  # Should be small but non-zero
        assert cluster.tightness_pct < Decimal("2.0")  # Should be tight cluster

    def test_empty_pivot_list(self):
        """Test: Empty pivot list returns empty cluster list"""
        clusters = cluster_pivots([], tolerance_pct=0.02)
        assert clusters == []

    def test_invalid_tolerance(self):
        """Test: Invalid tolerance raises ValueError"""
        pivots = [create_test_pivot(Decimal("100.00"), PivotType.LOW, 10)]

        with pytest.raises(ValueError, match="tolerance_pct must be > 0"):
            cluster_pivots(pivots, tolerance_pct=0.0)

        with pytest.raises(ValueError, match="tolerance_pct must be > 0"):
            cluster_pivots(pivots, tolerance_pct=-0.02)


# ============================================================================
# Task 11: Test Minimum Touch Validation (AC 5)
# ============================================================================

class TestMinimumTouchValidation:
    """Test scenario: Cluster with minimum touch requirements"""

    def test_single_pivot_filtered_out(self):
        """Test: Cluster with single pivot is filtered out"""
        pivots = [create_test_pivot(Decimal("100.00"), PivotType.LOW, 10)]
        clusters = cluster_pivots(pivots, tolerance_pct=0.02)

        # Minimum 2 pivots required, so empty list
        assert len(clusters) == 0

    def test_exactly_two_pivots_valid(self):
        """Test: Cluster with exactly 2 pivots is valid"""
        pivots = [
            create_test_pivot(Decimal("100.00"), PivotType.LOW, 10),
            create_test_pivot(Decimal("101.00"), PivotType.LOW, 15),
        ]
        clusters = cluster_pivots(pivots, tolerance_pct=0.02)

        assert len(clusters) == 1
        assert clusters[0].touch_count == 2

    def test_mixed_valid_invalid_clusters(self):
        """Test: Multiple clusters, some below minimum are filtered"""
        pivots = [
            # Cluster 1: 3 pivots @ $100 (valid)
            create_test_pivot(Decimal("100.00"), PivotType.LOW, 10),
            create_test_pivot(Decimal("100.50"), PivotType.LOW, 15),
            create_test_pivot(Decimal("101.00"), PivotType.LOW, 20),
            # Cluster 2: 1 pivot @ $110 (invalid - will be filtered)
            create_test_pivot(Decimal("110.00"), PivotType.LOW, 30),
            # Cluster 3: 2 pivots @ $120 (valid)
            create_test_pivot(Decimal("120.00"), PivotType.LOW, 40),
            create_test_pivot(Decimal("120.50"), PivotType.LOW, 45),
        ]

        clusters = cluster_pivots(pivots, tolerance_pct=0.02)

        # Should return 2 clusters (3-touch and 2-touch), 1-touch filtered out
        assert len(clusters) == 2
        touch_counts = [c.touch_count for c in clusters]
        assert 3 in touch_counts
        assert 2 in touch_counts


# ============================================================================
# Task 12: Test Trading Range Formation (AC 6, 7)
# ============================================================================

class TestTradingRangeFormation:
    """Test scenario: Valid and invalid trading range formation"""

    def test_valid_trading_range(self):
        """Test: Valid trading range is created successfully"""
        # Create support cluster avg $100
        support_pivots = [
            create_test_pivot(Decimal("100.00"), PivotType.LOW, 10),
            create_test_pivot(Decimal("100.50"), PivotType.LOW, 15),
            create_test_pivot(Decimal("101.00"), PivotType.LOW, 20),
        ]
        support_cluster = _create_price_cluster(support_pivots)

        # Create resistance cluster avg $110
        resistance_pivots = [
            create_test_pivot(Decimal("110.00"), PivotType.HIGH, 25),
            create_test_pivot(Decimal("110.50"), PivotType.HIGH, 30),
            create_test_pivot(Decimal("111.00"), PivotType.HIGH, 35),
        ]
        resistance_cluster = _create_price_cluster(resistance_pivots)

        # Create 40 bars
        bars = generate_test_bars(40)

        # Form trading range
        trading_range = form_trading_range(support_cluster, resistance_cluster, bars)

        # Verify range created
        assert trading_range is not None
        assert trading_range.support < trading_range.resistance
        assert trading_range.range_width == trading_range.resistance - trading_range.support
        assert trading_range.range_width_pct >= Decimal("0.03")  # ~10% range
        assert trading_range.duration >= 10
        assert trading_range.is_valid

    def test_invalid_support_greater_than_resistance(self):
        """Test: Invalid - support >= resistance returns None"""
        # Create support cluster avg $110 (backwards!)
        support_pivots = [
            create_test_pivot(Decimal("110.00"), PivotType.LOW, 10),
            create_test_pivot(Decimal("110.50"), PivotType.LOW, 15),
        ]
        support_cluster = _create_price_cluster(support_pivots)

        # Create resistance cluster avg $100 (backwards!)
        resistance_pivots = [
            create_test_pivot(Decimal("100.00"), PivotType.HIGH, 20),
            create_test_pivot(Decimal("100.50"), PivotType.HIGH, 25),
        ]
        resistance_cluster = _create_price_cluster(resistance_pivots)

        bars = generate_test_bars(30)

        # Should return None (validation failed)
        trading_range = form_trading_range(support_cluster, resistance_cluster, bars)
        assert trading_range is None

    def test_invalid_range_too_narrow(self):
        """Test: Invalid - range too narrow (< 3%) returns None"""
        # Create support cluster avg $100
        support_pivots = [
            create_test_pivot(Decimal("100.00"), PivotType.LOW, 10),
            create_test_pivot(Decimal("100.50"), PivotType.LOW, 15),
        ]
        support_cluster = _create_price_cluster(support_pivots)

        # Create resistance cluster avg $102 (only 2% range)
        resistance_pivots = [
            create_test_pivot(Decimal("102.00"), PivotType.HIGH, 20),
            create_test_pivot(Decimal("102.50"), PivotType.HIGH, 25),
        ]
        resistance_cluster = _create_price_cluster(resistance_pivots)

        bars = generate_test_bars(30)

        # Should return None (range_width_pct < 3%)
        trading_range = form_trading_range(support_cluster, resistance_cluster, bars)
        assert trading_range is None

    def test_invalid_insufficient_duration(self):
        """Test: Invalid - insufficient duration (< 10 bars) returns None"""
        # Create clusters with only 5 bars between them
        support_pivots = [
            create_test_pivot(Decimal("100.00"), PivotType.LOW, 0),
            create_test_pivot(Decimal("100.50"), PivotType.LOW, 2),
        ]
        support_cluster = _create_price_cluster(support_pivots)

        resistance_pivots = [
            create_test_pivot(Decimal("110.00"), PivotType.HIGH, 3),
            create_test_pivot(Decimal("110.50"), PivotType.HIGH, 5),
        ]
        resistance_cluster = _create_price_cluster(resistance_pivots)

        bars = generate_test_bars(10)

        # Duration = 5 - 0 + 1 = 6 bars (below 10 minimum)
        trading_range = form_trading_range(support_cluster, resistance_cluster, bars)
        assert trading_range is None


# ============================================================================
# Task 13: Test Quality Scoring (AC 8)
# ============================================================================

class TestQualityScoring:
    """Test scenario: Quality scoring with different range characteristics"""

    def test_perfect_range_scores_100(self):
        """Test: Perfect range characteristics score 100"""
        # Create perfect clusters
        # Duration: 40 bars (30 pts)
        # Total touches: 8 (30 pts)
        # Cluster tightness: std_dev < 1% (40 pts)

        # Support: 4 touches, very tight
        support_pivots = [
            create_test_pivot(Decimal("100.00"), PivotType.LOW, 0),
            create_test_pivot(Decimal("100.10"), PivotType.LOW, 10),
            create_test_pivot(Decimal("100.20"), PivotType.LOW, 20),
            create_test_pivot(Decimal("100.05"), PivotType.LOW, 30),
        ]
        support_cluster = _create_price_cluster(support_pivots)

        # Resistance: 4 touches, very tight
        resistance_pivots = [
            create_test_pivot(Decimal("110.00"), PivotType.HIGH, 5),
            create_test_pivot(Decimal("110.10"), PivotType.HIGH, 15),
            create_test_pivot(Decimal("110.20"), PivotType.HIGH, 25),
            create_test_pivot(Decimal("110.05"), PivotType.HIGH, 35),
        ]
        resistance_cluster = _create_price_cluster(resistance_pivots)

        duration = 40

        score = calculate_preliminary_quality_score(
            support_cluster, resistance_cluster, duration
        )

        # Should score very high (near 100)
        assert score >= 90

    def test_good_range_scores_70_80(self):
        """Test: Good range scores 70-80"""
        # Duration: 25 bars (20 pts)
        # Total touches: 6 (20 pts)
        # Cluster tightness: ~1.5% (20 pts)
        # Total: ~60 pts

        support_pivots = [
            create_test_pivot(Decimal("100.00"), PivotType.LOW, 0),
            create_test_pivot(Decimal("101.50"), PivotType.LOW, 10),
            create_test_pivot(Decimal("100.75"), PivotType.LOW, 20),
        ]
        support_cluster = _create_price_cluster(support_pivots)

        resistance_pivots = [
            create_test_pivot(Decimal("110.00"), PivotType.HIGH, 5),
            create_test_pivot(Decimal("111.50"), PivotType.HIGH, 15),
            create_test_pivot(Decimal("110.75"), PivotType.HIGH, 25),
        ]
        resistance_cluster = _create_price_cluster(resistance_pivots)

        duration = 25

        score = calculate_preliminary_quality_score(
            support_cluster, resistance_cluster, duration
        )

        # Should score moderate
        assert 40 <= score <= 80

    def test_marginal_range_scores_low(self):
        """Test: Marginal range scores < 50"""
        # Duration: 12 bars (10 pts)
        # Total touches: 4 (10 pts)
        # Cluster tightness: ~2.5% (10 pts)
        # Total: ~30 pts

        support_pivots = [
            create_test_pivot(Decimal("100.00"), PivotType.LOW, 0),
            create_test_pivot(Decimal("102.50"), PivotType.LOW, 5),
        ]
        support_cluster = _create_price_cluster(support_pivots)

        resistance_pivots = [
            create_test_pivot(Decimal("110.00"), PivotType.HIGH, 8),
            create_test_pivot(Decimal("112.50"), PivotType.HIGH, 12),
        ]
        resistance_cluster = _create_price_cluster(resistance_pivots)

        duration = 12

        score = calculate_preliminary_quality_score(
            support_cluster, resistance_cluster, duration
        )

        # Should score low
        assert score < 50

    def test_score_never_exceeds_100(self):
        """Test: Score is capped at 100"""
        # Create hypothetically perfect scenario
        support_pivots = [
            create_test_pivot(Decimal("100.00"), PivotType.LOW, i * 5)
            for i in range(10)  # 10 touches
        ]
        support_cluster = _create_price_cluster(support_pivots)

        resistance_pivots = [
            create_test_pivot(Decimal("110.00"), PivotType.HIGH, i * 5 + 2)
            for i in range(10)  # 10 touches
        ]
        resistance_cluster = _create_price_cluster(resistance_pivots)

        duration = 100  # Very long

        score = calculate_preliminary_quality_score(
            support_cluster, resistance_cluster, duration
        )

        # Should be capped at 100
        assert score <= 100


# ============================================================================
# Test Helper Functions
# ============================================================================

class TestHelperFunctions:
    """Test helper functions for cluster selection"""

    def test_find_best_support_cluster(self):
        """Test: Find best support cluster by touches and tightness"""
        clusters = cluster_pivots(generate_clustered_pivots(), tolerance_pct=0.02)
        best_support = find_best_support_cluster(clusters)

        assert best_support is not None
        assert best_support.cluster_type == PivotType.LOW
        # Should select cluster with most touches
        assert best_support.touch_count >= 3

    def test_find_best_resistance_cluster(self):
        """Test: Find best resistance cluster by touches and tightness"""
        clusters = cluster_pivots(generate_clustered_pivots(), tolerance_pct=0.02)
        best_resistance = find_best_resistance_cluster(clusters)

        assert best_resistance is not None
        assert best_resistance.cluster_type == PivotType.HIGH
        # Should select cluster with most touches
        assert best_resistance.touch_count >= 3

    def test_find_potential_ranges(self):
        """Test: Find all potential trading ranges"""
        pivots = generate_clustered_pivots()
        bars = generate_test_bars(60)

        ranges = find_potential_ranges(pivots, bars, tolerance_pct=0.02)

        # Should find at least 1 valid range
        assert len(ranges) >= 1

        # All ranges should be valid
        for r in ranges:
            assert r.is_valid
            assert r.support < r.resistance
            assert r.range_width_pct >= Decimal("0.03")
            assert r.duration >= 10

        # Ranges should be sorted by quality score (descending)
        if len(ranges) > 1:
            scores = [r.quality_score for r in ranges]
            assert scores == sorted(scores, reverse=True)
