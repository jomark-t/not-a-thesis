"""change user_type to non-unique

Revision ID: 4a475c666da5
Revises: 2a7373e245af
Create Date: 2018-06-12 18:11:49.470948

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4a475c666da5'
down_revision = '2a7373e245af'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index('ix_user_user_type', table_name='user')
    op.create_index(op.f('ix_user_user_type'), 'user', ['user_type'], unique=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_user_user_type'), table_name='user')
    op.create_index('ix_user_user_type', 'user', ['user_type'], unique=1)
    # ### end Alembic commands ###
