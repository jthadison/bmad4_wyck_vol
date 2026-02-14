"""
Real-time pattern scanner service for processing incoming OHLCV bars.

This module implements the RealtimePatternScanner service that processes bars
from the Alpaca market data feed in real-time, enabling pattern detection
on live data. Story 19.1.

Story 19.23: Added symbol priority tiers for priority-based bar processing.
High-priority symbols are processed before medium and low during congestion.

Story 19.2-19.3: Integrated BarWindowManager and RealtimePatternDetector for
real-time pattern detection on incoming bars.
"""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Literal

import structlog
from pydantic import BaseModel, Field

from src.config import settings
from src.models.ohlcv import OHLCVBar
from src.pattern_engine.priority_queue import (
    Priority,
    PriorityBarQueue,
    QueueEmpty,
    SymbolPriorityManager,
)

if TYPE_CHECKING:
    from src.market_data.service import MarketDataCoordinator
    from src.pattern_engine.bar_window_manager import BarWindowManager
    from src.pattern_engine.realtime_detector import RealtimePatternDetector

logger = structlog.get_logger(__name__)


# Configuration defaults (overridden by settings if available)
def _get_queue_max_size() -> int:
    """Get queue max size from settings."""
    return settings.scanner_queue_max_size


def _get_processing_timeout_ms() -> int:
    """Get processing timeout from settings."""
    return settings.scanner_processing_timeout_ms


def _get_circuit_breaker_threshold() -> int:
    """Get circuit breaker threshold from settings."""
    return settings.scanner_circuit_breaker_threshold


def _get_circuit_breaker_reset_seconds() -> int:
    """Get circuit breaker reset time from settings."""
    return settings.scanner_circuit_breaker_reset_seconds


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject new requests
    HALF_OPEN = "half_open"  # Testing if recovered


class ScannerHealth(BaseModel):
    """Health status of the real-time pattern scanner."""

    status: Literal["healthy", "degraded", "unhealthy"] = Field(description="Overall health status")
    queue_depth: int = Field(ge=0, description="Number of bars in processing queue")
    last_processed: datetime | None = Field(description="Timestamp of last processed bar")
    avg_latency_ms: float = Field(ge=0, description="Average processing latency in ms")
    bars_processed: int = Field(ge=0, description="Total bars processed since startup")
    bars_dropped: int = Field(ge=0, description="Total bars dropped due to backpressure")
    circuit_state: Literal["closed", "open", "half_open"] = Field(
        description="Circuit breaker state"
    )
    is_running: bool = Field(description="Whether scanner is currently running")


class ScannerHealthResponse(BaseModel):
    """API response model for scanner health endpoint."""

    status: Literal["healthy", "degraded", "unhealthy", "not_configured"] = Field(
        description="Overall health status"
    )
    queue_depth: int | None = Field(
        default=None, ge=0, description="Number of bars in processing queue"
    )
    last_processed: str | None = Field(
        default=None, description="ISO timestamp of last processed bar"
    )
    avg_latency_ms: float | None = Field(
        default=None, ge=0, description="Average processing latency in ms"
    )
    bars_processed: int | None = Field(
        default=None, ge=0, description="Total bars processed since startup"
    )
    bars_dropped: int | None = Field(
        default=None, ge=0, description="Total bars dropped due to backpressure"
    )
    circuit_state: str | None = Field(default=None, description="Circuit breaker state")
    is_running: bool | None = Field(
        default=None, description="Whether scanner is currently running"
    )
    message: str | None = Field(default=None, description="Additional status message")


@dataclass
class ProcessingMetrics:
    """Metrics for tracking processing performance."""

    bars_processed: int = 0
    bars_dropped: int = 0
    total_latency_ms: float = 0.0
    latency_samples: deque[float] = field(default_factory=lambda: deque(maxlen=100))
    last_processed: datetime | None = None
    processing_errors: int = 0

    @property
    def avg_latency_ms(self) -> float:
        """Calculate average latency from recent samples."""
        if not self.latency_samples:
            return 0.0
        return sum(self.latency_samples) / len(self.latency_samples)


class RealtimePatternScanner:
    """
    Real-time pattern scanner service.

    Processes incoming OHLCV bars from the market data feed with:
    - Asyncio queue for backpressure handling
    - Circuit breaker for downstream failures
    - Latency tracking and metrics
    - Health check endpoint support

    Usage:
        scanner = RealtimePatternScanner()
        await scanner.start(coordinator)
        # Scanner now processes bars automatically
        health = scanner.get_health()
        await scanner.stop()
    """

    def __init__(
        self,
        queue_max_size: int | None = None,
        processing_timeout_ms: int | None = None,
        window_manager: BarWindowManager | None = None,
        pattern_detector: RealtimePatternDetector | None = None,
    ):
        """
        Initialize the real-time pattern scanner.

        Args:
            queue_max_size: Maximum bars to queue (defaults from settings)
            processing_timeout_ms: Target processing time per bar (defaults from settings)
            window_manager: BarWindowManager for rolling window data (Story 19.2)
            pattern_detector: RealtimePatternDetector for pattern detection (Story 19.3)
        """
        self._queue_max_size = (
            queue_max_size if queue_max_size is not None else _get_queue_max_size()
        )
        self._processing_timeout_ms = (
            processing_timeout_ms
            if processing_timeout_ms is not None
            else _get_processing_timeout_ms()
        )

        # Pattern detection components (Story 19.2-19.3)
        self._window_manager = window_manager
        self._pattern_detector = pattern_detector

        # Priority queue for bar buffering (Story 19.23)
        # Uses priority-based ordering: HIGH > MEDIUM > LOW
        self._bar_queue = PriorityBarQueue(maxsize=self._queue_max_size)

        # Symbol priority manager (Story 19.23)
        self._priority_manager = SymbolPriorityManager()

        # State
        self._is_running = False
        self._processor_task: asyncio.Task | None = None
        self._coordinator: MarketDataCoordinator | None = None

        # Metrics
        self._metrics = ProcessingMetrics()

        # Circuit breaker
        self._circuit_state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._circuit_opened_at: datetime | None = None

        logger.info(
            "realtime_scanner_initialized",
            queue_max_size=self._queue_max_size,
            processing_timeout_ms=self._processing_timeout_ms,
            has_window_manager=window_manager is not None,
            has_pattern_detector=pattern_detector is not None,
        )

    @property
    def is_running(self) -> bool:
        """Check if scanner is running."""
        return self._is_running

    @property
    def queue_depth(self) -> int:
        """Get current queue depth."""
        return self._bar_queue.qsize()

    async def start(self, coordinator: MarketDataCoordinator) -> None:
        """
        Start the scanner and subscribe to bar events.

        Args:
            coordinator: MarketDataCoordinator to subscribe to
        """
        if self._is_running:
            logger.warning("scanner_already_running")
            return

        self._coordinator = coordinator
        self._is_running = True

        # Start processing task
        self._processor_task = asyncio.create_task(self._process_bars())

        # Register callback with coordinator
        # The coordinator calls _on_bar_received for each incoming bar
        coordinator.adapter.on_bar_received(self._on_bar_received)

        logger.info(
            "realtime_scanner_started",
            queue_max_size=self._queue_max_size,
        )

    async def stop(self) -> None:
        """Stop the scanner gracefully."""
        if not self._is_running:
            return

        self._is_running = False

        # Unregister callback from coordinator
        if self._coordinator:
            self._coordinator.adapter.remove_bar_callback(self._on_bar_received)

        # Cancel processor task
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
            self._processor_task = None

        # Clear priority queue (Story 19.23)
        cleared = await self._bar_queue.clear()

        logger.info(
            "realtime_scanner_stopped",
            bars_processed=self._metrics.bars_processed,
            bars_dropped=self._metrics.bars_dropped,
            queue_cleared=cleared,
        )

    # =========================================================================
    # Symbol Priority Management (Story 19.23)
    # =========================================================================

    async def set_symbol_priority(self, symbol: str, priority: Priority) -> None:
        """
        Set processing priority for a symbol.

        Args:
            symbol: Symbol identifier
            priority: Priority level (HIGH, MEDIUM, LOW)
        """
        await self._priority_manager.set_priority(symbol, priority)
        logger.info(
            "symbol_priority_set",
            symbol=symbol,
            priority=priority.name,
        )

    async def get_symbol_priority(self, symbol: str) -> Priority:
        """
        Get processing priority for a symbol.

        Args:
            symbol: Symbol identifier

        Returns:
            Priority level (MEDIUM if not explicitly set)
        """
        return await self._priority_manager.get_priority(symbol)

    async def set_symbol_priorities(self, priorities: dict[str, Priority]) -> None:
        """
        Bulk set priorities for multiple symbols.

        Args:
            priorities: Mapping of symbol to priority
        """
        await self._priority_manager.set_priorities(priorities)
        logger.info(
            "symbol_priorities_bulk_set",
            count=len(priorities),
        )

    async def clear_symbol_priorities(self) -> None:
        """Clear all symbol priority settings (revert to MEDIUM)."""
        await self._priority_manager.clear()
        logger.info("symbol_priorities_cleared")

    def _on_bar_received(self, bar: OHLCVBar) -> None:
        """
        Callback invoked when a bar is received from the coordinator.

        Queues the bar for processing with backpressure handling.
        Uses symbol priority for queue ordering (Story 19.23).

        Note: This is intentionally a synchronous method despite being called from
        an async WebSocket context. It uses put_nowait() for non-blocking queue
        insertion, making async unnecessary and avoiding event loop overhead.

        Args:
            bar: OHLCVBar from market data feed
        """
        if not self._is_running:
            return

        # Check circuit breaker
        if self._circuit_state == CircuitState.OPEN:
            self._check_circuit_reset()
            if self._circuit_state == CircuitState.OPEN:
                self._metrics.bars_dropped += 1
                logger.debug(
                    "bar_dropped_circuit_open",
                    symbol=bar.symbol,
                )
                return

        # Get symbol priority (Story 19.23)
        priority = self._priority_manager.get_priority_sync(bar.symbol)

        # Try to queue the bar with priority
        success = self._bar_queue.put_nowait(bar.symbol, bar, priority)
        if success:
            logger.debug(
                "bar_queued",
                symbol=bar.symbol,
                priority=priority.name,
                queue_depth=self._bar_queue.qsize(),
            )
        else:
            # Backpressure: queue is full, drop incoming bar (newest)
            self._metrics.bars_dropped += 1
            logger.warning(
                "bar_dropped_queue_full",
                symbol=bar.symbol,
                priority=priority.name,
                queue_depth=self._bar_queue.qsize(),
            )

    async def _process_bars(self) -> None:
        """
        Background task to process bars from the queue.

        Processes bars in priority order (HIGH > MEDIUM > LOW) with
        latency tracking and circuit breaker. Story 19.23.
        """
        while self._is_running:
            try:
                # Wait for next bar with timeout (priority-ordered)
                try:
                    prioritized_bar = await self._bar_queue.get(timeout=1.0)
                except QueueEmpty:
                    continue

                bar = prioritized_bar.bar
                symbol = prioritized_bar.symbol

                # Process the bar
                start_time = datetime.now(UTC)
                await self._process_single_bar(bar)
                end_time = datetime.now(UTC)

                # Track latency
                latency_ms = (end_time - start_time).total_seconds() * 1000
                self._metrics.latency_samples.append(latency_ms)
                self._metrics.total_latency_ms += latency_ms
                self._metrics.bars_processed += 1
                self._metrics.last_processed = end_time

                # Log if latency exceeds target
                if latency_ms > self._processing_timeout_ms:
                    logger.warning(
                        "bar_processing_slow",
                        symbol=symbol,
                        priority=Priority(prioritized_bar.priority).name,
                        latency_ms=latency_ms,
                        target_ms=self._processing_timeout_ms,
                    )
                else:
                    logger.debug(
                        "bar_processed",
                        symbol=symbol,
                        priority=Priority(prioritized_bar.priority).name,
                        latency_ms=latency_ms,
                    )

                # Reset consecutive failures on any successful processing
                self._consecutive_failures = 0

                # Transition circuit breaker from half-open to closed on success
                if self._circuit_state == CircuitState.HALF_OPEN:
                    self._circuit_state = CircuitState.CLOSED
                    logger.info("circuit_breaker_closed")

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._handle_processing_error(e)

    async def _process_single_bar(self, bar: OHLCVBar) -> None:
        """
        Process a single bar through pattern detection.

        Story 19.2-19.3: Adds bar to rolling window and runs pattern detection
        using the same detectors as the backtesting engine.

        Args:
            bar: OHLCVBar to process
        """
        # Log bar reception with timestamp for latency tracking
        receive_time = datetime.now(UTC)
        bar_age_ms = (receive_time - bar.timestamp).total_seconds() * 1000

        logger.debug(
            "realtime_bar_processing",
            symbol=bar.symbol,
            timestamp=bar.timestamp.isoformat(),
            bar_age_ms=bar_age_ms,
            close=str(bar.close),
            volume=bar.volume,
        )

        # Story 19.2: Add bar to rolling window
        if self._window_manager is not None:
            await self._window_manager.add_bar(bar.symbol, bar)

        # Story 19.3: Run pattern detection if detector is configured
        if self._pattern_detector is not None and self._window_manager is not None:
            from src.pattern_engine.bar_window_manager import WindowState

            # Only detect patterns when window is ready (200 bars)
            if self._window_manager.get_state(bar.symbol) == WindowState.READY:
                events = await self._pattern_detector.process_bar(bar)
                if events:
                    logger.info(
                        "patterns_detected",
                        symbol=bar.symbol,
                        pattern_count=len(events),
                        patterns=[e.pattern_type.value for e in events],
                    )

    def _handle_processing_error(self, error: Exception) -> None:
        """
        Handle processing errors with circuit breaker logic.

        Args:
            error: Exception that occurred during processing
        """
        self._consecutive_failures += 1
        self._metrics.processing_errors += 1

        logger.error(
            "bar_processing_error",
            error=str(error),
            consecutive_failures=self._consecutive_failures,
        )

        # Open circuit if threshold exceeded
        threshold = _get_circuit_breaker_threshold()
        if self._consecutive_failures >= threshold:
            if self._circuit_state != CircuitState.OPEN:
                self._circuit_state = CircuitState.OPEN
                self._circuit_opened_at = datetime.now(UTC)
                logger.warning(
                    "circuit_breaker_opened",
                    consecutive_failures=self._consecutive_failures,
                    threshold=threshold,
                )

    def _check_circuit_reset(self) -> None:
        """Check if circuit breaker should reset to half-open state."""
        if self._circuit_state != CircuitState.OPEN:
            return

        if self._circuit_opened_at is None:
            return

        elapsed = (datetime.now(UTC) - self._circuit_opened_at).total_seconds()
        if elapsed >= _get_circuit_breaker_reset_seconds():
            self._circuit_state = CircuitState.HALF_OPEN
            logger.info(
                "circuit_breaker_half_open",
                elapsed_seconds=elapsed,
            )

    def get_health(self) -> ScannerHealth:
        """
        Get health status of the scanner.

        Returns:
            ScannerHealth with current metrics
        """
        # Determine health status
        status: Literal["healthy", "degraded", "unhealthy"] = "healthy"
        if not self._is_running:
            status = "unhealthy"
        elif self._circuit_state == CircuitState.OPEN:
            status = "unhealthy"
        elif self._circuit_state == CircuitState.HALF_OPEN:
            status = "degraded"
        elif self._bar_queue.qsize() > self._queue_max_size * 0.8:
            status = "degraded"

        return ScannerHealth(
            status=status,
            queue_depth=self._bar_queue.qsize(),
            last_processed=self._metrics.last_processed,
            avg_latency_ms=self._metrics.avg_latency_ms,
            bars_processed=self._metrics.bars_processed,
            bars_dropped=self._metrics.bars_dropped,
            circuit_state=self._circuit_state.value,
            is_running=self._is_running,
        )


# Global scanner instance
_scanner: RealtimePatternScanner | None = None


def get_scanner() -> RealtimePatternScanner:
    """
    Get the global scanner instance.

    Returns:
        RealtimePatternScanner instance

    Raises:
        RuntimeError: If scanner not initialized
    """
    global _scanner
    if _scanner is None:
        raise RuntimeError("Scanner not initialized. Call init_scanner() first.")
    return _scanner


def init_scanner(
    queue_max_size: int | None = None,
    processing_timeout_ms: int | None = None,
    window_manager: BarWindowManager | None = None,
    pattern_detector: RealtimePatternDetector | None = None,
) -> RealtimePatternScanner:
    """
    Initialize the global scanner instance.

    Args:
        queue_max_size: Maximum bars to queue (defaults from settings)
        processing_timeout_ms: Target processing time per bar (defaults from settings)
        window_manager: BarWindowManager for rolling window data (Story 19.2)
        pattern_detector: RealtimePatternDetector for pattern detection (Story 19.3)

    Returns:
        RealtimePatternScanner instance
    """
    global _scanner
    _scanner = RealtimePatternScanner(
        queue_max_size=queue_max_size,
        processing_timeout_ms=processing_timeout_ms,
        window_manager=window_manager,
        pattern_detector=pattern_detector,
    )
    return _scanner
