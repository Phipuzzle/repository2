import pytest

from app.sql.validator import UnsafeQueryError, validate_read_query


def test_select_gets_default_limit_and_preserves_cte() -> None:
    validated = validate_read_query(
        "WITH sales AS (SELECT total_amount FROM analytics.demo_orders) "
        "SELECT total_amount FROM sales"
    )
    assert validated.limit == 1000
    assert validated.sql.endswith("LIMIT 1000")


def test_select_limit_is_capped() -> None:
    validated = validate_read_query(
        "SELECT id FROM analytics.demo_orders LIMIT 9000", max_limit=250
    )
    assert validated.limit == 250
    assert "LIMIT 250" in validated.sql


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM analytics.demo_orders",
        "SELECT 1; DROP TABLE analytics.demo_orders",
        "SELECT pg_sleep(10)",
        "SELECT id INTO analytics.exported FROM analytics.demo_orders",
        "SELECT id FROM analytics.demo_orders FOR UPDATE",
        "SELECT id FROM demo_orders",
        "SELECT * FROM information_schema.tables",
        "SELECT id FROM analytics.demo_orders LIMIT -1",
        "SELECT id FROM analytics.demo_orders LIMIT 1.5",
    ],
)
def test_rejects_unsafe_statements_functions_schemas_and_limits(sql: str) -> None:
    with pytest.raises(UnsafeQueryError):
        validate_read_query(sql)
