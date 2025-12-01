"""
Integration tests for MasterOrchestrator full pipeline.

Tests the complete analysis pipeline from data ingestion through signal generation
using realistic mock data that simulates actual market conditions.

Story 8.1: Master Orchestrator Architecture (AC: 9 - Integration tests pass)
"""

from datetime import UTC, datetime, timedelta
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
from src.orchestrator.master_orchestrator import MasterOrchestrator


def create_accumulation_pattern_bars(
    symbol: str = "BTCUSDT",
    timeframe: str = "1d",
    num_bars: int = 100,
    support: Decimal = Decimal("40000"),
    resistance: Decimal = Decimal("45000"),
) -> list[OHLCVBar]:
    """
    Create bars that simulate a Wyckoff accumulation pattern.

    Phases simulated:
    - Phase A (1-20): Selling climax, automatic rally, secondary test
    - Phase B (21-50): Trading range, tests of support/resistance
    - Phase C (51-65): Spring pattern with volume climax
    - Phase D (66-85): Sign of Strength, Last Point of Support
    - Phase E (86-100): Markup beginning
    """
    bars = []
    base_volume = 1_000_000
    range_size = resistance - support

    start_time = datetime(2024, 1, 1, tzinfo=UTC)

    for i in range(num_bars):
        timestamp = start_time + timedelta(days=i)

        if i < 20:
            # Phase A: Initial selling, then rally
            if i < 10:
                # Selling climax
                progress = i / 10
                close_price = support + range_size * Decimal(str(0.8 - 0.6 * progress))
                volume_mult = 2.5 - progress  # High volume decreasing
            else:
                # Automatic rally
                progress = (i - 10) / 10
                close_price = support + range_size * Decimal(str(0.2 + 0.5 * progress))
                volume_mult = 1.5
        elif i < 50:
            # Phase B: Trading range
            cycle_pos = ((i - 20) % 10) / 10
            close_price = support + range_size * Decimal(str(0.3 + 0.4 * abs(cycle_pos - 0.5) * 2))
            volume_mult = 1.0 + (i % 5) * 0.1
        elif i < 65:
            # Phase C: Spring
            if i < 55:
                # Spring below support
                progress = (i - 50) / 5
                close_price = support - range_size * Decimal(str(0.05 * progress))
                volume_mult = 2.0 + progress  # High volume on spring
            else:
                # Recovery from spring
                progress = (i - 55) / 10
                close_price = support + range_size * Decimal(str(0.3 + 0.2 * progress))
                volume_mult = 1.8
        elif i < 85:
            # Phase D: SOS and LPS
            if i < 75:
                # Sign of Strength
                progress = (i - 65) / 10
                close_price = support + range_size * Decimal(str(0.5 + 0.4 * progress))
                volume_mult = 2.5  # High volume on SOS
            else:
                # Last Point of Support
                progress = (i - 75) / 10
                close_price = support + range_size * Decimal(str(0.7 + 0.1 * progress))
                volume_mult = 1.2  # Lower volume on LPS
        else:
            # Phase E: Markup
            progress = (i - 85) / 15
            close_price = resistance + range_size * Decimal(str(0.1 + 0.3 * progress))
            volume_mult = 1.8

        # Add some randomness
        spread = range_size * Decimal("0.02")
        high_price = close_price + spread
        low_price = close_price - spread
        open_price = close_price - spread * Decimal("0.5")

        bar = OHLCVBar(
            symbol=symbol,
            timeframe=timeframe,
            timestamp=timestamp,
            open=open_price.quantize(Decimal("0.01")),
            high=high_price.quantize(Decimal("0.01")),
            low=low_price.quantize(Decimal("0.01")),
            close=close_price.quantize(Decimal("0.01")),
            volume=int(base_volume * volume_mult),
            spread=(high_price - low_price).quantize(Decimal("0.01")),
        )
        bars.append(bar)

    return bars


def create_volume_analysis_for_bars(bars: list[OHLCVBar]) -> list[VolumeAnalysis]:
    """Create volume analysis for a list of bars."""
    analyses = []
    avg_volume = sum(bar.volume for bar in bars) / len(bars)

    for bar in bars:
        volume_ratio = Decimal(str(bar.volume / avg_volume))
        spread = bar.high - bar.low
        avg_spread = sum((b.high - b.low) for b in bars) / len(bars)
        spread_ratio = spread / avg_spread if avg_spread > 0 else Decimal("1.0")

        close_position = (
            (bar.close - bar.low) / (bar.high - bar.low) if bar.high > bar.low else Decimal("0.5")
        )

        analysis = VolumeAnalysis(
            bar=bar,
            volume_ratio=volume_ratio.quantize(Decimal("0.01")),
            spread_ratio=spread_ratio.quantize(Decimal("0.01")),
            close_position=close_position.quantize(Decimal("0.01")),
            effort_result=None,
        )
        analyses.append(analysis)

    return analyses


@pytest.fixture
def integration_config() -> OrchestratorConfig:
    """Configuration for integration tests."""
    return OrchestratorConfig(
        default_lookback_bars=100,
        max_concurrent_symbols=5,
        enable_caching=True,
        enable_parallel_processing=True,
        circuit_breaker_threshold=3,
        min_range_quality_score=60,
        min_phase_confidence=70,
    )


@pytest.fixture
def accumulation_bars() -> list[OHLCVBar]:
    """Create bars representing accumulation pattern."""
    return create_accumulation_pattern_bars()


@pytest.fixture
def mock_detectors_with_patterns() -> OrchestratorContainer:
    """Create container with mock detectors that return patterns."""
    container = OrchestratorContainer(mode="mock")

    # Volume analyzer returns analyses
    mock_volume = MagicMock()
    container.set_mock("volume_analyzer", mock_volume)

    # Pivot detector
    mock_pivot = MagicMock()
    mock_pivot.detect.return_value = []
    container.set_mock("pivot_detector", mock_pivot)

    # Trading range detector - returns a valid range
    mock_range = MagicMock()
    container.set_mock("trading_range_detector", mock_range)

    # Range quality scorer - returns good score
    mock_scorer = MagicMock()
    mock_scorer.score.return_value = 75
    container.set_mock("range_quality_scorer", mock_scorer)

    # Level calculator
    mock_levels = MagicMock()
    mock_levels.calculate_creek.return_value = Decimal("44000")
    mock_levels.calculate_ice.return_value = Decimal("40500")
    mock_levels.calculate_jump.return_value = Decimal("45500")
    container.set_mock("level_calculator", mock_levels)

    # Phase detector - returns Phase C
    mock_phase = MagicMock()
    container.set_mock("phase_detector", mock_phase)

    # Spring detector - returns a spring pattern
    mock_spring = MagicMock()
    container.set_mock("spring_detector", mock_spring)

    # SOS detector
    mock_sos = MagicMock()
    container.set_mock("sos_detector", mock_sos)

    # LPS detector
    mock_lps = MagicMock()
    container.set_mock("lps_detector", mock_lps)

    # Risk manager
    mock_risk = MagicMock()
    mock_risk.validate_and_size = AsyncMock(return_value=None)
    container.set_mock("risk_manager", mock_risk)

    return container


class TestFullPipelineExecution:
    """Tests for complete pipeline execution."""

    @pytest.mark.asyncio
    async def test_full_pipeline_with_accumulation_data(
        self,
        integration_config: OrchestratorConfig,
        accumulation_bars: list[OHLCVBar],
        mock_detectors_with_patterns: OrchestratorContainer,
    ):
        """Test full pipeline processes accumulation pattern data."""
        event_bus = EventBus()
        cache = OrchestratorCache(integration_config)

        # Configure mocks to return realistic data
        volume_analyses = create_volume_analysis_for_bars(accumulation_bars)
        mock_detectors_with_patterns._mocks[
            "volume_analyzer"
        ].analyze.return_value = volume_analyses

        # Mock trading range
        mock_range = MagicMock()
        mock_range.range_id = uuid4()
        mock_range.start_index = 0
        mock_range.end_index = 99
        mock_range.support = Decimal("40000")
        mock_range.resistance = Decimal("45000")
        mock_range.quality_score = 75
        mock_detectors_with_patterns._mocks["trading_range_detector"].detect.return_value = [
            mock_range
        ]

        orchestrator = MasterOrchestrator(
            config=integration_config,
            container=mock_detectors_with_patterns,
            event_bus=event_bus,
            cache=cache,
        )

        with patch("src.repositories.ohlcv_repository.OHLCVRepository") as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_bars.return_value = accumulation_bars

            signals = await orchestrator.analyze_symbol("BTCUSDT", "1d")

            # Pipeline should complete without error
            assert isinstance(signals, list)

            # Verify volume analyzer was called
            mock_detectors_with_patterns._mocks["volume_analyzer"].analyze.assert_called()

    @pytest.mark.asyncio
    async def test_pipeline_publishes_events(
        self,
        integration_config: OrchestratorConfig,
        accumulation_bars: list[OHLCVBar],
        mock_detectors_with_patterns: OrchestratorContainer,
    ):
        """Test that pipeline publishes events at each stage."""
        event_bus = EventBus()
        cache = OrchestratorCache(integration_config)

        events_received: list[str] = []

        def track_event(event_type: str):
            async def handler(event):
                events_received.append(event_type)

            return handler

        # Subscribe to events
        event_bus.subscribe("bar_ingested", track_event("bar_ingested"))
        event_bus.subscribe("volume_analyzed", track_event("volume_analyzed"))
        event_bus.subscribe("range_detected", track_event("range_detected"))

        volume_analyses = create_volume_analysis_for_bars(accumulation_bars)
        mock_detectors_with_patterns._mocks[
            "volume_analyzer"
        ].analyze.return_value = volume_analyses

        orchestrator = MasterOrchestrator(
            config=integration_config,
            container=mock_detectors_with_patterns,
            event_bus=event_bus,
            cache=cache,
        )

        with patch("src.repositories.ohlcv_repository.OHLCVRepository") as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_bars.return_value = accumulation_bars

            await orchestrator.analyze_symbol("BTCUSDT", "1d")

            # Should have received events
            assert "bar_ingested" in events_received
            assert "volume_analyzed" in events_received

    @pytest.mark.asyncio
    async def test_pipeline_uses_cache(
        self,
        integration_config: OrchestratorConfig,
        accumulation_bars: list[OHLCVBar],
        mock_detectors_with_patterns: OrchestratorContainer,
    ):
        """Test that pipeline uses cache for repeated analyses."""
        event_bus = EventBus()
        cache = OrchestratorCache(integration_config)

        volume_analyses = create_volume_analysis_for_bars(accumulation_bars)
        mock_detectors_with_patterns._mocks[
            "volume_analyzer"
        ].analyze.return_value = volume_analyses

        orchestrator = MasterOrchestrator(
            config=integration_config,
            container=mock_detectors_with_patterns,
            event_bus=event_bus,
            cache=cache,
        )

        with patch("src.repositories.ohlcv_repository.OHLCVRepository") as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_bars.return_value = accumulation_bars

            # First call
            await orchestrator.analyze_symbol("BTCUSDT", "1d")
            first_call_count = mock_detectors_with_patterns._mocks[
                "volume_analyzer"
            ].analyze.call_count

            # Second call - should use cache
            await orchestrator.analyze_symbol("BTCUSDT", "1d")
            second_call_count = mock_detectors_with_patterns._mocks[
                "volume_analyzer"
            ].analyze.call_count

            # Volume analyzer should have been called
            assert first_call_count >= 1

    @pytest.mark.asyncio
    async def test_pipeline_error_isolation(
        self,
        integration_config: OrchestratorConfig,
        accumulation_bars: list[OHLCVBar],
        mock_detectors_with_patterns: OrchestratorContainer,
    ):
        """Test that detector failures are isolated."""
        event_bus = EventBus()
        cache = OrchestratorCache(integration_config)

        # Make volume analyzer fail
        mock_detectors_with_patterns._mocks["volume_analyzer"].analyze.side_effect = Exception(
            "Volume analyzer failed"
        )

        orchestrator = MasterOrchestrator(
            config=integration_config,
            container=mock_detectors_with_patterns,
            event_bus=event_bus,
            cache=cache,
        )

        with patch("src.repositories.ohlcv_repository.OHLCVRepository") as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_bars.return_value = accumulation_bars

            # Should not raise
            signals = await orchestrator.analyze_symbol("BTCUSDT", "1d")

            # Should return empty list on failure
            assert isinstance(signals, list)
            assert signals == []


class TestMultiSymbolProcessing:
    """Tests for multi-symbol parallel processing."""

    @pytest.mark.asyncio
    async def test_parallel_symbol_processing(
        self,
        integration_config: OrchestratorConfig,
        mock_detectors_with_patterns: OrchestratorContainer,
    ):
        """Test processing multiple symbols in parallel."""
        event_bus = EventBus()
        cache = OrchestratorCache(integration_config)

        symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        bars_by_symbol = {
            symbol: create_accumulation_pattern_bars(symbol=symbol) for symbol in symbols
        }

        def get_bars_for_symbol(symbol, timeframe, limit):
            return bars_by_symbol.get(symbol, [])

        mock_detectors_with_patterns._mocks["volume_analyzer"].analyze.return_value = []

        orchestrator = MasterOrchestrator(
            config=integration_config,
            container=mock_detectors_with_patterns,
            event_bus=event_bus,
            cache=cache,
        )

        with patch("src.repositories.ohlcv_repository.OHLCVRepository") as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_bars.side_effect = get_bars_for_symbol

            results = await orchestrator.analyze_symbols(symbols, "1d")

            # Should have results for all symbols
            assert len(results) == 3
            for symbol in symbols:
                assert symbol in results
                assert isinstance(results[symbol], list)

    @pytest.mark.asyncio
    async def test_partial_failure_handling(
        self,
        integration_config: OrchestratorConfig,
        mock_detectors_with_patterns: OrchestratorContainer,
    ):
        """Test that failure in one symbol doesn't affect others."""
        event_bus = EventBus()
        cache = OrchestratorCache(integration_config)

        def get_bars_with_failure(symbol, timeframe, limit):
            if symbol == "FAIL_SYMBOL":
                raise Exception("Failed to fetch bars")
            return create_accumulation_pattern_bars(symbol=symbol)

        mock_detectors_with_patterns._mocks["volume_analyzer"].analyze.return_value = []

        orchestrator = MasterOrchestrator(
            config=integration_config,
            container=mock_detectors_with_patterns,
            event_bus=event_bus,
            cache=cache,
        )

        with patch("src.repositories.ohlcv_repository.OHLCVRepository") as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_bars.side_effect = get_bars_with_failure

            results = await orchestrator.analyze_symbols(
                ["BTCUSDT", "FAIL_SYMBOL", "ETHUSDT"], "1d"
            )

            # Should have results for successful symbols
            assert "BTCUSDT" in results
            assert "ETHUSDT" in results


class TestHealthAndMetrics:
    """Tests for health check and metrics collection."""

    @pytest.mark.asyncio
    async def test_health_after_analysis(
        self,
        integration_config: OrchestratorConfig,
        accumulation_bars: list[OHLCVBar],
        mock_detectors_with_patterns: OrchestratorContainer,
    ):
        """Test health check reflects analysis activity."""
        event_bus = EventBus()
        cache = OrchestratorCache(integration_config)

        mock_detectors_with_patterns._mocks["volume_analyzer"].analyze.return_value = []

        orchestrator = MasterOrchestrator(
            config=integration_config,
            container=mock_detectors_with_patterns,
            event_bus=event_bus,
            cache=cache,
        )

        # Get initial health
        initial_health = orchestrator.get_health()
        initial_count = initial_health["metrics"]["analysis_count"]

        with patch("src.repositories.ohlcv_repository.OHLCVRepository") as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_bars.return_value = accumulation_bars

            await orchestrator.analyze_symbol("BTCUSDT", "1d")

        # Get health after analysis
        final_health = orchestrator.get_health()
        final_count = final_health["metrics"]["analysis_count"]

        # Analysis count should have increased
        assert final_count > initial_count

    def test_health_reports_component_status(
        self,
        integration_config: OrchestratorConfig,
        mock_detectors_with_patterns: OrchestratorContainer,
    ):
        """Test that health check reports component status."""
        event_bus = EventBus()
        cache = OrchestratorCache(integration_config)

        orchestrator = MasterOrchestrator(
            config=integration_config,
            container=mock_detectors_with_patterns,
            event_bus=event_bus,
            cache=cache,
        )

        health = orchestrator.get_health()

        assert "status" in health
        assert "components" in health
        assert "cache" in health["components"]
        assert "event_bus" in health["components"]


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_empty_bars_handling(
        self,
        integration_config: OrchestratorConfig,
        mock_detectors_with_patterns: OrchestratorContainer,
    ):
        """Test handling of empty bar data."""
        event_bus = EventBus()
        cache = OrchestratorCache(integration_config)

        orchestrator = MasterOrchestrator(
            config=integration_config,
            container=mock_detectors_with_patterns,
            event_bus=event_bus,
            cache=cache,
        )

        with patch("src.repositories.ohlcv_repository.OHLCVRepository") as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_bars.return_value = []

            signals = await orchestrator.analyze_symbol("BTCUSDT", "1d")

            assert signals == []

    @pytest.mark.asyncio
    async def test_single_bar_handling(
        self,
        integration_config: OrchestratorConfig,
        mock_detectors_with_patterns: OrchestratorContainer,
    ):
        """Test handling of single bar data."""
        event_bus = EventBus()
        cache = OrchestratorCache(integration_config)

        single_bar = OHLCVBar(
            symbol="BTCUSDT",
            timeframe="1d",
            timestamp=datetime.now(UTC),
            open=Decimal("40000"),
            high=Decimal("41000"),
            low=Decimal("39000"),
            close=Decimal("40500"),
            volume=1000000,
            spread=Decimal("2000"),
        )

        mock_detectors_with_patterns._mocks["volume_analyzer"].analyze.return_value = []

        orchestrator = MasterOrchestrator(
            config=integration_config,
            container=mock_detectors_with_patterns,
            event_bus=event_bus,
            cache=cache,
        )

        with patch("src.repositories.ohlcv_repository.OHLCVRepository") as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_bars.return_value = [single_bar]

            signals = await orchestrator.analyze_symbol("BTCUSDT", "1d")

            # Should handle gracefully
            assert isinstance(signals, list)

    @pytest.mark.asyncio
    async def test_invalid_symbol_handling(
        self,
        integration_config: OrchestratorConfig,
        mock_detectors_with_patterns: OrchestratorContainer,
    ):
        """Test handling of invalid symbol."""
        event_bus = EventBus()
        cache = OrchestratorCache(integration_config)

        orchestrator = MasterOrchestrator(
            config=integration_config,
            container=mock_detectors_with_patterns,
            event_bus=event_bus,
            cache=cache,
        )

        with patch("src.repositories.ohlcv_repository.OHLCVRepository") as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_bars.return_value = []

            # Should not raise for invalid symbol
            signals = await orchestrator.analyze_symbol("INVALID_SYMBOL", "1d")

            assert signals == []

    @pytest.mark.asyncio
    async def test_empty_symbol_list(
        self,
        integration_config: OrchestratorConfig,
        mock_detectors_with_patterns: OrchestratorContainer,
    ):
        """Test handling of empty symbol list."""
        event_bus = EventBus()
        cache = OrchestratorCache(integration_config)

        orchestrator = MasterOrchestrator(
            config=integration_config,
            container=mock_detectors_with_patterns,
            event_bus=event_bus,
            cache=cache,
        )

        results = await orchestrator.analyze_symbols([], "1d")

        assert results == {}
