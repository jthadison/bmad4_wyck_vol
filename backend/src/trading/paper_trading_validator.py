"""
Paper Trading Validation Runner (Story 23.8b)

Configures and manages paper trading validation runs that compare
paper trading results against backtest baselines.

Author: Story 23.8b
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)


class ValidationRunStatus(str, Enum):
    """Status of a validation run."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ValidationSymbolConfig(BaseModel):
    """Configuration for a single symbol in a validation run."""

    symbol: str = Field(description="Trading symbol (e.g., EURUSD, SPY)")
    timeframe: str = Field(default="1d", description="Timeframe for analysis")


class ValidationRunConfig(BaseModel):
    """Configuration for a paper trading validation run."""

    symbols: list[ValidationSymbolConfig] = Field(
        default_factory=lambda: [
            ValidationSymbolConfig(symbol="EURUSD"),
            ValidationSymbolConfig(symbol="SPX500"),
        ],
        description="Symbols to validate",
    )
    duration_days: int = Field(
        default=14, ge=1, le=90, description="Validation run duration in days"
    )
    tolerance_pct: Decimal = Field(
        default=Decimal("10.0"),
        ge=Decimal("0"),
        le=Decimal("100"),
        description="Acceptable deviation percentage from backtest baseline",
    )


class ValidationRunState(BaseModel):
    """State of a validation run."""

    id: UUID = Field(default_factory=uuid4)
    config: ValidationRunConfig
    status: ValidationRunStatus = ValidationRunStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None

    # Accumulated metrics per symbol
    symbol_metrics: dict[str, dict] = Field(default_factory=dict)

    # Signals tracked
    signals_generated: int = 0
    signals_executed: int = 0
    signals_rejected: int = 0


class PaperTradingValidator:
    """
    Service for managing paper trading validation runs.

    Configures validation runs with multiple symbols and tracks
    results for comparison against backtest baselines.
    """

    def __init__(self) -> None:
        self._current_run: Optional[ValidationRunState] = None

    @property
    def current_run(self) -> Optional[ValidationRunState]:
        """Get the current validation run state."""
        return self._current_run

    def start_run(self, config: Optional[ValidationRunConfig] = None) -> ValidationRunState:
        """
        Start a new validation run.

        Args:
            config: Optional configuration. Uses defaults if not provided.

        Returns:
            The newly created ValidationRunState.

        Raises:
            ValueError: If a run is already active.
        """
        if self._current_run and self._current_run.status == ValidationRunStatus.RUNNING:
            raise ValueError("A validation run is already active. Stop it first.")

        if config is None:
            config = ValidationRunConfig()

        run = ValidationRunState(
            config=config,
            status=ValidationRunStatus.RUNNING,
            started_at=datetime.now(UTC),
        )
        self._current_run = run

        logger.info(
            "validation_run_started",
            run_id=str(run.id),
            symbols=[s.symbol for s in config.symbols],
            duration_days=config.duration_days,
            tolerance_pct=float(config.tolerance_pct),
        )

        return run

    def stop_run(self) -> Optional[ValidationRunState]:
        """
        Stop the current validation run.

        Returns:
            The completed ValidationRunState, or None if no run is active.
        """
        if not self._current_run:
            return None

        self._current_run.status = ValidationRunStatus.COMPLETED
        self._current_run.completed_at = datetime.now(UTC)

        logger.info(
            "validation_run_stopped",
            run_id=str(self._current_run.id),
            signals_generated=self._current_run.signals_generated,
            signals_executed=self._current_run.signals_executed,
        )

        return self._current_run

    def record_signal(self, symbol: str, executed: bool) -> None:
        """
        Record a signal event during a validation run.

        Args:
            symbol: The symbol the signal was for.
            executed: Whether the signal was executed or rejected.
        """
        if not self._current_run or self._current_run.status != ValidationRunStatus.RUNNING:
            return

        self._current_run.signals_generated += 1
        if executed:
            self._current_run.signals_executed += 1
        else:
            self._current_run.signals_rejected += 1

        logger.debug(
            "validation_signal_recorded",
            symbol=symbol,
            executed=executed,
            total_generated=self._current_run.signals_generated,
        )

    def record_metrics(self, symbol: str, metrics: dict) -> None:
        """
        Record performance metrics for a symbol during the validation run.

        Args:
            symbol: The trading symbol.
            metrics: Dict of performance metrics (win_rate, profit_factor, etc.)
        """
        if not self._current_run or self._current_run.status != ValidationRunStatus.RUNNING:
            return

        self._current_run.symbol_metrics[symbol] = metrics

        logger.debug(
            "validation_metrics_recorded",
            symbol=symbol,
            metrics_keys=list(metrics.keys()),
        )

    def get_status(self) -> dict:
        """
        Get the current status of the validation run.

        Returns:
            Dict with run status information.
        """
        if not self._current_run:
            return {"active": False, "message": "No validation run configured"}

        run = self._current_run
        elapsed_seconds = 0.0
        if run.started_at:
            end = run.completed_at or datetime.now(UTC)
            elapsed_seconds = (end - run.started_at).total_seconds()

        return {
            "active": run.status == ValidationRunStatus.RUNNING,
            "run_id": str(run.id),
            "status": run.status.value,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "elapsed_seconds": elapsed_seconds,
            "symbols": [s.symbol for s in run.config.symbols],
            "duration_days": run.config.duration_days,
            "tolerance_pct": float(run.config.tolerance_pct),
            "signals_generated": run.signals_generated,
            "signals_executed": run.signals_executed,
            "signals_rejected": run.signals_rejected,
            "error_message": run.error_message,
        }
