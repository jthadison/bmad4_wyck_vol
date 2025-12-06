"""Add Exit Management Tables (Story 9.5)

Revision ID: 011
Revises: 010
Create Date: 2025-12-05

This migration creates the exit management infrastructure for campaign exit
strategies with partial exits, trailing stops, and invalidation conditions.

Changes:
--------
1. Create exit_rules table:
   - Target levels (T1, T2, T3) for partial exits
   - Exit percentages (default 50/30/20%)
   - Trailing stop configuration
   - Invalidation levels (spring_low, ice_level, creek_level, utad_high)

2. Create exit_orders table:
   - Tracks triggered exit orders (PARTIAL_EXIT, STOP_LOSS, INVALIDATION)
   - Links to campaigns and positions
   - Execution status tracking

3. Extend campaigns table:
   - jump_achieved: Track when Jump target reached (for Creek break detection)
   - invalidated_by: Pattern-specific vs portfolio-level invalidation tracking
   - campaign_start_date: For time-based invalidation (>180 days)
   - time_based_invalidation_override: User override for extended campaigns

4. Add indexes for performance:
   - exit_rules: campaign_id (UNIQUE)
   - exit_orders: campaign_id + triggered_at DESC, position_id

CRITICAL: All financial data uses NUMERIC(18,8) for prices
CRITICAL: All timestamps use TIMESTAMPTZ (timezone-aware, UTC)
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create exit management tables and extend campaigns table.

    Order of operations:
    1. Create exit_rules table
    2. Create exit_orders table
    3. Add new columns to campaigns table
    4. Create indexes for performance
    """

    # 1. Create exit_rules table
    op.create_table(
        "exit_rules",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            comment="Exit rule identifier",
        ),
        sa.Column(
            "campaign_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("campaigns.id", ondelete="CASCADE"),
            nullable=False,
            comment="Parent campaign (FK to campaigns.id)",
        ),
        # Target levels (NUMERIC(18,8) precision)
        sa.Column(
            "target_1_level",
            sa.NUMERIC(18, 8),
            nullable=False,
            comment="T1 target price (Ice for pre-breakout, Jump for post-breakout)",
        ),
        sa.Column(
            "target_2_level",
            sa.NUMERIC(18, 8),
            nullable=False,
            comment="T2 target price (Jump)",
        ),
        sa.Column(
            "target_3_level",
            sa.NUMERIC(18, 8),
            nullable=False,
            comment="T3 target price (Jump × 1.5 extended target)",
        ),
        # Partial exit percentages (NUMERIC(5,2) precision)
        sa.Column(
            "t1_exit_pct",
            sa.NUMERIC(5, 2),
            nullable=False,
            server_default=sa.text("50.00"),
            comment="Percentage to exit at T1 (default 50%)",
        ),
        sa.Column(
            "t2_exit_pct",
            sa.NUMERIC(5, 2),
            nullable=False,
            server_default=sa.text("30.00"),
            comment="Percentage to exit at T2 (default 30%)",
        ),
        sa.Column(
            "t3_exit_pct",
            sa.NUMERIC(5, 2),
            nullable=False,
            server_default=sa.text("20.00"),
            comment="Percentage to exit at T3 (default 20%)",
        ),
        # Trailing stop configuration
        sa.Column(
            "trail_to_breakeven_on_t1",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("TRUE"),
            comment="Move stop to entry_price when T1 hit",
        ),
        sa.Column(
            "trail_to_t1_on_t2",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("TRUE"),
            comment="Move stop to T1 level when T2 hit",
        ),
        # Invalidation levels (NUMERIC(18,8) precision)
        sa.Column(
            "spring_low",
            sa.NUMERIC(18, 8),
            nullable=True,
            comment="Spring low invalidation level",
        ),
        sa.Column(
            "ice_level",
            sa.NUMERIC(18, 8),
            nullable=True,
            comment="Ice level for post-SOS invalidation",
        ),
        sa.Column(
            "creek_level",
            sa.NUMERIC(18, 8),
            nullable=True,
            comment="Creek level for post-Jump invalidation",
        ),
        sa.Column(
            "utad_high",
            sa.NUMERIC(18, 8),
            nullable=True,
            comment="UTAD high invalidation level (for shorts)",
        ),
        sa.Column(
            "jump_target",
            sa.NUMERIC(18, 8),
            nullable=True,
            comment="Jump target price for tracking jump achievement",
        ),
        # Timestamps
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
            comment="Record creation timestamp",
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
            comment="Record last update timestamp",
        ),
        # Constraints
        sa.UniqueConstraint("campaign_id", name="uq_exit_rules_campaign"),
        sa.CheckConstraint(
            "t1_exit_pct >= 0 AND t1_exit_pct <= 100",
            name="ck_exit_rules_t1_pct_range",
        ),
        sa.CheckConstraint(
            "t2_exit_pct >= 0 AND t2_exit_pct <= 100",
            name="ck_exit_rules_t2_pct_range",
        ),
        sa.CheckConstraint(
            "t3_exit_pct >= 0 AND t3_exit_pct <= 100",
            name="ck_exit_rules_t3_pct_range",
        ),
        sa.CheckConstraint(
            "t1_exit_pct + t2_exit_pct + t3_exit_pct = 100",
            name="ck_exit_rules_pct_sum_100",
        ),
        sa.CheckConstraint(
            "target_1_level > 0 AND target_2_level > 0 AND target_3_level > 0",
            name="ck_exit_rules_positive_targets",
        ),
        comment="Campaign exit strategy configuration",
    )

    # 2. Create exit_orders table
    op.create_table(
        "exit_orders",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            comment="Unique exit order identifier",
        ),
        sa.Column(
            "campaign_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("campaigns.id", ondelete="RESTRICT"),
            nullable=False,
            comment="Parent campaign (FK to campaigns.id)",
        ),
        sa.Column(
            "position_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("positions.id", ondelete="RESTRICT"),
            nullable=False,
            comment="Source position (FK to positions.id)",
        ),
        # Exit details
        sa.Column(
            "order_type",
            sa.VARCHAR(20),
            nullable=False,
            comment="PARTIAL_EXIT | STOP_LOSS | INVALIDATION",
        ),
        sa.Column(
            "exit_level",
            sa.NUMERIC(18, 8),
            nullable=False,
            comment="Price at which exit triggered",
        ),
        sa.Column(
            "shares",
            sa.Integer,
            nullable=False,
            comment="Number of shares to exit",
        ),
        sa.Column(
            "reason",
            sa.Text,
            nullable=False,
            comment="Human-readable explanation of exit trigger",
        ),
        # Timestamps
        sa.Column(
            "triggered_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            comment="Timestamp when exit condition detected (UTC)",
        ),
        # Execution tracking
        sa.Column(
            "executed",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("FALSE"),
            comment="Boolean flag for broker execution tracking",
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
            comment="Record creation timestamp",
        ),
        # Constraints
        sa.CheckConstraint(
            "order_type IN ('PARTIAL_EXIT', 'STOP_LOSS', 'INVALIDATION')",
            name="ck_exit_orders_order_type",
        ),
        sa.CheckConstraint(
            "exit_level > 0",
            name="ck_exit_orders_positive_exit_level",
        ),
        sa.CheckConstraint(
            "shares > 0",
            name="ck_exit_orders_positive_shares",
        ),
        comment="Triggered exit orders for campaign positions",
    )

    # 3. Extend campaigns table
    op.add_column(
        "campaigns",
        sa.Column(
            "jump_achieved",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("FALSE"),
            comment="Track when Jump target reached (for Creek break detection)",
        ),
    )
    op.add_column(
        "campaigns",
        sa.Column(
            "invalidated_by",
            sa.VARCHAR(20),
            nullable=True,
            comment="PATTERN | PORTFOLIO | TIME_BASED | MANUAL",
        ),
    )
    op.add_column(
        "campaigns",
        sa.Column(
            "campaign_start_date",
            sa.Date,
            nullable=False,
            server_default=sa.text("CURRENT_DATE"),
            comment="Campaign start date for time-based invalidation",
        ),
    )
    op.add_column(
        "campaigns",
        sa.Column(
            "time_based_invalidation_override",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("FALSE"),
            comment="User override for campaigns beyond 180 days",
        ),
    )
    op.add_column(
        "campaigns",
        sa.Column(
            "time_override_reason",
            sa.Text,
            nullable=True,
            comment="User justification for extending beyond 180 days",
        ),
    )

    # Add check constraint for invalidated_by enum
    op.create_check_constraint(
        "ck_campaigns_invalidated_by",
        "campaigns",
        "invalidated_by IS NULL OR invalidated_by IN ('PATTERN', 'PORTFOLIO', 'TIME_BASED', 'MANUAL')",
    )

    # 4. Create indexes for performance
    op.create_index(
        "idx_exit_rules_campaign",
        "exit_rules",
        ["campaign_id"],
        unique=True,
    )
    op.create_index(
        "idx_exit_orders_campaign",
        "exit_orders",
        ["campaign_id", sa.text("triggered_at DESC")],
    )
    op.create_index(
        "idx_exit_orders_position",
        "exit_orders",
        ["position_id"],
    )


def downgrade() -> None:
    """
    Reverse the migration.

    Order of operations:
    1. Drop indexes
    2. Remove columns from campaigns table
    3. Drop exit_orders table
    4. Drop exit_rules table
    """

    # 1. Drop indexes
    op.drop_index("idx_exit_orders_position", table_name="exit_orders")
    op.drop_index("idx_exit_orders_campaign", table_name="exit_orders")
    op.drop_index("idx_exit_rules_campaign", table_name="exit_rules")

    # 2. Remove columns from campaigns table
    op.drop_constraint("ck_campaigns_invalidated_by", "campaigns", type_="check")
    op.drop_column("campaigns", "time_override_reason")
    op.drop_column("campaigns", "time_based_invalidation_override")
    op.drop_column("campaigns", "campaign_start_date")
    op.drop_column("campaigns", "invalidated_by")
    op.drop_column("campaigns", "jump_achieved")

    # 3. Drop exit_orders table
    op.drop_table("exit_orders")

    # 4. Drop exit_rules table
    op.drop_table("exit_rules")
