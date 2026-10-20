from typing import Any


def build_chart_spec(
    rows: list[dict[str, Any]], schema: list[dict[str, str]], title: str
) -> dict[str, Any] | None:
    if not rows or len(schema) < 2:
        return None
    x_field = schema[0]["name"]
    y_field = next(
        (field["name"] for field in schema[1:] if field["type"] == "number"), schema[1]["name"]
    )
    chart_type = (
        "line" if "月" in schema[0].get("label", "") or "month" in x_field.lower() else "bar"
    )
    dataset = [
        {x_field: row[x_field], y_field: row[y_field]}
        for row in rows
        if row.get(x_field) is not None
        and row.get(y_field) is not None
        and isinstance(row.get(x_field), (str, int, float))
        and isinstance(row.get(y_field), (int, float))
    ][:100]
    if not dataset:
        return None
    return {
        "type": chart_type,
        "title": title[:120],
        "xField": x_field,
        "yField": y_field,
        "dataset": dataset,
    }
