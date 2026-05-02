"""box cluster_ip

Revision ID: 0005
Revises: 0004
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "boxes",
        sa.Column("cluster_ip", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("boxes", "cluster_ip")
