"""Add demo query indexes for filtering and aggregation."""

from alembic import op

revision = "0004_demo_query_indexes"
down_revision = "0003_oidc_user_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_analytics_demo_orders_status",
        "demo_orders",
        ["status"],
        schema="analytics",
    )
    op.create_index(
        "ix_analytics_demo_orders_region_created_at",
        "demo_orders",
        ["region_id", "created_at"],
        schema="analytics",
    )
    op.create_index(
        "ix_analytics_demo_orders_product_created_at",
        "demo_orders",
        ["product_id", "created_at"],
        schema="analytics",
    )


def downgrade() -> None:
    op.drop_index("ix_analytics_demo_orders_status", schema="analytics")
    op.drop_index("ix_analytics_demo_orders_region_created_at", schema="analytics")
    op.drop_index("ix_analytics_demo_orders_product_created_at", schema="analytics")
