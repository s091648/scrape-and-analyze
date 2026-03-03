"""extend_auth_users

Revision ID: 06_extend_auth_users
Revises: 05_normalize_tags
Create Date: 2026-03-03
"""
from alembic import op
import sqlalchemy as sa

revision = '06_extend_auth_users'
down_revision = '05_normalize_tags'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns
    op.add_column('users', sa.Column('email', sa.String(255)), schema='auth')
    op.add_column('users', sa.Column('name', sa.String(255)), schema='auth')
    op.add_column('users', sa.Column('google_id', sa.String(255)), schema='auth')
    op.add_column('users', sa.Column('is_allowed', sa.Boolean(), nullable=False,
                                     server_default='true'), schema='auth')
    op.add_column('users', sa.Column('updated_at', sa.DateTime(timezone=True),
                                     nullable=False,
                                     server_default=sa.text('NOW()')), schema='auth')

    # Make username and hashed_password nullable (OAuth users have neither)
    op.alter_column('users', 'username', nullable=True, schema='auth')
    op.alter_column('users', 'hashed_password', nullable=True, schema='auth')

    # Change role default from 'admin' to 'user' (safer for new registrations)
    op.alter_column('users', 'role', server_default='user', schema='auth')

    # Unique constraints
    op.create_unique_constraint('uq_users_email', 'users', ['email'], schema='auth')
    op.create_unique_constraint('uq_users_google_id', 'users', ['google_id'], schema='auth')

    # At least one identifier required
    op.create_check_constraint(
        'chk_has_identifier',
        'users',
        'username IS NOT NULL OR email IS NOT NULL',
        schema='auth'
    )
    # If username is set, password must also be set
    op.create_check_constraint(
        'chk_credentials_complete',
        'users',
        'username IS NULL OR hashed_password IS NOT NULL',
        schema='auth'
    )


def downgrade() -> None:
    op.drop_constraint('chk_credentials_complete', 'users', schema='auth', type_='check')
    op.drop_constraint('chk_has_identifier', 'users', schema='auth', type_='check')
    op.drop_constraint('uq_users_google_id', 'users', schema='auth', type_='unique')
    op.drop_constraint('uq_users_email', 'users', schema='auth', type_='unique')
    op.alter_column('users', 'role', server_default='admin', schema='auth')
    op.alter_column('users', 'hashed_password', nullable=False, schema='auth')
    op.alter_column('users', 'username', nullable=False, schema='auth')
    op.drop_column('users', 'updated_at', schema='auth')
    op.drop_column('users', 'is_allowed', schema='auth')
    op.drop_column('users', 'google_id', schema='auth')
    op.drop_column('users', 'name', schema='auth')
    op.drop_column('users', 'email', schema='auth')
