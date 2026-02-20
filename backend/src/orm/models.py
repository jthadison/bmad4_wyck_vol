"""
SQLAlchemy ORM Models for BMAD Wyckoff System.

These models map to database tables for the Wyckoff trading system.
They enable type-safe querying through SQLAlchemy ORM.

Note: OHLCVBar (OHLCVBarModel) exists in src/repositories/models.py.

Models:
-------
- SectorMappingORM: Symbol-to-sector GICS classification
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
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY
from sqlalchemy.dialects.postgresql import NUMERIC, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


class StringListType(TypeDecorator):
    """
    Custom type for string lists that works with both PostgreSQL and SQLite.

    - PostgreSQL: Uses native ARRAY type
    - SQLite: Uses JSON type

    This enables test compatibility while maintaining PostgreSQL's native array support.
    """

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        """Load dialect-specific implementation."""
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_ARRAY(String))
        else:
            return dialect.type_descriptor(JSON)

    def process_bind_param(self, value, dialect):
        """Convert Python list to database representation."""
        if value is None:
            return value
        if dialect.name == "postgresql":
            return value  # PostgreSQL handles lists natively
        else:
            return value  # JSON dialect handles lists

    def process_result_value(self, value, dialect):
        """Convert database representation to Python list."""
        if value is None:
            return value
        return value  # Both dialects return lists directly


class SectorMappingORM(Base):
    """
    Sector mapping for symbol-to-sector classification (Story 11.9 Task 3).

    Maps stock symbols to GICS sectors for sector breakdown analytics.
    Also tracks relative strength scores for sector leader identification.

    Table: sector_mapping
    Primary Key: symbol (String)
    Indexes: idx_sector_mapping_sector (sector_name)

    See Also:
        Alembic migration 015_create_sector_mapping.py
    """

    __tablename__ = "sector_mapping"

    # Primary key - stock ticker symbol
    symbol: Mapped[str] = mapped_column(
        String(10),
        primary_key=True,
    )

    # GICS sector classification
    sector_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    # GICS industry group
    industry: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    # Relative strength score vs SPY (Task 7)
    rs_score: Mapped[Decimal | None] = mapped_column(
        NUMERIC(10, 4),
        nullable=True,
    )

    # Top 20% RS within sector
    is_sector_leader: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
    )

    # When RS was last calculated
    last_updated: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )


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

    # Rejection (Story 13.3.2 - Rejected Pattern Intelligence Tracking)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    rejected_by_session_filter: Mapped[bool] = mapped_column(
        Boolean, server_default="false", nullable=False
    )
    rejection_timestamp: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    is_tradeable: Mapped[bool] = mapped_column(Boolean, server_default="true", nullable=False)
    session: Mapped[str | None] = mapped_column(String(20), nullable=True)

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
    pattern_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    phase: Mapped[str | None] = mapped_column(String(1), nullable=True)
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

    # Audit trail fields (Story 19.11)
    lifecycle_state: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="generated"
    )
    validation_results: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    trade_outcome: Mapped[dict | None] = mapped_column(JSON, nullable=True)

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


class RegressionTestResultORM(Base):
    """
    Regression test results storage (Story 12.7 Task 4).

    Table: regression_test_results
    Primary Key: id (UUID)
    Unique: test_id
    JSONB Fields: config, aggregate_metrics, per_symbol_results, baseline_comparison
    """

    __tablename__ = "regression_test_results"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Test identification
    test_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        unique=True,
        nullable=False,
        index=True,
    )

    # Codebase version (git commit hash)
    codebase_version: Mapped[str] = mapped_column(String(50), nullable=False)

    # JSONB fields for complex nested objects
    config: Mapped[dict] = mapped_column(JSON, nullable=False)
    aggregate_metrics: Mapped[dict] = mapped_column(JSON, nullable=False)
    per_symbol_results: Mapped[dict] = mapped_column(JSON, nullable=False)
    baseline_comparison: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Regression detection results
    regression_detected: Mapped[bool] = mapped_column(Boolean, nullable=False)
    degraded_metrics: Mapped[list] = mapped_column(JSON, nullable=False)

    # Test status: PASS, FAIL, BASELINE_NOT_SET
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    # Execution metadata
    execution_time_seconds: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        server_default="0",
    )
    test_run_time: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('PASS', 'FAIL', 'BASELINE_NOT_SET')",
            name="chk_regression_test_status",
        ),
        CheckConstraint(
            "execution_time_seconds >= 0",
            name="chk_execution_time_positive",
        ),
    )


class RegressionBaselineORM(Base):
    """
    Regression baselines storage (Story 12.7 Task 5).

    Table: regression_baselines
    Primary Key: id (UUID)
    Unique: baseline_id, is_current (partial - only one can be TRUE)
    JSONB Fields: metrics, per_symbol_metrics
    """

    __tablename__ = "regression_baselines"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Baseline identification
    baseline_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        unique=True,
        nullable=False,
        index=True,
    )

    # Test reference
    test_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    # Codebase version (git commit hash)
    version: Mapped[str] = mapped_column(String(50), nullable=False)

    # JSONB fields for metrics
    metrics: Mapped[dict] = mapped_column(JSON, nullable=False)
    per_symbol_metrics: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Baseline status
    is_current: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
    )

    # Timestamps
    established_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )


class SignalApprovalQueueORM(Base):
    """
    Signal Approval Queue for manual trading approval workflow (Story 19.9).

    Table: signal_approval_queue
    Primary Key: id (UUID)
    Foreign Keys: signal_id -> signals.id (conceptual), user_id -> users.id
    Indexes: idx_signal_queue_user_status, idx_signal_queue_expires
    """

    __tablename__ = "signal_approval_queue"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Signal reference (conceptual FK - signals may be in-memory)
    signal_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    # User who owns this queue entry
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    # Queue status: pending, approved, rejected, expired
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="pending",
        index=True,
    )

    # Timestamps
    submitted_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    expires_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
    )

    approved_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )

    # Who approved (could be different from owner in future multi-user scenarios)
    approved_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
    )

    # Rejection reason
    rejection_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Signal snapshot (store signal data at submission time)
    # Note: Uses JSON in ORM for SQLite test compatibility.
    # Migration specifies JSONB for PostgreSQL production.
    signal_snapshot: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        server_default="{}",
    )

    # Standard timestamps
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'expired')",
            name="chk_signal_queue_status",
        ),
    )


class SignalAuditLogORM(Base):
    """
    Signal audit trail entries (Story 19.11).

    Tracks all state transitions for signals throughout their lifecycle.
    Each entry records a single state change with timestamp, user (if applicable),
    reason, and metadata.

    Table: signal_audit_log
    Primary Key: id (UUID)
    Foreign Keys: signal_id -> signals.id, user_id -> users.id
    Indexes: idx_signal_audit_signal (signal_id, created_at), idx_signal_audit_time (created_at)
    """

    __tablename__ = "signal_audit_log"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Signal reference
    signal_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("signals.id", ondelete="CASCADE"),
        nullable=False,
    )

    # User who triggered transition (nullable for system events)
    user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # State transition
    previous_state: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,  # Null for initial "generated" state
    )

    new_state: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    # Transition details
    transition_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Additional context (JSONB in production, JSON for SQLite test compatibility)
    # Note: Using "transition_metadata" to avoid conflict with SQLAlchemy's reserved "metadata"
    transition_metadata: Mapped[dict] = mapped_column(
        "metadata",  # Actual column name in database
        JSON,
        nullable=False,
        server_default="{}",
    )

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )


class AutoExecutionConfigORM(Base):
    """
    Auto-execution configuration model.

    Stores user preferences for automatic signal execution without manual approval.
    Includes safety features like kill switch and circuit breaker.

    Table: auto_execution_config
    Primary Key: user_id (UUID, FK to users.id)

    Story 19.14: Auto-Execution Configuration Backend
    """

    __tablename__ = "auto_execution_config"

    # Primary key and foreign key
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE", name="fk_auto_execution_config_user"),
        primary_key=True,
    )

    # Auto-execution control
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
    )

    # Configuration parameters
    min_confidence: Mapped[Decimal] = mapped_column(
        NUMERIC(5, 2),
        nullable=False,
        server_default="85.00",
    )

    max_trades_per_day: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="10",
    )

    max_risk_per_day: Mapped[Decimal | None] = mapped_column(
        NUMERIC(5, 2),
        nullable=True,
    )

    circuit_breaker_losses: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="3",
    )

    # Pattern and symbol filters
    enabled_patterns: Mapped[list[str]] = mapped_column(
        StringListType,
        nullable=False,
        # Note: server_default is in migration, omitted here for SQLite test compatibility
    )

    symbol_whitelist: Mapped[list[str] | None] = mapped_column(
        StringListType,
        nullable=True,
    )

    symbol_blacklist: Mapped[list[str] | None] = mapped_column(
        StringListType,
        nullable=True,
    )

    # Safety controls
    kill_switch_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
    )

    # Consent tracking
    consent_given_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )

    consent_ip_address: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "min_confidence >= 60 AND min_confidence <= 100", name="chk_min_confidence_range"
        ),
        CheckConstraint(
            "max_trades_per_day >= 1 AND max_trades_per_day <= 50", name="chk_max_trades_range"
        ),
        CheckConstraint(
            "max_risk_per_day IS NULL OR (max_risk_per_day > 0 AND max_risk_per_day <= 10)",
            name="chk_max_risk_range",
        ),
        CheckConstraint(
            "circuit_breaker_losses >= 1 AND circuit_breaker_losses <= 10",
            name="chk_circuit_breaker_range",
        ),
    )


class UserWatchlistORM(Base):
    """
    User watchlist for symbol monitoring (Story 19.12).

    Table: user_watchlist
    Primary Key: (user_id, symbol) - composite key
    Foreign Keys: user_id -> users.id
    Indexes: idx_watchlist_user_enabled
    """

    __tablename__ = "user_watchlist"

    # Composite primary key
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )

    symbol: Mapped[str] = mapped_column(
        String(10),
        primary_key=True,
    )

    # Priority and filtering
    priority: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        server_default="medium",
    )

    min_confidence: Mapped[Decimal | None] = mapped_column(
        NUMERIC(5, 2),
        nullable=True,
    )

    # Status
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "priority IN ('low', 'medium', 'high')",
            name="chk_watchlist_priority",
        ),
        CheckConstraint(
            "min_confidence IS NULL OR (min_confidence >= 60 AND min_confidence <= 100)",
            name="chk_watchlist_min_confidence",
        ),
    )


class PriceAlertORM(Base):
    """
    User price alerts for Wyckoff-specific market notifications.

    Table: price_alerts
    Primary Key: id (UUID)
    Foreign Keys: user_id -> users.id
    Indexes: idx_price_alerts_user_active, idx_price_alerts_symbol
    """

    __tablename__ = "price_alerts"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    symbol: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )

    # Alert classification
    alert_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    # Price level (NULL for phase_change alerts)
    # Use NUMERIC for financial precision (avoids floating-point rounding)
    price_level: Mapped[Decimal | None] = mapped_column(
        NUMERIC(18, 8),
        nullable=True,
    )

    # Direction for price_level alerts: 'above' | 'below'
    direction: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
    )

    # Wyckoff structural level type (optional context)
    wyckoff_level_type: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
    )

    # Optional trader notes
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    triggered_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "alert_type IN ('price_level', 'creek', 'ice', 'spring', 'phase_change')",
            name="chk_price_alert_type",
        ),
        CheckConstraint(
            "direction IS NULL OR direction IN ('above', 'below')",
            name="chk_price_alert_direction",
        ),
    )
