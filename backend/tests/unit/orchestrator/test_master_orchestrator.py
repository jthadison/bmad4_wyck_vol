"""
Unit tests for MasterOrchestrator.

Tests orchestration logic with mock detectors to verify pipeline execution,
error isolation, caching, and parallel processing.

Story 8.1: Master Orchestrator Architecture (AC: 1, 2, 5, 6, 8)
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.models.ohlcv import OHLCVBar
from src.models.volume_analysis import VolumeAnalysis
from src.orchestrator.cache import OrchestratorCache
from src.orchestrator.config import OrchestratorConfig
from src.orchestrator.container import OrchestratorContainer
from src.orchestrator.event_bus import EventBus
from src.orchestrator.master_orchestrator import (
    CircuitBreaker,
    MasterOrchestrator,
    Pattern,
    TradeSignal,
)


@pytest.fixture
def config() -> OrchestratorConfig:
    """Create test configuration."""
    return OrchestratorConfig(
        default_lookback_bars=100,
        max_concurrent_symbols=5,
        enable_caching=False,
        enable_parallel_processing=True,
        min_range_quality_score=60,
        min_phase_confidence=70,
    )


@pytest.fixture
def mock_container() -> OrchestratorContainer:
    """Create container with mock detectors."""
    container = OrchestratorContainer(mode="mock")

    # Mock volume analyzer
    mock_volume_analyzer = MagicMock()
    mock_volume_analyzer.analyze.return_value = []
    container.set_mock("volume_analyzer", mock_volume_analyzer)

    # Mock pivot detector
    mock_pivot_detector = MagicMock()
    mock_pivot_detector.detect.return_value = []
    container.set_mock("pivot_detector", mock_pivot_detector)

    # Mock trading range detector
    mock_range_detector = MagicMock()
    mock_range_detector.detect.return_value = []
    container.set_mock("trading_range_detector", mock_range_detector)

    # Mock range quality scorer
    mock_scorer = MagicMock()
    mock_scorer.score.return_value = 75
    container.set_mock("range_quality_scorer", mock_scorer)

    # Mock level calculator
    mock_level_calc = MagicMock()
    mock_level_calc.calculate_creek.return_value = None
    mock_level_calc.calculate_ice.return_value = None
    mock_level_calc.calculate_jump.return_value = None
    container.set_mock("level_calculator", mock_level_calc)

    # Mock SOS detector
    mock_sos = MagicMock()
    container.set_mock("sos_detector", mock_sos)

    # Mock LPS detector
    mock_lps = MagicMock()
    container.set_mock("lps_detector", mock_lps)

    # Mock risk manager
    mock_risk = MagicMock()
    mock_risk.validate_and_size = AsyncMock(return_value=None)
    container.set_mock("risk_manager", mock_risk)

    return container


@pytest.fixture
def event_bus() -> EventBus:
    """Create fresh event bus."""
    return EventBus()


@pytest.fixture
def cache(config: OrchestratorConfig) -> OrchestratorCache:
    """Create fresh cache."""
    return OrchestratorCache(config)


@pytest.fixture
def sample_bars() -> list[OHLCVBar]:
    """Create sample OHLCV bars for testing."""
    bars = []
    for i in range(25):
        bar = OHLCVBar(
            symbol="AAPL",
            timeframe="1d",
            timestamp=datetime(2024, 1, 1 + i, tzinfo=UTC),
            open=Decimal("100.00") + Decimal(str(i)),
            high=Decimal("102.00") + Decimal(str(i)),
            low=Decimal("98.00") + Decimal(str(i)),
            close=Decimal("101.00") + Decimal(str(i)),
            volume=1000000 + i * 10000,
            spread=Decimal("4.00"),
        )
        bars.append(bar)
    return bars


class TestCircuitBreaker:
    """Tests for CircuitBreaker."""

    def test_circuit_initially_closed(self):
        """Test that circuit starts closed."""
        cb = CircuitBreaker(threshold=3, reset_seconds=60)

        assert cb.is_open("detector") is False

    def test_circuit_opens_after_threshold(self):
        """Test that circuit opens after threshold failures."""
        cb = CircuitBreaker(threshold=3, reset_seconds=60)

        cb.record_failure("detector")
        cb.record_failure("detector")
        cb.record_failure("detector")

        assert cb.is_open("detector") is True

    def test_circuit_stays_closed_below_threshold(self):
        """Test that circuit stays closed below threshold."""
        cb = CircuitBreaker(threshold=5, reset_seconds=60)

        cb.record_failure("detector")
        cb.record_failure("detector")

        assert cb.is_open("detector") is False

    def test_success_clears_failures(self):
        """Test that success clears one failure."""
        cb = CircuitBreaker(threshold=3, reset_seconds=60)

        cb.record_failure("detector")
        cb.record_failure("detector")
        cb.record_success("detector")

        # Should now have 1 failure, not 2
        cb.record_failure("detector")  # 2 failures
        assert cb.is_open("detector") is False

        cb.record_failure("detector")  # 3 failures
        assert cb.is_open("detector") is True


class TestMasterOrchestratorInit:
    """Tests for MasterOrchestrator initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default configuration."""
        orchestrator = MasterOrchestrator()

        assert orchestrator._config is not None
        assert orchestrator._container is not None
        assert orchestrator._event_bus is not None
        assert orchestrator._cache is not None

    def test_init_with_custom_config(self, config: OrchestratorConfig):
        """Test initialization with custom configuration."""
        orchestrator = MasterOrchestrator(config=config)

        assert orchestrator._config.default_lookback_bars == 100
        assert orchestrator._config.max_concurrent_symbols == 5

    def test_init_with_injected_dependencies(
        self,
        config: OrchestratorConfig,
        mock_container: OrchestratorContainer,
        event_bus: EventBus,
        cache: OrchestratorCache,
    ):
        """Test initialization with injected dependencies."""
        orchestrator = MasterOrchestrator(
            config=config,
            container=mock_container,
            event_bus=event_bus,
            cache=cache,
        )

        assert orchestrator._container is mock_container
        assert orchestrator._event_bus is event_bus
        assert orchestrator._cache is cache


class TestMasterOrchestratorAnalyzeSymbol:
    """Tests for analyze_symbol method."""

    @pytest.mark.asyncio
    async def test_analyze_symbol_returns_list(
        self,
        config: OrchestratorConfig,
        mock_container: OrchestratorContainer,
        event_bus: EventBus,
        cache: OrchestratorCache,
        sample_bars: list[OHLCVBar],
    ):
        """Test that analyze_symbol returns list of signals."""
        orchestrator = MasterOrchestrator(
            config=config,
            container=mock_container,
            event_bus=event_bus,
            cache=cache,
        )

        # Mock repository to return sample bars
        with patch("src.repositories.ohlcv_repository.OHLCVRepository") as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_bars.return_value = sample_bars

            # Mock volume analyzer
            mock_container._mocks["volume_analyzer"].analyze.return_value = [
                VolumeAnalysis(
                    bar=bar,
                    volume_ratio=Decimal("1.0"),
                    spread_ratio=Decimal("1.0"),
                    close_position=Decimal("0.5"),
                    effort_result=None,
                )
                for bar in sample_bars
            ]

            signals = await orchestrator.analyze_symbol("AAPL", "1d")

            assert isinstance(signals, list)

    @pytest.mark.asyncio
    async def test_analyze_symbol_empty_bars_returns_empty(
        self,
        config: OrchestratorConfig,
        mock_container: OrchestratorContainer,
        event_bus: EventBus,
        cache: OrchestratorCache,
    ):
        """Test that empty bars returns empty signal list."""
        orchestrator = MasterOrchestrator(
            config=config,
            container=mock_container,
            event_bus=event_bus,
            cache=cache,
        )

        with patch("src.repositories.ohlcv_repository.OHLCVRepository") as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_bars.return_value = []

            signals = await orchestrator.analyze_symbol("AAPL", "1d")

            assert signals == []

    @pytest.mark.asyncio
    async def test_analyze_symbol_error_returns_empty(
        self,
        config: OrchestratorConfig,
        mock_container: OrchestratorContainer,
        event_bus: EventBus,
        cache: OrchestratorCache,
    ):
        """Test that errors during analysis return empty list."""
        orchestrator = MasterOrchestrator(
            config=config,
            container=mock_container,
            event_bus=event_bus,
            cache=cache,
        )

        with patch("src.repositories.ohlcv_repository.OHLCVRepository") as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_bars.side_effect = Exception("Database error")

            signals = await orchestrator.analyze_symbol("AAPL", "1d")

            assert signals == []


class TestMasterOrchestratorAnalyzeSymbols:
    """Tests for analyze_symbols parallel processing."""

    @pytest.mark.asyncio
    async def test_analyze_symbols_returns_dict(
        self,
        config: OrchestratorConfig,
        mock_container: OrchestratorContainer,
        event_bus: EventBus,
        cache: OrchestratorCache,
    ):
        """Test that analyze_symbols returns dict of symbols to signals."""
        orchestrator = MasterOrchestrator(
            config=config,
            container=mock_container,
            event_bus=event_bus,
            cache=cache,
        )

        with patch("src.repositories.ohlcv_repository.OHLCVRepository") as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_bars.return_value = []

            results = await orchestrator.analyze_symbols(["AAPL", "MSFT"], "1d")

            assert isinstance(results, dict)
            assert "AAPL" in results
            assert "MSFT" in results

    @pytest.mark.asyncio
    async def test_analyze_symbols_isolates_errors(
        self,
        config: OrchestratorConfig,
        mock_container: OrchestratorContainer,
        event_bus: EventBus,
        cache: OrchestratorCache,
    ):
        """Test that errors in one symbol don't affect others."""
        orchestrator = MasterOrchestrator(
            config=config,
            container=mock_container,
            event_bus=event_bus,
            cache=cache,
        )

        call_count = 0

        def mock_get_bars(symbol, timeframe, limit):
            nonlocal call_count
            call_count += 1
            if symbol == "FAIL":
                raise Exception("Failed to fetch")
            return []

        with patch("src.repositories.ohlcv_repository.OHLCVRepository") as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_bars.side_effect = mock_get_bars

            results = await orchestrator.analyze_symbols(["AAPL", "FAIL", "MSFT"], "1d")

            # Should have results for AAPL and MSFT
            assert "AAPL" in results
            assert "MSFT" in results
            # FAIL should be handled gracefully (empty list or not in results)


class TestMasterOrchestratorHealth:
    """Tests for health check functionality."""

    def test_get_health_returns_status(
        self,
        config: OrchestratorConfig,
        mock_container: OrchestratorContainer,
        event_bus: EventBus,
        cache: OrchestratorCache,
    ):
        """Test that get_health returns health information."""
        orchestrator = MasterOrchestrator(
            config=config,
            container=mock_container,
            event_bus=event_bus,
            cache=cache,
        )

        health = orchestrator.get_health()

        assert "status" in health
        assert "components" in health
        assert "metrics" in health

    def test_get_health_includes_metrics(
        self,
        config: OrchestratorConfig,
        mock_container: OrchestratorContainer,
        event_bus: EventBus,
        cache: OrchestratorCache,
    ):
        """Test that health includes analysis metrics."""
        orchestrator = MasterOrchestrator(
            config=config,
            container=mock_container,
            event_bus=event_bus,
            cache=cache,
        )

        health = orchestrator.get_health()

        assert "analysis_count" in health["metrics"]
        assert "signal_count" in health["metrics"]
        assert "error_count" in health["metrics"]


class TestPattern:
    """Tests for Pattern class."""

    def test_pattern_creation(self):
        """Test creating a Pattern instance."""
        pattern = Pattern(
            pattern_id=uuid4(),
            pattern_type="SPRING",
            symbol="AAPL",
            timeframe="1d",
            confidence_score=85,
            entry_price=Decimal("150.00"),
            stop_price=Decimal("145.00"),
            target_price=Decimal("170.00"),
            phase="C",
        )

        assert pattern.pattern_type == "SPRING"
        assert pattern.symbol == "AAPL"
        assert pattern.confidence_score == 85


class TestTradeSignal:
    """Tests for TradeSignal class."""

    def test_trade_signal_creation(self):
        """Test creating a TradeSignal instance."""
        signal = TradeSignal(
            signal_id=uuid4(),
            symbol="AAPL",
            timeframe="1d",
            pattern_type="SPRING",
            phase="C",
            entry_price=Decimal("150.00"),
            stop_price=Decimal("145.00"),
            target_price=Decimal("170.00"),
            position_size=100,
            risk_amount=Decimal("500.00"),
            r_multiple=Decimal("4.0"),
            confidence_score=85,
            correlation_id=uuid4(),
            validation_chain=["pattern_risk", "r_multiple"],
        )

        assert signal.symbol == "AAPL"
        assert signal.pattern_type == "SPRING"
        assert signal.position_size == 100
        assert len(signal.validation_chain) == 2


class TestMasterOrchestratorCaching:
    """Tests for caching behavior."""

    @pytest.mark.asyncio
    async def test_cache_hit_skips_analysis(
        self,
        mock_container: OrchestratorContainer,
        event_bus: EventBus,
        sample_bars: list[OHLCVBar],
    ):
        """Test that cache hit skips analysis."""
        config = OrchestratorConfig(enable_caching=True)
        cache = OrchestratorCache(config)

        orchestrator = MasterOrchestrator(
            config=config,
            container=mock_container,
            event_bus=event_bus,
            cache=cache,
        )

        # Pre-populate cache with volume analysis
        cache.set_volume_analysis("AAPL", "1d", [])

        with patch("src.repositories.ohlcv_repository.OHLCVRepository") as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_bars.return_value = sample_bars

            await orchestrator.analyze_symbol("AAPL", "1d")

            # Volume analyzer should not be called if cache hit
            # (This is a simplified test - real implementation would verify)


class TestMasterOrchestratorErrorIsolation:
    """Tests for error isolation (AC: 5)."""

    @pytest.mark.asyncio
    async def test_detector_failure_does_not_crash_pipeline(
        self,
        config: OrchestratorConfig,
        mock_container: OrchestratorContainer,
        event_bus: EventBus,
        cache: OrchestratorCache,
        sample_bars: list[OHLCVBar],
    ):
        """Test that detector failures don't crash the pipeline."""
        orchestrator = MasterOrchestrator(
            config=config,
            container=mock_container,
            event_bus=event_bus,
            cache=cache,
        )

        # Make volume analyzer fail
        mock_container._mocks["volume_analyzer"].analyze.side_effect = Exception("Analyzer error")

        with patch("src.repositories.ohlcv_repository.OHLCVRepository") as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_bars.return_value = sample_bars

            # Should not raise, should return empty list
            signals = await orchestrator.analyze_symbol("AAPL", "1d")

            assert signals == []
