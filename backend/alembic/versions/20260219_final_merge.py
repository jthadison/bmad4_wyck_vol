"""Merge all remaining heads into a single head

Revision ID: 20260219_final_merge
Revises: 947a238728c8, 20260218_widen_pattern_type, 20260214_correlation_ids
Create Date: 2026-02-19

Merges three parallel branches:
- 947a238728c8: filtered_status + audit_trail merge
- 20260218_widen_pattern_type: audit trail fields + pattern/phase signal columns
- 20260214_correlation_ids: scanner history correlation IDs
"""

from collections.abc import Sequence
from typing import Union

# revision identifiers, used by Alembic.
revision: str = "20260219_final_merge"
down_revision: Union[str, Sequence[str], None] = (
    "947a238728c8",
    "20260218_widen_pattern_type",
    "20260214_correlation_ids",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Merge only — no schema changes."""
    pass


def downgrade() -> None:
    """Merge only — no schema changes."""
    pass
