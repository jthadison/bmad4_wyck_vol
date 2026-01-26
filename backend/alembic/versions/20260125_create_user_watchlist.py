"""create user watchlist table

Revision ID: 20260125_user_watchlist
Revises: 20260125_signal_audit_trail
Create Date: 2026-01-25

Story 19.12: Watchlist Management Backend

This migration creates the user_watchlist table for symbol monitoring:
1. Composite primary key (user_id, symbol)
2. Priority levels for signal filtering
3. Optional minimum confidence threshold
4. Enable/disable per symbol

Key Features:
1. Max 100 symbols per user (enforced in application layer)
2. Default watchlist initialization: AAPL, TSLA, SPY, QQQ, NVDA, MSFT, AMZN
3. Subscription sync with Alpaca market data feed
4. Symbol validation against Alpaca asset list

Indexes:
- Primary key covers (user_id, symbol) queries
- idx_watchlist_user_enabled: Fast lookup of enabled symbols per user
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260125_user_watchlist"
down_revision: Union[str, Sequence[str], None] = "20260125_signal_audit_trail"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create user_watchlist table for symbol monitoring.

    Table Schema:
    - user_id: UUID (FK to users.id, cascade delete)
    - symbol: VARCHAR(10)
    - priority: VARCHAR(10) - low/medium/high
    - min_confidence: NUMERIC(5,2) - optional filter
    - enabled: BOOLEAN - active monitoring flag
    - created_at: TIMESTAMP WITH TIME ZONE
    - updated_at: TIMESTAMP WITH TIME ZONE

    Primary Key: (user_id, symbol)
    """

    op.create_table(
        "user_watchlist",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "symbol",
            sa.String(10),
            nullable=False,
        ),
        sa.Column(
            "priority",
            sa.String(10),
            nullable=False,
            server_default="medium",
        ),
        sa.Column(
            "min_confidence",
            sa.Numeric(5, 2),
            nullable=True,
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
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
        # Composite primary key
        sa.PrimaryKeyConstraint("user_id", "symbol", name="pk_user_watchlist"),
        # Foreign key to users table
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_watchlist_user",
            ondelete="CASCADE",
        ),
        # Check constraint for priority values
        sa.CheckConstraint(
            "priority IN ('low', 'medium', 'high')",
            name="chk_watchlist_priority",
        ),
        # Check constraint for min_confidence range
        sa.CheckConstraint(
            "min_confidence IS NULL OR (min_confidence >= 0 AND min_confidence <= 100)",
            name="chk_watchlist_min_confidence",
        ),
    )

    # Index for fast lookup of enabled symbols per user
    op.create_index(
        "idx_watchlist_user_enabled",
        "user_watchlist",
        ["user_id", "enabled"],
        unique=False,
    )


def downgrade() -> None:
    """Remove user_watchlist table."""

    # Drop index
    op.drop_index("idx_watchlist_user_enabled", table_name="user_watchlist")

    # Drop table
    op.drop_table("user_watchlist")
