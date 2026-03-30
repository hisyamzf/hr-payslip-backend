"""Add join_date and bank_account to employees

Revision ID: add_join_date_bank_account
Revises: 059ea706839b
Create Date: 2025-03-26 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = 'add_join_date_bank_account'
down_revision = '059ea706839b'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('employees', sa.Column('join_date', sa.Date(), nullable=True))
    op.add_column('employees', sa.Column('bank_account', sa.String(100), nullable=True))
    
    op.execute("""
        UPDATE employees 
        SET join_date = date_of_birth 
        WHERE join_date IS NULL
    """)
    
    op.alter_column('employees', 'join_date', nullable=False)


def downgrade():
    op.drop_column('employees', 'bank_account')
    op.drop_column('employees', 'join_date')
