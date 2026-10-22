from evals.metrics import (
    chart_accuracy,
    result_accuracy,
    sql_semantic_accuracy,
)


def test_result_accuracy_ignores_column_order_and_float_formatting() -> None:
    actual = [
        {"month": "2026-01", "sales": 128000.0},
        {"month": "2026-02", "sales": 146500.0},
    ]
    expected = [
        {"sales": 146500, "month": "2026-02"},
        {"sales": 128000, "month": "2026-01"},
    ]
    assert result_accuracy(actual, expected) == 1.0


def test_result_accuracy_rejects_different_rows() -> None:
    assert result_accuracy([{"a": 1}], [{"a": 2}]) == 0.0
    assert result_accuracy([], []) == 1.0


def test_result_accuracy_supports_non_exact_result_kinds() -> None:
    assert result_accuracy([], [], expected_kind="empty") == 1.0
    assert result_accuracy([{"a": 1}], [], expected_kind="non_empty") == 1.0
    assert (
        result_accuracy(
            [{"region": "华东", "orders": 1}],
            [],
            expected_kind="invariants",
            invariants={"min_rows": 1, "required_columns": ["region", "orders"]},
        )
        == 1.0
    )


def test_sql_semantic_accuracy_counts_required_terms() -> None:
    sql = "SELECT SUM(o.total_amount) FROM analytics.demo_orders o GROUP BY o.region_id"
    assert sql_semantic_accuracy(sql, ["SUM", "total_amount", "GROUP BY", "missing"]) == 0.75


def test_chart_accuracy_checks_type_and_fields() -> None:
    expected = {"type": "line", "xField": "month", "yField": "sales"}
    assert (
        chart_accuracy(
            {
                "type": "line",
                "xField": "month",
                "yField": "sales",
                "dataset": [{"month": "2026-01", "sales": 10}],
            },
            expected,
        )
        == 1.0
    )
    assert (
        chart_accuracy(
            {"type": "bar", "xField": "month", "yField": "sales", "dataset": [{}]}, expected
        )
        == 0.0
    )
    assert chart_accuracy(None, expected) == 0.0
