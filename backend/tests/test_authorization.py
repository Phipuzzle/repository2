from types import SimpleNamespace
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy.dialects import postgresql

from app.agent.authorization import (
    AuthorizationError,
    AuthorizationPolicy,
    authorize_read_query,
    load_policies,
)

USER_ID = UUID("00000000-0000-0000-0000-000000000001")


def test_authorization_requires_identity_unless_demo_mode_is_explicit() -> None:
    with pytest.raises(AuthorizationError, match="identity"):
        authorize_read_query("SELECT id FROM analytics.demo_orders")

    sql = authorize_read_query(
        "SELECT id FROM analytics.demo_orders", allow_anonymous=True
    )
    assert "analytics.demo_orders" in sql


def test_authorization_rejects_a_table_without_a_user_policy() -> None:
    with pytest.raises(AuthorizationError, match="not authorized"):
        authorize_read_query(
            "SELECT id FROM analytics.demo_regions",
            [AuthorizationPolicy("analytics.demo_orders")],
            user_id=USER_ID,
        )


def test_authorization_rejects_conflicting_policies_from_multiple_roles() -> None:
    with pytest.raises(AuthorizationError, match="Conflicting authorization policies"):
        authorize_read_query(
            "SELECT id FROM analytics.demo_orders",
            [
                AuthorizationPolicy("analytics.demo_orders", row_filter="region_id = 1"),
                AuthorizationPolicy("analytics.demo_orders", row_filter="region_id > 1"),
            ],
            user_id=USER_ID,
        )


def test_authorization_rejects_multiple_sql_statements() -> None:
    with pytest.raises(AuthorizationError, match="parsed"):
        authorize_read_query(
            "SELECT id FROM analytics.demo_orders; SELECT id FROM analytics.demo_regions",
            [AuthorizationPolicy("analytics.demo_orders")],
            user_id=USER_ID,
        )


def test_row_filter_and_column_mask_follow_aliases_and_expressions() -> None:
    sql = authorize_read_query(
        "SELECT sum(o.total_amount) AS amount FROM analytics.demo_orders AS o",
        [
            AuthorizationPolicy(
                "analytics.demo_orders",
                row_filter="region_id = 1",
                column_masks={"total_amount": "round({column}, 0)"},
            )
        ],
        user_id=USER_ID,
    )

    assert "ROUND(o.total_amount, 0)" in sql
    assert "o.region_id = 1" in sql


def test_nested_query_column_mask_is_applied_once_per_scope() -> None:
    sql = authorize_read_query(
        "SELECT (SELECT o.total_amount FROM analytics.demo_orders o) AS amount "
        "FROM analytics.demo_orders o",
        [
            AuthorizationPolicy(
                "analytics.demo_orders", column_masks={"total_amount": "round({column}, 0)"}
            )
        ],
        user_id=USER_ID,
    )

    assert sql.count("ROUND(o.total_amount, 0)") == 1
    assert "ROUND(ROUND(" not in sql


def test_masked_dataset_does_not_allow_select_star_or_unprotected_alias() -> None:
    policy = AuthorizationPolicy(
        "analytics.demo_orders", column_masks={"total_amount": "0"}
    )
    with pytest.raises(AuthorizationError, match=r"SELECT \*"):
        authorize_read_query(
            "SELECT o.* FROM analytics.demo_orders AS o", [policy], user_id=USER_ID
        )

    with pytest.raises(AuthorizationError, match="outside"):
        authorize_read_query(
            "SELECT o.id FROM analytics.demo_orders AS o WHERE o.total_amount > 0",
            [policy],
            user_id=USER_ID,
        )


def test_row_filter_is_applied_to_each_union_branch() -> None:
    sql = authorize_read_query(
        "SELECT id FROM analytics.demo_orders UNION SELECT id FROM analytics.demo_orders",
        [AuthorizationPolicy("analytics.demo_orders", row_filter="region_id = 1")],
        user_id=USER_ID,
    )
    assert sql.count("region_id = 1") == 2


def test_left_join_row_filter_is_added_to_join_condition() -> None:
    sql = authorize_read_query(
        "SELECT o.id, r.name FROM analytics.demo_orders o "
        "LEFT JOIN analytics.demo_regions r ON o.region_id = r.id",
        [
            AuthorizationPolicy("analytics.demo_orders"),
            AuthorizationPolicy("analytics.demo_regions", row_filter="id > 1"),
        ],
        user_id=USER_ID,
    )
    assert "LEFT JOIN analytics.demo_regions AS r ON o.region_id = r.id AND r.id > 1" in sql
    assert "WHERE r.id" not in sql


@pytest.mark.asyncio
async def test_load_policies_normalizes_user_id_to_uuid() -> None:
    permission = SimpleNamespace(
        resource="analytics.demo_orders",
        row_filter="region_id = 1",
        column_masks={},
    )

    class FakeResult:
        def all(self) -> list[Any]:
            return [permission]

    class FakeSession:
        statement: Any = None

        async def scalars(self, statement: Any) -> FakeResult:
            self.statement = statement
            return FakeResult()

    session = FakeSession()
    policies = await load_policies(session, str(USER_ID))  # type: ignore[arg-type]
    compiled = session.statement.compile(dialect=postgresql.dialect())  # type: ignore[no-untyped-call]

    assert policies == [
        AuthorizationPolicy(
            "analytics.demo_orders", "region_id = 1", {}
        )
    ]
    assert USER_ID in compiled.params.values()


@pytest.mark.asyncio
async def test_load_policies_rejects_malformed_user_id() -> None:
    with pytest.raises(AuthorizationError, match="valid UUID"):
        await load_policies(object(), "not-a-uuid")  # type: ignore[arg-type]
