"""
MasterOrchestrator Facade - Backward-Compatible Pipeline Interface.

Provides the same interface as the original MasterOrchestrator but
delegates to PipelineCoordinator for stage execution.

Story 18.10.5: Services Extraction and Orchestrator Facade (AC5)
Story 23.2: Wire orchestrator pipeline with real detectors
"""

import asyncio
from typing import Any
from uuid import UUID, uuid4

import structlog

from src.campaign_management.campaign_manager import CampaignManager
from src.models.phase_classification import WyckoffPhase
from src.models.validation import (
    StageValidationResult,
    ValidationContext,
    ValidationStatus,
)
from src.orchestrator.cache import OrchestratorCache, get_orchestrator_cache
from src.orchestrator.config import OrchestratorConfig
from src.orchestrator.container import OrchestratorContainer, get_orchestrator_container
from src.orchestrator.event_bus import EventBus, get_event_bus
from src.orchestrator.master_orchestrator import TradeSignal
from src.orchestrator.pipeline import PipelineContextBuilder, PipelineCoordinator
from src.orchestrator.pipeline.context import PipelineContext
from src.orchestrator.services import PortfolioMonitor
from src.signal_generator.validators.base import BaseValidator

logger = structlog.get_logger(__name__)


class _PassThroughSignalGenerator:
    """Adapter: passes validated patterns through as signals without transformation."""

    async def generate_signal(
        self,
        pattern: Any,
        trading_range: Any | None,
        context: PipelineContext,
    ) -> Any | None:
        """Return the pattern as-is (already a valid signal/pattern object)."""
        return pattern


class _RiskManagerAdapter:
    """Adapter: wraps RiskManager to satisfy the RiskAssessor protocol.

    Currently a pass-through stub. Risk validation is handled by RiskValidator
    in ValidationStage. Full position sizing and portfolio heat validation is
    deferred to a follow-up story.
    """

    def __init__(self, risk_manager: Any) -> None:
        # risk_manager accepted for API compatibility; not yet used.
        pass

    async def apply_sizing(
        self,
        signal: Any,
        context: PipelineContext,
    ) -> Any | None:
        """Pass signal through (risk validation done in ValidationStage)."""
        return signal


class _StrategyNoApiFallback(BaseValidator):
    """WARN-only stub when NEWS_API_KEY is not configured.

    Used in place of the real StrategyValidator when no external news calendar
    API is available.  Signals still proceed but carry an explicit WARN in the
    audit trail.  For production deployment, NEWS_API_KEY should be configured
    so the real StrategyValidator handles FR29 earnings/event blackout checks.
    """

    @property
    def validator_id(self) -> str:
        return "STRATEGY_VALIDATOR"

    @property
    def stage_name(self) -> str:
        return "Strategy"

    async def validate(self, context: ValidationContext) -> StageValidationResult:
        return self.create_result(
            ValidationStatus.WARN,
            reason="No news calendar API configured — strategy context skipped",
        )


class NoDataError(Exception):
    """Raised when no OHLCV bars are available for a symbol."""

    def __init__(self, symbol: str, timeframe: str) -> None:
        self.symbol = symbol
        self.timeframe = timeframe
        super().__init__(f"No OHLCV data for {symbol}/{timeframe}")


class MasterOrchestratorFacade:
    """
    Backward-compatible facade for pipeline execution.

    Maintains the original MasterOrchestrator interface while delegating
    to PipelineCoordinator for stage execution.

    Example:
        >>> orchestrator = MasterOrchestratorFacade()
        >>> signals = await orchestrator.analyze_symbol("AAPL", "1d")
    """

    def __init__(
        self,
        config: OrchestratorConfig | None = None,
        container: OrchestratorContainer | None = None,
        event_bus: EventBus | None = None,
        cache: OrchestratorCache | None = None,
        campaign_manager: CampaignManager | None = None,
    ) -> None:
        """Initialize facade with dependencies."""
        self._config = config or OrchestratorConfig()
        self._container = container or get_orchestrator_container(self._config)
        self._event_bus = event_bus or get_event_bus()
        self._cache = cache or get_orchestrator_cache(self._config)
        self._campaign_manager = campaign_manager

        # Pipeline coordinator
        self._coordinator = self._build_coordinator()

        # Services
        self._portfolio_monitor = PortfolioMonitor()

        # Concurrency control
        self._semaphore = asyncio.Semaphore(self._config.max_concurrent_symbols)
        self._lock = asyncio.Lock()

        # Metrics
        self._analysis_count = 0
        self._signal_count = 0
        self._error_count = 0

        logger.info("orchestrator_facade_initialized")

    def _build_coordinator(self) -> PipelineCoordinator:
        """Build pipeline coordinator with stages."""
        from src.orchestrator.stages import (
            PatternDetectionStage,
            PhaseDetectionStage,
            RangeDetectionStage,
            RiskAssessmentStage,
            SignalGenerationStage,
            ValidationStage,
            VolumeAnalysisStage,
        )

        # Build stages with container dependencies
        stages = []

        # Stage 1: Volume Analysis
        if hasattr(self._container, "volume_analyzer"):
            stages.append(VolumeAnalysisStage(self._container.volume_analyzer))

        # Stage 2: Range Detection
        if hasattr(self._container, "trading_range_detector"):
            stages.append(RangeDetectionStage(self._container.trading_range_detector))

        # Stage 3: Phase Detection
        # PhaseDetector is instantiated directly because OrchestratorContainer
        # does not yet expose a phase_detector property. This is consistent with
        # the PhaseDetectionStage requirement but deviates from the container DI
        # pattern used by other stages.
        # TODO(23.x): add phase_detector to OrchestratorContainer.
        from src.pattern_engine.phase_detector_v2 import PhaseDetector

        stages.append(PhaseDetectionStage(PhaseDetector()))

        # Stage 4: Pattern Detection
        from src.orchestrator.stages.pattern_detection_stage import (
            DetectorRegistry,
            PhaseDCompositeDetector,
        )

        registry = DetectorRegistry()

        # Register Spring detector for Phase C
        spring_det = self._container.spring_detector
        if spring_det is not None:
            registry.register(WyckoffPhase.C, spring_det)

        # Register composite SOS+UTAD detector for Phase D
        sos_det = self._container.sos_detector
        utad_det = self._container.utad_detector
        if sos_det is not None or utad_det is not None:
            composite_d = PhaseDCompositeDetector(
                sos_detector=sos_det,
                utad_detector=utad_det,
            )
            registry.register(WyckoffPhase.D, composite_d)

        # Register LPS detector for Phase E
        lps_det = self._container.lps_detector
        if lps_det is not None:
            registry.register(WyckoffPhase.E, lps_det)

        stages.append(PatternDetectionStage(registry))

        # Stage 5: Validation (FR20 order: Volume -> Phase -> Levels -> Risk -> Strategy)
        from src.signal_generator.validation_chain import ValidationChainOrchestrator
        from src.signal_generator.validators import (
            LevelValidator,
            PhaseValidator,
            RiskValidator,
            StrategyValidator,
            VolumeValidator,
        )

        validators: list = [
            VolumeValidator(),
            PhaseValidator(),
            LevelValidator(),
            RiskValidator(),
        ]

        # Wire StrategyValidator: use real implementation if NEWS_API_KEY is
        # configured, otherwise fall back to a WARN-only stub so all 5 stages
        # are present in the pipeline without requiring external services.
        # NOTE: For production, NEWS_API_KEY should be set so StrategyValidator
        # enforces FR29 earnings/event blackout windows.
        from src.config import settings

        if settings.news_api_key:
            from src.services.news_calendar_factory import NewsCalendarFactory

            validators.append(StrategyValidator(news_calendar_factory=NewsCalendarFactory()))
        else:
            validators.append(_StrategyNoApiFallback())

        stages.append(ValidationStage(ValidationChainOrchestrator(validators)))

        # Stage 6: Signal Generation
        stages.append(SignalGenerationStage(_PassThroughSignalGenerator()))

        # Stage 7: Risk Assessment
        if hasattr(self._container, "risk_manager"):
            stages.append(RiskAssessmentStage(_RiskManagerAdapter(self._container.risk_manager)))

        return PipelineCoordinator(stages)

    def set_campaign_manager(self, campaign_manager: CampaignManager) -> None:
        """Set CampaignManager instance."""
        self._campaign_manager = campaign_manager

    async def analyze_symbol(self, symbol: str, timeframe: str) -> list[TradeSignal]:
        """
        Analyze a symbol and generate trade signals.

        Delegates to PipelineCoordinator for execution.
        """
        correlation_id = uuid4()

        async with self._lock:
            self._analysis_count += 1

        logger.info(
            "facade_analysis_start",
            symbol=symbol,
            timeframe=timeframe,
            correlation_id=str(correlation_id),
        )

        try:
            # Fetch bars
            bars = await self._fetch_bars(symbol, timeframe)
            if not bars:
                logger.warning("no_ohlcv_data", symbol=symbol, timeframe=timeframe)
                raise NoDataError(symbol, timeframe)

            # Build context
            context = (
                PipelineContextBuilder()
                .with_correlation_id(correlation_id)
                .with_symbol(symbol)
                .with_timeframe(timeframe)
                .with_data("bars", bars)
                .build()
            )

            # Run pipeline
            result = await self._coordinator.run(bars, context)

            if not result.success:
                logger.warning("pipeline_failed", errors=result.errors)
                return []

            # Extract signals from result
            signals = self._extract_signals(result.output, symbol, timeframe, correlation_id)

            async with self._lock:
                self._signal_count += len(signals)

            return signals

        except NoDataError:
            raise
        except Exception as e:
            async with self._lock:
                self._error_count += 1
            logger.error("facade_analysis_error", error=str(e))
            return []

    async def _fetch_bars(self, symbol: str, timeframe: str) -> list:
        """Fetch OHLCV bars for analysis."""
        from src.database import async_session_maker
        from src.repositories.ohlcv_repository import OHLCVRepository

        try:
            async with async_session_maker() as session:
                repo = OHLCVRepository(session=session)
                bars = await repo.get_latest_bars(
                    symbol=symbol,
                    timeframe=timeframe,
                    count=self._config.default_lookback_bars,
                )
            return sorted(bars, key=lambda b: b.timestamp) if bars else []
        except Exception as e:
            logger.error("bars_fetch_error", error=str(e))
            return []

    def _extract_signals(
        self,
        output: Any,
        symbol: str,
        timeframe: str,
        correlation_id: UUID,
    ) -> list[TradeSignal]:
        """Extract TradeSignal objects from pipeline output."""
        if not output:
            return []

        # Output may be list of signals or need conversion
        if isinstance(output, list):
            return [s for s in output if isinstance(s, TradeSignal)]
        return []

    async def analyze_symbols(
        self,
        symbols: list[str],
        timeframe: str,
    ) -> dict[str, list[TradeSignal]]:
        """Analyze multiple symbols concurrently."""

        async def analyze_with_semaphore(symbol: str) -> tuple[str, list[TradeSignal]]:
            async with self._semaphore:
                try:
                    signals = await self.analyze_symbol(symbol, timeframe)
                except NoDataError:
                    logger.info("no_data_for_symbol", symbol=symbol, timeframe=timeframe)
                    signals = []
                return (symbol, signals)

        if self._config.enable_parallel_processing:
            tasks = [analyze_with_semaphore(s) for s in symbols]
            results = await asyncio.gather(*tasks, return_exceptions=True)
        else:
            results = []
            for s in symbols:
                try:
                    signals = await self.analyze_symbol(s, timeframe)
                    results.append((s, signals))
                except NoDataError:
                    logger.info("no_data_for_symbol", symbol=s, timeframe=timeframe)
                    results.append((s, []))
                except Exception as e:
                    results.append(e)

        output: dict[str, list[TradeSignal]] = {}
        for result in results:
            if isinstance(result, BaseException):
                logger.error("symbol_analysis_exception", error=str(result))
            else:
                output[result[0]] = result[1]

        return output

    def get_health(self) -> dict[str, Any]:
        """Get orchestrator health status."""
        container_health = self._container.health_check()
        cache_metrics = self._cache.get_metrics()
        event_bus_metrics = self._event_bus.get_metrics()

        if container_health.status == "unhealthy":
            status = "unhealthy"
        elif container_health.status == "degraded" or self._error_count > 10:
            status = "degraded"
        else:
            status = "healthy"

        return {
            "status": status,
            "components": {
                "container": {
                    "status": container_health.status,
                    "healthy": container_health.healthy,
                },
                "cache": cache_metrics,
                "event_bus": event_bus_metrics,
            },
            "metrics": {
                "analysis_count": self._analysis_count,
                "signal_count": self._signal_count,
                "error_count": self._error_count,
            },
        }
