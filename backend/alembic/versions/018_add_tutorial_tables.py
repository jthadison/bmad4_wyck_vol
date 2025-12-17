"""Add tutorial tables (Story 11.8b - Task 3)

Revision ID: 018_add_tutorial_tables
Revises: 017_add_help_system_tables
Create Date: 2025-12-17

This migration creates the tutorial system tables for interactive step-by-step tutorials.

Tables Created:
---------------
1. tutorials:
   - Tutorial metadata with difficulty and estimated time
   - Steps stored as JSONB array
   - Completion count tracking

2. tutorial_progress (OPTIONAL for future enhancement):
   - User progress tracking per tutorial
   - Current step and completion status
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON, TIMESTAMP, UUID

from alembic import op

# revision identifiers, used by Alembic.
revision = "018_add_tutorial_tables"
down_revision = "017_add_help_system_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create tutorial tables."""

    # ============================================================================
    # Table 1: tutorials
    # ============================================================================

    op.create_table(
        "tutorials",
        # Primary key
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        # Tutorial identification
        sa.Column("slug", sa.String(200), unique=True, nullable=False, index=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        # Tutorial metadata
        sa.Column("difficulty", sa.String(20), nullable=False),
        sa.Column("estimated_time_minutes", sa.Integer, nullable=False),
        # Steps as JSONB array (list of TutorialStep objects)
        sa.Column("steps", JSON, nullable=False),
        # Classification
        sa.Column("tags", JSON, nullable=False, server_default="[]"),
        # Timestamps
        sa.Column(
            "last_updated",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "created_at",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        # Analytics
        sa.Column("completion_count", sa.Integer, nullable=False, server_default="0"),
        # Check constraints
        sa.CheckConstraint(
            "difficulty IN ('BEGINNER', 'INTERMEDIATE', 'ADVANCED')",
            name="chk_tutorial_difficulty",
        ),
        sa.CheckConstraint(
            "estimated_time_minutes > 0 AND estimated_time_minutes <= 120",
            name="chk_estimated_time_range",
        ),
        sa.CheckConstraint("completion_count >= 0", name="chk_completion_count"),
    )

    # Create indexes
    op.create_index("idx_tutorials_difficulty", "tutorials", ["difficulty"])

    # ============================================================================
    # Table 2: tutorial_progress (OPTIONAL - for future user tracking)
    # ============================================================================
    # Note: This table is created but not used in MVP (Story 11.8b uses localStorage)
    # It's here for future enhancement when user authentication is implemented

    op.create_table(
        "tutorial_progress",
        # Primary key
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        # Foreign keys (user_id references users table if it exists)
        # Note: For MVP, this table is optional and not enforced
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "tutorial_id",
            UUID(as_uuid=True),
            nullable=False,
        ),
        # Progress tracking
        sa.Column("current_step", sa.Integer, nullable=False),
        sa.Column("completed", sa.Boolean, nullable=False, server_default="false"),
        # Timestamp
        sa.Column(
            "last_accessed",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        # Check constraints
        sa.CheckConstraint("current_step > 0", name="chk_current_step_positive"),
    )

    # Create foreign key to tutorials table
    op.create_foreign_key(
        "fk_tutorial_progress_tutorial",
        "tutorial_progress",
        "tutorials",
        ["tutorial_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Create indexes
    op.create_index("idx_tutorial_progress_user", "tutorial_progress", ["user_id"])
    op.create_index("idx_tutorial_progress_tutorial", "tutorial_progress", ["tutorial_id"])

    # Create unique constraint (one progress record per user per tutorial)
    op.create_index(
        "idx_tutorial_progress_user_tutorial_unique",
        "tutorial_progress",
        ["user_id", "tutorial_id"],
        unique=True,
    )


def downgrade() -> None:
    """Drop tutorial tables."""

    # Drop tables in reverse order
    op.drop_table("tutorial_progress")
    op.drop_table("tutorials")
