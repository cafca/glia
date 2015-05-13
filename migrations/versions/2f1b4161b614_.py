"""empty message

Revision ID: 2f1b4161b614
Revises: f3314c0fc02
Create Date: 2015-05-13 16:34:52.075324

"""

# revision identifiers, used by Alembic.
revision = '2f1b4161b614'
down_revision = 'f3314c0fc02'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('star', sa.Column('context_length', sa.Integer(), nullable=True))


def downgrade():
    op.drop_column('star', 'context_length')
