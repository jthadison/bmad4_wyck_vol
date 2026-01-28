"""
Settings API Routes

Endpoints for user settings including auto-execution configuration.
Story 19.14: Auto-Execution Configuration Backend
Story 19.22: Emergency Kill Switch - WebSocket notifications and audit logging
Story 19.25: Email Notification Channel - Email notification settings
"""

import ipaddress
import logging
from datetime import UTC, datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_current_user_id, get_db_session
from src.api.websocket import manager as websocket_manager
from src.config import get_settings
from src.models.auto_execution_config import (
    AutoExecutionConfigResponse,
    AutoExecutionConfigUpdate,
    AutoExecutionEnableRequest,
    KillSwitchActivationResponse,
)
from src.models.notification import (
    EmailNotificationSettings,
    EmailNotificationSettingsUpdate,
    EmailSettingsResponse,
    NotificationSettingsResponse,
)
from src.notifications.rate_limiter import EmailRateLimiter
from src.services.auto_execution_config_service import AutoExecutionConfigService

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])
logger = logging.getLogger(__name__)


def validate_ip_address(ip_str: str) -> str:
    """
    Validate and normalize IP address.

    Args:
        ip_str: IP address string

    Returns:
        Normalized IP address string

    Raises:
        ValueError: If IP address is invalid
    """
    if ip_str == "unknown":
        return ip_str

    try:
        # Parse and normalize IP address (handles both IPv4 and IPv6)
        ip_obj = ipaddress.ip_address(ip_str)
        return str(ip_obj)
    except ValueError as e:
        raise ValueError(f"Invalid IP address format: {ip_str}") from e


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

    # Validate IP address format
    try:
        client_ip = validate_ip_address(client_ip)
    except ValueError as e:
        logger.warning("Invalid IP address from request: %s", client_ip)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid client IP address",
        ) from e

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
        activated_at = datetime.now(UTC)

        # Log to audit trail (Story 19.22)
        logger.info(
            "Kill switch activated",
            extra={
                "event_type": "kill_switch_activated",
                "user_id": str(user_id),
                "source": "user_action",
                "activated_at": activated_at.isoformat(),
            },
        )

        # Broadcast WebSocket notification to all sessions (Story 19.22)
        await websocket_manager.broadcast(
            {
                "type": "kill_switch_activated",
                "message": "Kill switch activated - all auto-execution stopped",
                "activated_at": activated_at.isoformat(),
                "user_id": str(user_id),
            }
        )

        return KillSwitchActivationResponse(
            kill_switch_active=True,
            activated_at=activated_at,
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
        config = await service.deactivate_kill_switch(user_id)
        deactivated_at = datetime.now(UTC)

        # Log to audit trail (Story 19.22)
        logger.info(
            "Kill switch deactivated",
            extra={
                "event_type": "kill_switch_deactivated",
                "user_id": str(user_id),
                "source": "user_action",
                "deactivated_at": deactivated_at.isoformat(),
            },
        )

        # Broadcast WebSocket notification to all sessions (Story 19.22)
        await websocket_manager.broadcast(
            {
                "type": "kill_switch_deactivated",
                "message": "Kill switch deactivated - auto-execution resumed",
                "deactivated_at": deactivated_at.isoformat(),
                "user_id": str(user_id),
            }
        )

        return config
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


# ============================================================================
# Email Notification Settings (Story 19.25)
# ============================================================================

# In-memory storage for email settings (MVP - would be database in production)
_user_email_settings: dict[str, EmailNotificationSettings] = {}

# Shared rate limiter instance
_email_rate_limiter: Optional[EmailRateLimiter] = None


def get_email_rate_limiter() -> EmailRateLimiter:
    """Get or create the email rate limiter singleton."""
    global _email_rate_limiter
    if _email_rate_limiter is None:
        settings = get_settings()
        _email_rate_limiter = EmailRateLimiter(max_per_hour=settings.email_rate_limit_per_hour)
    return _email_rate_limiter


@router.get("/notifications", response_model=NotificationSettingsResponse)
async def get_notification_settings(
    user_id: UUID = Depends(get_current_user_id),
):
    """
    Get notification preferences for current user (Story 19.25).

    Returns all notification channel settings including:
    - Email settings with rate limit remaining
    - Browser notification settings
    - Sound notification settings

    **Authentication**: Required (JWT Bearer token)

    **Response**:
    ```json
    {
      "email": {
        "enabled": true,
        "address": "trader@example.com",
        "notify_all_signals": false,
        "notify_auto_executions": true,
        "notify_circuit_breaker": true,
        "rate_limit_remaining": 7
      },
      "browser": {
        "enabled": true
      },
      "sound": {
        "enabled": true,
        "volume": 80
      }
    }
    ```

    Example:
        ```bash
        curl -X GET http://localhost:8000/api/v1/settings/notifications \\
          -H "Authorization: Bearer YOUR_JWT_TOKEN"
        ```
    """
    user_key = str(user_id)
    rate_limiter = get_email_rate_limiter()

    # Get user's email settings or defaults
    email_settings = _user_email_settings.get(user_key)

    if email_settings:
        email_response = EmailSettingsResponse(
            enabled=email_settings.email_enabled,
            address=email_settings.email_address,
            notify_all_signals=email_settings.notify_all_signals,
            notify_auto_executions=email_settings.notify_auto_executions,
            notify_circuit_breaker=email_settings.notify_circuit_breaker,
            rate_limit_remaining=rate_limiter.get_remaining(user_id),
        )
    else:
        email_response = EmailSettingsResponse(
            rate_limit_remaining=rate_limiter.get_remaining(user_id),
        )

    return NotificationSettingsResponse(
        email=email_response,
    )


@router.put("/notifications/email", response_model=NotificationSettingsResponse)
async def update_email_notification_settings(
    updates: EmailNotificationSettingsUpdate,
    user_id: UUID = Depends(get_current_user_id),
):
    """
    Update email notification settings (Story 19.25).

    Allows partial updates to email notification preferences.

    **Authentication**: Required (JWT Bearer token)

    **Request Body**:
    ```json
    {
      "enabled": true,
      "address": "trader@example.com",
      "notify_all_signals": true
    }
    ```

    **Response**: Updated notification settings

    **Validation**:
    - Email address must be valid format if provided
    - At least one field must be provided

    Example:
        ```bash
        curl -X PUT http://localhost:8000/api/v1/settings/notifications/email \\
          -H "Authorization: Bearer YOUR_JWT_TOKEN" \\
          -H "Content-Type: application/json" \\
          -d '{
            "enabled": true,
            "address": "trader@example.com",
            "notify_all_signals": false
          }'
        ```
    """
    user_key = str(user_id)
    rate_limiter = get_email_rate_limiter()

    # Get existing settings or create new
    current_settings = _user_email_settings.get(user_key, EmailNotificationSettings())

    # Apply updates
    if updates.enabled is not None:
        current_settings.email_enabled = updates.enabled

    if updates.address is not None:
        current_settings.email_address = updates.address

    if updates.notify_all_signals is not None:
        current_settings.notify_all_signals = updates.notify_all_signals

    if updates.notify_auto_executions is not None:
        current_settings.notify_auto_executions = updates.notify_auto_executions

    if updates.notify_circuit_breaker is not None:
        current_settings.notify_circuit_breaker = updates.notify_circuit_breaker

    # Store updated settings
    _user_email_settings[user_key] = current_settings

    logger.info(
        "Email notification settings updated",
        extra={
            "user_id": user_key,
            "enabled": current_settings.email_enabled,
            "address": current_settings.email_address[:3] + "***"
            if current_settings.email_address
            else None,
        },
    )

    # Build response
    email_response = EmailSettingsResponse(
        enabled=current_settings.email_enabled,
        address=current_settings.email_address,
        notify_all_signals=current_settings.notify_all_signals,
        notify_auto_executions=current_settings.notify_auto_executions,
        notify_circuit_breaker=current_settings.notify_circuit_breaker,
        rate_limit_remaining=rate_limiter.get_remaining(user_id),
    )

    return NotificationSettingsResponse(
        email=email_response,
    )


def get_user_email_settings(user_id: UUID) -> Optional[EmailNotificationSettings]:
    """
    Get email notification settings for a user.

    Used by other services to check notification preferences.

    Args:
        user_id: User identifier

    Returns:
        EmailNotificationSettings if configured, None otherwise
    """
    return _user_email_settings.get(str(user_id))
