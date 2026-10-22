"""Add evaluation candidate table."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0009_evaluation_candidates"
down_revision = "0008_conversations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "evaluation_candidates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("feedback_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("reviewed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("feedback_id", name="uq_evaluation_candidates_feedback"),
        schema="metadata",
    )
    op.create_index(
        "ix_metadata_evaluation_candidates_feedback",
        "evaluation_candidates",
        ["feedback_id"],
        schema="metadata",
    )


def downgrade() -> None:
    op.drop_index("ix_metadata_evaluation_candidates_feedback", schema="metadata")
    op.drop_table("evaluation_candidates", schema="metadata")
