"""add_correlation_ids_to_scanner_history

Revision ID: 20260214_correlation_ids
Revises: 20260206_symbols_no_data
Create Date: 2026-02-14

Adds correlation_ids JSONB column to scanner_history table to track
which signals were generated during each scan cycle. Enables querying
"Which signals came from scan cycle X?" (Task #25).
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260214_correlation_ids"
down_revision: Union[str, Sequence[str], None] = "20260206_symbols_no_data"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add correlation_ids column to scanner_history."""
    op.add_column(
        "scanner_history",
        sa.Column(
            "correlation_ids",
            postgresql.JSONB(),
            nullable=True,  # Nullable for existing records
            server_default=sa.text("'[]'::jsonb"),  # Default to empty array
        ),
    )

    # Backfill existing rows with empty array (M-1: server_default only applies to new inserts)
    op.execute("UPDATE scanner_history SET correlation_ids = '[]'::jsonb WHERE correlation_ids IS NULL")


def downgrade() -> None:
    """Remove correlation_ids column from scanner_history."""
    op.drop_column("scanner_history", "correlation_ids")
