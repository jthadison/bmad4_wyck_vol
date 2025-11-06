"""
Unit tests for VolumeCache class.

Tests cover:
- Cache building with various bar counts
- O(1) ratio lookups
- Missing timestamp handling
- Cache invalidation
- Window parameter variations
- Insufficient bars edge case
- Empty bars edge case
- Performance benchmark (<100ms for 100-bar sequence)
- Cache statistics

Author: Story 5.6 - SpringDetector Module Integration
"""

import time
from datetime import datetime, UTC, timedelta
from decimal import Decimal

from src.pattern_engine.volume_cache import VolumeCache
from src.models.ohlcv import OHLCVBar


def create_test_bars(count: int, start_date: datetime = None) -> list[OHLCVBar]:
    """Create test bars with incrementing volumes."""
    if start_date is None:
        start_date = datetime(2024, 1, 1, tzinfo=UTC)

    bars = []
    for i in range(count):
        timestamp = start_date + timedelta(days=i)
        volume = 1000000 + (i * 10000)  # Incrementing volume

        bar = OHLCVBar(
            symbol="TEST",
            timestamp=timestamp,
            open=Decimal("100.00"),
            high=Decimal("101.00"),
            low=Decimal("99.00"),
            close=Decimal("100.50"),
            volume=volume,
            spread=Decimal("2.00"),
            timeframe="1d",
        )
        bars.append(bar)

    return bars


class TestVolumeCacheCreation:
    """Test VolumeCache initialization and cache building."""

    def test_create_cache_with_100_bars(self):
        """Test cache building with 100-bar sequence."""
        bars = create_test_bars(100)
        cache = VolumeCache(bars, window=20)

        # Should calculate ratios for bars[20:] = 80 ratios
        assert len(cache) == 80
        assert len(cache.ratios) == 80

    def test_create_cache_with_50_bars(self):
        """Test cache building with 50-bar sequence."""
        bars = create_test_bars(50)
        cache = VolumeCache(bars, window=20)

        # Should calculate ratios for bars[20:] = 30 ratios
        assert len(cache) == 30

    def test_cache_builds_chronologically(self):
        """Test that cache processes bars in chronological order."""
        bars = create_test_bars(30)
        cache = VolumeCache(bars, window=20)

        # Should have ratios for bars[20:]
        assert len(cache) == 10

        # Check that first 20 bars have no cached ratios
        for i in range(20):
            assert cache.get_ratio(bars[i].timestamp) is None

        # Check that bars[20:] have cached ratios
        for i in range(20, 30):
            assert cache.get_ratio(bars[i].timestamp) is not None


class TestGetRatio:
    """Test get_ratio() method functionality."""

    def test_get_ratio_returns_correct_value(self):
        """Test get_ratio() returns correct pre-calculated value."""
        bars = create_test_bars(30)
        cache = VolumeCache(bars, window=20)

        # Get ratio for bar 25
        ratio = cache.get_ratio(bars[25].timestamp)

        assert ratio is not None
        assert isinstance(ratio, Decimal)

        # Calculate expected ratio manually
        window_volumes = [bars[i].volume for i in range(5, 25)]  # bars[5:25]
        avg_volume = sum(window_volumes) / 20
        expected_ratio = Decimal(str(bars[25].volume / avg_volume))

        # Should match (within small tolerance for floating point)
        assert abs(ratio - expected_ratio) < Decimal("0.01")

    def test_get_ratio_returns_none_for_missing_timestamp(self):
        """Test get_ratio() returns None for timestamp not in cache."""
        bars = create_test_bars(30)
        cache = VolumeCache(bars, window=20)

        # Try to get ratio for timestamp not in bars
        missing_timestamp = datetime(2025, 1, 1, tzinfo=UTC)
        ratio = cache.get_ratio(missing_timestamp)

        assert ratio is None

    def test_get_ratio_returns_none_for_pre_window_bars(self):
        """Test get_ratio() returns None for bars before window."""
        bars = create_test_bars(30)
        cache = VolumeCache(bars, window=20)

        # First 20 bars should not have ratios
        for i in range(20):
            ratio = cache.get_ratio(bars[i].timestamp)
            assert ratio is None, f"Bar {i} should not have ratio (before window)"


class TestInvalidate:
    """Test cache invalidation functionality."""

    def test_invalidate_removes_cached_ratio(self):
        """Test invalidate() removes cached ratio."""
        bars = create_test_bars(30)
        cache = VolumeCache(bars, window=20)

        # Verify ratio exists
        timestamp = bars[25].timestamp
        assert cache.get_ratio(timestamp) is not None

        # Invalidate
        cache.invalidate(timestamp)

        # Should return None after invalidation
        assert cache.get_ratio(timestamp) is None

        # Cache size should decrease
        assert len(cache) == 9  # Was 10, now 9

    def test_invalidate_missing_timestamp_no_error(self):
        """Test invalidate() handles missing timestamp gracefully."""
        bars = create_test_bars(30)
        cache = VolumeCache(bars, window=20)

        # Invalidate timestamp not in cache (should not raise error)
        missing_timestamp = datetime(2025, 1, 1, tzinfo=UTC)
        cache.invalidate(missing_timestamp)

        # Cache size should remain unchanged
        assert len(cache) == 10


class TestWindowParameter:
    """Test different window sizes."""

    def test_cache_with_20_bar_window(self):
        """Test cache building with 20-bar window (default)."""
        bars = create_test_bars(50)
        cache = VolumeCache(bars, window=20)

        # Should have 30 ratios (50 - 20)
        assert len(cache) == 30

        # Bar 20 should be first with ratio
        assert cache.get_ratio(bars[20].timestamp) is not None

    def test_cache_with_50_bar_window(self):
        """Test cache building with 50-bar window."""
        bars = create_test_bars(100)
        cache = VolumeCache(bars, window=50)

        # Should have 50 ratios (100 - 50)
        assert len(cache) == 50

        # Bar 50 should be first with ratio
        assert cache.get_ratio(bars[50].timestamp) is not None
        assert cache.get_ratio(bars[49].timestamp) is None


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_insufficient_bars(self):
        """Test cache with bars count < window size."""
        bars = create_test_bars(15)  # Less than default window of 20
        cache = VolumeCache(bars, window=20)

        # Should create empty cache
        assert len(cache) == 0
        assert len(cache.ratios) == 0

    def test_empty_bars_list(self):
        """Test cache with empty bars list."""
        bars = []
        cache = VolumeCache(bars, window=20)

        # Should create empty cache
        assert len(cache) == 0

    def test_exact_window_size(self):
        """Test cache with bars count == window size."""
        bars = create_test_bars(20)
        cache = VolumeCache(bars, window=20)

        # Should have no ratios (need at least window+1 bars)
        assert len(cache) == 0

    def test_window_plus_one_bars(self):
        """Test cache with window+1 bars."""
        bars = create_test_bars(21)
        cache = VolumeCache(bars, window=20)

        # Should have exactly 1 ratio
        assert len(cache) == 1
        assert cache.get_ratio(bars[20].timestamp) is not None


class TestPerformance:
    """Test cache performance benchmarks."""

    def test_performance_100_bar_sequence(self):
        """Test cache building completes in <100ms for 100-bar sequence."""
        bars = create_test_bars(100)

        # Measure cache build time
        start_time = time.perf_counter()
        cache = VolumeCache(bars, window=20)
        end_time = time.perf_counter()

        elapsed_ms = (end_time - start_time) * 1000

        # Performance target: <100ms
        assert elapsed_ms < 100, f"Cache build took {elapsed_ms:.2f}ms, should be <100ms"
        assert len(cache) == 80

    def test_lookup_performance_o1(self):
        """Test that ratio lookups are O(1)."""
        bars = create_test_bars(100)
        cache = VolumeCache(bars, window=20)

        # Measure 100 lookups
        start_time = time.perf_counter()
        for i in range(20, 100):
            _ = cache.get_ratio(bars[i].timestamp)
        end_time = time.perf_counter()

        elapsed_ms = (end_time - start_time) * 1000

        # 100 O(1) lookups should be nearly instant (<1ms)
        assert elapsed_ms < 1, f"100 lookups took {elapsed_ms:.2f}ms, should be <1ms"

    def test_speedup_vs_repeated_calculation(self):
        """Test cache provides significant speedup vs repeated calculation.

        Note: Actual speedup in production can be 5-10x depending on:
        - Number of spring candidates
        - Bar sequence length
        - System performance

        This test uses a conservative 2.5x threshold for CI reliability.
        """
        bars = create_test_bars(100)
        window = 20

        # Time WITHOUT cache (simulate 50 spring candidates)
        start_time = time.perf_counter()
        for _ in range(50):
            for i in range(window, len(bars)):
                # Simulate per-candidate volume calculation
                window_volumes = [bars[j].volume for j in range(i - window, i)]
                _ = sum(window_volumes) / window
        end_time = time.perf_counter()
        no_cache_ms = (end_time - start_time) * 1000

        # Time WITH cache
        start_time = time.perf_counter()
        cache = VolumeCache(bars, window=window)
        for _ in range(50):
            for i in range(window, len(bars)):
                _ = cache.get_ratio(bars[i].timestamp)
        end_time = time.perf_counter()
        with_cache_ms = (end_time - start_time) * 1000

        # Cache should be at least 2.5x faster (conservative for CI)
        # Production speedup is typically 5-10x
        speedup = no_cache_ms / with_cache_ms
        assert speedup > 2.5, f"Cache speedup {speedup:.2f}x, expected >2.5x (production typically 5-10x)"


class TestCacheStatistics:
    """Test cache statistics and diagnostics."""

    def test_cache_repr(self):
        """Test __repr__ returns useful information."""
        bars = create_test_bars(50)
        cache = VolumeCache(bars, window=20)

        repr_str = repr(cache)

        assert "VolumeCache" in repr_str
        assert "ratios=30" in repr_str
        assert "window=20" in repr_str
        assert "KB" in repr_str

    def test_cache_len(self):
        """Test __len__ returns correct ratio count."""
        bars = create_test_bars(50)
        cache = VolumeCache(bars, window=20)

        assert len(cache) == 30
        assert len(cache) == len(cache.ratios)

    def test_cache_estimate_size(self):
        """Test _estimate_cache_size returns reasonable value."""
        bars = create_test_bars(100)
        cache = VolumeCache(bars, window=20)

        size_bytes = cache._estimate_cache_size()

        # 80 ratios × ~128 bytes/entry = ~10,240 bytes
        expected_size = 80 * 128
        assert abs(size_bytes - expected_size) < 100  # Allow small variance
