"""Add conversation and turn fields for multi-turn queries."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008_conversations"
down_revision = "0007_query_cache_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["app.users.id"], ondelete="SET NULL"),
        schema="app",
    )
    op.create_index(
        "ix_app_conversations_user_id",
        "conversations",
        ["user_id"],
        schema="app",
    )
    op.add_column(
        "query_runs",
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=True),
        schema="app",
    )
    op.add_column(
        "query_runs",
        sa.Column("turn_index", sa.Integer(), nullable=False, server_default="0"),
        schema="app",
    )
    op.create_foreign_key(
        "fk_app_query_runs_conversation_id",
        "query_runs",
        "conversations",
        ["conversation_id"],
        ["id"],
        source_schema="app",
        referent_schema="app",
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_app_query_runs_conversation_id",
        "query_runs",
        ["conversation_id"],
        schema="app",
    )


def downgrade() -> None:
    op.drop_index("ix_app_query_runs_conversation_id", schema="app")
    op.drop_constraint("fk_app_query_runs_conversation_id", "query_runs", schema="app")
    op.drop_column("query_runs", "turn_index", schema="app")
    op.drop_column("query_runs", "conversation_id", schema="app")
    op.drop_index("ix_app_conversations_user_id", schema="app")
    op.drop_table("conversations", schema="app")
