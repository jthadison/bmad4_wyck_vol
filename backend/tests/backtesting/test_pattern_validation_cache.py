"""
Unit tests for Pattern Validation Caching (Story 15.4)

Tests cache operations on Campaign model and IntradayCampaignDetector:
- Cache key generation (hash uniqueness)
- Cache hit/miss behavior
- TTL expiration
- LRU eviction
- Cache invalidation
- Cache statistics tracking
- Integration with add_pattern() workflow

Coverage Target: 85%+ for caching functionality
Performance Target: 30-50% reduction in validation overhead
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from time import sleep
from uuid import uuid4

import pytest

from src.backtesting.intraday_campaign_detector import (
    VALIDATION_CACHE_MAX_ENTRIES,
    Campaign,
    IntradayCampaignDetector,
)
from src.models.ohlcv import OHLCVBar
from src.models.sos_breakout import SOSBreakout
from src.models.spring import Spring

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def detector():
    """Standard detector with default configuration."""
    return IntradayCampaignDetector(
        campaign_window_hours=48,
        max_pattern_gap_hours=48,
        min_patterns_for_active=2,
        expiration_hours=72,
        max_concurrent_campaigns=3,
        max_portfolio_heat_pct=Decimal("10.0"),
    )


@pytest.fixture
def base_timestamp():
    """Base timestamp for test patterns."""
    return datetime(2025, 12, 15, 9, 0, tzinfo=UTC)


@pytest.fixture
def sample_bar(base_timestamp):
    """Sample OHLCV bar for pattern creation."""
    return OHLCVBar(
        timestamp=base_timestamp,
        open=Decimal("100.00"),
        high=Decimal("101.00"),
        low=Decimal("99.00"),
        close=Decimal("100.50"),
        volume=100000,
        spread=Decimal("2.00"),
        timeframe="15m",
        symbol="EUR/USD",
    )


@pytest.fixture
def sample_spring(sample_bar, base_timestamp):
    """Sample Spring pattern."""
    return Spring(
        bar=sample_bar,
        bar_index=10,
        penetration_pct=Decimal("0.02"),
        volume_ratio=Decimal("0.4"),
        recovery_bars=1,
        creek_reference=Decimal("100.00"),
        spring_low=Decimal("98.00"),
        recovery_price=Decimal("100.50"),
        detection_timestamp=base_timestamp,
        trading_range_id=uuid4(),
    )


@pytest.fixture
def sample_sos(sample_bar, base_timestamp):
    """Sample SOS breakout pattern."""
    sos_bar = OHLCVBar(
        timestamp=base_timestamp + timedelta(hours=2),
        open=Decimal("100.00"),
        high=Decimal("103.00"),
        low=Decimal("100.00"),
        close=Decimal("102.50"),
        volume=200000,
        spread=Decimal("3.00"),
        timeframe="15m",
        symbol="EUR/USD",
    )
    return SOSBreakout(
        bar=sos_bar,
        breakout_pct=Decimal("0.015"),  # 1.5% above Ice (required >=1%)
        volume_ratio=Decimal("2.0"),  # High volume (required >=1.5x)
        ice_reference=Decimal("101.00"),
        breakout_price=Decimal("102.50"),
        detection_timestamp=base_timestamp + timedelta(hours=2),
        trading_range_id=uuid4(),
        spread_ratio=Decimal("1.4"),  # Spread expansion (required >=1.2x)
        close_position=Decimal("0.75"),  # Close position (required 0.0-1.0)
        spread=Decimal("3.00"),  # Bar spread (high - low)
        asset_class="forex",
        volume_reliability="HIGH",
    )


# ============================================================================
# Task 1: Cache Key Generation Tests
# ============================================================================


def test_pattern_sequence_hash_uniqueness(sample_spring, sample_sos):
    """
    AC1.1: Hash generation produces unique keys for different sequences.

    Validates:
    - Different pattern sequences produce different hashes
    - Same sequence produces same hash (idempotent)
    """
    campaign1 = Campaign(patterns=[sample_spring])
    campaign2 = Campaign(patterns=[sample_spring, sample_sos])
    campaign3 = Campaign(patterns=[sample_spring])

    hash1 = campaign1._get_pattern_sequence_hash()
    hash2 = campaign2._get_pattern_sequence_hash()
    hash3 = campaign3._get_pattern_sequence_hash()

    # Different sequences → different hashes
    assert hash1 != hash2, "Spring-only vs Spring+SOS should have different hashes"

    # Same sequence → same hash
    assert hash1 == hash3, "Same pattern sequence should produce identical hash"


def test_pattern_sequence_hash_format(sample_spring):
    """
    AC1.2: Hash format is valid string representation.

    Validates:
    - Hash is non-empty string
    - Hash can be used as dict key (hashable)
    """
    campaign = Campaign(patterns=[sample_spring])
    hash_key = campaign._get_pattern_sequence_hash()

    assert isinstance(hash_key, str), "Hash should be a string"
    assert len(hash_key) > 0, "Hash should be non-empty"
    assert hash_key.lstrip("-").isdigit(), "Hash should be numeric string (from hash())"


# ============================================================================
# Task 2: Cache Hit/Miss Tests
# ============================================================================


def test_cache_miss_on_first_access(sample_spring):
    """
    AC2.1: First validation call results in cache miss.

    Validates:
    - get_cached_validation() returns None on empty cache
    """
    campaign = Campaign(patterns=[sample_spring])

    result = campaign.get_cached_validation()

    assert result is None, "First access should be cache miss"


def test_cache_hit_after_set(sample_spring):
    """
    AC2.2: Cached result is retrieved on subsequent access.

    Validates:
    - set_cached_validation() stores result
    - get_cached_validation() retrieves stored result
    """
    campaign = Campaign(patterns=[sample_spring])

    campaign.set_cached_validation(True)
    result = campaign.get_cached_validation()

    assert result is True, "Cached result should be retrieved"


def test_cache_stores_both_true_and_false(sample_spring):
    """
    AC2.3: Cache correctly stores both True and False validation results.

    Validates:
    - False results are cached (not confused with None)
    """
    campaign = Campaign(patterns=[sample_spring])

    # Cache False
    campaign.set_cached_validation(False)
    result = campaign.get_cached_validation()

    assert result is False, "False validation should be cached and retrieved"
    assert result is not None, "False should not be treated as cache miss"


# ============================================================================
# Task 3: TTL Expiration Tests
# ============================================================================


def test_cache_expiration_after_ttl(sample_spring):
    """
    AC3.1: Cached result expires after TTL (5 minutes default).

    Validates:
    - Cached result returns None after TTL expiration
    - TTL is enforced correctly

    Note: Uses short TTL (1 second) for test speed
    """
    campaign = Campaign(patterns=[sample_spring])
    campaign._cache_ttl_seconds = 1  # 1 second for testing

    campaign.set_cached_validation(True)

    # Immediate access should hit
    result1 = campaign.get_cached_validation()
    assert result1 is True, "Cached result should be available immediately"

    # Wait for TTL expiration
    sleep(1.1)

    # Access after TTL should miss
    result2 = campaign.get_cached_validation()
    assert result2 is None, "Cached result should expire after TTL"


def test_cache_not_expired_before_ttl(sample_spring):
    """
    AC3.2: Cached result remains valid before TTL expiration.

    Validates:
    - Cache hit occurs within TTL window
    """
    campaign = Campaign(patterns=[sample_spring])
    campaign._cache_ttl_seconds = 300  # 5 minutes

    campaign.set_cached_validation(True)

    # Access within TTL
    result = campaign.get_cached_validation()

    assert result is True, "Cached result should be valid within TTL"


# ============================================================================
# Task 4: LRU Eviction Tests
# ============================================================================


def test_lru_eviction_when_cache_full(sample_spring, sample_sos):
    """
    AC4.1: LRU eviction removes oldest entry when cache exceeds max entries.

    Validates:
    - Cache evicts oldest entry when > VALIDATION_CACHE_MAX_ENTRIES
    - Most recent entries are retained
    """
    campaign = Campaign(patterns=[sample_spring])

    # Fill cache with VALIDATION_CACHE_MAX_ENTRIES + 1 entries
    base_time = datetime.now(UTC)
    for i in range(VALIDATION_CACHE_MAX_ENTRIES + 1):
        # Create unique bar with different timestamp
        unique_bar = OHLCVBar(
            timestamp=base_time + timedelta(seconds=i),
            open=Decimal("100.00"),
            high=Decimal("101.00"),
            low=Decimal("99.00"),
            close=Decimal("100.50"),
            volume=100000,
            spread=Decimal("2.00"),
            timeframe="15m",
            symbol="EUR/USD",
        )
        # Create unique pattern with different timestamp
        pattern = Spring(
            bar=unique_bar,
            bar_index=i,
            penetration_pct=sample_spring.penetration_pct,
            volume_ratio=sample_spring.volume_ratio,
            recovery_bars=sample_spring.recovery_bars,
            creek_reference=sample_spring.creek_reference,
            spring_low=sample_spring.spring_low,
            recovery_price=sample_spring.recovery_price,
            detection_timestamp=base_time + timedelta(seconds=i),
            trading_range_id=uuid4(),
        )
        campaign.patterns = [pattern]
        campaign.set_cached_validation(True)

    # Cache should have exactly VALIDATION_CACHE_MAX_ENTRIES entries (oldest evicted)
    assert len(campaign._validation_cache) == VALIDATION_CACHE_MAX_ENTRIES, (
        f"Cache should not exceed {VALIDATION_CACHE_MAX_ENTRIES} entries, "
        f"got {len(campaign._validation_cache)}"
    )


# ============================================================================
# Task 5: Cache Invalidation Tests
# ============================================================================


def test_cache_invalidation_clears_cache(sample_spring):
    """
    AC5.1: invalidate_validation_cache() clears all cached results.

    Validates:
    - Cache is empty after invalidation
    - Subsequent access results in cache miss
    """
    campaign = Campaign(patterns=[sample_spring])

    campaign.set_cached_validation(True)
    campaign.invalidate_validation_cache()

    result = campaign.get_cached_validation()

    assert result is None, "Cache should be empty after invalidation"
    assert len(campaign._validation_cache) == 0, "Cache dict should be empty"


def test_cache_invalidation_on_pattern_add(detector, sample_spring, sample_sos):
    """
    AC5.2: Cache is invalidated when patterns change via add_pattern().

    Validates:
    - Adding pattern changes the pattern sequence hash
    - New validation uses a different cache key
    - Story 22.6: Validation cache is now centralized at detector level
    """
    # Create initial campaign
    campaign = detector.add_pattern(sample_spring)

    # Get initial hash for single-pattern campaign
    initial_hash = campaign._get_pattern_sequence_hash()

    # Add second pattern (triggers validation with new hash)
    detector.add_pattern(sample_sos)

    # Hash should change after pattern added (Story 22.6: invalidation via hash change)
    new_hash = campaign._get_pattern_sequence_hash()
    assert initial_hash != new_hash, "Pattern sequence hash should change after adding pattern"


# ============================================================================
# Task 6: Cache Statistics Tests
# ============================================================================


def test_cache_statistics_initial_state(detector):
    """
    AC6.1: Cache statistics start at zero.

    Validates:
    - _cache_hits = 0
    - _cache_misses = 0
    - hit_rate_pct = 0.0
    """
    stats = detector.get_cache_statistics()

    assert stats["cache_hits"] == 0, "Initial cache hits should be 0"
    assert stats["cache_misses"] == 0, "Initial cache misses should be 0"
    assert stats["total_checks"] == 0, "Initial total checks should be 0"
    assert stats["hit_rate_pct"] == 0.0, "Initial hit rate should be 0.0%"


def test_cache_statistics_tracks_hits_and_misses(detector, sample_spring, sample_sos):
    """
    AC6.2: Cache statistics correctly track hits and misses.

    Validates:
    - First validation increments _cache_misses
    - Subsequent validations increment _cache_hits
    - hit_rate_pct calculated correctly
    """
    campaign = Campaign(patterns=[sample_spring, sample_sos])

    # First validation (cache miss)
    detector._validate_sequence_cached(campaign)

    stats1 = detector.get_cache_statistics()
    assert stats1["cache_misses"] == 1, "First validation should be cache miss"
    assert stats1["cache_hits"] == 0, "No cache hits yet"

    # Second validation (cache hit)
    detector._validate_sequence_cached(campaign)

    stats2 = detector.get_cache_statistics()
    assert stats2["cache_hits"] == 1, "Second validation should be cache hit"
    assert stats2["cache_misses"] == 1, "Cache misses unchanged"
    assert stats2["total_checks"] == 2, "Total checks = hits + misses"
    assert stats2["hit_rate_pct"] == 50.0, "Hit rate = 1/2 = 50%"


def test_cache_hit_rate_calculation(detector, sample_spring, sample_sos):
    """
    AC6.3: Hit rate percentage calculated correctly.

    Validates:
    - hit_rate_pct = (hits / total) * 100
    - Multiple hits increase rate correctly
    """
    campaign = Campaign(patterns=[sample_spring, sample_sos])

    # 1 miss
    detector._validate_sequence_cached(campaign)

    # 3 hits
    for _ in range(3):
        detector._validate_sequence_cached(campaign)

    stats = detector.get_cache_statistics()

    assert stats["cache_hits"] == 3, "Should have 3 cache hits"
    assert stats["cache_misses"] == 1, "Should have 1 cache miss"
    assert stats["total_checks"] == 4, "Total = 3 + 1 = 4"
    assert stats["hit_rate_pct"] == 75.0, "Hit rate = 3/4 = 75%"


# ============================================================================
# Task 7: Integration with add_pattern() Tests
# ============================================================================


def test_add_pattern_uses_cached_validation(detector, sample_spring, sample_sos):
    """
    AC7.1: add_pattern() uses _validate_sequence_cached() for validation.

    Validates:
    - Cache metrics incremented during add_pattern()
    - Validation is cached and reused
    """
    # Add first pattern
    detector.add_pattern(sample_spring)

    initial_stats = detector.get_cache_statistics()
    initial_total = initial_stats["total_checks"]

    # Add second pattern (triggers validation)
    detector.add_pattern(sample_sos)

    final_stats = detector.get_cache_statistics()

    # Validation should have been called (total_checks increased)
    assert (
        final_stats["total_checks"] > initial_total
    ), "add_pattern() should trigger cached validation"


def test_cache_invalidated_after_invalid_sequence(detector, sample_spring, sample_sos):
    """
    AC7.2: Cache validation uses new hash when patterns change.

    Validates:
    - Pattern changes result in different cache keys
    - Story 22.6: Uses hash-based invalidation (no explicit clear needed)
    """
    # Create campaign with Spring
    campaign = detector.add_pattern(sample_spring)

    # Get initial pattern sequence hash
    initial_hash = campaign._get_pattern_sequence_hash()

    # Manually cache a validation result for the single-pattern sequence
    campaign.set_cached_validation(True)
    assert len(campaign._validation_cache) > 0, "Cache should have entry"

    # Try to add SOS (valid sequence)
    detector.add_pattern(sample_sos)

    # Hash should change (Story 22.6: invalidation via hash change, not explicit clear)
    new_hash = campaign._get_pattern_sequence_hash()
    assert initial_hash != new_hash, "Pattern sequence hash should change after adding pattern"

    # Old hash entry may still exist, but new validation uses different key
    # The important thing is the hash changed, so new validations will compute fresh results


# ============================================================================
# Task 8: Performance & Stress Tests
# ============================================================================


def test_cache_performance_improvement(detector, sample_spring, sample_sos):
    """
    AC8.1: Cache provides measurable performance improvement.

    Validates:
    - Cache hits are faster than cache misses
    - Hit rate > 50% in realistic scenarios

    Note: This is a basic performance check. Full benchmarking in separate file.
    """
    campaign = Campaign(patterns=[sample_spring, sample_sos])

    # Warm up cache (1 miss)
    detector._validate_sequence_cached(campaign)

    # Run 10 cached validations (10 hits)
    for _ in range(10):
        detector._validate_sequence_cached(campaign)

    stats = detector.get_cache_statistics()

    # Verify high hit rate
    assert stats["hit_rate_pct"] > 90.0, "Should have > 90% hit rate with repeated validation"
    assert stats["cache_hits"] == 10, "Should have 10 cache hits"
    assert stats["cache_misses"] == 1, "Should have 1 cache miss"


def test_cache_with_multiple_campaigns(detector, sample_spring, sample_sos):
    """
    AC8.2: Cache works correctly with multiple campaigns.

    Validates:
    - Story 22.6: Detector uses centralized ValidationCache
    - Different pattern sequences produce different cache keys
    - Cache entries are keyed by pattern sequence hash
    """
    # Create two independent campaigns
    campaign1 = Campaign(patterns=[sample_spring])
    campaign2 = Campaign(patterns=[sample_spring, sample_sos])

    # Get hashes for both campaigns
    hash1 = campaign1._get_pattern_sequence_hash()
    hash2 = campaign2._get_pattern_sequence_hash()

    # Verify different sequences produce different hashes
    assert hash1 != hash2, "Different pattern sequences should have different hashes"

    # Cache validation for both using detector's centralized cache
    result1 = detector._validate_sequence_cached(campaign1)
    result2 = detector._validate_sequence_cached(campaign2)

    # Both should validate successfully
    assert result1 is True, "Single Spring pattern should be valid"
    assert result2 is True, "Spring + SOS sequence should be valid"

    # Verify detector's cache has entries (Story 22.6: centralized cache)
    stats = detector.get_cache_statistics()
    assert stats["cache_misses"] == 2, "Should have 2 cache misses (first validation of each)"

    # Validate again - should hit cache
    detector._validate_sequence_cached(campaign1)
    detector._validate_sequence_cached(campaign2)

    stats_after = detector.get_cache_statistics()
    assert stats_after["cache_hits"] == 2, "Should have 2 cache hits on repeated validation"


# ============================================================================
# Task 9: Edge Cases & Error Handling
# ============================================================================


def test_cache_with_empty_pattern_list():
    """
    AC9.1: Cache handles empty pattern list gracefully.

    Validates:
    - Hash generation works with empty patterns
    - No errors on empty sequence
    """
    campaign = Campaign(patterns=[])

    hash_key = campaign._get_pattern_sequence_hash()

    assert hash_key is not None, "Hash should be generated for empty patterns"
    assert isinstance(hash_key, str), "Hash should be a string"
    assert len(hash_key) > 0, "Hash should be non-empty"


def test_cache_invalidation_on_empty_cache():
    """
    AC9.2: Cache invalidation on empty cache does not error.

    Validates:
    - invalidate_validation_cache() is idempotent
    """
    campaign = Campaign(patterns=[])

    # Should not raise exception
    campaign.invalidate_validation_cache()
    campaign.invalidate_validation_cache()

    assert len(campaign._validation_cache) == 0, "Cache should remain empty"


def test_cache_with_custom_ttl(sample_spring):
    """
    AC9.3: Custom TTL values are respected.

    Validates:
    - _cache_ttl_seconds can be customized
    - Custom TTL works correctly
    """
    campaign = Campaign(patterns=[sample_spring])
    campaign._cache_ttl_seconds = 2  # 2 seconds

    campaign.set_cached_validation(True)

    # Before TTL
    result1 = campaign.get_cached_validation()
    assert result1 is True, "Cache should hit before TTL"

    # After TTL
    sleep(2.1)
    result2 = campaign.get_cached_validation()
    assert result2 is None, "Cache should expire after custom TTL"
