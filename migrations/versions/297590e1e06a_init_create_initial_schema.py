"""init: create initial schema"""
from alembic import op
import sqlalchemy as sa

revision = '001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Create companies table
    op.create_table(
        'companies',
        sa.Column('id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('code', sa.String(50), nullable=False, unique=True),
        sa.Column('country', sa.String(50), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False, default='IDR'),
        sa.Column('status', sa.String(20), nullable=False, default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code', name='companies_code_uk'),
    )
    op.create_index('idx_companies_status', 'companies', ['status'])

    # Create users table (identity only, no company_id)
    op.create_table(
        'users',
        sa.Column('id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('phone', sa.String(20), nullable=False, unique=True),
        sa.Column('is_system_admin', sa.Boolean(), nullable=False, default=False),
        sa.Column('last_login_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('phone', name='users_phone_uk'),
    )

    # Create user_company_roles table (junction: user → company + role)
    op.create_table(
        'user_company_roles',
        sa.Column('id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('company_id', sa.UUID(), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),  # 'admin', 'client_admin', 'employee'
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('user_id', 'company_id', name='user_company_roles_user_company_uk'),
    )
    op.create_index('idx_user_company_roles_company', 'user_company_roles', ['company_id'])
    op.create_index('idx_user_company_roles_role', 'user_company_roles', ['role', 'company_id'])

    # Create employees table
    op.create_table(
        'employees',
        sa.Column('id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('company_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False, unique=True),
        sa.Column('first_name', sa.String(100), nullable=False),
        sa.Column('last_name', sa.String(100), nullable=False),
        sa.Column('employee_number', sa.String(50), nullable=False),
        sa.Column('date_of_birth', sa.Date(), nullable=False),
        sa.Column('email', sa.String(100)),
        sa.Column('employment_status', sa.String(20), nullable=False, default='active'),  # 'active', 'on_leave', 'terminated'
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('company_id', 'employee_number', name='employees_company_number_uk'),
        sa.UniqueConstraint('user_id', name='employees_user_uk'),
    )
    op.create_index('idx_employees_company_status', 'employees', ['company_id', 'employment_status'])

    # Create contracts table (current contract only)
    op.create_table(
        'contracts',
        sa.Column('id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('company_id', sa.UUID(), nullable=False),
        sa.Column('employee_id', sa.UUID(), nullable=False, unique=True),  # 1:1 current contract
        sa.Column('contract_type', sa.String(50), nullable=False),  # 'permanent', 'fixed_term', 'project'
        sa.Column('job_title', sa.String(100), nullable=False),
        sa.Column('department', sa.String(100), nullable=False),
        sa.Column('base_salary', sa.Numeric(15, 2), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date()),  # NULL if permanent
        sa.Column('file_url', sa.String(500)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], ondelete='RESTRICT'),
        sa.UniqueConstraint('company_id', 'employee_id', name='contracts_company_employee_uk'),
    )
    op.create_index('idx_contracts_company_department', 'contracts', ['company_id', 'department'])

    # Create payslips table
    op.create_table(
        'payslips',
        sa.Column('id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('company_id', sa.UUID(), nullable=False),
        sa.Column('employee_id', sa.UUID(), nullable=False),
        sa.Column('period_start', sa.Date(), nullable=False),
        sa.Column('period_end', sa.Date(), nullable=False),
        sa.Column('payment_date', sa.Date(), nullable=False),
        sa.Column('full_name', sa.String(200), nullable=False),
        sa.Column('department', sa.String(100), nullable=False),
        sa.Column('position', sa.String(100), nullable=False),
        sa.Column('earnings', sa.JSON(), nullable=False, default={}),
        sa.Column('deductions', sa.JSON(), nullable=False, default={}),
        sa.Column('gross_salary', sa.Numeric(15, 2), nullable=False),
        sa.Column('total_deductions', sa.Numeric(15, 2), nullable=False),
        sa.Column('net_salary', sa.Numeric(15, 2), nullable=False),
        sa.Column('notes', sa.Text()),
        sa.Column('status', sa.String(20), nullable=False, default='draft'),  # 'draft', 'generated'
        sa.Column('file_url', sa.String(500)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], ondelete='RESTRICT'),
        sa.UniqueConstraint('company_id', 'employee_id', 'period_start', name='payslips_company_employee_period_uk'),
    )
    op.create_index('idx_payslips_company_status', 'payslips', ['company_id', 'status'])
    op.create_index('idx_payslips_employee_period', 'payslips', ['employee_id', 'period_start'], order_by=['period_start DESC'])

    # Create otp_tokens table
    op.create_table(
        'otp_tokens',
        sa.Column('id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('phone', sa.String(20), nullable=False),
        sa.Column('otp_hash', sa.String(255), nullable=False),
        sa.Column('failed_attempts', sa.Integer(), nullable=False, default=0),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_used', sa.Boolean(), nullable=False, default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )
    op.create_index('idx_otp_tokens_phone_expires', 'otp_tokens', ['phone', 'expires_at'])

    # Create payslip_upload_sessions table
    op.create_table(
        'payslip_upload_sessions',
        sa.Column('id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('upload_session_id', sa.UUID(), nullable=False, unique=True),
        sa.Column('company_id', sa.UUID(), nullable=False),
        sa.Column('file_path', sa.String(500), nullable=False),
        sa.Column('file_hash', sa.String(255), nullable=False),
        sa.Column('parent_upload_session_id', sa.UUID()),  # For reprocessing
        sa.Column('period_start', sa.Date(), nullable=False),
        sa.Column('period_end', sa.Date(), nullable=False),
        sa.Column('payment_date', sa.Date(), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, default='pending'),
        sa.Column('column_mapping', sa.JSON()),
        sa.Column('processing_state', sa.JSON()),
        sa.Column('result', sa.JSON()),  # summary of success/failed
        sa.Column('created_by', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
    )
    op.create_index('idx_payslip_uploads_company_status', 'payslip_upload_sessions', ['company_id', 'status'])
    op.create_index('idx_payslip_uploads_file_hash', 'payslip_upload_sessions', ['file_hash'])

    # Create payslip_upload_rows table
    op.create_table(
        'payslip_upload_rows',
        sa.Column('id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('upload_session_id', sa.UUID(), nullable=False),
        sa.Column('row_number', sa.Integer(), nullable=False),
        sa.Column('employee_number', sa.String(50), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),  # 'success', 'failed', 'skipped', 'pending'
        sa.Column('error_message', sa.Text()),
        sa.Column('payslip_id', sa.UUID()),
        sa.Column('raw_data', sa.JSON()),
        sa.Column('processed_at', sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['upload_session_id'], ['payslip_upload_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['payslip_id'], ['payslips.id'], ondelete='SET NULL'),
    )
    op.create_index('idx_payslip_upload_rows_session_status', 'payslip_upload_rows', ['upload_session_id', 'status'])

    # Create audit_logs table (optional but good for compliance)
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('company_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID()),
        sa.Column('entity_type', sa.String(50), nullable=False),
        sa.Column('entity_id', sa.UUID(), nullable=False),
        sa.Column('action', sa.String(20), nullable=False),  # 'create', 'read', 'update', 'delete'
        sa.Column('old_values', sa.JSON()),
        sa.Column('new_values', sa.JSON()),
        sa.Column('ip_address', sa.String(45)),
        sa.Column('user_agent', sa.String(500)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
    )
    op.create_index('idx_audit_logs_company_created', 'audit_logs', ['company_id', 'created_at'])
    op.create_index('idx_audit_logs_entity', 'audit_logs', ['entity_type', 'entity_id', 'created_at'])

def downgrade() -> None:
    op.drop_table('audit_logs')
    op.drop_table('payslip_upload_rows')
    op.drop_table('payslip_upload_sessions')
    op.drop_table('otp_tokens')
    op.drop_table('payslips')
    op.drop_table('contracts')
    op.drop_table('employees')
    op.drop_table('user_company_roles')
    op.drop_table('users')
    op.drop_table('companies')