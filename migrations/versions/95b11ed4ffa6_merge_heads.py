"""merge_heads

Revision ID: 95b11ed4ffa6
Revises: add_refresh_tokens, remove_is_system_admin
Create Date: 2026-03-27 13:59:21.331038

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '95b11ed4ffa6'
down_revision: Union[str, Sequence[str], None] = ('add_refresh_tokens', 'remove_is_system_admin')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
