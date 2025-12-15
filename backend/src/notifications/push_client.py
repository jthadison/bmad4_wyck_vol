"""
Web Push Notification Client

Handles browser push notifications using Web Push protocol with:
- VAPID authentication
- Payload encryption
- Subscription management
- Expiration handling

Story: 11.6 - Notification & Alert System
"""

import json
from typing import Optional

import structlog

from src.models.notification import Notification, PushSubscription

logger = structlog.get_logger(__name__)


class PushClient:
    """
    Web Push client for browser push notifications.

    Uses pywebpush library and VAPID keys for authentication.
    """

    def __init__(
        self,
        vapid_private_key: Optional[str] = None,
        vapid_claims_email: Optional[str] = None,
        test_mode: bool = False,
    ):
        """
        Initialize push client.

        Args:
            vapid_private_key: VAPID private key for authentication
            vapid_claims_email: Email for VAPID claims (e.g., mailto:admin@example.com)
            test_mode: If True, log instead of sending
        """
        self.vapid_private_key = vapid_private_key
        self.vapid_claims_email = vapid_claims_email
        self.test_mode = test_mode

        if not test_mode and not all([vapid_private_key, vapid_claims_email]):
            logger.warning(
                "VAPID keys not configured, running in test mode",
                test_mode=True,
            )
            self.test_mode = True

    async def send_push_notification(
        self,
        subscription: PushSubscription,
        notification: Notification,
    ) -> bool:
        """
        Send push notification to a subscription.

        Args:
            subscription: Push subscription info
            notification: Notification to send

        Returns:
            True if sent successfully, False otherwise

        Raises:
            Exception: If push fails (including 410 Gone for expired subscriptions)
        """
        if self.test_mode:
            logger.info(
                "TEST MODE: Push notification would be sent",
                endpoint=self._mask_endpoint(subscription.endpoint),
                title=notification.title,
            )
            return True

        # Prepare push payload
        payload = self._create_payload(notification)

        try:
            from pywebpush import webpush

            # Send push notification
            webpush(
                subscription_info={
                    "endpoint": subscription.endpoint,
                    "keys": {
                        "p256dh": subscription.p256dh_key,
                        "auth": subscription.auth_key,
                    },
                },
                data=json.dumps(payload),
                vapid_private_key=self.vapid_private_key,
                vapid_claims={"sub": self.vapid_claims_email},
            )

            logger.info(
                "Push notification sent successfully",
                endpoint=self._mask_endpoint(subscription.endpoint),
                notification_id=str(notification.id),
            )

            return True

        except Exception as e:
            error_message = str(e)

            # Check for expired subscription (410 Gone)
            if "410" in error_message:
                logger.warning(
                    "Push subscription expired (410 Gone)",
                    endpoint=self._mask_endpoint(subscription.endpoint),
                )
                # Re-raise to let caller handle deletion
                raise

            logger.error(
                "Failed to send push notification",
                endpoint=self._mask_endpoint(subscription.endpoint),
                error=error_message,
            )

            return False

    async def send_test_push(
        self,
        subscription: PushSubscription,
    ) -> bool:
        """
        Send test push notification for verification.

        Args:
            subscription: Push subscription info

        Returns:
            True if sent successfully
        """
        # Create test notification
        from datetime import datetime
        from uuid import uuid4

        from src.models.notification import NotificationPriority, NotificationType

        test_notification = Notification(
            id=uuid4(),
            notification_type=NotificationType.SYSTEM_ERROR,  # Test type
            priority=NotificationPriority.INFO.value,
            title="Test Push Notification",
            message="Your browser push notifications are configured correctly.",
            metadata={},
            user_id=subscription.user_id,
            read=False,
            created_at=datetime.utcnow(),
        )

        return await self.send_push_notification(subscription, test_notification)

    def _create_payload(self, notification: Notification) -> dict:
        """
        Create push notification payload.

        Args:
            notification: Notification to send

        Returns:
            Push payload dict
        """
        # Web Push payload format
        # See: https://developer.mozilla.org/en-US/docs/Web/API/ServiceWorkerRegistration/showNotification
        payload = {
            "title": notification.title,
            "body": notification.message,
            "icon": "/static/icon-192.png",  # App icon
            "badge": "/static/badge-72.png",  # Badge icon
            "tag": str(notification.id),  # Notification ID for replacement
            "data": {
                "notification_id": str(notification.id),
                "notification_type": notification.notification_type.value,
                "metadata": notification.metadata,
                "created_at": notification.created_at.isoformat(),
            },
            "requireInteraction": notification.priority == "critical",  # Sticky for critical
        }

        # Add action buttons based on notification type
        if notification.notification_type.value == "signal_generated":
            payload["actions"] = [
                {
                    "action": "view",
                    "title": "View Signal",
                },
                {
                    "action": "dismiss",
                    "title": "Dismiss",
                },
            ]

        return payload

    def _mask_endpoint(self, endpoint: str) -> str:
        """Mask push endpoint for logging (PII protection)."""
        if len(endpoint) > 40:
            return endpoint[:20] + "..." + endpoint[-10:]
        return endpoint

    @staticmethod
    def generate_vapid_keys() -> tuple[str, str]:
        """
        Generate VAPID key pair for push authentication.

        Returns:
            Tuple of (private_key, public_key)
        """
        from py_vapid import Vapid

        vapid = Vapid()
        vapid.generate_keys()

        private_key = vapid.private_key.to_string().decode("utf-8")
        public_key = vapid.public_key.to_string().decode("utf-8")

        return (private_key, public_key)

    @staticmethod
    def save_vapid_keys(private_key: str, public_key: str, file_path: str = "vapid_keys.json"):
        """
        Save VAPID keys to file.

        Args:
            private_key: Private key string
            public_key: Public key string
            file_path: Path to save keys
        """
        keys = {
            "private_key": private_key,
            "public_key": public_key,
        }

        with open(file_path, "w") as f:
            json.dump(keys, f, indent=2)

        logger.info("VAPID keys saved", file_path=file_path)

    @staticmethod
    def load_vapid_keys(file_path: str = "vapid_keys.json") -> tuple[str, str]:
        """
        Load VAPID keys from file.

        Args:
            file_path: Path to keys file

        Returns:
            Tuple of (private_key, public_key)
        """
        with open(file_path) as f:
            keys = json.load(f)

        return (keys["private_key"], keys["public_key"])
