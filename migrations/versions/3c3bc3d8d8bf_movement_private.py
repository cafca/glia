"""Movement.private

Revision ID: 3c3bc3d8d8bf
Revises: 65c1f1d7cd6
Create Date: 2015-06-24 18:33:47.868115

"""

# revision identifiers, used by Alembic.
revision = '3c3bc3d8d8bf'
down_revision = '65c1f1d7cd6'

from alembic import op
import sqlalchemy as sa


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.add_column('movement', sa.Column('private', sa.Boolean(), nullable=True))
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('movement', 'private')
    ### end Alembic commands ###
