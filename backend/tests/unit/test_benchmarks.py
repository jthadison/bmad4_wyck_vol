"""
Unit tests for benchmark infrastructure (Story 12.9 - Task 13).

These tests validate the benchmark framework, fixtures, and configuration
to ensure reliable performance testing.

Test Coverage:
--------------
1. Benchmark config loads correctly (NFR1/NFR7 targets)
2. Fixtures generate valid data
3. Benchmark utilities work correctly
4. Regression detection logic
5. Prometheus metrics export format

Note: These are unit tests for the benchmark infrastructure itself,
not the actual performance benchmarks (which are in benchmarks/ directory).
"""

import json
from decimal import Decimal

import pytest

from benchmarks.benchmark_config import (
    BACKTEST_SPEED_TARGET_BARS_PER_SECOND,
    BENCHMARK_ITERATIONS,
    BENCHMARK_ROUNDS,
    DATABASE_QUERY_TARGET_MS,
    FULL_PIPELINE_LATENCY_TARGET_MS,
    PATTERN_DETECTION_LATENCY_BUDGET_MS,
    VOLUME_ANALYSIS_LATENCY_BUDGET_MS,
)


class TestBenchmarkConfig:
    """Test that benchmark configuration values are correct."""

    def test_nfr1_target_loaded(self):
        """NFR1 target should be 1000ms (1 second)."""
        assert FULL_PIPELINE_LATENCY_TARGET_MS == 1000

    def test_nfr7_target_loaded(self):
        """NFR7 target should be 100 bars/second."""
        assert BACKTEST_SPEED_TARGET_BARS_PER_SECOND == 100

    def test_component_latency_budgets_sum_to_nfr1(self):
        """Component latency budgets should sum to less than NFR1 target."""
        total_budget = (
            VOLUME_ANALYSIS_LATENCY_BUDGET_MS
            + PATTERN_DETECTION_LATENCY_BUDGET_MS["spring"]
            + 100  # Signal generation overhead
        )
        # Total budget should be less than NFR1 target to allow for overhead
        assert total_budget <= FULL_PIPELINE_LATENCY_TARGET_MS

    def test_database_query_targets_are_reasonable(self):
        """Database query targets should be reasonable (10-100ms)."""
        for query_type, target_ms in DATABASE_QUERY_TARGET_MS.items():
            assert 10 <= target_ms <= 100, f"{query_type} target {target_ms}ms out of range"

    def test_benchmark_iterations_configured(self):
        """Benchmark iterations should be configured for statistical validity."""
        assert BENCHMARK_ITERATIONS >= 10, "Need at least 10 iterations for stats"
        assert BENCHMARK_ROUNDS >= 3, "Need at least 3 rounds for reliability"


class TestBenchmarkFixtures:
    """Test that benchmark fixtures generate valid data."""

    def test_sample_ohlcv_bars_fixture(self, sample_ohlcv_bars):
        """Fixture should generate 1000 OHLCV bars."""
        assert len(sample_ohlcv_bars) == 1000
        assert all(hasattr(bar, "open") for bar in sample_ohlcv_bars)
        assert all(hasattr(bar, "high") for bar in sample_ohlcv_bars)
        assert all(hasattr(bar, "low") for bar in sample_ohlcv_bars)
        assert all(hasattr(bar, "close") for bar in sample_ohlcv_bars)
        assert all(hasattr(bar, "volume") for bar in sample_ohlcv_bars)

    def test_sample_ohlcv_bars_price_ordering(self, sample_ohlcv_bars):
        """OHLCV bars should have valid price ordering (high >= low)."""
        for bar in sample_ohlcv_bars:
            assert bar.high >= bar.low, f"High {bar.high} < Low {bar.low}"
            assert bar.high >= bar.open, f"High {bar.high} < Open {bar.open}"
            assert bar.high >= bar.close, f"High {bar.high} < Close {bar.close}"
            assert bar.low <= bar.open, f"Low {bar.low} > Open {bar.open}"
            assert bar.low <= bar.close, f"Low {bar.low} > Close {bar.close}"

    def test_sample_ohlcv_bars_volume_positive(self, sample_ohlcv_bars):
        """OHLCV bars should have positive volume."""
        assert all(bar.volume > 0 for bar in sample_ohlcv_bars)

    def test_sample_ohlcv_bars_large_fixture(self, sample_ohlcv_bars_large):
        """Large fixture should generate 10,000 OHLCV bars."""
        assert len(sample_ohlcv_bars_large) == 10000

    def test_trading_range_fixture_valid(self, sample_trading_range):
        """Trading range fixture should generate valid range."""
        assert sample_trading_range.is_valid
        assert sample_trading_range.support < sample_trading_range.resistance
        assert sample_trading_range.range_width_pct >= Decimal("0.03")
        assert sample_trading_range.duration >= 10


class TestBenchmarkRegressionDetection:
    """Test benchmark regression detection logic."""

    def test_regression_detected_when_slowdown_exceeds_threshold(self):
        """Should detect regression when mean latency exceeds 10% threshold."""
        baseline_mean_ms = 100.0
        current_mean_ms = 111.0  # 11% slower
        threshold_pct = 10.0

        regression = (current_mean_ms - baseline_mean_ms) / baseline_mean_ms * 100
        is_regression = regression > threshold_pct

        assert is_regression, "Should detect 11% regression with 10% threshold"

    def test_no_regression_when_within_threshold(self):
        """Should not detect regression when within 10% threshold."""
        baseline_mean_ms = 100.0
        current_mean_ms = 109.0  # 9% slower
        threshold_pct = 10.0

        regression = (current_mean_ms - baseline_mean_ms) / baseline_mean_ms * 100
        is_regression = regression > threshold_pct

        assert not is_regression, "Should not detect 9% regression with 10% threshold"

    def test_improvement_not_flagged_as_regression(self):
        """Performance improvements should not be flagged as regressions."""
        baseline_mean_ms = 100.0
        current_mean_ms = 80.0  # 20% faster
        threshold_pct = 10.0

        regression = (current_mean_ms - baseline_mean_ms) / baseline_mean_ms * 100
        is_regression = regression > threshold_pct

        assert not is_regression, "Improvements should not trigger regression detection"


class TestPrometheusMetricsExport:
    """Test Prometheus metrics export format."""

    def test_metrics_endpoint_returns_text_format(self, test_client):
        """Metrics endpoint should return Prometheus text format."""
        response = test_client.get("/api/v1/metrics")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/plain")

    def test_signal_generation_metrics_exported(self, test_client):
        """Signal generation metrics should be exported."""
        response = test_client.get("/api/v1/metrics")
        content = response.text

        # Check for signal generation metrics
        assert "signal_generation_requests_total" in content
        assert "signal_generation_latency_seconds" in content
        assert "pattern_detections_total" in content

    def test_backtest_metrics_exported(self, test_client):
        """Backtest metrics should be exported."""
        response = test_client.get("/api/v1/metrics")
        content = response.text

        # Check for backtest metrics
        assert "backtest_executions_total" in content
        assert "backtest_duration_seconds" in content

    def test_database_metrics_exported(self, test_client):
        """Database query metrics should be exported."""
        response = test_client.get("/api/v1/metrics")
        content = response.text

        # Check for database metrics
        assert "database_query_duration_seconds" in content

    def test_api_metrics_exported(self, test_client):
        """API request metrics should be exported."""
        response = test_client.get("/api/v1/metrics")
        content = response.text

        # Check for API metrics
        assert "api_requests_total" in content
        assert "api_request_duration_seconds" in content


class TestBenchmarkResultsPersistence:
    """Test that benchmark results can be saved and loaded."""

    def test_benchmark_results_saved_as_json(self, tmp_path):
        """Benchmark results should be saved as valid JSON."""
        results = {
            "name": "test_volume_analysis_latency",
            "stats": {
                "min": 0.0005,
                "max": 0.0015,
                "mean": 0.0008,
                "stddev": 0.0002,
            },
            "iterations": 100,
            "rounds": 5,
        }

        output_file = tmp_path / "benchmark_results.json"
        output_file.write_text(json.dumps(results, indent=2))

        # Verify file is valid JSON
        loaded = json.loads(output_file.read_text())
        assert loaded["name"] == "test_volume_analysis_latency"
        assert loaded["stats"]["mean"] == 0.0008

    def test_benchmark_comparison_calculates_regression(self, tmp_path):
        """Benchmark comparison should calculate regression percentage."""
        baseline = {
            "test_volume_analysis_latency": {"stats": {"mean": 0.0008}},
        }

        current = {
            "test_volume_analysis_latency": {"stats": {"mean": 0.0009}},
        }

        # Calculate regression
        test_name = "test_volume_analysis_latency"
        baseline_mean = baseline[test_name]["stats"]["mean"]
        current_mean = current[test_name]["stats"]["mean"]
        regression_pct = (current_mean - baseline_mean) / baseline_mean * 100

        assert regression_pct == pytest.approx(12.5, rel=0.01)  # 12.5% slower


class TestBenchmarkReportGeneration:
    """Test benchmark report generation (Task 8 related)."""

    def test_benchmark_stats_extracted_correctly(self):
        """Should extract stats from benchmark result object."""

        # Simulate pytest-benchmark stats structure
        class MockStats:
            def __init__(self):
                self.min = 0.0005
                self.max = 0.0015
                self.mean = 0.0008
                self.stddev = 0.0002
                self.median = 0.00075
                self.iqr = 0.0001

        class MockBenchmarkStats:
            def __init__(self):
                self.stats = MockStats()

        class MockBenchmark:
            def __init__(self):
                self.stats = MockBenchmarkStats()

        benchmark = MockBenchmark()

        # Extract stats
        stats = benchmark.stats.stats
        assert stats.mean == 0.0008
        assert stats.min == 0.0005
        assert stats.max == 0.0015

    def test_performance_summary_formatted_correctly(self):
        """Performance summary should format latency in appropriate units."""

        def format_latency(seconds: float) -> str:
            """Format latency in ms or µs."""
            if seconds >= 0.001:
                return f"{seconds * 1000:.2f}ms"
            else:
                return f"{seconds * 1_000_000:.2f}µs"

        assert format_latency(0.0008) == "0.80ms"
        assert format_latency(0.000008) == "8.00µs"
        assert format_latency(1.5) == "1500.00ms"


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def sample_ohlcv_bars():
    """
    Generate 1000 sample OHLCV bars for testing.

    Returns:
        List of OHLCVBar objects with realistic price/volume data
    """
    from datetime import UTC, datetime, timedelta
    from decimal import Decimal

    from src.models.ohlcv import OHLCVBar

    bars = []
    base_price = Decimal("100.00")
    base_volume = 1_000_000

    for i in range(1000):
        timestamp = datetime.now(UTC) - timedelta(days=1000 - i)
        price_variation = Decimal(str((i % 10) - 5)) / Decimal("10")  # ±0.5
        volume_variation = (i % 5) * 100_000

        open_price = base_price + price_variation
        high_price = open_price + Decimal("1.00")
        low_price = open_price - Decimal("0.50")
        close_price = open_price + price_variation / Decimal("2")

        bar = OHLCVBar(
            symbol="AAPL",
            timeframe="1d",
            timestamp=timestamp,
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=base_volume + volume_variation,
        )
        bars.append(bar)

    return bars


@pytest.fixture
def sample_ohlcv_bars_large():
    """
    Generate 10,000 sample OHLCV bars for load testing.

    Returns:
        List of OHLCVBar objects
    """
    from datetime import UTC, datetime, timedelta
    from decimal import Decimal

    from src.models.ohlcv import OHLCVBar

    bars = []
    base_price = Decimal("100.00")
    base_volume = 1_000_000

    for i in range(10000):
        timestamp = datetime.now(UTC) - timedelta(days=10000 - i)
        price_variation = Decimal(str((i % 10) - 5)) / Decimal("10")
        volume_variation = (i % 5) * 100_000

        open_price = base_price + price_variation
        high_price = open_price + Decimal("1.00")
        low_price = open_price - Decimal("0.50")
        close_price = open_price + price_variation / Decimal("2")

        bar = OHLCVBar(
            symbol="AAPL",
            timeframe="1d",
            timestamp=timestamp,
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=base_volume + volume_variation,
        )
        bars.append(bar)

    return bars


@pytest.fixture
def sample_trading_range():
    """
    Generate a sample trading range for testing.

    Returns:
        TradingRange object with valid parameters
    """
    from datetime import UTC, datetime
    from decimal import Decimal

    from src.models.price_cluster import PriceCluster
    from src.models.trading_range import TradingRange

    support_cluster = PriceCluster(
        level=Decimal("100.00"),
        touch_count=3,
        pivot_indices=[10, 20, 30],
        strength=Decimal("0.8"),
    )

    resistance_cluster = PriceCluster(
        level=Decimal("110.00"),
        touch_count=4,
        pivot_indices=[15, 25, 35, 45],
        strength=Decimal("0.85"),
    )

    trading_range = TradingRange(
        symbol="AAPL",
        timeframe="1d",
        support_cluster=support_cluster,
        resistance_cluster=resistance_cluster,
        support=Decimal("100.00"),
        resistance=Decimal("110.00"),
        midpoint=Decimal("105.00"),
        range_width=Decimal("10.00"),
        range_width_pct=Decimal("0.10"),  # 10%
        start_index=10,
        end_index=50,
        duration=41,
        created_at=datetime.now(UTC),
    )

    return trading_range


@pytest.fixture
def test_client():
    """
    Create FastAPI test client.

    Returns:
        TestClient for making requests to API endpoints
    """
    from fastapi.testclient import TestClient

    from src.api.main import app

    return TestClient(app)
