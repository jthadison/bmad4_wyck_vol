"""
SQLAlchemy ORM Models for Scanner Persistence (Story 20.1).

Models for scanner state persistence including:
- ScannerWatchlistORM: Symbols to scan
- ScannerConfigORM: Scanner configuration (singleton)
- ScannerHistoryORM: Scan cycle history

These tables persist scanner state across service restarts.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, Boolean, CheckConstraint, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator


class PortableJSONB(TypeDecorator):
    """JSONB on PostgreSQL, JSON on other dialects (e.g. SQLite in tests)."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_JSONB())
        return dialect.type_descriptor(JSON())


from src.database import Base


class ScannerWatchlistORM(Base):
    """
    Scanner watchlist entry for persistent symbol tracking.

    Table: scanner_watchlist
    Primary Key: id (UUID)
    Unique: symbol

    Stores symbols that the scanner should process, along with
    their timeframe and asset class configuration.
    """

    __tablename__ = "scanner_watchlist"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Symbol identification
    symbol: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        unique=True,
    )

    # Timeframe: 1M, 5M, 15M, 30M, 1H, 4H, 1D, 1W
    timeframe: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )

    # Asset class: forex, stock, index, crypto
    asset_class: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    # Whether this symbol is actively scanned
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
    )

    # Last time this symbol was scanned
    last_scanned_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )

    # When this symbol was added to watchlist
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    # When this symbol was last modified
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Note: PostgreSQL-specific constraints like symbol ~ '^[A-Z0-9./^-]+$'
    # are defined in the migration. The ORM constraints are SQLite-compatible
    # for testing purposes.
    __table_args__ = (
        CheckConstraint(
            "LENGTH(symbol) BETWEEN 1 AND 20",
            name="chk_scanner_watchlist_symbol_length",
        ),
        CheckConstraint(
            "timeframe IN ('1M', '5M', '15M', '30M', '1H', '4H', '1D', '1W')",
            name="chk_scanner_watchlist_timeframe",
        ),
        CheckConstraint(
            "asset_class IN ('forex', 'stock', 'index', 'crypto')",
            name="chk_scanner_watchlist_asset_class",
        ),
        Index(
            "idx_scanner_watchlist_enabled",
            "enabled",
        ),
    )


class ScannerConfigORM(Base):
    """
    Scanner configuration (singleton pattern).

    Table: scanner_config
    Primary Key: id (UUID)

    Stores scanner settings like scan interval, batch size,
    session filtering, and running state. Only one row exists.
    """

    __tablename__ = "scanner_config"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # How often to scan (in seconds), minimum 60
    scan_interval_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="300",
    )

    # How many symbols to process per batch (1-50)
    batch_size: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="10",
    )

    # Whether to filter by trading session hours
    session_filter_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
    )

    # Whether scanner is currently running
    is_running: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
    )

    # When last scan cycle completed
    last_cycle_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )

    # When config was last updated
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "scan_interval_seconds >= 60",
            name="chk_scanner_config_interval",
        ),
        CheckConstraint(
            "batch_size >= 1 AND batch_size <= 50",
            name="chk_scanner_config_batch_size",
        ),
    )


class ScannerHistoryORM(Base):
    """
    Scanner history for tracking scan cycles.

    Table: scanner_history
    Primary Key: id (UUID)
    Indexes: idx_scanner_history_cycle_started

    Records each scan cycle's results for monitoring
    and debugging purposes.
    """

    __tablename__ = "scanner_history"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # When this scan cycle started
    cycle_started_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
    )

    # When this scan cycle ended (null if still running or crashed)
    cycle_ended_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )

    # Number of symbols scanned in this cycle
    symbols_scanned: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # Number of signals generated in this cycle
    signals_generated: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # Number of errors encountered
    errors_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )

    # Number of symbols with no OHLCV data
    symbols_no_data: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )

    # Correlation IDs of signals generated during this cycle (Task #25)
    # Stored as JSONB array of UUID strings: ["uuid1", "uuid2", ...]
    correlation_ids: Mapped[list[str] | None] = mapped_column(
        PortableJSONB,
        nullable=True,
        server_default="[]",
    )

    # Cycle status: COMPLETED, PARTIAL, FAILED, SKIPPED
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('COMPLETED', 'PARTIAL', 'FAILED', 'SKIPPED')",
            name="chk_scanner_history_status",
        ),
        Index(
            "idx_scanner_history_cycle_started",
            "cycle_started_at",
        ),
    )
