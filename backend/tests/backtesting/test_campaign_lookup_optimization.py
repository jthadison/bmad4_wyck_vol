"""
Unit tests for Campaign Lookup Optimization (Story 15.3).

Tests cover:
1. Index consistency after operations
2. State transitions properly update indexes
3. Backward compatibility (campaigns property)
4. O(1) lookup performance
5. Index maintenance methods

Performance Notes:
    For more reliable CI performance testing, consider using pytest-benchmark:
    ```
    pip install pytest-benchmark
    pytest --benchmark-only tests/backtesting/test_campaign_lookup_optimization.py
    ```
    pytest-benchmark provides statistical analysis, warmup, and calibration
    for more accurate performance measurements across different environments.

Author: Story 15.3 Implementation
"""

import warnings
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from src.backtesting.intraday_campaign_detector import (
    Campaign,
    CampaignState,
    ExitReason,
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


def create_spring(sample_bar, base_timestamp, bar_index=10):
    """Helper to create Spring pattern."""
    return Spring(
        bar=sample_bar,
        bar_index=bar_index,
        penetration_pct=Decimal("0.02"),
        volume_ratio=Decimal("0.4"),
        recovery_bars=1,
        creek_reference=Decimal("100.00"),
        spring_low=Decimal("98.00"),
        recovery_price=Decimal("100.50"),
        detection_timestamp=base_timestamp,
        trading_range_id=uuid4(),
    )


def create_sos(base_timestamp, bar_index=20):
    """Helper to create SOS pattern."""
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
        breakout_pct=Decimal("0.025"),  # 2.5% above Ice
        volume_ratio=Decimal("2.0"),  # High volume (good)
        ice_reference=Decimal("100.00"),
        breakout_price=Decimal("102.50"),
        detection_timestamp=base_timestamp + timedelta(hours=2),
        trading_range_id=uuid4(),
        spread_ratio=Decimal("1.5"),
        close_position=Decimal("0.83"),
        spread=Decimal("3.00"),
    )


# ============================================================================
# Test: Index Consistency
# ============================================================================


class TestIndexConsistency:
    """Test that indexes remain consistent after operations."""

    def test_empty_detector_has_empty_indexes(self, detector):
        """Test newly created detector has empty indexes."""
        assert len(detector._campaigns_by_id) == 0
        assert len(detector._campaigns_by_state[CampaignState.FORMING]) == 0
        assert len(detector._campaigns_by_state[CampaignState.ACTIVE]) == 0
        assert len(detector._active_time_windows) == 0

    def test_add_pattern_updates_id_index(self, detector, sample_bar, base_timestamp):
        """Test that adding a pattern updates the ID index."""
        spring = create_spring(sample_bar, base_timestamp)
        campaign = detector.add_pattern(spring)

        assert campaign is not None
        assert campaign.campaign_id in detector._campaigns_by_id
        assert detector._campaigns_by_id[campaign.campaign_id] is campaign

    def test_add_pattern_updates_state_index(self, detector, sample_bar, base_timestamp):
        """Test that adding a pattern updates the state index."""
        spring = create_spring(sample_bar, base_timestamp)
        campaign = detector.add_pattern(spring)

        assert campaign is not None
        assert campaign.campaign_id in detector._campaigns_by_state[CampaignState.FORMING]

    def test_state_transition_updates_indexes(self, detector, sample_bar, base_timestamp):
        """Test that state transitions update both state indexes."""
        # Add first pattern (FORMING state)
        spring = create_spring(sample_bar, base_timestamp)
        campaign = detector.add_pattern(spring)
        assert campaign.campaign_id in detector._campaigns_by_state[CampaignState.FORMING]

        # Add second pattern (should transition to ACTIVE)
        sos = create_sos(base_timestamp)
        detector.add_pattern(sos)

        # Verify state indexes updated
        assert campaign.campaign_id not in detector._campaigns_by_state[CampaignState.FORMING]
        assert campaign.campaign_id in detector._campaigns_by_state[CampaignState.ACTIVE]

    def test_active_time_windows_updated_on_activation(self, detector, sample_bar, base_timestamp):
        """Test that _active_time_windows is updated when campaign becomes ACTIVE."""
        spring = create_spring(sample_bar, base_timestamp)
        campaign = detector.add_pattern(spring)
        assert campaign.campaign_id not in detector._active_time_windows

        sos = create_sos(base_timestamp)
        detector.add_pattern(sos)

        assert campaign.campaign_id in detector._active_time_windows

    def test_100_campaigns_all_indexed(self, detector):
        """Test that 100 campaigns are all properly indexed (using direct index add)."""
        # Use direct _add_to_indexes to bypass campaign grouping logic
        # This tests the index operations themselves
        campaigns = []
        for i in range(100):
            campaign = Campaign(
                campaign_id=f"test-bulk-{i}",
                state=CampaignState.FORMING,
            )
            detector._add_to_indexes(campaign)
            campaigns.append(campaign)

        # Verify all in ID index
        assert len(detector._campaigns_by_id) == len(campaigns)
        for campaign in campaigns:
            assert campaign.campaign_id in detector._campaigns_by_id

        # Verify state indexes are consistent
        total_in_state_indexes = sum(len(ids) for ids in detector._campaigns_by_state.values())
        assert total_in_state_indexes == len(campaigns)


# ============================================================================
# Test: Index Maintenance Methods
# ============================================================================


class TestIndexMaintenanceMethods:
    """Test _add_to_indexes, _update_indexes, _remove_from_indexes, _rebuild_indexes."""

    def test_add_to_indexes(self, detector):
        """Test _add_to_indexes adds campaign to all indexes."""
        campaign = Campaign(campaign_id="test-123", state=CampaignState.FORMING)
        detector._add_to_indexes(campaign)

        assert detector._campaigns_by_id["test-123"] is campaign
        assert "test-123" in detector._campaigns_by_state[CampaignState.FORMING]

    def test_add_to_indexes_active_updates_time_windows(self, detector):
        """Test _add_to_indexes updates time windows for ACTIVE campaigns."""
        campaign = Campaign(campaign_id="active-123", state=CampaignState.ACTIVE)
        detector._add_to_indexes(campaign)

        assert "active-123" in detector._active_time_windows

    def test_update_indexes_state_change(self, detector):
        """Test _update_indexes moves campaign between state indexes."""
        campaign = Campaign(campaign_id="test-456", state=CampaignState.FORMING)
        detector._add_to_indexes(campaign)

        # Change state and update indexes
        old_state = campaign.state
        campaign.state = CampaignState.ACTIVE
        detector._update_indexes(campaign, old_state)

        assert "test-456" not in detector._campaigns_by_state[CampaignState.FORMING]
        assert "test-456" in detector._campaigns_by_state[CampaignState.ACTIVE]
        assert "test-456" in detector._active_time_windows

    def test_update_indexes_removes_from_time_windows(self, detector):
        """Test _update_indexes removes from time windows when no longer ACTIVE."""
        campaign = Campaign(campaign_id="test-789", state=CampaignState.ACTIVE)
        detector._add_to_indexes(campaign)
        assert "test-789" in detector._active_time_windows

        # Transition to COMPLETED
        old_state = campaign.state
        campaign.state = CampaignState.COMPLETED
        detector._update_indexes(campaign, old_state)

        assert "test-789" not in detector._active_time_windows
        assert "test-789" in detector._campaigns_by_state[CampaignState.COMPLETED]

    def test_remove_from_indexes(self, detector):
        """Test _remove_from_indexes removes campaign from all indexes."""
        campaign = Campaign(campaign_id="remove-test", state=CampaignState.ACTIVE)
        detector._add_to_indexes(campaign)

        detector._remove_from_indexes("remove-test")

        assert "remove-test" not in detector._campaigns_by_id
        assert "remove-test" not in detector._campaigns_by_state[CampaignState.ACTIVE]
        assert "remove-test" not in detector._active_time_windows

    def test_remove_from_indexes_nonexistent(self, detector):
        """Test _remove_from_indexes handles nonexistent campaign gracefully."""
        # Should not raise
        detector._remove_from_indexes("nonexistent-id")

    def test_rebuild_indexes(self, detector):
        """Test _rebuild_indexes rebuilds all indexes from ID index."""
        # Add campaigns directly to ID index (simulating corrupted state)
        campaign1 = Campaign(campaign_id="rebuild-1", state=CampaignState.FORMING)
        campaign2 = Campaign(campaign_id="rebuild-2", state=CampaignState.ACTIVE)
        campaign3 = Campaign(campaign_id="rebuild-3", state=CampaignState.COMPLETED)

        detector._campaigns_by_id["rebuild-1"] = campaign1
        detector._campaigns_by_id["rebuild-2"] = campaign2
        detector._campaigns_by_id["rebuild-3"] = campaign3

        # Clear secondary indexes (simulating corruption)
        detector._campaigns_by_state.clear()
        detector._active_time_windows.clear()

        # Rebuild
        detector._rebuild_indexes()

        # Verify indexes rebuilt correctly
        assert "rebuild-1" in detector._campaigns_by_state[CampaignState.FORMING]
        assert "rebuild-2" in detector._campaigns_by_state[CampaignState.ACTIVE]
        assert "rebuild-3" in detector._campaigns_by_state[CampaignState.COMPLETED]
        assert "rebuild-2" in detector._active_time_windows
        assert "rebuild-1" not in detector._active_time_windows


# ============================================================================
# Test: Backward Compatibility
# ============================================================================


class TestBackwardCompatibility:
    """Test that campaigns property provides backward compatibility.

    Note: These tests intentionally access the deprecated campaigns property
    and suppress the DeprecationWarning since they're testing the property itself.
    """

    def test_campaigns_property_returns_list(self, detector):
        """Test campaigns property returns a list."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            assert isinstance(detector.campaigns, list)

    def test_campaigns_property_returns_all_campaigns(self, detector, sample_bar, base_timestamp):
        """Test campaigns property returns all campaigns from ID index."""
        spring = create_spring(sample_bar, base_timestamp)
        campaign = detector.add_pattern(spring)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            campaigns_list = detector.campaigns
            assert campaign in campaigns_list
            assert len(campaigns_list) == 1

    def test_campaigns_property_reflects_updates(self, detector, sample_bar, base_timestamp):
        """Test campaigns property reflects changes."""
        spring1 = create_spring(sample_bar, base_timestamp, bar_index=10)
        detector.add_pattern(spring1)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            assert len(detector.campaigns) == 1

        # Add another pattern to a new campaign
        spring2 = create_spring(sample_bar, base_timestamp + timedelta(hours=100), bar_index=20)
        detector.add_pattern(spring2)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            assert len(detector.campaigns) == 2

    def test_campaigns_property_emits_deprecation_warning(self, detector):
        """Test that accessing campaigns property emits DeprecationWarning."""
        with pytest.warns(DeprecationWarning, match="Direct mutation.*deprecated"):
            _ = detector.campaigns


# ============================================================================
# Test: O(1) Lookup Methods
# ============================================================================


class TestO1Lookups:
    """Test that lookup methods use O(1) hash map access."""

    def test_get_campaign_by_id_returns_correct_campaign(
        self, detector, sample_bar, base_timestamp
    ):
        """Test get_campaign_by_id returns the correct campaign."""
        spring = create_spring(sample_bar, base_timestamp)
        campaign = detector.add_pattern(spring)

        found = detector.get_campaign_by_id(campaign.campaign_id)
        assert found is campaign

    def test_get_campaign_by_id_returns_none_for_unknown(self, detector):
        """Test get_campaign_by_id returns None for unknown ID."""
        result = detector.get_campaign_by_id("nonexistent-id")
        assert result is None

    def test_get_campaigns_by_state_uses_index(self, detector, sample_bar, base_timestamp):
        """Test get_campaigns_by_state returns campaigns from state index."""
        spring = create_spring(sample_bar, base_timestamp)
        campaign = detector.add_pattern(spring)

        forming = detector.get_campaigns_by_state(CampaignState.FORMING)
        assert campaign in forming

        # Transition to ACTIVE
        sos = create_sos(base_timestamp)
        detector.add_pattern(sos)

        active = detector.get_campaigns_by_state(CampaignState.ACTIVE)
        assert campaign in active

        forming_after = detector.get_campaigns_by_state(CampaignState.FORMING)
        assert campaign not in forming_after

    def test_get_active_campaigns_uses_index(self, detector, sample_bar, base_timestamp):
        """Test get_active_campaigns uses state index."""
        spring = create_spring(sample_bar, base_timestamp)
        campaign = detector.add_pattern(spring)

        # Initially FORMING - should be in active campaigns
        active = detector.get_active_campaigns()
        assert campaign in active

    def test_find_campaign_by_id_uses_hash_map(self, detector, sample_bar, base_timestamp):
        """Test _find_campaign_by_id uses O(1) hash map lookup."""
        spring = create_spring(sample_bar, base_timestamp)
        campaign = detector.add_pattern(spring)

        # Internal method should use hash map
        found = detector._find_campaign_by_id(campaign.campaign_id)
        assert found is campaign


# ============================================================================
# Test: State Transitions Update Indexes
# ============================================================================


class TestStateTransitionIndexUpdates:
    """Test that all state transitions properly update indexes."""

    def test_expire_stale_campaigns_updates_indexes(self, detector, sample_bar, base_timestamp):
        """Test expire_stale_campaigns updates indexes when campaigns fail."""
        spring = create_spring(sample_bar, base_timestamp)
        campaign = detector.add_pattern(spring)

        assert campaign.campaign_id in detector._campaigns_by_state[CampaignState.FORMING]

        # Expire campaign (73 hours later)
        future_time = base_timestamp + timedelta(hours=73)
        detector.expire_stale_campaigns(future_time)

        assert campaign.state == CampaignState.FAILED
        assert campaign.campaign_id not in detector._campaigns_by_state[CampaignState.FORMING]
        assert campaign.campaign_id in detector._campaigns_by_state[CampaignState.FAILED]

    def test_mark_campaign_completed_updates_indexes(self, detector, sample_bar, base_timestamp):
        """Test mark_campaign_completed updates indexes."""
        # Create active campaign
        spring = create_spring(sample_bar, base_timestamp)
        campaign = detector.add_pattern(spring)
        sos = create_sos(base_timestamp)
        detector.add_pattern(sos)

        assert campaign.campaign_id in detector._campaigns_by_state[CampaignState.ACTIVE]

        # Mark completed
        detector.mark_campaign_completed(
            campaign.campaign_id,
            exit_price=Decimal("105.00"),
            exit_reason=ExitReason.TARGET_HIT,
        )

        assert campaign.state == CampaignState.COMPLETED
        assert campaign.campaign_id not in detector._campaigns_by_state[CampaignState.ACTIVE]
        assert campaign.campaign_id in detector._campaigns_by_state[CampaignState.COMPLETED]
        assert campaign.campaign_id not in detector._active_time_windows


# ============================================================================
# Test: Empty State Index Queries
# ============================================================================


class TestEmptyStateQueries:
    """Test edge cases with empty state indexes."""

    def test_get_campaigns_by_state_empty_returns_empty_list(self, detector):
        """Test querying empty state returns empty list, not error."""
        completed = detector.get_campaigns_by_state(CampaignState.COMPLETED)
        assert completed == []

    def test_get_active_campaigns_empty_returns_empty_list(self, detector):
        """Test get_active_campaigns returns empty list when none exist."""
        active = detector.get_active_campaigns()
        assert active == []


# ============================================================================
# Test: Performance Benchmarks
# ============================================================================


class TestPerformanceBenchmarks:
    """Performance benchmark tests for Story 15.3.

    These tests verify that lookups meet performance requirements:
    - Campaign lookup by ID: < 5ms
    - Active campaign query: < 10ms
    - Pattern addition: < 50ms
    """

    def test_lookup_by_id_performance(self, detector, sample_bar, base_timestamp):
        """Test that lookup by ID is fast (< 5ms) with 1000 campaigns.

        Story 15.3 requirement: Lookup by ID < 5ms vs ~20-50ms before.
        """
        import time

        # Create 1000 campaigns
        campaigns = []
        for i in range(1000):
            campaign = Campaign(
                campaign_id=f"perf-test-{i}",
                state=CampaignState.FORMING,
            )
            detector._add_to_indexes(campaign)
            campaigns.append(campaign)

        # Benchmark 1000 lookups
        start = time.perf_counter()
        for campaign in campaigns:
            result = detector.get_campaign_by_id(campaign.campaign_id)
            assert result is not None
        elapsed = time.perf_counter() - start

        # Average time per lookup should be < 5ms
        avg_lookup_ms = (elapsed / 1000) * 1000
        assert avg_lookup_ms < 5, f"Average lookup time {avg_lookup_ms:.2f}ms exceeds 5ms target"

    def test_active_campaign_query_performance(self, detector):
        """Test that active campaign query is fast (< 10ms) with 1000 campaigns.

        Story 15.3 requirement: Active campaign query < 10ms vs ~50-100ms before.
        """
        import time

        # Create 1000 campaigns (100 active, 900 other states)
        for i in range(100):
            campaign = Campaign(
                campaign_id=f"active-{i}",
                state=CampaignState.ACTIVE,
            )
            detector._add_to_indexes(campaign)

        for i in range(300):
            campaign = Campaign(
                campaign_id=f"forming-{i}",
                state=CampaignState.FORMING,
            )
            detector._add_to_indexes(campaign)

        for i in range(300):
            campaign = Campaign(
                campaign_id=f"completed-{i}",
                state=CampaignState.COMPLETED,
            )
            detector._add_to_indexes(campaign)

        for i in range(300):
            campaign = Campaign(
                campaign_id=f"failed-{i}",
                state=CampaignState.FAILED,
            )
            detector._add_to_indexes(campaign)

        # Benchmark active campaigns query
        start = time.perf_counter()
        for _ in range(100):  # Run 100 times to get stable measurement
            active = detector.get_active_campaigns()
        elapsed = time.perf_counter() - start

        # Average time per query should be < 10ms
        avg_query_ms = (elapsed / 100) * 1000
        assert avg_query_ms < 10, f"Average query time {avg_query_ms:.2f}ms exceeds 10ms target"

        # Verify correct count (should include FORMING + ACTIVE)
        assert len(active) == 400  # 100 ACTIVE + 300 FORMING

    def test_get_campaigns_by_state_performance(self, detector):
        """Test that state query is fast with many campaigns."""
        import time

        # Create 1000 campaigns with various states
        for i in range(250):
            detector._add_to_indexes(
                Campaign(
                    campaign_id=f"forming-{i}",
                    state=CampaignState.FORMING,
                )
            )
        for i in range(250):
            detector._add_to_indexes(
                Campaign(
                    campaign_id=f"active-{i}",
                    state=CampaignState.ACTIVE,
                )
            )
        for i in range(250):
            detector._add_to_indexes(
                Campaign(
                    campaign_id=f"completed-{i}",
                    state=CampaignState.COMPLETED,
                )
            )
        for i in range(250):
            detector._add_to_indexes(
                Campaign(
                    campaign_id=f"failed-{i}",
                    state=CampaignState.FAILED,
                )
            )

        # Benchmark state queries
        start = time.perf_counter()
        for _ in range(100):
            detector.get_campaigns_by_state(CampaignState.COMPLETED)
        elapsed = time.perf_counter() - start

        avg_query_ms = (elapsed / 100) * 1000
        assert (
            avg_query_ms < 10
        ), f"Average state query time {avg_query_ms:.2f}ms exceeds 10ms target"

    def test_index_consistency_after_many_operations(self, detector):
        """Test index consistency after many add/update operations."""
        campaigns = []

        # Add 100 campaigns
        for i in range(100):
            campaign = Campaign(
                campaign_id=f"test-{i}",
                state=CampaignState.FORMING,
            )
            detector._add_to_indexes(campaign)
            campaigns.append(campaign)

        # Transition 50 to ACTIVE
        for i in range(50):
            old_state = campaigns[i].state
            campaigns[i].state = CampaignState.ACTIVE
            detector._update_indexes(campaigns[i], old_state)

        # Transition 25 to COMPLETED
        for i in range(25):
            old_state = campaigns[i].state
            campaigns[i].state = CampaignState.COMPLETED
            detector._update_indexes(campaigns[i], old_state)

        # Verify index consistency
        assert len(detector._campaigns_by_id) == 100
        assert (
            len(detector._campaigns_by_state[CampaignState.FORMING]) == 50
        )  # 100 - 50 transitioned
        assert len(detector._campaigns_by_state[CampaignState.ACTIVE]) == 25  # 50 - 25 transitioned
        assert len(detector._campaigns_by_state[CampaignState.COMPLETED]) == 25

        # Total in state indexes should equal total campaigns
        total = sum(len(ids) for ids in detector._campaigns_by_state.values())
        assert total == 100


# ============================================================================
# Test: pytest-benchmark Compatible Tests (Optional)
# ============================================================================

# Check if pytest-benchmark is available
try:
    import pytest_benchmark  # noqa: F401

    BENCHMARK_AVAILABLE = True
except ImportError:
    BENCHMARK_AVAILABLE = False


@pytest.mark.skipif(not BENCHMARK_AVAILABLE, reason="pytest-benchmark not installed")
class TestPytestBenchmark:
    """Optional pytest-benchmark tests for more reliable CI performance measurements.

    These tests use pytest-benchmark for statistical analysis, warmup, and
    calibration. Install with: pip install pytest-benchmark

    Run with: pytest --benchmark-only tests/backtesting/test_campaign_lookup_optimization.py
    """

    @pytest.fixture
    def detector_with_1000_campaigns(self):
        """Pre-populated detector with 1000 campaigns for benchmarking."""
        detector = IntradayCampaignDetector()
        for i in range(1000):
            campaign = Campaign(
                campaign_id=f"bench-{i}",
                state=CampaignState.FORMING if i % 4 == 0 else (
                    CampaignState.ACTIVE if i % 4 == 1 else (
                        CampaignState.COMPLETED if i % 4 == 2 else CampaignState.FAILED
                    )
                ),
            )
            detector._add_to_indexes(campaign)
        return detector

    def test_benchmark_lookup_by_id(self, detector_with_1000_campaigns, benchmark):
        """Benchmark campaign lookup by ID with pytest-benchmark."""
        detector = detector_with_1000_campaigns

        def lookup():
            return detector.get_campaign_by_id("bench-500")

        result = benchmark(lookup)
        assert result is not None

    def test_benchmark_get_active_campaigns(self, detector_with_1000_campaigns, benchmark):
        """Benchmark get_active_campaigns with pytest-benchmark."""
        detector = detector_with_1000_campaigns

        def query():
            return detector.get_active_campaigns()

        result = benchmark(query)
        assert len(result) > 0

    def test_benchmark_get_campaigns_by_state(self, detector_with_1000_campaigns, benchmark):
        """Benchmark get_campaigns_by_state with pytest-benchmark."""
        detector = detector_with_1000_campaigns

        def query():
            return detector.get_campaigns_by_state(CampaignState.COMPLETED)

        result = benchmark(query)
        assert len(result) > 0

    def test_benchmark_add_to_indexes(self, benchmark):
        """Benchmark _add_to_indexes operation with pytest-benchmark."""
        detector = IntradayCampaignDetector()
        counter = [0]  # Use list to allow mutation in closure

        def add_campaign():
            campaign = Campaign(
                campaign_id=f"add-bench-{counter[0]}",
                state=CampaignState.FORMING,
            )
            counter[0] += 1
            detector._add_to_indexes(campaign)
            return campaign

        result = benchmark(add_campaign)
        assert result is not None
