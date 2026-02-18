"""
Signal Scanner Service (Story 20.3a, 20.3b, 20.4, 20.5b).

Background service for automated Wyckoff pattern scanning.
Manages scanner lifecycle: start, stop, status reporting.
Integrates with orchestrator for symbol analysis.

Safety Controls (Story 20.4):
    - Circuit breaker: Skip cycle when breaker is OPEN
    - Kill switch: Stop scanner entirely when activated
    - Session filtering: Skip forex during low-liquidity sessions
    - Rate limiting: Skip symbols scanned too recently

WebSocket Integration (Story 20.5b):
    - Broadcasts signal:new events when signals are detected
    - Broadcasts scanner:status_changed events on start/stop
    - Supports auto-restart on application startup

State Machine:
    STOPPED --(start)--> STARTING --(task created)--> RUNNING
    RUNNING --(stop)--> STOPPING --(task cancelled)--> STOPPED

Author: Story 20.3a, 20.3b, 20.4, 20.5b
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable
from uuid import UUID

import structlog
from pydantic import BaseModel, Field

from src.models.scanner_persistence import (
    AssetClass,
    ScanCycleStatus,
    ScannerConfigUpdate,
    ScannerHistoryCreate,
    WatchlistSymbol,
)
from src.orchestrator.orchestrator_facade import NoDataError
from src.services.session_filter import (
    get_current_session,
    should_skip_forex_symbol,
    should_skip_rate_limit,
)

if TYPE_CHECKING:
    from src.api.websocket import ConnectionManager
    from src.orchestrator.master_orchestrator import MasterOrchestrator, TradeSignal
    from src.orchestrator.orchestrator_facade import MasterOrchestratorFacade
    from src.repositories.scanner_repository import ScannerRepository
    from src.services.circuit_breaker_service import CircuitBreakerService


@runtime_checkable
class KillSwitchChecker(Protocol):
    """Protocol for kill switch checker services (Story 20.4)."""

    async def is_kill_switch_active(self, user_id: UUID) -> bool:
        """Check if kill switch is active for user."""
        ...


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
    signals: list[TradeSignal] = field(default_factory=list)
    symbols_no_data: int = 0  # Symbols with no OHLCV data available
    symbols_skipped_session: int = 0  # Story 20.4: forex session filtering
    symbols_skipped_rate_limit: int = 0  # Story 20.4: rate limiting
    kill_switch_triggered: bool = False  # Story 20.4: kill switch was activated
    correlation_ids: list[str] = field(default_factory=list)  # Task #25: Signal correlation IDs


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

    # Default batch delay in milliseconds (rate limiting between batches)
    DEFAULT_BATCH_DELAY_MS = 100

    # Maximum signals to collect per cycle (memory protection)
    MAX_SIGNALS_PER_CYCLE = 1000

    # Kill switch cache duration in seconds (reduces Redis overhead)
    KILL_SWITCH_CACHE_SECONDS = 5.0

    # Pattern types that indicate short direction (Story 20.5b)
    SHORT_PATTERNS: frozenset[str] = frozenset({"UTAD", "UT"})

    def __init__(
        self,
        repository: ScannerRepository | None = None,
        orchestrator: MasterOrchestrator | None = None,
        circuit_breaker: CircuitBreakerService | None = None,
        kill_switch_checker: KillSwitchChecker | None = None,
        user_id: UUID | None = None,
        fail_safe_on_error: bool = False,
        websocket_manager: ConnectionManager | None = None,
        session_factory: Any | None = None,
    ):
        """
        Initialize scanner service.

        Args:
            repository: Scanner repository for database operations (deprecated, use session_factory)
            orchestrator: MasterOrchestrator for symbol analysis (optional)
            circuit_breaker: CircuitBreakerService for safety checks (Story 20.4)
            kill_switch_checker: Service to check kill switch status (Story 20.4)
            user_id: User ID for circuit breaker/kill switch checks (Story 20.4)
            fail_safe_on_error: If True, treat safety check errors as active (fail-safe).
                               If False (default), treat errors as inactive (fail-permissive).
            websocket_manager: ConnectionManager for WebSocket broadcasts (Story 20.5b)
            session_factory: Async session factory for creating database sessions (Story 20.5b)
        """
        self._repository = repository
        self._session_factory = session_factory
        self._orchestrator = orchestrator
        self._circuit_breaker = circuit_breaker
        self._kill_switch_checker = kill_switch_checker
        self._user_id = user_id
        self._fail_safe_on_error = fail_safe_on_error
        self._websocket_manager = websocket_manager
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
        self._session_filter_enabled: bool = True  # Story 20.4: session filtering
        # Kill switch cache to reduce Redis overhead (Story 20.4 PR review)
        self._kill_switch_cache_time: float | None = None
        self._kill_switch_cached_value: bool = False
        # WebSocket broadcast metrics (Story 20.5b)
        self._signals_broadcast: int = 0
        self._broadcast_errors: int = 0

    def set_orchestrator(self, orchestrator: MasterOrchestrator | MasterOrchestratorFacade) -> None:
        """
        Set the orchestrator for symbol analysis.

        Args:
            orchestrator: Orchestrator instance (MasterOrchestrator or MasterOrchestratorFacade)
        """
        self._orchestrator = orchestrator
        logger.info("scanner_orchestrator_set")

    def set_websocket_manager(self, websocket_manager: ConnectionManager) -> None:
        """
        Set the WebSocket manager for signal broadcasting (Story 20.5b).

        Args:
            websocket_manager: ConnectionManager instance for broadcasts
        """
        self._websocket_manager = websocket_manager
        logger.info("scanner_websocket_manager_set")

    def set_repository(self, repository: ScannerRepository) -> None:
        """
        Set the repository for database operations.

        Args:
            repository: ScannerRepository instance
        """
        self._repository = repository
        logger.info("scanner_repository_set")

    @asynccontextmanager
    async def _get_repository(self) -> AsyncIterator[ScannerRepository]:
        """
        Get a repository instance with proper session lifecycle management (Story 20.5b).

        If session_factory is configured, creates a new session and repository,
        yielding it for use, then properly closes the session when done.
        If a static repository is configured, yields it directly.

        Usage:
            async with self._get_repository() as repository:
                await repository.get_config()

        Yields:
            ScannerRepository instance

        Raises:
            RuntimeError: If no repository or session factory configured
        """
        if self._repository is not None:
            yield self._repository
            return

        if self._session_factory is None:
            raise RuntimeError("No repository or session factory configured")

        # Import here to avoid circular imports
        from src.repositories.scanner_repository import ScannerRepository as ScanRepo

        # Create session using context manager for proper lifecycle
        async with self._session_factory() as session:
            yield ScanRepo(session)

    @property
    def is_running(self) -> bool:
        """Check if scanner is running."""
        return self._state == ScannerState.RUNNING

    async def start(self, *, broadcast: bool = True) -> None:
        """
        Start the scanner background task.

        Idempotent: safe to call multiple times.
        Non-blocking: returns immediately after starting task.

        Args:
            broadcast: If True (default), broadcast status change via WebSocket.
                      Set to False when using custom broadcast (e.g., auto_started).

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
        async with self._get_repository() as repository:
            config = await repository.get_config()
            self._scan_interval_seconds = config.scan_interval_seconds
            self._batch_size = config.batch_size
            self._last_cycle_at = config.last_cycle_at
            self._session_filter_enabled = config.session_filter_enabled  # Story 20.4

            # Load symbol count
            self._symbols_count = await repository.get_symbol_count()

            # Update database state
            await repository.update_config(ScannerConfigUpdate(is_running=True))

        # Reset stop event for new run
        self._stop_event.clear()

        # Create background task
        self._task = asyncio.create_task(self._scan_loop())

        self._state = ScannerState.RUNNING
        logger.info("scanner_started", scan_interval=self._scan_interval_seconds)

        # Story 20.5b AC6: Broadcast status change (unless caller handles it)
        if broadcast:
            await self._broadcast_status_change(is_running=True, event="started")

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
        async with self._get_repository() as repository:
            await repository.update_config(ScannerConfigUpdate(is_running=False))

        self._state = ScannerState.STOPPED
        logger.info("scanner_stopped")

        # Story 20.5b AC6: Broadcast status change
        await self._broadcast_status_change(is_running=False, event="stopped")

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
        Handles kill switch activation from scan cycle results.
        """
        logger.info("scanner_loop_started")

        while not self._stop_event.is_set():
            try:
                # Clear kill switch cache at start of each cycle
                self._kill_switch_cache_time = None
                self._kill_switch_cached_value = False

                # Execute scan cycle
                result = await self._scan_cycle()

                # Handle kill switch triggered (Story 20.4 PR review: avoid reentrancy)
                if result.kill_switch_triggered:
                    logger.warning("scanner_stopping_due_to_kill_switch")
                    break

                # Update last cycle time
                self._last_cycle_at = datetime.now(UTC)
                async with self._get_repository() as repository:
                    await repository.set_last_cycle_at(self._last_cycle_at)

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

    async def _check_kill_switch(self) -> bool:
        """
        Check if kill switch is activated (Story 20.4 AC2).

        Uses time-based caching to reduce Redis overhead (checks every 5 seconds).

        Returns:
            True if kill switch is activated, False otherwise
        """
        if self._kill_switch_checker is None or self._user_id is None:
            return False

        # Check cache first (Story 20.4 PR review: reduce Redis overhead)
        current_time = time.perf_counter()
        if (
            self._kill_switch_cache_time is not None
            and (current_time - self._kill_switch_cache_time) < self.KILL_SWITCH_CACHE_SECONDS
        ):
            return self._kill_switch_cached_value

        try:
            # Protocol check for type safety (Story 20.4 PR review)
            if isinstance(self._kill_switch_checker, KillSwitchChecker):
                result = await self._kill_switch_checker.is_kill_switch_active(self._user_id)
            elif hasattr(self._kill_switch_checker, "is_kill_switch_active"):
                # Fallback for duck typing compatibility
                result = await self._kill_switch_checker.is_kill_switch_active(self._user_id)
            else:
                result = False

            # Update cache
            self._kill_switch_cache_time = current_time
            self._kill_switch_cached_value = result
            return result
        except Exception as e:
            logger.error("kill_switch_check_failed", error=str(e))
            # Configurable fail-safe behavior (Story 20.4 PR review)
            if self._fail_safe_on_error:
                logger.warning("kill_switch_check_failed_using_fail_safe_mode")
                return True  # Fail-safe: treat error as activated
            return False  # Fail-permissive: treat error as not activated

    async def _check_circuit_breaker(self) -> bool:
        """
        Check if circuit breaker is open (Story 20.4 AC1).

        Returns:
            True if circuit breaker is open, False otherwise
        """
        if self._circuit_breaker is None or self._user_id is None:
            return False

        try:
            return await self._circuit_breaker.is_breaker_open(self._user_id)
        except Exception as e:
            logger.error("circuit_breaker_check_failed", error=str(e))
            # Configurable fail-safe behavior (Story 20.4 PR review)
            if self._fail_safe_on_error:
                logger.warning("circuit_breaker_check_failed_using_fail_safe_mode")
                return True  # Fail-safe: treat error as open
            return False  # Fail-permissive: treat error as closed

    async def _scan_cycle(self) -> ScanCycleResult:
        """
        Execute a single scan cycle (Story 20.3b, 20.4).

        Processes all enabled watchlist symbols through the orchestrator,
        using batch processing with rate limiting for API protection.

        Safety checks (Story 20.4):
        1. Kill switch - stops scanner entirely if activated
        2. Circuit breaker - skips cycle if breaker is OPEN
        3. Session filtering - skips forex during low-liquidity sessions
        4. Rate limiting - skips symbols scanned too recently

        Returns:
            ScanCycleResult with metrics and detected signals
        """
        self._is_scanning = True
        cycle_started_at = datetime.now(UTC)
        symbols_scanned = 0
        signals_generated = 0
        errors_count = 0
        symbols_no_data = 0
        symbols_skipped_session = 0
        symbols_skipped_rate_limit = 0
        all_signals: list[TradeSignal] = []
        was_stopped = False
        signals_truncated = False

        try:
            # Story 20.4 AC2: Kill switch check - signals scanner to stop
            # (Story 20.4 PR review: avoid reentrancy by returning flag instead of calling stop())
            if await self._check_kill_switch():
                logger.warning("kill_switch_activated_signaling_stop")
                return ScanCycleResult(
                    cycle_started_at=cycle_started_at,
                    cycle_ended_at=datetime.now(UTC),
                    symbols_scanned=0,
                    signals_generated=0,
                    errors_count=0,
                    status=ScanCycleStatus.SKIPPED,
                    signals=[],
                    kill_switch_triggered=True,
                )

            # Story 20.4 AC1: Circuit breaker check - skips this cycle
            if await self._check_circuit_breaker():
                logger.info("scan_cycle_skipped_circuit_breaker_open")
                return ScanCycleResult(
                    cycle_started_at=cycle_started_at,
                    cycle_ended_at=datetime.now(UTC),
                    symbols_scanned=0,
                    signals_generated=0,
                    errors_count=0,
                    status=ScanCycleStatus.SKIPPED,
                    signals=[],
                )

            # Fail fast if orchestrator not configured
            if self._orchestrator is None:
                logger.error("orchestrator_not_configured_skipping_cycle")
                return ScanCycleResult(
                    cycle_started_at=cycle_started_at,
                    cycle_ended_at=datetime.now(UTC),
                    symbols_scanned=0,
                    signals_generated=0,
                    errors_count=0,
                    status=ScanCycleStatus.SKIPPED,
                    signals=[],
                )

            # Get enabled symbols from repository
            async with self._get_repository() as repository:
                enabled_symbols = await repository.get_enabled_symbols()
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

                    # Story 20.4 AC2: Kill switch check per symbol (cached to reduce Redis overhead)
                    if await self._check_kill_switch():
                        logger.warning(
                            "kill_switch_activated_mid_cycle",
                            current_symbol=symbol.symbol,
                            symbols_processed=symbols_scanned,
                        )
                        # Return with kill_switch_triggered flag (avoid reentrancy)
                        return ScanCycleResult(
                            cycle_started_at=cycle_started_at,
                            cycle_ended_at=datetime.now(UTC),
                            symbols_scanned=symbols_scanned,
                            signals_generated=signals_generated,
                            errors_count=errors_count,
                            status=ScanCycleStatus.PARTIAL,
                            signals=all_signals,
                            symbols_skipped_session=symbols_skipped_session,
                            symbols_skipped_rate_limit=symbols_skipped_rate_limit,
                            kill_switch_triggered=True,
                        )

                    # Capture current time once for this symbol (Story 20.4 PR review)
                    current_time = datetime.now(UTC)

                    # Story 20.4 AC3/AC4: Forex session filtering
                    if symbol.asset_class == AssetClass.FOREX and self._session_filter_enabled:
                        should_skip, reason = should_skip_forex_symbol(
                            utc_time=current_time,
                            session_filter_enabled=True,
                        )
                        if should_skip:
                            session = get_current_session(current_time)
                            logger.info(
                                "symbol_skipped_session_filter",
                                symbol=symbol.symbol,
                                session=session.value,
                                reason=reason,
                            )
                            symbols_skipped_session += 1
                            continue

                    # Story 20.4 AC6: Rate limiting check
                    should_skip, reason = should_skip_rate_limit(
                        last_scanned_at=symbol.last_scanned_at,
                        scan_interval_seconds=self._scan_interval_seconds,
                        utc_now=current_time,
                    )
                    if should_skip:
                        logger.info(
                            "symbol_skipped_rate_limit",
                            symbol=symbol.symbol,
                            reason=reason,
                        )
                        symbols_skipped_rate_limit += 1
                        continue

                    # Analyze symbol with error isolation
                    signals, error = await self._analyze_symbol(symbol)

                    symbols_scanned += 1

                    if error == "no_data":
                        symbols_no_data += 1
                    elif error:
                        errors_count += 1
                    else:
                        # Story 20.5b AC1/AC3: Broadcast each signal individually
                        for sig in signals:
                            await self._broadcast_signal(sig)

                        # Memory protection: limit signals per cycle
                        if len(all_signals) < self.MAX_SIGNALS_PER_CYCLE:
                            remaining_capacity = self.MAX_SIGNALS_PER_CYCLE - len(all_signals)
                            signals_to_add = signals[:remaining_capacity]
                            all_signals.extend(signals_to_add)
                            if len(signals) > remaining_capacity and not signals_truncated:
                                signals_truncated = True
                                logger.warning(
                                    "max_signals_reached",
                                    max=self.MAX_SIGNALS_PER_CYCLE,
                                )
                        signals_generated += len(signals)

                if was_stopped:
                    break

                # Add delay between batches (not after last batch)
                if batch_index < total_batches - 1 and not self._stop_event.is_set():
                    delay_seconds = self._batch_delay_ms / 1000.0
                    await asyncio.sleep(delay_seconds)

            # Determine cycle status (Story 20.4 PR review: include skip counts)
            status = self._determine_cycle_status(
                symbols_total=total_symbols,
                symbols_processed=symbols_scanned,
                errors_count=errors_count,
                was_stopped=was_stopped,
                symbols_skipped_session=symbols_skipped_session,
                symbols_skipped_rate_limit=symbols_skipped_rate_limit,
            )

            cycle_ended_at = datetime.now(UTC)
            cycle_duration_ms = int((cycle_ended_at - cycle_started_at).total_seconds() * 1000)

            logger.info(
                "scan_cycle_complete",
                symbols_scanned=symbols_scanned,
                signals_generated=signals_generated,
                errors_count=errors_count,
                symbols_no_data=symbols_no_data,
                symbols_skipped_session=symbols_skipped_session,
                symbols_skipped_rate_limit=symbols_skipped_rate_limit,
                duration_ms=cycle_duration_ms,
                status=status.value,
            )

            # Extract correlation IDs from signals for audit trail (Task #25)
            correlation_ids = [str(signal.correlation_id) for signal in all_signals]

            # Record cycle in history
            result = ScanCycleResult(
                cycle_started_at=cycle_started_at,
                cycle_ended_at=cycle_ended_at,
                symbols_scanned=symbols_scanned,
                signals_generated=signals_generated,
                errors_count=errors_count,
                status=status,
                signals=all_signals,
                symbols_no_data=symbols_no_data,
                symbols_skipped_session=symbols_skipped_session,
                symbols_skipped_rate_limit=symbols_skipped_rate_limit,
                correlation_ids=correlation_ids,
            )

            await self._record_cycle_history(result)

            return result

        finally:
            self._is_scanning = False

    async def _analyze_symbol(
        self, symbol: WatchlistSymbol
    ) -> tuple[list[TradeSignal], str | None]:
        """
        Analyze a single symbol using the orchestrator (Story 20.3b AC2).

        Handles error isolation - errors are logged but don't stop the cycle.
        Note: Orchestrator is guaranteed non-None by _scan_cycle fail-fast check.

        Args:
            symbol: Watchlist symbol to analyze

        Returns:
            Tuple of (signals list, error message or None)
        """
        self._current_symbol = symbol.symbol
        start_time = time.perf_counter()

        try:
            # Note: orchestrator guaranteed non-None by _scan_cycle fail-fast check
            assert self._orchestrator is not None

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
            async with self._get_repository() as repository:
                await repository.update_last_scanned(symbol.symbol, datetime.now(UTC))

            duration_ms = int((time.perf_counter() - start_time) * 1000)

            logger.info(
                "symbol_analysis_complete",
                symbol=symbol.symbol,
                timeframe=symbol.timeframe.value,
                signals_detected=len(signals),
                duration_ms=duration_ms,
            )

            return signals, None

        except NoDataError:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            logger.warning(
                "symbol_no_ohlcv_data",
                symbol=symbol.symbol,
                timeframe=symbol.timeframe.value,
                duration_ms=duration_ms,
            )
            return [], "no_data"

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
        symbols_skipped_session: int = 0,
        symbols_skipped_rate_limit: int = 0,
    ) -> ScanCycleStatus:
        """
        Determine the status of a completed scan cycle.

        Args:
            symbols_total: Total symbols to process
            symbols_processed: Symbols actually processed
            errors_count: Number of errors encountered
            was_stopped: Whether cycle was interrupted by stop
            symbols_skipped_session: Symbols skipped due to session filtering
            symbols_skipped_rate_limit: Symbols skipped due to rate limiting

        Returns:
            ScanCycleStatus enum value
        """
        if was_stopped and symbols_processed < symbols_total:
            return ScanCycleStatus.PARTIAL
        if symbols_total > 0 and errors_count == symbols_total:
            return ScanCycleStatus.FAILED

        # Partial completion if some (but not all) symbols had errors
        if errors_count > 0 and errors_count < symbols_total:
            return ScanCycleStatus.PARTIAL

        # Story 20.4 PR review: account for skipped symbols
        total_skipped = symbols_skipped_session + symbols_skipped_rate_limit
        if symbols_total > 0 and total_skipped == symbols_total and symbols_processed == 0:
            # All symbols were filtered/skipped, none actually processed
            return ScanCycleStatus.FILTERED

        return ScanCycleStatus.COMPLETED

    async def _record_cycle_history(self, result: ScanCycleResult) -> None:
        """
        Record scan cycle in history table.

        NOTE (L-3): History is ALWAYS recorded after every scan cycle, regardless
        of outcome (COMPLETED, PARTIAL, FAILED, SKIPPED). This ensures we have a
        complete audit trail of all scanner activity, including failures.

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
                # Story 20.4 PR review: include skip counts in history
                symbols_no_data=result.symbols_no_data,
                symbols_skipped_session=result.symbols_skipped_session,
                symbols_skipped_rate_limit=result.symbols_skipped_rate_limit,
            )

            async with self._get_repository() as repository:
                await repository.add_history(history_entry)

                logger.debug(
                    "scan_cycle_history_recorded",
                    status=result.status.value,
                    symbols_scanned=result.symbols_scanned,
                    symbols_no_data=result.symbols_no_data,
                    symbols_skipped_session=result.symbols_skipped_session,
                    symbols_skipped_rate_limit=result.symbols_skipped_rate_limit,
                )

        except Exception as e:
            logger.error(
                "scan_cycle_history_recording_failed",
                error=str(e),
            )

    async def _broadcast_signal(self, signal: TradeSignal) -> None:
        """
        Broadcast detected signal via WebSocket (Story 20.5b AC1).

        Formats signal data according to WebSocket message schema and
        broadcasts to all connected clients.

        Args:
            signal: TradeSignal from orchestrator to broadcast
        """
        if self._websocket_manager is None:
            return

        try:
            # Determine direction from pattern type
            direction = "short" if signal.pattern_type in self.SHORT_PATTERNS else "long"

            message = {
                "type": "signal:new",
                "timestamp": datetime.now(UTC).isoformat(),
                "data": {
                    "id": str(signal.signal_id),
                    "symbol": signal.symbol,
                    "pattern": signal.pattern_type,
                    "direction": direction,
                    "confidence": signal.confidence_score,
                    "entry_price": str(signal.entry_price),
                    "stop_loss": str(signal.stop_price),
                    "take_profit": str(signal.target_price),
                    "timeframe": signal.timeframe,
                    "source": "scanner",
                    "detected_at": datetime.now(UTC).isoformat(),
                },
            }

            await self._websocket_manager.broadcast(message)
            self._signals_broadcast += 1

            logger.info(
                "signal_broadcast",
                symbol=signal.symbol,
                pattern=signal.pattern_type,
                signal_id=str(signal.signal_id),
            )

        except Exception as e:
            self._broadcast_errors += 1
            logger.error(
                "signal_broadcast_failed",
                symbol=signal.symbol,
                error=str(e),
            )
            # Don't re-raise - scan should continue

    async def _broadcast_status_change(self, is_running: bool, event: str) -> None:
        """
        Broadcast scanner status change via WebSocket (Story 20.5b AC6).

        Args:
            is_running: Current scanner running state
            event: Event type (started, stopped, auto_started)
        """
        if self._websocket_manager is None:
            return

        try:
            message = {
                "type": "scanner:status_changed",
                "timestamp": datetime.now(UTC).isoformat(),
                "data": {
                    "is_running": is_running,
                    "event": event,
                },
            }

            await self._websocket_manager.broadcast(message)

            logger.info(
                "scanner_status_broadcast",
                is_running=is_running,
                event=event,
            )

        except Exception as e:
            logger.error(
                "scanner_status_broadcast_failed",
                event=event,
                error=str(e),
            )
            # Don't re-raise - scanner operation should continue
