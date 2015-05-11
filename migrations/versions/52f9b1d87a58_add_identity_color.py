"""Add Identity.color

Revision ID: 52f9b1d87a58
Revises: 47caa8c69f2d
Create Date: 2015-05-11 16:40:39.814361

"""

# revision identifiers, used by Alembic.
revision = '52f9b1d87a58'
down_revision = '47caa8c69f2d'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('identity', sa.Column('color', sa.String(length=6), nullable=True))


def downgrade():
    op.drop_column('identity', 'color')
