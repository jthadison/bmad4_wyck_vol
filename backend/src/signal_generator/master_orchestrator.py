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
        pattern_detectors: list[Any] | None = None,  # Stub for now
        volume_validator: VolumeValidator | None = None,
        phase_validator: PhaseValidator | None = None,
        level_validator: LevelValidator | None = None,
        risk_validator: RiskValidator | None = None,
        strategy_validator: StrategyValidator | None = None,
        signal_generator: Any = None,  # Stub for now
        signal_repository: Any = None,  # Stub for now
        rejection_repository: Any = None,  # Stub for now
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
            pattern_detectors: List of all 13 pattern detectors
            volume_validator: Story 8.3
            phase_validator: Story 8.4
            level_validator: Story 8.5
            risk_validator: Story 8.6
            strategy_validator: Story 8.7
            signal_generator: Create TradeSignal from validation results
            signal_repository: Persist signals
            rejection_repository: Log rejections
            performance_tracker: Track latency
            max_concurrent_symbols: Parallel processing limit
            cache_ttl_seconds: Cache expiration time
            enable_performance_tracking: Toggle metrics collection
        """
        self.market_data_service = market_data_service
        self.trading_range_service = trading_range_service
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
        self.performance_tracker = performance_tracker or PerformanceTracker()
        self.max_concurrent_symbols = max_concurrent_symbols
        self.cache_ttl_seconds = cache_ttl_seconds
        self.enable_performance_tracking = enable_performance_tracking

        # Caching
        self._range_cache: dict[str, tuple[Any, float]] = {}  # {symbol: (range, timestamp)}
        self._phase_cache: dict[str, tuple[Any, float]] = {}  # {symbol: (phase, timestamp)}

        # Real-time processing
        self._bar_queue: asyncio.Queue = asyncio.Queue(maxsize=10)
        self._signal_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()

        # System state
        self._system_halted: bool = False
        self._event_emitter: Any = None  # WebSocket event emitter

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

            # Fetch volume analysis (REQUIRED)
            volume_analysis = await self._fetch_volume_analysis(symbol, pattern)
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
            market_context = await self._build_market_context(symbol, asset_class)

            # Detect forex session if applicable
            forex_session = None
            if asset_class == "FOREX":
                forex_session = self._get_forex_session()

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
            position_size=Decimal("100"),  # Default
            position_size_unit="SHARES" if context.asset_class == "STOCK" else "LOTS",
            leverage=Decimal("50.0") if context.asset_class == "FOREX" else None,
            margin_requirement=Decimal("100.0") if context.asset_class == "FOREX" else None,
            notional_value=Decimal("15000.0"),  # Default
            risk_amount=Decimal("200.0"),  # Default
            r_multiple=Decimal("3.0"),  # Default
            confidence_score=confidence_components.overall_confidence,
            confidence_components=confidence_components,
            validation_chain=validation_chain,
            status="APPROVED",
            timestamp=datetime.now(UTC),
        )

        # Persist signal
        if self.signal_repository:
            await self.signal_repository.save_signal(signal)

        return signal

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

    async def check_emergency_exits(self, bar: Any) -> list[EmergencyExit]:
        """
        Check for emergency exit conditions (Story 8.9).

        Emergency conditions (FR21):
        - Spring low break: bar.low < campaign.spring_low
        - Ice break after SOS: bar.low < campaign.ice_level
        - UTAD high exceeded: bar.high > campaign.utad_high
        - Daily loss ≥3%: portfolio.daily_pnl_pct <= -3.0
        - Max drawdown ≥15%: portfolio.max_drawdown_pct >= 15.0

        Args:
            bar: Current OHLCV bar

        Returns:
            List of EmergencyExit events triggered
        """
        exits: list[EmergencyExit] = []

        # Stub implementation - would check actual campaign data
        # For now, just log and return empty list
        self.logger.debug("check_emergency_exits", bar=bar)

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
        """Fetch bars from market data service."""
        # Stub - return empty list for now
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

    async def _fetch_volume_analysis(self, symbol: str, pattern: Any) -> Any:
        """Fetch volume analysis for pattern."""
        # Stub
        return None

    async def _fetch_phase_info(self, symbol: str, timeframe: str) -> Any:
        """Fetch phase classification."""
        # Stub
        return None

    async def _fetch_trading_range(self, trading_range_id: Any) -> Any:
        """Fetch trading range by ID."""
        # Stub
        return None

    async def _fetch_portfolio_context(self) -> Any:
        """Fetch current portfolio state."""
        # Stub
        return None

    async def _build_market_context(self, symbol: str, asset_class: str) -> Any:
        """Build market context (asset-class-aware)."""
        # Stub
        return None

    async def _fetch_historical_bars(
        self, symbol: str, timeframe: str, start_date: datetime, end_date: datetime
    ) -> list[Any]:
        """Fetch historical bars for backtesting."""
        # Stub
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
