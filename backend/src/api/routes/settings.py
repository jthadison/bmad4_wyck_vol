"""
Settings API Routes

Endpoints for user settings including auto-execution configuration.
Story 19.14: Auto-Execution Configuration Backend
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_current_user_id, get_db_session
from src.models.auto_execution_config import (
    AutoExecutionConfigResponse,
    AutoExecutionConfigUpdate,
    AutoExecutionEnableRequest,
    KillSwitchActivationResponse,
)
from src.services.auto_execution_config_service import AutoExecutionConfigService

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])
logger = logging.getLogger(__name__)


@router.get("/auto-execution", response_model=AutoExecutionConfigResponse)
async def get_auto_execution_config(
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get user's auto-execution configuration.

    Returns configuration settings and current metrics (trades today, risk today).

    **Authentication**: Required (JWT Bearer token)

    **Returns**:
    - Configuration settings
    - Current daily metrics
    - Consent status

    Example:
        ```bash
        curl -X GET http://localhost:8000/api/v1/settings/auto-execution \\
          -H "Authorization: Bearer YOUR_JWT_TOKEN"
        ```
    """
    service = AutoExecutionConfigService(db)
    try:
        return await service.get_config(user_id)
    except Exception as e:
        logger.exception("Failed to retrieve auto-execution configuration for user %s", user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve configuration. Please try again later.",
        ) from e


@router.put("/auto-execution", response_model=AutoExecutionConfigResponse)
async def update_auto_execution_config(
    updates: AutoExecutionConfigUpdate,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Update auto-execution configuration.

    Allows partial updates to configuration fields.
    Validates all updates against business rules.

    **Authentication**: Required (JWT Bearer token)

    **Request Body**: AutoExecutionConfigUpdate
    - min_confidence: Minimum signal confidence (60-100%)
    - max_trades_per_day: Maximum trades per day (1-50)
    - max_risk_per_day: Maximum daily risk percentage (0-10%)
    - circuit_breaker_losses: Consecutive losses before halt (1-10)
    - enabled_patterns: List of patterns to auto-execute
    - symbol_whitelist: Symbols allowed (null = all allowed)
    - symbol_blacklist: Symbols blocked

    **Returns**:
    - Updated configuration
    - Current daily metrics

    **Validation Errors**:
    - 400: Invalid configuration values

    Example:
        ```bash
        curl -X PUT http://localhost:8000/api/v1/settings/auto-execution \\
          -H "Authorization: Bearer YOUR_JWT_TOKEN" \\
          -H "Content-Type: application/json" \\
          -d '{
            "min_confidence": 90.0,
            "max_trades_per_day": 5,
            "enabled_patterns": ["SPRING"]
          }'
        ```
    """
    service = AutoExecutionConfigService(db)
    try:
        return await service.update_config(user_id, updates)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.exception("Failed to update auto-execution configuration for user %s", user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update configuration. Please try again later.",
        ) from e


@router.post("/auto-execution/enable", response_model=AutoExecutionConfigResponse)
async def enable_auto_execution(
    request_body: AutoExecutionEnableRequest,
    request: Request,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Enable auto-execution with consent.

    Requires explicit user acknowledgment and password confirmation.
    Records consent timestamp and IP address for audit trail.

    **Authentication**: Required (JWT Bearer token)

    **Request Body**: AutoExecutionEnableRequest
    - consent_acknowledged: Must be true
    - password: User's password for confirmation

    **Returns**:
    - Updated configuration with enabled=true
    - Consent timestamp

    **Errors**:
    - 400: Consent not acknowledged or invalid password
    - 401: Invalid password

    **Security**:
    - Password verification prevents accidental enabling
    - IP address logged for audit trail
    - Consent timestamp recorded

    Example:
        ```bash
        curl -X POST http://localhost:8000/api/v1/settings/auto-execution/enable \\
          -H "Authorization: Bearer YOUR_JWT_TOKEN" \\
          -H "Content-Type: application/json" \\
          -d '{
            "consent_acknowledged": true,
            "password": "user_password"
          }'
        ```
    """
    # Get client IP address for consent tracking
    client_ip = request.client.host if request.client else "unknown"

    service = AutoExecutionConfigService(db)
    try:
        return await service.enable_auto_execution(user_id, client_ip)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.exception("Failed to enable auto-execution for user %s", user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to enable auto-execution. Please try again later.",
        ) from e


@router.post("/auto-execution/disable", response_model=AutoExecutionConfigResponse)
async def disable_auto_execution(
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Disable auto-execution.

    Immediately stops all automatic trade execution.
    Configuration settings are preserved.

    **Authentication**: Required (JWT Bearer token)

    **Returns**:
    - Updated configuration with enabled=false

    Example:
        ```bash
        curl -X POST http://localhost:8000/api/v1/settings/auto-execution/disable \\
          -H "Authorization: Bearer YOUR_JWT_TOKEN"
        ```
    """
    service = AutoExecutionConfigService(db)
    try:
        return await service.disable_auto_execution(user_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.exception("Failed to disable auto-execution for user %s", user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to disable auto-execution. Please try again later.",
        ) from e


@router.post("/kill-switch", response_model=KillSwitchActivationResponse)
async def activate_kill_switch(
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Activate emergency kill switch.

    **EMERGENCY USE ONLY**

    Immediately stops all auto-execution without disabling the feature.
    Use when you need to halt trading immediately due to:
    - Market volatility
    - System issues
    - Unexpected behavior

    **Difference from Disable**:
    - Kill switch: Emergency stop, requires manual deactivation
    - Disable: Normal shutdown, can be re-enabled easily

    **Authentication**: Required (JWT Bearer token)

    **Returns**:
    - Kill switch status
    - Activation timestamp
    - Confirmation message

    **To Resume Trading**:
    - Must manually deactivate kill switch via separate endpoint
    - Or disable and re-enable auto-execution

    Example:
        ```bash
        curl -X POST http://localhost:8000/api/v1/settings/kill-switch \\
          -H "Authorization: Bearer YOUR_JWT_TOKEN"
        ```
    """
    service = AutoExecutionConfigService(db)
    try:
        config = await service.activate_kill_switch(user_id)
        return KillSwitchActivationResponse(
            kill_switch_active=True,
            activated_at=config.updated_at,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.exception("Failed to activate kill switch for user %s", user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to activate kill switch. Please try again later.",
        ) from e


@router.delete("/kill-switch", response_model=AutoExecutionConfigResponse)
async def deactivate_kill_switch(
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Deactivate kill switch to resume auto-execution.

    **Authentication**: Required (JWT Bearer token)

    **Returns**:
    - Updated configuration with kill_switch_active=false

    Example:
        ```bash
        curl -X DELETE http://localhost:8000/api/v1/settings/kill-switch \\
          -H "Authorization: Bearer YOUR_JWT_TOKEN"
        ```
    """
    service = AutoExecutionConfigService(db)
    try:
        return await service.deactivate_kill_switch(user_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.exception("Failed to deactivate kill switch for user %s", user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to deactivate kill switch. Please try again later.",
        ) from e
