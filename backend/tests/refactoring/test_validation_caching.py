"""
Validation Caching Tests (Story 22.14 - AC3)

Tests the validation cache system:
- Cache hit returns cached value
- Cache miss triggers calculation
- TTL expiration invalidates cache
- LRU eviction at max entries (100)
- Cache invalidation on state change
- Thread safety with concurrent access

These tests validate the Campaign._validation_cache system
before refactoring work begins.
"""

import queue
import threading
from datetime import UTC, datetime, timedelta

from src.backtesting.intraday_campaign_detector import (
    VALIDATION_CACHE_MAX_ENTRIES,
    Campaign,
)


class TestCacheHitMiss:
    """Test cache hit/miss behavior (AC3)."""

    def test_cache_miss_returns_none(self, sample_campaign: Campaign):
        """AC3: Cache miss should return None."""
        result = sample_campaign.get_cached_validation()
        assert result is None

    def test_cache_hit_returns_cached_value(self, sample_campaign: Campaign):
        """AC3: Cache hit should return cached validation result."""
        # Set cached value
        sample_campaign.set_cached_validation(True)

        # Should return cached value
        result = sample_campaign.get_cached_validation()
        assert result is True

    def test_cache_hit_returns_false_value(self, sample_campaign: Campaign):
        """AC3: Cache should properly store and return False values."""
        # Set cached value to False
        sample_campaign.set_cached_validation(False)

        # Should return False (not None)
        result = sample_campaign.get_cached_validation()
        assert result is False

    def test_multiple_cache_entries(self, sample_campaign: Campaign, sample_ar_pattern):
        """AC3: Multiple patterns should create distinct cache entries."""
        # Cache result for current pattern
        sample_campaign.set_cached_validation(True)

        # Add another pattern (changes hash)
        original_hash = sample_campaign._get_pattern_sequence_hash()
        sample_campaign.patterns.append(sample_ar_pattern)
        new_hash = sample_campaign._get_pattern_sequence_hash()

        # Hashes should differ
        assert original_hash != new_hash

        # New pattern sequence should be cache miss
        result = sample_campaign.get_cached_validation()
        assert result is None


class TestCacheTTLExpiration:
    """Test cache TTL expiration (AC3)."""

    def test_cache_expires_after_ttl(self, sample_campaign: Campaign):
        """AC3: Cache entry should expire after TTL."""
        # Set cached value
        sample_campaign.set_cached_validation(True)

        # Verify cache hit
        assert sample_campaign.get_cached_validation() is True

        # Mock expired timestamp
        cache_key = sample_campaign._get_pattern_sequence_hash()
        sample_campaign._validation_cache[cache_key]["timestamp"] = datetime.now(UTC) - timedelta(
            seconds=sample_campaign._cache_ttl_seconds + 1
        )

        # Should be cache miss (expired)
        result = sample_campaign.get_cached_validation()
        assert result is None

    def test_cache_valid_before_ttl(self, sample_campaign: Campaign):
        """AC3: Cache entry should be valid before TTL expires."""
        # Set cached value
        sample_campaign.set_cached_validation(True)

        # Set timestamp to just before expiration
        cache_key = sample_campaign._get_pattern_sequence_hash()
        sample_campaign._validation_cache[cache_key]["timestamp"] = datetime.now(UTC) - timedelta(
            seconds=sample_campaign._cache_ttl_seconds - 10
        )

        # Should still be valid
        result = sample_campaign.get_cached_validation()
        assert result is True

    def test_expired_entry_is_deleted(self, sample_campaign: Campaign):
        """AC3: Expired entries should be removed from cache."""
        # Set cached value
        sample_campaign.set_cached_validation(True)
        cache_key = sample_campaign._get_pattern_sequence_hash()

        # Verify entry exists
        assert cache_key in sample_campaign._validation_cache

        # Expire the entry
        sample_campaign._validation_cache[cache_key]["timestamp"] = datetime.now(UTC) - timedelta(
            seconds=sample_campaign._cache_ttl_seconds + 1
        )

        # Access triggers deletion
        sample_campaign.get_cached_validation()

        # Entry should be deleted
        assert cache_key not in sample_campaign._validation_cache


class TestLRUEviction:
    """Test LRU eviction at max entries (AC3)."""

    def test_lru_eviction_at_max_entries(self, sample_campaign: Campaign):
        """AC3: LRU eviction should occur at max entries (100)."""
        assert VALIDATION_CACHE_MAX_ENTRIES == 100

        # Fill cache to max
        for i in range(VALIDATION_CACHE_MAX_ENTRIES):
            cache_key = f"test-key-{i}"
            sample_campaign._validation_cache[cache_key] = {
                "result": True,
                "timestamp": datetime.now(UTC) - timedelta(seconds=i),
            }

        # Verify cache is at max
        assert len(sample_campaign._validation_cache) == VALIDATION_CACHE_MAX_ENTRIES

        # Add one more entry (triggers eviction)
        sample_campaign.set_cached_validation(True)

        # Should still be at max (oldest evicted)
        assert len(sample_campaign._validation_cache) <= VALIDATION_CACHE_MAX_ENTRIES

    def test_oldest_entry_evicted(self, sample_campaign: Campaign):
        """AC3: Oldest entry should be evicted on overflow."""
        # Add entries with known timestamps
        oldest_key = "oldest-entry"
        sample_campaign._validation_cache[oldest_key] = {
            "result": True,
            "timestamp": datetime.now(UTC) - timedelta(hours=2),  # Oldest
        }

        for i in range(VALIDATION_CACHE_MAX_ENTRIES - 1):
            cache_key = f"newer-key-{i}"
            sample_campaign._validation_cache[cache_key] = {
                "result": True,
                "timestamp": datetime.now(UTC) - timedelta(minutes=i),
            }

        # Verify cache is at max
        assert len(sample_campaign._validation_cache) == VALIDATION_CACHE_MAX_ENTRIES
        assert oldest_key in sample_campaign._validation_cache

        # Add new entry (triggers eviction)
        sample_campaign.set_cached_validation(True)

        # Oldest entry should be evicted
        assert oldest_key not in sample_campaign._validation_cache


class TestCacheInvalidation:
    """Test cache invalidation on state change (AC3)."""

    def test_invalidate_clears_cache(self, sample_campaign: Campaign):
        """AC3: invalidate_validation_cache should clear all entries."""
        # Add multiple cache entries
        sample_campaign._validation_cache["key1"] = {
            "result": True,
            "timestamp": datetime.now(UTC),
        }
        sample_campaign._validation_cache["key2"] = {
            "result": False,
            "timestamp": datetime.now(UTC),
        }

        # Verify entries exist
        assert len(sample_campaign._validation_cache) == 2

        # Invalidate cache
        sample_campaign.invalidate_validation_cache()

        # Cache should be empty
        assert len(sample_campaign._validation_cache) == 0

    def test_cache_invalid_after_pattern_change(self, sample_campaign: Campaign, sample_ar_pattern):
        """AC3: Cache should be invalidated when patterns change."""
        # Cache current validation
        sample_campaign.set_cached_validation(True)

        # Verify cache hit
        assert sample_campaign.get_cached_validation() is True

        # Add pattern (changes hash, effectively invalidates)
        sample_campaign.patterns.append(sample_ar_pattern)

        # Should be cache miss (different hash)
        result = sample_campaign.get_cached_validation()
        assert result is None


class TestPatternSequenceHash:
    """Test pattern sequence hash generation."""

    def test_hash_changes_with_patterns(self, sample_campaign: Campaign, sample_ar_pattern):
        """Hash should change when patterns are added."""
        hash1 = sample_campaign._get_pattern_sequence_hash()

        sample_campaign.patterns.append(sample_ar_pattern)
        hash2 = sample_campaign._get_pattern_sequence_hash()

        assert hash1 != hash2

    def test_hash_consistent_for_same_patterns(self, sample_campaign: Campaign):
        """Hash should be consistent for same pattern sequence."""
        hash1 = sample_campaign._get_pattern_sequence_hash()
        hash2 = sample_campaign._get_pattern_sequence_hash()

        assert hash1 == hash2

    def test_hash_includes_pattern_type(
        self, sample_campaign: Campaign, sample_ar_pattern, sample_sos_pattern
    ):
        """Hash should differ based on pattern type."""
        # Add AR pattern
        sample_campaign.patterns.append(sample_ar_pattern)
        hash_with_ar = sample_campaign._get_pattern_sequence_hash()

        # Create new campaign with SOS instead
        campaign2 = Campaign(
            campaign_id="test-2",
            patterns=[sample_campaign.patterns[0], sample_sos_pattern],
            timeframe="1h",
        )
        hash_with_sos = campaign2._get_pattern_sequence_hash()

        # Hashes should differ
        assert hash_with_ar != hash_with_sos


class TestThreadSafety:
    """Test thread safety with concurrent access (AC3)."""

    def test_concurrent_cache_reads(self, sample_campaign: Campaign):
        """AC3: Concurrent reads should not cause issues."""
        # Set cached value
        sample_campaign.set_cached_validation(True)

        results: queue.Queue = queue.Queue()
        errors: queue.Queue = queue.Queue()

        def read_cache():
            try:
                result = sample_campaign.get_cached_validation()
                results.put(result)
            except Exception as e:
                errors.put(e)

        # Launch multiple threads
        threads = [threading.Thread(target=read_cache) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have no errors
        assert errors.empty()
        # All reads should return True
        results_list = []
        while not results.empty():
            results_list.append(results.get())
        assert all(r is True for r in results_list)

    def test_concurrent_cache_writes(self, sample_campaign: Campaign):
        """AC3: Concurrent writes should not cause corruption."""
        errors: queue.Queue = queue.Queue()

        def write_cache(value):
            try:
                sample_campaign.set_cached_validation(value)
            except Exception as e:
                errors.put(e)

        # Launch multiple write threads
        threads = []
        for i in range(10):
            t = threading.Thread(target=write_cache, args=(i % 2 == 0,))
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have no errors
        assert errors.empty()
        # Cache should have an entry (last write wins)
        assert sample_campaign.get_cached_validation() is not None

    def test_concurrent_invalidate(self, sample_campaign: Campaign):
        """AC3: Concurrent invalidation should not cause issues."""
        # Set cached value
        sample_campaign.set_cached_validation(True)

        errors: queue.Queue = queue.Queue()

        def invalidate():
            try:
                sample_campaign.invalidate_validation_cache()
            except Exception as e:
                errors.put(e)

        # Launch multiple invalidation threads
        threads = [threading.Thread(target=invalidate) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have no errors
        assert errors.empty()
        # Cache should be empty
        assert len(sample_campaign._validation_cache) == 0


class TestCacheConfigurationConstants:
    """Test cache configuration constants."""

    def test_max_entries_constant(self):
        """Max entries should be 100."""
        assert VALIDATION_CACHE_MAX_ENTRIES == 100

    def test_default_ttl_is_300_seconds(self):
        """Default TTL should be 300 seconds (5 minutes)."""
        campaign = Campaign()
        assert campaign._cache_ttl_seconds == 300

    def test_cache_initialized_empty(self):
        """New campaigns should have empty cache."""
        campaign = Campaign()
        assert len(campaign._validation_cache) == 0
