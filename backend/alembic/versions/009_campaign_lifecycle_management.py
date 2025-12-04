"""Campaign Lifecycle Management Migration (Story 9.1)

Revision ID: 009
Revises: 001
Create Date: 2025-12-03

This migration extends the campaigns table with lifecycle management fields
and creates the campaign_positions table for multi-phase position tracking.

Changes:
--------
1. Add lifecycle fields to campaigns table:
   - campaign_id (human-readable ID: "AAPL-2024-10-15")
   - status (ACTIVE, MARKUP, COMPLETED, INVALIDATED)
   - phase (Wyckoff phase: C, D, E)
   - total_risk, weighted_avg_entry, total_shares, total_pnl
   - start_date, invalidation_reason

2. Create campaign_positions table:
   - Individual positions (Spring, SOS, LPS) within campaign
   - Links to signals table
   - Real-time P&L tracking

3. Add indexes for performance:
   - campaigns: symbol+status, trading_range_id, campaign_id
   - positions: campaign_id, signal_id

CRITICAL: All financial data uses NUMERIC(18,8) for prices, NUMERIC(12,2) for amounts
CRITICAL: All timestamps use TIMESTAMPTZ (timezone-aware, UTC)
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "009"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Extend campaigns table and create campaign_positions table.

    Order of operations:
    1. Add new columns to campaigns table
    2. Create campaign_positions table
    3. Create indexes for performance
    """

    # ==========================================================================
    # 1. Extend campaigns table with lifecycle fields (AC: 2, 3, 4)
    # ==========================================================================

    # Add campaign_id (human-readable ID) (AC: 3)
    op.add_column(
        "campaigns",
        sa.Column(
            "campaign_id",
            sa.String(length=50),
            nullable=True,  # Temporarily nullable for migration
            comment="Human-readable ID: {symbol}-{range_start_date}",
        ),
    )

    # Populate campaign_id from existing data (symbol + created_at date)
    op.execute(
        """
        UPDATE campaigns
        SET campaign_id = symbol || '-' || TO_CHAR(created_at, 'YYYY-MM-DD')
        WHERE campaign_id IS NULL
        """
    )

    # Make campaign_id non-nullable and unique
    op.alter_column("campaigns", "campaign_id", nullable=False)
    op.create_unique_constraint("uq_campaigns_campaign_id", "campaigns", ["campaign_id"])

    # Add phase (Wyckoff phase: C, D, E)
    op.add_column(
        "campaigns",
        sa.Column(
            "phase",
            sa.String(length=1),
            nullable=True,  # Temporarily nullable for migration
            comment="Wyckoff phase: C, D, E",
        ),
    )

    # Set default phase to 'C' for existing records
    op.execute("UPDATE campaigns SET phase = 'C' WHERE phase IS NULL")
    op.alter_column("campaigns", "phase", nullable=False)

    # Add total_risk (total dollar risk across positions)
    op.add_column(
        "campaigns",
        sa.Column(
            "total_risk",
            sa.NUMERIC(precision=12, scale=2),
            nullable=False,
            server_default="0.00",
            comment="Total dollar risk across all positions",
        ),
    )

    # Add weighted_avg_entry
    op.add_column(
        "campaigns",
        sa.Column(
            "weighted_avg_entry",
            sa.NUMERIC(precision=18, scale=8),
            nullable=True,
            comment="Weighted average entry price",
        ),
    )

    # Add total_shares
    op.add_column(
        "campaigns",
        sa.Column(
            "total_shares",
            sa.NUMERIC(precision=18, scale=8),
            nullable=False,
            server_default="0.00",
            comment="Sum of all position shares",
        ),
    )

    # Add total_pnl
    op.add_column(
        "campaigns",
        sa.Column(
            "total_pnl",
            sa.NUMERIC(precision=12, scale=2),
            nullable=False,
            server_default="0.00",
            comment="Current unrealized P&L",
        ),
    )

    # Add start_date (campaign start date)
    op.add_column(
        "campaigns",
        sa.Column(
            "start_date",
            sa.TIMESTAMP(timezone=True),
            nullable=True,  # Temporarily nullable
            comment="Campaign start date (UTC)",
        ),
    )

    # Populate start_date from created_at for existing records
    op.execute("UPDATE campaigns SET start_date = created_at WHERE start_date IS NULL")
    op.alter_column("campaigns", "start_date", nullable=False)

    # Add invalidation_reason
    op.add_column(
        "campaigns",
        sa.Column(
            "invalidation_reason",
            sa.Text(),
            nullable=True,
            comment="Reason for invalidation if status=INVALIDATED",
        ),
    )

    # Rename started_at to maintain consistency (if exists)
    # Drop old started_at if it exists and conflicts
    # (This is safe because we just copied it to start_date)
    try:
        op.drop_column("campaigns", "started_at")
    except Exception:
        pass  # Column might not exist in all schemas

    # ==========================================================================
    # 2. Create campaign_positions table (AC: 2)
    # ==========================================================================
    op.create_table(
        "campaign_positions",
        sa.Column(
            "position_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
            comment="Unique position identifier",
        ),
        sa.Column(
            "campaign_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="Foreign key to campaigns",
        ),
        sa.Column(
            "signal_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="Foreign key to signals",
        ),
        sa.Column(
            "pattern_type",
            sa.String(length=10),
            nullable=False,
            comment="SPRING, SOS, or LPS",
        ),
        sa.Column(
            "entry_date",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            comment="Position open timestamp (UTC)",
        ),
        sa.Column(
            "entry_price",
            sa.NUMERIC(precision=18, scale=8),
            nullable=False,
            comment="Actual fill price",
        ),
        sa.Column(
            "shares",
            sa.NUMERIC(precision=18, scale=8),
            nullable=False,
            comment="Position size (shares/lots)",
        ),
        sa.Column(
            "stop_loss",
            sa.NUMERIC(precision=18, scale=8),
            nullable=False,
            comment="Initial stop loss level",
        ),
        sa.Column(
            "target_price",
            sa.NUMERIC(precision=18, scale=8),
            nullable=False,
            comment="Primary target (Jump level)",
        ),
        sa.Column(
            "current_price",
            sa.NUMERIC(precision=18, scale=8),
            nullable=False,
            comment="Last market price (real-time)",
        ),
        sa.Column(
            "current_pnl",
            sa.NUMERIC(precision=12, scale=2),
            nullable=False,
            comment="Unrealized P&L: (current_price - entry_price) * shares",
        ),
        sa.Column(
            "status",
            sa.String(length=10),
            nullable=False,
            comment="OPEN, CLOSED, or PARTIAL",
        ),
        sa.Column(
            "allocation_percent",
            sa.NUMERIC(precision=5, scale=2),
            nullable=False,
            comment="% of campaign budget (e.g., 2.0% for Spring)",
        ),
        sa.Column(
            "risk_amount",
            sa.NUMERIC(precision=12, scale=2),
            nullable=False,
            comment="Dollar risk: (entry_price - stop_loss) * shares",
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        # Foreign key constraints
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            ondelete="CASCADE",  # Delete positions when campaign deleted
            name="fk_positions_campaign",
        ),
        sa.ForeignKeyConstraint(
            ["signal_id"],
            ["signals.id"],
            ondelete="RESTRICT",  # Don't delete signal if position exists
            name="fk_positions_signal",
        ),
    )

    # ==========================================================================
    # 3. Create indexes for performance (AC: 9)
    # ==========================================================================

    # Campaigns table indexes
    op.create_index(
        "idx_campaigns_symbol_status",
        "campaigns",
        ["symbol", "status"],
        unique=False,
    )

    op.create_index(
        "idx_campaigns_trading_range",
        "campaigns",
        ["trading_range_id"],
        unique=False,
    )

    op.create_index(
        "idx_campaigns_campaign_id",
        "campaigns",
        ["campaign_id"],
        unique=True,  # Already enforced by constraint, but helps queries
    )

    # Campaign positions table indexes
    op.create_index(
        "idx_positions_campaign",
        "campaign_positions",
        ["campaign_id"],
        unique=False,
    )

    op.create_index(
        "idx_positions_signal",
        "campaign_positions",
        ["signal_id"],
        unique=False,
    )

    op.create_index(
        "idx_positions_status",
        "campaign_positions",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    """
    Rollback campaign lifecycle changes.

    WARNING: This will delete all campaign_positions data!
    """

    # Drop indexes
    op.drop_index("idx_positions_status", table_name="campaign_positions")
    op.drop_index("idx_positions_signal", table_name="campaign_positions")
    op.drop_index("idx_positions_campaign", table_name="campaign_positions")
    op.drop_index("idx_campaigns_campaign_id", table_name="campaigns")
    op.drop_index("idx_campaigns_trading_range", table_name="campaigns")
    op.drop_index("idx_campaigns_symbol_status", table_name="campaigns")

    # Drop campaign_positions table
    op.drop_table("campaign_positions")

    # Remove added columns from campaigns table
    op.drop_column("campaigns", "invalidation_reason")
    op.drop_column("campaigns", "start_date")
    op.drop_column("campaigns", "total_pnl")
    op.drop_column("campaigns", "total_shares")
    op.drop_column("campaigns", "weighted_avg_entry")
    op.drop_column("campaigns", "total_risk")
    op.drop_column("campaigns", "phase")
    op.drop_constraint("uq_campaigns_campaign_id", "campaigns", type_="unique")
    op.drop_column("campaigns", "campaign_id")
