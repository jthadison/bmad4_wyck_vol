"""
Integration Tests for Scanner WebSocket Broadcasting (Story 20.5b)

Tests for:
- AC1: Signal broadcast on detection
- AC2: No broadcast when no signal
- AC3: Multiple signals broadcast individually
- AC4/AC5: Auto-restart on startup
- AC6: Scanner status WebSocket events

Author: Story 20.5b (WebSocket Signal Broadcasting & Auto-Restart)
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.websocket import ConnectionManager
from src.orm.scanner import ScannerConfigORM
from src.repositories.scanner_repository import ScannerRepository
from src.services.signal_scanner_service import (
    SignalScannerService,
)


@pytest.fixture
def patch_scanner_logger():
    """
    Patch the scanner service logger to avoid structlog 'event' parameter conflict.

    The production code uses `logger.info(..., event=event)` which conflicts with
    structlog's reserved 'event' keyword argument. This fixture patches the logger
    to use a mock that doesn't have this limitation.
    """
    with patch("src.services.signal_scanner_service.logger") as mock_logger:
        mock_logger.info = MagicMock()
        mock_logger.error = MagicMock()
        mock_logger.warning = MagicMock()
        mock_logger.debug = MagicMock()
        yield mock_logger


# Test constants
DEFAULT_SCAN_INTERVAL = 300
DEFAULT_BATCH_SIZE = 10


@pytest.fixture
def mock_websocket_manager():
    """Provide a mock ConnectionManager for WebSocket testing."""
    manager = MagicMock(spec=ConnectionManager)
    manager.broadcast = AsyncMock()
    return manager


@pytest.fixture
def mock_orchestrator():
    """Provide a mock MasterOrchestrator for testing."""
    orchestrator = MagicMock()
    orchestrator.analyze_symbol = AsyncMock(return_value=[])
    return orchestrator


@pytest.fixture
async def scanner_config_in_db(db_session: AsyncSession) -> ScannerConfigORM:
    """Create scanner config in database."""
    config = ScannerConfigORM(
        id=uuid4(),
        scan_interval_seconds=DEFAULT_SCAN_INTERVAL,
        batch_size=DEFAULT_BATCH_SIZE,
        session_filter_enabled=True,
        is_running=False,
        last_cycle_at=None,
        updated_at=datetime.now(UTC),
    )
    db_session.add(config)
    await db_session.commit()
    await db_session.refresh(config)
    return config


@pytest.fixture
async def scanner_config_running(db_session: AsyncSession) -> ScannerConfigORM:
    """Create scanner config in database with is_running=True."""
    config = ScannerConfigORM(
        id=uuid4(),
        scan_interval_seconds=DEFAULT_SCAN_INTERVAL,
        batch_size=DEFAULT_BATCH_SIZE,
        session_filter_enabled=True,
        is_running=True,  # Was running before shutdown
        last_cycle_at=None,
        updated_at=datetime.now(UTC),
    )
    db_session.add(config)
    await db_session.commit()
    await db_session.refresh(config)
    return config


def create_mock_signal(
    symbol: str = "EURUSD",
    pattern_type: str = "Spring",
    confidence: int = 85,
):
    """Create a mock TradeSignal for testing."""
    signal = MagicMock()
    signal.signal_id = uuid4()
    signal.symbol = symbol
    signal.pattern_type = pattern_type
    signal.confidence_score = confidence
    signal.entry_price = Decimal("1.0850")
    signal.stop_price = Decimal("1.0820")
    signal.target_price = Decimal("1.0920")
    signal.timeframe = "1H"
    return signal


class TestSignalBroadcasting:
    """Test signal broadcasting via WebSocket (AC1, AC2, AC3)."""

    @pytest.mark.asyncio
    async def test_signal_broadcast_on_detection(
        self,
        db_session: AsyncSession,
        scanner_config_in_db: ScannerConfigORM,
        mock_websocket_manager,
    ):
        """AC1: When a signal is detected, it should be broadcast via WebSocket."""
        repository = ScannerRepository(db_session)
        scanner = SignalScannerService(
            repository=repository,
            websocket_manager=mock_websocket_manager,
        )

        # Create a mock signal
        mock_signal = create_mock_signal()

        # Broadcast the signal
        await scanner._broadcast_signal(mock_signal)

        # Verify broadcast was called
        mock_websocket_manager.broadcast.assert_called_once()
        call_args = mock_websocket_manager.broadcast.call_args[0][0]

        assert call_args["type"] == "signal:new"
        assert "timestamp" in call_args
        assert call_args["data"]["symbol"] == "EURUSD"
        assert call_args["data"]["pattern"] == "Spring"
        assert call_args["data"]["direction"] == "long"
        assert call_args["data"]["confidence"] == 85
        assert call_args["data"]["source"] == "scanner"

    @pytest.mark.asyncio
    async def test_signal_broadcast_utad_is_short(
        self,
        db_session: AsyncSession,
        scanner_config_in_db: ScannerConfigORM,
        mock_websocket_manager,
    ):
        """AC1: UTAD patterns should have direction 'short'."""
        repository = ScannerRepository(db_session)
        scanner = SignalScannerService(
            repository=repository,
            websocket_manager=mock_websocket_manager,
        )

        mock_signal = create_mock_signal(pattern_type="UTAD")
        await scanner._broadcast_signal(mock_signal)

        call_args = mock_websocket_manager.broadcast.call_args[0][0]
        assert call_args["data"]["direction"] == "short"

    @pytest.mark.asyncio
    async def test_no_broadcast_when_no_websocket_manager(
        self,
        db_session: AsyncSession,
        scanner_config_in_db: ScannerConfigORM,
    ):
        """AC2: No broadcast should occur if WebSocket manager is None."""
        repository = ScannerRepository(db_session)
        scanner = SignalScannerService(
            repository=repository,
            websocket_manager=None,  # No WebSocket manager
        )

        mock_signal = create_mock_signal()

        # Should not raise an error
        await scanner._broadcast_signal(mock_signal)

    @pytest.mark.asyncio
    async def test_broadcast_failure_does_not_crash(
        self,
        db_session: AsyncSession,
        scanner_config_in_db: ScannerConfigORM,
        mock_websocket_manager,
    ):
        """Broadcast failures should be logged but not crash the scan."""
        mock_websocket_manager.broadcast = AsyncMock(side_effect=Exception("WebSocket error"))

        repository = ScannerRepository(db_session)
        scanner = SignalScannerService(
            repository=repository,
            websocket_manager=mock_websocket_manager,
        )

        mock_signal = create_mock_signal()

        # Should not raise an error
        await scanner._broadcast_signal(mock_signal)

        # Should have incremented error count
        assert scanner._broadcast_errors == 1

    @pytest.mark.asyncio
    async def test_multiple_signals_increment_counter(
        self,
        db_session: AsyncSession,
        scanner_config_in_db: ScannerConfigORM,
        mock_websocket_manager,
    ):
        """AC3: Each signal broadcast should increment the counter."""
        repository = ScannerRepository(db_session)
        scanner = SignalScannerService(
            repository=repository,
            websocket_manager=mock_websocket_manager,
        )

        # Broadcast 3 signals
        for i in range(3):
            mock_signal = create_mock_signal(symbol=f"SIGNAL{i}")
            await scanner._broadcast_signal(mock_signal)

        assert scanner._signals_broadcast == 3
        assert mock_websocket_manager.broadcast.call_count == 3


class TestStatusBroadcasting:
    """Test scanner status broadcasting via WebSocket (AC6)."""

    @pytest.mark.asyncio
    async def test_status_change_broadcast_on_start(
        self,
        db_session: AsyncSession,
        scanner_config_in_db: ScannerConfigORM,
        mock_websocket_manager,
        patch_scanner_logger,
    ):
        """AC6: Scanner start should broadcast status_changed event."""
        repository = ScannerRepository(db_session)
        scanner = SignalScannerService(
            repository=repository,
            websocket_manager=mock_websocket_manager,
        )

        await scanner._broadcast_status_change(is_running=True, event="started")

        mock_websocket_manager.broadcast.assert_called_once()
        call_args = mock_websocket_manager.broadcast.call_args[0][0]

        assert call_args["type"] == "scanner:status_changed"
        assert "timestamp" in call_args
        assert call_args["data"]["is_running"] is True
        assert call_args["data"]["event"] == "started"

    @pytest.mark.asyncio
    async def test_status_change_broadcast_on_stop(
        self,
        db_session: AsyncSession,
        scanner_config_in_db: ScannerConfigORM,
        mock_websocket_manager,
        patch_scanner_logger,
    ):
        """AC6: Scanner stop should broadcast status_changed event."""
        repository = ScannerRepository(db_session)
        scanner = SignalScannerService(
            repository=repository,
            websocket_manager=mock_websocket_manager,
        )

        await scanner._broadcast_status_change(is_running=False, event="stopped")

        call_args = mock_websocket_manager.broadcast.call_args[0][0]
        assert call_args["data"]["is_running"] is False
        assert call_args["data"]["event"] == "stopped"

    @pytest.mark.asyncio
    async def test_status_change_broadcast_auto_started(
        self,
        db_session: AsyncSession,
        scanner_config_in_db: ScannerConfigORM,
        mock_websocket_manager,
        patch_scanner_logger,
    ):
        """AC6: Auto-start should broadcast with 'auto_started' event."""
        repository = ScannerRepository(db_session)
        scanner = SignalScannerService(
            repository=repository,
            websocket_manager=mock_websocket_manager,
        )

        await scanner._broadcast_status_change(is_running=True, event="auto_started")

        call_args = mock_websocket_manager.broadcast.call_args[0][0]
        assert call_args["data"]["event"] == "auto_started"

    @pytest.mark.asyncio
    async def test_status_broadcast_failure_does_not_crash(
        self,
        db_session: AsyncSession,
        scanner_config_in_db: ScannerConfigORM,
        mock_websocket_manager,
        patch_scanner_logger,
    ):
        """Status broadcast failures should not crash the scanner."""
        mock_websocket_manager.broadcast = AsyncMock(side_effect=Exception("WebSocket error"))

        repository = ScannerRepository(db_session)
        scanner = SignalScannerService(
            repository=repository,
            websocket_manager=mock_websocket_manager,
        )

        # Should not raise an error
        await scanner._broadcast_status_change(is_running=True, event="started")


class TestAutoRestart:
    """Test auto-restart on startup (AC4, AC5)."""

    @pytest.mark.asyncio
    async def test_auto_restart_when_config_is_running_true(
        self,
        db_session: AsyncSession,
        scanner_config_running: ScannerConfigORM,
    ):
        """AC4: Scanner should auto-start if config.is_running was True."""
        repository = ScannerRepository(db_session)

        # Verify the config shows is_running=True
        config = await repository.get_config()
        assert config.is_running is True

    @pytest.mark.asyncio
    async def test_no_auto_restart_when_config_is_running_false(
        self,
        db_session: AsyncSession,
        scanner_config_in_db: ScannerConfigORM,
    ):
        """AC4: Scanner should not auto-start if config.is_running was False."""
        repository = ScannerRepository(db_session)

        # Verify the config shows is_running=False
        config = await repository.get_config()
        assert config.is_running is False


class TestScannerIntegrationWithBroadcast:
    """Test full scanner integration with broadcasting."""

    @pytest.mark.asyncio
    async def test_scanner_start_broadcasts_status(
        self,
        db_session: AsyncSession,
        scanner_config_in_db: ScannerConfigORM,
        mock_websocket_manager,
        patch_scanner_logger,
    ):
        """Starting scanner should broadcast status change."""
        repository = ScannerRepository(db_session)
        scanner = SignalScannerService(
            repository=repository,
            websocket_manager=mock_websocket_manager,
        )

        await scanner.start()

        # Verify status broadcast was called
        status_broadcasts = [
            call
            for call in mock_websocket_manager.broadcast.call_args_list
            if call[0][0].get("type") == "scanner:status_changed"
        ]
        assert len(status_broadcasts) == 1
        assert status_broadcasts[0][0][0]["data"]["is_running"] is True
        assert status_broadcasts[0][0][0]["data"]["event"] == "started"

        # Clean up - stop the scanner
        await scanner.stop()

    @pytest.mark.asyncio
    async def test_scanner_stop_broadcasts_status(
        self,
        db_session: AsyncSession,
        scanner_config_in_db: ScannerConfigORM,
        mock_websocket_manager,
        patch_scanner_logger,
    ):
        """Stopping scanner should broadcast status change."""
        repository = ScannerRepository(db_session)
        scanner = SignalScannerService(
            repository=repository,
            websocket_manager=mock_websocket_manager,
        )

        # Start then stop
        await scanner.start()
        mock_websocket_manager.broadcast.reset_mock()
        await scanner.stop()

        # Verify stop broadcast
        status_broadcasts = [
            call
            for call in mock_websocket_manager.broadcast.call_args_list
            if call[0][0].get("type") == "scanner:status_changed"
        ]
        assert len(status_broadcasts) == 1
        assert status_broadcasts[0][0][0]["data"]["is_running"] is False
        assert status_broadcasts[0][0][0]["data"]["event"] == "stopped"

    @pytest.mark.asyncio
    async def test_scanner_start_no_broadcast_with_flag(
        self,
        db_session: AsyncSession,
        scanner_config_in_db: ScannerConfigORM,
        mock_websocket_manager,
        patch_scanner_logger,
    ):
        """Starting with broadcast=False should not broadcast status."""
        repository = ScannerRepository(db_session)
        scanner = SignalScannerService(
            repository=repository,
            websocket_manager=mock_websocket_manager,
        )

        # Start with broadcast=False (used for auto-restart)
        await scanner.start(broadcast=False)

        # Verify NO status broadcast was called
        status_broadcasts = [
            call
            for call in mock_websocket_manager.broadcast.call_args_list
            if call[0][0].get("type") == "scanner:status_changed"
        ]
        assert len(status_broadcasts) == 0

        # Clean up - stop the scanner
        await scanner.stop()

    @pytest.mark.asyncio
    async def test_auto_start_sends_auto_started_event_only(
        self,
        db_session: AsyncSession,
        scanner_config_in_db: ScannerConfigORM,
        mock_websocket_manager,
        patch_scanner_logger,
    ):
        """Auto-start should only send auto_started, not started event."""
        repository = ScannerRepository(db_session)
        scanner = SignalScannerService(
            repository=repository,
            websocket_manager=mock_websocket_manager,
        )

        # Simulate auto-start: broadcast=False then manual auto_started event
        await scanner.start(broadcast=False)
        await scanner._broadcast_status_change(is_running=True, event="auto_started")

        # Verify only ONE status broadcast (auto_started)
        status_broadcasts = [
            call
            for call in mock_websocket_manager.broadcast.call_args_list
            if call[0][0].get("type") == "scanner:status_changed"
        ]
        assert len(status_broadcasts) == 1
        assert status_broadcasts[0][0][0]["data"]["event"] == "auto_started"

        # Clean up - stop the scanner
        await scanner.stop()


class TestWebSocketManagerSetup:
    """Test WebSocket manager configuration."""

    @pytest.mark.asyncio
    async def test_set_websocket_manager(
        self,
        db_session: AsyncSession,
        scanner_config_in_db: ScannerConfigORM,
        mock_websocket_manager,
    ):
        """WebSocket manager can be set after initialization."""
        repository = ScannerRepository(db_session)
        scanner = SignalScannerService(
            repository=repository,
            websocket_manager=None,
        )

        assert scanner._websocket_manager is None

        scanner.set_websocket_manager(mock_websocket_manager)

        assert scanner._websocket_manager == mock_websocket_manager

    @pytest.mark.asyncio
    async def test_session_factory_pattern(
        self,
        db_session: AsyncSession,
        scanner_config_in_db: ScannerConfigORM,
        mock_websocket_manager,
    ):
        """Scanner can be initialized with session factory."""
        mock_session_factory = MagicMock()
        mock_session_factory.return_value = db_session

        scanner = SignalScannerService(
            session_factory=mock_session_factory,
            websocket_manager=mock_websocket_manager,
        )

        assert scanner._session_factory == mock_session_factory
