"""Rename profile to blog

Revision ID: 79c14eaf5c9
Revises: 34be968b93cb
Create Date: 2015-05-20 14:17:44.420295

"""

# revision identifiers, used by Alembic.
revision = '79c14eaf5c9'
down_revision = '34be968b93cb'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.alter_column('identity', 'profile_id', new_column_name='blog_id')


def downgrade():
    op.alter_column('identity', 'blog_id', new_column_name='profile_id')
