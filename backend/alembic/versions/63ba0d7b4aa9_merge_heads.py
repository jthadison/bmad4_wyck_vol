"""merge_heads

Revision ID: 63ba0d7b4aa9
Revises: 022_add_regression_tables, 20251229_210055
Create Date: 2025-12-30 11:50:00.570410

"""
from collections.abc import Sequence
from typing import Union

# revision identifiers, used by Alembic.
revision: str = "63ba0d7b4aa9"
down_revision: Union[str, Sequence[str], None] = (
    "022_add_regression_tables",
    "20251229_210055",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
