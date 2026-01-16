"""
Emergency Exit Service.

Provides emergency exit functionality for the orchestrator.

Story 18.10.5: Services Extraction and Orchestrator Facade (AC3)
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class EmergencyExitRequest:
    """Request for emergency exit."""

    campaign_id: UUID
    symbol: str
    reason: str
    current_price: Decimal
    correlation_id: UUID | None = None


@dataclass
class EmergencyExitResult:
    """Result of emergency exit operation."""

    success: bool
    campaign_id: UUID
    exit_order_count: int
    reason: str
    timestamp: datetime


class ExitManager(Protocol):
    """Protocol for exit management operations."""

    async def execute_emergency_exit(
        self,
        campaign_id: UUID,
        invalidation_reason: str,
        correlation_id: str | None = None,
    ) -> list:
        """Execute emergency exit for a campaign."""
        ...


class EmergencyExitService:
    """
    Service for handling emergency exits in the orchestrator.

    Provides a clean interface for triggering emergency exits
    when invalidation conditions are detected during pipeline execution.

    Example:
        >>> service = EmergencyExitService(exit_manager)
        >>> result = await service.trigger_exit(request)
        >>> if result.success:
        ...     logger.info("Emergency exit executed")
    """

    def __init__(self, exit_manager: ExitManager | None = None) -> None:
        """
        Initialize emergency exit service.

        Args:
            exit_manager: Manager for executing exits (optional)
        """
        self._exit_manager = exit_manager
        self._exit_history: list[EmergencyExitResult] = []

    async def trigger_exit(self, request: EmergencyExitRequest) -> EmergencyExitResult:
        """
        Trigger emergency exit for a campaign.

        Args:
            request: Emergency exit request details

        Returns:
            EmergencyExitResult with operation status
        """
        logger.warning(
            "emergency_exit_triggered",
            campaign_id=str(request.campaign_id),
            symbol=request.symbol,
            reason=request.reason,
            current_price=str(request.current_price),
            correlation_id=str(request.correlation_id) if request.correlation_id else None,
        )

        exit_order_count = 0

        if self._exit_manager:
            try:
                exit_orders = await self._exit_manager.execute_emergency_exit(
                    campaign_id=request.campaign_id,
                    invalidation_reason=request.reason,
                    correlation_id=str(request.correlation_id) if request.correlation_id else None,
                )
                exit_order_count = len(exit_orders)
            except Exception as e:
                logger.error(
                    "emergency_exit_failed",
                    campaign_id=str(request.campaign_id),
                    error=str(e),
                )
                result = EmergencyExitResult(
                    success=False,
                    campaign_id=request.campaign_id,
                    exit_order_count=0,
                    reason=f"Exit failed: {e}",
                    timestamp=datetime.now(UTC),
                )
                self._exit_history.append(result)
                return result

        result = EmergencyExitResult(
            success=True,
            campaign_id=request.campaign_id,
            exit_order_count=exit_order_count,
            reason=request.reason,
            timestamp=datetime.now(UTC),
        )

        self._exit_history.append(result)

        logger.info(
            "emergency_exit_complete",
            campaign_id=str(request.campaign_id),
            exit_orders=exit_order_count,
        )

        return result

    def get_exit_history(self) -> list[EmergencyExitResult]:
        """Get history of emergency exits."""
        return self._exit_history.copy()

    def clear_history(self) -> None:
        """Clear exit history."""
        self._exit_history.clear()
