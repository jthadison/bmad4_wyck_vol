"""
Unit tests for Email Notification Settings API Routes (Story 19.25).

Tests:
- GET /api/v1/settings/notifications
- PUT /api/v1/settings/notifications/email
"""

from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.dependencies import get_current_user_id
from src.api.routes.settings import (
    _user_email_settings,
    get_email_rate_limiter,
    router,
)
from src.models.notification import EmailNotificationSettings

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_user_id():
    """Create mock user ID."""
    return uuid4()


@pytest.fixture
def app(mock_user_id):
    """Create test FastAPI app with auth override."""
    app = FastAPI()
    app.include_router(router)

    # Override auth dependency to return mock user ID
    def override_get_current_user_id() -> UUID:
        return mock_user_id

    app.dependency_overrides[get_current_user_id] = override_get_current_user_id
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_settings():
    """Clear settings before each test."""
    _user_email_settings.clear()
    yield
    _user_email_settings.clear()


# ============================================================================
# GET /api/v1/settings/notifications Tests
# ============================================================================


class TestGetNotificationSettings:
    """Tests for GET /api/v1/settings/notifications."""

    def test_get_default_settings(self, client):
        """Test getting default settings for new user."""
        response = client.get("/api/v1/settings/notifications")

        assert response.status_code == 200
        data = response.json()

        # Check email settings
        assert "email" in data
        assert data["email"]["enabled"] is False
        assert data["email"]["address"] is None
        assert data["email"]["notify_all_signals"] is False
        assert data["email"]["notify_auto_executions"] is True
        assert data["email"]["notify_circuit_breaker"] is True
        assert data["email"]["rate_limit_remaining"] == 10

        # Check browser settings
        assert "browser" in data
        assert data["browser"]["enabled"] is True

        # Check sound settings
        assert "sound" in data
        assert data["sound"]["enabled"] is True
        assert data["sound"]["volume"] == 80

    def test_get_existing_settings(self, client, mock_user_id):
        """Test getting existing user settings."""
        # Pre-populate settings
        _user_email_settings[str(mock_user_id)] = EmailNotificationSettings(
            email_enabled=True,
            email_address="trader@example.com",
            notify_all_signals=True,
        )

        response = client.get("/api/v1/settings/notifications")

        assert response.status_code == 200
        data = response.json()

        assert data["email"]["enabled"] is True
        assert data["email"]["address"] == "trader@example.com"
        assert data["email"]["notify_all_signals"] is True

    def test_rate_limit_remaining_decreases(self, client, mock_user_id):
        """Test that rate limit remaining decreases after sends."""
        rate_limiter = get_email_rate_limiter()

        # Simulate some sends
        rate_limiter.record_send(mock_user_id)
        rate_limiter.record_send(mock_user_id)
        rate_limiter.record_send(mock_user_id)

        response = client.get("/api/v1/settings/notifications")

        assert response.status_code == 200
        data = response.json()
        assert data["email"]["rate_limit_remaining"] == 7


# ============================================================================
# PUT /api/v1/settings/notifications/email Tests
# ============================================================================


class TestUpdateEmailNotificationSettings:
    """Tests for PUT /api/v1/settings/notifications/email."""

    def test_enable_email_notifications(self, client, mock_user_id):
        """Test enabling email notifications."""
        response = client.put(
            "/api/v1/settings/notifications/email",
            json={
                "enabled": True,
                "address": "trader@example.com",
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert data["email"]["enabled"] is True
        assert data["email"]["address"] == "trader@example.com"

        # Verify persisted
        stored = _user_email_settings.get(str(mock_user_id))
        assert stored is not None
        assert stored.email_enabled is True
        assert stored.email_address == "trader@example.com"

    def test_disable_email_notifications(self, client, mock_user_id):
        """Test disabling email notifications."""
        # Pre-populate with enabled settings
        _user_email_settings[str(mock_user_id)] = EmailNotificationSettings(
            email_enabled=True,
            email_address="trader@example.com",
        )

        response = client.put(
            "/api/v1/settings/notifications/email",
            json={"enabled": False},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["email"]["enabled"] is False
        # Address should be preserved
        assert data["email"]["address"] == "trader@example.com"

    def test_update_notify_all_signals(self, client, mock_user_id):
        """Test updating notify_all_signals setting."""
        _user_email_settings[str(mock_user_id)] = EmailNotificationSettings(
            email_enabled=True,
            email_address="trader@example.com",
            notify_all_signals=False,
        )

        response = client.put(
            "/api/v1/settings/notifications/email",
            json={"notify_all_signals": True},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["email"]["notify_all_signals"] is True

    def test_partial_update(self, client, mock_user_id):
        """Test partial update preserves other settings."""
        _user_email_settings[str(mock_user_id)] = EmailNotificationSettings(
            email_enabled=True,
            email_address="original@example.com",
            notify_all_signals=False,
            notify_auto_executions=True,
            notify_circuit_breaker=True,
        )

        # Only update email address
        response = client.put(
            "/api/v1/settings/notifications/email",
            json={"address": "new@example.com"},
        )

        assert response.status_code == 200
        data = response.json()

        # Updated field
        assert data["email"]["address"] == "new@example.com"

        # Preserved fields
        assert data["email"]["enabled"] is True
        assert data["email"]["notify_all_signals"] is False
        assert data["email"]["notify_auto_executions"] is True
        assert data["email"]["notify_circuit_breaker"] is True

    def test_update_all_settings(self, client, mock_user_id):
        """Test updating all settings at once."""
        response = client.put(
            "/api/v1/settings/notifications/email",
            json={
                "enabled": True,
                "address": "trader@example.com",
                "notify_all_signals": True,
                "notify_auto_executions": False,
                "notify_circuit_breaker": False,
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert data["email"]["enabled"] is True
        assert data["email"]["address"] == "trader@example.com"
        assert data["email"]["notify_all_signals"] is True
        assert data["email"]["notify_auto_executions"] is False
        assert data["email"]["notify_circuit_breaker"] is False

    def test_invalid_email_format(self, client):
        """Test validation of email address format."""
        response = client.put(
            "/api/v1/settings/notifications/email",
            json={
                "enabled": True,
                "address": "not-a-valid-email",
            },
        )

        # Should fail validation
        assert response.status_code == 422

    def test_rate_limit_in_response(self, client, mock_user_id):
        """Test that rate limit remaining is included in response."""
        rate_limiter = get_email_rate_limiter()
        rate_limiter.record_send(mock_user_id)
        rate_limiter.record_send(mock_user_id)

        response = client.put(
            "/api/v1/settings/notifications/email",
            json={"enabled": True},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["email"]["rate_limit_remaining"] == 8


# ============================================================================
# Integration Tests
# ============================================================================


class TestNotificationSettingsIntegration:
    """Integration tests for notification settings flow."""

    def test_full_settings_flow(self, client):
        """Test complete settings workflow: get -> update -> get."""
        # 1. Get initial (default) settings
        response = client.get("/api/v1/settings/notifications")
        assert response.status_code == 200
        assert response.json()["email"]["enabled"] is False

        # 2. Enable email notifications
        response = client.put(
            "/api/v1/settings/notifications/email",
            json={
                "enabled": True,
                "address": "trader@example.com",
                "notify_all_signals": False,
            },
        )
        assert response.status_code == 200

        # 3. Verify settings are persisted
        response = client.get("/api/v1/settings/notifications")
        assert response.status_code == 200
        data = response.json()
        assert data["email"]["enabled"] is True
        assert data["email"]["address"] == "trader@example.com"
        assert data["email"]["notify_all_signals"] is False

        # 4. Update to enable all signals
        response = client.put(
            "/api/v1/settings/notifications/email",
            json={"notify_all_signals": True},
        )
        assert response.status_code == 200

        # 5. Verify update
        response = client.get("/api/v1/settings/notifications")
        assert response.status_code == 200
        data = response.json()
        assert data["email"]["notify_all_signals"] is True
        # Other settings preserved
        assert data["email"]["enabled"] is True
        assert data["email"]["address"] == "trader@example.com"
