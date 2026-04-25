"""initial schema

Revision ID: 0001
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "boxes",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        sa.Column("host", sa.String(), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False, server_default="22"),
        sa.Column("user", sa.String(), nullable=False),
        sa.Column("ssh_key_path", sa.String(), nullable=True),
        sa.Column("use_agent", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("repo_path", sa.String(), nullable=False, server_default="~/spark-vllm-docker"),
        sa.Column("tags_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("capabilities_json", sa.JSON(), nullable=True),
        sa.Column("capabilities_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_table(
        "launches",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("box_id", sa.String(), sa.ForeignKey("boxes.id"), nullable=False),
        sa.Column("recipe_name", sa.String(), nullable=False),
        sa.Column("recipe_snapshot_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("mods_json", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("container_id", sa.String(), nullable=True),
        sa.Column("command", sa.String(), nullable=False),
        sa.Column("log_path", sa.String(), nullable=True),
        sa.Column("started_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("stopped_at", sa.DateTime(), nullable=True),
        sa.Column("exit_info_json", sa.JSON(), nullable=True),
    )
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ts", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("actor", sa.String(), nullable=False, server_default="local"),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("target", sa.String(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("launches")
    op.drop_table("boxes")
