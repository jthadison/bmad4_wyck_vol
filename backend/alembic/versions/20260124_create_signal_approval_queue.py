"""create signal_approval_queue table

Revision ID: 20260124_signal_approval_queue
Revises: 20260120_create_users
Create Date: 2026-01-24

Story 19.9: Signal Approval Queue Backend

This migration creates the signal_approval_queue table for the manual
approval workflow. Traders can review and approve/reject signals before
execution via paper trading service.

Key Features:
1. Queue entries with pending/approved/rejected/expired status
2. Configurable timeout (default 5 minutes)
3. Signal snapshot for point-in-time data preservation
4. Optimized indexes for user+status queries and expiration checks

Indexes:
- idx_signal_queue_user_status: Fast lookup by user and status
- idx_signal_queue_expires: Partial index for pending signals expiration
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260124_signal_approval_queue"
down_revision: Union[str, Sequence[str], None] = "20260120_create_users"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create signal_approval_queue table and indexes.

    Table Structure:
    - id: Primary key (UUID)
    - signal_id: Reference to the signal (UUID, indexed)
    - user_id: Owner of queue entry (UUID, indexed)
    - status: pending/approved/rejected/expired (VARCHAR(20))
    - submitted_at: When signal was queued (TIMESTAMPTZ)
    - expires_at: When signal expires (TIMESTAMPTZ)
    - approved_at: When approved (TIMESTAMPTZ, nullable)
    - approved_by: Who approved (UUID, nullable)
    - rejection_reason: Why rejected (TEXT, nullable)
    - signal_snapshot: Signal data at submission (JSONB)
    - created_at, updated_at: Standard audit timestamps
    """

    op.create_table(
        "signal_approval_queue",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "signal_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "submitted_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "expires_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "approved_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "approved_by",
            sa.dialects.postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "rejection_reason",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "signal_snapshot",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default="{}",
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
        # Check constraint for valid status values
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'expired')",
            name="chk_signal_queue_status",
        ),
        # Foreign key constraint for user ownership
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_signal_queue_user",
            ondelete="CASCADE",
        ),
    )

    # Composite index for user + status queries (most common access pattern)
    op.create_index(
        "idx_signal_queue_user_status",
        "signal_approval_queue",
        ["user_id", "status"],
        unique=False,
    )

    # Partial index for expiration checks (only pending signals)
    op.create_index(
        "idx_signal_queue_expires",
        "signal_approval_queue",
        ["status", "expires_at"],
        postgresql_where=sa.text("status = 'pending'"),
        unique=False,
    )


def downgrade() -> None:
    """Remove signal_approval_queue table and indexes."""

    # Drop indexes
    op.drop_index("idx_signal_queue_expires", table_name="signal_approval_queue")
    op.drop_index("idx_signal_queue_user_status", table_name="signal_approval_queue")

    # Drop table
    op.drop_table("signal_approval_queue")
