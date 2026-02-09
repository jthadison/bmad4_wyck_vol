"""add_paper_trading_sessions_table

Revision ID: 20260209_paper_sessions
Revises: 20260206_symbols_no_data
Create Date: 2026-02-09

Story 23.8a: Add paper_trading_sessions table for session archiving.
Preserves historical data when a paper trading account is reset.
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260209_paper_sessions"
down_revision: Union[str, Sequence[str], None] = "20260206_symbols_no_data"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create paper_trading_sessions table."""
    op.create_table(
        "paper_trading_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("account_snapshot", postgresql.JSONB, nullable=False),
        sa.Column("trades_snapshot", postgresql.JSONB, nullable=False),
        sa.Column("final_metrics", postgresql.JSONB, nullable=False),
        sa.Column("session_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("session_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "archived_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    op.create_index(
        "idx_paper_trading_sessions_archived_at",
        "paper_trading_sessions",
        ["archived_at"],
    )


def downgrade() -> None:
    """Drop paper_trading_sessions table."""
    op.drop_index("idx_paper_trading_sessions_archived_at", table_name="paper_trading_sessions")
    op.drop_table("paper_trading_sessions")
