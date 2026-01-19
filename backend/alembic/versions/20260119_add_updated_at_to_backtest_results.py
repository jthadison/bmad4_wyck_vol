"""add updated_at to backtest_results

Revision ID: 20260119_backtest_updated_at
Revises: 20260106_rejection_metadata
Create Date: 2026-01-19

Adds missing updated_at column to backtest_results table.
The SQLAlchemy model has this column but it was never added via migration.
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260119_backtest_updated_at"
down_revision: Union[str, Sequence[str], None] = "20260106_rejection_metadata"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add updated_at column to backtest_results table."""
    op.add_column(
        "backtest_results",
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Remove updated_at column from backtest_results table."""
    op.drop_column("backtest_results", "updated_at")
