"""
SQLAlchemy ORM Models for BMAD Wyckoff System (Story 10.3.1).

These models map to database tables for pattern and signal data.
They enable type-safe querying through SQLAlchemy ORM for daily summary queries.

Note: OHLCVBar model exists in src/repositories/models.py (created in earlier stories).
This file contains only the models needed for Story 10.3.1 pattern/signal queries.

Models:
-------
- Pattern: Detected Wyckoff patterns
- Signal: Generated trade signals
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import JSON, Boolean, CheckConstraint, Integer, String, Text
from sqlalchemy.dialects.postgresql import NUMERIC, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


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
