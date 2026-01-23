"""
Real-time pattern scanner service for processing incoming OHLCV bars.

This module implements the RealtimePatternScanner service that processes bars
from the Alpaca market data feed in real-time, enabling pattern detection
on live data. Story 19.1.
"""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING

import structlog

from src.models.ohlcv import OHLCVBar

if TYPE_CHECKING:
    from src.market_data.service import MarketDataCoordinator

logger = structlog.get_logger(__name__)


# Configuration constants
SCANNER_PROCESSING_TIMEOUT_MS = 100
SCANNER_QUEUE_MAX_SIZE = 1000
CIRCUIT_BREAKER_THRESHOLD = 5  # Failures before circuit opens
CIRCUIT_BREAKER_RESET_SECONDS = 30  # Time before circuit resets


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject new requests
    HALF_OPEN = "half_open"  # Testing if recovered


@dataclass
class ScannerHealth:
    """Health status of the real-time pattern scanner."""

    status: str  # "healthy", "degraded", "unhealthy"
    queue_depth: int
    last_processed: datetime | None
    avg_latency_ms: float
    bars_processed: int
    bars_dropped: int
    circuit_state: str
    is_running: bool


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
        queue_max_size: int = SCANNER_QUEUE_MAX_SIZE,
        processing_timeout_ms: int = SCANNER_PROCESSING_TIMEOUT_MS,
    ):
        """
        Initialize the real-time pattern scanner.

        Args:
            queue_max_size: Maximum bars to queue (default 1000)
            processing_timeout_ms: Target processing time per bar (default 100ms)
        """
        self._queue_max_size = queue_max_size
        self._processing_timeout_ms = processing_timeout_ms

        # Queue for bar buffering
        self._bar_queue: asyncio.Queue[OHLCVBar] = asyncio.Queue(maxsize=queue_max_size)

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
            queue_max_size=queue_max_size,
            processing_timeout_ms=processing_timeout_ms,
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

        # Clear queue
        while not self._bar_queue.empty():
            try:
                self._bar_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

        logger.info(
            "realtime_scanner_stopped",
            bars_processed=self._metrics.bars_processed,
            bars_dropped=self._metrics.bars_dropped,
        )

    def _on_bar_received(self, bar: OHLCVBar) -> None:
        """
        Callback invoked when a bar is received from the coordinator.

        Queues the bar for processing with backpressure handling.

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

        # Try to queue the bar
        try:
            self._bar_queue.put_nowait(bar)
            logger.debug(
                "bar_queued",
                symbol=bar.symbol,
                queue_depth=self._bar_queue.qsize(),
            )
        except asyncio.QueueFull:
            # Backpressure: queue is full, drop incoming bar (newest)
            self._metrics.bars_dropped += 1
            logger.warning(
                "bar_dropped_queue_full",
                symbol=bar.symbol,
                queue_depth=self._bar_queue.qsize(),
            )

    async def _process_bars(self) -> None:
        """
        Background task to process bars from the queue.

        Processes bars FIFO with latency tracking and circuit breaker.
        """
        while self._is_running:
            try:
                # Wait for next bar with timeout
                try:
                    bar = await asyncio.wait_for(
                        self._bar_queue.get(),
                        timeout=1.0,  # Check is_running every second
                    )
                except asyncio.TimeoutError:
                    continue

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
                        symbol=bar.symbol,
                        latency_ms=latency_ms,
                        target_ms=self._processing_timeout_ms,
                    )
                else:
                    logger.debug(
                        "bar_processed",
                        symbol=bar.symbol,
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

        For Story 19.1, this is a placeholder that logs the bar.
        Pattern detection will be added in subsequent stories.

        Args:
            bar: OHLCVBar to process
        """
        # Log bar reception with timestamp for latency tracking
        receive_time = datetime.now(UTC)
        bar_age_ms = (receive_time - bar.timestamp).total_seconds() * 1000

        logger.info(
            "realtime_bar_processing",
            symbol=bar.symbol,
            timestamp=bar.timestamp.isoformat(),
            bar_age_ms=bar_age_ms,
            close=str(bar.close),
            volume=bar.volume,
        )

        # TODO: Story 19.2+ will add pattern detection here
        # For now, we just validate the bar was received and processed

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
        if self._consecutive_failures >= CIRCUIT_BREAKER_THRESHOLD:
            if self._circuit_state != CircuitState.OPEN:
                self._circuit_state = CircuitState.OPEN
                self._circuit_opened_at = datetime.now(UTC)
                logger.warning(
                    "circuit_breaker_opened",
                    consecutive_failures=self._consecutive_failures,
                    threshold=CIRCUIT_BREAKER_THRESHOLD,
                )

    def _check_circuit_reset(self) -> None:
        """Check if circuit breaker should reset to half-open state."""
        if self._circuit_state != CircuitState.OPEN:
            return

        if self._circuit_opened_at is None:
            return

        elapsed = (datetime.now(UTC) - self._circuit_opened_at).total_seconds()
        if elapsed >= CIRCUIT_BREAKER_RESET_SECONDS:
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
        status = "healthy"
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
    queue_max_size: int = SCANNER_QUEUE_MAX_SIZE,
    processing_timeout_ms: int = SCANNER_PROCESSING_TIMEOUT_MS,
) -> RealtimePatternScanner:
    """
    Initialize the global scanner instance.

    Args:
        queue_max_size: Maximum bars to queue
        processing_timeout_ms: Target processing time per bar

    Returns:
        RealtimePatternScanner instance
    """
    global _scanner
    _scanner = RealtimePatternScanner(
        queue_max_size=queue_max_size,
        processing_timeout_ms=processing_timeout_ms,
    )
    return _scanner
