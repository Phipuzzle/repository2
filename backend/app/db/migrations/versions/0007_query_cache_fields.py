"""Add query cache metadata to QueryRun."""

import sqlalchemy as sa
from alembic import op

revision = "0007_query_cache_fields"
down_revision = "0006_semantic_layer"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "query_runs",
        sa.Column("cache_key", sa.String(255), nullable=True),
        schema="app",
    )
    op.add_column(
        "query_runs",
        sa.Column("data_version", sa.String(64), nullable=True),
        schema="app",
    )
    op.add_column(
        "query_runs",
        sa.Column("cache_expires_at", sa.DateTime(timezone=True), nullable=True),
        schema="app",
    )
    op.create_index(
        "ix_app_query_runs_cache_key",
        "query_runs",
        ["cache_key"],
        schema="app",
    )


def downgrade() -> None:
    op.drop_index("ix_app_query_runs_cache_key", schema="app")
    op.drop_column("query_runs", "cache_expires_at", schema="app")
    op.drop_column("query_runs", "data_version", schema="app")
    op.drop_column("query_runs", "cache_key", schema="app")
