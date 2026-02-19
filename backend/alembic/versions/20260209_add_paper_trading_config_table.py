"""add_paper_trading_config_table

Revision ID: 20260209_paper_cfg
Revises: 20260209_paper_sessions
Create Date: 2026-02-09

Story 23.8a: Add paper_trading_configs table for settings persistence.
Stores user-customizable paper trading simulation parameters.
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260209_paper_cfg"
down_revision: Union[str, Sequence[str], None] = "20260209_paper_sessions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create paper_trading_configs table."""
    op.create_table(
        "paper_trading_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("starting_capital", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("commission_per_share", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("slippage_percentage", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("use_realistic_fills", sa.Boolean(), nullable=False, server_default="true"),
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


def downgrade() -> None:
    """Drop paper_trading_configs table."""
    op.drop_table("paper_trading_configs")
