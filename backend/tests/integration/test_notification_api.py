"""
Integration Tests for Notification API Routes

Tests all 7 notification REST API endpoints with real database.
Uses httpx.AsyncClient to test FastAPI routes.

Story: 11.6 - Notification & Alert System
"""

from datetime import datetime
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.notification import NotificationPreferences, NotificationType
from src.repositories.notification_repository import NotificationRepository


@pytest.mark.integration
class TestNotificationAPI:
    """Integration tests for notification API endpoints."""

    @pytest.fixture
    async def notification_repository(self, db_session: AsyncSession) -> NotificationRepository:
        """Provide a NotificationRepository instance."""
        return NotificationRepository(db_session)

    # =============================
    # GET /api/v1/notifications
    # =============================

    @pytest.mark.asyncio
    async def test_get_notifications_empty(
        self,
        async_client: AsyncClient,
        test_user_id: UUID,
        auth_headers: dict,
    ):
        """Test getting notifications when user has none."""
        # Mock the get_current_user dependency
        from src.api.dependencies import get_current_user
        from src.api.main import app

        def mock_get_current_user():
            return {"id": str(test_user_id)}

        app.dependency_overrides[get_current_user] = mock_get_current_user

        try:
            response = await async_client.get(
                "/api/v1/notifications",
                headers=auth_headers,
            )

            assert response.status_code == 200
            data = response.json()
            assert data["data"] == []
            assert data["pagination"]["returned_count"] == 0
            assert data["pagination"]["total_count"] == 0
            assert data["pagination"]["has_more"] is False
        finally:
            del app.dependency_overrides[get_current_user]

    @pytest.mark.asyncio
    async def test_get_notifications_with_data(
        self,
        async_client: AsyncClient,
        notification_repository: NotificationRepository,
        test_user_id: UUID,
        auth_headers: dict,
    ):
        """Test getting notifications with data."""
        # Create test notifications
        user_uuid = test_user_id
        for i in range(5):
            await notification_repository.create_notification(
                user_id=user_uuid,
                notification_type=NotificationType.SIGNAL_GENERATED,
                priority="info",
                title=f"Signal {i}",
                message=f"Message {i}",
                metadata={"confidence": 85 + i},
            )

        # Mock the get_current_user dependency
        from src.api.dependencies import get_current_user
        from src.api.main import app

        def mock_get_current_user():
            return {"id": str(user_uuid)}

        app.dependency_overrides[get_current_user] = mock_get_current_user

        try:
            response = await async_client.get(
                "/api/v1/notifications",
                headers=auth_headers,
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data["data"]) == 5
            assert data["pagination"]["returned_count"] == 5
            assert data["pagination"]["total_count"] == 5
            assert data["pagination"]["has_more"] is False
        finally:
            del app.dependency_overrides[get_current_user]

    @pytest.mark.asyncio
    async def test_get_notifications_pagination(
        self,
        async_client: AsyncClient,
        notification_repository: NotificationRepository,
        test_user_id: UUID,
        auth_headers: dict,
    ):
        """Test notification pagination."""
        # Create test notifications
        user_uuid = test_user_id
        for i in range(10):
            await notification_repository.create_notification(
                user_id=user_uuid,
                notification_type=NotificationType.SIGNAL_GENERATED,
                priority="info",
                title=f"Signal {i}",
                message=f"Message {i}",
                metadata={},
            )

        # Mock the get_current_user dependency
        from src.api.dependencies import get_current_user
        from src.api.main import app

        def mock_get_current_user():
            return {"id": str(user_uuid)}

        app.dependency_overrides[get_current_user] = mock_get_current_user

        try:
            # Get first page
            response = await async_client.get(
                "/api/v1/notifications?limit=5&offset=0",
                headers=auth_headers,
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data["data"]) == 5
            assert data["pagination"]["returned_count"] == 5
            assert data["pagination"]["total_count"] == 10
            assert data["pagination"]["has_more"] is True

            # Get second page
            response = await async_client.get(
                "/api/v1/notifications?limit=5&offset=5",
                headers=auth_headers,
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data["data"]) == 5
            assert data["pagination"]["returned_count"] == 5
            assert data["pagination"]["total_count"] == 10
            assert data["pagination"]["has_more"] is False
        finally:
            del app.dependency_overrides[get_current_user]

    @pytest.mark.asyncio
    async def test_get_notifications_filter_unread(
        self,
        async_client: AsyncClient,
        notification_repository: NotificationRepository,
        test_user_id: UUID,
        auth_headers: dict,
    ):
        """Test filtering notifications by unread status."""
        user_uuid = test_user_id

        # Create notifications
        notif_ids = []
        for i in range(3):
            notif = await notification_repository.create_notification(
                user_id=user_uuid,
                notification_type=NotificationType.SIGNAL_GENERATED,
                priority="info",
                title=f"Signal {i}",
                message=f"Message {i}",
                metadata={},
            )
            notif_ids.append(notif.id)

        # Mark first one as read
        await notification_repository.mark_as_read(notif_ids[0], user_uuid)

        # Mock the get_current_user dependency
        from src.api.dependencies import get_current_user
        from src.api.main import app

        def mock_get_current_user():
            return {"id": str(user_uuid)}

        app.dependency_overrides[get_current_user] = mock_get_current_user

        try:
            # Get unread only
            response = await async_client.get(
                "/api/v1/notifications?unread_only=true",
                headers=auth_headers,
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data["data"]) == 2  # Only unread
            assert data["pagination"]["total_count"] == 2
        finally:
            del app.dependency_overrides[get_current_user]

    @pytest.mark.asyncio
    async def test_get_notifications_filter_by_type(
        self,
        async_client: AsyncClient,
        notification_repository: NotificationRepository,
        test_user_id: UUID,
        auth_headers: dict,
    ):
        """Test filtering notifications by type."""
        user_uuid = test_user_id

        # Create different types
        await notification_repository.create_notification(
            user_id=user_uuid,
            notification_type=NotificationType.SIGNAL_GENERATED,
            priority="info",
            title="Signal",
            message="Message",
            metadata={},
        )
        await notification_repository.create_notification(
            user_id=user_uuid,
            notification_type=NotificationType.RISK_WARNING,
            priority="warning",
            title="Risk",
            message="Warning",
            metadata={},
        )

        # Mock the get_current_user dependency
        from src.api.dependencies import get_current_user
        from src.api.main import app

        def mock_get_current_user():
            return {"id": str(user_uuid)}

        app.dependency_overrides[get_current_user] = mock_get_current_user

        try:
            # Filter by SIGNAL_GENERATED
            response = await async_client.get(
                "/api/v1/notifications?notification_type=signal_generated",
                headers=auth_headers,
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data["data"]) == 1
            assert data["data"][0]["notification_type"] == "signal_generated"
        finally:
            del app.dependency_overrides[get_current_user]

    # =============================
    # PATCH /api/v1/notifications/{id}/read
    # =============================

    @pytest.mark.asyncio
    async def test_mark_notification_read(
        self,
        async_client: AsyncClient,
        notification_repository: NotificationRepository,
        test_user_id: UUID,
        auth_headers: dict,
    ):
        """Test marking a notification as read."""
        user_uuid = test_user_id

        # Create notification
        notif = await notification_repository.create_notification(
            user_id=user_uuid,
            notification_type=NotificationType.SIGNAL_GENERATED,
            priority="info",
            title="Signal",
            message="Message",
            metadata={},
        )

        assert notif.read is False

        # Mock the get_current_user dependency
        from src.api.dependencies import get_current_user
        from src.api.main import app

        def mock_get_current_user():
            return {"id": str(user_uuid)}

        app.dependency_overrides[get_current_user] = mock_get_current_user

        try:
            # Mark as read
            response = await async_client.patch(
                f"/api/v1/notifications/{notif.id}/read",
                headers=auth_headers,
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["notification_id"] == str(notif.id)

            # Verify it's read
            notifications, _ = await notification_repository.get_notifications(
                user_id=user_uuid,
                limit=50,
                offset=0,
            )
            assert notifications[0].read is True
        finally:
            del app.dependency_overrides[get_current_user]

    @pytest.mark.asyncio
    async def test_mark_notification_read_not_found(
        self,
        async_client: AsyncClient,
        test_user_id: UUID,
        auth_headers: dict,
    ):
        """Test marking non-existent notification returns 404."""
        user_uuid = test_user_id
        fake_id = uuid4()

        # Mock the get_current_user dependency
        from src.api.dependencies import get_current_user
        from src.api.main import app

        def mock_get_current_user():
            return {"id": str(user_uuid)}

        app.dependency_overrides[get_current_user] = mock_get_current_user

        try:
            response = await async_client.patch(
                f"/api/v1/notifications/{fake_id}/read",
                headers=auth_headers,
            )

            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()
        finally:
            del app.dependency_overrides[get_current_user]

    # =============================
    # GET /api/v1/notifications/preferences
    # =============================

    @pytest.mark.asyncio
    async def test_get_preferences_not_exists(
        self,
        async_client: AsyncClient,
        test_user_id: UUID,
        auth_headers: dict,
    ):
        """Test getting preferences when none exist returns defaults."""
        user_uuid = test_user_id

        # Mock the get_current_user dependency
        from src.api.dependencies import get_current_user
        from src.api.main import app

        def mock_get_current_user():
            return {"id": str(user_uuid)}

        app.dependency_overrides[get_current_user] = mock_get_current_user

        try:
            response = await async_client.get(
                "/api/v1/notifications/preferences",
                headers=auth_headers,
            )

            assert response.status_code == 200
            data = response.json()
            assert data["user_id"] == str(user_uuid)
            assert data["email_enabled"] is True  # Default
            assert data["sms_enabled"] is False  # Default
            assert data["min_confidence_threshold"] == 85  # Default
        finally:
            del app.dependency_overrides[get_current_user]

    @pytest.mark.asyncio
    async def test_get_preferences_exists(
        self,
        async_client: AsyncClient,
        notification_repository: NotificationRepository,
        test_user_id: UUID,
        auth_headers: dict,
    ):
        """Test getting existing preferences."""
        user_uuid = test_user_id

        # Create preferences
        prefs = NotificationPreferences(
            user_id=user_uuid,
            email_enabled=True,
            email_address="test@example.com",
            sms_enabled=True,
            sms_phone_number="+11234567890",
            min_confidence_threshold=90,
            updated_at=datetime.utcnow(),
        )
        await notification_repository.update_preferences(prefs)

        # Mock the get_current_user dependency
        from src.api.dependencies import get_current_user
        from src.api.main import app

        def mock_get_current_user():
            return {"id": str(user_uuid)}

        app.dependency_overrides[get_current_user] = mock_get_current_user

        try:
            response = await async_client.get(
                "/api/v1/notifications/preferences",
                headers=auth_headers,
            )

            assert response.status_code == 200
            data = response.json()
            assert data["user_id"] == str(user_uuid)
            assert data["email_enabled"] is True
            assert data["email_address"] == "test@example.com"
            assert data["sms_enabled"] is True
            assert data["sms_phone_number"] == "+11234567890"
            assert data["min_confidence_threshold"] == 90
        finally:
            del app.dependency_overrides[get_current_user]

    # =============================
    # POST /api/v1/notifications/preferences
    # =============================

    @pytest.mark.asyncio
    async def test_update_preferences(
        self,
        async_client: AsyncClient,
        notification_repository: NotificationRepository,
        test_user_id: UUID,
        auth_headers: dict,
    ):
        """Test updating notification preferences."""
        user_uuid = test_user_id

        # Mock the get_current_user dependency
        from src.api.dependencies import get_current_user
        from src.api.main import app

        def mock_get_current_user():
            return {"id": str(user_uuid)}

        app.dependency_overrides[get_current_user] = mock_get_current_user

        try:
            # Update preferences
            response = await async_client.post(
                "/api/v1/notifications/preferences",
                headers=auth_headers,
                json={
                    "user_id": str(user_uuid),
                    "email_enabled": True,
                    "email_address": "test@example.com",
                    "sms_enabled": True,
                    "sms_phone_number": "+11234567890",
                    "min_confidence_threshold": 90,
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

            # Verify updated
            prefs = await notification_repository.get_preferences(user_uuid)
            assert prefs is not None
            assert prefs.email_enabled is True
            assert prefs.email_address == "test@example.com"
            assert prefs.min_confidence_threshold == 90
        finally:
            del app.dependency_overrides[get_current_user]

    @pytest.mark.asyncio
    async def test_update_preferences_wrong_user(
        self,
        async_client: AsyncClient,
        test_user_id: UUID,
        auth_headers: dict,
    ):
        """Test updating preferences for different user returns 403."""
        user_uuid = test_user_id
        other_user_uuid = uuid4()  # Generate a different user ID

        # Mock the get_current_user dependency
        from src.api.dependencies import get_current_user
        from src.api.main import app

        def mock_get_current_user():
            return {"id": str(user_uuid)}

        app.dependency_overrides[get_current_user] = mock_get_current_user

        try:
            # Try to update other user's preferences
            response = await async_client.post(
                "/api/v1/notifications/preferences",
                headers=auth_headers,
                json={
                    "user_id": str(other_user_uuid),  # Different user
                    "email_enabled": True,
                    "min_confidence_threshold": 90,
                },
            )

            assert response.status_code == 403
            assert "another user" in response.json()["detail"].lower()
        finally:
            del app.dependency_overrides[get_current_user]

    # =============================
    # POST /api/v1/notifications/push/subscribe
    # =============================

    @pytest.mark.asyncio
    async def test_subscribe_to_push(
        self,
        async_client: AsyncClient,
        notification_repository: NotificationRepository,
        test_user_id: UUID,
        auth_headers: dict,
    ):
        """Test creating a push subscription."""
        user_uuid = test_user_id

        # Mock the get_current_user dependency
        from src.api.dependencies import get_current_user
        from src.api.main import app

        def mock_get_current_user():
            return {"id": str(user_uuid)}

        app.dependency_overrides[get_current_user] = mock_get_current_user

        try:
            response = await async_client.post(
                "/api/v1/notifications/push/subscribe",
                headers=auth_headers,
                json={
                    "endpoint": "https://fcm.googleapis.com/fcm/send/test123",
                    "keys": {
                        "p256dh": "test_p256dh_key",
                        "auth": "test_auth_key",
                    },
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

            # Verify subscription created
            subs = await notification_repository.get_push_subscriptions(user_uuid)
            assert len(subs) == 1
            assert subs[0].endpoint == "https://fcm.googleapis.com/fcm/send/test123"
        finally:
            del app.dependency_overrides[get_current_user]

    @pytest.mark.asyncio
    async def test_subscribe_to_push_invalid_format(
        self,
        async_client: AsyncClient,
        test_user_id: UUID,
        auth_headers: dict,
    ):
        """Test push subscription with invalid format returns 400."""
        user_uuid = test_user_id

        # Mock the get_current_user dependency
        from src.api.dependencies import get_current_user
        from src.api.main import app

        def mock_get_current_user():
            return {"id": str(user_uuid)}

        app.dependency_overrides[get_current_user] = mock_get_current_user

        try:
            # Missing keys field
            response = await async_client.post(
                "/api/v1/notifications/push/subscribe",
                headers=auth_headers,
                json={
                    "endpoint": "https://fcm.googleapis.com/fcm/send/test123",
                },
            )

            assert response.status_code == 400
            assert "missing" in response.json()["detail"].lower()
        finally:
            del app.dependency_overrides[get_current_user]

    # =============================
    # DELETE /api/v1/notifications/push/unsubscribe
    # =============================

    @pytest.mark.asyncio
    async def test_unsubscribe_from_push(
        self,
        async_client: AsyncClient,
        notification_repository: NotificationRepository,
        test_user_id: UUID,
        auth_headers: dict,
    ):
        """Test deleting a push subscription."""
        user_uuid = test_user_id

        # Create subscription
        await notification_repository.create_push_subscription(
            user_id=user_uuid,
            endpoint="https://fcm.googleapis.com/fcm/send/test123",
            p256dh_key="key",
            auth_key="auth",
        )

        # Mock the get_current_user dependency
        from src.api.dependencies import get_current_user
        from src.api.main import app

        def mock_get_current_user():
            return {"id": str(user_uuid)}

        app.dependency_overrides[get_current_user] = mock_get_current_user

        try:
            response = await async_client.delete(
                "/api/v1/notifications/push/unsubscribe",
                headers=auth_headers,
                params={"endpoint": "https://fcm.googleapis.com/fcm/send/test123"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

            # Verify deleted
            subs = await notification_repository.get_push_subscriptions(user_uuid)
            assert len(subs) == 0
        finally:
            del app.dependency_overrides[get_current_user]

    @pytest.mark.asyncio
    async def test_unsubscribe_from_push_not_found(
        self,
        async_client: AsyncClient,
        test_user_id: UUID,
        auth_headers: dict,
    ):
        """Test unsubscribing non-existent subscription returns 404."""
        user_uuid = test_user_id

        # Mock the get_current_user dependency
        from src.api.dependencies import get_current_user
        from src.api.main import app

        def mock_get_current_user():
            return {"id": str(user_uuid)}

        app.dependency_overrides[get_current_user] = mock_get_current_user

        try:
            response = await async_client.delete(
                "/api/v1/notifications/push/unsubscribe",
                headers=auth_headers,
                params={"endpoint": "https://fcm.googleapis.com/fcm/send/notfound"},
            )

            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()
        finally:
            del app.dependency_overrides[get_current_user]
