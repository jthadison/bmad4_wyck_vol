"""add_walk_forward_tables

Revision ID: 021_add_walk_forward_tables
Revises: 280de7e8b909
Create Date: 2025-12-20 18:00:00.000000

Story 12.4 Task 11: Create walk_forward_results table for walk-forward
validation testing.

Changes:
- Create walk_forward_results table with JSONB columns for windows, config, stats
- Add indexes for query optimization (walk_forward_id, created_at)
- Support full walk-forward test result persistence
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "021_add_walk_forward_tables"
down_revision: Union[str, Sequence[str], None] = "280de7e8b909"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create walk_forward_results table for Story 12.4.

    AC11 Subtask 11.2-11.4: Create table with JSONB columns and indexes.
    """
    op.create_table(
        "walk_forward_results",
        # Primary key
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        # Walk-forward test identification
        sa.Column(
            "walk_forward_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            unique=True,
        ),
        # Configuration (JSONB)
        sa.Column("config", postgresql.JSONB, nullable=False),
        # Validation windows (JSONB - list of ValidationWindow objects)
        sa.Column("windows", postgresql.JSONB, nullable=False, server_default="[]"),
        # Summary statistics (JSONB)
        sa.Column("summary_statistics", postgresql.JSONB, nullable=False, server_default="{}"),
        # Stability score (coefficient of variation)
        sa.Column("stability_score", sa.NUMERIC(6, 4), nullable=False, server_default="0.0"),
        # Degradation windows (JSONB - list of window numbers)
        sa.Column("degradation_windows", postgresql.JSONB, nullable=False, server_default="[]"),
        # Statistical significance (JSONB - p-values dict)
        sa.Column(
            "statistical_significance", postgresql.JSONB, nullable=False, server_default="{}"
        ),
        # Chart data (JSONB - optional)
        sa.Column("chart_data", postgresql.JSONB, nullable=True),
        # Execution metadata
        sa.Column(
            "total_execution_time_seconds",
            sa.NUMERIC(10, 4),
            nullable=False,
            server_default="0.0",
        ),
        sa.Column(
            "avg_window_execution_time_seconds",
            sa.NUMERIC(10, 4),
            nullable=False,
            server_default="0.0",
        ),
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # Add indexes for query performance (AC11 Subtask 11.3)
    op.create_index(
        "ix_walk_forward_results_walk_forward_id",
        "walk_forward_results",
        ["walk_forward_id"],
        unique=True,
    )
    op.create_index(
        "ix_walk_forward_results_created_at",
        "walk_forward_results",
        ["created_at"],
    )


def downgrade() -> None:
    """
    Drop walk_forward_results table (rollback Story 12.4 changes).
    """
    # Drop indexes
    op.drop_index("ix_walk_forward_results_created_at", table_name="walk_forward_results")
    op.drop_index("ix_walk_forward_results_walk_forward_id", table_name="walk_forward_results")

    # Drop table
    op.drop_table("walk_forward_results")
