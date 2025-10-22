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
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

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
