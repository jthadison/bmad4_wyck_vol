"""Create allocation_plans table for BMAD allocation audit trail (Story 9.2)

Revision ID: 010
Revises: 009
Create Date: 2025-12-04

This migration creates the allocation_plans table to store BMAD position
allocation decisions for audit trail and campaign analysis.

Changes:
--------
1. Create allocation_plans table:
   - Tracks BMAD 40/30/30 allocation decisions
   - Records approved and rejected allocations
   - Captures rebalancing logic (when entries skipped)
   - Provides audit trail for campaign budget management

2. Add indexes for performance:
   - campaign_id (for audit trail queries)
   - signal_id (for signal->allocation lookups)
   - timestamp (for chronological ordering)

3. Add foreign key constraints:
   - campaign_id → campaigns (ON DELETE CASCADE)
   - signal_id → signals (ON DELETE RESTRICT - preserve audit trail)

CRITICAL: All financial data uses NUMERIC for precision (no FLOAT)
CRITICAL: All timestamps use TIMESTAMPTZ (timezone-aware, UTC)
CRITICAL: Percentages stored as decimals (0.40 for 40%, not 40.0)
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create allocation_plans table for BMAD allocation audit trail.

    Table stores both approved and rejected allocation plans to provide
    complete audit trail of campaign budget allocation decisions.
    """

    # ==========================================================================
    # 1. Create allocation_plans table (Story 9.2, AC: 6)
    # ==========================================================================

    op.create_table(
        "allocation_plans",
        # Primary key
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            comment="Unique allocation plan identifier",
        ),
        # Foreign keys
        sa.Column(
            "campaign_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="Campaign this allocation is for",
        ),
        sa.Column(
            "signal_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="Signal being allocated",
        ),
        # Pattern identification
        sa.Column(
            "pattern_type",
            sa.String(length=10),
            nullable=False,
            comment="SPRING | SOS | LPS",
        ),
        # BMAD allocation (FR23)
        sa.Column(
            "bmad_allocation_pct",
            sa.Numeric(precision=5, scale=4),
            nullable=False,
            comment="BMAD allocation percentage (0.4000 for 40%)",
        ),
        sa.Column(
            "target_risk_pct",
            sa.Numeric(precision=5, scale=2),
            nullable=False,
            comment="Target risk as % of campaign budget (e.g., 2.0% for Spring)",
        ),
        # Actual risk (FR16)
        sa.Column(
            "actual_risk_pct",
            sa.Numeric(precision=5, scale=2),
            nullable=False,
            comment="Actual risk from position sizing (0.5%, 1.0%, 0.6%)",
        ),
        sa.Column(
            "position_size_shares",
            sa.Numeric(precision=18, scale=8),
            nullable=False,
            comment="Number of shares calculated",
        ),
        # Budget tracking
        sa.Column(
            "allocation_used",
            sa.Numeric(precision=5, scale=2),
            nullable=False,
            comment="Actual % of campaign budget consumed",
        ),
        sa.Column(
            "remaining_budget",
            sa.Numeric(precision=5, scale=2),
            nullable=False,
            comment="Remaining campaign budget after allocation",
        ),
        # Rebalancing (AC: 5)
        sa.Column(
            "is_rebalanced",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="True if rebalanced due to skipped entry",
        ),
        sa.Column(
            "rebalance_reason",
            sa.Text(),
            nullable=True,
            comment="Explanation of rebalancing (if applicable)",
        ),
        # Approval/Rejection (AC: 7)
        sa.Column(
            "approved",
            sa.Boolean(),
            nullable=False,
            comment="True if allocation approved, False if rejected",
        ),
        sa.Column(
            "rejection_reason",
            sa.Text(),
            nullable=True,
            comment="Explanation of rejection (if rejected)",
        ),
        # Audit trail
        sa.Column(
            "timestamp",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
            comment="When allocation plan was created (UTC)",
        ),
        # Primary key constraint
        sa.PrimaryKeyConstraint("id", name="pk_allocation_plans"),
        # Foreign key constraints
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name="fk_allocation_plans_campaign_id",
            ondelete="CASCADE",  # Delete allocations when campaign deleted
        ),
        # Note: signal_id FK would reference signals table (not created yet in migrations)
        # For now, we'll add a comment and create the FK in a future migration or
        # rely on application-level integrity
        # Check constraints
        sa.CheckConstraint(
            "pattern_type IN ('SPRING', 'SOS', 'LPS')",
            name="ck_allocation_plans_pattern_type",
        ),
        sa.CheckConstraint(
            "bmad_allocation_pct >= 0 AND bmad_allocation_pct <= 1.0",
            name="ck_allocation_plans_bmad_allocation_pct",
        ),
        sa.CheckConstraint(
            "target_risk_pct >= 0 AND target_risk_pct <= 5.0",
            name="ck_allocation_plans_target_risk_pct",
        ),
        sa.CheckConstraint(
            "actual_risk_pct >= 0 AND actual_risk_pct <= 10.0",
            name="ck_allocation_plans_actual_risk_pct",
        ),
        sa.CheckConstraint(
            "allocation_used >= 0 AND allocation_used <= 5.0",
            name="ck_allocation_plans_allocation_used",
        ),
        sa.CheckConstraint(
            "remaining_budget >= 0 AND remaining_budget <= 5.0",
            name="ck_allocation_plans_remaining_budget",
        ),
        comment="BMAD allocation plans for campaign budget tracking (Story 9.2)",
    )

    # ==========================================================================
    # 2. Create indexes for performance
    # ==========================================================================

    # Index on campaign_id (for audit trail queries: get all allocations for campaign)
    op.create_index(
        "idx_allocation_plans_campaign",
        "allocation_plans",
        ["campaign_id"],
        unique=False,
    )

    # Index on signal_id (for signal->allocation lookups)
    op.create_index(
        "idx_allocation_plans_signal",
        "allocation_plans",
        ["signal_id"],
        unique=False,
    )

    # Index on timestamp (for chronological ordering)
    op.create_index(
        "idx_allocation_plans_timestamp",
        "allocation_plans",
        ["timestamp"],
        unique=False,
    )

    # Composite index for campaign + approved status (filter approved allocations)
    op.create_index(
        "idx_allocation_plans_campaign_approved",
        "allocation_plans",
        ["campaign_id", "approved"],
        unique=False,
    )


def downgrade() -> None:
    """
    Drop allocation_plans table and all related indexes.

    WARNING: This will permanently delete all allocation audit trail data.
    """

    # Drop indexes first (PostgreSQL requires this before dropping table)
    op.drop_index("idx_allocation_plans_campaign_approved", table_name="allocation_plans")
    op.drop_index("idx_allocation_plans_timestamp", table_name="allocation_plans")
    op.drop_index("idx_allocation_plans_signal", table_name="allocation_plans")
    op.drop_index("idx_allocation_plans_campaign", table_name="allocation_plans")

    # Drop table (CASCADE will drop foreign keys)
    op.drop_table("allocation_plans")
