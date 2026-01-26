"""create signal audit trail

Revision ID: 20260125_signal_audit_trail
Revises: 20260124_signal_approval_queue
Create Date: 2026-01-25

Story 19.11: Signal Audit Trail

This migration adds comprehensive audit trail capabilities for signals:
1. Extends signals table with lifecycle tracking fields
2. Creates signal_audit_log table for state transition history
3. Links trade outcomes from paper trading service

Key Features:
1. Lifecycle states: generated → pending → approved → executed → closed
2. Validation results persistence (5-stage validation chain)
3. Trade outcome tracking (P&L, R-multiple, exit reason)
4. Optimized indexes for querying and filtering

Indexes:
- idx_signals_query: Composite index for date range, symbol, pattern, status queries
- idx_signal_audit_signal: Fast lookup of audit entries by signal_id
- idx_signal_audit_time: Time-based audit queries
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260125_signal_audit_trail"
down_revision: Union[str, Sequence[str], None] = "20260124_signal_approval_queue"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add audit trail capabilities to signals.

    Changes to signals table:
    - lifecycle_state: Current state in lifecycle (VARCHAR(20))
    - validation_results: 5-stage validation chain results (JSONB)
    - trade_outcome: P&L and trade metrics when closed (JSONB)

    New signal_audit_log table:
    - Tracks all state transitions with timestamp
    - Captures user_id for approvals/rejections
    - Stores transition reason and metadata
    """

    # 1. Extend signals table
    op.add_column(
        "signals",
        sa.Column(
            "lifecycle_state",
            sa.String(20),
            nullable=False,
            server_default="generated",
        ),
    )

    op.add_column(
        "signals",
        sa.Column(
            "validation_results",
            postgresql.JSONB(),
            nullable=True,
        ),
    )

    op.add_column(
        "signals",
        sa.Column(
            "trade_outcome",
            postgresql.JSONB(),
            nullable=True,
        ),
    )

    # Add check constraint for valid lifecycle states
    op.create_check_constraint(
        "chk_signal_lifecycle_state",
        "signals",
        "lifecycle_state IN ('generated', 'pending', 'approved', 'rejected', 'expired', 'executed', 'closed', 'cancelled')",
    )

    # Create composite index for query optimization
    # Covers most common query pattern: date range + symbol + pattern + status
    op.create_index(
        "idx_signals_query",
        "signals",
        ["created_at", "symbol", "signal_type", "lifecycle_state"],
        unique=False,
    )

    # 2. Create signal_audit_log table
    op.create_table(
        "signal_audit_log",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "signal_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,  # Nullable for system-generated transitions
        ),
        sa.Column(
            "previous_state",
            sa.String(20),
            nullable=True,  # Null for initial "generated" state
        ),
        sa.Column(
            "new_state",
            sa.String(20),
            nullable=False,
        ),
        sa.Column(
            "transition_reason",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        # Foreign key to signals table
        sa.ForeignKeyConstraint(
            ["signal_id"],
            ["signals.id"],
            name="fk_signal_audit_signal",
            ondelete="CASCADE",
        ),
        # Foreign key to users table (nullable for system events)
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_signal_audit_user",
            ondelete="SET NULL",
        ),
    )

    # Index for fast lookup of all audit entries for a signal
    op.create_index(
        "idx_signal_audit_signal",
        "signal_audit_log",
        ["signal_id", "created_at"],
        unique=False,
    )

    # Index for time-based audit queries
    op.create_index(
        "idx_signal_audit_time",
        "signal_audit_log",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Remove signal audit trail capabilities."""

    # Drop audit log table and indexes
    op.drop_index("idx_signal_audit_time", table_name="signal_audit_log")
    op.drop_index("idx_signal_audit_signal", table_name="signal_audit_log")
    op.drop_table("signal_audit_log")

    # Drop signals query index
    op.drop_index("idx_signals_query", table_name="signals")

    # Drop check constraint
    op.drop_constraint("chk_signal_lifecycle_state", "signals", type_="check")

    # Remove columns from signals table
    op.drop_column("signals", "trade_outcome")
    op.drop_column("signals", "validation_results")
    op.drop_column("signals", "lifecycle_state")
