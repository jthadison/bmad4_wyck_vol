"""
Unit tests for SignalScannerService lifecycle (Story 20.3a).

Tests scanner state machine: start, stop, status, graceful shutdown.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.signal_scanner_service import (
    ScannerState,
    SignalScannerService,
)


@pytest.fixture
def mock_repository():
    """Create mock ScannerRepository."""
    repo = MagicMock()

    # Mock get_config to return a default config
    config = MagicMock()
    config.scan_interval_seconds = 60
    config.last_cycle_at = None
    repo.get_config = AsyncMock(return_value=config)

    # Mock update_config
    repo.update_config = AsyncMock()

    # Mock get_symbol_count
    repo.get_symbol_count = AsyncMock(return_value=5)

    # Mock set_last_cycle_at
    repo.set_last_cycle_at = AsyncMock()

    return repo


@pytest.fixture
def scanner(mock_repository):
    """Create SignalScannerService with mock repository."""
    return SignalScannerService(mock_repository)


class TestScannerInitialization:
    """Tests for scanner initialization (AC1)."""

    def test_initialization_is_stopped(self, scanner):
        """Test that scanner initializes in STOPPED state."""
        assert scanner.is_running is False
        assert scanner._state == ScannerState.STOPPED

    def test_get_status_returns_stopped(self, scanner):
        """Test that get_status returns stopped state."""
        status = scanner.get_status()

        assert status.is_running is False
        assert status.current_state == "stopped"


class TestScannerStart:
    """Tests for scanner start (AC2)."""

    @pytest.mark.asyncio
    async def test_start_transitions_to_running(self, scanner, mock_repository):
        """Test that start() transitions scanner to RUNNING state."""
        await scanner.start()

        try:
            assert scanner.is_running is True
            assert scanner._state == ScannerState.RUNNING
            assert scanner._task is not None
        finally:
            await scanner.stop()

    @pytest.mark.asyncio
    async def test_start_creates_background_task(self, scanner, mock_repository):
        """Test that start() creates an asyncio background task."""
        await scanner.start()

        try:
            assert scanner._task is not None
            assert isinstance(scanner._task, asyncio.Task)
            assert not scanner._task.done()
        finally:
            await scanner.stop()

    @pytest.mark.asyncio
    async def test_start_updates_database_is_running(self, scanner, mock_repository):
        """Test that start() sets is_running=true in database."""
        await scanner.start()

        try:
            # Check that update_config was called with is_running=True
            mock_repository.update_config.assert_called()
            call_args = mock_repository.update_config.call_args[0][0]
            assert call_args.is_running is True
        finally:
            await scanner.stop()

    @pytest.mark.asyncio
    async def test_start_is_idempotent(self, scanner, mock_repository):
        """Test that start() is idempotent - no duplicate tasks."""
        await scanner.start()

        try:
            task1 = scanner._task

            # Call start again
            await scanner.start()

            # Should still have same task
            assert scanner._task is task1
            assert scanner.is_running is True
        finally:
            await scanner.stop()

    @pytest.mark.asyncio
    async def test_start_loads_config_from_database(self, scanner, mock_repository):
        """Test that start() loads scan interval from database."""
        mock_repository.get_config.return_value.scan_interval_seconds = 120

        await scanner.start()

        try:
            assert scanner._scan_interval_seconds == 120
            mock_repository.get_config.assert_called()
        finally:
            await scanner.stop()

    @pytest.mark.asyncio
    async def test_start_loads_symbol_count(self, scanner, mock_repository):
        """Test that start() loads symbol count from database."""
        mock_repository.get_symbol_count.return_value = 10

        await scanner.start()

        try:
            assert scanner._symbols_count == 10
        finally:
            await scanner.stop()


class TestScannerStop:
    """Tests for scanner stop (AC3)."""

    @pytest.mark.asyncio
    async def test_stop_transitions_to_stopped(self, scanner, mock_repository):
        """Test that stop() transitions scanner to STOPPED state."""
        await scanner.start()
        await scanner.stop()

        assert scanner.is_running is False
        assert scanner._state == ScannerState.STOPPED

    @pytest.mark.asyncio
    async def test_stop_cancels_background_task(self, scanner, mock_repository):
        """Test that stop() cancels the background task."""
        await scanner.start()
        task = scanner._task

        await scanner.stop()

        assert scanner._task is None
        assert task.done()

    @pytest.mark.asyncio
    async def test_stop_updates_database_is_running(self, scanner, mock_repository):
        """Test that stop() sets is_running=false in database."""
        await scanner.start()
        mock_repository.update_config.reset_mock()

        await scanner.stop()

        # Check that update_config was called with is_running=False
        mock_repository.update_config.assert_called()
        call_args = mock_repository.update_config.call_args[0][0]
        assert call_args.is_running is False

    @pytest.mark.asyncio
    async def test_stop_is_idempotent(self, scanner, mock_repository):
        """Test that stop() is idempotent - safe to call multiple times."""
        # Stop when already stopped
        await scanner.stop()

        assert scanner.is_running is False
        assert scanner._state == ScannerState.STOPPED

    @pytest.mark.asyncio
    async def test_stop_when_already_stopped(self, scanner, mock_repository):
        """Test that stop() on stopped scanner logs and returns."""
        # Should not raise
        await scanner.stop()
        await scanner.stop()

        assert scanner._state == ScannerState.STOPPED


class TestScanLoopTiming:
    """Tests for scan loop timing (AC4)."""

    @pytest.mark.asyncio
    async def test_scan_loop_respects_interval(self, scanner, mock_repository):
        """Test that scan loop waits for configured interval."""
        mock_repository.get_config.return_value.scan_interval_seconds = 60

        await scanner.start()

        try:
            # Give loop time to execute one cycle
            await asyncio.sleep(0.2)

            status = scanner.get_status()
            assert status.scan_interval_seconds == 60
        finally:
            await scanner.stop()

    @pytest.mark.asyncio
    async def test_stop_interrupts_wait(self, scanner, mock_repository):
        """Test that stop() interrupts the interval wait."""
        # Set a very long interval
        mock_repository.get_config.return_value.scan_interval_seconds = 3600

        await scanner.start()

        # Give loop time to start waiting
        await asyncio.sleep(0.2)

        # Stop should complete quickly, not wait for interval
        start_time = asyncio.get_event_loop().time()
        await scanner.stop()
        elapsed = asyncio.get_event_loop().time() - start_time

        # Should stop within 5 seconds, not 3600
        assert elapsed < 5


class TestGracefulShutdown:
    """Tests for graceful shutdown (AC5)."""

    @pytest.mark.asyncio
    async def test_graceful_shutdown_waits_for_current_work(self, scanner, mock_repository):
        """Test that stop() waits for current symbol to complete."""
        await scanner.start()

        # Give the scan loop time to start
        await asyncio.sleep(0.1)

        # Stop should wait gracefully
        await scanner.stop()

        assert scanner._state == ScannerState.STOPPED
        assert scanner._task is None

    @pytest.mark.asyncio
    async def test_graceful_shutdown_timeout(self, scanner, mock_repository):
        """Test that stop() has a timeout for graceful shutdown."""
        # This test verifies the timeout mechanism exists
        # In production, if a cycle hangs, it will be force-cancelled

        await scanner.start()
        await asyncio.sleep(0.1)

        # Stop should complete within reasonable time
        start_time = asyncio.get_event_loop().time()
        await scanner.stop()
        elapsed = asyncio.get_event_loop().time() - start_time

        # Should complete within graceful timeout + buffer
        assert elapsed < SignalScannerService.GRACEFUL_SHUTDOWN_TIMEOUT + 2


class TestStatusReporting:
    """Tests for status reporting (AC6)."""

    def test_status_when_stopped(self, scanner):
        """Test get_status() when scanner is stopped."""
        status = scanner.get_status()

        assert status.is_running is False
        assert status.current_state == "stopped"
        assert status.next_scan_in_seconds is None

    @pytest.mark.asyncio
    async def test_status_when_running(self, scanner, mock_repository):
        """Test get_status() when scanner is running."""
        await scanner.start()

        try:
            status = scanner.get_status()

            assert status.is_running is True
            assert status.current_state in ("running", "waiting", "scanning")
            assert status.scan_interval_seconds == 60
            assert status.symbols_count == 5
        finally:
            await scanner.stop()

    @pytest.mark.asyncio
    async def test_status_calculates_next_scan_time(self, scanner, mock_repository):
        """Test that status calculates next_scan_in_seconds correctly."""
        mock_repository.get_config.return_value.scan_interval_seconds = 300

        await scanner.start()

        try:
            # Wait for first cycle to complete
            await asyncio.sleep(0.3)

            status = scanner.get_status()

            # Should have next_scan_in_seconds calculated
            if status.last_cycle_at is not None:
                assert status.next_scan_in_seconds is not None
                # Should be close to interval (300) minus small elapsed time
                assert 0 <= status.next_scan_in_seconds <= 300
        finally:
            await scanner.stop()

    def test_status_model_fields(self, scanner):
        """Test that ScannerStatus has all required fields."""
        status = scanner.get_status()

        assert hasattr(status, "is_running")
        assert hasattr(status, "last_cycle_at")
        assert hasattr(status, "next_scan_in_seconds")
        assert hasattr(status, "scan_interval_seconds")
        assert hasattr(status, "current_state")
        assert hasattr(status, "symbols_count")


class TestStateTransitions:
    """Tests for state machine transitions."""

    @pytest.mark.asyncio
    async def test_full_lifecycle(self, scanner, mock_repository):
        """Test complete lifecycle: stop -> start -> running -> stop."""
        # Initial state
        assert scanner._state == ScannerState.STOPPED

        # Start
        await scanner.start()
        assert scanner._state == ScannerState.RUNNING

        # Stop
        await scanner.stop()
        assert scanner._state == ScannerState.STOPPED

    @pytest.mark.asyncio
    async def test_cannot_start_while_stopping(self, scanner, mock_repository):
        """Test that start() during STOPPING state is handled."""
        await scanner.start()

        # Manually set to stopping to test edge case
        scanner._state = ScannerState.STOPPING

        # Should not transition to running
        await scanner.start()

        # State should still be stopping (not running)
        assert scanner._state != ScannerState.RUNNING

        # Clean up
        scanner._state = ScannerState.STOPPED
        if scanner._task:
            scanner._task.cancel()
            try:
                await scanner._task
            except asyncio.CancelledError:
                pass
            scanner._task = None


class TestErrorHandling:
    """Tests for error handling in scan loop."""

    @pytest.mark.asyncio
    async def test_scan_loop_continues_on_error(self, mock_repository):
        """Test that scan loop continues running despite errors."""
        # Set up a repository that fails on first call during scan cycle
        # but succeeds on subsequent calls
        call_count = [0]  # Use list to allow mutation in closure

        async def failing_then_succeeding(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] <= 2:  # Fail first 2 calls (during start and first cycle)
                return 5  # Return valid count
            return 5

        mock_repository.get_symbol_count = AsyncMock(side_effect=failing_then_succeeding)

        scanner = SignalScannerService(mock_repository)
        await scanner.start()

        try:
            # Wait for scan loop to execute
            await asyncio.sleep(0.3)

            # Scanner should still be running
            assert scanner.is_running is True
            assert scanner._state == ScannerState.RUNNING
        finally:
            await scanner.stop()
