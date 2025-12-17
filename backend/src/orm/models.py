"""
SQLAlchemy ORM Models for BMAD Wyckoff System.

These models map to database tables for the Wyckoff trading system.
They enable type-safe querying through SQLAlchemy ORM.

Note: OHLCVBar (OHLCVBarModel) exists in src/repositories/models.py.

Models:
-------
- TradingRange: Wyckoff trading ranges (accumulation/distribution)
- User: User accounts
- UserSettingsDB: User settings
- APIKeyDB: API keys for authentication
- Pattern: Detected Wyckoff patterns
- Signal: Generated trade signals
- NotificationORM: User notifications
- NotificationPreferencesORM: User notification preferences
- PushSubscriptionORM: Browser push subscriptions
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import JSON, Boolean, CheckConstraint, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import NUMERIC, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


class TradingRange(Base):
    """
    Trading range model for Wyckoff accumulation/distribution ranges.

    Table: trading_ranges
    Primary Key: id (UUID)
    """

    __tablename__ = "trading_ranges"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Symbol and timeframe
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(5), nullable=False)

    # Time range
    start_time: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    end_time: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    duration_bars: Mapped[int] = mapped_column(Integer, nullable=False)

    # Price levels
    creek_level: Mapped[Decimal] = mapped_column(NUMERIC(18, 8), nullable=False)
    ice_level: Mapped[Decimal] = mapped_column(NUMERIC(18, 8), nullable=False)
    jump_target: Mapped[Decimal] = mapped_column(NUMERIC(18, 8), nullable=False)

    # Range metrics
    cause_factor: Mapped[Decimal] = mapped_column(NUMERIC(4, 2), nullable=False)
    range_width: Mapped[Decimal] = mapped_column(NUMERIC(10, 4), nullable=False)
    phase: Mapped[str] = mapped_column(String(1), nullable=False)
    strength_score: Mapped[int] = mapped_column(Integer, nullable=False)

    # Touch counts
    touch_count_creek: Mapped[int] = mapped_column(Integer, server_default="0")
    touch_count_ice: Mapped[int] = mapped_column(Integer, server_default="0")

    # Soft delete
    deleted_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    # Optimistic locking
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint("duration_bars BETWEEN 15 AND 100", name="chk_duration_bars"),
        CheckConstraint("cause_factor BETWEEN 2.0 AND 3.0", name="chk_cause_factor"),
        CheckConstraint("phase IN ('A','B','C','D','E')", name="chk_phase"),
        CheckConstraint("strength_score BETWEEN 60 AND 100", name="chk_strength_score"),
    )


class User(Base):
    """
    User account model.

    Table: users
    Primary Key: id (UUID)
    """

    __tablename__ = "users"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # User credentials
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
    last_login_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)


class UserSettingsDB(Base):
    """
    User settings model.

    Table: user_settings
    Primary Key: user_id (UUID, FK to users.id)
    """

    __tablename__ = "user_settings"

    # Primary key and foreign key
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
    )

    # Settings JSON
    settings: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Timestamps
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )


class APIKeyDB(Base):
    """
    API Key model for user authentication.

    Table: api_keys
    Primary Key: id (UUID)
    Foreign Keys: user_id -> users.id
    """

    __tablename__ = "api_keys"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Foreign key
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)

    # API key details
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    scopes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    last_used_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)


class Pattern(Base):
    """
    Detected Wyckoff patterns.

    Table: patterns
    Primary Key: id (UUID)
    Foreign Keys: trading_range_id -> trading_ranges.id
    """

    __tablename__ = "patterns"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Pattern identification
    pattern_type: Mapped[str] = mapped_column(String(10), nullable=False)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(5), nullable=False)

    # Timestamps
    detection_time: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    pattern_bar_timestamp: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )

    # Pattern metrics
    confidence_score: Mapped[int] = mapped_column(Integer, nullable=False)
    phase: Mapped[str] = mapped_column(String(1), nullable=False)

    # Relationships
    trading_range_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)

    # Price levels
    entry_price: Mapped[Decimal] = mapped_column(NUMERIC(18, 8), nullable=False)
    stop_loss: Mapped[Decimal] = mapped_column(NUMERIC(18, 8), nullable=False)
    invalidation_level: Mapped[Decimal] = mapped_column(NUMERIC(18, 8), nullable=False)

    # Volume/spread analysis
    volume_ratio: Mapped[Decimal] = mapped_column(NUMERIC(10, 4), nullable=False)
    spread_ratio: Mapped[Decimal] = mapped_column(NUMERIC(10, 4), nullable=False)

    # Test confirmation
    test_confirmed: Mapped[bool] = mapped_column(Boolean, server_default="false")
    test_bar_timestamp: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    # Rejection
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Pattern metadata (use different name to avoid SQLAlchemy reserved 'metadata')
    # Use JSON type (compatible with both SQLite and PostgreSQL)
    pattern_metadata: Mapped[dict] = mapped_column("metadata", JSON, nullable=False)
    metadata_version: Mapped[int] = mapped_column(Integer, server_default="1")

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    __table_args__ = (
        CheckConstraint("confidence_score BETWEEN 70 AND 95", name="chk_confidence_score"),
        CheckConstraint("phase IN ('A','B','C','D','E')", name="chk_pattern_phase"),
    )


class Signal(Base):
    """
    Generated trade signals.

    Table: signals
    Primary Key: id (UUID)
    Foreign Keys: pattern_id -> patterns.id, campaign_id -> campaigns.id
    """

    __tablename__ = "signals"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Signal identification
    signal_type: Mapped[str] = mapped_column(String(10), nullable=False, server_default="LONG")
    pattern_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)

    # Symbol and timeframe
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(5), nullable=False)

    # Timestamps
    generated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    # Price levels
    entry_price: Mapped[Decimal] = mapped_column(NUMERIC(18, 8), nullable=False)
    stop_loss: Mapped[Decimal] = mapped_column(NUMERIC(18, 8), nullable=False)
    target_1: Mapped[Decimal] = mapped_column(NUMERIC(18, 8), nullable=False)
    target_2: Mapped[Decimal] = mapped_column(NUMERIC(18, 8), nullable=False)

    # Position sizing
    position_size: Mapped[Decimal] = mapped_column(NUMERIC(18, 8), nullable=False)
    risk_amount: Mapped[Decimal] = mapped_column(NUMERIC(12, 2), nullable=False)
    r_multiple: Mapped[Decimal] = mapped_column(NUMERIC(6, 2), nullable=False)

    # Confidence and status
    confidence_score: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="PENDING")

    # Campaign tracking
    campaign_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    campaign_allocation: Mapped[Decimal] = mapped_column(NUMERIC(5, 4), server_default="0")

    # Notification
    notification_sent: Mapped[bool] = mapped_column(Boolean, server_default="false")

    # Approval chain
    approval_chain: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    __table_args__ = (CheckConstraint("r_multiple >= 2.0", name="chk_r_multiple"),)


class NotificationORM(Base):
    """
    User notifications across all channels.

    Table: notifications
    Primary Key: id (UUID)
    Foreign Keys: user_id -> users.id
    Indexes: idx_notifications_user_read, idx_notifications_type
    """

    __tablename__ = "notifications"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Notification classification
    notification_type: Mapped[str] = mapped_column(String(20), nullable=False)
    priority: Mapped[str] = mapped_column(String(10), nullable=False)

    # Content
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(String(1000), nullable=False)
    notification_metadata: Mapped[dict] = mapped_column(
        "metadata", JSON, nullable=False, server_default="{}"
    )

    # User relationship
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)

    # Status
    read: Mapped[bool] = mapped_column(Boolean, server_default="false", nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "notification_type IN ('signal_generated', 'risk_warning', 'emergency_exit', 'system_error')",
            name="chk_notification_type",
        ),
        CheckConstraint(
            "priority IN ('info', 'warning', 'critical')",
            name="chk_notification_priority",
        ),
    )


class NotificationPreferencesORM(Base):
    """
    User notification preferences and configuration.

    Table: notification_preferences
    Primary Key: user_id (UUID) - One preference record per user
    """

    __tablename__ = "notification_preferences"

    # Primary key (also foreign key to users)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
    )

    # Preferences stored as JSONB for flexibility
    # Contains: email_enabled, sms_enabled, push_enabled, channels, quiet_hours, etc.
    preferences: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Timestamps
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )


class PushSubscriptionORM(Base):
    """
    Browser push notification subscriptions.

    Table: push_subscriptions
    Primary Key: id (UUID)
    Foreign Keys: user_id -> users.id
    Unique: (user_id, endpoint) - One subscription per browser/device
    """

    __tablename__ = "push_subscriptions"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # User relationship
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)

    # Web Push subscription data
    endpoint: Mapped[str] = mapped_column(Text, nullable=False)
    p256dh_key: Mapped[str] = mapped_column(Text, nullable=False)
    auth_key: Mapped[str] = mapped_column(Text, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    __table_args__ = (UniqueConstraint("user_id", "endpoint", name="uq_user_endpoint"),)


class HelpArticleORM(Base):
    """
    Help article with searchable content (Story 11.8a).

    Table: help_articles
    Primary Key: id (UUID)
    Unique: slug
    Indexes: idx_help_articles_search (GIN full-text search)
    """

    __tablename__ = "help_articles"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Article identification
    slug: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)

    # Content
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    content_html: Mapped[str] = mapped_column(Text, nullable=False)

    # Classification
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    tags: Mapped[list] = mapped_column(JSON, nullable=False, server_default="[]")
    keywords: Mapped[str] = mapped_column(Text, nullable=False, server_default="")

    # Engagement metrics
    view_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    helpful_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    not_helpful_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    # Timestamps
    last_updated: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "category IN ('GLOSSARY', 'FAQ', 'TUTORIAL', 'REFERENCE')",
            name="chk_help_article_category",
        ),
        CheckConstraint("view_count >= 0", name="chk_view_count"),
        CheckConstraint("helpful_count >= 0", name="chk_helpful_count"),
        CheckConstraint("not_helpful_count >= 0", name="chk_not_helpful_count"),
    )


class GlossaryTermORM(Base):
    """
    Wyckoff glossary term (Story 11.8a).

    Table: glossary_terms
    Primary Key: id (UUID)
    Unique: slug
    Indexes: idx_glossary_terms_slug, idx_glossary_terms_phase
    """

    __tablename__ = "glossary_terms"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Term identification
    term: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)

    # Definitions
    short_definition: Mapped[str] = mapped_column(String(500), nullable=False)
    full_description: Mapped[str] = mapped_column(Text, nullable=False)
    full_description_html: Mapped[str] = mapped_column(Text, nullable=False)

    # Wyckoff association
    wyckoff_phase: Mapped[str | None] = mapped_column(String(1), nullable=True, index=True)

    # Related terms and tags
    related_terms: Mapped[list] = mapped_column(JSON, nullable=False, server_default="[]")
    tags: Mapped[list] = mapped_column(JSON, nullable=False, server_default="[]")

    # Timestamps
    last_updated: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "wyckoff_phase IS NULL OR wyckoff_phase IN ('A', 'B', 'C', 'D', 'E')",
            name="chk_glossary_wyckoff_phase",
        ),
    )


class HelpFeedbackORM(Base):
    """
    User feedback on help articles (Story 11.8a).

    Table: help_feedback
    Primary Key: id (UUID)
    Foreign Keys: article_id -> help_articles.id
    """

    __tablename__ = "help_feedback"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Article relationship
    article_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)

    # Feedback
    helpful: Mapped[bool] = mapped_column(Boolean, nullable=False)
    user_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )


class TutorialORM(Base):
    """
    Interactive step-by-step tutorial (Story 11.8b).

    Table: tutorials
    Primary Key: id (UUID)
    Unique: slug
    Indexes: idx_tutorials_slug, idx_tutorials_difficulty
    """

    __tablename__ = "tutorials"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Tutorial identification
    slug: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Tutorial metadata
    difficulty: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    estimated_time_minutes: Mapped[int] = mapped_column(Integer, nullable=False)

    # Steps (stored as JSONB array of TutorialStep objects)
    steps: Mapped[list] = mapped_column(JSON, nullable=False)

    # Classification
    tags: Mapped[list] = mapped_column(JSON, nullable=False, server_default="[]")

    # Timestamps
    last_updated: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    # Analytics
    completion_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    __table_args__ = (
        CheckConstraint(
            "difficulty IN ('BEGINNER', 'INTERMEDIATE', 'ADVANCED')",
            name="chk_tutorial_difficulty",
        ),
        CheckConstraint(
            "estimated_time_minutes > 0 AND estimated_time_minutes <= 120",
            name="chk_estimated_time_range",
        ),
        CheckConstraint("completion_count >= 0", name="chk_completion_count"),
    )


class TutorialProgressORM(Base):
    """
    User progress tracking for tutorials (Story 11.8b - OPTIONAL).

    Table: tutorial_progress
    Primary Key: id (UUID)
    Foreign Keys: tutorial_id -> tutorials.id
    Unique: (user_id, tutorial_id)

    Note: This table is created but not used in MVP (Story 11.8b uses localStorage).
    It's available for future enhancement when user authentication is implemented.
    """

    __tablename__ = "tutorial_progress"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # User and tutorial relationship
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    tutorial_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)

    # Progress tracking
    current_step: Mapped[int] = mapped_column(Integer, nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    # Timestamp
    last_accessed: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    __table_args__ = (
        CheckConstraint("current_step > 0", name="chk_current_step_positive"),
        UniqueConstraint("user_id", "tutorial_id", name="uq_user_tutorial"),
    )
