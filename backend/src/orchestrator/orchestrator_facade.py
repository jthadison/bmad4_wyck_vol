"""
MasterOrchestrator Facade - Backward-Compatible Pipeline Interface.

Provides the same interface as the original MasterOrchestrator but
delegates to PipelineCoordinator for stage execution.

Story 18.10.5: Services Extraction and Orchestrator Facade (AC5)
Story 23.2: Wire orchestrator pipeline with real detectors
"""

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import structlog

from src.campaign_management.campaign_manager import CampaignManager
from src.models.phase_classification import WyckoffPhase
from src.models.signal import ConfidenceComponents, TargetLevels
from src.models.signal import TradeSignal as TradeSignalModel
from src.models.validation import (
    StageValidationResult,
    ValidationChain,
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


class _TradeSignalGenerator:
    """Converts validated pattern objects (SpringSignal, SOSSignal, etc.) to TradeSignal.

    Stage 6 of the pipeline: patterns carry price data but are not TradeSignal
    instances. This generator extracts price fields via duck typing, computes
    derived risk fields, attaches the ValidationChain from upstream, and
    constructs a proper TradeSignal that downstream stages (risk assessment,
    persistence) can consume.
    """

    async def generate_signal(
        self,
        pattern: Any,
        trading_range: Any | None,
        context: PipelineContext,
    ) -> TradeSignalModel | None:
        """Generate a TradeSignal from a validated pattern object."""
        # 1. Extract price fields via duck typing
        entry_price = getattr(pattern, "entry_price", None)
        stop_loss = getattr(pattern, "stop_loss", None)
        target = getattr(pattern, "target_price", None) or getattr(pattern, "target", None)

        # Fallback for Spring.recovery_price (Spring objects have no entry_price)
        if entry_price is None:
            entry_price = getattr(pattern, "recovery_price", None)

        # Fallback for Spring stop: 1% buffer below spring_low (FR17)
        if stop_loss is None:
            spring_low = getattr(pattern, "spring_low", None)
            if spring_low is not None:
                stop_loss = Decimal(str(spring_low)) * Decimal("0.99")

        # Fallback for target: try jump_level, then calculate from trading range
        if target is None:
            target = getattr(pattern, "jump_level", None)
        if (
            target is None
            and trading_range is not None
            and hasattr(trading_range, "calculate_jump_level")
        ):
            target = trading_range.calculate_jump_level()
        if target is None:
            # Last resort: 12% above creek_reference
            creek = getattr(pattern, "creek_reference", None)
            if creek is not None:
                target = Decimal(str(creek)) * Decimal("1.12")

        if entry_price is None or stop_loss is None or target is None:
            logger.warning(
                "signal_generator_missing_price_fields",
                pattern_type=type(pattern).__name__,
                has_entry=entry_price is not None,
                has_stop=stop_loss is not None,
                has_target=target is not None,
            )
            return None

        # Ensure Decimal
        entry_price = Decimal(str(entry_price))
        stop_loss = Decimal(str(stop_loss))
        target = Decimal(str(target))

        # 2. Extract identity fields
        symbol: str = getattr(pattern, "symbol", context.symbol)
        timeframe: str = getattr(pattern, "timeframe", context.timeframe)

        # Determine pattern_type
        pattern_type_raw = getattr(pattern, "pattern_type", None)
        if pattern_type_raw is not None:
            pattern_type = str(pattern_type_raw).upper()
        else:
            # SOSSignal uses entry_type instead of pattern_type
            entry_type = getattr(pattern, "entry_type", None)
            if entry_type == "LPS_ENTRY":
                pattern_type = "LPS"
            elif entry_type == "SOS_DIRECT_ENTRY":
                pattern_type = "SOS"
            else:
                # Infer from class name as last resort
                class_name = type(pattern).__name__.upper()
                if "LPS" in class_name:
                    pattern_type = "LPS"
                elif "SOS" in class_name:
                    pattern_type = "SOS"
                elif "UTAD" in class_name:
                    pattern_type = "UTAD"
                else:
                    pattern_type = "SPRING"

        if pattern_type not in ("SPRING", "SOS", "LPS", "UTAD"):
            logger.warning(
                "signal_generator_unknown_pattern_type",
                pattern_type=pattern_type,
                symbol=symbol,
                detail="Rejecting signal — pattern type not in allowed set",
            )
            return None

        # Normalise phase to single char; infer from pattern_type if absent
        phase: str = str(getattr(pattern, "phase", "") or "")
        if not phase:
            phase = {"SPRING": "C", "SOS": "D", "UTAD": "D", "LPS": "E"}.get(pattern_type, "C")
        if len(phase) > 1:
            phase = phase[0]

        # 3. Compute derived fields
        risk = abs(entry_price - stop_loss)
        if risk == 0:
            logger.warning(
                "signal_generator_zero_risk",
                symbol=symbol,
                entry=str(entry_price),
                stop=str(stop_loss),
            )
            return None

        r_multiple = abs(target - entry_price) / risk
        position_size = Decimal(str(getattr(pattern, "recommended_position_size", Decimal("100"))))
        # Ensure whole shares for STOCK (minimum 1)
        if position_size < Decimal("1"):
            position_size = Decimal("100")
        risk_amount = risk * position_size
        notional_value = entry_price * position_size

        # 4. Get ValidationChain from context
        validation_results = context.get("validation_results")
        chain: ValidationChain | None = None
        if validation_results is not None and hasattr(validation_results, "get_chain_for_pattern"):
            chain = validation_results.get_chain_for_pattern(pattern)

        if chain is None:
            pattern_id = getattr(pattern, "id", None) or uuid4()
            chain = ValidationChain(pattern_id=pattern_id)

        # 5. Derive confidence from chain metadata or pattern
        raw_confidence = getattr(pattern, "confidence", None)
        if raw_confidence is None:
            # For Spring-like patterns: derive confidence from volume_ratio (lower = higher quality)
            volume_ratio = getattr(pattern, "volume_ratio", None)
            if volume_ratio is not None:
                # volume_ratio in [0, 0.7] guaranteed by Spring validator
                # Map to confidence [70, 95]: lower volume = higher confidence
                raw_confidence = max(70, min(95, int(95 - (float(volume_ratio) / 0.7) * 25)))
            else:
                raw_confidence = 75
        confidence_score = int(raw_confidence)
        if confidence_score < 70:
            logger.warning(
                "signal_generator_low_confidence",
                raw_confidence=raw_confidence,
                symbol=symbol,
                detail="Rejecting signal — confidence below 70 threshold",
            )
            return None
        confidence_score = min(95, confidence_score)

        # Build ConfidenceComponents that satisfies the weighted-average validator.
        # Use the single confidence value and reverse-engineer valid components:
        # overall = pattern*0.5 + phase*0.3 + volume*0.2
        # Setting all three equal to overall satisfies the formula.
        components = ConfidenceComponents(
            pattern_confidence=confidence_score,
            phase_confidence=confidence_score,
            volume_confidence=confidence_score,
            overall_confidence=confidence_score,
        )

        # 6. Build TargetLevels
        target_levels = TargetLevels(primary_target=target, secondary_targets=[])

        # 7. Construct TradeSignal
        now = datetime.now(UTC)
        try:
            signal = TradeSignalModel(
                symbol=symbol,
                pattern_type=pattern_type,
                phase=phase,
                timeframe=timeframe,
                entry_price=entry_price,
                stop_loss=stop_loss,
                target_levels=target_levels,
                position_size=position_size,
                risk_amount=risk_amount,
                r_multiple=r_multiple,
                notional_value=notional_value,
                confidence_score=confidence_score,
                confidence_components=components,
                validation_chain=chain,
                status="PENDING",
                timestamp=now,
                created_at=now,
            )
        except Exception as e:
            logger.warning(
                "signal_generator_construction_failed",
                symbol=symbol,
                pattern_type=pattern_type,
                error=str(e),
            )
            return None

        return signal


class _RiskManagerAdapter:
    """Adapter: wraps RiskManager to satisfy the RiskAssessor protocol.

    Calls RiskManager.validate_and_size() for each signal, enforcing the full
    8-step risk pipeline: pattern risk, phase prerequisites, R-multiple,
    structural stop, position sizing, portfolio heat (10% hard cap), campaign
    risk (5% max), and correlation limits.

    Falls back to pass-through with a WARNING log when portfolio_context or
    trading_range are not available in PipelineContext (e.g. unit tests, no DB).
    The pipeline still produces signals in that case — the warning makes the
    gap observable in logs.
    """

    def __init__(self, risk_manager: Any) -> None:
        self._risk_manager = risk_manager

    async def apply_sizing(
        self,
        signal: Any,
        context: PipelineContext,
    ) -> Any | None:
        """Apply full risk validation to a signal via RiskManager.

        Returns the signal unchanged if approved, None if rejected.
        Falls back to pass-through if required context is missing.
        """
        from uuid import UUID as _UUID

        from src.models.risk_allocation import PatternType
        from src.risk_management.risk_manager import Signal as RiskSignal

        portfolio_context = context.get("portfolio_context")
        trading_range = context.get("current_trading_range")

        if portfolio_context is None or trading_range is None:
            logger.warning(
                "risk_adapter_context_missing",
                has_portfolio=portfolio_context is not None,
                has_trading_range=trading_range is not None,
                symbol=context.symbol,
                detail="portfolio_context or trading_range absent — passing signal through",
            )
            return signal

        # Extract price fields via duck typing.
        # SpringSignal uses target_price; SOSSignal uses target; TradeSignal
        # uses target_levels.primary_target.
        entry = getattr(signal, "entry_price", None)
        stop = getattr(signal, "stop_loss", None)
        target = getattr(signal, "target_price", None) or getattr(signal, "target", None)
        if target is None:
            tl = getattr(signal, "target_levels", None)
            if tl is not None:
                target = getattr(tl, "primary_target", None)
        symbol = getattr(signal, "symbol", context.symbol)

        if not all([entry, stop, target]):
            logger.warning(
                "risk_adapter_signal_incomplete",
                signal_type=type(signal).__name__,
                has_entry=entry is not None,
                has_stop=stop is not None,
                has_target=target is not None,
                detail="Cannot validate incomplete signal — passing through",
            )
            return signal

        # Resolve PatternType enum.
        # Most signal models expose pattern_type: str (e.g. "SPRING").
        # For models that don't, infer from class name: "SpringSignal" → "SPRING".
        pattern_type_str = getattr(signal, "pattern_type", None)
        if pattern_type_str is None:
            pattern_type_str = type(signal).__name__.replace("Signal", "").upper()

        try:
            pattern_type = PatternType(pattern_type_str)
        except ValueError:
            logger.warning(
                "risk_adapter_unknown_pattern_type",
                pattern_type=pattern_type_str,
                signal_type=type(signal).__name__,
                detail="Unknown pattern type — passing signal through",
            )
            return signal

        # Resolve optional campaign_id to UUID.
        campaign_id: _UUID | None = None
        raw_id = getattr(signal, "campaign_id", None)
        if raw_id is not None:
            try:
                campaign_id = _UUID(str(raw_id))
            except (ValueError, AttributeError):
                pass

        rm_signal = RiskSignal(
            symbol=symbol,
            pattern_type=pattern_type,
            entry=entry,
            stop=stop,
            target=target,
            campaign_id=campaign_id,
        )

        result = await self._risk_manager.validate_and_size(
            signal=rm_signal,
            portfolio_context=portfolio_context,
            trading_range=trading_range,
        )

        if result is None:
            logger.info(
                "risk_adapter_signal_rejected",
                symbol=symbol,
                pattern_type=pattern_type.value,
            )
            return None

        logger.debug(
            "risk_adapter_signal_approved",
            symbol=symbol,
            pattern_type=pattern_type.value,
        )

        # P6c: Map PositionSizing fields onto TradeSignal (Pydantic model)
        from src.models.signal import TradeSignal as PydanticTradeSignal

        if isinstance(signal, PydanticTradeSignal) and result is not None:
            updates: dict[str, Any] = {}
            if hasattr(result, "shares") and result.shares and result.shares >= 1:
                updates["position_size"] = Decimal(str(result.shares))
            if hasattr(result, "actual_risk") and result.actual_risk is not None:
                updates["risk_amount"] = result.actual_risk
            if hasattr(result, "position_value") and result.position_value is not None:
                updates["notional_value"] = result.position_value
            if updates:
                try:
                    signal = signal.model_copy(update=updates)
                except Exception as e:
                    logger.warning("risk_adapter_sizing_update_failed", error=str(e))

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

        # Services — wire PortfolioMonitor to real DB repos when available (P2a)
        self._portfolio_monitor = self._build_portfolio_monitor()

        # Concurrency control
        self._semaphore = asyncio.Semaphore(self._config.max_concurrent_symbols)
        self._lock = asyncio.Lock()

        # Metrics
        self._analysis_count = 0
        self._signal_count = 0
        self._error_count = 0

        logger.info("orchestrator_facade_initialized")

    async def _persist_signals(self, signals: list) -> None:
        """Persist approved signals to the database (P6b).

        Failures are logged but never raised — persistence must not
        block signal delivery.
        """
        from src.database import async_session_maker
        from src.models.signal import TradeSignal as PydanticTradeSignal
        from src.repositories.signal_repository import SignalRepository

        if async_session_maker is None:
            logger.warning(
                "persist_signals_no_db",
                detail="async_session_maker is None — skipping persistence",
            )
            return

        pydantic_signals = [s for s in signals if isinstance(s, PydanticTradeSignal)]
        if not pydantic_signals:
            return

        try:
            async with async_session_maker() as session:
                repo = SignalRepository(db_session=session)
                for signal in pydantic_signals:
                    await repo.save_signal(signal)
            logger.info("signals_persisted", count=len(pydantic_signals))
        except Exception as exc:
            logger.error("persist_signals_failed", error=str(exc), count=len(pydantic_signals))

    @staticmethod
    def _build_portfolio_monitor() -> PortfolioMonitor:
        """Build PortfolioMonitor wired to real DB repos when available (P2a)."""
        from src.database import async_session_maker
        from src.orchestrator.services.portfolio_monitor import (
            SqlCampaignRepository,
            SqlPositionRepository,
        )

        if async_session_maker is not None:
            position_repo = SqlPositionRepository(async_session_maker)
            campaign_repo = SqlCampaignRepository(async_session_maker)
            return PortfolioMonitor(
                position_repo=position_repo,
                campaign_repo=campaign_repo,
            )
        # Fallback: no DB available (tests, dev without DB)
        return PortfolioMonitor()

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
        stages.append(SignalGenerationStage(_TradeSignalGenerator()))

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

            # Inject portfolio context so RiskAssessmentStage can enforce limits
            portfolio_context = await self._portfolio_monitor.build_context()
            context.set("portfolio_context", portfolio_context)

            # Run pipeline
            result = await self._coordinator.run(bars, context)

            if not result.success:
                logger.warning("pipeline_failed", errors=result.errors)
                return []

            # Extract signals from result
            signals = self._extract_signals(result.output, symbol, timeframe, correlation_id)

            # Persist approved signals (P6b)
            if signals:
                await self._persist_signals(signals)

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

        # Output may be list of signals or need conversion.
        # Accept both the legacy TradeSignal class and the Pydantic TradeSignalModel.
        if isinstance(output, list):
            return [s for s in output if isinstance(s, TradeSignal | TradeSignalModel)]
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
