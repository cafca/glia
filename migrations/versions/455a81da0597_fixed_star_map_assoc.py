"""Fixed Star-Map assoc

Revision ID: 455a81da0597
Revises: 217b54d2d8e1
Create Date: 2015-06-01 15:15:31.494379

"""

# revision identifiers, used by Alembic.
revision = '455a81da0597'
down_revision = '217b54d2d8e1'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.drop_table('starmap_index')
    op.add_column('star', sa.Column('starmap_id', sa.String(length=32), nullable=True))
    op.create_foreign_key("fk_star_starmap", 'star', 'starmap', ['starmap_id'], ['id'])


def downgrade():
    op.drop_constraint("fk_star_starmap", 'star', type_='foreignkey')
    op.drop_column('star', 'starmap_id')
    op.create_table('starmap_index',
        sa.Column('starmap_id', sa.VARCHAR(length=32), autoincrement=False, nullable=True),
        sa.Column('star_id', sa.VARCHAR(length=32), autoincrement=False, nullable=True),
        sa.ForeignKeyConstraint(['star_id'], [u'star.id'], name=u'starmap_index_star_id_fkey'),
        sa.ForeignKeyConstraint(['starmap_id'], [u'starmap.id'], name=u'starmap_index_starmap_id_fkey')
    )
