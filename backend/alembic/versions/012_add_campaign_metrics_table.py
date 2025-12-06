"""Add Campaign Metrics Table (Story 9.6)

Revision ID: 012
Revises: 011
Create Date: 2025-12-06

This migration creates the campaign_metrics table for storing performance
analytics calculated from completed campaigns.

Changes:
--------
1. Create campaign_metrics table:
   - Campaign-level metrics (total_return_pct, total_r_achieved, win_rate, max_drawdown)
   - Position-level aggregates (total_positions, winning_positions, losing_positions)
   - Comparison metrics (expected vs actual Jump target achievement)
   - Phase-specific metrics (Phase C vs Phase D performance - AC #11)
   - Metadata (calculation_timestamp, completed_at)

2. Add indexes for performance:
   - campaign_id (UNIQUE - one metrics record per campaign)
   - completed_at DESC (for historical queries)
   - Unique constraint on (campaign_id, calculation_timestamp)

CRITICAL: All financial data uses NUMERIC(18,8) for prices/PnL
CRITICAL: All percentages use NUMERIC(5,2) or NUMERIC(18,8)
CRITICAL: All timestamps use TIMESTAMPTZ (timezone-aware, UTC)
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create campaign_metrics table for performance tracking.

    Order of operations:
    1. Create campaign_metrics table
    2. Create indexes for performance
    """

    # 1. Create campaign_metrics table
    op.create_table(
        "campaign_metrics",
        # Campaign identification
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            comment="Campaign metrics identifier",
        ),
        sa.Column(
            "campaign_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("campaigns.id", ondelete="CASCADE"),
            nullable=False,
            comment="Campaign identifier (FK to campaigns.id)",
        ),
        sa.Column(
            "symbol",
            sa.VARCHAR(20),
            nullable=False,
            comment="Trading symbol",
        ),
        # Campaign-level metrics
        sa.Column(
            "total_return_pct",
            sa.NUMERIC(18, 8),
            nullable=False,
            comment="Total campaign return percentage",
        ),
        sa.Column(
            "total_r_achieved",
            sa.NUMERIC(8, 4),
            nullable=False,
            comment="Sum of R-multiples across all positions",
        ),
        sa.Column(
            "duration_days",
            sa.INTEGER,
            nullable=False,
            comment="Campaign duration in days",
        ),
        sa.Column(
            "max_drawdown",
            sa.NUMERIC(18, 8),
            nullable=False,
            comment="Maximum drawdown percentage",
        ),
        sa.Column(
            "total_positions",
            sa.INTEGER,
            nullable=False,
            comment="Total number of positions",
        ),
        sa.Column(
            "winning_positions",
            sa.INTEGER,
            nullable=False,
            comment="Number of winning positions",
        ),
        sa.Column(
            "losing_positions",
            sa.INTEGER,
            nullable=False,
            comment="Number of losing positions",
        ),
        sa.Column(
            "win_rate",
            sa.NUMERIC(5, 2),
            nullable=False,
            comment="Percentage of winning positions (0.00 - 100.00)",
        ),
        sa.Column(
            "average_entry_price",
            sa.NUMERIC(18, 8),
            nullable=False,
            comment="Weighted average entry price",
        ),
        sa.Column(
            "average_exit_price",
            sa.NUMERIC(18, 8),
            nullable=False,
            comment="Weighted average exit price",
        ),
        # Comparison metrics (expected vs actual)
        sa.Column(
            "expected_jump_target",
            sa.NUMERIC(18, 8),
            nullable=True,
            comment="Projected Jump target from trading range",
        ),
        sa.Column(
            "actual_high_reached",
            sa.NUMERIC(18, 8),
            nullable=True,
            comment="Highest price reached during campaign",
        ),
        sa.Column(
            "target_achievement_pct",
            sa.NUMERIC(7, 2),
            nullable=True,
            comment="Percentage of Jump target achieved",
        ),
        sa.Column(
            "expected_r",
            sa.NUMERIC(8, 4),
            nullable=True,
            comment="Expected R-multiple based on Jump target",
        ),
        sa.Column(
            "actual_r_achieved",
            sa.NUMERIC(8, 4),
            nullable=True,
            comment="Actual R-multiple achieved (same as total_r_achieved)",
        ),
        # Phase-specific metrics (AC #11) - Wyckoff methodology validation
        sa.Column(
            "phase_c_avg_r",
            sa.NUMERIC(8, 4),
            nullable=True,
            comment="Average R-multiple for Phase C entries (SPRING + LPS)",
        ),
        sa.Column(
            "phase_d_avg_r",
            sa.NUMERIC(8, 4),
            nullable=True,
            comment="Average R-multiple for Phase D entries (SOS)",
        ),
        sa.Column(
            "phase_c_positions",
            sa.INTEGER,
            nullable=False,
            server_default="0",
            comment="Count of Phase C entries (SPRING + LPS)",
        ),
        sa.Column(
            "phase_d_positions",
            sa.INTEGER,
            nullable=False,
            server_default="0",
            comment="Count of Phase D entries (SOS)",
        ),
        sa.Column(
            "phase_c_win_rate",
            sa.NUMERIC(5, 2),
            nullable=True,
            comment="Win rate for Phase C entries",
        ),
        sa.Column(
            "phase_d_win_rate",
            sa.NUMERIC(5, 2),
            nullable=True,
            comment="Win rate for Phase D entries",
        ),
        # Metadata
        sa.Column(
            "calculation_timestamp",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            comment="When metrics were calculated (UTC)",
        ),
        sa.Column(
            "completed_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            comment="When campaign was completed (UTC)",
        ),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            comment="Record creation timestamp (UTC)",
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            comment="Record last update timestamp (UTC)",
        ),
    )

    # 2. Create indexes for performance
    # Index on campaign_id for fast lookups (UNIQUE - one metrics record per campaign)
    op.create_index(
        "ix_campaign_metrics_campaign_id",
        "campaign_metrics",
        ["campaign_id"],
        unique=True,
    )

    # Index on completed_at for historical queries (ordered DESC for recent campaigns first)
    op.create_index(
        "ix_campaign_metrics_completed_at",
        "campaign_metrics",
        ["completed_at"],
        postgresql_using="btree",
    )

    # Index on symbol for filtering by trading symbol
    op.create_index(
        "ix_campaign_metrics_symbol",
        "campaign_metrics",
        ["symbol"],
    )

    # Composite index for filtered historical queries (symbol + completed_at)
    op.create_index(
        "ix_campaign_metrics_symbol_completed_at",
        "campaign_metrics",
        ["symbol", "completed_at"],
    )

    # Unique constraint on (campaign_id, calculation_timestamp) to prevent duplicates
    op.create_unique_constraint(
        "uq_campaign_metrics_campaign_calculation",
        "campaign_metrics",
        ["campaign_id", "calculation_timestamp"],
    )


def downgrade() -> None:
    """
    Drop campaign_metrics table and indexes.

    Order of operations:
    1. Drop unique constraint
    2. Drop indexes
    3. Drop campaign_metrics table
    """

    # 1. Drop unique constraint
    op.drop_constraint(
        "uq_campaign_metrics_campaign_calculation",
        "campaign_metrics",
        type_="unique",
    )

    # 2. Drop indexes
    op.drop_index("ix_campaign_metrics_symbol_completed_at", table_name="campaign_metrics")
    op.drop_index("ix_campaign_metrics_symbol", table_name="campaign_metrics")
    op.drop_index("ix_campaign_metrics_completed_at", table_name="campaign_metrics")
    op.drop_index("ix_campaign_metrics_campaign_id", table_name="campaign_metrics")

    # 3. Drop campaign_metrics table
    op.drop_table("campaign_metrics")
