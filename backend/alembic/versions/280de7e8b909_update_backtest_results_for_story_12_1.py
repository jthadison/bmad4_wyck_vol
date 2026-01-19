"""update_backtest_results_for_story_12_1

Revision ID: 280de7e8b909
Revises: 020_system_configuration
Create Date: 2025-12-20 16:10:07.511781

Story 12.1 Task 12: Update backtest_results table schema to support
comprehensive backtesting engine with equity curves, trades, and metrics.

Changes:
- Drop old pattern detection metric columns
- Add JSONB columns for equity_curve, trades, metrics (config already exists)
- Add execution_time_seconds for performance tracking
- Add indexes for query optimization (idx_backtest_symbol, idx_backtest_created_at)
- Update start_date/end_date to DateTime (was Date)
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "280de7e8b909"
down_revision: Union[str, Sequence[str], None] = "020_system_configuration"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Upgrade backtest_results table for Story 12.1.

    AC10 Subtask 12.1-12.3: Add JSONB columns, indexes for performance.
    """
    # Drop old pattern detection columns (no longer used)
    op.drop_column("backtest_results", "total_patterns_detected")
    op.drop_column("backtest_results", "true_positives")
    op.drop_column("backtest_results", "false_positives")
    op.drop_column("backtest_results", "false_negatives")
    op.drop_column("backtest_results", "precision")
    op.drop_column("backtest_results", "recall")
    op.drop_column("backtest_results", "total_signals_generated")
    op.drop_column("backtest_results", "winning_signals")
    op.drop_column("backtest_results", "losing_signals")
    op.drop_column("backtest_results", "win_rate")
    op.drop_column("backtest_results", "average_r_multiple")
    op.drop_column("backtest_results", "max_drawdown")

    # Note: config column already exists from 001_initial_schema_with_timescaledb.py
    # so we don't need to add it again

    # Add new JSONB columns for Story 12.1
    op.add_column(
        "backtest_results",
        sa.Column("equity_curve", postgresql.JSONB, nullable=False, server_default="[]"),
    )
    op.add_column(
        "backtest_results",
        sa.Column("trades", postgresql.JSONB, nullable=False, server_default="[]"),
    )
    op.add_column(
        "backtest_results",
        sa.Column("metrics", postgresql.JSONB, nullable=False, server_default="{}"),
    )

    # Add execution metadata
    op.add_column(
        "backtest_results",
        sa.Column(
            "execution_time_seconds", sa.NUMERIC(10, 4), nullable=False, server_default="0.0"
        ),
    )

    # Update date columns to DateTime with timezone
    op.alter_column(
        "backtest_results",
        "start_date",
        existing_type=sa.Date(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=False,
    )
    op.alter_column(
        "backtest_results",
        "end_date",
        existing_type=sa.Date(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=False,
    )

    # Add indexes for query performance (AC10 Subtask 12.3)
    op.create_index("idx_backtest_symbol", "backtest_results", ["symbol"])
    op.create_index("idx_backtest_created_at", "backtest_results", ["created_at"])

    # Add unique index on backtest_run_id if not exists
    op.create_index(
        "idx_backtest_run_id_unique", "backtest_results", ["backtest_run_id"], unique=True
    )


def downgrade() -> None:
    """
    Downgrade backtest_results table (rollback Story 12.1 changes).
    """
    # Drop indexes
    op.drop_index("idx_backtest_run_id_unique", table_name="backtest_results")
    op.drop_index("idx_backtest_created_at", table_name="backtest_results")
    op.drop_index("idx_backtest_symbol", table_name="backtest_results")

    # Restore date columns
    op.alter_column(
        "backtest_results",
        "start_date",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.Date(),
        existing_nullable=False,
    )
    op.alter_column(
        "backtest_results",
        "end_date",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.Date(),
        existing_nullable=False,
    )

    # Drop Story 12.1 columns (config column existed before this migration, so don't drop it)
    op.drop_column("backtest_results", "execution_time_seconds")
    op.drop_column("backtest_results", "metrics")
    op.drop_column("backtest_results", "trades")
    op.drop_column("backtest_results", "equity_curve")

    # Restore old pattern detection columns
    op.add_column(
        "backtest_results",
        sa.Column("total_patterns_detected", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "backtest_results",
        sa.Column("true_positives", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "backtest_results",
        sa.Column("false_positives", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "backtest_results",
        sa.Column("false_negatives", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "backtest_results",
        sa.Column("precision", sa.NUMERIC(6, 4), nullable=False, server_default="0.0"),
    )
    op.add_column(
        "backtest_results",
        sa.Column("recall", sa.NUMERIC(6, 4), nullable=False, server_default="0.0"),
    )
    op.add_column(
        "backtest_results",
        sa.Column("total_signals_generated", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "backtest_results",
        sa.Column("winning_signals", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "backtest_results",
        sa.Column("losing_signals", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "backtest_results",
        sa.Column("win_rate", sa.NUMERIC(6, 4), nullable=False, server_default="0.0"),
    )
    op.add_column(
        "backtest_results",
        sa.Column("average_r_multiple", sa.NUMERIC(6, 2), nullable=False, server_default="0.0"),
    )
    op.add_column(
        "backtest_results",
        sa.Column("max_drawdown", sa.NUMERIC(6, 4), nullable=False, server_default="0.0"),
    )
