"""
MasterOrchestrator - Central Pipeline Coordinator.

Coordinates all Wyckoff pattern detectors and validators through a 7-stage
pipeline: Data -> Volume -> Range -> Phase -> Pattern -> Risk -> Signal.

Story 8.1: Master Orchestrator Architecture (AC: 1, 2, 5, 6)
"""

import asyncio
import time
import traceback
from collections import defaultdict
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import structlog

from src.models.ohlcv import OHLCVBar
from src.models.phase_classification import PhaseClassification
from src.models.trading_range import TradingRange
from src.models.volume_analysis import VolumeAnalysis
from src.orchestrator.cache import OrchestratorCache, get_orchestrator_cache
from src.orchestrator.config import OrchestratorConfig
from src.orchestrator.container import OrchestratorContainer, get_orchestrator_container
from src.orchestrator.event_bus import EventBus, get_event_bus
from src.orchestrator.events import (
    BarIngestedEvent,
    DetectorFailedEvent,
    PatternDetectedEvent,
    PhaseDetectedEvent,
    RangeDetectedEvent,
    SignalGeneratedEvent,
    VolumeAnalyzedEvent,
)
from src.orchestrator.pipeline_stage import StageResult

logger = structlog.get_logger(__name__)


class Pattern:
    """
    Detected pattern data structure.

    Represents a Wyckoff pattern (Spring, SOS, LPS, etc.) detected by
    pattern detectors, ready for risk validation.
    """

    def __init__(
        self,
        pattern_id: UUID,
        pattern_type: str,
        symbol: str,
        timeframe: str,
        confidence_score: int,
        entry_price: Decimal,
        stop_price: Decimal,
        target_price: Decimal,
        phase: str,
        trading_range: TradingRange | None = None,
    ):
        self.pattern_id = pattern_id
        self.pattern_type = pattern_type
        self.symbol = symbol
        self.timeframe = timeframe
        self.confidence_score = confidence_score
        self.entry_price = entry_price
        self.stop_price = stop_price
        self.target_price = target_price
        self.phase = phase
        self.trading_range = trading_range


class TradeSignal:
    """
    Trade signal output structure.

    Represents a validated trade signal ready for execution.
    Created in Stage 7 after risk validation passes.
    """

    def __init__(
        self,
        signal_id: UUID,
        symbol: str,
        timeframe: str,
        pattern_type: str,
        phase: str,
        entry_price: Decimal,
        stop_price: Decimal,
        target_price: Decimal,
        position_size: int,
        risk_amount: Decimal,
        r_multiple: Decimal,
        confidence_score: int,
        correlation_id: UUID,
        validation_chain: list[str],
        campaign_id: UUID | None = None,
    ):
        self.signal_id = signal_id
        self.symbol = symbol
        self.timeframe = timeframe
        self.pattern_type = pattern_type
        self.phase = phase
        self.entry_price = entry_price
        self.stop_price = stop_price
        self.target_price = target_price
        self.position_size = position_size
        self.risk_amount = risk_amount
        self.r_multiple = r_multiple
        self.confidence_score = confidence_score
        self.correlation_id = correlation_id
        self.validation_chain = validation_chain
        self.campaign_id = campaign_id


class CircuitBreaker:
    """
    Circuit breaker for detector failure protection.

    Opens circuit after threshold failures, preventing cascading failures.
    Resets after configured timeout.
    """

    def __init__(self, threshold: int = 5, reset_seconds: int = 60):
        self._threshold = threshold
        self._reset_seconds = reset_seconds
        self._failures: dict[str, list[float]] = defaultdict(list)
        self._open: dict[str, bool] = defaultdict(lambda: False)

    def record_failure(self, detector_name: str) -> None:
        """Record a detector failure."""
        now = time.time()
        self._failures[detector_name].append(now)
        # Clean old failures
        self._failures[detector_name] = [
            t for t in self._failures[detector_name] if now - t < self._reset_seconds
        ]
        # Check threshold
        if len(self._failures[detector_name]) >= self._threshold:
            self._open[detector_name] = True
            logger.warning(
                "circuit_breaker_open",
                detector=detector_name,
                failures=len(self._failures[detector_name]),
            )

    def is_open(self, detector_name: str) -> bool:
        """Check if circuit is open for a detector."""
        if not self._open[detector_name]:
            return False
        # Check if reset period has passed
        if self._failures[detector_name]:
            oldest = min(self._failures[detector_name])
            if time.time() - oldest > self._reset_seconds:
                self._open[detector_name] = False
                self._failures[detector_name] = []
                logger.info("circuit_breaker_reset", detector=detector_name)
                return False
        return True

    def record_success(self, detector_name: str) -> None:
        """Record a successful detector call (for gradual recovery)."""
        # Clear one failure on success
        if self._failures[detector_name]:
            self._failures[detector_name].pop(0)


class MasterOrchestrator:
    """
    Master orchestrator coordinating all Wyckoff pattern detection.

    Implements a 7-stage pipeline:
    1. Data: Fetch OHLCV bars
    2. Volume: Calculate volume metrics (Epic 2)
    3. Range: Detect trading ranges (Epic 3)
    4. Phase: Detect Wyckoff phases (Epic 4)
    5. Pattern: Detect patterns - Spring, SOS, LPS (Epics 5-6)
    6. Risk: Validate against risk limits (Epic 7)
    7. Signal: Generate trade signals

    Features:
    - Event-driven coordination via EventBus
    - Dependency injection via OrchestratorContainer
    - Caching of intermediate results
    - Error isolation with circuit breakers
    - Parallel symbol processing
    - Structured logging with correlation IDs

    Example:
        >>> orchestrator = MasterOrchestrator()
        >>> signals = await orchestrator.analyze_symbol("AAPL", "1d")
        >>> for signal in signals:
        ...     print(f"{signal.pattern_type}: {signal.entry_price}")
    """

    def __init__(
        self,
        config: OrchestratorConfig | None = None,
        container: OrchestratorContainer | None = None,
        event_bus: EventBus | None = None,
        cache: OrchestratorCache | None = None,
    ) -> None:
        """
        Initialize MasterOrchestrator with dependencies.

        Args:
            config: Optional configuration (uses defaults if not provided)
            container: Optional DI container (uses singleton if not provided)
            event_bus: Optional event bus (uses singleton if not provided)
            cache: Optional cache (uses singleton if not provided)
        """
        self._config = config or OrchestratorConfig()
        self._container = container or get_orchestrator_container(self._config)
        self._event_bus = event_bus or get_event_bus()
        self._cache = cache or get_orchestrator_cache(self._config)

        # Circuit breaker for detector failures
        self._circuit_breaker = CircuitBreaker(
            threshold=self._config.circuit_breaker_threshold,
            reset_seconds=self._config.circuit_breaker_reset_seconds,
        )

        # Concurrency control
        self._semaphore = asyncio.Semaphore(self._config.max_concurrent_symbols)
        self._lock = asyncio.Lock()

        # Metrics
        self._analysis_count = 0
        self._signal_count = 0
        self._error_count = 0

        logger.info(
            "master_orchestrator_initialized",
            config={
                "lookback_bars": self._config.default_lookback_bars,
                "max_concurrent": self._config.max_concurrent_symbols,
                "cache_enabled": self._config.enable_caching,
                "parallel_enabled": self._config.enable_parallel_processing,
            },
        )

    # Stage 1: Data Ingestion

    async def _fetch_bars(self, symbol: str, timeframe: str, correlation_id: UUID) -> StageResult:
        """
        Stage 1: Fetch OHLCV bars for analysis.

        Retrieves bars from repository, validates data integrity, and
        publishes BarIngested events.

        Args:
            symbol: Stock symbol
            timeframe: Bar timeframe
            correlation_id: Request correlation ID

        Returns:
            StageResult with list of OHLCVBar objects
        """
        start_time = time.perf_counter()

        try:
            from src.repositories.ohlcv_repository import OHLCVRepository

            repo = OHLCVRepository()
            bars = repo.get_bars(
                symbol=symbol,
                timeframe=timeframe,
                limit=self._config.default_lookback_bars,
            )

            if not bars:
                return StageResult(
                    success=False,
                    output=None,
                    error=f"No bars found for {symbol}/{timeframe}",
                    execution_time_ms=(time.perf_counter() - start_time) * 1000,
                    stage_name="data_ingestion",
                )

            # Validate bars
            bars = sorted(bars, key=lambda b: b.timestamp)

            # Publish BarIngested events
            for i, bar in enumerate(bars):
                event = BarIngestedEvent(
                    correlation_id=correlation_id,
                    symbol=symbol,
                    timeframe=timeframe,
                    bar_timestamp=bar.timestamp,
                    bar_index=i,
                )
                await self._event_bus.publish(event)

            logger.debug(
                "bars_fetched",
                symbol=symbol,
                timeframe=timeframe,
                bar_count=len(bars),
                correlation_id=str(correlation_id),
            )

            return StageResult(
                success=True,
                output=bars,
                execution_time_ms=(time.perf_counter() - start_time) * 1000,
                stage_name="data_ingestion",
            )

        except Exception as e:
            logger.error(
                "data_fetch_error",
                symbol=symbol,
                timeframe=timeframe,
                error=str(e),
                correlation_id=str(correlation_id),
            )
            return StageResult(
                success=False,
                output=None,
                error=str(e),
                execution_time_ms=(time.perf_counter() - start_time) * 1000,
                stage_name="data_ingestion",
            )

    # Stage 2: Volume Analysis

    async def _analyze_volume(
        self,
        bars: list[OHLCVBar],
        symbol: str,
        timeframe: str,
        correlation_id: UUID,
    ) -> StageResult:
        """
        Stage 2: Analyze volume metrics.

        Calculates volume ratio, spread ratio, close position, and effort/result
        classification for all bars.

        Args:
            bars: List of OHLCV bars
            symbol: Stock symbol
            timeframe: Bar timeframe
            correlation_id: Request correlation ID

        Returns:
            StageResult with list of VolumeAnalysis objects
        """
        start_time = time.perf_counter()

        # Check cache
        if self._config.enable_caching:
            cached = self._cache.get_volume_analysis(symbol, timeframe)
            if cached:
                logger.debug(
                    "volume_analysis_cache_hit",
                    symbol=symbol,
                    timeframe=timeframe,
                    correlation_id=str(correlation_id),
                )
                return StageResult(
                    success=True,
                    output=cached,
                    execution_time_ms=(time.perf_counter() - start_time) * 1000,
                    stage_name="volume_analysis",
                )

        try:
            # Check circuit breaker
            if self._circuit_breaker.is_open("volume_analyzer"):
                return StageResult(
                    success=False,
                    output=None,
                    error="Volume analyzer circuit breaker open",
                    execution_time_ms=(time.perf_counter() - start_time) * 1000,
                    stage_name="volume_analysis",
                )

            analyzer = self._container.volume_analyzer
            analysis_results = analyzer.analyze(bars)

            # Cache result
            if self._config.enable_caching:
                self._cache.set_volume_analysis(symbol, timeframe, analysis_results)

            # Publish VolumeAnalyzed event for latest bar
            if analysis_results:
                latest = analysis_results[-1]
                event = VolumeAnalyzedEvent(
                    correlation_id=correlation_id,
                    symbol=symbol,
                    timeframe=timeframe,
                    volume_ratio=float(latest.volume_ratio) if latest.volume_ratio else None,
                    spread_ratio=float(latest.spread_ratio) if latest.spread_ratio else None,
                    close_position=float(latest.close_position) if latest.close_position else 0.5,
                    effort_result=latest.effort_result.value if latest.effort_result else "NORMAL",
                    bars_analyzed=len(analysis_results),
                )
                await self._event_bus.publish(event)

            self._circuit_breaker.record_success("volume_analyzer")

            return StageResult(
                success=True,
                output=analysis_results,
                execution_time_ms=(time.perf_counter() - start_time) * 1000,
                stage_name="volume_analysis",
            )

        except Exception as e:
            self._circuit_breaker.record_failure("volume_analyzer")
            logger.error(
                "volume_analysis_error",
                symbol=symbol,
                error=str(e),
                correlation_id=str(correlation_id),
            )
            return StageResult(
                success=False,
                output=None,
                error=str(e),
                execution_time_ms=(time.perf_counter() - start_time) * 1000,
                stage_name="volume_analysis",
            )

    # Stage 3: Trading Range Detection

    async def _detect_trading_ranges(
        self,
        bars: list[OHLCVBar],
        volume_analysis: list[VolumeAnalysis],
        symbol: str,
        timeframe: str,
        correlation_id: UUID,
    ) -> StageResult:
        """
        Stage 3: Detect trading ranges.

        Identifies pivot points, clusters them into ranges, calculates
        Creek/Ice/Jump levels, and scores range quality.

        Args:
            bars: List of OHLCV bars
            volume_analysis: Volume analysis results
            symbol: Stock symbol
            timeframe: Bar timeframe
            correlation_id: Request correlation ID

        Returns:
            StageResult with list of TradingRange objects
        """
        start_time = time.perf_counter()

        # Check cache
        if self._config.enable_caching:
            cached = self._cache.get_trading_ranges(symbol, timeframe)
            if cached:
                logger.debug(
                    "trading_ranges_cache_hit",
                    symbol=symbol,
                    timeframe=timeframe,
                    correlation_id=str(correlation_id),
                )
                return StageResult(
                    success=True,
                    output=cached,
                    execution_time_ms=(time.perf_counter() - start_time) * 1000,
                    stage_name="range_detection",
                )

        try:
            result = StageResult(
                success=True,
                output=[],
                execution_time_ms=0,
                stage_name="range_detection",
            )

            # 1. Detect pivots
            if self._circuit_breaker.is_open("pivot_detector"):
                result.add_warning("Pivot detector circuit breaker open")
                result.add_failed_detector("pivot_detector")
            else:
                try:
                    pivot_detector = self._container.pivot_detector
                    pivots = pivot_detector.detect(bars)
                    self._circuit_breaker.record_success("pivot_detector")
                except Exception as e:
                    self._circuit_breaker.record_failure("pivot_detector")
                    result.add_failed_detector("pivot_detector")
                    logger.error("pivot_detection_error", error=str(e))
                    pivots = []

            # 2. Detect trading ranges
            if self._circuit_breaker.is_open("trading_range_detector"):
                result.add_warning("Trading range detector circuit breaker open")
                result.add_failed_detector("trading_range_detector")
                trading_ranges = []
            else:
                try:
                    range_detector = self._container.trading_range_detector
                    trading_ranges = range_detector.detect(
                        bars, pivots if "pivots" in dir() else []
                    )
                    self._circuit_breaker.record_success("trading_range_detector")
                except Exception as e:
                    self._circuit_breaker.record_failure("trading_range_detector")
                    result.add_failed_detector("trading_range_detector")
                    logger.error("range_detection_error", error=str(e))
                    trading_ranges = []

            # 3. Score range quality (filter by minimum score)
            valid_ranges = []
            for tr in trading_ranges:
                try:
                    scorer = self._container.range_quality_scorer
                    score = scorer.score(tr, bars)
                    tr.update_quality_score(score)
                    if score >= self._config.min_range_quality_score:
                        valid_ranges.append(tr)
                except Exception as e:
                    logger.warning("range_scoring_error", error=str(e))
                    valid_ranges.append(tr)  # Include without score

            # 4. Calculate levels (Creek, Ice, Jump)
            for tr in valid_ranges:
                try:
                    level_calc = self._container.level_calculator
                    tr.creek = level_calc.calculate_creek(tr, bars)
                    tr.ice = level_calc.calculate_ice(tr, bars)
                    tr.jump = level_calc.calculate_jump(tr, bars)
                except Exception as e:
                    logger.warning("level_calculation_error", error=str(e))

            # Cache results
            if self._config.enable_caching and valid_ranges:
                self._cache.set_trading_ranges(symbol, timeframe, valid_ranges)

            # Publish events for each range
            for tr in valid_ranges:
                event = RangeDetectedEvent(
                    correlation_id=correlation_id,
                    symbol=symbol,
                    timeframe=timeframe,
                    range_id=tr.id,
                    creek=float(tr.creek.level) if tr.creek else float(tr.support),
                    ice=float(tr.ice.level) if tr.ice else float(tr.resistance),
                    jump=float(tr.jump.target) if tr.jump else None,
                    quality_score=tr.quality_score or 0,
                    support=float(tr.support),
                    resistance=float(tr.resistance),
                )
                await self._event_bus.publish(event)

            result.output = valid_ranges
            result.execution_time_ms = (time.perf_counter() - start_time) * 1000

            return result

        except Exception as e:
            logger.error(
                "range_detection_error",
                symbol=symbol,
                error=str(e),
                correlation_id=str(correlation_id),
            )
            return StageResult(
                success=False,
                output=None,
                error=str(e),
                execution_time_ms=(time.perf_counter() - start_time) * 1000,
                stage_name="range_detection",
            )

    # Stage 4: Phase Detection

    async def _detect_phases(
        self,
        bars: list[OHLCVBar],
        trading_ranges: list[TradingRange],
        volume_analysis: list[VolumeAnalysis],
        symbol: str,
        timeframe: str,
        correlation_id: UUID,
    ) -> StageResult:
        """
        Stage 4: Detect Wyckoff phases.

        Identifies current Wyckoff phase (A, B, C, D, E) for each trading range
        with confidence scoring.

        Args:
            bars: List of OHLCV bars
            trading_ranges: Detected trading ranges
            volume_analysis: Volume analysis results
            symbol: Stock symbol
            timeframe: Bar timeframe
            correlation_id: Request correlation ID

        Returns:
            StageResult with list of PhaseClassification objects
        """
        start_time = time.perf_counter()

        # Check cache
        if self._config.enable_caching:
            cached = self._cache.get_phases(symbol, timeframe)
            if cached:
                logger.debug(
                    "phases_cache_hit",
                    symbol=symbol,
                    timeframe=timeframe,
                    correlation_id=str(correlation_id),
                )
                return StageResult(
                    success=True,
                    output=cached,
                    execution_time_ms=(time.perf_counter() - start_time) * 1000,
                    stage_name="phase_detection",
                )

        try:
            # Phase detection is typically done within trading ranges
            # For now, create placeholder phase classifications
            phases: list[PhaseClassification] = []

            for tr in trading_ranges:
                # Simple heuristic for phase detection
                # Real implementation would use phase detection modules from Epic 4
                from datetime import UTC, datetime

                from src.models.phase_classification import PhaseEvents, WyckoffPhase

                # Determine phase based on range characteristics
                # This is a simplified version - real implementation in Epic 4
                phase = WyckoffPhase.B  # Default to Phase B
                confidence = 70
                trading_allowed = True

                if tr.event_history:
                    # Check for specific events
                    has_sc = tr.has_event("SC")
                    has_ar = tr.has_event("AR")
                    has_spring = tr.has_event("SPRING")
                    has_sos = tr.has_event("SOS")

                    if has_sos:
                        phase = WyckoffPhase.D
                        confidence = 85
                    elif has_spring:
                        phase = WyckoffPhase.C
                        confidence = 80
                    elif has_sc and has_ar:
                        phase = WyckoffPhase.B
                        confidence = 75

                phase_class = PhaseClassification(
                    phase=phase,
                    confidence=confidence,
                    duration=tr.duration,
                    events_detected=PhaseEvents(),
                    trading_range=tr.model_dump(),
                    trading_allowed=trading_allowed,
                    phase_start_index=tr.start_index,
                    phase_start_timestamp=tr.start_timestamp or datetime.now(UTC),
                )

                # Only include phases meeting minimum confidence
                if confidence >= self._config.min_phase_confidence:
                    phases.append(phase_class)

                    # Publish event
                    event = PhaseDetectedEvent(
                        correlation_id=correlation_id,
                        symbol=symbol,
                        timeframe=timeframe,
                        phase=phase.value,
                        confidence=confidence,
                        duration=tr.duration,
                        trading_allowed=trading_allowed,
                    )
                    await self._event_bus.publish(event)

            # Cache results
            if self._config.enable_caching and phases:
                self._cache.set_phases(symbol, timeframe, phases)

            return StageResult(
                success=True,
                output=phases,
                execution_time_ms=(time.perf_counter() - start_time) * 1000,
                stage_name="phase_detection",
            )

        except Exception as e:
            logger.error(
                "phase_detection_error",
                symbol=symbol,
                error=str(e),
                correlation_id=str(correlation_id),
            )
            return StageResult(
                success=False,
                output=None,
                error=str(e),
                execution_time_ms=(time.perf_counter() - start_time) * 1000,
                stage_name="phase_detection",
            )

    # Stage 5: Pattern Detection

    async def _detect_patterns(
        self,
        bars: list[OHLCVBar],
        trading_ranges: list[TradingRange],
        phases: list[PhaseClassification],
        volume_analysis: list[VolumeAnalysis],
        symbol: str,
        timeframe: str,
        correlation_id: UUID,
    ) -> StageResult:
        """
        Stage 5: Detect Wyckoff patterns.

        Runs pattern detectors based on current phase:
        - Phase C: Spring detection
        - Phase D: SOS/LPS detection

        Args:
            bars: List of OHLCV bars
            trading_ranges: Detected trading ranges
            phases: Phase classifications
            volume_analysis: Volume analysis results
            symbol: Stock symbol
            timeframe: Bar timeframe
            correlation_id: Request correlation ID

        Returns:
            StageResult with list of Pattern objects
        """
        start_time = time.perf_counter()

        try:
            patterns: list[Pattern] = []
            result = StageResult(
                success=True,
                output=patterns,
                execution_time_ms=0,
                stage_name="pattern_detection",
            )

            for i, phase in enumerate(phases):
                if not phase.trading_allowed:
                    continue

                tr = trading_ranges[i] if i < len(trading_ranges) else None
                if not tr:
                    continue

                # Get current price for entry calculation
                current_bar = bars[-1] if bars else None
                if not current_bar:
                    continue

                # Phase C: Spring detection
                if phase.phase and phase.phase.value == "C":
                    if not self._circuit_breaker.is_open("spring_detector"):
                        # Spring detector not yet implemented in container
                        # Would call: spring_detector.detect(bars, tr, volume_analysis)
                        pass

                # Phase D: SOS/LPS detection
                if phase.phase and phase.phase.value == "D":
                    # SOS detection
                    if not self._circuit_breaker.is_open("sos_detector"):
                        try:
                            sos_detector = self._container.sos_detector
                            # Real implementation would call detector
                            # sos_results = sos_detector.detect(bars, tr, volume_analysis)
                            self._circuit_breaker.record_success("sos_detector")
                        except Exception as e:
                            self._circuit_breaker.record_failure("sos_detector")
                            result.add_failed_detector("sos_detector")
                            logger.warning("sos_detection_error", error=str(e))

                    # LPS detection
                    if not self._circuit_breaker.is_open("lps_detector"):
                        try:
                            lps_detector = self._container.lps_detector
                            # Real implementation would call detector
                            # lps_results = lps_detector.detect(bars, tr, volume_analysis)
                            self._circuit_breaker.record_success("lps_detector")
                        except Exception as e:
                            self._circuit_breaker.record_failure("lps_detector")
                            result.add_failed_detector("lps_detector")
                            logger.warning("lps_detection_error", error=str(e))

            # Publish events for detected patterns
            for pattern in patterns:
                event = PatternDetectedEvent(
                    correlation_id=correlation_id,
                    symbol=symbol,
                    timeframe=timeframe,
                    pattern_id=pattern.pattern_id,
                    pattern_type=pattern.pattern_type,
                    confidence_score=pattern.confidence_score,
                    entry_price=float(pattern.entry_price),
                    stop_price=float(pattern.stop_price),
                    target_price=float(pattern.target_price),
                    phase=pattern.phase,
                )
                await self._event_bus.publish(event)

            result.output = patterns
            result.execution_time_ms = (time.perf_counter() - start_time) * 1000

            return result

        except Exception as e:
            logger.error(
                "pattern_detection_error",
                symbol=symbol,
                error=str(e),
                correlation_id=str(correlation_id),
            )
            return StageResult(
                success=False,
                output=None,
                error=str(e),
                execution_time_ms=(time.perf_counter() - start_time) * 1000,
                stage_name="pattern_detection",
            )

    # Stage 6: Risk Validation

    async def _validate_risk(
        self,
        patterns: list[Pattern],
        symbol: str,
        correlation_id: UUID,
    ) -> StageResult:
        """
        Stage 6: Validate patterns against risk limits.

        Calls RiskManager for each pattern to validate risk constraints
        and calculate position sizing.

        Args:
            patterns: Detected patterns
            symbol: Stock symbol
            correlation_id: Request correlation ID

        Returns:
            StageResult with list of (Pattern, PositionSizing) tuples
        """
        start_time = time.perf_counter()

        try:
            validated: list[tuple[Pattern, Any]] = []
            rejected: list[tuple[Pattern, str]] = []

            result = StageResult(
                success=True,
                output=validated,
                execution_time_ms=0,
                stage_name="risk_validation",
            )

            if self._circuit_breaker.is_open("risk_manager"):
                result.add_warning("Risk manager circuit breaker open")
                result.success = False
                result.error = "Risk manager unavailable"
                return result

            risk_manager = self._container.risk_manager

            for pattern in patterns:
                try:
                    # Build portfolio context
                    portfolio_context = await self._build_portfolio_context()

                    # Create signal for risk validation
                    from src.models.risk_allocation import PatternType
                    from src.risk_management.risk_manager import Signal

                    # Map pattern type string to enum
                    pattern_type_map = {
                        "SPRING": PatternType.SPRING,
                        "SOS": PatternType.SOS,
                        "LPS": PatternType.LPS,
                        "ST": PatternType.ST,
                        "UTAD": PatternType.UTAD,
                    }
                    pattern_type = pattern_type_map.get(pattern.pattern_type, PatternType.SPRING)

                    signal = Signal(
                        symbol=pattern.symbol,
                        pattern_type=pattern_type,
                        entry=pattern.entry_price,
                        stop=pattern.stop_price,
                        target=pattern.target_price,
                    )

                    # Validate and size
                    position_sizing = await risk_manager.validate_and_size(
                        signal=signal,
                        portfolio_context=portfolio_context,
                        trading_range=pattern.trading_range,
                    )

                    if position_sizing:
                        validated.append((pattern, position_sizing))
                        self._circuit_breaker.record_success("risk_manager")
                    else:
                        rejected.append((pattern, "Risk validation failed"))

                except Exception as e:
                    rejected.append((pattern, str(e)))
                    logger.warning(
                        "risk_validation_error",
                        pattern_id=str(pattern.pattern_id),
                        error=str(e),
                    )

            if rejected:
                logger.info(
                    "patterns_rejected",
                    symbol=symbol,
                    rejected_count=len(rejected),
                    reasons=[r[1] for r in rejected],
                    correlation_id=str(correlation_id),
                )

            result.output = validated
            result.execution_time_ms = (time.perf_counter() - start_time) * 1000

            return result

        except Exception as e:
            self._circuit_breaker.record_failure("risk_manager")
            logger.error(
                "risk_validation_error",
                symbol=symbol,
                error=str(e),
                correlation_id=str(correlation_id),
            )
            return StageResult(
                success=False,
                output=None,
                error=str(e),
                execution_time_ms=(time.perf_counter() - start_time) * 1000,
                stage_name="risk_validation",
            )

    # Stage 7: Signal Generation

    async def _generate_signals(
        self,
        validated_patterns: list[tuple[Pattern, Any]],
        symbol: str,
        timeframe: str,
        correlation_id: UUID,
    ) -> StageResult:
        """
        Stage 7: Generate trade signals.

        Creates TradeSignal objects for each validated pattern with
        complete position sizing and validation chain.

        Args:
            validated_patterns: Patterns that passed risk validation
            symbol: Stock symbol
            timeframe: Bar timeframe
            correlation_id: Request correlation ID

        Returns:
            StageResult with list of TradeSignal objects
        """
        start_time = time.perf_counter()

        try:
            signals: list[TradeSignal] = []

            for pattern, position_sizing in validated_patterns:
                signal = TradeSignal(
                    signal_id=uuid4(),
                    symbol=symbol,
                    timeframe=timeframe,
                    pattern_type=pattern.pattern_type,
                    phase=pattern.phase,
                    entry_price=pattern.entry_price,
                    stop_price=pattern.stop_price,
                    target_price=pattern.target_price,
                    position_size=position_sizing.shares if position_sizing else 0,
                    risk_amount=position_sizing.risk_amount if position_sizing else Decimal("0"),
                    r_multiple=position_sizing.r_multiple if position_sizing else Decimal("0"),
                    confidence_score=pattern.confidence_score,
                    correlation_id=correlation_id,
                    validation_chain=[
                        "pattern_risk",
                        "phase_prerequisites",
                        "r_multiple",
                        "structural_stop",
                        "position_size",
                        "portfolio_heat",
                        "campaign_risk",
                        "correlated_risk",
                    ],
                )
                signals.append(signal)

                # Publish event
                event = SignalGeneratedEvent(
                    correlation_id=correlation_id,
                    symbol=symbol,
                    timeframe=timeframe,
                    signal_id=signal.signal_id,
                    pattern_type=signal.pattern_type,
                    entry_price=float(signal.entry_price),
                    stop_price=float(signal.stop_price),
                    target_price=float(signal.target_price),
                    position_size=signal.position_size,
                    risk_amount=float(signal.risk_amount),
                    r_multiple=float(signal.r_multiple),
                )
                await self._event_bus.publish(event)

            async with self._lock:
                self._signal_count += len(signals)

            logger.info(
                "signals_generated",
                symbol=symbol,
                signal_count=len(signals),
                correlation_id=str(correlation_id),
            )

            return StageResult(
                success=True,
                output=signals,
                execution_time_ms=(time.perf_counter() - start_time) * 1000,
                stage_name="signal_generation",
            )

        except Exception as e:
            logger.error(
                "signal_generation_error",
                symbol=symbol,
                error=str(e),
                correlation_id=str(correlation_id),
            )
            return StageResult(
                success=False,
                output=None,
                error=str(e),
                execution_time_ms=(time.perf_counter() - start_time) * 1000,
                stage_name="signal_generation",
            )

    # Portfolio Context Builder

    async def _build_portfolio_context(self) -> Any:
        """
        Build PortfolioContext for risk validation.

        Fetches account equity, open positions, active campaigns,
        and configuration for risk validation.

        Returns:
            PortfolioContext object for risk validation
        """
        from src.models.portfolio import PortfolioContext
        from src.models.risk import CorrelationConfig

        # Default context for now
        # Real implementation would fetch from portfolio service
        return PortfolioContext(
            account_equity=Decimal("100000.00"),
            open_positions=[],
            active_campaigns=[],
            sector_mappings={},
            correlation_config=CorrelationConfig(
                max_sector_correlation=Decimal("6.0"),
                max_asset_class_correlation=Decimal("15.0"),
                enforcement_mode="strict",
                sector_mappings={},
            ),
            r_multiple_config={},
        )

    # Main Analysis Method

    async def analyze_symbol(self, symbol: str, timeframe: str) -> list[TradeSignal]:
        """
        Analyze a symbol and generate trade signals.

        Executes the full 7-stage pipeline:
        1. Fetch bars
        2. Analyze volume
        3. Detect trading ranges
        4. Detect phases
        5. Detect patterns
        6. Validate risk
        7. Generate signals

        Args:
            symbol: Stock symbol (e.g., "AAPL")
            timeframe: Bar timeframe (e.g., "1d")

        Returns:
            List of TradeSignal objects (may be empty if no patterns detected)

        Example:
            >>> orchestrator = MasterOrchestrator()
            >>> signals = await orchestrator.analyze_symbol("AAPL", "1d")
            >>> for signal in signals:
            ...     print(f"{signal.pattern_type}: {signal.entry_price}")
        """
        correlation_id = uuid4()
        start_time = time.perf_counter()

        async with self._lock:
            self._analysis_count += 1

        logger.info(
            "orchestrator_analysis_start",
            symbol=symbol,
            timeframe=timeframe,
            correlation_id=str(correlation_id),
        )

        try:
            # Stage 1: Data Ingestion
            data_result = await self._fetch_bars(symbol, timeframe, correlation_id)
            if not data_result.success:
                logger.warning(
                    "pipeline_stopped_at_data",
                    symbol=symbol,
                    error=data_result.error,
                    correlation_id=str(correlation_id),
                )
                return []
            bars = data_result.output

            # Stage 2: Volume Analysis
            volume_result = await self._analyze_volume(bars, symbol, timeframe, correlation_id)
            if not volume_result.success:
                logger.warning(
                    "pipeline_stopped_at_volume",
                    symbol=symbol,
                    error=volume_result.error,
                    correlation_id=str(correlation_id),
                )
                return []
            volume_analysis = volume_result.output

            # Stage 3: Trading Range Detection
            range_result = await self._detect_trading_ranges(
                bars, volume_analysis, symbol, timeframe, correlation_id
            )
            if not range_result.success:
                logger.warning(
                    "pipeline_stopped_at_range",
                    symbol=symbol,
                    error=range_result.error,
                    correlation_id=str(correlation_id),
                )
                return []
            trading_ranges = range_result.output or []

            if not trading_ranges:
                logger.info(
                    "no_trading_ranges_detected",
                    symbol=symbol,
                    correlation_id=str(correlation_id),
                )
                return []

            # Stage 4: Phase Detection
            phase_result = await self._detect_phases(
                bars, trading_ranges, volume_analysis, symbol, timeframe, correlation_id
            )
            if not phase_result.success:
                logger.warning(
                    "pipeline_stopped_at_phase",
                    symbol=symbol,
                    error=phase_result.error,
                    correlation_id=str(correlation_id),
                )
                return []
            phases = phase_result.output or []

            if not phases:
                logger.info(
                    "no_phases_detected",
                    symbol=symbol,
                    correlation_id=str(correlation_id),
                )
                return []

            # Stage 5: Pattern Detection
            pattern_result = await self._detect_patterns(
                bars, trading_ranges, phases, volume_analysis, symbol, timeframe, correlation_id
            )
            patterns = pattern_result.output or []

            if not patterns:
                logger.info(
                    "no_patterns_detected",
                    symbol=symbol,
                    correlation_id=str(correlation_id),
                )
                return []

            # Stage 6: Risk Validation
            risk_result = await self._validate_risk(patterns, symbol, correlation_id)
            validated_patterns = risk_result.output or []

            if not validated_patterns:
                logger.info(
                    "no_patterns_validated",
                    symbol=symbol,
                    correlation_id=str(correlation_id),
                )
                return []

            # Stage 7: Signal Generation
            signal_result = await self._generate_signals(
                validated_patterns, symbol, timeframe, correlation_id
            )
            signals = signal_result.output or []

            # Log completion
            total_time = (time.perf_counter() - start_time) * 1000
            logger.info(
                "orchestrator_analysis_complete",
                symbol=symbol,
                timeframe=timeframe,
                signals_generated=len(signals),
                total_time_ms=round(total_time, 2),
                correlation_id=str(correlation_id),
                stage_times={
                    "data": round(data_result.execution_time_ms, 2),
                    "volume": round(volume_result.execution_time_ms, 2),
                    "range": round(range_result.execution_time_ms, 2),
                    "phase": round(phase_result.execution_time_ms, 2),
                    "pattern": round(pattern_result.execution_time_ms, 2),
                    "risk": round(risk_result.execution_time_ms, 2),
                    "signal": round(signal_result.execution_time_ms, 2),
                },
            )

            return signals

        except Exception as e:
            async with self._lock:
                self._error_count += 1

            logger.error(
                "orchestrator_analysis_error",
                symbol=symbol,
                timeframe=timeframe,
                error=str(e),
                stack_trace=traceback.format_exc(),
                correlation_id=str(correlation_id),
            )

            # Publish error event
            event = DetectorFailedEvent(
                correlation_id=correlation_id,
                symbol=symbol,
                timeframe=timeframe,
                detector_name="master_orchestrator",
                error_message=str(e),
                stack_trace=traceback.format_exc(),
            )
            await self._event_bus.publish(event)

            return []

    # Parallel Symbol Processing

    async def analyze_symbols(
        self, symbols: list[str], timeframe: str
    ) -> dict[str, list[TradeSignal]]:
        """
        Analyze multiple symbols concurrently.

        Uses asyncio.gather with semaphore to limit concurrent analyses.
        Each symbol is analyzed independently with error isolation.

        Args:
            symbols: List of stock symbols
            timeframe: Bar timeframe for all symbols

        Returns:
            Dictionary mapping symbol to list of signals

        Example:
            >>> orchestrator = MasterOrchestrator()
            >>> results = await orchestrator.analyze_symbols(
            ...     ["AAPL", "MSFT", "GOOGL"], "1d"
            ... )
            >>> for symbol, signals in results.items():
            ...     print(f"{symbol}: {len(signals)} signals")
        """
        start_time = time.perf_counter()

        logger.info(
            "multi_symbol_analysis_start",
            symbol_count=len(symbols),
            timeframe=timeframe,
        )

        async def analyze_with_semaphore(symbol: str) -> tuple[str, list[TradeSignal]]:
            async with self._semaphore:
                signals = await self.analyze_symbol(symbol, timeframe)
                return (symbol, signals)

        # Run all analyses concurrently
        if self._config.enable_parallel_processing:
            tasks = [analyze_with_semaphore(s) for s in symbols]
            results = await asyncio.gather(*tasks, return_exceptions=True)
        else:
            results = []
            for s in symbols:
                try:
                    signals = await self.analyze_symbol(s, timeframe)
                    results.append((s, signals))
                except Exception as e:
                    results.append(e)

        # Collect results
        output: dict[str, list[TradeSignal]] = {}
        error_count = 0

        for result in results:
            if isinstance(result, BaseException):
                error_count += 1
                logger.error("symbol_analysis_exception", error=str(result))
            else:
                # result is tuple[str, list[TradeSignal]]
                result_tuple: tuple[str, list[TradeSignal]] = result
                output[result_tuple[0]] = result_tuple[1]

        total_time = (time.perf_counter() - start_time) * 1000
        total_signals = sum(len(s) for s in output.values())

        logger.info(
            "multi_symbol_analysis_complete",
            symbols_analyzed=len(output),
            symbols_failed=error_count,
            total_signals=total_signals,
            total_time_ms=round(total_time, 2),
            avg_time_per_symbol_ms=round(total_time / len(symbols), 2) if symbols else 0,
        )

        return output

    # Health and Metrics

    def get_health(self) -> dict[str, Any]:
        """
        Get orchestrator health status.

        Returns:
            Dictionary with:
            - status: "healthy", "degraded", or "unhealthy"
            - components: Health of each component
            - metrics: Analysis and error counts
        """
        container_health = self._container.health_check()
        cache_metrics = self._cache.get_metrics()
        event_bus_metrics = self._event_bus.get_metrics()

        # Determine overall status
        if container_health["status"] == "unhealthy":
            status = "unhealthy"
        elif container_health["status"] == "degraded" or self._error_count > 10:
            status = "degraded"
        else:
            status = "healthy"

        return {
            "status": status,
            "components": {
                "container": container_health,
                "cache": cache_metrics,
                "event_bus": event_bus_metrics,
            },
            "metrics": {
                "analysis_count": self._analysis_count,
                "signal_count": self._signal_count,
                "error_count": self._error_count,
            },
        }
