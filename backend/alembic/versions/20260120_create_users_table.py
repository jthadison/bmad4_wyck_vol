"""create users table

Revision ID: 20260120_create_users
Revises: 20260119_backtest_updated_at
Create Date: 2026-01-20

This migration creates the users table required by multiple downstream migrations:
- signal_approval_queue (FK user_id -> users.id)
- signal_audit_log (FK user_id -> users.id)
- user_watchlist (FK user_id -> users.id)
- auto_execution_config (FK user_id -> users.id)

The users table supports authentication and user preferences for the trading system.

CRITICAL: This migration MUST run before any migration that references users.id
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260120_create_users"
down_revision: Union[str, Sequence[str], None] = "20260119_backtest_updated_at"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create users table for authentication and user management.

    Table Schema:
    - id: UUID primary key
    - email: Unique email address
    - hashed_password: bcrypt hashed password
    - full_name: Display name (optional)
    - is_active: Account active flag
    - is_superuser: Admin privileges flag
    - created_at: Account creation timestamp
    - updated_at: Last modification timestamp
    """

    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "email",
            sa.String(255),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "hashed_password",
            sa.String(255),
            nullable=False,
        ),
        sa.Column(
            "full_name",
            sa.String(100),
            nullable=True,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "is_superuser",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
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

    # Index on email for fast login lookups
    op.create_index(
        "idx_users_email",
        "users",
        ["email"],
        unique=True,
    )

    # Index on active status for filtering
    op.create_index(
        "idx_users_active",
        "users",
        ["is_active"],
        unique=False,
    )


def downgrade() -> None:
    """Remove users table."""

    # Drop indexes
    op.drop_index("idx_users_active", table_name="users")
    op.drop_index("idx_users_email", table_name="users")

    # Drop table
    op.drop_table("users")
