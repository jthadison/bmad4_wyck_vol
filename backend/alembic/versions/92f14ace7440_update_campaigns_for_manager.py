"""update_campaigns_for_manager

Revision ID: 92f14ace7440
Revises: 012
Create Date: 2025-12-06 17:56:57.780736

Story 9.7: CampaignManager Module Integration

Changes:
--------
1. Add entries JSONB field to campaigns table for EntryDetails tracking
   - Stores pattern entry metadata (SPRING/SOS/LPS) with entry_price, shares, risk_allocated
   - Format: {"SPRING": {...}, "SOS": {...}, "LPS": {...}}

2. Add version field for optimistic locking (concurrency control)
   - Prevents race conditions when multiple operations update same campaign
   - Incremented on each update, checked before write

CRITICAL: All financial data uses NUMERIC(18,8) for prices, NUMERIC(12,2) for amounts
CRITICAL: All timestamps use TIMESTAMPTZ (timezone-aware, UTC)
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "92f14ace7440"
down_revision: Union[str, Sequence[str], None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add entries JSONB field and version field to campaigns table.

    Order of operations:
    1. Add entries JSONB field (Story 9.7 AC #1)
    2. Add version field for optimistic locking (Story 9.7 AC #7)

    Note: These columns may already exist from the initial schema.
    This migration is idempotent - it checks before adding.
    """
    # Get connection to check existing columns
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = {col["name"] for col in inspector.get_columns("campaigns")}

    # ==========================================================================
    # 1. Add entries JSONB field for EntryDetails tracking (if not exists)
    # ==========================================================================
    if "entries" not in existing_columns:
        op.add_column(
            "campaigns",
            sa.Column(
                "entries",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default="'{}'::jsonb",
                comment="Entry details by pattern type (SPRING/SOS/LPS mapping)",
            ),
        )

    # ==========================================================================
    # 2. Add version field for optimistic locking (if not exists)
    # ==========================================================================
    if "version" not in existing_columns:
        op.add_column(
            "campaigns",
            sa.Column(
                "version",
                sa.Integer(),
                nullable=False,
                server_default="1",
                comment="Optimistic locking version (increment on update)",
            ),
        )


def downgrade() -> None:
    """
    Rollback CampaignManager schema changes.

    WARNING: This will delete all entries data!

    Note: Only drops columns if they exist (idempotent).
    """
    # Get connection to check existing columns
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = {col["name"] for col in inspector.get_columns("campaigns")}

    if "version" in existing_columns:
        op.drop_column("campaigns", "version")
    if "entries" in existing_columns:
        op.drop_column("campaigns", "entries")
