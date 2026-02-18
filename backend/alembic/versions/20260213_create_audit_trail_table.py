"""create audit trail table

Revision ID: 20260213_audit_trail
Revises: 20260209_add_paper_trading_config
Create Date: 2026-02-13

Task #2: Audit trail persistence for correlation overrides.

Creates a general-purpose audit_trail table for tracking manual overrides,
configuration changes, and compliance-relevant actions. Initial use case
is correlation limit overrides (AC 10 from Story 7.5).

Key Features:
1. General-purpose: event_type + entity_type + entity_id pattern
2. JSONB metadata for flexible context storage
3. Indexed for common query patterns (entity lookup, time range, event type, actor)
4. correlation_id for cross-system tracing
5. Tamper-proof: PostgreSQL rules prevent UPDATE and DELETE
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260213_audit_trail"
down_revision: Union[str, Sequence[str], None] = "20260209_add_paper_trading_config"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create audit_trail table with indexes."""
    op.create_table(
        "audit_trail",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "event_type",
            sa.String(50),
            nullable=False,
            comment="Event category: CORRELATION_OVERRIDE, CONFIG_CHANGE, etc.",
        ),
        sa.Column(
            "entity_type",
            sa.String(50),
            nullable=False,
            comment="Entity being acted on: SIGNAL, CAMPAIGN, CONFIG, etc.",
        ),
        sa.Column(
            "entity_id",
            sa.String(100),
            nullable=False,
            comment="ID of the entity (UUID as string or other identifier)",
        ),
        sa.Column(
            "actor",
            sa.String(255),
            nullable=False,
            comment="Who performed the action (user email, system ID, etc.)",
        ),
        sa.Column(
            "action",
            sa.Text(),
            nullable=False,
            comment="Human-readable description of the action taken",
        ),
        sa.Column(
            "correlation_id",
            sa.String(100),
            nullable=True,
            comment="Correlation ID for cross-system tracing (optional)",
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default="{}",
            comment="Additional context: reason, correlation details, before/after values",
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    # Index for looking up audit entries by entity
    op.create_index(
        "idx_audit_trail_entity",
        "audit_trail",
        ["entity_type", "entity_id"],
    )

    # Index for time-range queries
    op.create_index(
        "idx_audit_trail_created_at",
        "audit_trail",
        ["created_at"],
    )

    # Index for filtering by event type
    op.create_index(
        "idx_audit_trail_event_type",
        "audit_trail",
        ["event_type"],
    )

    # Composite index for common query: event_type + time range
    op.create_index(
        "idx_audit_trail_event_type_created_at",
        "audit_trail",
        ["event_type", "created_at"],
    )

    # Index for filtering by actor (approver)
    op.create_index(
        "idx_audit_trail_actor",
        "audit_trail",
        ["actor"],
    )

    # Index for correlation_id tracing
    op.create_index(
        "idx_audit_trail_correlation_id",
        "audit_trail",
        ["correlation_id"],
        postgresql_where=sa.text("correlation_id IS NOT NULL"),
    )

    # Tamper-proof: prevent UPDATE and DELETE on audit_trail
    op.execute("CREATE RULE audit_trail_no_update AS ON UPDATE TO audit_trail DO INSTEAD NOTHING;")
    op.execute("CREATE RULE audit_trail_no_delete AS ON DELETE TO audit_trail DO INSTEAD NOTHING;")


def downgrade() -> None:
    """Drop audit_trail table, indexes, and rules."""
    # Drop tamper-proof rules
    op.execute("DROP RULE IF EXISTS audit_trail_no_delete ON audit_trail;")
    op.execute("DROP RULE IF EXISTS audit_trail_no_update ON audit_trail;")

    # Drop indexes
    op.drop_index("idx_audit_trail_correlation_id", table_name="audit_trail")
    op.drop_index("idx_audit_trail_actor", table_name="audit_trail")
    op.drop_index("idx_audit_trail_event_type_created_at", table_name="audit_trail")
    op.drop_index("idx_audit_trail_event_type", table_name="audit_trail")
    op.drop_index("idx_audit_trail_created_at", table_name="audit_trail")
    op.drop_index("idx_audit_trail_entity", table_name="audit_trail")
    op.drop_table("audit_trail")
