"""Add semantic metric and dimension dictionary tables."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006_semantic_layer"
down_revision = "0005_metadata_embeddings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "semantic_metrics",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False, unique=True),
        sa.Column(
            "aliases",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("formula", sa.Text(), nullable=False),
        sa.Column("qualifier", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("default_grain", sa.String(40), nullable=False, server_default=sa.text("''")),
        sa.Column("chart_type", sa.String(24), nullable=False, server_default="bar"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        schema="metadata",
    )
    op.create_table(
        "semantic_dimensions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False, unique=True),
        sa.Column(
            "aliases",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("table_name", sa.String(63), nullable=False),
        sa.Column("column_name", sa.String(63), nullable=False),
        sa.Column("dimension_type", sa.String(24), nullable=False, server_default="categorical"),
        sa.Column("time_grain", sa.String(24), nullable=True),
        schema="metadata",
    )
    op.create_table(
        "semantic_mappings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("metric_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dimension_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["metric_id"],
            ["metadata.semantic_metrics.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["dimension_id"],
            ["metadata.semantic_dimensions.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("metric_id", "dimension_id", name="uq_semantic_mapping_ref"),
        schema="metadata",
    )
    op.create_index(
        "ix_metadata_semantic_mappings_metric",
        "semantic_mappings",
        ["metric_id"],
        schema="metadata",
    )
    op.create_index(
        "ix_metadata_semantic_mappings_dimension",
        "semantic_mappings",
        ["dimension_id"],
        schema="metadata",
    )


def downgrade() -> None:
    op.drop_table("semantic_mappings", schema="metadata")
    op.drop_table("semantic_dimensions", schema="metadata")
    op.drop_table("semantic_metrics", schema="metadata")
