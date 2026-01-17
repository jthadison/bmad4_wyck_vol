"""
Notification API Routes

Provides REST endpoints for:
- GET /api/v1/notifications - List notifications with filtering
- PATCH /api/v1/notifications/{id}/read - Mark as read
- GET /api/v1/notifications/preferences - Get preferences
- POST /api/v1/notifications/preferences - Update preferences
- POST /api/v1/notifications/test/{channel} - Send test notification
- POST /api/v1/notifications/push/subscribe - Subscribe to push
- DELETE /api/v1/notifications/push/unsubscribe - Unsubscribe from push

Story: 11.6 - Notification & Alert System
"""

from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_current_user, get_db_session
from src.config import settings
from src.models.notification import (
    NotificationListResponse,
    NotificationPreferences,
    NotificationResponse,
    NotificationType,
)
from src.notifications.email_client import EmailClient
from src.notifications.push_client import PushClient
from src.notifications.service import NotificationService
from src.notifications.twilio_client import TwilioClient
from src.repositories.notification_repository import NotificationRepository

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


# Dependency to get notification repository
async def get_notification_repository(
    session: AsyncSession = Depends(get_db_session),
) -> NotificationRepository:
    """Get notification repository instance."""
    return NotificationRepository(session)


# Dependency to get notification service
async def get_notification_service(
    repository: NotificationRepository = Depends(get_notification_repository),
) -> NotificationService:
    """Get notification service with configured clients."""
    # Initialize channel clients
    twilio_client = TwilioClient(
        account_sid=getattr(settings, "TWILIO_ACCOUNT_SID", None),
        auth_token=getattr(settings, "TWILIO_AUTH_TOKEN", None),
        phone_number=getattr(settings, "TWILIO_PHONE_NUMBER", None),
        test_mode=getattr(settings, "NOTIFICATION_TEST_MODE", True),
    )

    email_client = EmailClient(
        smtp_host=getattr(settings, "SMTP_HOST", None),
        smtp_port=getattr(settings, "SMTP_PORT", 587),
        smtp_user=getattr(settings, "SMTP_USER", None),
        smtp_password=getattr(settings, "SMTP_PASSWORD", None),
        from_email=getattr(settings, "SMTP_FROM_EMAIL", None),
        test_mode=getattr(settings, "NOTIFICATION_TEST_MODE", True),
    )

    push_client = PushClient(
        vapid_private_key=getattr(settings, "VAPID_PRIVATE_KEY", None),
        vapid_claims_email=getattr(settings, "VAPID_CLAIMS_EMAIL", None),
        test_mode=getattr(settings, "NOTIFICATION_TEST_MODE", True),
    )

    # Get WebSocket manager for toast notifications
    from src.api.websocket import manager as websocket_manager

    return NotificationService(
        repository=repository,
        twilio_client=twilio_client,
        email_client=email_client,
        push_client=push_client,
        websocket_manager=websocket_manager,
    )


@router.get("", response_model=NotificationListResponse)
async def get_notifications(
    unread_only: bool = Query(False, description="Only return unread notifications"),
    notification_type: Optional[NotificationType] = Query(
        None, description="Filter by notification type"
    ),
    limit: int = Query(50, ge=1, le=100, description="Maximum results to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    current_user: dict = Depends(get_current_user),
    repository: NotificationRepository = Depends(get_notification_repository),
):
    """
    Get notifications for current user with optional filtering.

    Returns paginated list of notifications ordered by most recent first.
    """
    user_id = current_user["id"]

    notifications, total_count = await repository.get_notifications(
        user_id=user_id,
        unread_only=unread_only,
        notification_type=notification_type,
        limit=limit,
        offset=offset,
    )

    return {
        "data": notifications,
        "pagination": {
            "returned_count": len(notifications),
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + len(notifications)) < total_count,
        },
    }


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_read(
    notification_id: UUID = Path(..., description="Notification ID"),
    current_user: dict = Depends(get_current_user),
    repository: NotificationRepository = Depends(get_notification_repository),
):
    """
    Mark a notification as read.

    Only the owning user can mark their notifications as read.
    """
    user_id = current_user["id"]

    success = await repository.mark_as_read(
        notification_id=notification_id,
        user_id=user_id,
    )

    if not success:
        raise HTTPException(
            status_code=404,
            detail="Notification not found or not authorized",
        )

    return {
        "success": True,
        "notification_id": notification_id,
        "message": "Notification marked as read",
    }


@router.get("/preferences", response_model=NotificationPreferences)
async def get_notification_preferences(
    current_user: dict = Depends(get_current_user),
    repository: NotificationRepository = Depends(get_notification_repository),
):
    """
    Get notification preferences for current user.

    Returns default preferences if none are set.
    """
    user_id = current_user["id"]

    preferences = await repository.get_preferences(user_id)

    if not preferences:
        # Return default preferences
        from datetime import datetime

        preferences = NotificationPreferences(
            user_id=user_id,
            updated_at=datetime.utcnow(),
        )

    return preferences


@router.post("/preferences", response_model=NotificationResponse)
async def update_notification_preferences(
    preferences: NotificationPreferences,
    current_user: dict = Depends(get_current_user),
    repository: NotificationRepository = Depends(get_notification_repository),
):
    """
    Update notification preferences for current user.

    Validates preferences and persists to database.
    """
    user_id = current_user["id"]

    # Ensure user_id matches current user
    if preferences.user_id != user_id:
        raise HTTPException(
            status_code=403,
            detail="Cannot update preferences for another user",
        )

    updated_prefs = await repository.update_preferences(preferences)

    return {
        "success": True,
        "message": "Preferences updated successfully",
    }


@router.post("/test/{channel}", response_model=NotificationResponse, status_code=202)
async def send_test_notification(
    channel: Literal["sms", "email", "push"] = Path(..., description="Channel to test"),
    current_user: dict = Depends(get_current_user),
    repository: NotificationRepository = Depends(get_notification_repository),
    service: NotificationService = Depends(get_notification_service),
):
    """
    Send test notification for channel verification.

    Accepts: sms, email, push
    Returns 202 Accepted (async operation)
    """
    user_id = current_user["id"]

    # Get user preferences to get contact info
    preferences = await repository.get_preferences(user_id)

    if not preferences:
        raise HTTPException(
            status_code=400,
            detail="No preferences configured. Please set up your notification preferences first.",
        )

    try:
        if channel == "sms":
            if not preferences.sms_enabled or not preferences.sms_phone_number:
                raise HTTPException(
                    status_code=400,
                    detail="SMS not enabled or phone number not set",
                )

            success = await service.twilio_client.send_test_sms(preferences.sms_phone_number)

            if not success:
                raise HTTPException(
                    status_code=503,
                    detail="Failed to send test SMS",
                )

            return {
                "success": True,
                "message": f"Test SMS sent to {preferences.sms_phone_number}",
            }

        elif channel == "email":
            if not preferences.email_enabled or not preferences.email_address:
                raise HTTPException(
                    status_code=400,
                    detail="Email not enabled or address not set",
                )

            success = await service.email_client.send_test_email(preferences.email_address)

            if not success:
                raise HTTPException(
                    status_code=503,
                    detail="Failed to send test email",
                )

            return {
                "success": True,
                "message": f"Test email sent to {preferences.email_address}",
            }

        elif channel == "push":
            if not preferences.push_enabled:
                raise HTTPException(
                    status_code=400,
                    detail="Push notifications not enabled",
                )

            # Get user's push subscriptions
            subscriptions = await repository.get_push_subscriptions(user_id)

            if not subscriptions:
                raise HTTPException(
                    status_code=400,
                    detail="No push subscriptions found. Please subscribe first.",
                )

            # Send test push to all subscriptions
            sent_count = 0
            for subscription in subscriptions:
                try:
                    success = await service.push_client.send_test_push(subscription)
                    if success:
                        sent_count += 1
                except Exception:
                    # Continue trying other subscriptions
                    pass

            if sent_count == 0:
                raise HTTPException(
                    status_code=503,
                    detail="Failed to send test push notification",
                )

            return {
                "success": True,
                "message": f"Test push sent to {sent_count} device(s)",
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send test notification: {str(e)}",
        ) from e


@router.post("/push/subscribe", response_model=NotificationResponse)
async def subscribe_to_push(
    subscription: dict,
    current_user: dict = Depends(get_current_user),
    repository: NotificationRepository = Depends(get_notification_repository),
):
    """
    Subscribe to push notifications.

    Request body should contain Web Push subscription info:
    {
      "endpoint": "https://...",
      "keys": {
        "p256dh": "...",
        "auth": "..."
      }
    }
    """
    user_id = current_user["id"]

    try:
        created_subscription = await repository.create_push_subscription(
            user_id=user_id,
            endpoint=subscription["endpoint"],
            p256dh_key=subscription["keys"]["p256dh"],
            auth_key=subscription["keys"]["auth"],
        )

        return {
            "success": True,
            "message": "Push subscription created successfully",
        }

    except KeyError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid subscription format: missing {str(e)}",
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create push subscription: {str(e)}",
        ) from e


@router.delete("/push/unsubscribe", response_model=NotificationResponse)
async def unsubscribe_from_push(
    endpoint: str = Query(..., description="Push subscription endpoint"),
    current_user: dict = Depends(get_current_user),
    repository: NotificationRepository = Depends(get_notification_repository),
):
    """
    Unsubscribe from push notifications.

    Deletes the subscription associated with the given endpoint.
    """
    user_id = current_user["id"]

    success = await repository.delete_push_subscription(
        user_id=user_id,
        endpoint=endpoint,
    )

    if not success:
        raise HTTPException(
            status_code=404,
            detail="Push subscription not found",
        )

    return {
        "success": True,
        "message": "Push subscription deleted successfully",
    }
