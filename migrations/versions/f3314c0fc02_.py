"""empty message

Revision ID: f3314c0fc02
Revises: None
Create Date: 2015-05-12 15:45:20.537535

"""

# revision identifiers, used by Alembic.
revision = 'f3314c0fc02'
down_revision = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.create_table('planet',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('title', sa.Text(), nullable=True),
    sa.Column('kind', sa.String(length=32), nullable=True),
    sa.Column('created', sa.DateTime(), nullable=True),
    sa.Column('modified', sa.DateTime(), nullable=True),
    sa.Column('source', sa.String(length=128), nullable=True),
    sa.Column('state', sa.Integer(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('starmap',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('modified', sa.DateTime(), nullable=True),
    sa.Column('kind', sa.String(length=16), nullable=True),
    sa.Column('state', sa.Integer(), nullable=True),
    sa.Column('author_id', sa.String(length=32), nullable=True),
    sa.ForeignKeyConstraint(['author_id'], ['persona.id'], name='fk_author_id', use_alter=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('vesicle',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('message_type', sa.String(length=32), nullable=True),
    sa.Column('payload', sa.Text(), nullable=True),
    sa.Column('signature', sa.Text(), nullable=True),
    sa.Column('created', sa.DateTime(), nullable=True),
    sa.Column('keycrypt', sa.Text(), nullable=True),
    sa.Column('enc', sa.String(length=16), nullable=True),
    sa.Column('_send_attributes', sa.Text(), nullable=True),
    sa.Column('handled', sa.Boolean(), nullable=True),
    sa.Column('author_id', sa.String(length=32), nullable=True),
    sa.ForeignKeyConstraint(['author_id'], ['persona.id'], name='fk_author_id', use_alter=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('user',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('email', sa.String(length=128), nullable=True),
    sa.Column('created', sa.DateTime(), nullable=True),
    sa.Column('modified', sa.DateTime(), nullable=True),
    sa.Column('pw_hash', sa.String(length=64), nullable=True),
    sa.Column('active', sa.Boolean(), nullable=True),
    sa.Column('authenticated', sa.Boolean(), nullable=True),
    sa.Column('signup_code', sa.String(length=128), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('tag',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('name', sa.String(length=32), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('linked_picture_planet',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('url', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['id'], ['planet.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('tag_planet',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('tag_id', sa.String(length=32), nullable=True),
    sa.ForeignKeyConstraint(['id'], ['planet.id'], ),
    sa.ForeignKeyConstraint(['tag_id'], ['tag.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('souma',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('crypt_private', sa.Text(), nullable=True),
    sa.Column('crypt_public', sa.Text(), nullable=True),
    sa.Column('sign_private', sa.Text(), nullable=True),
    sa.Column('sign_public', sa.Text(), nullable=True),
    sa.Column('starmap_id', sa.String(length=32), nullable=True),
    sa.Column('_version_string', sa.String(length=32), nullable=True),
    sa.ForeignKeyConstraint(['starmap_id'], ['starmap.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('picture_planet',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('filename', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['id'], ['planet.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('identity',
    sa.Column('_stub', sa.Boolean(), nullable=True),
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('kind', sa.String(length=32), nullable=True),
    sa.Column('created', sa.DateTime(), nullable=True),
    sa.Column('modified', sa.DateTime(), nullable=True),
    sa.Column('username', sa.String(length=80), nullable=True),
    sa.Column('crypt_private', sa.Text(), nullable=True),
    sa.Column('crypt_public', sa.Text(), nullable=True),
    sa.Column('sign_private', sa.Text(), nullable=True),
    sa.Column('sign_public', sa.Text(), nullable=True),
    sa.Column('color', sa.String(length=6), nullable=True),
    sa.Column('profile_id', sa.String(length=32), nullable=True),
    sa.ForeignKeyConstraint(['profile_id'], ['starmap.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('planet_vesicles',
    sa.Column('planet_id', sa.String(length=32), nullable=True),
    sa.Column('vesicle_id', sa.String(length=32), nullable=True),
    sa.ForeignKeyConstraint(['planet_id'], ['planet.id'], ),
    sa.ForeignKeyConstraint(['vesicle_id'], ['vesicle.id'], )
    )
    op.create_table('link_planet',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('url', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['id'], ['planet.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('starmap_vesicles',
    sa.Column('starmap_id', sa.String(length=32), nullable=True),
    sa.Column('vesicle_id', sa.String(length=32), nullable=True),
    sa.ForeignKeyConstraint(['starmap_id'], ['starmap.id'], ),
    sa.ForeignKeyConstraint(['vesicle_id'], ['vesicle.id'], )
    )
    op.create_table('text_planet',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('text', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['id'], ['planet.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('identity_vesicles',
    sa.Column('identity_id', sa.String(length=32), nullable=True),
    sa.Column('vesicle_id', sa.String(length=32), nullable=True),
    sa.ForeignKeyConstraint(['identity_id'], ['identity.id'], ),
    sa.ForeignKeyConstraint(['vesicle_id'], ['vesicle.id'], )
    )
    op.create_table('star',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('text', sa.Text(), nullable=True),
    sa.Column('kind', sa.String(length=32), nullable=True),
    sa.Column('created', sa.DateTime(), nullable=True),
    sa.Column('modified', sa.DateTime(), nullable=True),
    sa.Column('state', sa.Integer(), nullable=True),
    sa.Column('author_id', sa.String(length=32), nullable=True),
    sa.Column('parent_id', sa.String(length=32), nullable=True),
    sa.ForeignKeyConstraint(['author_id'], ['identity.id'], ),
    sa.ForeignKeyConstraint(['parent_id'], ['star.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('persona',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('email', sa.String(length=120), nullable=True),
    sa.Column('auth', sa.String(length=32), nullable=True),
    sa.Column('session_id', sa.String(length=32), nullable=True),
    sa.Column('last_connected', sa.DateTime(), nullable=True),
    sa.Column('index_id', sa.String(length=32), nullable=True),
    sa.Column('myelin_offset', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['id'], ['identity.id'], ),
    sa.ForeignKeyConstraint(['index_id'], ['starmap.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('keycrypts',
    sa.Column('vesicle_id', sa.String(length=32), nullable=True),
    sa.Column('recipient_id', sa.String(length=32), nullable=True),
    sa.ForeignKeyConstraint(['recipient_id'], ['persona.id'], ),
    sa.ForeignKeyConstraint(['vesicle_id'], ['vesicle.id'], )
    )
    op.create_table('movement',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('state', sa.Integer(), nullable=True),
    sa.Column('admin_id', sa.String(length=32), nullable=True),
    sa.ForeignKeyConstraint(['admin_id'], ['persona.id'], ),
    sa.ForeignKeyConstraint(['id'], ['identity.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('star_vesicles',
    sa.Column('star_id', sa.String(length=32), nullable=True),
    sa.Column('vesicle_id', sa.String(length=32), nullable=True),
    sa.ForeignKeyConstraint(['star_id'], ['star.id'], ),
    sa.ForeignKeyConstraint(['vesicle_id'], ['vesicle.id'], )
    )
    op.create_table('planet_association',
    sa.Column('star_id', sa.String(length=32), nullable=False),
    sa.Column('planet_id', sa.String(length=32), nullable=False),
    sa.Column('author_id', sa.String(length=32), nullable=True),
    sa.ForeignKeyConstraint(['author_id'], ['persona.id'], ),
    sa.ForeignKeyConstraint(['planet_id'], ['planet.id'], ),
    sa.ForeignKeyConstraint(['star_id'], ['star.id'], ),
    sa.PrimaryKeyConstraint('star_id', 'planet_id')
    )
    op.create_table('starmap_index',
    sa.Column('starmap_id', sa.String(length=32), nullable=True),
    sa.Column('star_id', sa.String(length=32), nullable=True),
    sa.ForeignKeyConstraint(['star_id'], ['star.id'], ),
    sa.ForeignKeyConstraint(['starmap_id'], ['starmap.id'], )
    )
    op.create_table('contacts',
    sa.Column('left_id', sa.String(length=32), nullable=True),
    sa.Column('right_id', sa.String(length=32), nullable=True),
    sa.ForeignKeyConstraint(['left_id'], ['persona.id'], ),
    sa.ForeignKeyConstraint(['right_id'], ['persona.id'], ),
    sa.UniqueConstraint('left_id', 'right_id', name='_uc_contacts')
    )
    op.create_table('persona_association',
    sa.Column('left_id', sa.String(length=32), nullable=False),
    sa.Column('right_id', sa.String(length=32), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=True),
    sa.ForeignKeyConstraint(['left_id'], ['user.id'], ),
    sa.ForeignKeyConstraint(['right_id'], ['persona.id'], ),
    sa.PrimaryKeyConstraint('left_id', 'right_id')
    )
    op.create_table('movement_vesicles',
    sa.Column('movement_id', sa.String(length=32), nullable=True),
    sa.Column('vesicle_id', sa.String(length=32), nullable=True),
    sa.ForeignKeyConstraint(['movement_id'], ['movement.id'], ),
    sa.ForeignKeyConstraint(['vesicle_id'], ['vesicle.id'], )
    )
    op.create_table('movements_followed',
    sa.Column('persona_id', sa.String(length=32), nullable=True),
    sa.Column('movement_id', sa.String(length=32), nullable=True),
    sa.ForeignKeyConstraint(['movement_id'], ['movement.id'], ),
    sa.ForeignKeyConstraint(['persona_id'], ['persona.id'], )
    )
    op.create_table('members',
    sa.Column('movement_id', sa.String(length=32), nullable=True),
    sa.Column('persona_id', sa.String(length=32), nullable=True),
    sa.ForeignKeyConstraint(['movement_id'], ['movement.id'], ),
    sa.ForeignKeyConstraint(['persona_id'], ['persona.id'], )
    )
    op.create_table('movementmember_association',
    sa.Column('movement_id', sa.String(length=32), nullable=False),
    sa.Column('persona_id', sa.String(length=32), nullable=False),
    sa.Column('role', sa.String(length=16), nullable=True),
    sa.Column('created', sa.DateTime(), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('active', sa.Boolean(), nullable=True),
    sa.Column('last_seen', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['movement_id'], ['movement.id'], ),
    sa.ForeignKeyConstraint(['persona_id'], ['persona.id'], ),
    sa.PrimaryKeyConstraint('movement_id', 'persona_id')
    )
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('movementmember_association')
    op.drop_table('members')
    op.drop_table('movements_followed')
    op.drop_table('movement_vesicles')
    op.drop_table('persona_association')
    op.drop_table('contacts')
    op.drop_table('starmap_index')
    op.drop_table('planet_association')
    op.drop_table('star_vesicles')
    op.drop_table('movement')
    op.drop_table('keycrypts')
    op.drop_table('persona')
    op.drop_table('star')
    op.drop_table('identity_vesicles')
    op.drop_table('text_planet')
    op.drop_table('starmap_vesicles')
    op.drop_table('link_planet')
    op.drop_table('planet_vesicles')
    op.drop_table('identity')
    op.drop_table('picture_planet')
    op.drop_table('souma')
    op.drop_table('tag_planet')
    op.drop_table('linked_picture_planet')
    op.drop_table('tag')
    op.drop_table('user')
    op.drop_table('vesicle')
    op.drop_table('starmap')
    op.drop_table('planet')
    ### end Alembic commands ###
