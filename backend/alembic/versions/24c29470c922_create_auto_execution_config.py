"""create_auto_execution_config

Revision ID: 24c29470c922
Revises: 20260125_signal_audit_trail
Create Date: 2026-01-26 08:57:40.105712

Story 19.14: Auto-Execution Configuration Backend

This migration creates the auto_execution_config table to store user preferences
for automatic signal execution without manual approval.

Key Features:
1. Global enable/disable with consent tracking
2. Configurable confidence threshold (default 85%)
3. Daily trade and risk limits
4. Circuit breaker for consecutive losses
5. Pattern-specific filtering (e.g., only Springs)
6. Symbol whitelist/blacklist
7. Emergency kill switch

Safety Features:
- Explicit opt-in required (consent_given_at)
- IP address logging for consent
- Kill switch to immediately stop all auto-execution
- Circuit breaker to prevent runaway losses
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "24c29470c922"
down_revision: Union[str, Sequence[str], None] = "20260125_signal_audit_trail"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create auto_execution_config table."""

    op.create_table(
        "auto_execution_config",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "min_confidence",
            sa.DECIMAL(5, 2),
            nullable=False,
            server_default="85.00",
        ),
        sa.Column(
            "max_trades_per_day",
            sa.Integer(),
            nullable=False,
            server_default="10",
        ),
        sa.Column(
            "max_risk_per_day",
            sa.DECIMAL(5, 2),
            nullable=True,
        ),
        sa.Column(
            "circuit_breaker_losses",
            sa.Integer(),
            nullable=False,
            server_default="3",
        ),
        sa.Column(
            "enabled_patterns",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default=sa.text("ARRAY['SPRING', 'SOS', 'LPS']::VARCHAR[]"),
        ),
        sa.Column(
            "symbol_whitelist",
            postgresql.ARRAY(sa.String()),
            nullable=True,
        ),
        sa.Column(
            "symbol_blacklist",
            postgresql.ARRAY(sa.String()),
            nullable=True,
        ),
        sa.Column(
            "kill_switch_active",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "consent_given_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "consent_ip_address",
            sa.String(45),
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
        # Foreign key to users table
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_auto_execution_config_user",
            ondelete="CASCADE",
        ),
    )

    # Add check constraints for validation
    op.create_check_constraint(
        "chk_min_confidence_range",
        "auto_execution_config",
        "min_confidence >= 60 AND min_confidence <= 100",
    )

    op.create_check_constraint(
        "chk_max_trades_range",
        "auto_execution_config",
        "max_trades_per_day >= 1 AND max_trades_per_day <= 50",
    )

    op.create_check_constraint(
        "chk_max_risk_range",
        "auto_execution_config",
        "max_risk_per_day IS NULL OR (max_risk_per_day > 0 AND max_risk_per_day <= 10)",
    )

    op.create_check_constraint(
        "chk_circuit_breaker_range",
        "auto_execution_config",
        "circuit_breaker_losses >= 1 AND circuit_breaker_losses <= 10",
    )

    # Note: No additional index needed on user_id as it's the primary key


def downgrade() -> None:
    """Drop auto_execution_config table."""

    op.drop_constraint("chk_circuit_breaker_range", "auto_execution_config", type_="check")
    op.drop_constraint("chk_max_risk_range", "auto_execution_config", type_="check")
    op.drop_constraint("chk_max_trades_range", "auto_execution_config", type_="check")
    op.drop_constraint("chk_min_confidence_range", "auto_execution_config", type_="check")
    op.drop_table("auto_execution_config")
