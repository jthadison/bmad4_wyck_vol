"""
Multi-Symbol Concurrent Processor.

Handles concurrent processing of multiple symbols with:
- Per-symbol isolation
- Circuit breakers for failure handling
- Latency tracking
- Admin notifications

Story 19.4 - Multi-Symbol Concurrent Processing.
"""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import structlog

from src.config import settings
from src.models.ohlcv import OHLCVBar
from src.models.scanner import (
    CircuitStateEnum,
    ScannerStatusResponse,
    SymbolState,
    SymbolStatus,
)
from src.observability.metrics import (
    stale_symbols_gauge,
    stale_symbols_total,
    symbol_data_age_seconds,
)
from src.pattern_engine.circuit_breaker import CircuitBreaker, CircuitState

logger = structlog.get_logger(__name__)


# Configuration defaults
DEFAULT_MAX_CONCURRENT = 10
DEFAULT_PROCESSING_TIMEOUT_MS = 200
DEFAULT_CIRCUIT_BREAKER_THRESHOLD = 3
DEFAULT_LATENCY_SAMPLE_SIZE = 100


@dataclass
class SymbolMetrics:
    """Metrics for a single symbol's processing."""

    bars_processed: int = 0
    total_latency_ms: float = 0.0
    latency_samples: deque[float] = field(
        default_factory=lambda: deque(maxlen=DEFAULT_LATENCY_SAMPLE_SIZE)
    )
    last_processed: datetime | None = None
    last_error: str | None = None
    # Staleness tracking (Story 19.26)
    last_bar_time: datetime | None = None  # Timestamp of the last bar received

    @property
    def avg_latency_ms(self) -> float:
        """Calculate average latency from recent samples."""
        if not self.latency_samples:
            return 0.0
        return sum(self.latency_samples) / len(self.latency_samples)

    def is_stale(self) -> bool:
        """Check if symbol data is stale (Story 19.26)."""
        if self.last_bar_time is None:
            return True
        last_bar = self.last_bar_time
        if last_bar.tzinfo is None:
            last_bar = last_bar.replace(tzinfo=UTC)
        age = datetime.now(UTC) - last_bar
        threshold = timedelta(seconds=settings.staleness_threshold_seconds)
        return age > threshold

    def get_data_age_seconds(self) -> float | None:
        """Get age of last bar in seconds (Story 19.26)."""
        if self.last_bar_time is None:
            return None
        last_bar = self.last_bar_time
        if last_bar.tzinfo is None:
            last_bar = last_bar.replace(tzinfo=UTC)
        age = datetime.now(UTC) - last_bar
        return age.total_seconds()


@dataclass
class SymbolContext:
    """Context for processing a single symbol."""

    symbol: str
    circuit_breaker: CircuitBreaker
    metrics: SymbolMetrics = field(default_factory=SymbolMetrics)
    queue: asyncio.Queue[OHLCVBar] = field(default_factory=lambda: asyncio.Queue(maxsize=100))
    processor_task: asyncio.Task | None = field(default=None, init=False)
    enabled: bool = True


class MultiSymbolProcessor:
    """
    Concurrent processor for multiple symbols.

    Processes bars for multiple symbols concurrently with:
    - Per-symbol queues for isolation
    - Per-symbol circuit breakers
    - Latency tracking
    - Admin notifications on failures

    Usage:
        processor = MultiSymbolProcessor(
            symbols=["AAPL", "TSLA", "MSFT"],
            on_admin_notify=notify_admin,
        )
        await processor.start()
        processor.queue_bar(bar)  # Route to correct symbol
        status = processor.get_status()
        await processor.stop()
    """

    def __init__(
        self,
        symbols: list[str],
        bar_processor: Callable[[OHLCVBar], None] | None = None,
        on_admin_notify: Callable[[str, str], None] | None = None,
        max_concurrent: int = DEFAULT_MAX_CONCURRENT,
        processing_timeout_ms: int = DEFAULT_PROCESSING_TIMEOUT_MS,
        circuit_breaker_threshold: int = DEFAULT_CIRCUIT_BREAKER_THRESHOLD,
    ):
        """
        Initialize multi-symbol processor.

        Args:
            symbols: List of symbol tickers to process
            bar_processor: Async callable to process each bar
            on_admin_notify: Callback for admin notifications (symbol, message)
            max_concurrent: Maximum concurrent symbol processors
            processing_timeout_ms: Target processing time per bar
            circuit_breaker_threshold: Failures before circuit opens
        """
        self._symbols = symbols[:max_concurrent]  # Limit to max concurrent
        self._bar_processor = bar_processor
        self._on_admin_notify = on_admin_notify
        self._processing_timeout_ms = processing_timeout_ms
        self._circuit_breaker_threshold = circuit_breaker_threshold
        self._is_running = False
        self._lock = asyncio.Lock()

        # Create per-symbol contexts
        self._contexts: dict[str, SymbolContext] = {}
        for symbol in self._symbols:
            circuit_breaker = CircuitBreaker(
                symbol=symbol,
                failure_threshold=circuit_breaker_threshold,
                on_admin_notify=on_admin_notify,
            )
            self._contexts[symbol] = SymbolContext(
                symbol=symbol,
                circuit_breaker=circuit_breaker,
            )

        logger.info(
            "multi_symbol_processor_initialized",
            symbols=self._symbols,
            max_concurrent=max_concurrent,
            processing_timeout_ms=processing_timeout_ms,
        )

    @property
    def is_running(self) -> bool:
        """Check if processor is running."""
        return self._is_running

    @property
    def symbols(self) -> list[str]:
        """Get list of monitored symbols."""
        return list(self._contexts.keys())

    async def start(self) -> None:
        """Start processing for all symbols."""
        if self._is_running:
            logger.warning("multi_symbol_processor_already_running")
            return

        self._is_running = True

        # Start per-symbol processor tasks
        async with self._lock:
            for symbol, context in self._contexts.items():
                context.processor_task = asyncio.create_task(
                    self._process_symbol_bars(context),
                    name=f"symbol_processor_{symbol}",
                )

        logger.info(
            "multi_symbol_processor_started",
            symbol_count=len(self._contexts),
        )

    async def stop(self) -> None:
        """Stop processing and clean up."""
        if not self._is_running:
            return

        self._is_running = False

        # Cancel all processor tasks
        async with self._lock:
            for context in self._contexts.values():
                if context.processor_task:
                    context.processor_task.cancel()
                    try:
                        await context.processor_task
                    except asyncio.CancelledError:
                        pass
                    context.processor_task = None

        logger.info(
            "multi_symbol_processor_stopped",
            symbols=list(self._contexts.keys()),
        )

    async def add_symbol(self, symbol: str) -> bool:
        """
        Add a new symbol to process.

        Args:
            symbol: Symbol ticker to add

        Returns:
            True if added, False if already exists or at capacity
        """
        async with self._lock:
            if symbol in self._contexts:
                logger.warning("symbol_already_exists", symbol=symbol)
                return False

            circuit_breaker = CircuitBreaker(
                symbol=symbol,
                failure_threshold=self._circuit_breaker_threshold,
                on_admin_notify=self._on_admin_notify,
            )
            context = SymbolContext(
                symbol=symbol,
                circuit_breaker=circuit_breaker,
            )
            self._contexts[symbol] = context

            if self._is_running:
                context.processor_task = asyncio.create_task(
                    self._process_symbol_bars(context),
                    name=f"symbol_processor_{symbol}",
                )

            logger.info("symbol_added", symbol=symbol)
            return True

    async def remove_symbol(self, symbol: str) -> bool:
        """
        Remove a symbol from processing.

        Args:
            symbol: Symbol ticker to remove

        Returns:
            True if removed, False if not found
        """
        async with self._lock:
            if symbol not in self._contexts:
                logger.warning("symbol_not_found", symbol=symbol)
                return False

            context = self._contexts[symbol]
            if context.processor_task:
                context.processor_task.cancel()
                try:
                    await context.processor_task
                except asyncio.CancelledError:
                    pass

            del self._contexts[symbol]
            logger.info("symbol_removed", symbol=symbol)
            return True

    def queue_bar(self, bar: OHLCVBar) -> bool:
        """
        Queue a bar for processing.

        Routes the bar to the correct symbol's queue.

        Args:
            bar: OHLCVBar to process

        Returns:
            True if queued, False if dropped (queue full or unknown symbol)
        """
        if not self._is_running:
            return False

        context = self._contexts.get(bar.symbol)
        if not context:
            logger.debug("bar_dropped_unknown_symbol", symbol=bar.symbol)
            return False

        if not context.enabled:
            logger.debug("bar_dropped_symbol_disabled", symbol=bar.symbol)
            return False

        try:
            context.queue.put_nowait(bar)
            return True
        except asyncio.QueueFull:
            logger.warning(
                "bar_dropped_queue_full",
                symbol=bar.symbol,
                queue_size=context.queue.qsize(),
            )
            return False

    async def _process_symbol_bars(self, context: SymbolContext) -> None:
        """
        Background task to process bars for a single symbol.

        Runs until stopped, processing bars from the symbol's queue.

        Args:
            context: SymbolContext for this symbol
        """
        symbol = context.symbol
        logger.info("symbol_processor_started", symbol=symbol)

        while self._is_running:
            try:
                # Wait for next bar with timeout
                try:
                    bar = await asyncio.wait_for(
                        context.queue.get(),
                        timeout=1.0,  # Check is_running every second
                    )
                except asyncio.TimeoutError:
                    continue

                # Check circuit breaker
                if not await context.circuit_breaker.can_execute():
                    logger.debug(
                        "bar_skipped_circuit_open",
                        symbol=symbol,
                        circuit_state=context.circuit_breaker.state.value,
                    )
                    continue

                # Process the bar with timing
                start_time = datetime.now(UTC)
                try:
                    await self._process_single_bar(bar, context)
                    await context.circuit_breaker.record_success()
                    context.metrics.last_error = None
                except Exception as e:
                    await context.circuit_breaker.record_failure(e)
                    context.metrics.last_error = str(e)
                    logger.error(
                        "bar_processing_failed",
                        symbol=symbol,
                        error=str(e),
                        exc_info=True,
                    )
                    continue

                # Track latency
                end_time = datetime.now(UTC)
                latency_ms = (end_time - start_time).total_seconds() * 1000
                context.metrics.latency_samples.append(latency_ms)
                context.metrics.total_latency_ms += latency_ms
                context.metrics.bars_processed += 1
                context.metrics.last_processed = end_time
                # Track last bar time for staleness (Story 19.26)
                context.metrics.last_bar_time = bar.timestamp

                # Log if latency exceeds target
                if latency_ms > self._processing_timeout_ms:
                    logger.warning(
                        "bar_processing_slow",
                        symbol=symbol,
                        latency_ms=latency_ms,
                        target_ms=self._processing_timeout_ms,
                    )
                else:
                    logger.debug(
                        "bar_processed",
                        symbol=symbol,
                        latency_ms=latency_ms,
                    )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(
                    "symbol_processor_error",
                    symbol=symbol,
                    error=str(e),
                    exc_info=True,
                )

        logger.info("symbol_processor_stopped", symbol=symbol)

    async def _process_single_bar(self, bar: OHLCVBar, context: SymbolContext) -> None:
        """
        Process a single bar.

        Args:
            bar: OHLCVBar to process
            context: SymbolContext for this symbol
        """
        if self._bar_processor:
            # Call the configured bar processor
            result = self._bar_processor(bar)
            # Handle async processors
            if asyncio.iscoroutine(result):
                await result
        else:
            # Default: just log the bar
            logger.debug(
                "bar_received",
                symbol=bar.symbol,
                close=str(bar.close),
                volume=bar.volume,
            )

    def get_symbol_status(self, symbol: str) -> SymbolStatus | None:
        """
        Get status for a specific symbol.

        Args:
            symbol: Symbol ticker

        Returns:
            SymbolStatus or None if symbol not found
        """
        context = self._contexts.get(symbol)
        if not context:
            return None

        return self._build_symbol_status(context)

    def _build_symbol_status(self, context: SymbolContext) -> SymbolStatus:
        """Build SymbolStatus from context."""
        cb = context.circuit_breaker
        metrics = context.metrics

        # Check staleness (Story 19.26)
        is_stale = metrics.is_stale()

        # Determine state
        if cb.state == CircuitState.OPEN:
            state = SymbolState.FAILED
        elif cb.state == CircuitState.HALF_OPEN:
            state = SymbolState.PAUSED
        elif not context.enabled:
            state = SymbolState.IDLE
        elif is_stale:
            state = SymbolState.STALE  # Story 19.26: Mark stale symbols
        else:
            state = SymbolState.PROCESSING

        # Map circuit state
        circuit_state_map = {
            CircuitState.CLOSED: CircuitStateEnum.CLOSED,
            CircuitState.OPEN: CircuitStateEnum.OPEN,
            CircuitState.HALF_OPEN: CircuitStateEnum.HALF_OPEN,
        }

        return SymbolStatus(
            symbol=context.symbol,
            state=state,
            last_processed=metrics.last_processed,
            consecutive_failures=cb.consecutive_failures,
            circuit_state=circuit_state_map[cb.state],
            avg_latency_ms=metrics.avg_latency_ms,
            bars_processed=metrics.bars_processed,
            last_error=metrics.last_error,
            # Staleness fields (Story 19.26)
            is_stale=is_stale,
            last_bar_time=metrics.last_bar_time,
            data_age_seconds=metrics.get_data_age_seconds(),
        )

    def get_status(self) -> ScannerStatusResponse:
        """
        Get overall scanner status.

        Returns:
            ScannerStatusResponse with all symbol statuses
        """
        symbol_statuses = [self._build_symbol_status(ctx) for ctx in self._contexts.values()]

        # Calculate aggregates
        total = len(symbol_statuses)
        healthy = sum(1 for s in symbol_statuses if s.state == SymbolState.PROCESSING)
        paused = sum(1 for s in symbol_statuses if s.state == SymbolState.PAUSED)
        failed = sum(1 for s in symbol_statuses if s.state == SymbolState.FAILED)
        stale = sum(1 for s in symbol_statuses if s.state == SymbolState.STALE)  # Story 19.26

        # Calculate overall average latency
        latencies = [s.avg_latency_ms for s in symbol_statuses if s.avg_latency_ms > 0]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0

        # Determine overall status
        if not self._is_running:
            overall_status = "unhealthy"
        elif failed > 0:
            overall_status = "degraded" if healthy > 0 else "unhealthy"
        elif paused > 0 or stale > 0:  # Story 19.26: Stale symbols degrade status
            overall_status = "degraded"
        else:
            overall_status = "healthy"

        # Update staleness metrics (Story 19.26)
        self._update_staleness_metrics(symbol_statuses)

        return ScannerStatusResponse(
            overall_status=overall_status,
            symbols=symbol_statuses,
            total_symbols=total,
            healthy_symbols=healthy,
            paused_symbols=paused,
            failed_symbols=failed,
            stale_count=stale,  # Story 19.26
            avg_latency_ms=avg_latency,
            is_running=self._is_running,
        )

    def _update_staleness_metrics(self, symbol_statuses: list[SymbolStatus]) -> None:
        """
        Update Prometheus metrics for staleness tracking (Story 19.26).

        Args:
            symbol_statuses: List of symbol statuses to update metrics for
        """
        stale_count = 0
        for status in symbol_statuses:
            # Update per-symbol staleness gauge
            stale_symbols_gauge.labels(symbol=status.symbol).set(1 if status.is_stale else 0)

            # Update per-symbol data age gauge
            if status.data_age_seconds is not None:
                symbol_data_age_seconds.labels(symbol=status.symbol).set(status.data_age_seconds)

            if status.is_stale:
                stale_count += 1

        # Update total stale count gauge
        stale_symbols_total.set(stale_count)

    async def reset_circuit_breaker(self, symbol: str) -> bool:
        """
        Reset circuit breaker for a symbol.

        Args:
            symbol: Symbol ticker

        Returns:
            True if reset, False if symbol not found
        """
        context = self._contexts.get(symbol)
        if not context:
            return False

        await context.circuit_breaker.reset()
        context.metrics.last_error = None
        logger.info("circuit_breaker_reset", symbol=symbol)
        return True


# Global processor instance
_processor: MultiSymbolProcessor | None = None


def get_multi_symbol_processor() -> MultiSymbolProcessor | None:
    """
    Get the global multi-symbol processor instance.

    Returns:
        MultiSymbolProcessor instance or None if not initialized
    """
    return _processor


def init_multi_symbol_processor(
    symbols: list[str],
    bar_processor: Callable[[OHLCVBar], None] | None = None,
    on_admin_notify: Callable[[str, str], None] | None = None,
    **kwargs,
) -> MultiSymbolProcessor:
    """
    Initialize the global multi-symbol processor.

    Args:
        symbols: List of symbol tickers to process
        bar_processor: Async callable to process each bar
        on_admin_notify: Callback for admin notifications
        **kwargs: Additional configuration options

    Returns:
        MultiSymbolProcessor instance
    """
    global _processor
    _processor = MultiSymbolProcessor(
        symbols=symbols,
        bar_processor=bar_processor,
        on_admin_notify=on_admin_notify,
        **kwargs,
    )
    return _processor
