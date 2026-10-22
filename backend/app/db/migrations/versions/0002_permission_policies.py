"""Add row and column authorization policy fields."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_permission_policies"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {
        column["name"]
        for column in sa.inspect(bind).get_columns("permissions", schema="app")
    }
    if "row_filter" not in columns:
        op.add_column(
            "permissions", sa.Column("row_filter", sa.Text(), nullable=True), schema="app"
        )
    if "column_masks" not in columns:
        op.add_column(
            "permissions",
            sa.Column(
                "column_masks",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            schema="app",
        )


def downgrade() -> None:
    bind = op.get_bind()
    columns = {
        column["name"]
        for column in sa.inspect(bind).get_columns("permissions", schema="app")
    }
    if "column_masks" in columns:
        op.drop_column("permissions", "column_masks", schema="app")
    if "row_filter" in columns:
        op.drop_column("permissions", "row_filter", schema="app")
