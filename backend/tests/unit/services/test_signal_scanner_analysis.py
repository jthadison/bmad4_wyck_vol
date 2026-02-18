"""
Unit tests for SignalScannerService symbol analysis (Story 20.3b).

Tests scanner cycle processing: orchestrator integration, batch processing,
error isolation, and metrics recording.
"""

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.models.scanner_persistence import (
    AssetClass,
    ScanCycleStatus,
    Timeframe,
    WatchlistSymbol,
)
from src.services.signal_scanner_service import (
    ScanCycleResult,
    SignalScannerService,
)


def create_mock_symbol(
    symbol: str,
    timeframe: Timeframe = Timeframe.H1,
    enabled: bool = True,
) -> WatchlistSymbol:
    """Create a mock WatchlistSymbol for testing."""
    return WatchlistSymbol(
        id=uuid4(),
        symbol=symbol,
        timeframe=timeframe,
        asset_class=AssetClass.FOREX,
        enabled=enabled,
        last_scanned_at=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.fixture
def mock_repository():
    """Create mock ScannerRepository."""
    repo = MagicMock()

    # Mock get_config to return a default config
    config = MagicMock()
    config.scan_interval_seconds = 60
    config.batch_size = 10
    config.last_cycle_at = None
    config.session_filter_enabled = False  # Disable session filtering for these tests
    repo.get_config = AsyncMock(return_value=config)

    # Mock update_config
    repo.update_config = AsyncMock()

    # Mock get_symbol_count
    repo.get_symbol_count = AsyncMock(return_value=5)

    # Mock set_last_cycle_at
    repo.set_last_cycle_at = AsyncMock()

    # Mock get_enabled_symbols (default empty)
    repo.get_enabled_symbols = AsyncMock(return_value=[])

    # Mock update_last_scanned
    repo.update_last_scanned = AsyncMock()

    # Mock add_history
    repo.add_history = AsyncMock()

    return repo


@pytest.fixture
def mock_orchestrator():
    """Create mock MasterOrchestrator."""
    orchestrator = MagicMock()
    orchestrator.analyze_symbol = AsyncMock(return_value=[])
    return orchestrator


def create_scanner_without_session_filter(repository, orchestrator):
    """Create a SignalScannerService with session filtering disabled for tests."""
    scanner = SignalScannerService(repository, orchestrator)
    scanner._session_filter_enabled = False
    return scanner


@pytest.fixture
def scanner(mock_repository, mock_orchestrator):
    """Create SignalScannerService with mocks (session filtering disabled)."""
    return create_scanner_without_session_filter(mock_repository, mock_orchestrator)


class TestScanCycleProcessesEnabledOnly:
    """Tests for AC1: Iterate Enabled Symbols."""

    @pytest.mark.asyncio
    async def test_scan_cycle_processes_enabled_symbols_only(
        self, mock_repository, mock_orchestrator
    ):
        """Test that _scan_cycle only processes enabled symbols."""
        # Setup: 2 enabled, 1 disabled (but get_enabled_symbols returns only enabled)
        enabled_symbols = [
            create_mock_symbol("EURUSD"),
            create_mock_symbol("SPY"),
        ]
        mock_repository.get_enabled_symbols.return_value = enabled_symbols

        scanner = create_scanner_without_session_filter(mock_repository, mock_orchestrator)

        # Execute
        result = await scanner._scan_cycle()

        # Assert
        assert mock_orchestrator.analyze_symbol.call_count == 2
        mock_orchestrator.analyze_symbol.assert_any_call("EURUSD", timeframe="1H")
        mock_orchestrator.analyze_symbol.assert_any_call("SPY", timeframe="1H")

    @pytest.mark.asyncio
    async def test_scan_cycle_skips_disabled_symbols(self, mock_repository, mock_orchestrator):
        """Test that disabled symbols from get_enabled_symbols are not processed."""
        # get_enabled_symbols already filters, so this tests that filter
        mock_repository.get_enabled_symbols.return_value = [
            create_mock_symbol("EURUSD"),
        ]

        scanner = create_scanner_without_session_filter(mock_repository, mock_orchestrator)

        result = await scanner._scan_cycle()

        # Only EURUSD should be analyzed
        assert mock_orchestrator.analyze_symbol.call_count == 1
        mock_orchestrator.analyze_symbol.assert_called_with("EURUSD", timeframe="1H")

    @pytest.mark.asyncio
    async def test_scan_cycle_handles_empty_watchlist(self, mock_repository, mock_orchestrator):
        """Test that _scan_cycle handles empty watchlist gracefully."""
        mock_repository.get_enabled_symbols.return_value = []

        scanner = create_scanner_without_session_filter(mock_repository, mock_orchestrator)

        result = await scanner._scan_cycle()

        assert result.symbols_scanned == 0
        assert result.status == ScanCycleStatus.COMPLETED
        assert mock_orchestrator.analyze_symbol.call_count == 0


class TestOrchestratorIntegration:
    """Tests for AC2: Orchestrator Integration."""

    @pytest.mark.asyncio
    async def test_orchestrator_called_with_correct_args(self, mock_repository, mock_orchestrator):
        """Test that orchestrator.analyze_symbol is called with correct arguments."""
        symbols = [
            create_mock_symbol("EURUSD", timeframe=Timeframe.H1),
            create_mock_symbol("SPY", timeframe=Timeframe.D1),
        ]
        mock_repository.get_enabled_symbols.return_value = symbols

        scanner = create_scanner_without_session_filter(mock_repository, mock_orchestrator)

        await scanner._scan_cycle()

        mock_orchestrator.analyze_symbol.assert_any_call("EURUSD", timeframe="1H")
        mock_orchestrator.analyze_symbol.assert_any_call("SPY", timeframe="1D")

    @pytest.mark.asyncio
    async def test_last_scanned_at_updated(self, mock_repository, mock_orchestrator):
        """Test that last_scanned_at is updated for each symbol."""
        symbols = [create_mock_symbol("EURUSD")]
        mock_repository.get_enabled_symbols.return_value = symbols

        scanner = create_scanner_without_session_filter(mock_repository, mock_orchestrator)

        await scanner._scan_cycle()

        mock_repository.update_last_scanned.assert_called_once()
        call_args = mock_repository.update_last_scanned.call_args
        assert call_args[0][0] == "EURUSD"
        assert isinstance(call_args[0][1], datetime)

    @pytest.mark.asyncio
    async def test_signals_collected_from_orchestrator(self, mock_repository, mock_orchestrator):
        """Test that signals from orchestrator are collected in result."""
        symbols = [create_mock_symbol("EURUSD"), create_mock_symbol("SPY")]
        mock_repository.get_enabled_symbols.return_value = symbols

        # Return different signals for each symbol
        mock_signal_1 = MagicMock()
        mock_signal_2 = MagicMock()
        mock_orchestrator.analyze_symbol.side_effect = [[mock_signal_1], [mock_signal_2]]

        scanner = create_scanner_without_session_filter(mock_repository, mock_orchestrator)

        result = await scanner._scan_cycle()

        assert result.signals_generated == 2
        assert len(result.signals) == 2
        assert mock_signal_1 in result.signals
        assert mock_signal_2 in result.signals

    @pytest.mark.asyncio
    async def test_orchestrator_not_configured_returns_skipped(self, mock_repository):
        """Test that scanner returns SKIPPED when orchestrator not configured."""
        symbols = [create_mock_symbol("EURUSD")]
        mock_repository.get_enabled_symbols.return_value = symbols

        # Scanner without orchestrator
        scanner = SignalScannerService(mock_repository, orchestrator=None)
        scanner._session_filter_enabled = False

        result = await scanner._scan_cycle()

        # Should return SKIPPED status without processing any symbols
        assert result.symbols_scanned == 0
        assert result.errors_count == 0
        assert result.status == ScanCycleStatus.SKIPPED


class TestErrorIsolation:
    """Tests for AC3: Error Isolation."""

    @pytest.mark.asyncio
    async def test_error_isolation_continues_after_failure(
        self, mock_repository, mock_orchestrator
    ):
        """Test that one symbol failure doesn't stop the cycle."""
        symbols = [
            create_mock_symbol("EURUSD"),
            create_mock_symbol("GBPUSD"),
            create_mock_symbol("SPY"),
        ]
        mock_repository.get_enabled_symbols.return_value = symbols

        # Second symbol fails
        mock_orchestrator.analyze_symbol.side_effect = [
            [],  # EURUSD success
            Exception("API Error"),  # GBPUSD failure
            [],  # SPY success
        ]

        scanner = create_scanner_without_session_filter(mock_repository, mock_orchestrator)

        result = await scanner._scan_cycle()

        assert result.symbols_scanned == 3
        assert result.errors_count == 1
        assert result.status == ScanCycleStatus.PARTIAL

    @pytest.mark.asyncio
    async def test_all_failures_returns_failed_status(self, mock_repository, mock_orchestrator):
        """Test that all failures result in FAILED status."""
        symbols = [
            create_mock_symbol("EURUSD"),
            create_mock_symbol("GBPUSD"),
        ]
        mock_repository.get_enabled_symbols.return_value = symbols

        # All symbols fail
        mock_orchestrator.analyze_symbol.side_effect = Exception("API Error")

        scanner = create_scanner_without_session_filter(mock_repository, mock_orchestrator)

        result = await scanner._scan_cycle()

        assert result.symbols_scanned == 2
        assert result.errors_count == 2
        assert result.status == ScanCycleStatus.FAILED

    @pytest.mark.asyncio
    async def test_error_does_not_update_last_scanned(self, mock_repository, mock_orchestrator):
        """Test that failed symbol doesn't update last_scanned_at."""
        symbols = [create_mock_symbol("EURUSD")]
        mock_repository.get_enabled_symbols.return_value = symbols

        mock_orchestrator.analyze_symbol.side_effect = Exception("API Error")

        scanner = create_scanner_without_session_filter(mock_repository, mock_orchestrator)

        await scanner._scan_cycle()

        # update_last_scanned should not be called for failed symbol
        mock_repository.update_last_scanned.assert_not_called()


class TestBatchProcessing:
    """Tests for AC5: Batch Processing."""

    @pytest.mark.asyncio
    async def test_batch_processing_splits_correctly(self, mock_repository, mock_orchestrator):
        """Test that symbols are split into correct batch sizes."""
        # 25 symbols, batch size 10 = 3 batches
        symbols = [create_mock_symbol(f"SYM{i}") for i in range(25)]
        mock_repository.get_enabled_symbols.return_value = symbols

        config = MagicMock()
        config.scan_interval_seconds = 60
        config.batch_size = 10
        config.last_cycle_at = None
        config.session_filter_enabled = False  # Disable session filtering for test
        mock_repository.get_config.return_value = config

        scanner = create_scanner_without_session_filter(mock_repository, mock_orchestrator)
        await scanner.start()

        try:
            # Let cycle run
            await asyncio.sleep(0.3)

            # All 25 symbols should be analyzed
            assert mock_orchestrator.analyze_symbol.call_count == 25
        finally:
            await scanner.stop()

    @pytest.mark.asyncio
    async def test_batch_delay_applied_between_batches(self, mock_repository, mock_orchestrator):
        """Test that delay is applied between batches."""
        symbols = [create_mock_symbol(f"SYM{i}") for i in range(25)]
        mock_repository.get_enabled_symbols.return_value = symbols

        scanner = create_scanner_without_session_filter(mock_repository, mock_orchestrator)
        scanner._batch_size = 10
        scanner._batch_delay_ms = 100

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await scanner._scan_cycle()

            # 3 batches = 2 delays (after batch 1 and 2, not after last)
            # Filter for only the batch delay calls (0.1 seconds)
            batch_delay_calls = [call for call in mock_sleep.call_args_list if call[0][0] == 0.1]
            assert len(batch_delay_calls) == 2

    @pytest.mark.asyncio
    async def test_no_delay_after_last_batch(self, mock_repository, mock_orchestrator):
        """Test that no delay is added after the last batch."""
        # 5 symbols, batch size 10 = 1 batch, no delays
        symbols = [create_mock_symbol(f"SYM{i}") for i in range(5)]
        mock_repository.get_enabled_symbols.return_value = symbols

        scanner = create_scanner_without_session_filter(mock_repository, mock_orchestrator)
        scanner._batch_size = 10
        scanner._batch_delay_ms = 100

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await scanner._scan_cycle()

            # Only 1 batch, no delays
            batch_delay_calls = [call for call in mock_sleep.call_args_list if call[0][0] == 0.1]
            assert len(batch_delay_calls) == 0


class TestScanCycleMetrics:
    """Tests for AC4: Scan Cycle Metrics."""

    @pytest.mark.asyncio
    async def test_cycle_metrics_recorded(self, mock_repository, mock_orchestrator):
        """Test that scan cycle metrics are correctly recorded."""
        symbols = [
            create_mock_symbol("EURUSD"),
            create_mock_symbol("GBPUSD"),
            create_mock_symbol("SPY"),
        ]
        mock_repository.get_enabled_symbols.return_value = symbols

        # 2 succeed with signals, 1 fails
        mock_orchestrator.analyze_symbol.side_effect = [
            [MagicMock()],  # EURUSD: 1 signal
            Exception("Error"),  # GBPUSD: failure
            [MagicMock()],  # SPY: 1 signal
        ]

        scanner = create_scanner_without_session_filter(mock_repository, mock_orchestrator)

        result = await scanner._scan_cycle()

        assert result.symbols_scanned == 3
        assert result.signals_generated == 2
        assert result.errors_count == 1
        assert result.status == ScanCycleStatus.PARTIAL

    @pytest.mark.asyncio
    async def test_history_recorded_in_database(self, mock_repository, mock_orchestrator):
        """Test that scanner_history is recorded after cycle."""
        symbols = [create_mock_symbol("EURUSD")]
        mock_repository.get_enabled_symbols.return_value = symbols

        scanner = create_scanner_without_session_filter(mock_repository, mock_orchestrator)

        await scanner._scan_cycle()

        mock_repository.add_history.assert_called_once()
        history_entry = mock_repository.add_history.call_args[0][0]
        assert history_entry.symbols_scanned == 1
        assert history_entry.status == ScanCycleStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_cycle_timestamps_recorded(self, mock_repository, mock_orchestrator):
        """Test that cycle start/end timestamps are recorded."""
        symbols = [create_mock_symbol("EURUSD")]
        mock_repository.get_enabled_symbols.return_value = symbols

        scanner = create_scanner_without_session_filter(mock_repository, mock_orchestrator)

        before = datetime.now(UTC)
        result = await scanner._scan_cycle()
        after = datetime.now(UTC)

        assert before <= result.cycle_started_at <= after
        assert before <= result.cycle_ended_at <= after
        assert result.cycle_started_at <= result.cycle_ended_at


class TestGracefulStopDuringCycle:
    """Tests for AC6: Graceful Stop During Cycle."""

    @pytest.mark.asyncio
    async def test_stop_mid_cycle_completes_current_symbol(
        self, mock_repository, mock_orchestrator
    ):
        """Test that stop during cycle lets current symbol complete."""
        # 10 symbols to process
        symbols = [create_mock_symbol(f"SYM{i}") for i in range(10)]
        mock_repository.get_enabled_symbols.return_value = symbols

        # Orchestrator takes time to analyze (simulating real work)
        async def slow_analyze(symbol, **kwargs):
            await asyncio.sleep(0.05)  # 50ms per symbol
            return []

        mock_orchestrator.analyze_symbol.side_effect = slow_analyze

        scanner = create_scanner_without_session_filter(mock_repository, mock_orchestrator)
        scanner._batch_size = 5

        # Start scan cycle in background
        cycle_task = asyncio.create_task(scanner._scan_cycle())

        # Wait for a few symbols to process
        await asyncio.sleep(0.15)  # ~3 symbols processed

        # Signal stop
        scanner._stop_event.set()

        # Wait for cycle to complete
        result = await cycle_task

        # Should have partial status
        assert result.status == ScanCycleStatus.PARTIAL
        assert result.symbols_scanned < 10

    @pytest.mark.asyncio
    async def test_stop_records_partial_status(self, mock_repository, mock_orchestrator):
        """Test that stopped cycle records PARTIAL status in history."""
        symbols = [create_mock_symbol(f"SYM{i}") for i in range(10)]
        mock_repository.get_enabled_symbols.return_value = symbols

        async def slow_analyze(symbol, **kwargs):
            await asyncio.sleep(0.03)
            return []

        mock_orchestrator.analyze_symbol.side_effect = slow_analyze

        scanner = create_scanner_without_session_filter(mock_repository, mock_orchestrator)
        scanner._batch_size = 5

        cycle_task = asyncio.create_task(scanner._scan_cycle())
        await asyncio.sleep(0.1)
        scanner._stop_event.set()
        result = await cycle_task

        # Verify history was recorded with PARTIAL status
        mock_repository.add_history.assert_called_once()
        history_entry = mock_repository.add_history.call_args[0][0]
        assert history_entry.status == ScanCycleStatus.PARTIAL


class TestScanCycleResult:
    """Tests for ScanCycleResult dataclass."""

    def test_scan_cycle_result_creation(self):
        """Test that ScanCycleResult can be created with all fields."""
        now = datetime.now(UTC)
        result = ScanCycleResult(
            cycle_started_at=now,
            cycle_ended_at=now,
            symbols_scanned=5,
            signals_generated=2,
            errors_count=1,
            status=ScanCycleStatus.COMPLETED,
            signals=[MagicMock(), MagicMock()],
        )

        assert result.symbols_scanned == 5
        assert result.signals_generated == 2
        assert result.errors_count == 1
        assert result.status == ScanCycleStatus.COMPLETED
        assert len(result.signals) == 2

    def test_scan_cycle_result_default_signals(self):
        """Test that signals defaults to empty list."""
        now = datetime.now(UTC)
        result = ScanCycleResult(
            cycle_started_at=now,
            cycle_ended_at=now,
            symbols_scanned=0,
            signals_generated=0,
            errors_count=0,
            status=ScanCycleStatus.COMPLETED,
        )

        assert result.signals == []


class TestStatusDetermination:
    """Tests for _determine_cycle_status method."""

    def test_completed_status(self, scanner):
        """Test COMPLETED status when all symbols processed without errors."""
        status = scanner._determine_cycle_status(
            symbols_total=5,
            symbols_processed=5,
            errors_count=0,
            was_stopped=False,
        )
        assert status == ScanCycleStatus.COMPLETED

    def test_partial_status_when_stopped(self, scanner):
        """Test PARTIAL status when stopped mid-cycle."""
        status = scanner._determine_cycle_status(
            symbols_total=10,
            symbols_processed=3,
            errors_count=0,
            was_stopped=True,
        )
        assert status == ScanCycleStatus.PARTIAL

    def test_failed_status_all_errors(self, scanner):
        """Test FAILED status when all symbols error."""
        status = scanner._determine_cycle_status(
            symbols_total=5,
            symbols_processed=5,
            errors_count=5,
            was_stopped=False,
        )
        assert status == ScanCycleStatus.FAILED

    def test_completed_even_with_stop_if_all_processed(self, scanner):
        """Test COMPLETED when stop but all symbols already processed."""
        status = scanner._determine_cycle_status(
            symbols_total=5,
            symbols_processed=5,
            errors_count=0,
            was_stopped=True,
        )
        assert status == ScanCycleStatus.COMPLETED


class TestBatchSplitting:
    """Tests for _split_into_batches method."""

    def test_split_exact_batches(self, scanner):
        """Test splitting into exact batch sizes."""
        symbols = [create_mock_symbol(f"S{i}") for i in range(20)]
        batches = scanner._split_into_batches(symbols, batch_size=10)

        assert len(batches) == 2
        assert len(batches[0]) == 10
        assert len(batches[1]) == 10

    def test_split_uneven_batches(self, scanner):
        """Test splitting with remainder."""
        symbols = [create_mock_symbol(f"S{i}") for i in range(25)]
        batches = scanner._split_into_batches(symbols, batch_size=10)

        assert len(batches) == 3
        assert len(batches[0]) == 10
        assert len(batches[1]) == 10
        assert len(batches[2]) == 5

    def test_split_single_batch(self, scanner):
        """Test when all symbols fit in one batch."""
        symbols = [create_mock_symbol(f"S{i}") for i in range(5)]
        batches = scanner._split_into_batches(symbols, batch_size=10)

        assert len(batches) == 1
        assert len(batches[0]) == 5

    def test_split_empty_list(self, scanner):
        """Test splitting empty list."""
        batches = scanner._split_into_batches([], batch_size=10)

        assert len(batches) == 0

    def test_split_zero_batch_size(self, scanner):
        """Test splitting with zero batch size returns all in one batch."""
        symbols = [create_mock_symbol(f"S{i}") for i in range(5)]
        batches = scanner._split_into_batches(symbols, batch_size=0)

        assert len(batches) == 1
        assert len(batches[0]) == 5


class TestSetOrchestrator:
    """Tests for set_orchestrator method."""

    def test_set_orchestrator(self, mock_repository, mock_orchestrator):
        """Test that orchestrator can be set after initialization."""
        scanner = SignalScannerService(mock_repository, orchestrator=None)
        assert scanner._orchestrator is None

        scanner.set_orchestrator(mock_orchestrator)

        assert scanner._orchestrator is mock_orchestrator
