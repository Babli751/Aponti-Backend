from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision = "1edbf8bc5766"
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    # first_name ve last_name zaten var, eklemeye gerek yok
    op.drop_column('users', 'full_name')

def downgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    columns = [c["name"] for c in inspector.get_columns("users")]

    # full_name yoksa ekle
    if "full_name" not in columns:
        op.add_column("users", sa.Column("full_name", sa.String(), nullable=True))

    # last_name varsa sil
    if "last_name" in columns:
        op.drop_column("users", "last_name")

    # first_name varsa sil
    if "first_name" in columns:
        op.drop_column("users", "first_name")
