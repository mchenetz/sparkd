"""recipe versions

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recipe_versions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("yaml_text", sa.String(), nullable=False),
        sa.Column(
            "source", sa.String(), nullable=False, server_default="manual"
        ),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_recipe_versions_name", "recipe_versions", ["name"]
    )


def downgrade() -> None:
    op.drop_index("ix_recipe_versions_name", table_name="recipe_versions")
    op.drop_table("recipe_versions")
