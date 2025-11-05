from alembic import op
import sqlalchemy as sa

revision = "7a4df91f327c"
down_revision = "1edbf8bc5766"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('users', sa.Column('barber_bio', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('barber_shop_name', sa.String(), nullable=True))
    op.add_column('users', sa.Column('barber_shop_address', sa.String(), nullable=True))

def downgrade() -> None:
    op.drop_column('users', 'barber_bio')
    op.drop_column('users', 'barber_shop_name')
    op.drop_column('users', 'barber_shop_address')
