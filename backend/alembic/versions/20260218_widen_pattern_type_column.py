"""widen pattern_type column from String(10) to String(20)

Revision ID: 20260218_widen_pattern_type
Revises: 20260218_signals_pattern_phase
Create Date: 2026-02-18

The initial migration added pattern_type as VARCHAR(10), which is too narrow
for future pattern type names. This widens it to VARCHAR(20) for safety.
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260218_widen_pattern_type"
down_revision: Union[str, Sequence[str]] = "20260218_signals_pattern_phase"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "signals",
        "pattern_type",
        type_=sa.String(20),
        existing_type=sa.String(10),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "signals",
        "pattern_type",
        type_=sa.String(10),
        existing_type=sa.String(20),
        existing_nullable=True,
    )
