"""add_filtered_status_to_scanner_history

Revision ID: 20260204_filtered_status
Revises: 20260130_scanner_tables
Create Date: 2026-02-04

Add FILTERED status to scanner_history check constraint.

The FILTERED status is used when all symbols are skipped due to
session filtering or rate limiting, with none actually processed.
"""

from collections.abc import Sequence
from typing import Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260204_filtered_status"
down_revision: Union[str, Sequence[str], None] = "20260130_scanner_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add FILTERED to scanner_history status constraint."""
    # Drop existing constraint
    op.drop_constraint("chk_scanner_history_status", "scanner_history", type_="check")

    # Create new constraint with FILTERED added
    op.create_check_constraint(
        "chk_scanner_history_status",
        "scanner_history",
        "status IN ('COMPLETED', 'PARTIAL', 'FAILED', 'SKIPPED', 'FILTERED')",
    )


def downgrade() -> None:
    """Remove FILTERED from scanner_history status constraint."""
    # Drop constraint with FILTERED
    op.drop_constraint("chk_scanner_history_status", "scanner_history", type_="check")

    # Recreate original constraint
    op.create_check_constraint(
        "chk_scanner_history_status",
        "scanner_history",
        "status IN ('COMPLETED', 'PARTIAL', 'FAILED', 'SKIPPED')",
    )
