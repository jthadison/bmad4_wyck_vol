"""add_regression_testing_tables

Revision ID: 022_add_regression_tables
Revises: 022_add_story_12_6_metrics
Create Date: 2025-12-22 00:00:00.000000

Story 12.7 Task 6: Create regression_test_results and regression_baselines tables
for automated regression testing system.

Changes:
- Create regression_test_results table with JSONB columns for config, metrics, per_symbol_results
- Create regression_baselines table with JSONB columns for metrics, per_symbol_metrics
- Add unique constraint on regression_baselines.is_current=TRUE
- Add indexes for query optimization
- Support full regression test workflow persistence
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "022_add_regression_tables"
down_revision: Union[str, Sequence[str], None] = "022_add_story_12_6_metrics"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create regression testing tables for Story 12.7.

    AC Task 6 Subtasks:
    - 6.1: Create regression_test_results table
    - 6.2: Create regression_baselines table
    - 6.3: Add indexes for performance
    - 6.4: Add unique constraint on is_current baseline
    """
    # Create regression_test_results table
    op.create_table(
        "regression_test_results",
        # Primary key
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        # Test identification
        sa.Column(
            "test_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            unique=True,
        ),
        # Configuration (JSONB - RegressionTestConfig)
        sa.Column("config", postgresql.JSONB, nullable=False),
        # Test execution time
        sa.Column("test_run_time", sa.DateTime(timezone=False), nullable=False),
        # Codebase version (git commit hash)
        sa.Column("codebase_version", sa.String(40), nullable=False),
        # Aggregate metrics (JSONB - BacktestMetrics)
        sa.Column("aggregate_metrics", postgresql.JSONB, nullable=False),
        # Per-symbol results (JSONB - dict[str, BacktestResult])
        sa.Column("per_symbol_results", postgresql.JSONB, nullable=False, server_default="{}"),
        # Baseline comparison (JSONB - RegressionComparison, nullable)
        sa.Column("baseline_comparison", postgresql.JSONB, nullable=True),
        # Regression detection
        sa.Column("regression_detected", sa.Boolean, nullable=False, server_default="false"),
        # Degraded metrics (JSONB - list[str])
        sa.Column("degraded_metrics", postgresql.JSONB, nullable=False, server_default="[]"),
        # Test status
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="BASELINE_NOT_SET",
        ),
        # Execution time
        sa.Column(
            "execution_time_seconds",
            sa.NUMERIC(10, 4),
            nullable=False,
            server_default="0.0",
        ),
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
    )

    # Create regression_baselines table
    op.create_table(
        "regression_baselines",
        # Primary key
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        # Baseline identification
        sa.Column(
            "baseline_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            unique=True,
        ),
        # Reference to test that created this baseline
        sa.Column(
            "test_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        # Codebase version (git commit hash)
        sa.Column("version", sa.String(40), nullable=False),
        # Aggregate metrics (JSONB - BacktestMetrics)
        sa.Column("metrics", postgresql.JSONB, nullable=False),
        # Per-symbol metrics (JSONB - dict[str, BacktestMetrics])
        sa.Column("per_symbol_metrics", postgresql.JSONB, nullable=False, server_default="{}"),
        # Establishment timestamp
        sa.Column("established_at", sa.DateTime(timezone=False), nullable=False),
        # Current baseline flag
        sa.Column("is_current", sa.Boolean, nullable=False, server_default="false"),
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
    )

    # Add indexes for regression_test_results (AC Task 6.3)
    op.create_index(
        "ix_regression_test_results_test_id",
        "regression_test_results",
        ["test_id"],
        unique=True,
    )
    op.create_index(
        "ix_regression_test_results_test_run_time",
        "regression_test_results",
        ["test_run_time"],
    )
    op.create_index(
        "ix_regression_test_results_status",
        "regression_test_results",
        ["status"],
    )
    op.create_index(
        "ix_regression_test_results_codebase_version",
        "regression_test_results",
        ["codebase_version"],
    )

    # Add indexes for regression_baselines (AC Task 6.3)
    op.create_index(
        "ix_regression_baselines_baseline_id",
        "regression_baselines",
        ["baseline_id"],
        unique=True,
    )
    op.create_index(
        "ix_regression_baselines_test_id",
        "regression_baselines",
        ["test_id"],
    )
    op.create_index(
        "ix_regression_baselines_established_at",
        "regression_baselines",
        ["established_at"],
    )
    op.create_index(
        "ix_regression_baselines_is_current",
        "regression_baselines",
        ["is_current"],
    )

    # Add unique constraint on is_current=TRUE (AC Task 6.4)
    # This ensures only one baseline can be is_current=TRUE at a time
    # PostgreSQL partial unique index
    op.create_index(
        "ix_regression_baselines_unique_current",
        "regression_baselines",
        ["is_current"],
        unique=True,
        postgresql_where=sa.text("is_current = true"),
    )

    # Add foreign key constraint from baselines to test_results
    op.create_foreign_key(
        "fk_regression_baselines_test_id",
        "regression_baselines",
        "regression_test_results",
        ["test_id"],
        ["test_id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    """
    Drop regression testing tables (rollback Story 12.7 changes).
    """
    # Drop foreign key
    op.drop_constraint(
        "fk_regression_baselines_test_id",
        "regression_baselines",
        type_="foreignkey",
    )

    # Drop regression_baselines indexes
    op.drop_index(
        "ix_regression_baselines_unique_current",
        table_name="regression_baselines",
    )
    op.drop_index(
        "ix_regression_baselines_is_current",
        table_name="regression_baselines",
    )
    op.drop_index(
        "ix_regression_baselines_established_at",
        table_name="regression_baselines",
    )
    op.drop_index(
        "ix_regression_baselines_test_id",
        table_name="regression_baselines",
    )
    op.drop_index(
        "ix_regression_baselines_baseline_id",
        table_name="regression_baselines",
    )

    # Drop regression_test_results indexes
    op.drop_index(
        "ix_regression_test_results_codebase_version",
        table_name="regression_test_results",
    )
    op.drop_index(
        "ix_regression_test_results_status",
        table_name="regression_test_results",
    )
    op.drop_index(
        "ix_regression_test_results_test_run_time",
        table_name="regression_test_results",
    )
    op.drop_index(
        "ix_regression_test_results_test_id",
        table_name="regression_test_results",
    )

    # Drop tables
    op.drop_table("regression_baselines")
    op.drop_table("regression_test_results")
