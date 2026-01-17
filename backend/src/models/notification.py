"""
Notification data models for multi-channel alert system.

This module defines Pydantic models for notifications, preferences, and related data structures
used across toast, email, SMS, and push notification channels.
"""

from datetime import datetime, time
from enum import Enum
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


class NotificationType(str, Enum):
    """Types of notifications supported by the system."""

    SIGNAL_GENERATED = "signal_generated"
    RISK_WARNING = "risk_warning"
    EMERGENCY_EXIT = "emergency_exit"
    SYSTEM_ERROR = "system_error"


class NotificationPriority(str, Enum):
    """Priority levels determining channel routing.

    - INFO: Toast only (non-intrusive)
    - WARNING: Toast + Email (moderate urgency)
    - CRITICAL: All channels (highest urgency, overrides quiet hours)
    """

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class NotificationChannel(str, Enum):
    """Available notification delivery channels."""

    TOAST = "toast"  # In-app WebSocket notification
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"  # Browser push notification


class Notification(BaseModel):
    """Individual notification record persisted to database."""

    id: UUID
    notification_type: NotificationType
    priority: NotificationPriority
    title: str = Field(..., max_length=200)
    message: str = Field(..., max_length=1000)
    metadata: dict[str, Any] = Field(default_factory=dict)  # Type-specific data
    user_id: UUID
    read: bool = False
    created_at: datetime

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat(), UUID: lambda v: str(v)}


class QuietHours(BaseModel):
    """Quiet hours configuration for do-not-disturb periods.

    Applies to INFO and WARNING priority notifications only.
    CRITICAL notifications always override quiet hours.
    """

    enabled: bool = False
    start_time: time = time(22, 0)  # Default: 10:00 PM
    end_time: time = time(8, 0)  # Default: 8:00 AM
    timezone: str = "America/New_York"  # User's timezone

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        """Validate timezone is a valid IANA timezone string."""
        import pytz

        try:
            pytz.timezone(v)
        except pytz.UnknownTimeZoneError as e:
            raise ValueError(f"Invalid timezone: {v}") from e
        return v


class ChannelPreferences(BaseModel):
    """Channel configuration per priority level.

    Allows users to customize which channels receive notifications
    for each priority level.
    """

    info_channels: list[NotificationChannel] = [NotificationChannel.TOAST]
    warning_channels: list[NotificationChannel] = [
        NotificationChannel.TOAST,
        NotificationChannel.EMAIL,
    ]
    critical_channels: list[NotificationChannel] = [
        NotificationChannel.TOAST,
        NotificationChannel.EMAIL,
        NotificationChannel.SMS,
        NotificationChannel.PUSH,
    ]


class NotificationPreferences(BaseModel):
    """User notification preferences and configuration."""

    user_id: UUID
    email_enabled: bool = True
    email_address: Optional[EmailStr] = None
    sms_enabled: bool = False
    sms_phone_number: Optional[str] = None  # E.164 format: +1234567890
    push_enabled: bool = False
    min_confidence_threshold: int = Field(default=85, ge=70, le=95)
    quiet_hours: QuietHours = Field(default_factory=QuietHours)
    channel_preferences: ChannelPreferences = Field(default_factory=ChannelPreferences)
    updated_at: datetime

    @field_validator("sms_phone_number")
    @classmethod
    def validate_phone_number(cls, v: Optional[str]) -> Optional[str]:
        """Validate phone number is in E.164 format."""
        if v is None:
            return v

        # E.164 format: +[country code][number] (e.g., +12345678901)
        import re

        if not re.match(r"^\+[1-9]\d{1,14}$", v):
            raise ValueError("Phone number must be in E.164 format (e.g., +12345678901)")
        return v

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            time: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
        }


class NotificationToast(BaseModel):
    """WebSocket message for real-time toast notifications."""

    type: Literal["notification_toast"] = "notification_toast"
    sequence_number: int
    notification: Notification
    timestamp: datetime

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat(), UUID: lambda v: str(v)}


class PushSubscription(BaseModel):
    """Browser push notification subscription info.

    Stores Web Push subscription data for sending push notifications
    via the Web Push protocol.
    """

    user_id: UUID
    endpoint: str
    p256dh_key: str  # Public key for encryption
    auth_key: str  # Authentication secret
    created_at: datetime

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat(), UUID: lambda v: str(v)}


class TestNotificationRequest(BaseModel):
    """Request to send test notification for channel verification."""

    channel: NotificationChannel


class NotificationResponse(BaseModel):
    """Standard response for notification operations."""

    success: bool
    message: Optional[str] = None
    notification_id: Optional[UUID] = None

    class Config:
        json_encoders = {UUID: lambda v: str(v)}


class NotificationListResponse(BaseModel):
    """Paginated list of notifications with metadata."""

    data: list[Notification]
    pagination: dict[str, Any]

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat(), UUID: lambda v: str(v)}
