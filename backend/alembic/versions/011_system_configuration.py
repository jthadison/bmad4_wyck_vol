"""Add system_configuration table

Revision ID: 011_system_configuration
Revises: 010_audit_trail_enhancements
Create Date: 2025-12-09

"""
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMPTZ, UUID

from alembic import op

# revision identifiers, used by Alembic.
revision = "011_system_configuration"
down_revision = "010_audit_trail_enhancements"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create system_configuration table for storing system parameter settings."""
    # Create system_configuration table
    op.create_table(
        "system_configuration",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("configuration_json", JSONB, nullable=False),
        sa.Column("applied_at", TIMESTAMPTZ, nullable=False, server_default=sa.text("NOW()")),
        sa.Column("applied_by", sa.String(100), nullable=True),
        sa.Column("created_at", TIMESTAMPTZ, nullable=False, server_default=sa.text("NOW()")),
    )

    # Create index for version-based queries (get latest version)
    op.create_index(
        "idx_config_version",
        "system_configuration",
        ["version"],
        postgresql_ops={"version": "DESC"},
    )

    # Create index for applied_at queries
    op.create_index(
        "idx_config_applied_at",
        "system_configuration",
        ["applied_at"],
        postgresql_ops={"applied_at": "DESC"},
    )

    # Insert default configuration
    op.execute(
        """
        INSERT INTO system_configuration (version, configuration_json, applied_by)
        VALUES (
            1,
            '{
                "id": "00000000-0000-0000-0000-000000000001",
                "version": 1,
                "volume_thresholds": {
                    "spring_volume_min": "0.7",
                    "spring_volume_max": "1.0",
                    "sos_volume_min": "2.0",
                    "lps_volume_min": "0.5",
                    "utad_volume_max": "0.7"
                },
                "risk_limits": {
                    "max_risk_per_trade": "2.0",
                    "max_campaign_risk": "5.0",
                    "max_portfolio_heat": "10.0"
                },
                "cause_factors": {
                    "min_cause_factor": "2.0",
                    "max_cause_factor": "3.0"
                },
                "pattern_confidence": {
                    "min_spring_confidence": 70,
                    "min_sos_confidence": 70,
                    "min_lps_confidence": 70,
                    "min_utad_confidence": 70
                },
                "applied_at": "2025-12-09T00:00:00Z",
                "applied_by": "system"
            }',
            'system'
        )
    """
    )


def downgrade() -> None:
    """Drop system_configuration table."""
    op.drop_index("idx_config_applied_at", table_name="system_configuration")
    op.drop_index("idx_config_version", table_name="system_configuration")
    op.drop_table("system_configuration")
