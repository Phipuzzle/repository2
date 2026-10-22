from __future__ import annotations

import json
import re
from typing import Any


def _canonical_key(value: Any) -> tuple[str, Any]:
    if value is None:
        return ("none", "")
    if isinstance(value, bool):
        return ("bool", value)
    if isinstance(value, (int, float)):
        return ("number", format(float(value), ".15g"))
    if isinstance(value, (list, dict)):
        return ("json", json.dumps(value, sort_keys=True, ensure_ascii=False, default=str))
    return ("string", str(value).strip())


def _column_kind(name: str) -> str | None:
    normalized = name.lower()
    if normalized in {"id", "region_id", "product_id", "order_id"} or normalized.endswith("_id"):
        return None
    if any(token in normalized for token in ("order", "订单")):
        return "orders"
    if any(token in normalized for token in ("sales", "amount", "revenue", "金额", "销售")):
        return "sales"
    if any(token in normalized for token in ("region", "区域")):
        return "region"
    if any(token in normalized for token in ("category", "类别", "商品")):
        return "category"
    if any(token in normalized for token in ("month", "月", "date", "日期")):
        return "month"
    return "other"


def canonical_rows(rows: list[dict[str, Any]]) -> set[tuple[tuple[str, Any], ...]]:
    """Compare result sets by semantic column kind, ignoring surrogate IDs."""
    normalized = []
    for row in rows:
        projected = []
        for name, value in row.items():
            kind = _column_kind(str(name))
            if kind is None:
                continue
            normalized_value = _canonical_key(value)[1]
            if kind == "month" and isinstance(normalized_value, str):
                match = re.match(r"(\d{4}-\d{2})(?:-\d{2})?", normalized_value)
                if match:
                    normalized_value = match.group(1)
            projected.append((kind, normalized_value))
        normalized.append(tuple(sorted(projected)))
    return set(normalized)


def result_accuracy(
    actual: list[dict[str, Any]],
    expected: list[dict[str, Any]],
    expected_kind: str = "exact",
    invariants: dict[str, Any] | None = None,
) -> float:
    if expected_kind == "empty":
        return float(len(actual) == 0)
    if expected_kind == "non_empty":
        return float(len(actual) > 0)
    if expected_kind == "invariants":
        if not invariants:
            return 0.0
        min_rows = invariants.get("min_rows")
        max_rows = invariants.get("max_rows")
        if min_rows is not None and len(actual) < int(min_rows):
            return 0.0
        if max_rows is not None and len(actual) > int(max_rows):
            return 0.0
        required_columns = invariants.get("required_columns", [])
        actual_kinds = {_column_kind(str(name)) for row in actual for name in row}
        expected_kinds = {_column_kind(str(name)) for name in required_columns}
        if not expected_kinds.issubset(actual_kinds):
            return 0.0
        return 1.0
    if not actual and not expected:
        return 1.0
    return float(canonical_rows(actual) == canonical_rows(expected))


def sql_semantic_accuracy(sql: str, required_terms: list[str]) -> float:
    normalized = sql.lower()
    if not required_terms:
        return 1.0
    return sum(1.0 for term in required_terms if term.lower() in normalized) / len(required_terms)


def chart_accuracy(actual: dict[str, Any] | None, expected: dict[str, Any] | None) -> float:
    if expected is None:
        return 1.0
    if not isinstance(actual, dict):
        return 0.0
    dataset = actual.get("dataset")
    if not isinstance(dataset, list) or not dataset:
        return 0.0
    actual_x = str(actual.get("xField", "")).lower()
    expected_x = str(expected.get("xField", "")).lower()
    actual_y = str(actual.get("yField", "")).lower()
    expected_y = str(expected.get("yField", "")).lower()

    def metric_kind(field: str) -> str:
        if any(token in field for token in ("order", "订单")):
            return "orders"
        if any(token in field for token in ("sales", "amount", "revenue", "金额", "销售")):
            return "sales"
        return field

    def dimension_kind(field: str) -> str:
        if any(token in field for token in ("region", "区域")):
            return "region"
        if any(token in field for token in ("category", "类别", "商品")):
            return "category"
        if any(token in field for token in ("month", "月", "date", "日期")):
            return "month"
        return field

    x_matches = dimension_kind(actual_x) == dimension_kind(expected_x)
    y_matches = metric_kind(actual_y) == metric_kind(expected_y)
    return float(actual.get("type") == expected.get("type") and x_matches and y_matches)
