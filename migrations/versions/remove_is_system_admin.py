"""Remove is_system_admin column from users table

Revision ID: remove_is_system_admin
Revises: add_join_date_bank_account
Create Date: 2026-03-27 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = 'remove_is_system_admin'
down_revision = 'add_join_date_bank_account'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column('users', 'is_system_admin')


def downgrade():
    op.add_column('users', sa.Column('is_system_admin', sa.Boolean(), nullable=False, server_default='false'))
