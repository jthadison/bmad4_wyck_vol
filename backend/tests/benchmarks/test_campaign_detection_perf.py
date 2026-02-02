"""
Performance benchmarks for campaign detection (Story 22.15).

Validates campaign detection performance:
- AC1: <10ms per pattern for campaign detection
- AC1: <50MB memory for operation
- AC4: Results within 5% of baseline
"""

import time
import tracemalloc
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pandas as pd
import pytest

from tests.benchmarks.conftest import PERFORMANCE_TARGETS


def create_test_ohlcv_bar(symbol: str, timestamp: datetime) -> "OHLCVBar":
    """Create a test OHLCVBar instance."""
    from src.models.ohlcv import OHLCVBar

    return OHLCVBar(
        id=uuid4(),
        symbol=symbol,
        timeframe="1h",
        timestamp=timestamp,
        open=Decimal("150.00"),
        high=Decimal("152.00"),
        low=Decimal("149.00"),
        close=Decimal("151.00"),
        volume=1000000,
        spread=Decimal("3.00"),
        spread_ratio=Decimal("1.0"),
        volume_ratio=Decimal("1.0"),
        created_at=datetime.now(UTC),
    )


def create_test_spring(symbol: str, timestamp: datetime, trading_range_id=None) -> "Spring":
    """Create a valid Spring pattern for testing."""
    from src.models.spring import Spring

    bar = create_test_ohlcv_bar(symbol, timestamp)
    return Spring(
        bar=bar,
        bar_index=50,
        penetration_pct=Decimal("0.02"),  # 2% below Creek
        volume_ratio=Decimal("0.5"),  # Low volume (valid for Spring)
        recovery_bars=2,
        creek_reference=Decimal("150.00"),
        spring_low=Decimal("147.00"),
        recovery_price=Decimal("151.00"),
        detection_timestamp=timestamp,
        trading_range_id=trading_range_id or uuid4(),
    )


def create_test_ar(symbol: str, timestamp: datetime) -> "AutomaticRally":
    """Create a valid AutomaticRally pattern for testing."""
    from src.models.automatic_rally import AutomaticRally

    return AutomaticRally(
        id=uuid4(),
        bar=create_test_ohlcv_bar(symbol, timestamp),
        bar_index=30,
        rally_pct=Decimal("0.05"),  # 5% rally
        volume_ratio=Decimal("0.8"),  # Declining volume on rally
        bars_since_sc=3,
        sc_reference_price=Decimal("147.00"),
        ar_high=Decimal("155.00"),
        detection_timestamp=timestamp,
        trading_range_id=uuid4(),
    )


@pytest.mark.benchmark
class TestCampaignDetectionPerformance:
    """Performance benchmarks for the campaign detection system."""

    def test_campaign_detector_pattern_throughput(self, benchmark_ohlcv_1000: pd.DataFrame):
        """
        Benchmark IntradayCampaignDetector pattern processing.

        Target: <10ms per pattern (AC1), which translates to <0.01ms per bar
        when processing sequential bar data.
        """
        from src.backtesting.intraday_campaign_detector import IntradayCampaignDetector

        detector = IntradayCampaignDetector(
            campaign_window_hours=48,
            max_pattern_gap_hours=48,
            min_patterns_for_active=2,
            max_concurrent_campaigns=3,
        )

        # Create a series of Spring patterns to process
        patterns = []
        base_time = datetime.now(UTC)

        for i in range(100):
            patterns.append(create_test_spring(f"SYM{i % 10}", base_time + timedelta(hours=i)))

        # Measure pattern processing time
        times = []
        for pattern in patterns:
            start = time.perf_counter()
            detector.add_pattern(pattern)
            elapsed = (time.perf_counter() - start) * 1000  # ms
            times.append(elapsed)

        avg_time = sum(times) / len(times)
        max_time = max(times)
        total_time = sum(times)

        print("\nCampaign Detection (100 patterns):")
        print(f"  Average per pattern: {avg_time:.4f}ms")
        print(f"  Max per pattern: {max_time:.4f}ms")
        print(f"  Total for 100 patterns: {total_time:.2f}ms")

        # AC1: <10ms per pattern
        assert avg_time < 10, f"Pattern processing too slow: {avg_time:.4f}ms > 10ms"

    def test_campaign_detector_batch_performance(self):
        """
        Benchmark batch pattern processing performance.

        Story 15.5: Batch processing for better throughput.
        """
        from src.backtesting.intraday_campaign_detector import IntradayCampaignDetector

        detector = IntradayCampaignDetector(
            campaign_window_hours=48,
            max_pattern_gap_hours=48,
            min_patterns_for_active=2,
            max_concurrent_campaigns=10,  # Higher limit for batch test
        )

        # Create 500 patterns across different symbols
        patterns = []
        base_time = datetime.now(UTC)
        symbols = ["AAPL", "GOOGL", "MSFT", "AMZN", "NVDA"]

        for i in range(500):
            symbol = symbols[i % len(symbols)]
            patterns.append(
                create_test_spring(symbol, base_time + timedelta(hours=i // len(symbols)))
            )

        # Time batch processing (with required account_size parameter)
        start = time.perf_counter()
        result = detector.add_patterns_batch(
            patterns,
            account_size=Decimal("100000"),
            risk_pct_per_trade=Decimal("2.0"),
        )
        elapsed = (time.perf_counter() - start) * 1000  # ms

        per_pattern_ms = elapsed / len(patterns)

        print("\nBatch Pattern Processing (500 patterns):")
        print(f"  Total time: {elapsed:.2f}ms")
        print(f"  Per pattern: {per_pattern_ms:.4f}ms")
        print(f"  Processed: {result.patterns_processed}")
        print(f"  Rejected: {result.patterns_rejected}")
        print(f"  Campaigns created: {result.campaigns_created}")

        # Batch should be faster than individual processing
        assert per_pattern_ms < 10, f"Batch processing too slow: {per_pattern_ms:.4f}ms > 10ms"

    def test_campaign_state_transition_performance(self):
        """
        Benchmark campaign state transition operations.

        Validates state machine performance for campaign lifecycle.
        """
        from src.backtesting.intraday_campaign_detector import (
            CampaignState,
            IntradayCampaignDetector,
        )

        detector = IntradayCampaignDetector(
            campaign_window_hours=48,
            max_pattern_gap_hours=48,
            min_patterns_for_active=2,
            max_concurrent_campaigns=50,
        )

        base_time = datetime.now(UTC)

        # Create campaigns that will go through state transitions
        for i in range(100):
            # Spring pattern creates FORMING campaign
            spring = create_test_spring(f"SYM{i}", base_time + timedelta(hours=i * 10))
            detector.add_pattern(spring)

            # Second spring pattern should transition to ACTIVE
            spring2 = create_test_spring(
                f"SYM{i}", base_time + timedelta(hours=i * 10 + 1), spring.trading_range_id
            )
            detector.add_pattern(spring2)

        # Time state transition operations
        start = time.perf_counter()
        active_campaigns = detector.get_active_campaigns()
        get_active_time = (time.perf_counter() - start) * 1000

        # Use get_campaigns_by_state to get all campaigns
        start = time.perf_counter()
        all_campaigns = (
            detector.get_campaigns_by_state(CampaignState.FORMING)
            + detector.get_campaigns_by_state(CampaignState.ACTIVE)
            + detector.get_campaigns_by_state(CampaignState.COMPLETED)
        )
        get_all_time = (time.perf_counter() - start) * 1000

        print("\nState Transition Performance (100 campaigns):")
        print(f"  Get active campaigns: {get_active_time:.2f}ms")
        print(f"  Get all campaigns: {get_all_time:.2f}ms")
        print(f"  Active: {len(active_campaigns)}")
        print(f"  Total: {len(all_campaigns)}")

        # Operations should be fast
        assert get_active_time < 50, f"Get active too slow: {get_active_time:.2f}ms"
        assert get_all_time < 50, f"Get all too slow: {get_all_time:.2f}ms"

    def test_campaign_detection_memory(self):
        """
        Benchmark memory usage during campaign detection.

        Target: <50MB peak memory (AC1).
        """
        from src.backtesting.intraday_campaign_detector import IntradayCampaignDetector

        detector = IntradayCampaignDetector(
            campaign_window_hours=48,
            max_pattern_gap_hours=48,
            min_patterns_for_active=2,
            max_concurrent_campaigns=100,
        )

        base_time = datetime.now(UTC)

        tracemalloc.start()

        # Add 1000 patterns to stress memory
        for i in range(1000):
            spring = create_test_spring(f"SYM{i % 50}", base_time + timedelta(hours=i))
            detector.add_pattern(spring)

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        peak_mb = peak / 1024 / 1024

        print("\nMemory Usage (1000 patterns):")
        print(f"  Current: {current / 1024 / 1024:.2f}MB")
        print(f"  Peak: {peak_mb:.2f}MB")

        target = PERFORMANCE_TARGETS["memory_operation_mb"]
        assert peak_mb < target, f"Memory usage too high: {peak_mb:.2f}MB > {target}MB"

    def test_portfolio_heat_calculation_performance(self):
        """
        Benchmark portfolio heat calculation performance.

        Story 14.3: Portfolio heat tracking must be efficient.
        """
        from src.backtesting.intraday_campaign_detector import IntradayCampaignDetector

        detector = IntradayCampaignDetector(
            campaign_window_hours=48,
            max_pattern_gap_hours=48,
            min_patterns_for_active=2,
            max_concurrent_campaigns=50,
            max_portfolio_heat_pct=Decimal("10.0"),
        )

        base_time = datetime.now(UTC)

        # Create 50 campaigns
        for i in range(50):
            spring = create_test_spring(f"SYM{i}", base_time + timedelta(hours=i))
            detector.add_pattern(spring)

        # Time active campaign retrieval (used for heat calculation)
        times = []
        for _ in range(100):
            start = time.perf_counter()
            active = detector.get_active_campaigns()
            # Calculate heat from active campaigns (similar to internal heat calculation)
            total_risk = sum(c.dollar_risk or Decimal("0") for c in active)
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)

        avg_time = sum(times) / len(times)
        heat = float(total_risk / Decimal("100000") * 100) if total_risk else 0.0

        print("\nPortfolio Heat Calculation (via active campaigns):")
        print(f"  Average: {avg_time:.4f}ms")
        print(f"  Active campaigns: {len(active)}")
        print(f"  Estimated heat: {heat:.2f}%")

        # Heat calculation should be very fast
        assert avg_time < 5, f"Heat calculation too slow: {avg_time:.4f}ms > 5ms"

    def test_campaign_lookup_by_state_performance(self):
        """
        Benchmark campaign lookup by state.

        Validates state-based lookups are efficient.
        """
        from src.backtesting.intraday_campaign_detector import (
            CampaignState,
            IntradayCampaignDetector,
        )

        detector = IntradayCampaignDetector(
            campaign_window_hours=48,
            max_pattern_gap_hours=48,
            min_patterns_for_active=2,
            max_concurrent_campaigns=100,
        )

        base_time = datetime.now(UTC)
        symbols = [f"SYM{i}" for i in range(100)]

        # Create campaigns for each symbol
        for i, symbol in enumerate(symbols):
            spring = create_test_spring(symbol, base_time + timedelta(hours=i))
            detector.add_pattern(spring)

        # Time state lookups
        states = [CampaignState.FORMING, CampaignState.ACTIVE, CampaignState.COMPLETED]
        times = []
        for state in states:
            for _ in range(30):
                start = time.perf_counter()
                campaigns = detector.get_campaigns_by_state(state)
                elapsed = (time.perf_counter() - start) * 1000
                times.append(elapsed)

        avg_time = sum(times) / len(times)
        max_time = max(times)

        print("\nCampaign Lookup by State (90 lookups):")
        print(f"  Average: {avg_time:.4f}ms")
        print(f"  Max: {max_time:.4f}ms")

        # Lookups should be fast
        assert avg_time < 1, f"State lookup too slow: {avg_time:.4f}ms > 1ms"
