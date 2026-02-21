"""seed_admin

Revision ID: da18741c2135
Revises: f9a54cc49040
Create Date: 2026-02-21 00:47:29.246625

"""
import os
import logging
from alembic import op

revision = 'da18741c2135'
down_revision = 'f9a54cc49040'
branch_labels = None
depends_on = None

log = logging.getLogger('alembic.runtime.migration')


def upgrade() -> None:
    admin_password = os.environ.get('ADMIN_PASSWORD')
    if not admin_password:
        log.warning("ADMIN_PASSWORD not set — skipping admin user seeding")
        return

    import bcrypt
    hashed = bcrypt.hashpw(admin_password.encode(), bcrypt.gensalt()).decode()
    op.execute(
        f"INSERT INTO auth.users (id, username, hashed_password, role) "
        f"VALUES (gen_random_uuid(), 'admin', '{hashed}', 'admin') "
        f"ON CONFLICT (username) DO NOTHING"
    )


def downgrade() -> None:
    op.execute("DELETE FROM auth.users WHERE username = 'admin'")
