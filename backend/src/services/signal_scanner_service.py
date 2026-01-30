"""
Signal Scanner Service (Story 20.3a).

Background service for automated Wyckoff pattern scanning.
Manages scanner lifecycle: start, stop, status reporting.

State Machine:
    STOPPED --(start)--> STARTING --(task created)--> RUNNING
    RUNNING --(stop)--> STOPPING --(task cancelled)--> STOPPED

Author: Story 20.3a
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING

import structlog
from pydantic import BaseModel, Field

from src.models.scanner_persistence import ScannerConfigUpdate

if TYPE_CHECKING:
    from src.repositories.scanner_repository import ScannerRepository

logger = structlog.get_logger(__name__)


class ScannerState(str, Enum):
    """Scanner lifecycle state."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"


class ScannerStatus(BaseModel):
    """
    Scanner status snapshot.

    Provides current state, timing information, and statistics.
    """

    is_running: bool = Field(description="Whether scanner is actively running")
    last_cycle_at: datetime | None = Field(
        default=None, description="When last scan cycle completed"
    )
    next_scan_in_seconds: int | None = Field(
        default=None, description="Seconds until next scan (None if stopped)"
    )
    scan_interval_seconds: int = Field(description="Configured scan interval")
    current_state: str = Field(
        description="Current state: stopped, starting, running, waiting, scanning, stopping"
    )
    symbols_count: int = Field(default=0, description="Number of symbols in watchlist")


class SignalScannerService:
    """
    Background service for automated Wyckoff pattern scanning.

    Manages scanner lifecycle with proper state transitions,
    graceful shutdown, and interruptible scan cycles.

    Usage:
        scanner = SignalScannerService(repository)
        await scanner.start()  # Begin background scanning
        ...
        await scanner.stop()   # Graceful shutdown
    """

    # Timeout for graceful shutdown (seconds)
    GRACEFUL_SHUTDOWN_TIMEOUT = 10

    def __init__(
        self,
        repository: ScannerRepository,
    ):
        """
        Initialize scanner service.

        Args:
            repository: Scanner repository for database operations
        """
        self._repository = repository
        self._state = ScannerState.STOPPED
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task | None = None
        self._current_symbol: str | None = None
        self._last_cycle_at: datetime | None = None
        self._scan_interval_seconds: int = 300  # Default, updated from config
        self._symbols_count: int = 0
        self._is_scanning: bool = False

    @property
    def is_running(self) -> bool:
        """Check if scanner is running."""
        return self._state == ScannerState.RUNNING

    async def start(self) -> None:
        """
        Start the scanner background task.

        Idempotent: safe to call multiple times.
        Non-blocking: returns immediately after starting task.

        State Transition: STOPPED -> STARTING -> RUNNING
        """
        if self._state == ScannerState.RUNNING:
            logger.info("scanner_already_running_ignoring_start_request")
            return

        if self._state == ScannerState.STARTING:
            logger.info("scanner_already_starting_ignoring_start_request")
            return

        if self._state == ScannerState.STOPPING:
            logger.warning("scanner_stopping_cannot_start")
            return

        logger.info("scanner_starting")
        self._state = ScannerState.STARTING

        # Load config from database
        config = await self._repository.get_config()
        self._scan_interval_seconds = config.scan_interval_seconds
        self._last_cycle_at = config.last_cycle_at

        # Load symbol count
        self._symbols_count = await self._repository.get_symbol_count()

        # Update database state
        await self._repository.update_config(ScannerConfigUpdate(is_running=True))

        # Reset stop event for new run
        self._stop_event.clear()

        # Create background task
        self._task = asyncio.create_task(self._scan_loop())

        self._state = ScannerState.RUNNING
        logger.info("scanner_started", scan_interval=self._scan_interval_seconds)

    async def stop(self) -> None:
        """
        Stop the scanner gracefully.

        Idempotent: safe to call multiple times.
        Waits for current symbol to complete before stopping.

        State Transition: RUNNING -> STOPPING -> STOPPED
        """
        if self._state == ScannerState.STOPPED:
            logger.info("scanner_already_stopped_ignoring_stop_request")
            return

        if self._state == ScannerState.STOPPING:
            logger.info("scanner_already_stopping")
            return

        logger.info("scanner_stopping")
        self._state = ScannerState.STOPPING

        # Signal stop to scan loop
        self._stop_event.set()

        # Wait for task to finish with timeout
        if self._task is not None:
            try:
                await asyncio.wait_for(
                    self._task,
                    timeout=self.GRACEFUL_SHUTDOWN_TIMEOUT,
                )
                logger.info("scanner_stopped_gracefully")
            except asyncio.TimeoutError:
                logger.warning("scanner_graceful_shutdown_timeout_forcing_cancel")
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
            except asyncio.CancelledError:
                pass

        self._task = None

        # Update database state
        await self._repository.update_config(ScannerConfigUpdate(is_running=False))

        self._state = ScannerState.STOPPED
        logger.info("scanner_stopped")

    def get_status(self) -> ScannerStatus:
        """
        Get current scanner status.

        Returns:
            ScannerStatus with current state and timing info
        """
        # Determine display state
        if self._state == ScannerState.STOPPED:
            current_state = "stopped"
        elif self._state == ScannerState.STARTING:
            current_state = "starting"
        elif self._state == ScannerState.STOPPING:
            current_state = "stopping"
        elif self._is_scanning:
            current_state = "scanning"
        else:
            current_state = "waiting"

        # Calculate next scan time
        next_scan_in_seconds: int | None = None
        if self._state == ScannerState.RUNNING and self._last_cycle_at is not None:
            elapsed = (datetime.now(UTC) - self._last_cycle_at).total_seconds()
            remaining = self._scan_interval_seconds - elapsed
            next_scan_in_seconds = max(0, int(remaining))

        return ScannerStatus(
            is_running=self.is_running,
            last_cycle_at=self._last_cycle_at,
            next_scan_in_seconds=next_scan_in_seconds,
            scan_interval_seconds=self._scan_interval_seconds,
            current_state=current_state,
            symbols_count=self._symbols_count,
        )

    async def _scan_loop(self) -> None:
        """
        Main scan loop.

        Runs scan cycles at configured interval until stop is requested.
        Uses interruptible wait pattern for responsive shutdown.
        """
        logger.info("scanner_loop_started")

        while not self._stop_event.is_set():
            try:
                # Execute scan cycle
                await self._scan_cycle()

                # Update last cycle time
                self._last_cycle_at = datetime.now(UTC)
                await self._repository.set_last_cycle_at(self._last_cycle_at)

                logger.info(
                    "scan_cycle_complete_waiting",
                    wait_seconds=self._scan_interval_seconds,
                )

                # Interruptible wait using stop_event
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=self._scan_interval_seconds,
                    )
                    # Stop event was set, exit loop
                    logger.info("scanner_stop_event_received")
                    break
                except asyncio.TimeoutError:
                    # Normal timeout, continue to next cycle
                    pass

            except asyncio.CancelledError:
                logger.info("scanner_loop_cancelled")
                break
            except Exception as e:
                logger.error("scanner_loop_error", error=str(e))
                # Continue running despite errors
                await asyncio.sleep(5)  # Brief pause before retry

        logger.info("scanner_loop_stopped")

    async def _scan_cycle(self) -> None:
        """
        Execute a single scan cycle.

        Placeholder implementation for Story 20.3a.
        Full implementation in Story 20.3b.
        """
        self._is_scanning = True
        try:
            # Refresh symbol count
            self._symbols_count = await self._repository.get_symbol_count()

            # Placeholder: actual scanning logic in 20.3b
            logger.debug(
                "scan_cycle_executing",
                symbols_count=self._symbols_count,
            )

            # Brief placeholder delay (to be replaced with actual scanning)
            if not self._stop_event.is_set():
                await asyncio.sleep(0.1)

        finally:
            self._is_scanning = False
