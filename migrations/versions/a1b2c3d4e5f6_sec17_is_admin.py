"""SEC-17: add is_admin to user table

Revision ID: a1b2c3d4e5f6
Revises: 545890bb638f
Create Date: 2026-10-19

Server-side admin role for mentor verification (SEC-17).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '545890bb638f'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_admin', sa.Boolean(),
                                      nullable=False, server_default='0'))


def downgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('is_admin')
