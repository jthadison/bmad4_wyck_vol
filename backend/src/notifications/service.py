"""
Notification Service Core

Central orchestrator for all notification channels. Handles:
- Notification filtering (confidence threshold, quiet hours)
- Channel routing based on priority
- Persistence to database
- Delegation to channel-specific clients

Story: 11.6 - Notification & Alert System
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

import pytz
import structlog

from src.models.notification import (
    Notification,
    NotificationChannel,
    NotificationPreferences,
    NotificationPriority,
    NotificationType,
    QuietHours,
)
from src.repositories.notification_repository import NotificationRepository

logger = structlog.get_logger(__name__)


class NotificationService:
    """
    Core notification orchestration service.

    Handles filtering, routing, and delivery of notifications across channels.
    """

    def __init__(
        self,
        repository: NotificationRepository,
        twilio_client: Optional["TwilioClient"] = None,
        email_client: Optional["EmailClient"] = None,
        push_client: Optional["PushClient"] = None,
        websocket_manager: Optional[any] = None,
    ):
        """
        Initialize notification service with channel clients.

        Args:
            repository: Notification repository for database operations
            twilio_client: Optional Twilio SMS client
            email_client: Optional email SMTP client
            push_client: Optional Web Push client
            websocket_manager: Optional WebSocket manager for toast notifications
        """
        self.repository = repository
        self.twilio_client = twilio_client
        self.email_client = email_client
        self.push_client = push_client
        self.websocket_manager = websocket_manager

    async def send_notification(
        self,
        user_id: UUID,
        notification_type: NotificationType,
        priority: NotificationPriority,
        title: str,
        message: str,
        metadata: dict,
    ) -> Optional[Notification]:
        """
        Send a notification through appropriate channels.

        Applies filtering, routing, persistence, and channel delegation.

        Args:
            user_id: Target user UUID
            notification_type: Type of notification
            priority: Priority level (determines channels)
            title: Notification title
            message: Notification message
            metadata: Type-specific metadata

        Returns:
            Created Notification if sent, None if filtered out
        """
        # Get user preferences
        preferences = await self.repository.get_preferences(user_id)

        # If no preferences exist, use defaults
        if not preferences:
            logger.info(
                "No preferences found for user, using defaults",
                user_id=str(user_id),
            )
            # Create default preferences (won't send channels unless enabled)
            from datetime import datetime

            preferences = NotificationPreferences(
                user_id=user_id,
                updated_at=datetime.utcnow(),
            )

        # Apply confidence threshold filter (only for SIGNAL_GENERATED)
        if notification_type == NotificationType.SIGNAL_GENERATED:
            confidence = metadata.get("confidence", 0)
            if confidence < preferences.min_confidence_threshold:
                logger.info(
                    "Notification filtered by confidence threshold",
                    user_id=str(user_id),
                    confidence=confidence,
                    threshold=preferences.min_confidence_threshold,
                )
                return None

        # Apply quiet hours filter (except for CRITICAL)
        if priority != NotificationPriority.CRITICAL:
            if self._is_quiet_hours(preferences.quiet_hours):
                logger.info(
                    "Notification filtered by quiet hours",
                    user_id=str(user_id),
                    priority=priority.value,
                )
                return None

        # Persist notification to database
        notification = await self.repository.create_notification(
            user_id=user_id,
            notification_type=notification_type,
            priority=priority.value,
            title=title,
            message=message,
            metadata=metadata,
        )

        logger.info(
            "Notification created",
            notification_id=str(notification.id),
            user_id=str(user_id),
            notification_type=notification_type.value,
            priority=priority.value,
        )

        # Determine channels based on priority and preferences
        channels = self._get_channels_for_priority(priority, preferences)

        # Send to each enabled channel
        await self._route_to_channels(notification, channels, preferences)

        return notification

    def _is_quiet_hours(self, quiet_hours: QuietHours) -> bool:
        """
        Check if current time is within quiet hours.

        Args:
            quiet_hours: Quiet hours configuration

        Returns:
            True if currently in quiet hours, False otherwise
        """
        if not quiet_hours.enabled:
            return False

        # Get current time in user's timezone
        tz = pytz.timezone(quiet_hours.timezone)
        now = datetime.now(tz).time()

        start = quiet_hours.start_time
        end = quiet_hours.end_time

        # Handle quiet hours that span midnight
        if start <= end:
            # Normal range (e.g., 22:00 - 23:59)
            return start <= now <= end
        else:
            # Spans midnight (e.g., 22:00 - 08:00)
            return now >= start or now <= end

    def _get_channels_for_priority(
        self,
        priority: NotificationPriority,
        preferences: NotificationPreferences,
    ) -> list[NotificationChannel]:
        """
        Get enabled channels for a priority level.

        Args:
            priority: Notification priority
            preferences: User preferences

        Returns:
            List of enabled channels for this priority
        """
        channel_prefs = preferences.channel_preferences

        # Map priority to configured channels
        if priority == NotificationPriority.INFO:
            base_channels = channel_prefs.info_channels
        elif priority == NotificationPriority.WARNING:
            base_channels = channel_prefs.warning_channels
        else:  # CRITICAL
            base_channels = channel_prefs.critical_channels

        # Filter by user's enabled channels
        enabled_channels = []

        for channel in base_channels:
            if channel == NotificationChannel.TOAST:
                # Toast always enabled (WebSocket)
                enabled_channels.append(channel)
            elif channel == NotificationChannel.EMAIL and preferences.email_enabled:
                if preferences.email_address:
                    enabled_channels.append(channel)
            elif channel == NotificationChannel.SMS and preferences.sms_enabled:
                if preferences.sms_phone_number:
                    enabled_channels.append(channel)
            elif channel == NotificationChannel.PUSH and preferences.push_enabled:
                enabled_channels.append(channel)

        return enabled_channels

    async def _route_to_channels(
        self,
        notification: Notification,
        channels: list[NotificationChannel],
        preferences: NotificationPreferences,
    ) -> None:
        """
        Route notification to specified channels.

        Args:
            notification: Notification to send
            channels: List of channels to use
            preferences: User preferences (for contact info)
        """
        for channel in channels:
            try:
                if channel == NotificationChannel.TOAST:
                    await self._send_toast(notification)
                elif channel == NotificationChannel.EMAIL:
                    await self._send_email(notification, preferences.email_address)  # type: ignore
                elif channel == NotificationChannel.SMS:
                    await self._send_sms(notification, preferences.sms_phone_number)  # type: ignore
                elif channel == NotificationChannel.PUSH:
                    await self._send_push(notification, notification.user_id)

                logger.info(
                    "Notification sent via channel",
                    notification_id=str(notification.id),
                    channel=channel.value,
                )

            except Exception as e:
                logger.error(
                    "Failed to send notification via channel",
                    notification_id=str(notification.id),
                    channel=channel.value,
                    error=str(e),
                    exc_info=True,
                )

    async def _send_toast(self, notification: Notification) -> None:
        """
        Send toast notification via WebSocket.

        Args:
            notification: Notification to send
        """
        if not self.websocket_manager:
            logger.warning("WebSocket manager not configured, skipping toast")
            return

        # Emit notification_toast to all connected WebSocket clients
        await self.websocket_manager.emit_notification_toast(notification)

    async def _send_email(self, notification: Notification, email_address: str) -> None:
        """
        Send email notification.

        Args:
            notification: Notification to send
            email_address: Recipient email address
        """
        if not self.email_client:
            logger.warning("Email client not configured, skipping email")
            return

        await self.email_client.send_notification_email(
            to_address=email_address,
            notification=notification,
        )

    async def _send_sms(self, notification: Notification, phone_number: str) -> None:
        """
        Send SMS notification via Twilio.

        Args:
            notification: Notification to send
            phone_number: Recipient phone number (E.164 format)
        """
        if not self.twilio_client:
            logger.warning("Twilio client not configured, skipping SMS")
            return

        # Format message for SMS (brief)
        sms_text = f"{notification.title}\n{notification.message}"

        await self.twilio_client.send_sms(
            phone_number=phone_number,
            message=sms_text,
        )

    async def _send_push(self, notification: Notification, user_id: UUID) -> None:
        """
        Send push notification to user's subscribed devices.

        Args:
            notification: Notification to send
            user_id: User UUID (to get subscriptions)
        """
        if not self.push_client:
            logger.warning("Push client not configured, skipping push")
            return

        # Get user's push subscriptions
        subscriptions = await self.repository.get_push_subscriptions(user_id)

        for subscription in subscriptions:
            try:
                await self.push_client.send_push_notification(
                    subscription=subscription,
                    notification=notification,
                )
            except Exception as e:
                logger.error(
                    "Failed to send push to subscription",
                    subscription_endpoint=self._mask_endpoint(subscription.endpoint),
                    error=str(e),
                )

                # If subscription expired (410 Gone), delete it
                if "410" in str(e) or "expired" in str(e).lower():
                    await self.repository.delete_push_subscription(
                        user_id=user_id,
                        endpoint=subscription.endpoint,
                    )
                    logger.info(
                        "Deleted expired push subscription",
                        user_id=str(user_id),
                    )

    def _mask_endpoint(self, endpoint: str) -> str:
        """Mask push endpoint for logging (PII protection)."""
        if len(endpoint) > 40:
            return endpoint[:20] + "..." + endpoint[-10:]
        return endpoint
