"""add_symbols_no_data_to_scanner_history

Revision ID: 20260206_symbols_no_data
Revises: 20260130_scanner_tables
Create Date: 2026-02-06

Adds symbols_no_data column to scanner_history table to track
symbols that had no OHLCV data during a scan cycle, separately
from errors_count and symbols_scanned.
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260206_symbols_no_data"
down_revision: Union[str, Sequence[str], None] = "20260130_scanner_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add symbols_no_data column to scanner_history."""
    op.add_column(
        "scanner_history",
        sa.Column(
            "symbols_no_data",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    """Remove symbols_no_data column from scanner_history."""
    op.drop_column("scanner_history", "symbols_no_data")
