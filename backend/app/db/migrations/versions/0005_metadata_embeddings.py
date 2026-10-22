"""Add metadata embedding table backed by pgvector."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.db.vector import VectorType

revision = "0005_metadata_embeddings"
down_revision = "0004_demo_query_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "embeddings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("content_kind", sa.String(24), nullable=False),
        sa.Column("ref_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("embedding", VectorType(512), nullable=False),
        sa.Column("model_id", sa.String(255), nullable=False),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("content_kind", "ref_id", "version", name="uq_metadata_embeddings_ref"),
        schema="metadata",
    )
    op.create_index(
        "ix_metadata_embeddings_ref_id",
        "embeddings",
        ["ref_id"],
        schema="metadata",
    )
    op.execute(
        "CREATE INDEX ix_metadata_embeddings_vector "
        "ON metadata.embeddings USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS metadata.ix_metadata_embeddings_vector")
    op.drop_index("ix_metadata_embeddings_ref_id", schema="metadata")
    op.drop_table("embeddings", schema="metadata")
