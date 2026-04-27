"""launch cluster_name

Revision ID: 0004
Revises: 0003
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "launches",
        sa.Column("cluster_name", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("launches", "cluster_name")
