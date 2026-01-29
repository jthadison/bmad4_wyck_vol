"""
Shared fixtures for notification client tests.

Provides common test fixtures used across email, SMS, and push notification tests.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from src.models.notification import (
    Notification,
    NotificationPriority,
    NotificationType,
    PushSubscription,
)


# =============================================================================
# CircuitBreaker Constants (from twilio_client.py defaults)
# =============================================================================

DEFAULT_CIRCUIT_BREAKER_FAILURE_THRESHOLD = 5
DEFAULT_CIRCUIT_BREAKER_TIMEOUT_SECONDS = 60
DEFAULT_RATE_LIMITER_MAX_PER_HOUR = 30


# =============================================================================
# Shared Notification Fixtures
# =============================================================================


@pytest.fixture
def sample_user_id():
    """Generate a sample user ID."""
    return uuid4()


@pytest.fixture
def sample_notification(sample_user_id):
    """
    Create a sample notification for testing.

    Returns a SIGNAL_GENERATED notification with WARNING priority.
    """
    return Notification(
        id=uuid4(),
        notification_type=NotificationType.SIGNAL_GENERATED,
        priority=NotificationPriority.WARNING,
        title="New Trading Signal",
        message="AAPL Spring pattern detected with 87% confidence",
        metadata={"symbol": "AAPL", "pattern": "Spring", "confidence": 87},
        user_id=sample_user_id,
        read=False,
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def sample_critical_notification(sample_user_id):
    """
    Create a sample critical notification for testing.

    Returns an EMERGENCY_EXIT notification with CRITICAL priority.
    """
    return Notification(
        id=uuid4(),
        notification_type=NotificationType.EMERGENCY_EXIT,
        priority=NotificationPriority.CRITICAL,
        title="Emergency Exit Triggered",
        message="AAPL position closed at stop loss",
        metadata={"symbol": "AAPL", "exit_price": 149.50, "loss": -150.00},
        user_id=sample_user_id,
        read=False,
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def sample_risk_notification(sample_user_id):
    """
    Create a sample risk warning notification for testing.

    Returns a RISK_WARNING notification with WARNING priority.
    """
    return Notification(
        id=uuid4(),
        notification_type=NotificationType.RISK_WARNING,
        priority=NotificationPriority.WARNING,
        title="Portfolio Risk Alert",
        message="Portfolio heat exceeds 8%",
        metadata={"portfolio_heat": 8.5, "max_heat": 10.0},
        user_id=sample_user_id,
        read=False,
        created_at=datetime.now(UTC),
    )


# =============================================================================
# Push Subscription Fixtures
# =============================================================================


@pytest.fixture
def sample_push_subscription(sample_user_id):
    """
    Create a sample push subscription for testing.

    Returns a valid PushSubscription with FCM endpoint.
    """
    return PushSubscription(
        user_id=sample_user_id,
        endpoint="https://fcm.googleapis.com/fcm/send/abc123xyz",
        p256dh_key="BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4YfYCA_0QTpQtUbVlUls0VJXg7A8u-Ts1XbjhazAkj7I99e8QcYP7DkM",
        auth_key="tBHItJI5svbpez7KI4CCXg",
        created_at=datetime.now(UTC),
    )
