"""
MasterOrchestrator - Signal Generation Pipeline Coordinator (Story 8.10)

Purpose:
--------
Coordinates end-to-end signal generation pipeline from market data ingestion
through pattern detection, multi-stage validation, and final signal output.

Pipeline Stages:
----------------
1. Fetch bars from Market Data Service
2. Get trading ranges and levels
3. Run pattern detection (13 detectors in parallel)
4. Build validation context
5. Execute validation chain (Volume → Phase → Levels → Risk → Strategy)
6. Generate TradeSignal or RejectedSignal
7. Persist results and emit events

Operating Modes:
----------------
- Real-time mode: Process bars as they arrive via WebSocket
- Batch mode: Analyze historical periods for backtesting
- Multi-symbol watchlists: Parallel processing with concurrency limits

Integration:
------------
- Story 8.2: Multi-stage validation workflow
- Stories 8.3-8.7: All validators
- Story 8.8: TradeSignal/RejectedSignal output
- Story 8.9: Emergency exit conditions

Author: Story 8.10
"""

import asyncio
import time
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID, uuid4

import structlog
from pydantic import BaseModel, Field

from src.models.signal import ConfidenceComponents, RejectedSignal, TargetLevels, TradeSignal
from src.models.validation import (
    StageValidationResult,
    ValidationChain,
    ValidationContext,
    ValidationStatus,
)
from src.signal_generator.validators.level_validator import LevelValidator
from src.signal_generator.validators.phase_validator import PhaseValidator
from src.signal_generator.validators.risk_validator import RiskValidator
from src.signal_generator.validators.strategy_validator import StrategyValidator

# Note: These imports will be mocked/stubbed for now since not all are implemented
# from backend.src.market_data.service import MarketDataService
# from backend.src.pattern_engine.trading_range_service import TradingRangeService
# from backend.src.pattern_engine.detectors.base_detector import BasePatternDetector
from src.signal_generator.validators.volume_validator import VolumeValidator
from src.signal_prioritization.priority_queue import SignalPriorityQueue

# ============================================================================
# Forex Session Detection
# ============================================================================


class ForexSession(str):
    """Forex trading session identifier."""

    ASIAN = "ASIAN"
    LONDON = "LONDON"
    NY = "NY"
    OVERLAP = "OVERLAP"  # London + NY overlap (13:00-17:00 UTC)


# ============================================================================
# Backtest Result Model
# ============================================================================


class BacktestMetrics(BaseModel):
    """Backtest performance metrics."""

    total_patterns_detected: int = Field(..., description="Total patterns found")
    total_signals_generated: int = Field(..., description="Approved signals")
    total_signals_rejected: int = Field(..., description="Rejected signals")
    rejection_by_stage: dict[str, int] = Field(
        default_factory=dict, description="Rejections grouped by stage"
    )
    avg_latency_ms: float = Field(..., description="Average processing latency")
    p95_latency_ms: float = Field(..., description="95th percentile latency")
    p99_latency_ms: float = Field(..., description="99th percentile latency")


class BacktestResult(BaseModel):
    """Result of historical period analysis."""

    signals: list[TradeSignal] = Field(default_factory=list, description="Generated signals")
    rejections: list[RejectedSignal] = Field(default_factory=list, description="Rejected signals")
    metrics: BacktestMetrics = Field(..., description="Performance statistics")
    processing_time_seconds: float = Field(..., description="Total execution time")


# ============================================================================
# Emergency Exit Model
# ============================================================================


class EmergencyExit(BaseModel):
    """Emergency exit event."""

    id: UUID = Field(default_factory=uuid4)
    campaign_id: str = Field(..., description="Campaign being exited")
    reason: str = Field(..., description="Exit trigger reason")
    exit_price: Decimal = Field(..., description="Exit execution price")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PortfolioState(BaseModel):
    """
    Portfolio state for emergency exit checking (Story 8.10.3).

    Provides all fields needed for asset-class-aware emergency exits:
    - Daily P&L tracking (daily_pnl, daily_pnl_pct)
    - Max drawdown tracking (max_drawdown_pct)
    - Forex notional exposure (total_forex_notional, max_forex_notional)
    """

    total_equity: Decimal = Field(..., description="Current account equity")
    available_equity: Decimal = Field(..., description="Available equity for new trades")
    daily_pnl: Decimal = Field(..., description="Dollar P&L for current day")
    daily_pnl_pct: Decimal = Field(..., description="Percentage P&L (daily_pnl / total_equity)")
    max_drawdown_pct: Decimal = Field(..., description="Maximum drawdown since inception")
    total_heat: Decimal = Field(..., description="Current risk exposure (%)")
    total_forex_notional: Decimal = Field(
        default=Decimal("0"), description="Total forex notional exposure (Story 8.6.1)"
    )
    max_forex_notional: Decimal = Field(
        default=Decimal("0"), description="Max forex notional (3x equity)"
    )


# ============================================================================
# Performance Tracker (Stub Implementation)
# ============================================================================


class PerformanceTracker:
    """
    Tracks latency at each pipeline stage.

    Provides timing measurements for performance monitoring and alerts.
    """

    def __init__(self):
        self.timers: dict[str, float] = {}
        self.measurements: dict[str, list[float]] = defaultdict(list)
        self.logger = structlog.get_logger(__name__)

    def start_timer(self, name: str) -> str:
        """Start a new timer and return timer ID."""
        timer_id = f"{name}_{uuid4()}"
        self.timers[timer_id] = time.time() * 1000  # milliseconds
        return timer_id

    def end_timer(self, timer_id: str) -> float:
        """End timer and return elapsed milliseconds."""
        if timer_id not in self.timers:
            self.logger.warning("end_timer_unknown_id", timer_id=timer_id)
            return 0.0

        start_time = self.timers.pop(timer_id)
        elapsed = (time.time() * 1000) - start_time

        # Extract stage name from timer_id
        stage_name = timer_id.rsplit("_", 1)[0]
        self.measurements[stage_name].append(elapsed)

        return elapsed

    def get_metrics(self) -> dict[str, Any]:
        """Get performance statistics."""
        metrics = {}
        for stage, times in self.measurements.items():
            if not times:
                continue
            sorted_times = sorted(times)
            metrics[stage] = {
                "count": len(times),
                "avg_ms": sum(times) / len(times),
                "p50_ms": sorted_times[len(sorted_times) // 2],
                "p95_ms": sorted_times[int(len(sorted_times) * 0.95)]
                if len(sorted_times) > 20
                else sorted_times[-1],
                "p99_ms": sorted_times[int(len(sorted_times) * 0.99)]
                if len(sorted_times) > 100
                else sorted_times[-1],
            }
        return metrics


# ============================================================================
# MasterOrchestrator
# ============================================================================


class MasterOrchestrator:
    """
    Coordinates end-to-end signal generation pipeline.

    Pipeline stages:
    1. Fetch bars from Market Data Service
    2. Get trading ranges and levels
    3. Run pattern detection (13 detectors in parallel)
    4. Build validation context
    5. Execute validation chain (Volume → Phase → Levels → Risk → Strategy)
    6. Generate TradeSignal or RejectedSignal
    7. Persist results and emit events

    Supports:
    - Real-time mode: Process bars as they arrive via WebSocket
    - Batch mode: Analyze historical periods for backtesting
    - Multi-symbol watchlists: Parallel processing with concurrency limits
    """

    def __init__(
        self,
        market_data_service: Any = None,  # Stub for now
        trading_range_service: Any = None,  # Stub for now
        volume_service: Any = None,  # NEW: Story 8.10.1 - Volume analysis service
        portfolio_service: Any = None,  # NEW: Story 8.10.1 - Portfolio context service
        market_context_builder: Any = None,  # NEW: Story 8.10.1 - Market context builder
        pattern_detectors: list[Any] | None = None,  # Stub for now
        volume_validator: VolumeValidator | None = None,
        phase_validator: PhaseValidator | None = None,
        level_validator: LevelValidator | None = None,
        risk_validator: RiskValidator | None = None,
        strategy_validator: StrategyValidator | None = None,
        signal_generator: Any = None,  # Stub for now
        signal_repository: Any = None,  # Stub for now
        rejection_repository: Any = None,  # Stub for now
        signal_priority_queue: SignalPriorityQueue | None = None,  # NEW: Story 9.3
        websocket_manager: Any = None,  # NEW: Story 10.9 - WebSocket event emissions
        performance_tracker: PerformanceTracker | None = None,
        max_concurrent_symbols: int = 10,
        cache_ttl_seconds: int = 300,
        enable_performance_tracking: bool = True,
    ):
        """
        Initialize orchestrator with all dependencies (dependency injection).

        Args:
            market_data_service: Fetch OHLCV bars
            trading_range_service: Get ranges and levels
            volume_service: Volume analysis service (Story 8.10.1)
            portfolio_service: Portfolio context service (Story 8.10.1)
            market_context_builder: Asset-class-aware market context builder (Story 8.10.1)
            pattern_detectors: List of all 13 pattern detectors
            volume_validator: Story 8.3
            phase_validator: Story 8.4
            level_validator: Story 8.5
            risk_validator: Story 8.6
            strategy_validator: Story 8.7
            signal_generator: Create TradeSignal from validation results
            signal_repository: Persist signals
            rejection_repository: Log rejections
            signal_priority_queue: Priority queue for signal ranking (Story 9.3)
            performance_tracker: Track latency
            max_concurrent_symbols: Parallel processing limit
            cache_ttl_seconds: Cache expiration time
            enable_performance_tracking: Toggle metrics collection
        """
        self.market_data_service = market_data_service
        self.trading_range_service = trading_range_service
        self.volume_service = volume_service  # NEW: Story 8.10.1
        self.portfolio_service = portfolio_service  # NEW: Story 8.10.1
        self.market_context_builder = market_context_builder  # NEW: Story 8.10.1
        self.pattern_detectors = pattern_detectors or []

        # Initialize validators (create default instances if not provided)
        self.volume_validator = volume_validator or VolumeValidator()
        self.phase_validator = phase_validator or PhaseValidator()
        self.level_validator = level_validator or LevelValidator()
        self.risk_validator = risk_validator or RiskValidator()
        # StrategyValidator requires news_calendar_factory, so must be provided
        self.strategy_validator = strategy_validator

        self.signal_generator = signal_generator
        self.signal_repository = signal_repository
        self.rejection_repository = rejection_repository
        self.signal_priority_queue = signal_priority_queue  # NEW: Story 9.3
        self.websocket_manager = websocket_manager  # NEW: Story 10.9
        self.performance_tracker = performance_tracker or PerformanceTracker()
        self.max_concurrent_symbols = max_concurrent_symbols
        self.cache_ttl_seconds = cache_ttl_seconds
        self.enable_performance_tracking = enable_performance_tracking

        # Caching
        self._range_cache: dict[str, tuple[Any, float]] = {}  # {symbol: (range, timestamp)}
        self._phase_cache: dict[str, tuple[Any, float]] = {}  # {symbol: (phase, timestamp)}

        # System state
        self._system_halted: bool = False
        self._event_emitter: Any = None  # Deprecated: use websocket_manager instead

        self.logger = structlog.get_logger(__name__)

    # ========================================================================
    # Core Orchestration Methods
    # ========================================================================

    async def analyze_symbol(
        self,
        symbol: str,
        timeframe: str,
        correlation_id: str | None = None,
    ) -> list[TradeSignal]:
        """
        Analyze a single symbol for patterns and generate signals.

        Args:
            symbol: Ticker symbol (e.g., "AAPL") or forex pair ("EUR/USD")
            timeframe: Bar interval (e.g., "1h", "1d")
            correlation_id: Optional request correlation ID

        Returns:
            List of generated TradeSignals (approved signals only)

        Raises:
            None - errors are logged and processing continues
        """
        correlation_id = correlation_id or str(uuid4())

        self.logger.info(
            "analyze_symbol_start",
            symbol=symbol,
            timeframe=timeframe,
            correlation_id=correlation_id,
        )

        # Start performance tracking
        total_timer = (
            self.performance_tracker.start_timer("total_pipeline")
            if self.enable_performance_tracking
            else None
        )

        try:
            # 1. Fetch bars
            fetch_timer = (
                self.performance_tracker.start_timer("fetch_bars")
                if self.enable_performance_tracking
                else None
            )
            bars = await self._fetch_bars(symbol, timeframe, limit=100)
            if fetch_timer:
                self.performance_tracker.end_timer(fetch_timer)

            if not bars:
                self.logger.warning("no_bars_found", symbol=symbol, correlation_id=correlation_id)
                return []

            # 2. Get trading ranges
            range_timer = (
                self.performance_tracker.start_timer("fetch_ranges")
                if self.enable_performance_tracking
                else None
            )
            trading_ranges = await self._get_trading_ranges(symbol)
            if range_timer:
                self.performance_tracker.end_timer(range_timer)

            # 3. Run pattern detection (all detectors in parallel)
            detect_timer = (
                self.performance_tracker.start_timer("pattern_detection")
                if self.enable_performance_tracking
                else None
            )
            detected_patterns = await self._run_pattern_detection(
                bars, trading_ranges, correlation_id
            )
            if detect_timer:
                self.performance_tracker.end_timer(detect_timer)

            # 4. Validate and generate signals
            signals = []
            for pattern in detected_patterns:
                try:
                    signal = await self._process_pattern(pattern, correlation_id)
                    if isinstance(signal, TradeSignal):
                        signals.append(signal)
                except Exception as e:
                    self.logger.error(
                        "pattern_processing_error",
                        pattern_id=str(pattern.get("id", "unknown")),
                        error=str(e),
                        correlation_id=correlation_id,
                        exc_info=True,
                    )

            # 5. Check performance (NFR1: <1 second per symbol per bar)
            if total_timer:
                total_latency = self.performance_tracker.end_timer(total_timer)
                if total_latency > 1000:
                    self.logger.warning(
                        "performance_threshold_exceeded",
                        latency_ms=total_latency,
                        threshold_ms=1000,
                        symbol=symbol,
                        correlation_id=correlation_id,
                    )

            self.logger.info(
                "analyze_symbol_complete",
                symbol=symbol,
                patterns_detected=len(detected_patterns),
                signals_generated=len(signals),
                correlation_id=correlation_id,
            )

            return signals

        except Exception as e:
            self.logger.error(
                "analyze_symbol_failed",
                symbol=symbol,
                error=str(e),
                correlation_id=correlation_id,
                exc_info=True,
            )
            return []

    async def run_validation_chain(
        self,
        pattern: Any,
        context: ValidationContext,
        correlation_id: str,
    ) -> ValidationChain:
        """
        Execute multi-stage validation chain (FR20).

        Validation stages (in order):
        1. Volume (Story 8.3)
        2. Phase (Story 8.4)
        3. Levels (Story 8.5)
        4. Risk (Story 8.6)
        5. Strategy (Story 8.7)

        Early exit: If any stage returns FAIL, stop and return.

        Args:
            pattern: Detected pattern
            context: Validation context with all required data
            correlation_id: Request correlation ID

        Returns:
            ValidationChain with all validation results
        """
        chain = ValidationChain(pattern_id=pattern.get("id", uuid4()))
        chain.started_at = datetime.now(UTC)

        try:
            # Stage 1: Volume Validation
            volume_result = await self.volume_validator.validate(context)
            chain.add_result(volume_result)
            if volume_result.status == ValidationStatus.FAIL:
                chain.completed_at = datetime.now(UTC)
                return chain

            # Stage 2: Phase Validation
            phase_result = await self.phase_validator.validate(context)
            chain.add_result(phase_result)
            if phase_result.status == ValidationStatus.FAIL:
                chain.completed_at = datetime.now(UTC)
                return chain

            # Stage 3: Level Validation
            level_result = await self.level_validator.validate(context)
            chain.add_result(level_result)
            if level_result.status == ValidationStatus.FAIL:
                chain.completed_at = datetime.now(UTC)
                return chain

            # Stage 4: Risk Validation
            risk_result = await self.risk_validator.validate(context)
            chain.add_result(risk_result)
            if risk_result.status == ValidationStatus.FAIL:
                chain.completed_at = datetime.now(UTC)
                return chain

            # Stage 5: Strategy Validation
            strategy_result = await self.strategy_validator.validate(context)
            chain.add_result(strategy_result)
            if strategy_result.status == ValidationStatus.FAIL:
                chain.completed_at = datetime.now(UTC)
                return chain

            # All stages passed
            chain.completed_at = datetime.now(UTC)
            return chain

        except Exception as e:
            self.logger.error(
                "validation_chain_error",
                pattern_id=str(pattern.get("id", "unknown")),
                error=str(e),
                correlation_id=correlation_id,
                exc_info=True,
            )
            # Create FAIL result for exception
            error_result = StageValidationResult(
                stage="SYSTEM",
                status=ValidationStatus.FAIL,
                reason=f"Validation chain error: {str(e)}",
                validator_id="MASTER_ORCHESTRATOR",
            )
            chain.add_result(error_result)
            chain.completed_at = datetime.now(UTC)
            return chain

    async def build_validation_context(
        self,
        pattern: Any,
        symbol: str,
        timeframe: str,
    ) -> ValidationContext | None:
        """
        Build ValidationContext for validation chain (FOREX-AWARE).

        Args:
            pattern: Detected pattern
            symbol: Trading symbol
            timeframe: Bar interval

        Returns:
            ValidationContext with all required data, or None if data missing
        """
        try:
            # Detect asset class
            asset_class = self._detect_asset_class(symbol)

            # Detect forex session if applicable (MUST be done before _fetch_volume_analysis)
            # Story 8.3.1: Volume analysis requires forex_session for session-aware baselines
            forex_session = None
            if asset_class == "FOREX":
                forex_session = self._get_forex_session()

            # Fetch volume analysis (REQUIRED)
            # CRITICAL: Pass forex_session for session-aware volume baselines (Victoria requirement)
            volume_analysis = await self._fetch_volume_analysis(symbol, pattern, forex_session)
            if not volume_analysis:
                self.logger.error(
                    "volume_analysis_missing", symbol=symbol, pattern_id=str(pattern.get("id"))
                )
                return None

            # Fetch phase info (optional)
            phase_info = await self._fetch_phase_info(symbol, timeframe)

            # Fetch trading range (optional)
            trading_range = await self._fetch_trading_range(pattern.get("trading_range_id"))

            # Fetch portfolio context (optional)
            portfolio_context = await self._fetch_portfolio_context()

            # Build market context (asset-class-aware)
            market_context = await self._build_market_context(symbol, asset_class, forex_session)

            # Build context
            context = ValidationContext(
                pattern=pattern,
                symbol=symbol,
                timeframe=timeframe,
                volume_analysis=volume_analysis,
                asset_class=asset_class,
                forex_session=forex_session,
                phase_info=phase_info,
                trading_range=trading_range,
                portfolio_context=portfolio_context,
                market_context=market_context,
            )

            return context

        except Exception as e:
            self.logger.error(
                "build_validation_context_error",
                symbol=symbol,
                error=str(e),
                exc_info=True,
            )
            return None

    # ========================================================================
    # Signal Generation
    # ========================================================================

    async def generate_signal_from_pattern(
        self,
        pattern: Any,
        validation_chain: ValidationChain,
        context: ValidationContext,
    ) -> TradeSignal | RejectedSignal:
        """
        Generate TradeSignal or RejectedSignal from validation results.

        Args:
            pattern: Detected pattern
            validation_chain: Validation results
            context: Validation context

        Returns:
            TradeSignal if validation passed, RejectedSignal otherwise
        """
        # If validation failed, create RejectedSignal
        if validation_chain.overall_status == ValidationStatus.FAIL:
            rejected = RejectedSignal(
                pattern_id=pattern.get("id", uuid4()),
                symbol=context.symbol,
                pattern_type=pattern.get("pattern_type", "UNKNOWN"),
                rejection_stage=validation_chain.rejection_stage or "UNKNOWN",
                rejection_reason=validation_chain.rejection_reason or "Validation failed",
                validation_chain=validation_chain,
                timestamp=datetime.now(UTC),
            )

            # Log rejection
            if self.rejection_repository:
                await self.rejection_repository.log_rejection(rejected)

            # Story 10.9: Emit signal:rejected event via WebSocket
            if self.websocket_manager:
                try:
                    await self.websocket_manager.emit_signal_rejected(
                        {
                            "id": str(rejected.pattern_id),
                            "symbol": rejected.symbol,
                            "pattern_type": rejected.pattern_type,
                            "rejection_stage": rejected.rejection_stage,
                            "rejection_reason": rejected.rejection_reason,
                            "timestamp": rejected.timestamp.isoformat(),
                        }
                    )
                except Exception as e:
                    self.logger.warning(
                        "websocket_emit_failed",
                        event="signal:rejected",
                        error=str(e),
                    )

            return rejected

        # Validation passed, create TradeSignal
        # Extract data from pattern and context
        entry_price = pattern.get("entry_price", Decimal("0"))
        stop_loss = pattern.get("stop_loss", Decimal("0"))
        target_price = pattern.get("target_price", Decimal("0"))

        # Build confidence components
        confidence_components = ConfidenceComponents(
            pattern_confidence=pattern.get("confidence_score", 80),
            phase_confidence=context.phase_info.confidence
            if context.phase_info and hasattr(context.phase_info, "confidence")
            else 75,
            volume_confidence=80,  # Default
            overall_confidence=80,  # Will be validated by model
        )

        # Build target levels
        target_levels = TargetLevels(
            primary_target=target_price,
            secondary_targets=[],
        )

        # Story 8.10.2: Extract risk metadata from RiskValidator
        risk_metadata = validation_chain.get_metadata_for_stage("Risk")

        # Story 8.10.2 AC 7: Error handling for missing metadata
        if not risk_metadata:
            self.logger.critical(
                "risk_metadata_missing",
                pattern_id=pattern.get("id"),
                symbol=context.symbol,
                pattern_type=pattern.get("pattern_type"),
                validation_chain_status=validation_chain.overall_status,
            )
            return RejectedSignal(
                pattern_id=pattern.get("id", UUID(int=0)),
                symbol=context.symbol,
                pattern_type=pattern.get("pattern_type", "UNKNOWN"),
                rejection_stage="SYSTEM",
                rejection_reason="Risk validator did not provide position sizing metadata",
                validation_chain=validation_chain,
            )

        # Story 8.10.2 AC 3: Extract calculated values from metadata
        position_size = risk_metadata.get("position_size", Decimal("0"))
        position_size_unit = risk_metadata.get("position_size_unit", "SHARES")
        leverage = risk_metadata.get("leverage")
        margin_requirement = risk_metadata.get("margin_requirement")
        notional_value = risk_metadata.get("notional_value", Decimal("0"))
        risk_amount = risk_metadata.get("risk_amount", Decimal("0"))
        r_multiple = risk_metadata.get("r_multiple", Decimal("0"))

        # Create TradeSignal
        signal = TradeSignal(
            asset_class=context.asset_class,
            symbol=context.symbol,
            pattern_type=pattern.get("pattern_type", "SPRING"),
            phase=pattern.get("phase", "C"),
            timeframe=context.timeframe,
            entry_price=entry_price,
            stop_loss=stop_loss,
            target_levels=target_levels,
            position_size=position_size,
            position_size_unit=position_size_unit,
            leverage=leverage,
            margin_requirement=margin_requirement,
            notional_value=notional_value,
            risk_amount=risk_amount,
            r_multiple=r_multiple,
            confidence_score=confidence_components.overall_confidence,
            confidence_components=confidence_components,
            validation_chain=validation_chain,
            status="APPROVED",
            timestamp=datetime.now(UTC),
        )

        # Persist signal
        if self.signal_repository:
            await self.signal_repository.save_signal(signal)

        # Add signal to priority queue (Story 9.3)
        if self.signal_priority_queue:
            self.signal_priority_queue.push(signal)
            self.logger.info(
                "signal_added_to_priority_queue",
                signal_id=str(signal.id),
                pattern_type=signal.pattern_type,
                confidence_score=signal.confidence_score,
                r_multiple=str(signal.r_multiple),
            )

        # Story 10.9: Emit signal:new event via WebSocket
        if self.websocket_manager:
            try:
                await self.websocket_manager.emit_signal_generated(
                    {
                        "id": str(signal.id),
                        "symbol": signal.symbol,
                        "pattern_type": signal.pattern_type,
                        "phase": signal.phase,
                        "entry_price": str(signal.entry_price),
                        "stop_loss": str(signal.stop_loss),
                        "target_price": str(signal.target_levels.primary_target),
                        "position_size": str(signal.position_size),
                        "position_size_unit": signal.position_size_unit,
                        "confidence_score": signal.confidence_score,
                        "r_multiple": str(signal.r_multiple),
                        "status": signal.status,
                        "timestamp": signal.timestamp.isoformat(),
                    }
                )
            except Exception as e:
                self.logger.warning(
                    "websocket_emit_failed",
                    event="signal:new",
                    error=str(e),
                )

        return signal

    # ========================================================================
    # Priority Queue Methods (Story 9.3)
    # ========================================================================

    def get_next_signal(self) -> TradeSignal | None:
        """
        Get highest priority signal from queue (Story 9.3).

        Pops and returns the signal with the highest priority score.
        Used by trading system to execute signals in priority order.

        Returns:
            TradeSignal | None: Highest priority signal, or None if queue empty
        """
        if not self.signal_priority_queue:
            self.logger.warning("signal_priority_queue_not_configured")
            return None

        signal = self.signal_priority_queue.pop()

        if signal:
            self.logger.info(
                "next_signal_retrieved",
                signal_id=str(signal.id),
                pattern_type=signal.pattern_type,
                symbol=signal.symbol,
            )

        return signal

    def get_pending_signals(self, limit: int = 50) -> list[TradeSignal]:
        """
        Get all pending signals in priority order (Story 9.3).

        Returns copy of signals without modifying queue.
        Used by API endpoint GET /signals?sorted=true.

        Args:
            limit: Maximum number of signals to return (default: 50)

        Returns:
            list[TradeSignal]: Signals sorted by priority (highest first)
        """
        if not self.signal_priority_queue:
            self.logger.warning("signal_priority_queue_not_configured")
            return []

        all_signals = self.signal_priority_queue.get_all_sorted()
        return all_signals[:limit]

    # ========================================================================
    # Multi-Symbol Watchlist Processing
    # ========================================================================

    async def analyze_watchlist(
        self,
        symbols: list[str],
        timeframe: str,
    ) -> dict[str, list[TradeSignal]]:
        """
        Analyze multiple symbols in parallel.

        Args:
            symbols: List of ticker symbols
            timeframe: Bar interval

        Returns:
            Dict mapping symbol to list of signals
        """
        semaphore = asyncio.Semaphore(self.max_concurrent_symbols)

        async def analyze_with_limit(symbol: str):
            async with semaphore:
                return await self.analyze_symbol(symbol, timeframe)

        tasks = [analyze_with_limit(sym) for sym in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Build result dict (exclude failed symbols)
        result_dict = {}
        for symbol, result in zip(symbols, results, strict=False):
            if isinstance(result, list):
                result_dict[symbol] = result
            else:
                self.logger.error(
                    "symbol_analysis_failed",
                    symbol=symbol,
                    error=str(result),
                )

        return result_dict

    # ========================================================================
    # Real-Time Mode
    # ========================================================================

    async def process_new_bar(self, bar: Any) -> list[TradeSignal]:
        """
        Process new bar in real-time mode (AC: 3).

        Called by Market Data Service when bar arrives via WebSocket.

        Args:
            bar: New OHLCV bar

        Returns:
            List of generated signals
        """
        symbol = bar.get("symbol") if isinstance(bar, dict) else getattr(bar, "symbol", "UNKNOWN")
        timeframe = (
            bar.get("timeframe") if isinstance(bar, dict) else getattr(bar, "timeframe", "1h")
        )

        # Invalidate cache for this symbol
        self._invalidate_cache(symbol)

        # Analyze symbol
        signals = await self.analyze_symbol(symbol, timeframe)

        # Emit WebSocket events
        for signal in signals:
            await self._emit_event("signal_generated", signal.model_dump())

        return signals

    # ========================================================================
    # Batch Mode (Backtesting)
    # ========================================================================

    async def analyze_historical_period(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
    ) -> BacktestResult:
        """
        Analyze historical period for backtesting (AC: 4).

        Args:
            symbol: Ticker symbol
            timeframe: Bar interval
            start_date: Start of period (UTC)
            end_date: End of period (UTC)

        Returns:
            BacktestResult with signals, rejections, metrics
        """
        start_time = time.time()
        signals: list[TradeSignal] = []
        rejections: list[RejectedSignal] = []
        latencies: list[float] = []

        self.logger.info(
            "backtest_start",
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
        )

        # Fetch historical bars
        bars = await self._fetch_historical_bars(symbol, timeframe, start_date, end_date)

        # Process each bar
        for bar in bars:
            bar_start = time.time()

            # Analyze symbol at this point in time
            bar_signals = await self.analyze_symbol(symbol, timeframe)

            for signal in bar_signals:
                if isinstance(signal, TradeSignal):
                    signals.append(signal)
                elif isinstance(signal, RejectedSignal):
                    rejections.append(signal)

            latencies.append((time.time() - bar_start) * 1000)

        # Calculate metrics
        rejection_by_stage: dict[str, int] = defaultdict(int)
        for rejection in rejections:
            rejection_by_stage[rejection.rejection_stage] += 1

        sorted_latencies = sorted(latencies) if latencies else [0.0]
        metrics = BacktestMetrics(
            total_patterns_detected=len(signals) + len(rejections),
            total_signals_generated=len(signals),
            total_signals_rejected=len(rejections),
            rejection_by_stage=dict(rejection_by_stage),
            avg_latency_ms=sum(latencies) / len(latencies) if latencies else 0.0,
            p95_latency_ms=sorted_latencies[int(len(sorted_latencies) * 0.95)]
            if len(sorted_latencies) > 20
            else sorted_latencies[-1],
            p99_latency_ms=sorted_latencies[int(len(sorted_latencies) * 0.99)]
            if len(sorted_latencies) > 100
            else sorted_latencies[-1],
        )

        processing_time = time.time() - start_time

        self.logger.info(
            "backtest_complete",
            symbol=symbol,
            signals_generated=len(signals),
            signals_rejected=len(rejections),
            processing_time_seconds=processing_time,
        )

        return BacktestResult(
            signals=signals,
            rejections=rejections,
            metrics=metrics,
            processing_time_seconds=processing_time,
        )

    # ========================================================================
    # Emergency Exit Integration
    # ========================================================================

    async def check_emergency_exits(
        self,
        bar: Any,
        portfolio: PortfolioState,
        asset_class: Literal["STOCK", "FOREX", "CRYPTO"],
    ) -> list[EmergencyExit]:
        """
        Check emergency exit conditions (asset-class-aware).

        Thresholds by asset class:
        - Forex: 2% daily loss (faster with leverage)
        - Stock: 3% daily loss
        - Both: 15% max drawdown (universal)
        - Forex: 3x notional exposure limit

        Emergency conditions (FR21):
        - Daily loss ≥ threshold (2% forex, 3% stocks)
        - Max drawdown ≥15%
        - Forex notional > 3x equity (FOREX only)

        Args:
            bar: Current OHLCV bar
            portfolio: Portfolio state with P&L and risk metrics
            asset_class: STOCK/FOREX/CRYPTO

        Returns:
            List of EmergencyExit events triggered
        """
        exits: list[EmergencyExit] = []

        # Determine asset-class-specific thresholds
        if asset_class == "FOREX":
            daily_loss_threshold = Decimal("-0.02")  # 2% for forex
        elif asset_class == "STOCK":
            daily_loss_threshold = Decimal("-0.03")  # 3% for stocks
        else:  # CRYPTO
            daily_loss_threshold = Decimal("-0.03")  # 3% for crypto (future)

        # Check daily loss limit (asset-class-aware)
        if portfolio.daily_pnl_pct <= daily_loss_threshold:
            reason = (
                f"Daily loss {portfolio.daily_pnl_pct:.2%} exceeds "
                f"{abs(daily_loss_threshold):.0%} limit for {asset_class}"
            )
            exits.append(
                EmergencyExit(
                    campaign_id="SYSTEM",  # System-wide halt
                    reason=reason,
                    exit_price=bar.close if hasattr(bar, "close") else Decimal("0"),
                    timestamp=datetime.now(UTC),
                )
            )
            self.logger.critical(
                "emergency_exit_daily_loss",
                reason=reason,
                asset_class=asset_class,
                daily_pnl_pct=float(portfolio.daily_pnl_pct),
                threshold=float(daily_loss_threshold),
                portfolio_equity=float(portfolio.total_equity),
            )

        # Check max drawdown (universal - applies to all asset classes)
        if portfolio.max_drawdown_pct >= Decimal("0.15"):
            reason = (
                f"Max drawdown {portfolio.max_drawdown_pct:.2%} exceeds 15% limit for {asset_class}"
            )
            exits.append(
                EmergencyExit(
                    campaign_id="SYSTEM",
                    reason=reason,
                    exit_price=bar.close if hasattr(bar, "close") else Decimal("0"),
                    timestamp=datetime.now(UTC),
                )
            )
            # System halt required for max drawdown
            self._system_halted = True
            self.logger.critical(
                "system_halted_max_drawdown",
                reason=reason,
                asset_class=asset_class,
                max_drawdown_pct=float(portfolio.max_drawdown_pct),
                portfolio_equity=float(portfolio.total_equity),
            )

        # Check forex notional exposure limit (FOREX only)
        if asset_class == "FOREX":
            if portfolio.total_forex_notional > portfolio.max_forex_notional:
                reason = (
                    f"Forex notional ${portfolio.total_forex_notional:,.0f} exceeds "
                    f"3x equity limit ${portfolio.max_forex_notional:,.0f}"
                )
                exits.append(
                    EmergencyExit(
                        campaign_id="SYSTEM",
                        reason=reason,
                        exit_price=bar.close if hasattr(bar, "close") else Decimal("0"),
                        timestamp=datetime.now(UTC),
                    )
                )
                self.logger.critical(
                    "emergency_exit_forex_notional",
                    reason=reason,
                    total_notional=float(portfolio.total_forex_notional),
                    max_notional=float(portfolio.max_forex_notional),
                    equity=float(portfolio.total_equity),
                )

        return exits

    # ========================================================================
    # Forex Session Detection
    # ========================================================================

    def _get_forex_session(self, current_time: datetime | None = None) -> str:
        """
        Detect current forex trading session.

        Session detection logic:
        - OVERLAP (London + NY): 13:00-17:00 UTC (8am-12pm EST) - HIGHEST PRIORITY
        - LONDON: 8:00-17:00 UTC (3am-12pm EST)
        - NY: 13:00-22:00 UTC (8am-5pm EST)
        - ASIAN: 0:00-8:00 UTC (7pm-3am EST)

        Args:
            current_time: Time to check (defaults to now in UTC)

        Returns:
            ForexSession enum value
        """
        if current_time is None:
            current_time = datetime.now(UTC)

        hour = current_time.hour

        # OVERLAP takes precedence (13:00-17:00 UTC)
        if 13 <= hour < 17:
            return ForexSession.OVERLAP

        # LONDON session (8:00-17:00 UTC)
        if 8 <= hour < 17:
            return ForexSession.LONDON

        # NY session (13:00-22:00 UTC)
        if 13 <= hour < 22:
            return ForexSession.NY

        # ASIAN session (0:00-8:00 UTC)
        return ForexSession.ASIAN

    def _is_forex_symbol(self, symbol: str) -> bool:
        """Check if symbol is forex pair."""
        return "/" in symbol

    def _detect_asset_class(self, symbol: str) -> Literal["STOCK", "FOREX", "CRYPTO"]:
        """
        Detect asset class from symbol.

        Args:
            symbol: Trading symbol

        Returns:
            Asset class: STOCK, FOREX, or CRYPTO
        """
        if "/" not in symbol:
            return "STOCK"

        # Check for crypto pairs
        crypto_bases = ["BTC", "ETH", "USDT", "USDC"]
        for crypto in crypto_bases:
            if symbol.startswith(crypto):
                return "CRYPTO"

        # Otherwise forex
        return "FOREX"

    # ========================================================================
    # Helper Methods (Stubs - will be implemented with real services)
    # ========================================================================

    async def _fetch_bars(self, symbol: str, timeframe: str, limit: int = 100) -> list[Any]:
        """
        Fetch OHLCV bars from MarketDataService.

        Args:
            symbol: Trading symbol
            timeframe: Bar interval (1m, 5m, 15m, 1h, 1d)
            limit: Number of recent bars to fetch (default: 100)

        Returns:
            List of OHLCVBar objects, or empty list on error
        """
        try:
            if not self.market_data_service:
                self.logger.warning("market_data_service_not_configured", symbol=symbol)
                return []

            # Call market data service to fetch bars
            bars = await self.market_data_service.fetch_bars(
                symbol=symbol, timeframe=timeframe, limit=limit
            )
            return bars
        except Exception as e:
            self.logger.error(
                "fetch_bars_failed",
                symbol=symbol,
                timeframe=timeframe,
                limit=limit,
                error=str(e),
                exc_info=True,
            )
            return []

    async def _get_trading_ranges(self, symbol: str) -> list[Any]:
        """Get trading ranges for symbol."""
        # Stub - return empty list for now
        return []

    async def _run_pattern_detection(
        self, bars: list[Any], trading_ranges: list[Any], correlation_id: str
    ) -> list[Any]:
        """Run all pattern detectors in parallel."""
        # Stub - return empty list for now
        return []

    async def _process_pattern(
        self, pattern: Any, correlation_id: str
    ) -> TradeSignal | RejectedSignal | None:
        """Process a single detected pattern through validation chain."""
        # Stub implementation
        return None

    async def _fetch_volume_analysis(
        self, symbol: str, pattern: Any, forex_session: str | None = None
    ) -> Any:
        """
        Fetch volume analysis for pattern bar.

        IMPORTANT: forex_session parameter is REQUIRED for forex symbols
        to use session-aware volume baselines (Story 8.3.1).

        Args:
            symbol: Ticker symbol
            pattern: Pattern dict with bar_timestamp
            forex_session: ASIAN/LONDON/NY/OVERLAP (forex only)

        Returns:
            VolumeAnalysis object or None if not found
        """
        try:
            if not hasattr(self, "volume_service") or not self.volume_service:
                self.logger.warning("volume_service_not_configured", symbol=symbol)
                return None

            # Get bar timestamp from pattern
            bar_timestamp = pattern.get("bar_timestamp")
            if not bar_timestamp:
                self.logger.error(
                    "pattern_missing_timestamp", symbol=symbol, pattern_id=str(pattern.get("id"))
                )
                return None

            # Call volume service with forex_session for session-aware baselines
            volume_analysis = await self.volume_service.get_analysis(
                symbol=symbol,
                timestamp=bar_timestamp,
                forex_session=forex_session,  # Pass session for Story 8.3.1
            )
            return volume_analysis
        except Exception as e:
            self.logger.error(
                "fetch_volume_analysis_failed",
                symbol=symbol,
                forex_session=forex_session,
                error=str(e),
                exc_info=True,
            )
            return None

    async def _fetch_phase_info(self, symbol: str, timeframe: str) -> Any:
        """Fetch phase classification."""
        # Stub
        return None

    async def _fetch_trading_range(self, trading_range_id: UUID | None) -> Any:
        """
        Fetch TradingRange by UUID.

        Args:
            trading_range_id: UUID of trading range

        Returns:
            TradingRange object or None if not found
        """
        try:
            if not trading_range_id:
                return None

            if not self.trading_range_service:
                self.logger.warning("trading_range_service_not_configured")
                return None

            trading_range = await self.trading_range_service.get_by_id(trading_range_id)
            return trading_range
        except Exception as e:
            self.logger.error(
                "fetch_trading_range_failed",
                trading_range_id=str(trading_range_id) if trading_range_id else None,
                error=str(e),
                exc_info=True,
            )
            return None

    async def _fetch_portfolio_context(self) -> Any:
        """
        Fetch current portfolio state.

        Returns PortfolioContext with:
        - total_equity
        - available_equity
        - total_heat (current risk exposure)
        - active_positions
        - active_campaigns
        - total_forex_notional (NEW: Story 8.6.1 - Rachel requirement)
        - max_forex_notional (3x equity limit)

        Returns:
            PortfolioContext or None on error
        """
        try:
            if not hasattr(self, "portfolio_service") or not self.portfolio_service:
                self.logger.warning("portfolio_service_not_configured")
                # Return safe defaults (no positions, no heat)
                return {
                    "total_equity": Decimal("0"),
                    "available_equity": Decimal("0"),
                    "total_heat": Decimal("0"),
                    "active_positions": [],
                    "active_campaigns": [],
                    "total_forex_notional": Decimal("0"),
                    "max_forex_notional": Decimal("0"),
                }

            portfolio = await self.portfolio_service.get_current_context()
            return portfolio
        except Exception as e:
            self.logger.error("fetch_portfolio_context_failed", error=str(e), exc_info=True)
            # Return safe defaults (no positions, no heat)
            return {
                "total_equity": Decimal("0"),
                "available_equity": Decimal("0"),
                "total_heat": Decimal("0"),
                "active_positions": [],
                "active_campaigns": [],
                "total_forex_notional": Decimal("0"),
                "max_forex_notional": Decimal("0"),
            }

    async def _build_market_context(
        self,
        symbol: str,
        asset_class: Literal["STOCK", "FOREX", "CRYPTO"],
        forex_session: str | None = None,
    ) -> Any:
        """
        Build asset-class-aware market context.

        For STOCK: Fetch earnings calendar, market regime
        For FOREX: Fetch forex news calendar, current session liquidity

        Args:
            symbol: Ticker symbol
            asset_class: STOCK/FOREX/CRYPTO
            forex_session: ASIAN/LONDON/NY/OVERLAP (forex only)

        Returns:
            MarketContext with asset-class-specific data
        """
        try:
            if not hasattr(self, "market_context_builder") or not self.market_context_builder:
                self.logger.warning("market_context_builder_not_configured", symbol=symbol)
                # Return safe defaults (no news, no events)
                return {
                    "symbol": symbol,
                    "asset_class": asset_class,
                    "upcoming_events": [],
                    "market_regime": "UNKNOWN",
                }

            context = await self.market_context_builder.build(
                symbol=symbol, asset_class=asset_class, forex_session=forex_session
            )
            return context
        except Exception as e:
            self.logger.error(
                "build_market_context_failed",
                symbol=symbol,
                asset_class=asset_class,
                forex_session=forex_session,
                error=str(e),
                exc_info=True,
            )
            # Return safe defaults (no news, no events)
            return {
                "symbol": symbol,
                "asset_class": asset_class,
                "upcoming_events": [],
                "market_regime": "UNKNOWN",
            }

    async def _fetch_historical_bars(
        self, symbol: str, timeframe: str, start_date: datetime, end_date: datetime
    ) -> list[Any]:
        """
        Fetch historical bars for backtesting.

        Returns bars in chronological order (oldest first).

        Args:
            symbol: Trading symbol
            timeframe: Bar interval
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            List of OHLCVBar objects sorted by timestamp, or empty list on error
        """
        try:
            if not self.market_data_service:
                self.logger.warning("market_data_service_not_configured", symbol=symbol)
                return []

            bars = await self.market_data_service.fetch_historical(
                symbol=symbol, timeframe=timeframe, start_date=start_date, end_date=end_date
            )

            # Ensure chronological order (oldest first for backtesting)
            bars.sort(key=lambda b: b.timestamp)
            return bars
        except Exception as e:
            self.logger.error(
                "fetch_historical_bars_failed",
                symbol=symbol,
                timeframe=timeframe,
                start_date=start_date.isoformat() if start_date else None,
                end_date=end_date.isoformat() if end_date else None,
                error=str(e),
                exc_info=True,
            )
            return []

    def _invalidate_cache(self, symbol: str) -> None:
        """Invalidate cached data for symbol."""
        self._range_cache.pop(symbol, None)
        self._phase_cache.pop(symbol, None)

    async def _emit_event(self, event_type: str, payload: dict) -> None:
        """Emit WebSocket event."""
        if self._event_emitter:
            await self._event_emitter.emit(event_type, payload)
        else:
            self.logger.debug("event_emitted", event_type=event_type, payload=payload)
