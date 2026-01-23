"""
Unit tests for RealtimePatternScanner service.

Story 19.1: Real-Time Bar Processing Pipeline
Tests cover:
- Service startup/shutdown
- Bar queuing and backpressure handling
- Latency tracking and metrics
- Circuit breaker behavior
- Health check endpoint
"""

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from src.models.ohlcv import OHLCVBar
from src.pattern_engine.realtime_scanner import (
    CircuitState,
    ProcessingMetrics,
    RealtimePatternScanner,
    _get_circuit_breaker_threshold,
    _get_processing_timeout_ms,
    _get_queue_max_size,
    get_scanner,
    init_scanner,
)

# =============================
# Fixtures
# =============================


@pytest.fixture
def sample_ohlcv_bar() -> OHLCVBar:
    """Create a sample OHLCVBar for testing."""
    return OHLCVBar(
        symbol="AAPL",
        timeframe="1m",
        timestamp=datetime.now(UTC),
        open=Decimal("150.00"),
        high=Decimal("151.00"),
        low=Decimal("149.50"),
        close=Decimal("150.50"),
        volume=100000,
        spread=Decimal("1.50"),
        spread_ratio=Decimal("1.0"),
        volume_ratio=Decimal("1.0"),
    )


@pytest.fixture
def mock_coordinator():
    """Create a mock MarketDataCoordinator."""
    coordinator = MagicMock()
    coordinator.adapter = MagicMock()
    coordinator.adapter.on_bar_received = MagicMock()
    coordinator.adapter.remove_bar_callback = MagicMock()
    return coordinator


@pytest.fixture
def scanner():
    """Create a RealtimePatternScanner instance for testing."""
    return RealtimePatternScanner(
        queue_max_size=100,
        processing_timeout_ms=100,
    )


# =============================
# Initialization Tests
# =============================


class TestRealtimePatternScannerInit:
    """Tests for scanner initialization."""

    def test_init_with_defaults(self):
        """Scanner initializes with default configuration from settings."""
        scanner = RealtimePatternScanner()

        assert scanner._queue_max_size == _get_queue_max_size()
        assert scanner._processing_timeout_ms == _get_processing_timeout_ms()
        assert scanner._is_running is False
        assert scanner._circuit_state == CircuitState.CLOSED
        assert scanner.queue_depth == 0

    def test_init_with_custom_config(self):
        """Scanner initializes with custom configuration."""
        scanner = RealtimePatternScanner(
            queue_max_size=500,
            processing_timeout_ms=50,
        )

        assert scanner._queue_max_size == 500
        assert scanner._processing_timeout_ms == 50

    def test_init_metrics(self):
        """Scanner initializes with zero metrics."""
        scanner = RealtimePatternScanner()
        metrics = scanner._metrics

        assert metrics.bars_processed == 0
        assert metrics.bars_dropped == 0
        assert metrics.total_latency_ms == 0.0
        assert metrics.last_processed is None
        assert metrics.processing_errors == 0


# =============================
# Startup/Shutdown Tests
# =============================


class TestScannerLifecycle:
    """Tests for scanner startup and shutdown."""

    @pytest.mark.asyncio
    async def test_start_registers_callback(self, scanner, mock_coordinator):
        """Start registers callback with coordinator adapter."""
        await scanner.start(mock_coordinator)

        mock_coordinator.adapter.on_bar_received.assert_called_once()
        assert scanner.is_running is True
        assert scanner._coordinator is mock_coordinator

        await scanner.stop()

    @pytest.mark.asyncio
    async def test_start_creates_processor_task(self, scanner, mock_coordinator):
        """Start creates background processor task."""
        await scanner.start(mock_coordinator)

        assert scanner._processor_task is not None
        assert not scanner._processor_task.done()

        await scanner.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_processor_task(self, scanner, mock_coordinator):
        """Stop cancels the processor task."""
        await scanner.start(mock_coordinator)
        task = scanner._processor_task

        await scanner.stop()

        assert scanner.is_running is False
        assert task.cancelled() or task.done()

    @pytest.mark.asyncio
    async def test_stop_clears_queue(self, scanner, mock_coordinator, sample_ohlcv_bar):
        """Stop clears any queued bars."""
        await scanner.start(mock_coordinator)

        # Queue some bars
        scanner._on_bar_received(sample_ohlcv_bar)
        scanner._on_bar_received(sample_ohlcv_bar)

        await scanner.stop()

        assert scanner.queue_depth == 0

    @pytest.mark.asyncio
    async def test_start_idempotent(self, scanner, mock_coordinator):
        """Starting an already running scanner is idempotent."""
        await scanner.start(mock_coordinator)
        await scanner.start(mock_coordinator)  # Should not raise

        # Should only register callback once
        assert mock_coordinator.adapter.on_bar_received.call_count == 1

        await scanner.stop()

    @pytest.mark.asyncio
    async def test_stop_idempotent(self, scanner, mock_coordinator):
        """Stopping a non-running scanner is idempotent."""
        await scanner.stop()  # Should not raise

        await scanner.start(mock_coordinator)
        await scanner.stop()

    @pytest.mark.asyncio
    async def test_stop_unregisters_callback(self, scanner, mock_coordinator):
        """Stop unregisters the bar callback from the coordinator."""
        await scanner.start(mock_coordinator)
        await scanner.stop()

        mock_coordinator.adapter.remove_bar_callback.assert_called_once_with(
            scanner._on_bar_received
        )


# =============================
# Bar Processing Tests
# =============================


class TestBarProcessing:
    """Tests for bar queuing and processing."""

    @pytest.mark.asyncio
    async def test_bar_queued_on_receive(self, scanner, mock_coordinator, sample_ohlcv_bar):
        """Received bar is added to queue."""
        await scanner.start(mock_coordinator)

        scanner._on_bar_received(sample_ohlcv_bar)

        assert scanner.queue_depth == 1

        await scanner.stop()

    @pytest.mark.asyncio
    async def test_bar_processed_from_queue(self, scanner, mock_coordinator, sample_ohlcv_bar):
        """Bar is processed from queue and metrics updated."""
        await scanner.start(mock_coordinator)

        scanner._on_bar_received(sample_ohlcv_bar)

        # Wait for processing
        await asyncio.sleep(0.2)

        assert scanner._metrics.bars_processed >= 1
        assert scanner._metrics.last_processed is not None

        await scanner.stop()

    @pytest.mark.asyncio
    async def test_bars_processed_fifo(self, scanner, mock_coordinator):
        """Bars are processed in FIFO order."""
        await scanner.start(mock_coordinator)

        processed_symbols = []

        # Patch _process_single_bar to track processing order
        original_process = scanner._process_single_bar

        async def track_process(bar):
            processed_symbols.append(bar.symbol)
            await original_process(bar)

        scanner._process_single_bar = track_process

        # Queue bars with different symbols
        for symbol in ["AAPL", "TSLA", "GOOGL"]:
            bar = OHLCVBar(
                symbol=symbol,
                timeframe="1m",
                timestamp=datetime.now(UTC),
                open=Decimal("100.00"),
                high=Decimal("101.00"),
                low=Decimal("99.00"),
                close=Decimal("100.50"),
                volume=10000,
                spread=Decimal("2.00"),
                spread_ratio=Decimal("1.0"),
                volume_ratio=Decimal("1.0"),
            )
            scanner._on_bar_received(bar)

        # Wait for processing
        await asyncio.sleep(0.5)

        assert processed_symbols == ["AAPL", "TSLA", "GOOGL"]

        await scanner.stop()

    @pytest.mark.asyncio
    async def test_latency_tracked(self, scanner, mock_coordinator, sample_ohlcv_bar):
        """Processing latency is tracked in metrics."""
        await scanner.start(mock_coordinator)

        scanner._on_bar_received(sample_ohlcv_bar)

        # Wait for processing
        await asyncio.sleep(0.2)

        assert len(scanner._metrics.latency_samples) >= 1
        assert scanner._metrics.avg_latency_ms >= 0

        await scanner.stop()

    def test_bar_not_queued_when_not_running(self, scanner, sample_ohlcv_bar):
        """Bar is not queued when scanner is not running."""
        scanner._on_bar_received(sample_ohlcv_bar)

        assert scanner.queue_depth == 0


# =============================
# Backpressure Tests
# =============================


class TestBackpressure:
    """Tests for backpressure handling."""

    @pytest.mark.asyncio
    async def test_queue_full_drops_bar(self, mock_coordinator, sample_ohlcv_bar):
        """When queue is full, new bars are dropped."""
        scanner = RealtimePatternScanner(queue_max_size=2)
        await scanner.start(mock_coordinator)

        # Pause processing
        scanner._is_running = True
        old_task = scanner._processor_task
        scanner._processor_task = None

        # Fill queue
        scanner._on_bar_received(sample_ohlcv_bar)
        scanner._on_bar_received(sample_ohlcv_bar)
        scanner._on_bar_received(sample_ohlcv_bar)  # Should be dropped

        assert scanner.queue_depth == 2
        assert scanner._metrics.bars_dropped == 1

        # Restore processor
        scanner._processor_task = old_task
        await scanner.stop()

    @pytest.mark.asyncio
    async def test_dropped_bars_counted(self, mock_coordinator, sample_ohlcv_bar):
        """Dropped bars are counted in metrics."""
        scanner = RealtimePatternScanner(queue_max_size=1)
        await scanner.start(mock_coordinator)

        # Pause processing
        old_task = scanner._processor_task
        scanner._processor_task = None

        # Overflow queue
        for _ in range(5):
            scanner._on_bar_received(sample_ohlcv_bar)

        assert scanner._metrics.bars_dropped == 4

        # Restore processor
        scanner._processor_task = old_task
        await scanner.stop()


# =============================
# Circuit Breaker Tests
# =============================


class TestCircuitBreaker:
    """Tests for circuit breaker behavior."""

    def test_circuit_starts_closed(self, scanner):
        """Circuit breaker starts in closed state."""
        assert scanner._circuit_state == CircuitState.CLOSED

    def test_circuit_opens_on_threshold(self, scanner):
        """Circuit opens after threshold failures."""
        for _ in range(_get_circuit_breaker_threshold()):
            scanner._handle_processing_error(Exception("Test error"))

        assert scanner._circuit_state == CircuitState.OPEN
        assert scanner._circuit_opened_at is not None

    def test_circuit_open_drops_bars(self, scanner, sample_ohlcv_bar):
        """Open circuit drops incoming bars."""
        scanner._is_running = True
        scanner._circuit_state = CircuitState.OPEN
        scanner._circuit_opened_at = datetime.now(UTC)

        scanner._on_bar_received(sample_ohlcv_bar)

        assert scanner.queue_depth == 0
        assert scanner._metrics.bars_dropped == 1

    def test_circuit_resets_to_half_open(self, scanner):
        """Circuit resets to half-open after timeout."""
        scanner._circuit_state = CircuitState.OPEN
        # Set opened time in the past
        scanner._circuit_opened_at = datetime(2020, 1, 1, tzinfo=UTC)

        scanner._check_circuit_reset()

        assert scanner._circuit_state == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_circuit_closes_on_success(self, scanner, mock_coordinator, sample_ohlcv_bar):
        """Circuit closes on successful processing in half-open state."""
        await scanner.start(mock_coordinator)

        scanner._circuit_state = CircuitState.HALF_OPEN
        scanner._on_bar_received(sample_ohlcv_bar)

        # Wait for processing
        await asyncio.sleep(0.2)

        assert scanner._circuit_state == CircuitState.CLOSED
        assert scanner._consecutive_failures == 0

        await scanner.stop()

    @pytest.mark.asyncio
    async def test_consecutive_failures_reset_on_any_success(
        self, scanner, mock_coordinator, sample_ohlcv_bar
    ):
        """Consecutive failures counter resets on any successful processing."""
        await scanner.start(mock_coordinator)

        # Simulate some failures (but not enough to trip circuit)
        scanner._consecutive_failures = 4  # One less than threshold

        # Process a bar successfully
        scanner._on_bar_received(sample_ohlcv_bar)
        await asyncio.sleep(0.2)

        # Consecutive failures should be reset
        assert scanner._consecutive_failures == 0
        assert scanner._circuit_state == CircuitState.CLOSED

        await scanner.stop()


# =============================
# Health Check Tests
# =============================


class TestHealthCheck:
    """Tests for health check functionality."""

    def test_health_healthy_when_running(self, scanner):
        """Health status is healthy when running normally."""
        scanner._is_running = True
        scanner._circuit_state = CircuitState.CLOSED

        health = scanner.get_health()

        assert health.status == "healthy"
        assert health.is_running is True

    def test_health_unhealthy_when_not_running(self, scanner):
        """Health status is unhealthy when not running."""
        scanner._is_running = False

        health = scanner.get_health()

        assert health.status == "unhealthy"
        assert health.is_running is False

    def test_health_unhealthy_when_circuit_open(self, scanner):
        """Health status is unhealthy when circuit is open."""
        scanner._is_running = True
        scanner._circuit_state = CircuitState.OPEN

        health = scanner.get_health()

        assert health.status == "unhealthy"
        assert health.circuit_state == "open"

    def test_health_degraded_when_circuit_half_open(self, scanner):
        """Health status is degraded when circuit is half-open."""
        scanner._is_running = True
        scanner._circuit_state = CircuitState.HALF_OPEN

        health = scanner.get_health()

        assert health.status == "degraded"

    def test_health_degraded_when_queue_high(self, scanner, sample_ohlcv_bar):
        """Health status is degraded when queue is >80% full."""
        scanner._is_running = True
        scanner._circuit_state = CircuitState.CLOSED

        # Fill queue to 85%
        for _ in range(85):
            try:
                scanner._bar_queue.put_nowait(sample_ohlcv_bar)
            except asyncio.QueueFull:
                break

        health = scanner.get_health()

        assert health.status == "degraded"
        assert health.queue_depth >= 80

    def test_health_includes_metrics(self, scanner):
        """Health includes processing metrics."""
        scanner._metrics.bars_processed = 100
        scanner._metrics.bars_dropped = 5
        scanner._metrics.latency_samples.append(45.0)
        scanner._metrics.last_processed = datetime.now(UTC)

        health = scanner.get_health()

        assert health.bars_processed == 100
        assert health.bars_dropped == 5
        assert health.avg_latency_ms == 45.0
        assert health.last_processed is not None


# =============================
# Processing Metrics Tests
# =============================


class TestProcessingMetrics:
    """Tests for ProcessingMetrics dataclass."""

    def test_avg_latency_empty(self):
        """Average latency is 0 with no samples."""
        metrics = ProcessingMetrics()

        assert metrics.avg_latency_ms == 0.0

    def test_avg_latency_calculation(self):
        """Average latency calculated correctly."""
        metrics = ProcessingMetrics()
        metrics.latency_samples.extend([10.0, 20.0, 30.0])

        assert metrics.avg_latency_ms == 20.0

    def test_latency_samples_rolling(self):
        """Latency samples use rolling window (max 100)."""
        metrics = ProcessingMetrics()

        # Add 150 samples
        for i in range(150):
            metrics.latency_samples.append(float(i))

        assert len(metrics.latency_samples) == 100
        # Should have samples 50-149
        assert list(metrics.latency_samples)[0] == 50.0


# =============================
# Global Functions Tests
# =============================


class TestGlobalFunctions:
    """Tests for global scanner functions."""

    @pytest.fixture(autouse=True)
    def reset_global_scanner(self):
        """Save and restore global scanner state for each test."""
        import src.pattern_engine.realtime_scanner as module

        original_scanner = module._scanner
        yield
        module._scanner = original_scanner

    def test_init_scanner_creates_instance(self):
        """init_scanner creates global scanner instance."""
        scanner = init_scanner(queue_max_size=200, processing_timeout_ms=75)

        assert scanner is not None
        assert scanner._queue_max_size == 200
        assert scanner._processing_timeout_ms == 75

    def test_get_scanner_returns_instance(self):
        """get_scanner returns the initialized instance."""
        init_scanner()
        scanner = get_scanner()

        assert scanner is not None

    def test_get_scanner_raises_if_not_initialized(self):
        """get_scanner raises if not initialized."""
        import src.pattern_engine.realtime_scanner as module

        module._scanner = None

        with pytest.raises(RuntimeError, match="Scanner not initialized"):
            get_scanner()


# =============================
# Integration-like Tests
# =============================


class TestScannerIntegration:
    """Integration-like tests for full scanner workflow."""

    @pytest.mark.asyncio
    async def test_full_processing_workflow(self, mock_coordinator):
        """Full workflow: start, receive bars, process, stop."""
        scanner = RealtimePatternScanner(queue_max_size=10)

        # Start
        await scanner.start(mock_coordinator)
        assert scanner.is_running

        # Receive bars
        for i in range(5):
            bar = OHLCVBar(
                symbol=f"SYM{i}",
                timeframe="1m",
                timestamp=datetime.now(UTC),
                open=Decimal("100.00"),
                high=Decimal("101.00"),
                low=Decimal("99.00"),
                close=Decimal("100.50"),
                volume=10000,
                spread=Decimal("2.00"),
                spread_ratio=Decimal("1.0"),
                volume_ratio=Decimal("1.0"),
            )
            scanner._on_bar_received(bar)

        # Wait for processing
        await asyncio.sleep(0.5)

        # Check metrics
        assert scanner._metrics.bars_processed >= 5
        assert scanner._metrics.last_processed is not None

        # Check health
        health = scanner.get_health()
        assert health.status == "healthy"
        assert health.bars_processed >= 5

        # Stop
        await scanner.stop()
        assert not scanner.is_running

    @pytest.mark.asyncio
    async def test_processing_under_load(self, mock_coordinator):
        """Scanner handles multiple bars under load."""
        scanner = RealtimePatternScanner(queue_max_size=100)
        await scanner.start(mock_coordinator)

        # Rapid fire bars
        for i in range(50):
            bar = OHLCVBar(
                symbol="AAPL",
                timeframe="1m",
                timestamp=datetime.now(UTC),
                open=Decimal("100.00"),
                high=Decimal("101.00"),
                low=Decimal("99.00"),
                close=Decimal("100.50"),
                volume=10000,
                spread=Decimal("2.00"),
                spread_ratio=Decimal("1.0"),
                volume_ratio=Decimal("1.0"),
            )
            scanner._on_bar_received(bar)

        # Wait for processing
        await asyncio.sleep(1.0)

        # All bars should be processed
        assert scanner._metrics.bars_processed >= 50
        assert scanner._metrics.bars_dropped == 0

        await scanner.stop()
