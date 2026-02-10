"""
Paper Trading ORM Models (Story 12.8 Task 5)

SQLAlchemy ORM models for paper trading database tables.
These will be merged into src/repositories/models.py.

Author: Story 12.8
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import (
    DECIMAL,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


class PaperAccountDB(Base):
    """
    Paper Account database model (Story 12.8 Task 5).

    Singleton account for paper trading mode.
    Tracks virtual capital, performance metrics, and trading statistics.
    """

    __tablename__ = "paper_accounts"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Capital tracking
    starting_capital: Mapped[Decimal] = mapped_column(
        DECIMAL(precision=20, scale=8),
        nullable=False,
    )
    current_capital: Mapped[Decimal] = mapped_column(
        DECIMAL(precision=20, scale=8),
        nullable=False,
    )
    equity: Mapped[Decimal] = mapped_column(
        DECIMAL(precision=20, scale=8),
        nullable=False,
    )

    # P&L tracking
    total_realized_pnl: Mapped[Decimal] = mapped_column(
        DECIMAL(precision=20, scale=8),
        nullable=False,
        server_default="0",
    )
    total_unrealized_pnl: Mapped[Decimal] = mapped_column(
        DECIMAL(precision=20, scale=8),
        nullable=False,
        server_default="0",
    )

    # Cost tracking
    total_commission_paid: Mapped[Decimal] = mapped_column(
        DECIMAL(precision=20, scale=8),
        nullable=False,
        server_default="0",
    )
    total_slippage_cost: Mapped[Decimal] = mapped_column(
        DECIMAL(precision=20, scale=8),
        nullable=False,
        server_default="0",
    )

    # Trade statistics
    total_trades: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )
    winning_trades: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )
    losing_trades: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )

    # Performance metrics
    win_rate: Mapped[Decimal] = mapped_column(
        DECIMAL(precision=20, scale=8),
        nullable=False,
        server_default="0",
    )
    average_r_multiple: Mapped[Decimal] = mapped_column(
        DECIMAL(precision=20, scale=8),
        nullable=False,
        server_default="0",
    )
    max_drawdown: Mapped[Decimal] = mapped_column(
        DECIMAL(precision=20, scale=8),
        nullable=False,
        server_default="0",
    )
    current_heat: Mapped[Decimal] = mapped_column(
        DECIMAL(precision=20, scale=8),
        nullable=False,
        server_default="0",
    )

    # Duration tracking (for 3-month requirement)
    paper_trading_start_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<PaperAccountDB(id={self.id}, equity={self.equity}, "
            f"total_trades={self.total_trades})>"
        )


class PaperPositionDB(Base):
    """
    Paper Position database model (Story 12.8 Task 5).

    Represents an open virtual position in paper trading mode.
    Updated in real-time as market prices change.
    """

    __tablename__ = "paper_positions"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Foreign keys
    signal_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("signals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Position details
    symbol: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        index=True,
    )
    entry_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    entry_price: Mapped[Decimal] = mapped_column(
        DECIMAL(precision=20, scale=8),
        nullable=False,
    )
    quantity: Mapped[Decimal] = mapped_column(
        DECIMAL(precision=20, scale=8),
        nullable=False,
    )

    # Stops and targets
    stop_loss: Mapped[Decimal] = mapped_column(
        DECIMAL(precision=20, scale=8),
        nullable=False,
    )
    target_1: Mapped[Decimal] = mapped_column(
        DECIMAL(precision=20, scale=8),
        nullable=False,
    )
    target_2: Mapped[Decimal] = mapped_column(
        DECIMAL(precision=20, scale=8),
        nullable=False,
    )

    # Current state
    current_price: Mapped[Decimal] = mapped_column(
        DECIMAL(precision=20, scale=8),
        nullable=False,
    )
    unrealized_pnl: Mapped[Decimal] = mapped_column(
        DECIMAL(precision=20, scale=8),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="OPEN",
        index=True,
    )

    # Costs
    commission_paid: Mapped[Decimal] = mapped_column(
        DECIMAL(precision=20, scale=8),
        nullable=False,
    )
    slippage_cost: Mapped[Decimal] = mapped_column(
        DECIMAL(precision=20, scale=8),
        nullable=False,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<PaperPositionDB(id={self.id}, symbol={self.symbol}, "
            f"status={self.status}, unrealized_pnl={self.unrealized_pnl})>"
        )


class PaperTradeDB(Base):
    """
    Paper Trade database model (Story 12.8 Task 5).

    Represents a closed trade from paper trading mode.
    Stored for performance analysis and comparison to backtests.
    """

    __tablename__ = "paper_trades"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Foreign keys
    position_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("paper_positions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    signal_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("signals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Trade details
    symbol: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        index=True,
    )
    entry_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    entry_price: Mapped[Decimal] = mapped_column(
        DECIMAL(precision=20, scale=8),
        nullable=False,
    )
    exit_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    exit_price: Mapped[Decimal] = mapped_column(
        DECIMAL(precision=20, scale=8),
        nullable=False,
    )
    quantity: Mapped[Decimal] = mapped_column(
        DECIMAL(precision=20, scale=8),
        nullable=False,
    )

    # Performance
    realized_pnl: Mapped[Decimal] = mapped_column(
        DECIMAL(precision=20, scale=8),
        nullable=False,
    )
    r_multiple_achieved: Mapped[Decimal] = mapped_column(
        DECIMAL(precision=20, scale=8),
        nullable=False,
    )

    # Costs
    commission_total: Mapped[Decimal] = mapped_column(
        DECIMAL(precision=20, scale=8),
        nullable=False,
    )
    slippage_total: Mapped[Decimal] = mapped_column(
        DECIMAL(precision=20, scale=8),
        nullable=False,
    )

    # Exit details
    exit_reason: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<PaperTradeDB(id={self.id}, symbol={self.symbol}, "
            f"realized_pnl={self.realized_pnl}, exit_reason={self.exit_reason})>"
        )


class PaperTradingSessionDB(Base):
    """
    Archived paper trading session (Story 23.8a).

    Preserves historical data when a paper trading account is reset.
    """

    __tablename__ = "paper_trading_sessions"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    account_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    trades_snapshot: Mapped[list] = mapped_column(JSONB, nullable=False)
    final_metrics: Mapped[dict] = mapped_column(JSONB, nullable=False)
    session_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    session_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    archived_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<PaperTradingSessionDB(id={self.id}, "
            f"session_start={self.session_start}, session_end={self.session_end})>"
        )


class PaperTradingConfigDB(Base):
    """
    Paper Trading Config database model (Story 23.8a).

    Singleton configuration for paper trading mode.
    Stores user-customizable settings for simulation parameters.
    """

    __tablename__ = "paper_trading_configs"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
    )
    starting_capital: Mapped[Decimal] = mapped_column(
        DECIMAL(precision=20, scale=8),
        nullable=False,
    )
    commission_per_share: Mapped[Decimal] = mapped_column(
        DECIMAL(precision=20, scale=8),
        nullable=False,
    )
    slippage_percentage: Mapped[Decimal] = mapped_column(
        DECIMAL(precision=20, scale=8),
        nullable=False,
    )
    use_realistic_fills: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<PaperTradingConfigDB(id={self.id}, enabled={self.enabled}, "
            f"starting_capital={self.starting_capital})>"
        )
