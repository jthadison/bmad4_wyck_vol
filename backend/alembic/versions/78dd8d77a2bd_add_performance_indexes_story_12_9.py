"""add_performance_indexes_story_12_9

Revision ID: 78dd8d77a2bd
Revises: 63ba0d7b4aa9
Create Date: 2025-12-30 11:50:11.638557

Story 12.9: Performance Benchmarking - Database Index Optimization

This migration adds performance-optimized indexes for high-traffic query patterns
identified in Task 4 (Database Query Benchmarks). These indexes target:

1. OHLCV data retrieval by symbol and timerange (NFR1: <50ms target)
2. Signal queries by symbol, status, and pattern type
3. Pattern detection queries by symbol and timeframe
4. Backtest results pagination and filtering
5. Trading range queries by symbol and status

Performance Impact:
- OHLCV range queries: Expected 5-10x speedup
- Signal status queries: Expected 3-5x speedup
- Pattern type filtering: Expected 4-6x speedup
- Composite queries: Expected 2-3x speedup

Note: Some tables (ohlcv_bars, users) already have basic indexes on symbol,
timestamp, username, email from earlier migrations. This migration adds
composite and specialized indexes for complex query patterns.
"""
from collections.abc import Sequence
from typing import Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "78dd8d77a2bd"
down_revision: Union[str, Sequence[str], None] = "63ba0d7b4aa9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add performance indexes for high-traffic query patterns.

    Index Categories:
    1. OHLCV Bars - Composite indexes for symbol + timerange queries
    2. Signals - Status, pattern type, and symbol filtering
    3. Patterns - Pattern type and detection time queries
    4. Trading Ranges - Symbol, status, and timestamp filtering
    5. Backtest Results - Status and pagination
    6. Campaigns - Status and user filtering
    """

    # ========================================================================
    # OHLCV Bars (ohlcv_bars) - Most frequently queried table
    # ========================================================================

    # Composite index for symbol + timerange queries (PRIMARY USE CASE)
    # Covers: SELECT * FROM ohlcv_bars WHERE symbol = ? AND timestamp BETWEEN ? AND ?
    # Expected speedup: 5-10x for range queries
    op.create_index(
        "idx_ohlcv_symbol_timestamp",
        "ohlcv_bars",
        ["symbol", "timestamp"],
        unique=False,
    )

    # Composite index for symbol + timeframe + timestamp
    # Covers: Queries filtering by all three (less common but valuable)
    op.create_index(
        "idx_ohlcv_symbol_timeframe_timestamp",
        "ohlcv_bars",
        ["symbol", "timeframe", "timestamp"],
        unique=False,
    )

    # Descending timestamp index for "latest bars" queries
    # Covers: SELECT * FROM ohlcv_bars ORDER BY timestamp DESC LIMIT ?
    op.create_index(
        "idx_ohlcv_timestamp_desc",
        "ohlcv_bars",
        ["timestamp"],
        unique=False,
        postgresql_ops={"timestamp": "DESC"},
    )

    # ========================================================================
    # Signals (signals) - High-traffic for signal generation and filtering
    # ========================================================================

    # Composite index for symbol + status queries
    # Covers: SELECT * FROM signals WHERE symbol = ? AND status = ?
    # Expected speedup: 3-5x for active signal queries
    op.create_index(
        "idx_signals_symbol_status",
        "signals",
        ["symbol", "status"],
        unique=False,
    )

    # Note: idx_signals_status already exists from 001_initial_schema_with_timescaledb.py
    # as a composite index on (status, generated_at DESC), which covers status-only queries.
    # Skipping duplicate index creation.

    # Composite index for pattern_id filtering (joins with patterns table)
    # Covers: SELECT * FROM signals WHERE pattern_id = ?
    op.create_index(
        "idx_signals_pattern_id",
        "signals",
        ["pattern_id"],
        unique=False,
    )

    # Composite index for campaign_id filtering
    # Covers: SELECT * FROM signals WHERE campaign_id = ?
    op.create_index(
        "idx_signals_campaign_id",
        "signals",
        ["campaign_id"],
        unique=False,
    )

    # Descending generated_at index for "latest signals" queries
    # Covers: SELECT * FROM signals ORDER BY generated_at DESC LIMIT ?
    op.create_index(
        "idx_signals_generated_at_desc",
        "signals",
        ["generated_at"],
        unique=False,
        postgresql_ops={"generated_at": "DESC"},
    )

    # Note: idx_signals_symbol_generated_at already exists from 016_analytics_indexes.py
    # Skipping duplicate index creation.

    # ========================================================================
    # Patterns (patterns) - Pattern detection queries
    # ========================================================================

    # Composite index for symbol + pattern_type
    # Covers: SELECT * FROM patterns WHERE symbol = ? AND pattern_type = ?
    # Expected speedup: 4-6x for pattern type filtering
    op.create_index(
        "idx_patterns_symbol_pattern_type",
        "patterns",
        ["symbol", "pattern_type"],
        unique=False,
    )

    # Index for pattern_type-only queries
    # Covers: SELECT * FROM patterns WHERE pattern_type = ?
    op.create_index(
        "idx_patterns_pattern_type",
        "patterns",
        ["pattern_type"],
        unique=False,
    )

    # Composite index for symbol + detection_time (time-series queries)
    # Covers: SELECT * FROM patterns WHERE symbol = ? AND detection_time > ?
    op.create_index(
        "idx_patterns_symbol_detection_time",
        "patterns",
        ["symbol", "detection_time"],
        unique=False,
    )

    # Descending detection_time index for "latest patterns" queries
    # Covers: SELECT * FROM patterns ORDER BY detection_time DESC LIMIT ?
    op.create_index(
        "idx_patterns_detection_time_desc",
        "patterns",
        ["detection_time"],
        unique=False,
        postgresql_ops={"detection_time": "DESC"},
    )

    # Index for trading_range_id foreign key
    # Covers: SELECT * FROM patterns WHERE trading_range_id = ?
    op.create_index(
        "idx_patterns_trading_range_id",
        "patterns",
        ["trading_range_id"],
        unique=False,
    )

    # Composite index for symbol + timeframe + detection_time
    # Covers: Complex queries filtering by all three
    op.create_index(
        "idx_patterns_symbol_timeframe_detection",
        "patterns",
        ["symbol", "timeframe", "detection_time"],
        unique=False,
    )

    # ========================================================================
    # Trading Ranges (trading_ranges) - Range lifecycle and status queries
    # ========================================================================

    # Composite index for symbol + status
    # Covers: SELECT * FROM trading_ranges WHERE symbol = ? AND status IN (?)
    # Note: Status field not in schema yet, but planned for Story 3.8
    # Commented out for now - uncomment when status column added
    # op.create_index(
    #     "idx_trading_ranges_symbol_status",
    #     "trading_ranges",
    #     ["symbol", "status"],
    #     unique=False,
    # )

    # Composite index for symbol + start_time
    # Covers: SELECT * FROM trading_ranges WHERE symbol = ? AND start_time > ?
    op.create_index(
        "idx_trading_ranges_symbol_start_time",
        "trading_ranges",
        ["symbol", "start_time"],
        unique=False,
    )

    # Descending start_time index for "latest ranges" queries
    # Covers: SELECT * FROM trading_ranges ORDER BY start_time DESC LIMIT ?
    op.create_index(
        "idx_trading_ranges_start_time_desc",
        "trading_ranges",
        ["start_time"],
        unique=False,
        postgresql_ops={"start_time": "DESC"},
    )

    # Composite index for symbol + timeframe + start_time
    # Covers: Queries filtering by all three
    op.create_index(
        "idx_trading_ranges_symbol_timeframe_start",
        "trading_ranges",
        ["symbol", "timeframe", "start_time"],
        unique=False,
    )

    # Index for phase queries
    # Covers: SELECT * FROM trading_ranges WHERE phase = ?
    op.create_index(
        "idx_trading_ranges_phase",
        "trading_ranges",
        ["phase"],
        unique=False,
    )

    # ========================================================================
    # Backtest Results (backtest_results) - Pagination and filtering
    # ========================================================================

    # Note: backtest_results table doesn't have a 'status' column yet.
    # The partial index for status filtering is commented out until the column is added.
    # op.execute(
    #     """
    #     CREATE INDEX idx_backtest_results_status_pending
    #     ON backtest_results (status)
    #     WHERE status = 'PENDING'
    #     """
    # )

    # Descending created_at index for pagination
    # Covers: SELECT * FROM backtest_results ORDER BY created_at DESC LIMIT ? OFFSET ?
    op.create_index(
        "idx_backtest_results_created_at_desc",
        "backtest_results",
        ["created_at"],
        unique=False,
        postgresql_ops={"created_at": "DESC"},
    )

    # ========================================================================
    # Campaigns (campaigns) - User campaigns and status filtering
    # ========================================================================

    # Composite index for user_id + status
    # Covers: SELECT * FROM campaigns WHERE user_id = ? AND status = ?
    op.create_index(
        "idx_campaigns_user_id_status",
        "campaigns",
        ["user_id", "status"],
        unique=False,
    )

    # Descending created_at index for "latest campaigns" queries
    # Covers: SELECT * FROM campaigns WHERE user_id = ? ORDER BY created_at DESC
    op.create_index(
        "idx_campaigns_created_at_desc",
        "campaigns",
        ["created_at"],
        unique=False,
        postgresql_ops={"created_at": "DESC"},
    )

    # ========================================================================
    # Positions (positions) - Active position tracking
    # ========================================================================

    # Composite index for campaign_id + status
    # Covers: SELECT * FROM positions WHERE campaign_id = ? AND status = ?
    op.create_index(
        "idx_positions_campaign_id_status",
        "positions",
        ["campaign_id", "status"],
        unique=False,
    )

    # Index for signal_id foreign key
    # Covers: SELECT * FROM positions WHERE signal_id = ?
    op.create_index(
        "idx_positions_signal_id",
        "positions",
        ["signal_id"],
        unique=False,
    )

    # ========================================================================
    # Notifications (notifications) - User notification queries
    # ========================================================================

    # Composite index for user_id + read status
    # Covers: SELECT * FROM notifications WHERE user_id = ? AND read = false
    op.create_index(
        "idx_notifications_user_id_read",
        "notifications",
        ["user_id", "read"],
        unique=False,
    )

    # Composite index for user_id + notification_type
    # Covers: SELECT * FROM notifications WHERE user_id = ? AND notification_type = ?
    op.create_index(
        "idx_notifications_user_id_type",
        "notifications",
        ["user_id", "notification_type"],
        unique=False,
    )


def downgrade() -> None:
    """
    Remove all performance indexes added in upgrade().

    This allows clean rollback if indexes cause issues or need redesign.
    """

    # Notifications
    op.drop_index("idx_notifications_user_id_type", table_name="notifications")
    op.drop_index("idx_notifications_user_id_read", table_name="notifications")

    # Positions
    op.drop_index("idx_positions_signal_id", table_name="positions")
    op.drop_index("idx_positions_campaign_id_status", table_name="positions")

    # Campaigns
    op.drop_index("idx_campaigns_created_at_desc", table_name="campaigns")
    op.drop_index("idx_campaigns_user_id_status", table_name="campaigns")

    # Backtest Results
    op.drop_index("idx_backtest_results_created_at_desc", table_name="backtest_results")
    # Note: idx_backtest_results_status_pending not created (status column doesn't exist)
    # op.execute("DROP INDEX IF EXISTS idx_backtest_results_status_pending")

    # Trading Ranges
    op.drop_index("idx_trading_ranges_phase", table_name="trading_ranges")
    op.drop_index("idx_trading_ranges_symbol_timeframe_start", table_name="trading_ranges")
    op.drop_index("idx_trading_ranges_start_time_desc", table_name="trading_ranges")
    op.drop_index("idx_trading_ranges_symbol_start_time", table_name="trading_ranges")
    # op.drop_index("idx_trading_ranges_symbol_status", table_name="trading_ranges")

    # Patterns
    op.drop_index("idx_patterns_symbol_timeframe_detection", table_name="patterns")
    op.drop_index("idx_patterns_trading_range_id", table_name="patterns")
    op.drop_index("idx_patterns_detection_time_desc", table_name="patterns")
    op.drop_index("idx_patterns_symbol_detection_time", table_name="patterns")
    op.drop_index("idx_patterns_pattern_type", table_name="patterns")
    op.drop_index("idx_patterns_symbol_pattern_type", table_name="patterns")

    # Signals
    # Note: idx_signals_symbol_generated_at not dropped here - it was created in 016_analytics_indexes.py
    op.drop_index("idx_signals_generated_at_desc", table_name="signals")
    op.drop_index("idx_signals_campaign_id", table_name="signals")
    op.drop_index("idx_signals_pattern_id", table_name="signals")
    # Note: idx_signals_status not dropped here - it was created in 001_initial_schema_with_timescaledb.py
    op.drop_index("idx_signals_symbol_status", table_name="signals")

    # OHLCV Bars
    op.drop_index("idx_ohlcv_timestamp_desc", table_name="ohlcv_bars")
    op.drop_index("idx_ohlcv_symbol_timeframe_timestamp", table_name="ohlcv_bars")
    op.drop_index("idx_ohlcv_symbol_timestamp", table_name="ohlcv_bars")
