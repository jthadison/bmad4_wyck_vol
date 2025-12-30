"""add_performance_indexes_story_12_9

Revision ID: 78dd8d77a2bd
Revises: 63ba0d7b4aa9
Create Date: 2025-12-30 11:50:11.638557

"""
from collections.abc import Sequence
from typing import Union

# revision identifiers, used by Alembic.
revision: str = "78dd8d77a2bd"
down_revision: Union[str, Sequence[str], None] = "63ba0d7b4aa9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
