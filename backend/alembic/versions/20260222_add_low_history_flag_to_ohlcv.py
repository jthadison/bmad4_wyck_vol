"""add low_history_flag to ohlcv_bars

Revision ID: 20260222_add_low_history_flag_to_ohlcv
Revises: 20260220_create_price_alerts
Create Date: 2026-02-22 00:00:00.000000

Story 25.14: Adds low_history_flag column to ohlcv_bars table.
Informational flag set True when volume/spread ratios are computed from
fewer than 20 historical bars (e.g., early session, new symbol).
Never blocks signal generation — downstream consumers may optionally
discount confidence on flagged bars.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260222_add_low_history_flag_to_ohlcv"
down_revision: str | None = "20260220_create_price_alerts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add low_history_flag column to ohlcv_bars table."""
    op.add_column(
        "ohlcv_bars",
        sa.Column(
            "low_history_flag",
            sa.Boolean(),
            nullable=True,
            comment="True if ratio computed from < 20 bars (informational only)",
        ),
    )


def downgrade() -> None:
    """Remove low_history_flag column from ohlcv_bars table."""
    op.drop_column("ohlcv_bars", "low_history_flag")
