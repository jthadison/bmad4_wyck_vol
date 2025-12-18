"""Add Analytics Fields for Pattern Performance Dashboard

Revision ID: 014
Revises: 013_notifications
Create Date: 2025-12-12

This migration adds fields required for the Pattern Performance Dashboard (Story 11.9):

1. signals table:
   - exit_date: When trade was closed (TIMESTAMPTZ, nullable)
   - exit_price: Price at which trade was closed (NUMERIC(18,8), nullable)

2. patterns table:
   - vsa_events: JSONB column for VSA metrics (Task 6)
     Structure: {"no_demand": 3, "no_supply": 1, "stopping_volume": 2}
   - preliminary_events: JSONB column for PS/SC/AR/ST counts (Task 8)
     Structure: {"PS": 2, "SC": 1, "AR": 3, "ST": 1}

These fields enable:
- Win/loss calculation based on actual exit prices
- Performance analytics aggregations
- VSA event tracking for supply/demand analysis
- Preliminary event tracking for Wyckoff methodology validation

CRITICAL: All financial data uses NUMERIC(18,8) precision
CRITICAL: All timestamps use TIMESTAMPTZ (timezone-aware, UTC)
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "014"
down_revision = "013_notifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Add analytics fields to signals and patterns tables.
    """

    # Add exit tracking fields to signals table
    op.add_column(
        "signals",
        sa.Column(
            "exit_date",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
            comment="When trade was closed (UTC)",
        ),
    )
    op.add_column(
        "signals",
        sa.Column(
            "exit_price",
            sa.NUMERIC(precision=18, scale=8),
            nullable=True,
            comment="Price at which trade was closed",
        ),
    )

    # Add VSA events JSONB column to patterns table
    op.add_column(
        "patterns",
        sa.Column(
            "vsa_events",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="VSA event counts: {no_demand, no_supply, stopping_volume}",
        ),
    )

    # Add preliminary events JSONB column to patterns table
    op.add_column(
        "patterns",
        sa.Column(
            "preliminary_events",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Preliminary event counts: {PS, SC, AR, ST}",
        ),
    )

    # Add check constraint: exit_date and exit_price must both be NULL or both be NOT NULL
    op.create_check_constraint(
        "chk_exit_fields_together",
        "signals",
        "(exit_date IS NULL AND exit_price IS NULL) OR (exit_date IS NOT NULL AND exit_price IS NOT NULL)",
    )


def downgrade() -> None:
    """
    Remove analytics fields from signals and patterns tables.
    """

    # Drop check constraint first
    op.drop_constraint("chk_exit_fields_together", "signals", type_="check")

    # Drop columns from patterns table
    op.drop_column("patterns", "preliminary_events")
    op.drop_column("patterns", "vsa_events")

    # Drop columns from signals table
    op.drop_column("signals", "exit_price")
    op.drop_column("signals", "exit_date")
