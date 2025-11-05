from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "1edbf8bc5766"
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Make business_id nullable in services table
    op.alter_column('services', 'business_id', nullable=True)

def downgrade() -> None:
    # Make business_id not nullable (revert)
    op.alter_column('services', 'business_id', nullable=False)