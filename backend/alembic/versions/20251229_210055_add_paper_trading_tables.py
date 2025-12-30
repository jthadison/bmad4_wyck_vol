"""add_paper_trading_tables

Revision ID: 20251229_210055
Revises: 022_add_story_12_6_metrics
Create Date: 2025-12-29 21:00:55

Story 12.8 Task 5: Add database tables for paper trading mode.

Changes:
- Create paper_accounts table (singleton for system)
- Create paper_positions table (virtual open positions)
- Create paper_trades table (closed trade history)
- Add indexes for query optimization
- Add foreign key constraints
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20251229_210055"
down_revision: Union[str, Sequence[str], None] = "022_add_story_12_6_metrics"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create paper trading tables for Story 12.8.

    Paper trading mode simulates live trading without real capital.
    """
    # Create paper_accounts table (singleton)
    op.create_table(
        "paper_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("starting_capital", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("current_capital", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("equity", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column(
            "total_realized_pnl",
            sa.Numeric(precision=20, scale=8),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "total_unrealized_pnl",
            sa.Numeric(precision=20, scale=8),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "total_commission_paid",
            sa.Numeric(precision=20, scale=8),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "total_slippage_cost",
            sa.Numeric(precision=20, scale=8),
            nullable=False,
            server_default="0",
        ),
        sa.Column("total_trades", sa.Integer, nullable=False, server_default="0"),
        sa.Column("winning_trades", sa.Integer, nullable=False, server_default="0"),
        sa.Column("losing_trades", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "win_rate", sa.Numeric(precision=20, scale=8), nullable=False, server_default="0"
        ),
        sa.Column(
            "average_r_multiple",
            sa.Numeric(precision=20, scale=8),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "max_drawdown", sa.Numeric(precision=20, scale=8), nullable=False, server_default="0"
        ),
        sa.Column(
            "current_heat", sa.Numeric(precision=20, scale=8), nullable=False, server_default="0"
        ),
        sa.Column("paper_trading_start_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    # Create paper_positions table (virtual open positions)
    op.create_table(
        "paper_positions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("signal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("symbol", sa.String(length=10), nullable=False),
        sa.Column("entry_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("entry_price", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("stop_loss", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("target_1", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("target_2", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("current_price", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("unrealized_pnl", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="OPEN"),
        sa.Column("commission_paid", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("slippage_cost", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        # Foreign key to signals table (if exists)
        sa.ForeignKeyConstraint(["signal_id"], ["signals.id"], ondelete="CASCADE"),
    )

    # Create indexes for paper_positions
    op.create_index("idx_paper_positions_signal_id", "paper_positions", ["signal_id"])
    op.create_index("idx_paper_positions_symbol", "paper_positions", ["symbol"])
    op.create_index("idx_paper_positions_status", "paper_positions", ["status"])
    op.create_index("idx_paper_positions_entry_time", "paper_positions", ["entry_time"])

    # Create paper_trades table (closed trade history)
    op.create_table(
        "paper_trades",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("position_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("signal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("symbol", sa.String(length=10), nullable=False),
        sa.Column("entry_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("entry_price", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("exit_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("exit_price", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("realized_pnl", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("r_multiple_achieved", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("commission_total", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("slippage_total", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("exit_reason", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        # Foreign keys
        sa.ForeignKeyConstraint(["position_id"], ["paper_positions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["signal_id"], ["signals.id"], ondelete="CASCADE"),
    )

    # Create indexes for paper_trades
    op.create_index("idx_paper_trades_position_id", "paper_trades", ["position_id"])
    op.create_index("idx_paper_trades_signal_id", "paper_trades", ["signal_id"])
    op.create_index("idx_paper_trades_symbol", "paper_trades", ["symbol"])
    op.create_index("idx_paper_trades_exit_time", "paper_trades", ["exit_time"])
    op.create_index("idx_paper_trades_exit_reason", "paper_trades", ["exit_reason"])


def downgrade() -> None:
    """
    Drop paper trading tables.
    """
    # Drop tables in reverse order (respect foreign keys)
    op.drop_index("idx_paper_trades_exit_reason", table_name="paper_trades")
    op.drop_index("idx_paper_trades_exit_time", table_name="paper_trades")
    op.drop_index("idx_paper_trades_symbol", table_name="paper_trades")
    op.drop_index("idx_paper_trades_signal_id", table_name="paper_trades")
    op.drop_index("idx_paper_trades_position_id", table_name="paper_trades")
    op.drop_table("paper_trades")

    op.drop_index("idx_paper_positions_entry_time", table_name="paper_positions")
    op.drop_index("idx_paper_positions_status", table_name="paper_positions")
    op.drop_index("idx_paper_positions_symbol", table_name="paper_positions")
    op.drop_index("idx_paper_positions_signal_id", table_name="paper_positions")
    op.drop_table("paper_positions")

    op.drop_table("paper_accounts")
