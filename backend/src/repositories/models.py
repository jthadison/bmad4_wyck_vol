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
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

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
    Campaign database model (Story 9.1, 9.4, 9.7).

    Represents a trading campaign (Spring → SOS → LPS entry sequence)
    within a single trading range with BMAD allocation and 5% risk limit.

    Updated in Story 9.7:
    - Added entries JSONB field for EntryDetails tracking
    - Added campaign_id, phase, timeframe fields (from migration 009)
    - Added lifecycle tracking fields
    """

    __tablename__ = "campaigns"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Identification
    campaign_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
        index=True,
        comment="Human-readable ID: {symbol}-{range_start_date}",
    )
    symbol: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )
    timeframe: Mapped[str] = mapped_column(
        String(5),
        nullable=False,
        comment="Bar interval (e.g., 1h, 1d)",
    )
    trading_range_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,  # Optional link to trading range
        index=True,
    )

    # Lifecycle management
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="ACTIVE",
        index=True,
    )
    phase: Mapped[str] = mapped_column(
        String(1),
        nullable=False,
        comment="Wyckoff phase: C, D, E",
    )

    # Entry details tracking (Story 9.7)
    entries: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        server_default="'{}'::jsonb",
        comment="Entry details by pattern type (SPRING/SOS/LPS mapping)",
    )

    # Risk tracking
    total_risk: Mapped[Decimal] = mapped_column(
        DECIMAL(12, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Total dollar risk across all positions",
    )
    total_allocation: Mapped[Decimal] = mapped_column(
        DECIMAL(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Total % of portfolio allocated (max 5%)",
    )
    current_risk: Mapped[Decimal] = mapped_column(
        DECIMAL(12, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Current open risk (updated as positions close)",
    )

    # Position aggregations
    weighted_avg_entry: Mapped[Decimal | None] = mapped_column(
        DECIMAL(18, 8),
        nullable=True,
        comment="Weighted average entry price",
    )
    total_shares: Mapped[Decimal] = mapped_column(
        DECIMAL(18, 8),
        nullable=False,
        default=Decimal("0.00"),
        comment="Sum of all position shares",
    )
    total_pnl: Mapped[Decimal] = mapped_column(
        DECIMAL(12, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Current unrealized P&L",
    )

    # Lifecycle timestamps
    start_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Campaign start date (UTC)",
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Campaign completion date (UTC)",
    )
    invalidation_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Reason for invalidation if status=INVALIDATED",
    )

    # Optimistic locking
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="Optimistic locking version (increment on update)",
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
        # Check constraint for risk limit (5% max)
        CheckConstraint("total_allocation <= 5.0", name="ck_campaign_allocation_limit"),
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<Campaign(id={self.id}, campaign_id={self.campaign_id}, "
            f"symbol={self.symbol}, status={self.status}, phase={self.phase})>"
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


class ExitRuleModel(Base):
    """
    Exit Rule database model (Story 9.5).

    Represents exit strategy configuration for a campaign with target
    levels, partial exit percentages, and invalidation conditions.
    """

    __tablename__ = "exit_rules"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Foreign key to campaign (UNIQUE - one exit rule per campaign)
    campaign_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # Target levels (NUMERIC(18,8) precision)
    target_1_level: Mapped[Decimal] = mapped_column(
        DECIMAL(18, 8),
        nullable=False,
    )
    target_2_level: Mapped[Decimal] = mapped_column(
        DECIMAL(18, 8),
        nullable=False,
    )
    target_3_level: Mapped[Decimal] = mapped_column(
        DECIMAL(18, 8),
        nullable=False,
    )

    # Partial exit percentages (NUMERIC(5,2) precision)
    t1_exit_pct: Mapped[Decimal] = mapped_column(
        DECIMAL(5, 2),
        nullable=False,
        default=Decimal("50.00"),
    )
    t2_exit_pct: Mapped[Decimal] = mapped_column(
        DECIMAL(5, 2),
        nullable=False,
        default=Decimal("30.00"),
    )
    t3_exit_pct: Mapped[Decimal] = mapped_column(
        DECIMAL(5, 2),
        nullable=False,
        default=Decimal("20.00"),
    )

    # Trailing stop configuration
    trail_to_breakeven_on_t1: Mapped[bool] = mapped_column(
        nullable=False,
        default=True,
    )
    trail_to_t1_on_t2: Mapped[bool] = mapped_column(
        nullable=False,
        default=True,
    )

    # Invalidation levels (NUMERIC(18,8) precision)
    spring_low: Mapped[Decimal] = mapped_column(
        DECIMAL(18, 8),
        nullable=True,
    )
    ice_level: Mapped[Decimal] = mapped_column(
        DECIMAL(18, 8),
        nullable=True,
    )
    creek_level: Mapped[Decimal] = mapped_column(
        DECIMAL(18, 8),
        nullable=True,
    )
    utad_high: Mapped[Decimal] = mapped_column(
        DECIMAL(18, 8),
        nullable=True,
    )
    jump_target: Mapped[Decimal] = mapped_column(
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

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "t1_exit_pct >= 0 AND t1_exit_pct <= 100",
            name="ck_exit_rules_t1_pct_range",
        ),
        CheckConstraint(
            "t2_exit_pct >= 0 AND t2_exit_pct <= 100",
            name="ck_exit_rules_t2_pct_range",
        ),
        CheckConstraint(
            "t3_exit_pct >= 0 AND t3_exit_pct <= 100",
            name="ck_exit_rules_t3_pct_range",
        ),
        CheckConstraint(
            "target_1_level > 0 AND target_2_level > 0 AND target_3_level > 0",
            name="ck_exit_rules_positive_targets",
        ),
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<ExitRule(id={self.id}, campaign_id={self.campaign_id}, "
            f"T1={self.target_1_level}, T2={self.target_2_level}, T3={self.target_3_level})>"
        )


class ExitOrderModel(Base):
    """
    Exit Order database model (Story 9.5).

    Represents a triggered exit order (partial exit, stop loss, or
    emergency invalidation exit).
    """

    __tablename__ = "exit_orders"

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
    position_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("positions.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # Exit details
    order_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    exit_level: Mapped[Decimal] = mapped_column(
        DECIMAL(18, 8),
        nullable=False,
    )
    shares: Mapped[int] = mapped_column(
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    # Timestamps
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    # Execution tracking
    executed: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
    )

    # Record timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )

    # Constraints
    __table_args__ = (
        # Composite index for campaign+triggered_at queries
        Index("ix_exit_orders_campaign_triggered", "campaign_id", "triggered_at"),
        # Check constraints
        CheckConstraint(
            "order_type IN ('PARTIAL_EXIT', 'STOP_LOSS', 'INVALIDATION')",
            name="ck_exit_orders_order_type",
        ),
        CheckConstraint("exit_level > 0", name="ck_exit_orders_positive_exit_level"),
        CheckConstraint("shares > 0", name="ck_exit_orders_positive_shares"),
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<ExitOrder(id={self.id}, campaign_id={self.campaign_id}, "
            f"order_type={self.order_type}, shares={self.shares})>"
        )


class CampaignMetricsModel(Base):
    """
    Campaign performance metrics database model (Story 9.6).

    Stores calculated performance analytics for completed campaigns including
    campaign-level metrics (total return %, total R, win rate, max drawdown),
    comparison metrics (expected vs actual), and phase-specific metrics
    (Phase C vs Phase D performance).
    """

    __tablename__ = "campaign_metrics"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Campaign identification
    campaign_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
    )
    symbol: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    # Campaign-level metrics
    total_return_pct: Mapped[Decimal] = mapped_column(
        DECIMAL(18, 8),
        nullable=False,
    )
    total_r_achieved: Mapped[Decimal] = mapped_column(
        DECIMAL(8, 4),
        nullable=False,
    )
    duration_days: Mapped[int] = mapped_column(
        nullable=False,
    )
    max_drawdown: Mapped[Decimal] = mapped_column(
        DECIMAL(18, 8),
        nullable=False,
    )
    total_positions: Mapped[int] = mapped_column(
        nullable=False,
    )
    winning_positions: Mapped[int] = mapped_column(
        nullable=False,
    )
    losing_positions: Mapped[int] = mapped_column(
        nullable=False,
    )
    win_rate: Mapped[Decimal] = mapped_column(
        DECIMAL(5, 2),
        nullable=False,
    )
    average_entry_price: Mapped[Decimal] = mapped_column(
        DECIMAL(18, 8),
        nullable=False,
    )
    average_exit_price: Mapped[Decimal] = mapped_column(
        DECIMAL(18, 8),
        nullable=False,
    )

    # Comparison metrics (expected vs actual)
    expected_jump_target: Mapped[Decimal | None] = mapped_column(
        DECIMAL(18, 8),
        nullable=True,
    )
    actual_high_reached: Mapped[Decimal | None] = mapped_column(
        DECIMAL(18, 8),
        nullable=True,
    )
    target_achievement_pct: Mapped[Decimal | None] = mapped_column(
        DECIMAL(7, 2),
        nullable=True,
    )
    expected_r: Mapped[Decimal | None] = mapped_column(
        DECIMAL(8, 4),
        nullable=True,
    )
    actual_r_achieved: Mapped[Decimal | None] = mapped_column(
        DECIMAL(8, 4),
        nullable=True,
    )

    # Phase-specific metrics (AC #11) - Wyckoff methodology validation
    phase_c_avg_r: Mapped[Decimal | None] = mapped_column(
        DECIMAL(8, 4),
        nullable=True,
    )
    phase_d_avg_r: Mapped[Decimal | None] = mapped_column(
        DECIMAL(8, 4),
        nullable=True,
    )
    phase_c_positions: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
    )
    phase_d_positions: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
    )
    phase_c_win_rate: Mapped[Decimal | None] = mapped_column(
        DECIMAL(5, 2),
        nullable=True,
    )
    phase_d_win_rate: Mapped[Decimal | None] = mapped_column(
        DECIMAL(5, 2),
        nullable=True,
    )

    # Metadata
    calculation_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
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

    # Constraints and indexes
    __table_args__ = (
        # Unique index on campaign_id (one metrics record per campaign)
        Index("ix_campaign_metrics_campaign_id", "campaign_id", unique=True),
        # Index on completed_at for historical queries
        Index("ix_campaign_metrics_completed_at", "completed_at"),
        # Index on symbol for filtering
        Index("ix_campaign_metrics_symbol", "symbol"),
        # Composite index for filtered historical queries
        Index("ix_campaign_metrics_symbol_completed_at", "symbol", "completed_at"),
        # Unique constraint on (campaign_id, calculation_timestamp)
        UniqueConstraint(
            "campaign_id", "calculation_timestamp", name="uq_campaign_metrics_campaign_calculation"
        ),
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<CampaignMetrics(id={self.id}, campaign_id={self.campaign_id}, "
            f"symbol={self.symbol}, total_r={self.total_r_achieved})>"
        )


class BacktestResultModel(Base):
    """
    Backtest Result database model (Story 12.1 Task 9).

    Stores completed backtest runs with their configuration, trades,
    equity curves, and performance metrics.
    """

    __tablename__ = "backtest_results"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Backtest run identification
    backtest_run_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        unique=True,
        index=True,
    )

    # Trading symbol and timeframe
    symbol: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    timeframe: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="1d",
    )

    # Date range
    start_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    end_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    # Configuration (JSONB)
    config: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
    )

    # Equity curve time series (JSONB)
    equity_curve: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    # Trades (JSONB)
    trades: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    # Performance summary metrics (JSONB)
    summary: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
    )

    # Look-ahead bias validation
    look_ahead_bias_check: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
    )

    # Execution metadata
    execution_time_seconds: Mapped[Decimal] = mapped_column(
        DECIMAL(10, 4),
        nullable=False,
        default=Decimal("0.0"),
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

    # Indexes for query performance
    __table_args__ = (
        # Index on symbol for filtering
        Index("ix_backtest_results_symbol", "symbol"),
        # Index on created_at for sorting
        Index("ix_backtest_results_created_at", "created_at"),
        # Composite index for symbol + created_at queries
        Index("ix_backtest_results_symbol_created_at", "symbol", "created_at"),
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<BacktestResult(id={self.id}, backtest_run_id={self.backtest_run_id}, "
            f"symbol={self.symbol}, trades={len(self.trades)})>"
        )


class WalkForwardResultModel(Base):
    """
    Walk-Forward Test Result database model (Story 12.4 Task 10).

    Stores walk-forward validation test results with rolling windows,
    summary statistics, stability scores, and statistical significance tests.
    """

    __tablename__ = "walk_forward_results"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Walk-forward test identification
    walk_forward_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        unique=True,
        index=True,
    )

    # Configuration (JSONB)
    config: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
    )

    # Validation windows (JSONB - list of ValidationWindow objects)
    windows: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    # Summary statistics (JSONB)
    summary_statistics: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )

    # Stability score (coefficient of variation)
    stability_score: Mapped[Decimal] = mapped_column(
        DECIMAL(6, 4),
        nullable=False,
        default=Decimal("0.0"),
    )

    # Degradation windows (JSONB - list of window numbers)
    degradation_windows: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    # Statistical significance (JSONB - p-values dict)
    statistical_significance: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )

    # Chart data (JSONB - optional)
    chart_data: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    # Execution metadata
    total_execution_time_seconds: Mapped[Decimal] = mapped_column(
        DECIMAL(10, 4),
        nullable=False,
        default=Decimal("0.0"),
    )

    avg_window_execution_time_seconds: Mapped[Decimal] = mapped_column(
        DECIMAL(10, 4),
        nullable=False,
        default=Decimal("0.0"),
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

    # Indexes for query performance
    __table_args__ = (
        # Index on created_at for sorting
        Index("ix_walk_forward_results_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<WalkForwardResult(id={self.id}, walk_forward_id={self.walk_forward_id}, "
            f"windows={len(self.windows)})>"
        )
