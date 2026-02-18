"""add audit trail fields and peak equity

Revision ID: 20260218_audit_peak_equity
Revises: 20260213_audit_trail
Create Date: 2026-02-18

Story 23.8a AC2: Add pattern_type, confidence_score, signal_source to
paper_trades and paper_positions for full audit trail.
Also adds peak_equity to paper_accounts for drawdown tracking.
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260218_audit_peak_equity"
down_revision: Union[str, Sequence[str]] = "20260213_audit_trail"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # paper_trades: audit trail fields
    op.add_column(
        "paper_trades",
        sa.Column("pattern_type", sa.String(50), nullable=True),
    )
    op.add_column(
        "paper_trades",
        sa.Column("confidence_score", sa.DECIMAL(precision=10, scale=8), nullable=True),
    )
    op.add_column(
        "paper_trades",
        sa.Column("signal_source", sa.String(100), nullable=True),
    )

    # paper_positions: audit trail fields
    op.add_column(
        "paper_positions",
        sa.Column("pattern_type", sa.String(50), nullable=True),
    )
    op.add_column(
        "paper_positions",
        sa.Column("confidence_score", sa.DECIMAL(precision=10, scale=8), nullable=True),
    )
    op.add_column(
        "paper_positions",
        sa.Column("signal_source", sa.String(100), nullable=True),
    )

    # paper_accounts: peak equity for drawdown tracking
    op.add_column(
        "paper_accounts",
        sa.Column(
            "peak_equity",
            sa.DECIMAL(precision=20, scale=8),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("paper_accounts", "peak_equity")

    op.drop_column("paper_positions", "signal_source")
    op.drop_column("paper_positions", "confidence_score")
    op.drop_column("paper_positions", "pattern_type")

    op.drop_column("paper_trades", "signal_source")
    op.drop_column("paper_trades", "confidence_score")
    op.drop_column("paper_trades", "pattern_type")
