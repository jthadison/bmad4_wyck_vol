"""
Emergency Exit Service.

Provides emergency exit functionality for the orchestrator.

Story 18.10.5: Services Extraction and Orchestrator Facade (AC3)
Story 23.13: Kill switch integration with broker router.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

import structlog

if TYPE_CHECKING:
    from src.brokers.broker_router import BrokerRouter

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

    DEFAULT_MAX_HISTORY_SIZE = 1000

    def __init__(
        self,
        exit_manager: ExitManager | None = None,
        max_history_size: int = DEFAULT_MAX_HISTORY_SIZE,
        broker_router: "BrokerRouter | None" = None,
    ) -> None:
        """
        Initialize emergency exit service.

        Args:
            exit_manager: Manager for executing exits (optional)
            max_history_size: Maximum number of exit results to retain in history
            broker_router: Broker router for kill switch close-all (Story 23.13)
        """
        self._exit_manager = exit_manager
        self._exit_history: list[EmergencyExitResult] = []
        self._max_history_size = max_history_size
        self._broker_router = broker_router

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

        # Enforce max history size
        if len(self._exit_history) > self._max_history_size:
            self._exit_history = self._exit_history[-self._max_history_size :]

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

    async def activate_kill_switch(self, reason: str = "Manual activation") -> dict:
        """
        Activate the kill switch: close all positions and block new orders.

        Args:
            reason: Reason for kill switch activation

        Returns:
            Dict with activation result details
        """
        logger.critical("kill_switch_activation_requested", reason=reason)

        closed_count = 0
        failed_count = 0

        if self._broker_router:
            self._broker_router.activate_kill_switch(reason=reason)

            reports = await self._broker_router.close_all_positions()
            from src.models.order import OrderStatus

            closed_count = sum(1 for r in reports if r.status == OrderStatus.FILLED)
            failed_count = sum(1 for r in reports if r.status == OrderStatus.REJECTED)
        else:
            logger.warning("kill_switch_no_broker_router_configured")

        logger.critical(
            "kill_switch_activated",
            reason=reason,
            positions_closed=closed_count,
            positions_failed=failed_count,
        )

        return {
            "activated": True,
            "reason": reason,
            "positions_closed": closed_count,
            "positions_failed": failed_count,
            "timestamp": datetime.now(UTC).isoformat(),
        }

    def deactivate_kill_switch(self) -> dict:
        """
        Deactivate the kill switch, allowing new orders.

        Returns:
            Dict with deactivation result details
        """
        if self._broker_router:
            self._broker_router.deactivate_kill_switch()

        logger.info("kill_switch_deactivated")

        return {
            "activated": False,
            "timestamp": datetime.now(UTC).isoformat(),
        }

    def get_kill_switch_status(self) -> dict:
        """
        Get current kill switch status.

        Returns:
            Dict with kill switch state details
        """
        if self._broker_router:
            return self._broker_router.get_kill_switch_status()
        return {"active": False, "activated_at": None, "reason": None}
