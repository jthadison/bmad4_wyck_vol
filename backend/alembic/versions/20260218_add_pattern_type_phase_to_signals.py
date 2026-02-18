"""add pattern_type and phase columns to signals table

Revision ID: 20260218_signals_pattern_phase
Revises: 20260218_audit_peak_equity
Create Date: 2026-02-18

Adds pattern_type (VARCHAR(10)) and phase (VARCHAR(1)) columns to the
signals table so the repository can store and restore the actual Wyckoff
pattern type and phase instead of deriving them from signal_type.
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260218_signals_pattern_phase"
down_revision: Union[str, Sequence[str]] = "20260218_audit_peak_equity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "signals",
        sa.Column("pattern_type", sa.String(10), nullable=True),
    )
    op.add_column(
        "signals",
        sa.Column("phase", sa.String(1), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("signals", "phase")
    op.drop_column("signals", "pattern_type")
