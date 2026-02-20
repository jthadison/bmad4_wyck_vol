"""create price_alerts table

Revision ID: 20260220_create_price_alerts
Revises: 20260219_final_merge
Create Date: 2026-02-20 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260220_create_price_alerts"
down_revision: str | None = "20260219_final_merge"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create price_alerts table for user Wyckoff price alert system (Feature P2-5)."""
    op.create_table(
        "price_alerts",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("alert_type", sa.String(20), nullable=False),
        sa.Column("price_level", sa.dialects.postgresql.NUMERIC(18, 8), nullable=True),
        sa.Column("direction", sa.String(10), nullable=True),
        sa.Column("wyckoff_level_type", sa.String(20), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("triggered_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint(
            "alert_type IN ('price_level', 'creek', 'ice', 'spring', 'phase_change')",
            name="chk_price_alert_type",
        ),
        sa.CheckConstraint(
            "direction IS NULL OR direction IN ('above', 'below')",
            name="chk_price_alert_direction",
        ),
    )
    op.create_index(
        "idx_price_alerts_user_active",
        "price_alerts",
        ["user_id", "is_active"],
    )
    op.create_index(
        "idx_price_alerts_symbol",
        "price_alerts",
        ["symbol"],
    )


def downgrade() -> None:
    """Drop price_alerts table."""
    op.drop_index("idx_price_alerts_symbol", table_name="price_alerts")
    op.drop_index("idx_price_alerts_user_active", table_name="price_alerts")
    op.drop_table("price_alerts")
