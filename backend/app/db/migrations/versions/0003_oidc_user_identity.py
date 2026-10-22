"""Add OIDC identity mapping to application users."""

import sqlalchemy as sa
from alembic import op

revision = "0003_oidc_user_identity"
down_revision = "0002_permission_policies"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("users", schema="app")}
    if "identity_issuer" not in columns:
        op.add_column("users", sa.Column("identity_issuer", sa.String(length=512)), schema="app")
    if "identity_subject" not in columns:
        op.add_column("users", sa.Column("identity_subject", sa.String(length=255)), schema="app")
    constraints = {
        constraint["name"] for constraint in inspector.get_unique_constraints("users", schema="app")
    }
    if "uq_users_oidc_identity" not in constraints:
        op.create_unique_constraint(
            "uq_users_oidc_identity",
            "users",
            ["identity_issuer", "identity_subject"],
            schema="app",
        )
    checks = {
        constraint["name"] for constraint in inspector.get_check_constraints("users", schema="app")
    }
    if "ck_users_oidc_identity_pair" not in checks:
        op.create_check_constraint(
            "ck_users_oidc_identity_pair",
            "users",
            "(identity_issuer IS NULL) = (identity_subject IS NULL)",
            schema="app",
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    constraints = {
        constraint["name"] for constraint in inspector.get_unique_constraints("users", schema="app")
    }
    checks = {
        constraint["name"] for constraint in inspector.get_check_constraints("users", schema="app")
    }
    if "ck_users_oidc_identity_pair" in checks:
        op.drop_constraint("ck_users_oidc_identity_pair", "users", schema="app", type_="check")
    if "uq_users_oidc_identity" in constraints:
        op.drop_constraint("uq_users_oidc_identity", "users", schema="app", type_="unique")
    columns = {column["name"] for column in inspector.get_columns("users", schema="app")}
    if "identity_subject" in columns:
        op.drop_column("users", "identity_subject", schema="app")
    if "identity_issuer" in columns:
        op.drop_column("users", "identity_issuer", schema="app")
