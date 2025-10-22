"""Initial schema with TimescaleDB

Revision ID: 001
Revises:
Create Date: 2025-10-21

This migration creates the complete database schema for the BMAD Wyckoff system:
1. ohlcv_bars - TimescaleDB hypertable with daily chunks and compression
2. trading_ranges - Wyckoff trading range metadata
3. patterns - Detected patterns with JSONB metadata
4. signals - Trade signals with risk management
5. campaigns - Position sizing campaigns
6. backtest_results - Backtesting metrics
7. audit_trail - Immutable audit log

CRITICAL: All financial data uses NUMERIC(18,8) precision (never FLOAT)
CRITICAL: All timestamps use TIMESTAMPTZ (timezone-aware)
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create all database tables and TimescaleDB configurations.

    Order of creation respects foreign key dependencies:
    1. trading_ranges (no dependencies)
    2. ohlcv_bars (no dependencies)
    3. patterns (depends on trading_ranges)
    4. campaigns (depends on trading_ranges)
    5. signals (depends on patterns and campaigns)
    6. backtest_results (no dependencies)
    7. audit_trail (no dependencies)
    """

    # ==========================================================================
    # Table 1: trading_ranges
    # ==========================================================================
    op.create_table(
        'trading_ranges',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('symbol', sa.String(length=20), nullable=False),
        sa.Column('timeframe', sa.String(length=5), nullable=False),
        sa.Column('start_time', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('end_time', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('duration_bars', sa.Integer(), nullable=False),
        sa.Column('creek_level', sa.NUMERIC(precision=18, scale=8), nullable=False, comment='Support level (Wyckoff creek)'),
        sa.Column('ice_level', sa.NUMERIC(precision=18, scale=8), nullable=False, comment='Resistance level (Wyckoff ice)'),
        sa.Column('jump_target', sa.NUMERIC(precision=18, scale=8), nullable=False, comment='Projected price target'),
        sa.Column('cause_factor', sa.NUMERIC(precision=4, scale=2), nullable=False, comment='Wyckoff cause-effect ratio'),
        sa.Column('range_width', sa.NUMERIC(precision=10, scale=4), nullable=False),
        sa.Column('phase', sa.String(length=1), nullable=False, comment='Wyckoff phase: A, B, C, D, or E'),
        sa.Column('strength_score', sa.Integer(), nullable=False, comment='Range quality score 60-100'),
        sa.Column('touch_count_creek', sa.Integer(), server_default='0'),
        sa.Column('touch_count_ice', sa.Integer(), server_default='0'),
        sa.Column('deleted_at', sa.TIMESTAMP(timezone=True), nullable=True, comment='Soft delete timestamp'),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1', comment='Optimistic locking version'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.CheckConstraint('duration_bars BETWEEN 15 AND 100', name='chk_duration_bars'),
        sa.CheckConstraint('cause_factor BETWEEN 2.0 AND 3.0', name='chk_cause_factor'),
        sa.CheckConstraint("phase IN ('A','B','C','D','E')", name='chk_phase'),
        sa.CheckConstraint('strength_score BETWEEN 60 AND 100', name='chk_strength_score'),
    )

    # ==========================================================================
    # Table 2: ohlcv_bars (TimescaleDB Hypertable)
    # ==========================================================================
    # NOTE: For TimescaleDB hypertables, we must convert to hypertable BEFORE
    # adding unique constraints that don't include the partitioning column
    op.create_table(
        'ohlcv_bars',
        # Note: We remove the UUID primary key and use composite key instead
        # TimescaleDB requires partitioning column in all unique indexes
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('symbol', sa.String(length=20), nullable=False),
        sa.Column('timeframe', sa.String(length=5), nullable=False),
        sa.Column('timestamp', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('open', sa.NUMERIC(precision=18, scale=8), nullable=False),
        sa.Column('high', sa.NUMERIC(precision=18, scale=8), nullable=False),
        sa.Column('low', sa.NUMERIC(precision=18, scale=8), nullable=False),
        sa.Column('close', sa.NUMERIC(precision=18, scale=8), nullable=False),
        sa.Column('volume', sa.BigInteger(), nullable=False),
        sa.Column('spread', sa.NUMERIC(precision=18, scale=8), nullable=False, comment='high - low'),
        sa.Column('spread_ratio', sa.NUMERIC(precision=10, scale=4), nullable=False, comment='Spread vs 20-bar average'),
        sa.Column('volume_ratio', sa.NUMERIC(precision=10, scale=4), nullable=False, comment='Volume vs 20-bar average'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.CheckConstraint('volume >= 0', name='chk_volume_positive'),
        # Composite primary key that includes timestamp (required for TimescaleDB)
        sa.PrimaryKeyConstraint('symbol', 'timeframe', 'timestamp', name='pk_ohlcv_bars'),
    )

    # Create index on id for lookups by UUID
    op.create_index('idx_ohlcv_id', 'ohlcv_bars', ['id'])

    # Convert to TimescaleDB hypertable (AC: 2, 3)
    # This enables automatic partitioning by time with daily chunks
    # MUST be done before creating other indexes
    op.execute("""
        SELECT create_hypertable(
            'ohlcv_bars',
            'timestamp',
            chunk_time_interval => INTERVAL '1 day',
            if_not_exists => TRUE
        );
    """)

    # Create index for efficient recent data queries (AC: 5)
    # Created AFTER hypertable conversion
    op.create_index(
        'idx_ohlcv_symbol_timeframe',
        'ohlcv_bars',
        ['symbol', 'timeframe', sa.text('timestamp DESC')],
    )

    # Enable compression for data older than 7 days (AC: 4)
    op.execute("""
        ALTER TABLE ohlcv_bars SET (
            timescaledb.compress,
            timescaledb.compress_segmentby = 'symbol,timeframe',
            timescaledb.compress_orderby = 'timestamp DESC'
        );
    """)

    # Add compression policy (AC: 4)
    op.execute("""
        SELECT add_compression_policy('ohlcv_bars', INTERVAL '7 days');
    """)

    # ==========================================================================
    # Table 3: patterns
    # ==========================================================================
    op.create_table(
        'patterns',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('pattern_type', sa.String(length=10), nullable=False, comment='SPRING, UTAD, SOS, etc.'),
        sa.Column('symbol', sa.String(length=20), nullable=False),
        sa.Column('timeframe', sa.String(length=5), nullable=False),
        sa.Column('detection_time', sa.TIMESTAMP(timezone=True), nullable=False, comment='When algo detected pattern'),
        sa.Column('pattern_bar_timestamp', sa.TIMESTAMP(timezone=True), nullable=False, comment='Actual bar where pattern occurred'),
        sa.Column('confidence_score', sa.Integer(), nullable=False),
        sa.Column('phase', sa.String(length=1), nullable=False, comment='Wyckoff phase'),
        sa.Column('trading_range_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('entry_price', sa.NUMERIC(precision=18, scale=8), nullable=False),
        sa.Column('stop_loss', sa.NUMERIC(precision=18, scale=8), nullable=False),
        sa.Column('invalidation_level', sa.NUMERIC(precision=18, scale=8), nullable=False),
        sa.Column('volume_ratio', sa.NUMERIC(precision=10, scale=4), nullable=False),
        sa.Column('spread_ratio', sa.NUMERIC(precision=10, scale=4), nullable=False),
        sa.Column('test_confirmed', sa.Boolean(), server_default='false'),
        sa.Column('test_bar_timestamp', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment='Pattern-specific flexible metadata'),
        sa.Column('metadata_version', sa.Integer(), server_default='1'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.CheckConstraint('confidence_score BETWEEN 70 AND 95', name='chk_confidence_score'),
        sa.CheckConstraint("phase IN ('A','B','C','D','E')", name='chk_pattern_phase'),
        sa.ForeignKeyConstraint(['trading_range_id'], ['trading_ranges.id'], ondelete='RESTRICT'),
    )

    # Create indexes for efficient pattern queries
    op.create_index(
        'idx_patterns_symbol',
        'patterns',
        ['symbol', sa.text('pattern_bar_timestamp DESC')],
    )
    op.create_index(
        'idx_patterns_type_phase',
        'patterns',
        ['pattern_type', 'phase'],
    )

    # ==========================================================================
    # Table 4: campaigns
    # ==========================================================================
    op.create_table(
        'campaigns',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('symbol', sa.String(length=20), nullable=False),
        sa.Column('timeframe', sa.String(length=5), nullable=False),
        sa.Column('trading_range_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('total_allocation', sa.NUMERIC(precision=5, scale=2), nullable=False, comment='Max 5% portfolio allocation'),
        sa.Column('current_risk', sa.NUMERIC(precision=12, scale=2), nullable=False),
        sa.Column('entries', postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment='Array of entry objects'),
        sa.Column('average_entry', sa.NUMERIC(precision=18, scale=8), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('started_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('completed_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.CheckConstraint('total_allocation <= 5.0', name='chk_total_allocation'),
        sa.ForeignKeyConstraint(['trading_range_id'], ['trading_ranges.id'], ondelete='RESTRICT'),
    )

    # ==========================================================================
    # Table 5: signals
    # ==========================================================================
    op.create_table(
        'signals',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('signal_type', sa.String(length=10), nullable=False, server_default='LONG'),
        sa.Column('pattern_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('symbol', sa.String(length=20), nullable=False),
        sa.Column('timeframe', sa.String(length=5), nullable=False),
        sa.Column('generated_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('entry_price', sa.NUMERIC(precision=18, scale=8), nullable=False),
        sa.Column('stop_loss', sa.NUMERIC(precision=18, scale=8), nullable=False),
        sa.Column('target_1', sa.NUMERIC(precision=18, scale=8), nullable=False),
        sa.Column('target_2', sa.NUMERIC(precision=18, scale=8), nullable=False),
        sa.Column('position_size', sa.NUMERIC(precision=18, scale=8), nullable=False),
        sa.Column('risk_amount', sa.NUMERIC(precision=12, scale=2), nullable=False),
        sa.Column('r_multiple', sa.NUMERIC(precision=6, scale=2), nullable=False, comment='Risk-reward ratio'),
        sa.Column('confidence_score', sa.Integer(), nullable=False),
        sa.Column('campaign_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('campaign_allocation', sa.NUMERIC(precision=5, scale=4), server_default='0'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='PENDING'),
        sa.Column('notification_sent', sa.Boolean(), server_default='false'),
        sa.Column('approval_chain', postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment='Validation steps passed'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.CheckConstraint('r_multiple >= 2.0', name='chk_r_multiple'),
        sa.ForeignKeyConstraint(['pattern_id'], ['patterns.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ondelete='SET NULL'),
    )

    # Create index for efficient signal status queries
    op.create_index(
        'idx_signals_status',
        'signals',
        ['status', sa.text('generated_at DESC')],
    )

    # ==========================================================================
    # Table 6: backtest_results
    # ==========================================================================
    op.create_table(
        'backtest_results',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('backtest_run_id', postgresql.UUID(as_uuid=True), nullable=False, comment='Groups results from same backtest run'),
        sa.Column('symbol', sa.String(length=20), nullable=False),
        sa.Column('timeframe', sa.String(length=5), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        # Pattern detection metrics
        sa.Column('total_patterns_detected', sa.Integer(), nullable=False),
        sa.Column('true_positives', sa.Integer(), nullable=False),
        sa.Column('false_positives', sa.Integer(), nullable=False),
        sa.Column('false_negatives', sa.Integer(), nullable=False),
        sa.Column('precision', sa.NUMERIC(precision=6, scale=4), nullable=False, comment='TP / (TP + FP)'),
        sa.Column('recall', sa.NUMERIC(precision=6, scale=4), nullable=False, comment='TP / (TP + FN)'),
        # Signal performance metrics
        sa.Column('total_signals_generated', sa.Integer(), nullable=False),
        sa.Column('winning_signals', sa.Integer(), nullable=False),
        sa.Column('losing_signals', sa.Integer(), nullable=False),
        sa.Column('win_rate', sa.NUMERIC(precision=6, scale=4), nullable=False),
        sa.Column('average_r_multiple', sa.NUMERIC(precision=6, scale=2), nullable=False),
        sa.Column('max_drawdown', sa.NUMERIC(precision=6, scale=4), nullable=False),
        # Configuration and validation
        sa.Column('config', postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment='Detector configuration used'),
        sa.Column('look_ahead_bias_check', sa.Boolean(), server_default='false'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    )

    # ==========================================================================
    # Table 7: audit_trail (Immutable)
    # ==========================================================================
    op.create_table(
        'audit_trail',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('entity_type', sa.String(length=50), nullable=False, comment='Table name'),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('timestamp', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('actor', sa.String(length=100), nullable=False, comment='User or service that performed action'),
        sa.Column('action', sa.Text(), nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('correlation_id', postgresql.UUID(as_uuid=True), nullable=False, comment='Trace entire workflow'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    )

    # Create index for correlation tracking
    op.create_index(
        'idx_audit_correlation',
        'audit_trail',
        ['correlation_id'],
    )

    # Make audit_trail immutable (AC: 9 - prevent UPDATE/DELETE)
    op.execute("""
        REVOKE UPDATE, DELETE ON audit_trail FROM PUBLIC;
    """)


def downgrade() -> None:
    """
    Drop all tables in reverse order of creation (respects foreign keys).
    """
    # Remove compression policy before dropping hypertable
    op.execute("""
        SELECT remove_compression_policy('ohlcv_bars', if_exists => true);
    """)

    # Drop tables in reverse dependency order
    op.drop_table('audit_trail')
    op.drop_table('backtest_results')
    op.drop_table('signals')
    op.drop_table('campaigns')
    op.drop_table('patterns')
    op.drop_table('ohlcv_bars')  # TimescaleDB automatically handles hypertable cleanup
    op.drop_table('trading_ranges')
