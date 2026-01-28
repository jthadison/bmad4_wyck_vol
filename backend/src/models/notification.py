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


class SignalNotification(BaseModel):
    """
    WebSocket notification payload for approved signals (Story 19.7).

    Broadcast via WebSocket when a signal passes all validation stages.
    Contains all information needed for trader to act on the opportunity.

    Attributes:
        type: Message type identifier ("signal_approved")
        signal_id: Unique signal identifier
        timestamp: When signal was approved (UTC)
        symbol: Trading symbol (e.g., "AAPL", "EUR/USD")
        pattern_type: Wyckoff pattern (SPRING, SOS, LPS, UTAD)
        confidence_score: Overall confidence (70-95)
        confidence_grade: Letter grade (A+, A, B, C)
        entry_price: Recommended entry price
        stop_loss: Stop loss level
        target_price: Primary target (Jump level)
        risk_amount: Dollar amount at risk
        risk_percentage: Risk as percentage of account
        r_multiple: Reward/risk ratio
        expires_at: Signal expiration for manual approval

    Example JSON:
        {
          "type": "signal_approved",
          "signal_id": "550e8400-e29b-41d4-a716-446655440000",
          "timestamp": "2026-01-23T10:30:00Z",
          "symbol": "AAPL",
          "pattern_type": "SPRING",
          "confidence_score": 92,
          "confidence_grade": "A+",
          "entry_price": "150.25",
          "stop_loss": "149.50",
          "target_price": "152.75",
          "risk_amount": "75.00",
          "risk_percentage": 1.5,
          "r_multiple": 3.33,
          "expires_at": "2026-01-23T10:35:00Z"
        }
    """

    type: Literal["signal_approved"] = "signal_approved"
    signal_id: UUID = Field(..., description="Unique signal identifier")
    timestamp: datetime = Field(..., description="When signal was approved (UTC)")
    symbol: str = Field(..., max_length=20, description="Trading symbol")
    pattern_type: str = Field(..., description="Wyckoff pattern type")
    confidence_score: int = Field(
        ..., ge=70, le=100, description="Overall confidence score (70-100)"
    )
    confidence_grade: str = Field(..., description="Letter grade (A+, A, B, C)")
    entry_price: str = Field(..., description="Entry price as decimal string")
    stop_loss: str = Field(..., description="Stop loss price as decimal string")
    target_price: str = Field(..., description="Primary target price as decimal string")
    risk_amount: str = Field(..., description="Dollar risk amount as decimal string")
    risk_percentage: float = Field(..., ge=0.0, le=100.0, description="Risk as percentage")
    r_multiple: float = Field(..., ge=0.0, description="Reward/risk ratio")
    expires_at: datetime = Field(..., description="Signal expiration timestamp (UTC)")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat(), UUID: lambda v: str(v)}

    @classmethod
    def confidence_to_grade(cls, score: int) -> str:
        """
        Convert confidence score to letter grade.

        Grade Scale:
        - A+: 90-100
        - A:  85-89
        - B:  80-84
        - C:  70-79

        Args:
            score: Confidence score (70-100)

        Returns:
            Letter grade string

        Raises:
            ValueError: If score is below minimum threshold of 70
        """
        if score < 70:
            raise ValueError(f"Confidence score {score} below minimum threshold of 70")
        if score >= 90:
            return "A+"
        elif score >= 85:
            return "A"
        elif score >= 80:
            return "B"
        else:
            return "C"


# ============================================================================
# Email Notification Models (Story 19.25)
# ============================================================================


class EmailNotificationSettings(BaseModel):
    """
    User email notification preferences (Story 19.25).

    Controls email notification behavior including:
    - Whether emails are enabled
    - Email address override (if different from account)
    - Confidence filtering (all signals vs high-confidence only)
    - Notification types (auto-executions, circuit breaker, etc.)
    """

    email_enabled: bool = Field(
        default=False,
        description="Whether email notifications are enabled",
    )
    email_address: Optional[EmailStr] = Field(
        default=None,
        description="Override email address (if different from account email)",
    )
    notify_all_signals: bool = Field(
        default=False,
        description="If False, only high confidence (A+, A) signals trigger emails",
    )
    notify_auto_executions: bool = Field(
        default=True,
        description="Send email when auto-execution completes",
    )
    notify_circuit_breaker: bool = Field(
        default=True,
        description="Send email when circuit breaker activates",
    )

    class Config:
        json_encoders = {UUID: lambda v: str(v)}


class EmailNotificationSettingsUpdate(BaseModel):
    """
    Request model for updating email notification settings.

    All fields are optional to allow partial updates.
    """

    enabled: Optional[bool] = Field(
        default=None,
        description="Enable/disable email notifications",
    )
    address: Optional[EmailStr] = Field(
        default=None,
        description="Email address for notifications",
    )
    notify_all_signals: Optional[bool] = Field(
        default=None,
        description="Notify for all signals (True) or high-confidence only (False)",
    )
    notify_auto_executions: Optional[bool] = Field(
        default=None,
        description="Notify on auto-execution completion",
    )
    notify_circuit_breaker: Optional[bool] = Field(
        default=None,
        description="Notify on circuit breaker activation",
    )


class EmailSettingsResponse(BaseModel):
    """Email notification settings in notification settings response."""

    enabled: bool = False
    address: Optional[str] = None
    notify_all_signals: bool = False
    notify_auto_executions: bool = True
    notify_circuit_breaker: bool = True
    rate_limit_remaining: int = Field(
        default=10,
        description="Emails remaining in current hour",
    )


class BrowserSettingsResponse(BaseModel):
    """Browser notification settings in notification settings response."""

    enabled: bool = True


class SoundSettingsResponse(BaseModel):
    """Sound notification settings in notification settings response."""

    enabled: bool = True
    volume: int = Field(default=80, ge=0, le=100)


class NotificationSettingsResponse(BaseModel):
    """
    Complete notification settings response (Story 19.25).

    Returns all notification channel settings in a single response.
    """

    email: EmailSettingsResponse = Field(default_factory=EmailSettingsResponse)
    browser: BrowserSettingsResponse = Field(default_factory=BrowserSettingsResponse)
    sound: SoundSettingsResponse = Field(default_factory=SoundSettingsResponse)


class SignalEmailData(BaseModel):
    """
    Data structure for signal email content (Story 19.25).

    Contains all information needed to render a signal alert email.
    """

    signal_id: UUID
    symbol: str
    pattern_type: str
    confidence_score: int
    confidence_grade: str
    entry_price: str
    stop_loss: str
    target_price: str
    risk_amount: str
    r_multiple: float
    approve_url: str
    unsubscribe_url: str

    class Config:
        json_encoders = {UUID: lambda v: str(v)}
