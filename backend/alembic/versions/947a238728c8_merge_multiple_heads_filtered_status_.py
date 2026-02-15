"""Merge multiple heads: filtered_status, audit_trail, phase_analysis

Revision ID: 947a238728c8
Revises: 20260204_filtered_status, 20260213_audit_trail, 20260214_phase_analysis
Create Date: 2026-02-15 01:12:30.515276

"""
from collections.abc import Sequence
from typing import Union

# revision identifiers, used by Alembic.
revision: str = "947a238728c8"
down_revision: Union[str, Sequence[str], None] = (
    "20260204_filtered_status",
    "20260213_audit_trail",
    "20260214_phase_analysis",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
