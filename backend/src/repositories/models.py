"""
SQLAlchemy ORM models for database tables.

This module defines the database schema using SQLAlchemy ORM.
"""

from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import (
    DECIMAL,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


class OHLCVBarModel(Base):
    """
    OHLCV Bar database model.

    This table is configured as a TimescaleDB hypertable partitioned by timestamp.
    See Story 1.2 for hypertable creation SQL.
    """

    __tablename__ = "ohlcv_bars"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Symbol and timeframe
    symbol: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )
    timeframe: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )

    # Timestamp (UTC)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    # OHLC prices (NUMERIC for precision)
    open: Mapped[Decimal] = mapped_column(
        DECIMAL(18, 8),
        nullable=False,
    )
    high: Mapped[Decimal] = mapped_column(
        DECIMAL(18, 8),
        nullable=False,
    )
    low: Mapped[Decimal] = mapped_column(
        DECIMAL(18, 8),
        nullable=False,
    )
    close: Mapped[Decimal] = mapped_column(
        DECIMAL(18, 8),
        nullable=False,
    )

    # Volume
    volume: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    # Calculated fields
    spread: Mapped[Decimal] = mapped_column(
        DECIMAL(18, 8),
        nullable=False,
    )
    spread_ratio: Mapped[Decimal] = mapped_column(
        DECIMAL(10, 4),
        nullable=False,
        default=Decimal("1.0"),
    )
    volume_ratio: Mapped[Decimal] = mapped_column(
        DECIMAL(10, 4),
        nullable=False,
        default=Decimal("1.0"),
    )

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )

    # Constraints
    __table_args__ = (
        # Unique constraint for idempotent ingestion
        UniqueConstraint(
            "symbol",
            "timeframe",
            "timestamp",
            name="uq_ohlcv_symbol_timeframe_timestamp",
        ),
        # Composite index for queries
        Index(
            "ix_ohlcv_symbol_timeframe_timestamp",
            "symbol",
            "timeframe",
            "timestamp",
        ),
        # Check constraint for volume
        CheckConstraint("volume >= 0", name="ck_ohlcv_volume_non_negative"),
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<OHLCVBar(symbol={self.symbol}, timeframe={self.timeframe}, "
            f"timestamp={self.timestamp}, close={self.close})>"
        )


class CampaignModel(Base):
    """
    Campaign database model (Story 9.4).

    Represents a trading campaign (Spring → SOS → LPS entry sequence)
    within a single trading range with BMAD allocation and 5% risk limit.
    """

    __tablename__ = "campaigns"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Identification
    symbol: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )
    trading_range_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,  # Optional link to trading range
    )

    # Risk tracking
    current_risk: Mapped[Decimal] = mapped_column(
        DECIMAL(6, 4),  # Max 5.0000%
        nullable=False,
        default=Decimal("0.0"),
    )
    total_allocation: Mapped[Decimal] = mapped_column(
        DECIMAL(6, 4),
        nullable=False,
        default=Decimal("0.0"),
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="ACTIVE",
        index=True,
    )

    # Optimistic locking
    version: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=1,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    # Relationship to positions
    positions: Mapped[list["PositionModel"]] = relationship(
        "PositionModel",
        back_populates="campaign",
        lazy="raise",  # Require explicit loading via selectinload() in queries
    )

    # Constraints
    __table_args__ = (
        # Check constraint for risk limit
        CheckConstraint("current_risk <= 5.0", name="ck_campaign_risk_limit"),
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<Campaign(id={self.id}, symbol={self.symbol}, "
            f"current_risk={self.current_risk}, status={self.status})>"
        )


class PositionModel(Base):
    """
    Position database model (Story 9.4).

    Represents an individual trading position (Spring, SOS, or LPS entry)
    within a campaign with complete P&L tracking.
    """

    __tablename__ = "positions"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Foreign keys
    campaign_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("campaigns.id", ondelete="RESTRICT"),
        nullable=False,
    )
    signal_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,  # FK to signals table (to be created in future story)
    )

    # Identification
    symbol: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    timeframe: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )
    pattern_type: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )

    # Entry details
    entry_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    entry_price: Mapped[Decimal] = mapped_column(
        DECIMAL(18, 8),
        nullable=False,
    )
    shares: Mapped[Decimal] = mapped_column(
        DECIMAL(18, 8),
        nullable=False,
    )
    stop_loss: Mapped[Decimal] = mapped_column(
        DECIMAL(18, 8),
        nullable=False,
    )

    # Current state (OPEN positions)
    current_price: Mapped[Decimal] = mapped_column(
        DECIMAL(18, 8),
        nullable=True,
    )
    current_pnl: Mapped[Decimal] = mapped_column(
        DECIMAL(18, 8),
        nullable=True,
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="OPEN",
    )

    # Exit details (CLOSED positions)
    closed_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    exit_price: Mapped[Decimal] = mapped_column(
        DECIMAL(18, 8),
        nullable=True,
    )
    realized_pnl: Mapped[Decimal] = mapped_column(
        DECIMAL(18, 8),
        nullable=True,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    # Relationship to campaign
    campaign: Mapped["CampaignModel"] = relationship(
        "CampaignModel",
        back_populates="positions",
    )

    # Constraints
    __table_args__ = (
        # Composite index for campaign+status queries (covers both individual lookups)
        Index("ix_positions_campaign_status", "campaign_id", "status"),
        # Check constraints
        CheckConstraint("shares > 0", name="ck_position_shares_positive"),
        CheckConstraint("entry_price > 0", name="ck_position_entry_price_positive"),
        CheckConstraint("stop_loss > 0", name="ck_position_stop_loss_positive"),
        CheckConstraint(
            "status IN ('OPEN', 'CLOSED')",
            name="ck_position_status_valid",
        ),
        CheckConstraint(
            "pattern_type IN ('SPRING', 'SOS', 'LPS')",
            name="ck_position_pattern_type_valid",
        ),
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<Position(id={self.id}, symbol={self.symbol}, "
            f"pattern_type={self.pattern_type}, status={self.status})>"
        )
