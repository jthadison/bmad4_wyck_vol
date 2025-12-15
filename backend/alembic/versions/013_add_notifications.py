"""
Add notifications system tables.

Revision ID: 013_notifications
Revises: 92f14ace7440
Create Date: 2025-12-14

Creates tables for multi-channel notification system:
- notifications: User notification records
- notification_preferences: User preferences for notification delivery
- push_subscriptions: Web Push subscription data

Story: 11.6 - Notification & Alert System
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# Revision identifiers
revision = "013_notifications"
down_revision = "92f14ace7440"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create notification system tables with indexes."""

    # Create notifications table
    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("notification_type", sa.String(20), nullable=False),
        sa.Column("priority", sa.String(10), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("message", sa.String(1000), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("read", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "notification_type IN ('signal_generated', 'risk_warning', 'emergency_exit', 'system_error')",
            name="chk_notification_type",
        ),
        sa.CheckConstraint(
            "priority IN ('info', 'warning', 'critical')",
            name="chk_notification_priority",
        ),
    )

    # Create indexes for notifications
    op.create_index(
        "idx_notifications_user_read",
        "notifications",
        ["user_id", "read", sa.text("created_at DESC")],
    )
    op.create_index(
        "idx_notifications_type",
        "notifications",
        ["notification_type"],
    )

    # Create notification_preferences table
    op.create_table(
        "notification_preferences",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("preferences", sa.JSON(), nullable=False),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

    # Create push_subscriptions table
    op.create_table(
        "push_subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("p256dh_key", sa.Text(), nullable=False),
        sa.Column("auth_key", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

    # Create unique constraint on user_id + endpoint (one subscription per browser)
    op.create_index(
        "idx_push_subscriptions_user_endpoint",
        "push_subscriptions",
        ["user_id", "endpoint"],
        unique=True,
    )


def downgrade() -> None:
    """Drop notification system tables."""

    # Drop tables in reverse order
    op.drop_index("idx_push_subscriptions_user_endpoint", table_name="push_subscriptions")
    op.drop_table("push_subscriptions")

    op.drop_table("notification_preferences")

    op.drop_index("idx_notifications_type", table_name="notifications")
    op.drop_index("idx_notifications_user_read", table_name="notifications")
    op.drop_table("notifications")
