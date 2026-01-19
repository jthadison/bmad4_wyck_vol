"""add_story_12_6_metrics

Revision ID: 022_add_story_12_6_metrics
Revises: 021_add_walk_forward_tables
Create Date: 2025-12-23 10:30:00.000000

Story 12.6 Task 13: Add comprehensive metrics and reporting fields to backtest_results table.

Changes:
- Add pattern_performance JSONB column for per-pattern performance analysis
- Add monthly_returns JSONB column for monthly return heatmap data
- Add drawdown_periods JSONB column for drawdown period tracking
- Add risk_metrics JSONB column for portfolio risk statistics
- Add campaign_performance JSONB column for Wyckoff campaign tracking
- Add cost_summary JSONB column for transaction cost summary (Story 12.5)
- Note: look_ahead_bias_check already exists from initial schema

These fields enable comprehensive backtest reporting including:
- Pattern-by-pattern performance breakdown
- Monthly return calendar heatmap
- Drawdown period analysis with recovery tracking
- Risk-adjusted metrics (Sharpe, Sortino, Calmar, Kelly, etc.)
- Wyckoff campaign lifecycle tracking
- Transaction cost impact analysis
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "022_add_story_12_6_metrics"
down_revision: Union[str, Sequence[str], None] = "021_add_walk_forward_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Upgrade backtest_results table for Story 12.6 comprehensive metrics.

    Adds JSONB columns for enhanced reporting metrics.
    """
    # Story 12.6: Pattern performance analysis
    op.add_column(
        "backtest_results",
        sa.Column(
            "pattern_performance",
            postgresql.JSONB,
            nullable=False,
            server_default="[]",
            comment="Performance breakdown by pattern type (Story 12.6)",
        ),
    )

    # Story 12.6: Monthly returns heatmap
    op.add_column(
        "backtest_results",
        sa.Column(
            "monthly_returns",
            postgresql.JSONB,
            nullable=False,
            server_default="[]",
            comment="Monthly return heatmap data (Story 12.6)",
        ),
    )

    # Story 12.6: Drawdown period analysis
    op.add_column(
        "backtest_results",
        sa.Column(
            "drawdown_periods",
            postgresql.JSONB,
            nullable=False,
            server_default="[]",
            comment="Drawdown period tracking (Story 12.6)",
        ),
    )

    # Story 12.6: Portfolio risk metrics
    op.add_column(
        "backtest_results",
        sa.Column(
            "risk_metrics",
            postgresql.JSONB,
            nullable=True,
            comment="Portfolio risk statistics (Story 12.6)",
        ),
    )

    # Story 12.6: Wyckoff campaign performance
    op.add_column(
        "backtest_results",
        sa.Column(
            "campaign_performance",
            postgresql.JSONB,
            nullable=False,
            server_default="[]",
            comment="Wyckoff campaign tracking (Story 12.6)",
        ),
    )

    # Story 12.5: Transaction cost summary
    op.add_column(
        "backtest_results",
        sa.Column(
            "cost_summary",
            postgresql.JSONB,
            nullable=True,
            comment="Transaction cost summary (Story 12.5)",
        ),
    )

    # Note: look_ahead_bias_check column already exists from 001_initial_schema_with_timescaledb.py
    # so we don't need to add it again

    # Add GIN indexes for JSONB query performance
    # These enable efficient querying of pattern types, campaigns, etc.
    op.create_index(
        "idx_backtest_pattern_performance_gin",
        "backtest_results",
        ["pattern_performance"],
        postgresql_using="gin",
    )

    op.create_index(
        "idx_backtest_campaign_performance_gin",
        "backtest_results",
        ["campaign_performance"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    """
    Downgrade backtest_results table (rollback Story 12.6 changes).
    """
    # Drop GIN indexes
    op.drop_index("idx_backtest_campaign_performance_gin", table_name="backtest_results")
    op.drop_index("idx_backtest_pattern_performance_gin", table_name="backtest_results")

    # Drop Story 12.6 columns (look_ahead_bias_check existed before this migration)
    op.drop_column("backtest_results", "cost_summary")
    op.drop_column("backtest_results", "campaign_performance")
    op.drop_column("backtest_results", "risk_metrics")
    op.drop_column("backtest_results", "drawdown_periods")
    op.drop_column("backtest_results", "monthly_returns")
    op.drop_column("backtest_results", "pattern_performance")
