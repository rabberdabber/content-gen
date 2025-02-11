"""allow model and prompt columns in images table to be null

Revision ID: d260054c5be6
Revises: dbdee1bed036
Create Date: 2024-12-15 11:27:28.684425

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = 'd260054c5be6'
down_revision = 'dbdee1bed036'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('image', 'prompt',
               existing_type=sa.VARCHAR(),
               nullable=True)
    op.alter_column('image', 'model',
               existing_type=sa.VARCHAR(length=20),
               nullable=True)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('image', 'model',
               existing_type=sa.VARCHAR(length=20),
               nullable=False)
    op.alter_column('image', 'prompt',
               existing_type=sa.VARCHAR(),
               nullable=False)
    # ### end Alembic commands ###
