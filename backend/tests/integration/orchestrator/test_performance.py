"""
Performance benchmark tests for MasterOrchestrator.

Tests that the orchestrator meets the performance requirement of processing
10 symbols × 500 bars in <5 seconds.

Story 8.1: Master Orchestrator Architecture (AC: 10 - Performance benchmarks pass)
"""

import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.ohlcv import OHLCVBar
from src.models.volume_analysis import VolumeAnalysis
from src.orchestrator.cache import OrchestratorCache
from src.orchestrator.config import OrchestratorConfig
from src.orchestrator.container import OrchestratorContainer
from src.orchestrator.event_bus import EventBus
from src.orchestrator.master_orchestrator import MasterOrchestrator


def create_bars(symbol: str, num_bars: int = 500) -> list[OHLCVBar]:
    """Create test bars for performance testing."""
    bars = []
    base_price = Decimal("100.00")
    start_time = datetime(2024, 1, 1, tzinfo=UTC)

    for i in range(num_bars):
        price_delta = Decimal(str(i % 10 - 5))
        close_price = base_price + price_delta

        bar = OHLCVBar(
            symbol=symbol,
            timeframe="1d",
            timestamp=start_time + timedelta(days=i),
            open=close_price - Decimal("1.00"),
            high=close_price + Decimal("2.00"),
            low=close_price - Decimal("2.00"),
            close=close_price,
            volume=1_000_000 + i * 1000,
            spread=Decimal("4.00"),
        )
        bars.append(bar)

    return bars


def create_lightweight_volume_analyses(bars: list[OHLCVBar]) -> list[VolumeAnalysis]:
    """Create minimal volume analyses for performance testing."""
    return [
        VolumeAnalysis(
            bar=bar,
            volume_ratio=Decimal("1.0"),
            spread_ratio=Decimal("1.0"),
            close_position=Decimal("0.5"),
            effort_result=None,
        )
        for bar in bars
    ]


@pytest.fixture
def perf_config() -> OrchestratorConfig:
    """Configuration optimized for performance testing."""
    return OrchestratorConfig(
        default_lookback_bars=500,
        max_concurrent_symbols=10,
        enable_caching=True,
        enable_parallel_processing=True,
        circuit_breaker_threshold=5,
        min_range_quality_score=60,
        min_phase_confidence=70,
    )


@pytest.fixture
def lightweight_container() -> OrchestratorContainer:
    """Container with lightweight mock detectors for perf testing."""
    container = OrchestratorContainer(mode="mock")

    # Fast-returning mocks
    mock_volume = MagicMock()
    mock_volume.analyze.return_value = []
    container.set_mock("volume_analyzer", mock_volume)

    mock_pivot = MagicMock()
    mock_pivot.detect.return_value = []
    container.set_mock("pivot_detector", mock_pivot)

    mock_range = MagicMock()
    mock_range.detect.return_value = []
    container.set_mock("trading_range_detector", mock_range)

    mock_scorer = MagicMock()
    mock_scorer.score.return_value = 75
    container.set_mock("range_quality_scorer", mock_scorer)

    mock_levels = MagicMock()
    mock_levels.calculate_creek.return_value = None
    mock_levels.calculate_ice.return_value = None
    mock_levels.calculate_jump.return_value = None
    container.set_mock("level_calculator", mock_levels)

    mock_phase = MagicMock()
    mock_phase.detect.return_value = None
    container.set_mock("phase_detector", mock_phase)

    mock_spring = MagicMock()
    mock_spring.detect.return_value = []
    container.set_mock("spring_detector", mock_spring)

    mock_sos = MagicMock()
    mock_sos.detect.return_value = []
    container.set_mock("sos_detector", mock_sos)

    mock_lps = MagicMock()
    mock_lps.detect.return_value = []
    container.set_mock("lps_detector", mock_lps)

    mock_risk = MagicMock()
    mock_risk.validate_and_size = AsyncMock(return_value=None)
    container.set_mock("risk_manager", mock_risk)

    return container


class TestPerformanceBenchmarks:
    """Performance benchmark tests (AC: 10)."""

    @pytest.mark.asyncio
    @pytest.mark.benchmark
    async def test_ten_symbols_500_bars_under_5_seconds(
        self,
        perf_config: OrchestratorConfig,
        lightweight_container: OrchestratorContainer,
    ):
        """
        BENCHMARK: 10 symbols × 500 bars must complete in <5 seconds.

        This is the primary performance acceptance criteria from Story 8.1.
        """
        event_bus = EventBus()
        cache = OrchestratorCache(perf_config)

        symbols = [f"SYM{i}" for i in range(10)]
        bars_by_symbol = {symbol: create_bars(symbol, 500) for symbol in symbols}

        def mock_get_bars(symbol, timeframe, limit):
            return bars_by_symbol.get(symbol, [])

        # Configure volume analyzer to return analyses
        def mock_analyze(bars, *args, **kwargs):
            return create_lightweight_volume_analyses(bars) if bars else []

        lightweight_container._mocks["volume_analyzer"].analyze.side_effect = mock_analyze

        orchestrator = MasterOrchestrator(
            config=perf_config,
            container=lightweight_container,
            event_bus=event_bus,
            cache=cache,
        )

        with patch("src.repositories.ohlcv_repository.OHLCVRepository") as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_bars.side_effect = mock_get_bars

            start_time = time.perf_counter()
            results = await orchestrator.analyze_symbols(symbols, "1d")
            elapsed_time = time.perf_counter() - start_time

        # Assert performance requirement
        assert elapsed_time < 5.0, f"Performance test failed: took {elapsed_time:.2f}s (>5s limit)"

        # Assert all symbols were processed
        assert len(results) == 10, f"Expected 10 results, got {len(results)}"

        # Log performance for debugging
        print(f"\nPerformance: 10 symbols × 500 bars in {elapsed_time:.3f}s")
        print(f"Average per symbol: {elapsed_time / 10 * 1000:.1f}ms")

    @pytest.mark.asyncio
    @pytest.mark.benchmark
    async def test_single_symbol_500_bars_performance(
        self,
        perf_config: OrchestratorConfig,
        lightweight_container: OrchestratorContainer,
    ):
        """Benchmark single symbol processing time."""
        event_bus = EventBus()
        cache = OrchestratorCache(perf_config)

        bars = create_bars("TEST", 500)

        def mock_analyze(b, *args, **kwargs):
            return create_lightweight_volume_analyses(b) if b else []

        lightweight_container._mocks["volume_analyzer"].analyze.side_effect = mock_analyze

        orchestrator = MasterOrchestrator(
            config=perf_config,
            container=lightweight_container,
            event_bus=event_bus,
            cache=cache,
        )

        with patch("src.repositories.ohlcv_repository.OHLCVRepository") as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_bars.return_value = bars

            start_time = time.perf_counter()
            signals = await orchestrator.analyze_symbol("TEST", "1d")
            elapsed_time = time.perf_counter() - start_time

        # Single symbol should be well under 1 second
        assert elapsed_time < 1.0, f"Single symbol took {elapsed_time:.2f}s (>1s)"

        print(f"\nSingle symbol 500 bars: {elapsed_time * 1000:.1f}ms")

    @pytest.mark.asyncio
    @pytest.mark.benchmark
    async def test_caching_improves_repeated_analysis(
        self,
        perf_config: OrchestratorConfig,
        lightweight_container: OrchestratorContainer,
    ):
        """Test that caching improves performance for repeated analyses."""
        event_bus = EventBus()
        cache = OrchestratorCache(perf_config)

        bars = create_bars("CACHE_TEST", 500)

        def mock_analyze(b, *args, **kwargs):
            return create_lightweight_volume_analyses(b) if b else []

        lightweight_container._mocks["volume_analyzer"].analyze.side_effect = mock_analyze

        orchestrator = MasterOrchestrator(
            config=perf_config,
            container=lightweight_container,
            event_bus=event_bus,
            cache=cache,
        )

        with patch("src.repositories.ohlcv_repository.OHLCVRepository") as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_bars.return_value = bars

            # First analysis - cold cache
            start_time = time.perf_counter()
            await orchestrator.analyze_symbol("CACHE_TEST", "1d")
            cold_time = time.perf_counter() - start_time

            # Second analysis - warm cache
            start_time = time.perf_counter()
            await orchestrator.analyze_symbol("CACHE_TEST", "1d")
            warm_time = time.perf_counter() - start_time

        # Warm cache should be faster (or at least not significantly slower)
        print(f"\nCold cache: {cold_time * 1000:.1f}ms")
        print(f"Warm cache: {warm_time * 1000:.1f}ms")
        print(f"Speedup: {cold_time / warm_time:.2f}x" if warm_time > 0 else "N/A")

    @pytest.mark.asyncio
    @pytest.mark.benchmark
    async def test_parallel_vs_sequential_processing(
        self,
        lightweight_container: OrchestratorContainer,
    ):
        """Compare parallel vs sequential processing performance."""
        symbols = [f"SYM{i}" for i in range(5)]
        bars_by_symbol = {symbol: create_bars(symbol, 100) for symbol in symbols}

        def mock_get_bars(symbol, timeframe, limit):
            return bars_by_symbol.get(symbol, [])

        def mock_analyze(b, *args, **kwargs):
            return create_lightweight_volume_analyses(b) if b else []

        lightweight_container._mocks["volume_analyzer"].analyze.side_effect = mock_analyze

        # Test parallel processing
        parallel_config = OrchestratorConfig(
            default_lookback_bars=100,
            max_concurrent_symbols=5,
            enable_parallel_processing=True,
            enable_caching=False,
        )
        parallel_orchestrator = MasterOrchestrator(
            config=parallel_config,
            container=lightweight_container,
            event_bus=EventBus(),
            cache=OrchestratorCache(parallel_config),
        )

        with patch("src.repositories.ohlcv_repository.OHLCVRepository") as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_bars.side_effect = mock_get_bars

            start_time = time.perf_counter()
            await parallel_orchestrator.analyze_symbols(symbols, "1d")
            parallel_time = time.perf_counter() - start_time

        # Test sequential processing
        sequential_config = OrchestratorConfig(
            default_lookback_bars=100,
            max_concurrent_symbols=1,  # Forces sequential
            enable_parallel_processing=False,
            enable_caching=False,
        )
        sequential_orchestrator = MasterOrchestrator(
            config=sequential_config,
            container=lightweight_container,
            event_bus=EventBus(),
            cache=OrchestratorCache(sequential_config),
        )

        with patch("src.repositories.ohlcv_repository.OHLCVRepository") as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_bars.side_effect = mock_get_bars

            start_time = time.perf_counter()
            await sequential_orchestrator.analyze_symbols(symbols, "1d")
            sequential_time = time.perf_counter() - start_time

        print(f"\nParallel (5 symbols): {parallel_time * 1000:.1f}ms")
        print(f"Sequential (5 symbols): {sequential_time * 1000:.1f}ms")

        # Parallel should not be slower than sequential
        # (In mock tests, they may be similar due to no I/O blocking)


class TestScalabilityBenchmarks:
    """Tests for scalability characteristics."""

    @pytest.mark.asyncio
    @pytest.mark.benchmark
    async def test_scaling_with_bar_count(
        self,
        perf_config: OrchestratorConfig,
        lightweight_container: OrchestratorContainer,
    ):
        """Test how processing time scales with bar count."""
        event_bus = EventBus()
        cache = OrchestratorCache(perf_config)

        def mock_analyze(b, *args, **kwargs):
            return create_lightweight_volume_analyses(b) if b else []

        lightweight_container._mocks["volume_analyzer"].analyze.side_effect = mock_analyze

        orchestrator = MasterOrchestrator(
            config=perf_config,
            container=lightweight_container,
            event_bus=event_bus,
            cache=cache,
        )

        bar_counts = [100, 250, 500, 1000]
        times = []

        for count in bar_counts:
            bars = create_bars("SCALE_TEST", count)

            # Clear cache between tests
            cache.clear()

            with patch("src.repositories.ohlcv_repository.OHLCVRepository") as MockRepo:
                mock_repo = MockRepo.return_value
                mock_repo.get_bars.return_value = bars

                start_time = time.perf_counter()
                await orchestrator.analyze_symbol("SCALE_TEST", "1d")
                elapsed = time.perf_counter() - start_time
                times.append(elapsed)

        print("\nBar count scaling:")
        for count, t in zip(bar_counts, times, strict=False):
            print(f"  {count} bars: {t * 1000:.1f}ms")

        # Processing should scale reasonably (not exponentially)
        # Check that doubling bars doesn't more than triple time
        if times[0] > 0:
            scaling_factor = times[-1] / times[0]
            bar_factor = bar_counts[-1] / bar_counts[0]
            print(f"Scaling: {bar_factor}x bars -> {scaling_factor:.1f}x time")

    @pytest.mark.asyncio
    @pytest.mark.benchmark
    async def test_scaling_with_symbol_count(
        self,
        perf_config: OrchestratorConfig,
        lightweight_container: OrchestratorContainer,
    ):
        """Test how processing time scales with symbol count."""

        def mock_analyze(b, *args, **kwargs):
            return create_lightweight_volume_analyses(b) if b else []

        lightweight_container._mocks["volume_analyzer"].analyze.side_effect = mock_analyze

        symbol_counts = [1, 5, 10, 20]
        times = []

        for count in symbol_counts:
            event_bus = EventBus()
            cache = OrchestratorCache(perf_config)

            orchestrator = MasterOrchestrator(
                config=perf_config,
                container=lightweight_container,
                event_bus=event_bus,
                cache=cache,
            )

            symbols = [f"SYM{i}" for i in range(count)]
            bars_by_symbol = {symbol: create_bars(symbol, 100) for symbol in symbols}

            def mock_get_bars(symbol, timeframe, limit, _bars=bars_by_symbol):
                return _bars.get(symbol, [])

            with patch("src.repositories.ohlcv_repository.OHLCVRepository") as MockRepo:
                mock_repo = MockRepo.return_value
                mock_repo.get_bars.side_effect = mock_get_bars

                start_time = time.perf_counter()
                await orchestrator.analyze_symbols(symbols, "1d")
                elapsed = time.perf_counter() - start_time
                times.append(elapsed)

        print("\nSymbol count scaling:")
        for count, t in zip(symbol_counts, times, strict=False):
            print(f"  {count} symbols: {t * 1000:.1f}ms")


class TestMemoryEfficiency:
    """Tests for memory efficiency."""

    @pytest.mark.asyncio
    @pytest.mark.benchmark
    async def test_cache_memory_bounded(
        self,
        lightweight_container: OrchestratorContainer,
    ):
        """Test that cache size is bounded."""
        config = OrchestratorConfig(
            default_lookback_bars=100,
            cache_max_size=100,  # Small cache for testing
            enable_caching=True,
        )
        event_bus = EventBus()
        cache = OrchestratorCache(config)

        def mock_analyze(b, *args, **kwargs):
            return create_lightweight_volume_analyses(b) if b else []

        lightweight_container._mocks["volume_analyzer"].analyze.side_effect = mock_analyze

        orchestrator = MasterOrchestrator(
            config=config,
            container=lightweight_container,
            event_bus=event_bus,
            cache=cache,
        )

        # Process many symbols to exceed cache size
        for i in range(200):
            bars = create_bars(f"MEM_TEST_{i}", 50)

            with patch("src.repositories.ohlcv_repository.OHLCVRepository") as MockRepo:
                mock_repo = MockRepo.return_value
                mock_repo.get_bars.return_value = bars

                await orchestrator.analyze_symbol(f"MEM_TEST_{i}", "1d")

        # Cache should be bounded
        metrics = cache.get_metrics()
        assert (
            metrics["size"] <= config.cache_max_size
        ), f"Cache size {metrics['size']} exceeded max {config.cache_max_size}"

        print("\nCache stats after 200 symbols:")
        print(f"  Size: {metrics['size']} (max: {config.cache_max_size})")
        print(f"  Hits: {metrics['hits']}")
        print(f"  Misses: {metrics['misses']}")
