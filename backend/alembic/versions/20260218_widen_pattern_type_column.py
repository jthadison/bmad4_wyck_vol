"""widen pattern_type column from VARCHAR(10) to VARCHAR(20)

Revision ID: 20260218_widen_pattern_type
Revises: 20260218_signals_pattern_phase
Create Date: 2026-02-18

SPRING, SOS, LPS, UTAD are all <= 6 chars, but VARCHAR(10) is narrower
than the ORM String(20) declaration. Widen to String(20) to keep ORM and
schema in sync and avoid potential truncation if pattern type names grow.
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
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "signals",
        "pattern_type",
        type_=sa.String(10),
        existing_type=sa.String(20),
        nullable=True,
    )
