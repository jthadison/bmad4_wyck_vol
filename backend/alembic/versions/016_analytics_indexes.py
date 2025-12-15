"""Create Analytics Performance Indexes (Task 2)

Revision ID: 016
Revises: 015
Create Date: 2025-12-12

This migration creates database indexes to optimize analytics queries for
the Pattern Performance Dashboard.

Indexes Created:
----------------
1. idx_signals_analytics:
   - Composite index on signals(status, generated_at, pattern_id)
   - Partial index: WHERE status IN ('CLOSED_WIN', 'CLOSED_LOSS')
   - Purpose: Filter closed trades by date range for performance calculations
   - Expected impact: <100ms for pattern performance queries

2. idx_signals_symbol_generated_at:
   - Composite index on signals(symbol, generated_at DESC)
   - Purpose: Sector breakdown queries (JOIN with sector_mapping)
   - Expected impact: Fast symbol-based aggregations

3. idx_patterns_type_phase:
   - Composite index on patterns(pattern_type, detection_phase)
   - Purpose: Phase-filtered performance metrics
   - Expected impact: <50ms for phase breakdown queries

4. idx_signals_exit_date:
   - Simple index on signals(exit_date)
   - Purpose: Trend analysis queries (GROUP BY date)
   - Expected impact: Fast daily aggregations

Query Performance Targets (with indexes):
------------------------------------------
- Pattern performance (4 patterns): 50-100ms
- Win rate trend (30 days): 30-50ms
- Trade details (paginated 50): 20-30ms
- Sector breakdown (12 sectors): 40-60ms

IMPORTANT: Run EXPLAIN ANALYZE on analytics queries after migration to verify
           index usage and performance targets are met.
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create analytics performance indexes.
    """

    # Index 1: Composite index for analytics queries on signals table
    # Partial index for closed trades only (reduces index size)
    op.execute(
        """
        CREATE INDEX idx_signals_analytics
        ON signals(status, generated_at DESC, pattern_id)
        WHERE status IN ('CLOSED_WIN', 'CLOSED_LOSS');
        """
    )

    # Index 2: Symbol-based queries for sector breakdown
    op.create_index(
        "idx_signals_symbol_generated_at",
        "signals",
        ["symbol", sa.text("generated_at DESC")],
    )

    # Index 3: Pattern type and phase for phase-filtered queries
    # Note: This index may already exist from 001_initial_schema as idx_patterns_type_phase
    # Check if it exists before creating to avoid duplicate index error
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_patterns_type_phase
        ON patterns(pattern_type, detection_phase);
        """
    )

    # Index 4: Exit date for trend analysis queries
    op.create_index(
        "idx_signals_exit_date",
        "signals",
        [sa.text("exit_date DESC")],
        postgresql_where=sa.text("exit_date IS NOT NULL"),
    )

    # Index 5: Patterns symbol and timestamp for preliminary events lookup
    op.create_index(
        "idx_patterns_symbol_detection",
        "patterns",
        ["symbol", sa.text("detection_time DESC")],
    )

    # Add comment documenting expected performance
    op.execute(
        """
        COMMENT ON INDEX idx_signals_analytics IS
        'Analytics query optimization: <100ms for pattern performance aggregations';
        """
    )
    op.execute(
        """
        COMMENT ON INDEX idx_signals_symbol_generated_at IS
        'Sector breakdown optimization: <60ms for symbol-based aggregations';
        """
    )
    op.execute(
        """
        COMMENT ON INDEX idx_signals_exit_date IS
        'Trend analysis optimization: <50ms for daily win rate calculations';
        """
    )


def downgrade() -> None:
    """
    Drop analytics performance indexes.
    """
    op.drop_index("idx_patterns_symbol_detection", table_name="patterns")
    op.drop_index("idx_signals_exit_date", table_name="signals")
    # idx_patterns_type_phase may be from original schema, so use IF EXISTS
    op.execute("DROP INDEX IF EXISTS idx_patterns_type_phase;")
    op.drop_index("idx_signals_symbol_generated_at", table_name="signals")
    op.execute("DROP INDEX IF EXISTS idx_signals_analytics;")
