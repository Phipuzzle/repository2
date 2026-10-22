"""Add model token usage to query runs."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0010_query_run_usage"
down_revision = "0009_evaluation_candidates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "query_runs",
        sa.Column("usage", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        schema="app",
    )


def downgrade() -> None:
    op.drop_column("query_runs", "usage", schema="app")
