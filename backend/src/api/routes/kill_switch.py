"""
Kill Switch API Routes (Story 23.13)

Emergency kill switch endpoints for activating/deactivating
the system-wide trading halt and closing all positions.

Author: Story 23.13
"""

from typing import Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.api.dependencies import get_current_user_id

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/kill-switch", tags=["Kill Switch"])


# --- Singleton service holder ---

_emergency_exit_service = None


def set_emergency_exit_service(service) -> None:
    """Register the emergency exit service singleton for route handlers."""
    global _emergency_exit_service
    _emergency_exit_service = service


def _get_service():
    """Get the emergency exit service, raising 503 if not configured."""
    if _emergency_exit_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Kill switch service not configured",
        )
    return _emergency_exit_service


# --- Request/Response Models ---


class ActivateRequest(BaseModel):
    """Request to activate the kill switch."""

    reason: str = Field(
        default="Manual activation",
        description="Reason for activating the kill switch",
        max_length=500,
    )


class KillSwitchStatusResponse(BaseModel):
    """Kill switch status response."""

    active: bool = Field(description="Whether the kill switch is currently active")
    activated_at: Optional[str] = Field(default=None, description="ISO timestamp of activation")
    reason: Optional[str] = Field(default=None, description="Reason for activation")


class ActivateResponse(BaseModel):
    """Response after activating the kill switch."""

    activated: bool = Field(description="Whether activation succeeded")
    reason: str = Field(description="Reason for activation")
    positions_closed: int = Field(description="Number of positions successfully closed")
    positions_failed: int = Field(description="Number of positions that failed to close")
    timestamp: str = Field(description="ISO timestamp of activation")


class DeactivateResponse(BaseModel):
    """Response after deactivating the kill switch."""

    activated: bool = Field(description="Whether the kill switch is still active (should be False)")
    timestamp: str = Field(description="ISO timestamp of deactivation")


# --- Endpoints ---


@router.post(
    "/activate",
    response_model=ActivateResponse,
    status_code=status.HTTP_200_OK,
)
async def activate_kill_switch(
    request: ActivateRequest,
    user_id: UUID = Depends(get_current_user_id),
):
    """
    Activate the kill switch: close all positions and block new orders.

    This is an emergency action that:
    1. Closes all open positions across all connected brokers
    2. Blocks all new order submissions until deactivated
    """
    service = _get_service()

    logger.critical(
        "kill_switch_activate_endpoint_called",
        user_id=user_id,
        reason=request.reason,
    )

    result = await service.activate_kill_switch(reason=request.reason)
    return ActivateResponse(**result)


@router.post(
    "/deactivate",
    response_model=DeactivateResponse,
    status_code=status.HTTP_200_OK,
)
async def deactivate_kill_switch(
    user_id: UUID = Depends(get_current_user_id),
):
    """
    Deactivate the kill switch, allowing new orders to be submitted.
    """
    service = _get_service()

    logger.warning(
        "kill_switch_deactivate_endpoint_called",
        user_id=str(user_id),
    )

    result = service.deactivate_kill_switch()
    return DeactivateResponse(**result)


@router.get(
    "/status",
    response_model=KillSwitchStatusResponse,
    status_code=status.HTTP_200_OK,
)
async def get_kill_switch_status(
    user_id: UUID = Depends(get_current_user_id),
):
    """
    Get current kill switch status.
    """
    service = _get_service()
    result = service.get_kill_switch_status()
    return KillSwitchStatusResponse(**result)
