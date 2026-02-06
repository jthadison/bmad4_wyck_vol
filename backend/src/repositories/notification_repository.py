"""
Notification Repository

Handles database operations for notifications, preferences, and push subscriptions.
Provides async methods for creating, reading, and updating notification data.

Story: 11.6 - Notification & Alert System
"""

from datetime import datetime
from typing import Any, Optional, Union
from uuid import UUID

from sqlalchemy import and_, delete, desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.notification import (
    Notification,
    NotificationPreferences,
    NotificationType,
    PushSubscription,
)
from src.orm.models import NotificationORM, NotificationPreferencesORM, PushSubscriptionORM


def _to_uuid(value: Union[UUID, str]) -> UUID:
    """Convert string or UUID to UUID."""
    if isinstance(value, str):
        return UUID(value)
    return value


class NotificationRepository:
    """Repository for notification database operations."""

    def __init__(self, session: AsyncSession):
        """
        Initialize repository with database session.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    # =============================
    # Notification CRUD Operations
    # =============================

    async def create_notification(
        self,
        user_id: Union[UUID, str],
        notification_type: NotificationType,
        priority: str,
        title: str,
        message: str,
        metadata: dict[str, Any],
    ) -> Notification:
        """
        Create and persist a new notification.

        Args:
            user_id: Target user UUID (or string UUID)
            notification_type: Type of notification
            priority: Priority level (info/warning/critical)
            title: Notification title
            message: Notification message
            metadata: Type-specific metadata dict

        Returns:
            Created Notification model
        """
        user_uuid = _to_uuid(user_id)
        notification = NotificationORM(
            notification_type=notification_type.value,
            priority=priority,
            title=title,
            message=message,
            notification_metadata=metadata,
            user_id=user_uuid,
            read=False,
        )

        self.session.add(notification)
        await self.session.flush()
        await self.session.refresh(notification)

        return self._orm_to_notification(notification)

    async def get_notifications(
        self,
        user_id: Union[UUID, str],
        unread_only: bool = False,
        notification_type: Optional[NotificationType] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Notification], int]:
        """
        Get notifications for a user with optional filtering.

        Args:
            user_id: User UUID (or string UUID)
            unread_only: Only return unread notifications
            notification_type: Filter by notification type
            limit: Maximum number of results (default 50, max 100)
            offset: Result offset for pagination

        Returns:
            Tuple of (notifications list, total count)
        """
        user_uuid = _to_uuid(user_id)
        # Clamp limit to max 100
        limit = min(limit, 100)

        # Build query with filters
        query = select(NotificationORM).where(NotificationORM.user_id == user_uuid)

        if unread_only:
            query = query.where(NotificationORM.read == False)  # noqa: E712

        if notification_type:
            query = query.where(NotificationORM.notification_type == notification_type.value)

        # Get total count with same filters
        count_query = select(NotificationORM.id).where(NotificationORM.user_id == user_uuid)
        if unread_only:
            count_query = count_query.where(NotificationORM.read == False)  # noqa: E712
        if notification_type:
            count_query = count_query.where(
                NotificationORM.notification_type == notification_type.value
            )
        count_result = await self.session.execute(count_query)
        total_count = len(count_result.all())

        # Get paginated results ordered by most recent first
        query = query.order_by(desc(NotificationORM.created_at)).limit(limit).offset(offset)

        result = await self.session.execute(query)
        notifications = result.scalars().all()

        return ([self._orm_to_notification(n) for n in notifications], total_count)

    async def mark_as_read(
        self, notification_id: Union[UUID, str], user_id: Union[UUID, str]
    ) -> bool:
        """
        Mark a notification as read.

        Args:
            notification_id: Notification UUID (or string UUID)
            user_id: User UUID (or string UUID) for authorization check

        Returns:
            True if notification was found and marked, False otherwise
        """
        notif_uuid = _to_uuid(notification_id)
        user_uuid = _to_uuid(user_id)
        stmt = (
            update(NotificationORM)
            .where(
                and_(
                    NotificationORM.id == notif_uuid,
                    NotificationORM.user_id == user_uuid,
                )
            )
            .values(read=True)
        )

        result = await self.session.execute(stmt)
        await self.session.commit()

        return result.rowcount > 0

    async def get_unread_count(self, user_id: Union[UUID, str]) -> int:
        """
        Get count of unread notifications for a user.

        Args:
            user_id: User UUID (or string UUID)

        Returns:
            Number of unread notifications
        """
        user_uuid = _to_uuid(user_id)
        query = select(NotificationORM).where(
            and_(
                NotificationORM.user_id == user_uuid,
                NotificationORM.read == False,  # noqa: E712
            )
        )

        result = await self.session.execute(query)
        return len(result.all())

    # =============================
    # Preferences CRUD Operations
    # =============================

    async def get_preferences(self, user_id: Union[UUID, str]) -> Optional[NotificationPreferences]:
        """
        Get notification preferences for a user.

        Args:
            user_id: User UUID (or string UUID)

        Returns:
            NotificationPreferences model or None if not set
        """
        user_uuid = _to_uuid(user_id)
        stmt = select(NotificationPreferencesORM).where(
            NotificationPreferencesORM.user_id == user_uuid
        )

        result = await self.session.execute(stmt)
        prefs_orm = result.scalar_one_or_none()

        if not prefs_orm:
            return None

        # Deserialize JSON preferences to Pydantic model
        prefs_dict = prefs_orm.preferences.copy()
        prefs_dict["user_id"] = prefs_orm.user_id
        prefs_dict["updated_at"] = prefs_orm.updated_at

        return NotificationPreferences(**prefs_dict)

    async def update_preferences(
        self, preferences: NotificationPreferences
    ) -> NotificationPreferences:
        """
        Update or create notification preferences for a user.

        Args:
            preferences: New preferences model

        Returns:
            Updated NotificationPreferences model
        """
        user_uuid = _to_uuid(preferences.user_id)

        # Serialize Pydantic model to JSON (exclude user_id and updated_at)
        prefs_dict = preferences.model_dump(
            exclude={"user_id", "updated_at"},
            mode="json",
        )

        # Check if preferences already exist
        existing = await self.session.execute(
            select(NotificationPreferencesORM).where(
                NotificationPreferencesORM.user_id == user_uuid
            )
        )
        existing_prefs = existing.scalar_one_or_none()

        if existing_prefs:
            # Update existing preferences
            stmt = (
                update(NotificationPreferencesORM)
                .where(NotificationPreferencesORM.user_id == user_uuid)
                .values(preferences=prefs_dict, updated_at=datetime.utcnow())
            )
            await self.session.execute(stmt)
        else:
            # Insert new preferences
            new_prefs = NotificationPreferencesORM(
                user_id=user_uuid,
                preferences=prefs_dict,
                updated_at=datetime.utcnow(),
            )
            self.session.add(new_prefs)

        await self.session.commit()

        # Return updated preferences
        return await self.get_preferences(user_uuid)  # type: ignore

    # =============================
    # Push Subscription Operations
    # =============================

    async def create_push_subscription(
        self,
        user_id: Union[UUID, str],
        endpoint: str,
        p256dh_key: str,
        auth_key: str,
    ) -> PushSubscription:
        """
        Create or update a push subscription.

        Args:
            user_id: User UUID (or string UUID)
            endpoint: Push subscription endpoint URL
            p256dh_key: Public key for encryption
            auth_key: Authentication secret

        Returns:
            Created PushSubscription model
        """
        user_uuid = _to_uuid(user_id)

        # Check if subscription already exists
        existing = await self.session.execute(
            select(PushSubscriptionORM).where(
                and_(
                    PushSubscriptionORM.user_id == user_uuid,
                    PushSubscriptionORM.endpoint == endpoint,
                )
            )
        )
        existing_sub = existing.scalar_one_or_none()

        if existing_sub:
            # Update existing subscription
            stmt = (
                update(PushSubscriptionORM)
                .where(
                    and_(
                        PushSubscriptionORM.user_id == user_uuid,
                        PushSubscriptionORM.endpoint == endpoint,
                    )
                )
                .values(
                    p256dh_key=p256dh_key,
                    auth_key=auth_key,
                    created_at=datetime.utcnow(),
                )
            )
            await self.session.execute(stmt)
        else:
            # Insert new subscription
            new_sub = PushSubscriptionORM(
                user_id=user_uuid,
                endpoint=endpoint,
                p256dh_key=p256dh_key,
                auth_key=auth_key,
            )
            self.session.add(new_sub)

        await self.session.commit()

        # Fetch the subscription
        query = select(PushSubscriptionORM).where(
            and_(
                PushSubscriptionORM.user_id == user_uuid,
                PushSubscriptionORM.endpoint == endpoint,
            )
        )
        result = await self.session.execute(query)
        subscription = result.scalar_one()

        return self._orm_to_push_subscription(subscription)

    async def get_push_subscriptions(self, user_id: Union[UUID, str]) -> list[PushSubscription]:
        """
        Get all push subscriptions for a user.

        Args:
            user_id: User UUID (or string UUID)

        Returns:
            List of PushSubscription models
        """
        user_uuid = _to_uuid(user_id)
        stmt = select(PushSubscriptionORM).where(PushSubscriptionORM.user_id == user_uuid)

        result = await self.session.execute(stmt)
        subscriptions = result.scalars().all()

        return [self._orm_to_push_subscription(s) for s in subscriptions]

    async def delete_push_subscription(self, user_id: Union[UUID, str], endpoint: str) -> bool:
        """
        Delete a push subscription (e.g., when it expires or is unsubscribed).

        Args:
            user_id: User UUID (or string UUID)
            endpoint: Push subscription endpoint URL

        Returns:
            True if subscription was deleted, False if not found
        """
        user_uuid = _to_uuid(user_id)
        stmt = delete(PushSubscriptionORM).where(
            and_(
                PushSubscriptionORM.user_id == user_uuid,
                PushSubscriptionORM.endpoint == endpoint,
            )
        )

        result = await self.session.execute(stmt)
        await self.session.commit()

        return result.rowcount > 0

    # =============================
    # Helper Methods
    # =============================

    def _orm_to_notification(self, orm: NotificationORM) -> Notification:
        """Convert ORM model to Pydantic model."""
        return Notification(
            id=orm.id,
            notification_type=NotificationType(orm.notification_type),
            priority=orm.priority,
            title=orm.title,
            message=orm.message,
            metadata=orm.notification_metadata,
            user_id=orm.user_id,
            read=orm.read,
            created_at=orm.created_at,
        )

    def _orm_to_push_subscription(self, orm: PushSubscriptionORM) -> PushSubscription:
        """Convert ORM model to Pydantic model."""
        return PushSubscription(
            user_id=orm.user_id,
            endpoint=orm.endpoint,
            p256dh_key=orm.p256dh_key,
            auth_key=orm.auth_key,
            created_at=orm.created_at,
        )
