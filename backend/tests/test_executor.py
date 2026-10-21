from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

from app.agent.executor import execute_read_query, explain_query
from app.core.config import get_settings


class FakeTransaction:
    async def __aenter__(self) -> "FakeTransaction":
        return self

    async def __aexit__(self, *_exc_info: Any) -> None:
        return None


class FakeRow:
    def __init__(self, values: dict[str, Any]) -> None:
        self._mapping = values


class FakeResult:
    def keys(self) -> list[str]:
        return ["amount", "created_at", "region"]

    def fetchall(self) -> list[FakeRow]:
        return [
            FakeRow(
                {
                    "amount": Decimal("12.50"),
                    "created_at": datetime(2026, 1, 2, tzinfo=UTC),
                    "region": "North",
                }
            )
        ]


class FakeExplainResult:
    def scalar_one(self) -> list[dict[str, Any]]:
        return [{"Plan": {"Total Cost": 42.5}}]


class FakeConnection:
    def __init__(self, result: Any) -> None:
        self.result = result
        self.statements: list[str] = []

    def begin(self) -> FakeTransaction:
        return FakeTransaction()

    async def execute(self, statement: Any) -> Any:
        self.statements.append(str(statement))
        return self.result


class FakeConnectionContext:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    async def __aenter__(self) -> FakeConnection:
        return self.connection

    async def __aexit__(self, *_exc_info: Any) -> None:
        return None


class FakeEngine:
    def __init__(self, result: Any) -> None:
        self.connection = FakeConnection(result)

    def connect(self) -> FakeConnectionContext:
        return FakeConnectionContext(self.connection)


@pytest.mark.asyncio
async def test_read_query_sets_read_only_timeout_and_serializes_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "query_timeout_seconds", 7)
    engine = FakeEngine(FakeResult())

    rows, schema = await execute_read_query(engine, "SELECT amount FROM analytics.demo_orders")  # type: ignore[arg-type]

    assert engine.connection.statements == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '7000ms'",
        "SELECT amount FROM analytics.demo_orders",
    ]
    assert rows == [
        {
            "amount": 12.5,
            "created_at": "2026-01-02T00:00:00+00:00",
            "region": "North",
        }
    ]
    assert schema == [
        {"name": "amount", "type": "number", "label": "amount"},
        {"name": "created_at", "type": "string", "label": "created_at"},
        {"name": "region", "type": "string", "label": "region"},
    ]


@pytest.mark.asyncio
async def test_explain_runs_in_read_only_transaction_with_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "query_timeout_seconds", 5)
    engine = FakeEngine(FakeExplainResult())

    cost = await explain_query(engine, "SELECT id FROM analytics.demo_orders")  # type: ignore[arg-type]

    assert cost == 42.5
    assert engine.connection.statements == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '5000ms'",
        "EXPLAIN (FORMAT JSON) SELECT id FROM analytics.demo_orders",
    ]
