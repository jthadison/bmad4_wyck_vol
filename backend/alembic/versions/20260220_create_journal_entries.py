"""create journal_entries table

Revision ID: 20260220_journal_entries
Revises: 20260219_final_merge
Create Date: 2026-02-20

Feature P2-8 (Trade Journal): Creates the journal_entries table for storing
trade journal entries with Wyckoff checklist, emotional state, and optional
linkage to campaigns and signals.

Table Structure:
- id: Primary key (UUID)
- user_id: Entry owner (UUID, indexed)
- campaign_id: Optional campaign link (UUID, nullable, indexed)
- signal_id: Optional signal link (UUID, nullable)
- symbol: Trading symbol (VARCHAR(20), indexed)
- entry_type: pre_trade / post_trade / observation (VARCHAR(20))
- notes: Full text notes (TEXT, nullable)
- emotional_state: Trader emotion tag (VARCHAR(20), nullable)
- wyckoff_checklist: 4-point criteria JSON (JSON, nullable)
- created_at, updated_at: Audit timestamps (TIMESTAMPTZ)

Indexes:
- idx_journal_entries_user_id: Fast lookup by user
- idx_journal_entries_symbol: Filter by symbol
- idx_journal_entries_created_at: Chronological ordering
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260220_journal_entries"
down_revision: Union[str, Sequence[str], None] = "20260219_final_merge"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create journal_entries table and indexes."""

    op.create_table(
        "journal_entries",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "campaign_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "signal_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "symbol",
            sa.String(20),
            nullable=False,
        ),
        sa.Column(
            "entry_type",
            sa.String(20),
            nullable=False,
            server_default="observation",
        ),
        sa.Column(
            "notes",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "emotional_state",
            sa.String(20),
            nullable=True,
            server_default="neutral",
        ),
        sa.Column(
            "wyckoff_checklist",
            sa.dialects.postgresql.JSON(),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    # Index for fast user-based lookups (most common access pattern)
    op.create_index(
        "idx_journal_entries_user_id",
        "journal_entries",
        ["user_id"],
        unique=False,
    )

    # Index for filtering entries by symbol
    op.create_index(
        "idx_journal_entries_symbol",
        "journal_entries",
        ["symbol"],
        unique=False,
    )

    # Index for chronological ordering / date-range queries
    op.create_index(
        "idx_journal_entries_created_at",
        "journal_entries",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Remove journal_entries table and indexes."""

    op.drop_index("idx_journal_entries_created_at", table_name="journal_entries")
    op.drop_index("idx_journal_entries_symbol", table_name="journal_entries")
    op.drop_index("idx_journal_entries_user_id", table_name="journal_entries")

    op.drop_table("journal_entries")
