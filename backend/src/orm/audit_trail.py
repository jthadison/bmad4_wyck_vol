"""
SQLAlchemy ORM Model for Audit Trail (Task #2).

General-purpose audit trail table for tracking manual overrides,
configuration changes, and compliance-relevant actions.

Table: audit_trail
Primary Key: id (UUID)
Indexes: entity (type+id), created_at, event_type, event_type+created_at
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, String, Text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


class AuditTrailORM(Base):
    """
    Audit trail entry for compliance and operational tracking.

    Table: audit_trail
    Primary Key: id (UUID)

    Tracks manual overrides (e.g., correlation limit bypasses),
    configuration changes, and other compliance-relevant actions.
    """

    __tablename__ = "audit_trail"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Event classification
    event_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    # Entity being acted on
    entity_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    entity_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    # Who performed the action
    actor: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # Human-readable description
    action: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Correlation ID for cross-system tracing
    correlation_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    # Additional context (JSONB in production, JSON for SQLite test compatibility)
    audit_metadata: Mapped[dict] = mapped_column(
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
