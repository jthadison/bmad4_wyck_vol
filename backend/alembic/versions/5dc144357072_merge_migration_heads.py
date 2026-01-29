"""merge migration heads

Revision ID: 5dc144357072
Revises: 20260125_user_watchlist, 24c29470c922
Create Date: 2026-01-29 16:10:56.403341

"""
from collections.abc import Sequence
from typing import Union

# revision identifiers, used by Alembic.
revision: str = "5dc144357072"
down_revision: Union[str, Sequence[str], None] = ("20260125_user_watchlist", "24c29470c922")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
