"""
Unit tests for ValidationCache - Story 22.6

Tests cover:
- Basic get/set operations
- TTL expiration with time mocking
- LRU eviction order
- Thread safety with concurrent access
- Metrics accuracy
- invalidate_pattern functionality

Target: ≥95% coverage
"""

import threading
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from src.cache.validation_cache import CacheEntry, CacheMetrics, ValidationCache


class TestCacheEntry:
    """Tests for CacheEntry dataclass."""

    def test_cache_entry_creation(self):
        expires = datetime.now(UTC)
        entry = CacheEntry(value="test", expires_at=expires)

        assert entry.value == "test"
        assert entry.expires_at == expires

    def test_cache_entry_is_frozen(self):
        entry = CacheEntry(value="test", expires_at=datetime.now(UTC))

        with pytest.raises(AttributeError):
            entry.value = "modified"


class TestCacheMetrics:
    """Tests for CacheMetrics dataclass."""

    def test_default_metrics(self):
        metrics = CacheMetrics()

        assert metrics.hits == 0
        assert metrics.misses == 0
        assert metrics.evictions == 0

    def test_total_requests(self):
        metrics = CacheMetrics(hits=10, misses=5)

        assert metrics.total_requests == 15

    def test_hit_rate_calculation(self):
        metrics = CacheMetrics(hits=3, misses=1)

        assert metrics.hit_rate == pytest.approx(0.75)

    def test_hit_rate_zero_requests(self):
        metrics = CacheMetrics()

        assert metrics.hit_rate == 0.0


class TestValidationCacheBasic:
    """Tests for basic ValidationCache operations."""

    def test_basic_get_set(self):
        cache: ValidationCache[str] = ValidationCache()
        cache.set("key1", "value1")

        assert cache.get("key1") == "value1"

    def test_get_miss_returns_none(self):
        cache: ValidationCache[str] = ValidationCache()

        assert cache.get("nonexistent") is None

    def test_set_overwrites_existing(self):
        cache: ValidationCache[str] = ValidationCache()
        cache.set("key1", "value1")
        cache.set("key1", "value2")

        assert cache.get("key1") == "value2"

    def test_invalidate_existing_key(self):
        cache: ValidationCache[str] = ValidationCache()
        cache.set("key1", "value1")

        result = cache.invalidate("key1")

        assert result is True
        assert cache.get("key1") is None

    def test_invalidate_nonexistent_key(self):
        cache: ValidationCache[str] = ValidationCache()

        result = cache.invalidate("nonexistent")

        assert result is False

    def test_clear(self):
        cache: ValidationCache[str] = ValidationCache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")

        cache.clear()

        assert cache.get("key1") is None
        assert cache.get("key2") is None
        assert len(cache) == 0

    def test_len(self):
        cache: ValidationCache[str] = ValidationCache()

        assert len(cache) == 0

        cache.set("key1", "value1")
        assert len(cache) == 1

        cache.set("key2", "value2")
        assert len(cache) == 2

    def test_contains_valid_key(self):
        cache: ValidationCache[str] = ValidationCache()
        cache.set("key1", "value1")

        assert "key1" in cache
        assert "key2" not in cache


class TestValidationCacheTTL:
    """Tests for TTL expiration behavior."""

    def test_ttl_not_expired(self):
        cache: ValidationCache[str] = ValidationCache(ttl_seconds=300)
        cache.set("key1", "value1")

        # Immediately should work
        assert cache.get("key1") == "value1"

    def test_ttl_expired(self):
        cache: ValidationCache[str] = ValidationCache(ttl_seconds=1)
        cache.set("key1", "value1")

        # Mock time to simulate expiration
        future = datetime.now(UTC) + timedelta(seconds=2)
        with patch("src.cache.validation_cache.datetime") as mock_dt:
            mock_dt.now.return_value = future

            assert cache.get("key1") is None

    def test_contains_expired_key(self):
        cache: ValidationCache[str] = ValidationCache(ttl_seconds=1)
        cache.set("key1", "value1")

        future = datetime.now(UTC) + timedelta(seconds=2)
        with patch("src.cache.validation_cache.datetime") as mock_dt:
            mock_dt.now.return_value = future

            assert "key1" not in cache


class TestValidationCacheLRU:
    """Tests for LRU eviction policy."""

    def test_lru_eviction_on_capacity(self):
        cache: ValidationCache[str] = ValidationCache(max_entries=3)

        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")
        cache.set("key4", "value4")  # Should evict key1

        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"
        assert cache.get("key3") == "value3"
        assert cache.get("key4") == "value4"

    def test_lru_access_updates_order(self):
        cache: ValidationCache[str] = ValidationCache(max_entries=3)

        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")

        # Access key1 to make it recently used
        _ = cache.get("key1")

        cache.set("key4", "value4")  # Should evict key2 (oldest unused)

        assert cache.get("key1") == "value1"
        assert cache.get("key2") is None
        assert cache.get("key3") == "value3"
        assert cache.get("key4") == "value4"

    def test_eviction_count_tracked(self):
        cache: ValidationCache[str] = ValidationCache(max_entries=2)

        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")  # Evicts key1
        cache.set("key4", "value4")  # Evicts key2

        metrics = cache.get_metrics()
        assert metrics.evictions == 2


class TestValidationCacheMetrics:
    """Tests for cache metrics tracking."""

    def test_hit_tracking(self):
        cache: ValidationCache[str] = ValidationCache()
        cache.set("key1", "value1")

        cache.get("key1")  # Hit
        cache.get("key1")  # Hit

        metrics = cache.get_metrics()
        assert metrics.hits == 2

    def test_miss_tracking(self):
        cache: ValidationCache[str] = ValidationCache()

        cache.get("nonexistent1")
        cache.get("nonexistent2")

        metrics = cache.get_metrics()
        assert metrics.misses == 2

    def test_combined_metrics(self):
        cache: ValidationCache[str] = ValidationCache()
        cache.set("key1", "value1")

        cache.get("key1")  # Hit
        cache.get("key1")  # Hit
        cache.get("key2")  # Miss

        metrics = cache.get_metrics()

        assert metrics.hits == 2
        assert metrics.misses == 1
        assert metrics.hit_rate == pytest.approx(0.666, rel=0.01)

    def test_metrics_returns_copy(self):
        cache: ValidationCache[str] = ValidationCache()
        cache.set("key1", "value1")
        cache.get("key1")

        metrics1 = cache.get_metrics()
        cache.get("key1")
        metrics2 = cache.get_metrics()

        # metrics1 should not be updated
        assert metrics1.hits == 1
        assert metrics2.hits == 2


class TestValidationCacheInvalidatePattern:
    """Tests for pattern-based invalidation."""

    def test_invalidate_pattern_matches(self):
        cache: ValidationCache[str] = ValidationCache()

        cache.set("campaign-1:check1", "a")
        cache.set("campaign-1:check2", "b")
        cache.set("campaign-2:check1", "c")

        count = cache.invalidate_pattern("campaign-1:")

        assert count == 2
        assert cache.get("campaign-1:check1") is None
        assert cache.get("campaign-1:check2") is None
        assert cache.get("campaign-2:check1") == "c"

    def test_invalidate_pattern_no_matches(self):
        cache: ValidationCache[str] = ValidationCache()
        cache.set("key1", "value1")

        count = cache.invalidate_pattern("nonexistent:")

        assert count == 0
        assert cache.get("key1") == "value1"


class TestValidationCacheThreadSafety:
    """Tests for thread safety."""

    def test_concurrent_writes(self):
        cache: ValidationCache[int] = ValidationCache(max_entries=1000)
        errors: list[Exception] = []

        def writer(thread_id: int):
            try:
                for i in range(100):
                    cache.set(f"key-{thread_id}-{i}", i)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

    def test_concurrent_reads_and_writes(self):
        cache: ValidationCache[int] = ValidationCache(max_entries=1000)
        errors: list[Exception] = []

        # Pre-populate cache
        for i in range(50):
            cache.set(f"key{i}", i)

        def writer():
            try:
                for i in range(100):
                    cache.set(f"writer-key{i}", i)
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for i in range(100):
                    cache.get(f"key{i % 50}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer) for _ in range(3)] + [
            threading.Thread(target=reader) for _ in range(3)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

    def test_concurrent_invalidation(self):
        cache: ValidationCache[int] = ValidationCache(max_entries=1000)
        errors: list[Exception] = []

        # Pre-populate
        for i in range(100):
            cache.set(f"key{i}", i)

        def invalidator():
            try:
                for i in range(100):
                    cache.invalidate(f"key{i}")
            except Exception as e:
                errors.append(e)

        def setter():
            try:
                for i in range(100):
                    cache.set(f"key{i}", i * 2)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=invalidator) for _ in range(2)] + [
            threading.Thread(target=setter) for _ in range(2)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


class TestValidationCacheGenericTypes:
    """Tests for generic type support."""

    def test_bool_cache(self):
        cache: ValidationCache[bool] = ValidationCache()
        cache.set("valid", True)
        cache.set("invalid", False)

        assert cache.get("valid") is True
        assert cache.get("invalid") is False

    def test_dict_cache(self):
        cache: ValidationCache[dict] = ValidationCache()
        data = {"phase": "C", "confidence": 0.85}
        cache.set("result", data)

        assert cache.get("result") == data

    def test_none_value(self):
        # None as a value should be distinguishable from cache miss
        # This is a limitation - cache.get returns None for both
        cache: ValidationCache[str | None] = ValidationCache()
        cache.set("key", None)

        # Contains check works
        assert "key" in cache
