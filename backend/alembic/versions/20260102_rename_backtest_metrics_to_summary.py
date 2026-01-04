"""rename backtest metrics to summary

Revision ID: 20260102_rename_metrics
Revises: 78dd8d77a2bd
Create Date: 2026-01-02

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260102_rename_metrics"
down_revision = "78dd8d77a2bd"
branch_labels = None
depends_on = None


def upgrade():
    """Rename metrics column to summary in backtest_results table."""
    op.alter_column("backtest_results", "metrics", new_column_name="summary")


def downgrade():
    """Rename summary column back to metrics in backtest_results table."""
    op.alter_column("backtest_results", "summary", new_column_name="metrics")
