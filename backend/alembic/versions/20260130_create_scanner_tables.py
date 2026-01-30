"""create_scanner_tables

Revision ID: 20260130_scanner_tables
Revises: 5dc144357072
Create Date: 2026-01-30 10:00:00.000000

Story 20.1: Scanner Database Schema & Models

This migration creates the scanner persistence tables:
1. scanner_watchlist - Symbols to scan with timeframe/asset class
2. scanner_config - Singleton scanner configuration (interval, batch size, etc.)
3. scanner_history - Scan cycle history for monitoring

Key Features:
- Symbol validation via CHECK constraint (uppercase alphanumeric + ./^-)
- Timeframe validation (1M, 5M, 15M, 30M, 1H, 4H, 1D, 1W)
- Asset class validation (forex, stock, index, crypto)
- Singleton config pattern (only one row allowed)
- Scan cycle status tracking (COMPLETED, PARTIAL, FAILED, SKIPPED)
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260130_scanner_tables"
down_revision: Union[str, Sequence[str], None] = "5dc144357072"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create scanner tables."""

    # ===========================================
    # Table 1: scanner_watchlist
    # ===========================================
    op.create_table(
        "scanner_watchlist",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "symbol",
            sa.String(20),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "timeframe",
            sa.String(10),
            nullable=False,
        ),
        sa.Column(
            "asset_class",
            sa.String(20),
            nullable=False,
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
        sa.Column(
            "last_scanned_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    # Symbol length and format constraints
    op.create_check_constraint(
        "chk_scanner_watchlist_symbol_length",
        "scanner_watchlist",
        "LENGTH(symbol) BETWEEN 1 AND 20",
    )

    op.create_check_constraint(
        "chk_scanner_watchlist_symbol_format",
        "scanner_watchlist",
        "symbol ~ '^[A-Z0-9./^-]+$'",
    )

    # Timeframe validation
    op.create_check_constraint(
        "chk_scanner_watchlist_timeframe",
        "scanner_watchlist",
        "timeframe IN ('1M', '5M', '15M', '30M', '1H', '4H', '1D', '1W')",
    )

    # Asset class validation
    op.create_check_constraint(
        "chk_scanner_watchlist_asset_class",
        "scanner_watchlist",
        "asset_class IN ('forex', 'stock', 'index', 'crypto')",
    )

    # Index on enabled for efficient get_enabled_symbols() queries
    op.create_index(
        "idx_scanner_watchlist_enabled",
        "scanner_watchlist",
        ["enabled"],
        postgresql_using="btree",
    )

    # ===========================================
    # Table 2: scanner_config (singleton)
    # ===========================================
    op.create_table(
        "scanner_config",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "scan_interval_seconds",
            sa.Integer(),
            nullable=False,
            server_default="300",
        ),
        sa.Column(
            "batch_size",
            sa.Integer(),
            nullable=False,
            server_default="10",
        ),
        sa.Column(
            "session_filter_enabled",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
        sa.Column(
            "is_running",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "last_cycle_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    # Interval must be at least 60 seconds
    op.create_check_constraint(
        "chk_scanner_config_interval",
        "scanner_config",
        "scan_interval_seconds >= 60",
    )

    # Batch size must be 1-50
    op.create_check_constraint(
        "chk_scanner_config_batch_size",
        "scanner_config",
        "batch_size >= 1 AND batch_size <= 50",
    )

    # Insert singleton config row
    op.execute(
        """
        INSERT INTO scanner_config (id, scan_interval_seconds, batch_size, session_filter_enabled, is_running, updated_at)
        VALUES (gen_random_uuid(), 300, 10, true, false, NOW())
        """
    )

    # ===========================================
    # Table 3: scanner_history
    # ===========================================
    op.create_table(
        "scanner_history",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "cycle_started_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "cycle_ended_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "symbols_scanned",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "signals_generated",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "errors_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
        ),
    )

    # Status validation
    op.create_check_constraint(
        "chk_scanner_history_status",
        "scanner_history",
        "status IN ('COMPLETED', 'PARTIAL', 'FAILED', 'SKIPPED')",
    )

    # Index on cycle_started_at for efficient history queries
    op.create_index(
        "idx_scanner_history_cycle_started",
        "scanner_history",
        ["cycle_started_at"],
        postgresql_using="btree",
    )


def downgrade() -> None:
    """Drop scanner tables."""

    # Drop scanner_history
    op.drop_index("idx_scanner_history_cycle_started", table_name="scanner_history")
    op.drop_constraint("chk_scanner_history_status", "scanner_history", type_="check")
    op.drop_table("scanner_history")

    # Drop scanner_config
    op.drop_constraint("chk_scanner_config_batch_size", "scanner_config", type_="check")
    op.drop_constraint("chk_scanner_config_interval", "scanner_config", type_="check")
    op.drop_table("scanner_config")

    # Drop scanner_watchlist
    op.drop_index("idx_scanner_watchlist_enabled", table_name="scanner_watchlist")
    op.drop_constraint("chk_scanner_watchlist_asset_class", "scanner_watchlist", type_="check")
    op.drop_constraint("chk_scanner_watchlist_timeframe", "scanner_watchlist", type_="check")
    op.drop_constraint("chk_scanner_watchlist_symbol_format", "scanner_watchlist", type_="check")
    op.drop_constraint("chk_scanner_watchlist_symbol_length", "scanner_watchlist", type_="check")
    op.drop_table("scanner_watchlist")
