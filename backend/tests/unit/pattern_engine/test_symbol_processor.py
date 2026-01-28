"""
Unit tests for MultiSymbolProcessor class.

Tests cover:
- Concurrent processing of multiple symbols
- Per-symbol isolation
- Circuit breaker integration
- Latency tracking
- Bar routing
- Status reporting
- Symbol management (add/remove)

Author: Story 19.4 - Multi-Symbol Concurrent Processing
"""

import asyncio
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from src.models.ohlcv import OHLCVBar
from src.models.scanner import CircuitStateEnum, SymbolState
from src.pattern_engine.circuit_breaker import CircuitState
from src.pattern_engine.symbol_processor import (
    MultiSymbolProcessor,
    SymbolMetrics,
    get_multi_symbol_processor,
    init_multi_symbol_processor,
)


def create_test_bar(symbol: str, timestamp: datetime = None) -> OHLCVBar:
    """Create a test OHLCV bar."""
    if timestamp is None:
        timestamp = datetime.now(UTC)

    return OHLCVBar(
        symbol=symbol,
        timestamp=timestamp,
        open=Decimal("100.00"),
        high=Decimal("101.00"),
        low=Decimal("99.00"),
        close=Decimal("100.50"),
        volume=1000000,
        spread=Decimal("2.00"),
        timeframe="1m",
    )


class TestMultiSymbolProcessorInitialization:
    """Test MultiSymbolProcessor initialization."""

    def test_creates_contexts_for_all_symbols(self):
        """Should create contexts for all provided symbols."""
        processor = MultiSymbolProcessor(symbols=["AAPL", "TSLA", "MSFT"])

        assert len(processor.symbols) == 3
        assert "AAPL" in processor.symbols
        assert "TSLA" in processor.symbols
        assert "MSFT" in processor.symbols

    def test_limits_symbols_to_max_concurrent(self):
        """Should limit symbols to max_concurrent."""
        symbols = [f"SYM{i}" for i in range(20)]
        processor = MultiSymbolProcessor(symbols=symbols, max_concurrent=10)

        assert len(processor.symbols) == 10

    def test_is_not_running_initially(self):
        """Processor should not be running initially."""
        processor = MultiSymbolProcessor(symbols=["AAPL"])
        assert not processor.is_running

    def test_creates_circuit_breaker_per_symbol(self):
        """Each symbol should have its own circuit breaker."""
        processor = MultiSymbolProcessor(symbols=["AAPL", "TSLA"])

        aapl_status = processor.get_symbol_status("AAPL")
        tsla_status = processor.get_symbol_status("TSLA")

        assert aapl_status is not None
        assert tsla_status is not None
        assert aapl_status.circuit_state == CircuitStateEnum.CLOSED
        assert tsla_status.circuit_state == CircuitStateEnum.CLOSED


class TestStartStop:
    """Test start/stop functionality."""

    @pytest.mark.asyncio
    async def test_start_sets_running_flag(self):
        """Start should set is_running to True."""
        processor = MultiSymbolProcessor(symbols=["AAPL"])
        await processor.start()

        try:
            assert processor.is_running
        finally:
            await processor.stop()

    @pytest.mark.asyncio
    async def test_stop_clears_running_flag(self):
        """Stop should set is_running to False."""
        processor = MultiSymbolProcessor(symbols=["AAPL"])
        await processor.start()
        await processor.stop()

        assert not processor.is_running

    @pytest.mark.asyncio
    async def test_double_start_is_safe(self):
        """Double start should be safe (no error)."""
        processor = MultiSymbolProcessor(symbols=["AAPL"])
        await processor.start()
        await processor.start()  # Should not raise

        try:
            assert processor.is_running
        finally:
            await processor.stop()

    @pytest.mark.asyncio
    async def test_double_stop_is_safe(self):
        """Double stop should be safe (no error)."""
        processor = MultiSymbolProcessor(symbols=["AAPL"])
        await processor.start()
        await processor.stop()
        await processor.stop()  # Should not raise

        assert not processor.is_running


class TestQueueBar:
    """Test bar queueing functionality."""

    @pytest.mark.asyncio
    async def test_queue_bar_routes_to_correct_symbol(self):
        """Bars should be routed to the correct symbol's queue."""
        processor = MultiSymbolProcessor(symbols=["AAPL", "TSLA"])
        await processor.start()

        try:
            bar = create_test_bar("AAPL")
            result = processor.queue_bar(bar)

            assert result is True
            # Check AAPL queue has the bar
            assert processor._contexts["AAPL"].queue.qsize() == 1
            # Check TSLA queue is empty
            assert processor._contexts["TSLA"].queue.qsize() == 0
        finally:
            await processor.stop()

    def test_queue_bar_returns_false_when_not_running(self):
        """queue_bar should return False when processor is not running."""
        processor = MultiSymbolProcessor(symbols=["AAPL"])
        bar = create_test_bar("AAPL")

        result = processor.queue_bar(bar)
        assert result is False

    @pytest.mark.asyncio
    async def test_queue_bar_returns_false_for_unknown_symbol(self):
        """queue_bar should return False for unknown symbols."""
        processor = MultiSymbolProcessor(symbols=["AAPL"])
        await processor.start()

        try:
            bar = create_test_bar("UNKNOWN")
            result = processor.queue_bar(bar)
            assert result is False
        finally:
            await processor.stop()


class TestConcurrentProcessing:
    """Test concurrent processing capabilities."""

    @pytest.mark.asyncio
    async def test_processes_multiple_symbols_concurrently(self):
        """Should process bars for multiple symbols concurrently."""
        processed_symbols = []

        async def track_processing(bar: OHLCVBar):
            processed_symbols.append(bar.symbol)
            await asyncio.sleep(0.01)  # Simulate processing time

        processor = MultiSymbolProcessor(
            symbols=["AAPL", "TSLA", "MSFT"],
            bar_processor=track_processing,
        )
        await processor.start()

        try:
            # Queue bars for all symbols
            for symbol in ["AAPL", "TSLA", "MSFT"]:
                processor.queue_bar(create_test_bar(symbol))

            # Wait for processing
            await asyncio.sleep(0.2)

            # All should be processed
            assert "AAPL" in processed_symbols
            assert "TSLA" in processed_symbols
            assert "MSFT" in processed_symbols
        finally:
            await processor.stop()

    @pytest.mark.asyncio
    async def test_failure_in_one_symbol_does_not_affect_others(self):
        """Failure in one symbol should not affect other symbols."""
        processed_count = {"AAPL": 0, "TSLA": 0}

        async def process_with_failure(bar: OHLCVBar):
            if bar.symbol == "TSLA":
                raise ValueError("Simulated TSLA failure")
            processed_count[bar.symbol] += 1

        processor = MultiSymbolProcessor(
            symbols=["AAPL", "TSLA"],
            bar_processor=process_with_failure,
        )
        await processor.start()

        try:
            # Queue bars for both symbols
            for _ in range(3):
                processor.queue_bar(create_test_bar("AAPL"))
                processor.queue_bar(create_test_bar("TSLA"))

            # Wait for processing
            await asyncio.sleep(0.3)

            # AAPL should be processed, TSLA failures should be isolated
            assert processed_count["AAPL"] == 3
        finally:
            await processor.stop()


class TestLatencyTracking:
    """Test latency tracking."""

    @pytest.mark.asyncio
    async def test_tracks_processing_latency(self):
        """Should track processing latency for each symbol."""

        async def slow_processor(bar: OHLCVBar):
            await asyncio.sleep(0.05)  # 50ms processing

        processor = MultiSymbolProcessor(
            symbols=["AAPL"],
            bar_processor=slow_processor,
        )
        await processor.start()

        try:
            processor.queue_bar(create_test_bar("AAPL"))
            await asyncio.sleep(0.2)

            status = processor.get_symbol_status("AAPL")
            assert status.avg_latency_ms > 0
        finally:
            await processor.stop()


class TestSymbolStatus:
    """Test symbol status reporting."""

    def test_get_symbol_status_for_existing_symbol(self):
        """Should return status for existing symbol with fresh data."""
        processor = MultiSymbolProcessor(symbols=["AAPL"])
        # Set a recent bar time to ensure symbol is not stale (Story 19.26)
        processor._contexts["AAPL"].metrics.last_bar_time = datetime.now(UTC)
        status = processor.get_symbol_status("AAPL")

        assert status is not None
        assert status.symbol == "AAPL"
        assert status.state == SymbolState.PROCESSING

    def test_get_symbol_status_for_stale_symbol(self):
        """Should return STALE state for symbol without recent data (Story 19.26)."""
        processor = MultiSymbolProcessor(symbols=["AAPL"])
        # No bar time set - symbol should be stale
        status = processor.get_symbol_status("AAPL")

        assert status is not None
        assert status.symbol == "AAPL"
        assert status.state == SymbolState.STALE
        assert status.is_stale is True

    def test_get_symbol_status_for_unknown_symbol(self):
        """Should return None for unknown symbol."""
        processor = MultiSymbolProcessor(symbols=["AAPL"])
        status = processor.get_symbol_status("UNKNOWN")

        assert status is None

    def test_status_reflects_circuit_breaker_state(self):
        """Status should reflect circuit breaker state."""
        processor = MultiSymbolProcessor(symbols=["AAPL"])

        # Set circuit to OPEN
        processor._contexts["AAPL"].circuit_breaker._state = CircuitState.OPEN

        status = processor.get_symbol_status("AAPL")
        assert status.state == SymbolState.FAILED
        assert status.circuit_state == CircuitStateEnum.OPEN


class TestOverallStatus:
    """Test overall scanner status."""

    def test_get_status_returns_all_symbols(self):
        """get_status should include all symbols."""
        processor = MultiSymbolProcessor(symbols=["AAPL", "TSLA", "MSFT"])
        status = processor.get_status()

        assert status.total_symbols == 3
        assert len(status.symbols) == 3

    def test_status_counts_healthy_symbols(self):
        """Status should count healthy symbols correctly."""
        processor = MultiSymbolProcessor(symbols=["AAPL", "TSLA", "MSFT"])
        # Set recent bar times to ensure symbols are not stale (Story 19.26)
        for symbol in ["AAPL", "TSLA", "MSFT"]:
            processor._contexts[symbol].metrics.last_bar_time = datetime.now(UTC)
        status = processor.get_status()

        assert status.healthy_symbols == 3
        assert status.paused_symbols == 0
        assert status.failed_symbols == 0
        assert status.stale_count == 0  # Story 19.26

    @pytest.mark.asyncio
    async def test_status_reflects_degraded_state(self):
        """Status should be degraded when symbols are failing but processor running."""
        processor = MultiSymbolProcessor(symbols=["AAPL", "TSLA"])
        # Set recent bar times to ensure symbols are not stale (Story 19.26)
        for symbol in ["AAPL", "TSLA"]:
            processor._contexts[symbol].metrics.last_bar_time = datetime.now(UTC)
        await processor.start()

        try:
            # Set one circuit to OPEN
            processor._contexts["TSLA"].circuit_breaker._state = CircuitState.OPEN

            status = processor.get_status()
            assert status.overall_status == "degraded"
            assert status.failed_symbols == 1
            assert status.healthy_symbols == 1  # AAPL should still be healthy
        finally:
            await processor.stop()

    def test_status_reflects_unhealthy_when_not_running(self):
        """Status should be unhealthy when not running."""
        processor = MultiSymbolProcessor(symbols=["AAPL"])
        status = processor.get_status()

        assert status.overall_status == "unhealthy"
        assert status.is_running is False


class TestSymbolManagement:
    """Test dynamic symbol management."""

    @pytest.mark.asyncio
    async def test_add_symbol(self):
        """Should be able to add a new symbol."""
        processor = MultiSymbolProcessor(symbols=["AAPL"])
        await processor.start()

        try:
            result = await processor.add_symbol("TSLA")
            assert result is True
            assert "TSLA" in processor.symbols
        finally:
            await processor.stop()

    @pytest.mark.asyncio
    async def test_add_existing_symbol_returns_false(self):
        """Adding existing symbol should return False."""
        processor = MultiSymbolProcessor(symbols=["AAPL"])
        await processor.start()

        try:
            result = await processor.add_symbol("AAPL")
            assert result is False
        finally:
            await processor.stop()

    @pytest.mark.asyncio
    async def test_remove_symbol(self):
        """Should be able to remove a symbol."""
        processor = MultiSymbolProcessor(symbols=["AAPL", "TSLA"])
        await processor.start()

        try:
            result = await processor.remove_symbol("TSLA")
            assert result is True
            assert "TSLA" not in processor.symbols
        finally:
            await processor.stop()

    @pytest.mark.asyncio
    async def test_remove_unknown_symbol_returns_false(self):
        """Removing unknown symbol should return False."""
        processor = MultiSymbolProcessor(symbols=["AAPL"])
        await processor.start()

        try:
            result = await processor.remove_symbol("UNKNOWN")
            assert result is False
        finally:
            await processor.stop()


class TestCircuitBreakerReset:
    """Test circuit breaker reset functionality."""

    @pytest.mark.asyncio
    async def test_reset_circuit_breaker(self):
        """Should be able to reset a symbol's circuit breaker."""
        processor = MultiSymbolProcessor(symbols=["AAPL"])

        # Open the circuit
        processor._contexts["AAPL"].circuit_breaker._state = CircuitState.OPEN

        result = await processor.reset_circuit_breaker("AAPL")
        assert result is True

        status = processor.get_symbol_status("AAPL")
        assert status.circuit_state == CircuitStateEnum.CLOSED

    @pytest.mark.asyncio
    async def test_reset_unknown_symbol_returns_false(self):
        """Resetting unknown symbol should return False."""
        processor = MultiSymbolProcessor(symbols=["AAPL"])

        result = await processor.reset_circuit_breaker("UNKNOWN")
        assert result is False


class TestAdminNotifications:
    """Test admin notification integration."""

    @pytest.mark.asyncio
    async def test_admin_notification_on_circuit_open(self):
        """Should trigger admin notification when circuit opens."""
        notifications = []

        def on_notify(symbol: str, message: str):
            notifications.append((symbol, message))

        async def failing_processor(bar: OHLCVBar):
            raise ValueError("Simulated failure")

        processor = MultiSymbolProcessor(
            symbols=["AAPL"],
            bar_processor=failing_processor,
            on_admin_notify=on_notify,
            circuit_breaker_threshold=3,
        )
        await processor.start()

        try:
            # Queue bars to trigger failures
            for _ in range(5):
                processor.queue_bar(create_test_bar("AAPL"))
                await asyncio.sleep(0.1)

            # Should have received notification
            assert len(notifications) >= 1
            assert notifications[0][0] == "AAPL"
        finally:
            await processor.stop()


class TestGlobalInstance:
    """Test global processor instance management."""

    def test_init_creates_global_processor(self):
        """init_multi_symbol_processor should create global instance."""
        processor = init_multi_symbol_processor(symbols=["AAPL"])

        global_processor = get_multi_symbol_processor()
        assert global_processor is processor

    def test_get_returns_none_before_init(self):
        """get_multi_symbol_processor should return None before init."""
        # Reset global state
        import src.pattern_engine.symbol_processor as sp

        sp._processor = None

        result = get_multi_symbol_processor()
        assert result is None


class TestSymbolMetrics:
    """Test SymbolMetrics dataclass."""

    def test_avg_latency_with_no_samples(self):
        """avg_latency_ms should return 0 with no samples."""
        metrics = SymbolMetrics()
        assert metrics.avg_latency_ms == 0.0

    def test_avg_latency_with_samples(self):
        """avg_latency_ms should calculate average correctly."""
        metrics = SymbolMetrics()
        metrics.latency_samples.append(10.0)
        metrics.latency_samples.append(20.0)
        metrics.latency_samples.append(30.0)

        assert metrics.avg_latency_ms == 20.0
