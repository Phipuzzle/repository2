from datetime import date, datetime
from decimal import Decimal
from typing import Any

from opentelemetry import trace
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import get_settings


class QueryCostLimitError(RuntimeError):
    def __init__(self, cost: float) -> None:
        self.cost = cost
        super().__init__(f"Estimated query cost {cost:.0f} exceeds approval threshold")


def _json_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


async def explain_query(engine: AsyncEngine, sql: str) -> float:
    with trace.get_tracer("intelligent-data-agent").start_as_current_span(
        "postgres.explain"
    ) as span:
        async with engine.connect() as connection:
            async with connection.begin():
                await connection.execute(text("SET TRANSACTION READ ONLY"))
                timeout = get_settings().query_timeout_seconds * 1000
                await connection.execute(text(f"SET LOCAL statement_timeout = '{timeout}ms'"))
                result = await connection.execute(text("EXPLAIN (FORMAT JSON) " + sql))
        plan: list[dict[str, Any]] = result.scalar_one()
        cost = float(plan[0]["Plan"].get("Total Cost", 0))
        span.set_attribute("db.query.cost", cost)
        return cost


async def execute_read_query(
    engine: AsyncEngine, sql: str
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    with trace.get_tracer("intelligent-data-agent").start_as_current_span(
        "postgres.execute"
    ) as span:
        async with engine.connect() as connection:
            async with connection.begin():
                await connection.execute(text("SET TRANSACTION READ ONLY"))
                timeout = get_settings().query_timeout_seconds * 1000
                await connection.execute(text(f"SET LOCAL statement_timeout = '{timeout}ms'"))
                result = await connection.execute(text(sql))
                keys = list(result.keys())
                rows = [
                    {key: _json_value(value) for key, value in row._mapping.items()}
                    for row in result.fetchall()
                ]
        span.set_attribute("db.result.row_count", len(rows))

    schema = []
    for key in keys:
        sample = next((row[key] for row in rows if row[key] is not None), None)
        value_type = "number" if isinstance(sample, (int, float, Decimal)) else "string"
        schema.append({"name": key, "type": value_type, "label": key})
    return rows, schema
