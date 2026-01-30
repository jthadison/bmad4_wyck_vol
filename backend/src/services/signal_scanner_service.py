"""
Signal Scanner Service (Story 20.3a, 20.3b).

Background service for automated Wyckoff pattern scanning.
Manages scanner lifecycle: start, stop, status reporting.
Integrates with orchestrator for symbol analysis.

State Machine:
    STOPPED --(start)--> STARTING --(task created)--> RUNNING
    RUNNING --(stop)--> STOPPING --(task cancelled)--> STOPPED

Author: Story 20.3a, 20.3b
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

import structlog
from pydantic import BaseModel, Field

from src.models.scanner_persistence import (
    ScanCycleStatus,
    ScannerConfigUpdate,
    ScannerHistoryCreate,
    WatchlistSymbol,
)

if TYPE_CHECKING:
    from src.orchestrator.master_orchestrator import MasterOrchestrator
    from src.repositories.scanner_repository import ScannerRepository

logger = structlog.get_logger(__name__)


@dataclass
class ScanCycleResult:
    """
    Result of a single scan cycle.

    Contains metrics and signals from analyzing all symbols.
    """

    cycle_started_at: datetime
    cycle_ended_at: datetime
    symbols_scanned: int
    signals_generated: int
    errors_count: int
    status: ScanCycleStatus
    signals: list[Any] = field(default_factory=list)


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
        scanner = SignalScannerService(repository, orchestrator)
        await scanner.start()  # Begin background scanning
        ...
        await scanner.stop()   # Graceful shutdown
    """

    # Timeout for graceful shutdown (seconds)
    GRACEFUL_SHUTDOWN_TIMEOUT = 10

    # Default batch delay in milliseconds
    DEFAULT_BATCH_DELAY_MS = 100

    def __init__(
        self,
        repository: ScannerRepository,
        orchestrator: MasterOrchestrator | None = None,
    ):
        """
        Initialize scanner service.

        Args:
            repository: Scanner repository for database operations
            orchestrator: MasterOrchestrator for symbol analysis (optional)
        """
        self._repository = repository
        self._orchestrator = orchestrator
        self._state = ScannerState.STOPPED
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task | None = None
        self._current_symbol: str | None = None
        self._last_cycle_at: datetime | None = None
        self._scan_interval_seconds: int = 300  # Default, updated from config
        self._batch_size: int = 10  # Default, updated from config
        self._batch_delay_ms: int = self.DEFAULT_BATCH_DELAY_MS
        self._symbols_count: int = 0
        self._is_scanning: bool = False

    def set_orchestrator(self, orchestrator: MasterOrchestrator) -> None:
        """
        Set the orchestrator for symbol analysis.

        Args:
            orchestrator: MasterOrchestrator instance
        """
        self._orchestrator = orchestrator
        logger.info("scanner_orchestrator_set")

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
        self._batch_size = config.batch_size
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
                result = await self._scan_cycle()

                # Update last cycle time
                self._last_cycle_at = datetime.now(UTC)
                await self._repository.set_last_cycle_at(self._last_cycle_at)

                logger.info(
                    "scan_cycle_complete_waiting",
                    wait_seconds=self._scan_interval_seconds,
                    signals_generated=result.signals_generated,
                    errors_count=result.errors_count,
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

    async def _scan_cycle(self) -> ScanCycleResult:
        """
        Execute a single scan cycle (Story 20.3b).

        Processes all enabled watchlist symbols through the orchestrator,
        using batch processing with rate limiting for API protection.

        Returns:
            ScanCycleResult with metrics and detected signals
        """
        self._is_scanning = True
        cycle_started_at = datetime.now(UTC)
        symbols_scanned = 0
        signals_generated = 0
        errors_count = 0
        all_signals: list[Any] = []
        was_stopped = False

        try:
            # Get enabled symbols from repository
            enabled_symbols = await self._repository.get_enabled_symbols()
            self._symbols_count = len(enabled_symbols)
            total_symbols = len(enabled_symbols)

            logger.info(
                "scan_cycle_started",
                symbols_count=total_symbols,
                batch_size=self._batch_size,
            )

            if total_symbols == 0:
                logger.info("scan_cycle_no_symbols")
                return ScanCycleResult(
                    cycle_started_at=cycle_started_at,
                    cycle_ended_at=datetime.now(UTC),
                    symbols_scanned=0,
                    signals_generated=0,
                    errors_count=0,
                    status=ScanCycleStatus.COMPLETED,
                    signals=[],
                )

            # Split symbols into batches
            batches = self._split_into_batches(enabled_symbols, self._batch_size)
            total_batches = len(batches)

            for batch_index, batch in enumerate(batches):
                # Check stop event before each batch
                if self._stop_event.is_set():
                    logger.info(
                        "scan_cycle_interrupted_before_batch",
                        batch_number=batch_index + 1,
                        total_batches=total_batches,
                        symbols_processed=symbols_scanned,
                        total_symbols=total_symbols,
                    )
                    was_stopped = True
                    break

                logger.info(
                    "processing_batch",
                    batch_number=batch_index + 1,
                    total_batches=total_batches,
                    symbols_in_batch=len(batch),
                )

                # Process each symbol in the batch
                for symbol in batch:
                    # Check stop event before each symbol
                    if self._stop_event.is_set():
                        logger.info(
                            "scan_cycle_interrupted_mid_batch",
                            current_symbol=symbol.symbol,
                            symbols_processed=symbols_scanned,
                            total_symbols=total_symbols,
                        )
                        was_stopped = True
                        break

                    # Analyze symbol with error isolation
                    signals, error = await self._analyze_symbol(symbol)

                    symbols_scanned += 1

                    if error:
                        errors_count += 1
                    else:
                        all_signals.extend(signals)
                        signals_generated += len(signals)

                if was_stopped:
                    break

                # Add delay between batches (not after last batch)
                if batch_index < total_batches - 1 and not self._stop_event.is_set():
                    delay_seconds = self._batch_delay_ms / 1000.0
                    await asyncio.sleep(delay_seconds)

            # Determine cycle status
            status = self._determine_cycle_status(
                total_symbols, symbols_scanned, errors_count, was_stopped
            )

            cycle_ended_at = datetime.now(UTC)
            cycle_duration_ms = int((cycle_ended_at - cycle_started_at).total_seconds() * 1000)

            logger.info(
                "scan_cycle_complete",
                symbols_scanned=symbols_scanned,
                signals_generated=signals_generated,
                errors_count=errors_count,
                duration_ms=cycle_duration_ms,
                status=status.value,
            )

            # Record cycle in history
            result = ScanCycleResult(
                cycle_started_at=cycle_started_at,
                cycle_ended_at=cycle_ended_at,
                symbols_scanned=symbols_scanned,
                signals_generated=signals_generated,
                errors_count=errors_count,
                status=status,
                signals=all_signals,
            )

            await self._record_cycle_history(result)

            return result

        finally:
            self._is_scanning = False

    async def _analyze_symbol(self, symbol: WatchlistSymbol) -> tuple[list[Any], str | None]:
        """
        Analyze a single symbol using the orchestrator (Story 20.3b AC2).

        Handles error isolation - errors are logged but don't stop the cycle.

        Args:
            symbol: Watchlist symbol to analyze

        Returns:
            Tuple of (signals list, error message or None)
        """
        self._current_symbol = symbol.symbol
        start_time = time.perf_counter()

        try:
            if self._orchestrator is None:
                logger.warning(
                    "orchestrator_not_configured",
                    symbol=symbol.symbol,
                )
                return [], None  # Skip analysis but don't count as error

            logger.info(
                "analyzing_symbol",
                symbol=symbol.symbol,
                timeframe=symbol.timeframe.value,
            )

            # Call orchestrator to analyze symbol
            signals = await self._orchestrator.analyze_symbol(
                symbol.symbol, timeframe=symbol.timeframe.value
            )

            # Update last_scanned_at
            await self._repository.update_last_scanned(symbol.symbol, datetime.now(UTC))

            duration_ms = int((time.perf_counter() - start_time) * 1000)

            logger.info(
                "symbol_analysis_complete",
                symbol=symbol.symbol,
                timeframe=symbol.timeframe.value,
                signals_detected=len(signals),
                duration_ms=duration_ms,
            )

            return signals, None

        except Exception as e:
            duration_ms = int((time.perf_counter() - start_time) * 1000)

            logger.error(
                "symbol_analysis_failed",
                symbol=symbol.symbol,
                error=str(e),
                duration_ms=duration_ms,
                exc_info=True,
            )

            return [], str(e)

        finally:
            self._current_symbol = None

    def _split_into_batches(
        self, symbols: list[WatchlistSymbol], batch_size: int
    ) -> list[list[WatchlistSymbol]]:
        """
        Split symbols into batches of specified size.

        Args:
            symbols: List of symbols to batch
            batch_size: Maximum symbols per batch

        Returns:
            List of symbol batches
        """
        if batch_size <= 0:
            return [symbols]

        return [symbols[i : i + batch_size] for i in range(0, len(symbols), batch_size)]

    def _determine_cycle_status(
        self,
        symbols_total: int,
        symbols_processed: int,
        errors_count: int,
        was_stopped: bool,
    ) -> ScanCycleStatus:
        """
        Determine the status of a completed scan cycle.

        Args:
            symbols_total: Total symbols to process
            symbols_processed: Symbols actually processed
            errors_count: Number of errors encountered
            was_stopped: Whether cycle was interrupted by stop

        Returns:
            ScanCycleStatus enum value
        """
        if was_stopped and symbols_processed < symbols_total:
            return ScanCycleStatus.PARTIAL
        if symbols_total > 0 and errors_count == symbols_total:
            return ScanCycleStatus.FAILED
        return ScanCycleStatus.COMPLETED

    async def _record_cycle_history(self, result: ScanCycleResult) -> None:
        """
        Record scan cycle in history table.

        Args:
            result: Completed scan cycle result
        """
        try:
            history_entry = ScannerHistoryCreate(
                cycle_started_at=result.cycle_started_at,
                cycle_ended_at=result.cycle_ended_at,
                symbols_scanned=result.symbols_scanned,
                signals_generated=result.signals_generated,
                errors_count=result.errors_count,
                status=result.status,
            )

            await self._repository.add_history(history_entry)

            logger.debug(
                "scan_cycle_history_recorded",
                status=result.status.value,
                symbols_scanned=result.symbols_scanned,
            )

        except Exception as e:
            logger.error(
                "scan_cycle_history_recording_failed",
                error=str(e),
            )
