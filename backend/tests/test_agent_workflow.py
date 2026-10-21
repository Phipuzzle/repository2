from typing import Any

import pytest

from app.agent.chart import build_chart_spec
from app.agent.model import DeepSeekModelAdapter, ModelConfigurationError
from app.agent.workflow import build_workflow
from app.core.config import get_settings
from app.db.session import engine


class EmptyMetadataSession:
    async def __aenter__(self) -> "EmptyMetadataSession":
        return self

    async def __aexit__(self, *_exc_info: Any) -> None:
        return None

    async def scalars(self, _statement: Any) -> "EmptyRows":
        return EmptyRows()


class EmptyRows:
    def all(self) -> list[Any]:
        return []


class FakeModelAdapter:
    def model_for(self, complexity: str) -> str:
        return "deepseek-v4-pro" if complexity == "complex" else "deepseek-flash"

    async def complete_json(
        self, *, model: str, system: str, user: str, temperature: float = 0.0
    ) -> dict[str, Any]:
        if "意图分类器" in system:
            return {"intent": "订单列表", "complexity": "simple", "needs_clarification": False}
        if "查询规划器" in system:
            return {"plan": "读取前五条订单"}
        if "只读 SQL 专家" in system:
            return {
                "sql": "SELECT id, total_amount FROM analytics.demo_orders LIMIT 5",
                "explanation": "查询订单",
            }
        return {"insight": "返回了订单数据。"}


@pytest.mark.asyncio
async def test_workflow_runs_read_only_query_and_builds_chart(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_explain(_engine: Any, _sql: str) -> float:
        return 10.0

    async def fake_execute(
        _engine: Any, _sql: str
    ) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
        rows = [{"id": index, "total_amount": index * 100.0} for index in range(1, 6)]
        return rows, [
            {"name": "id", "type": "number", "label": "id"},
            {"name": "total_amount", "type": "number", "label": "total_amount"},
        ]

    monkeypatch.setattr("app.agent.workflow.explain_query", fake_explain)
    monkeypatch.setattr("app.agent.workflow.execute_read_query", fake_execute)
    graph = build_workflow(
        session_factory=EmptyMetadataSession,  # type: ignore[arg-type]
        engine=engine,
        adapter=FakeModelAdapter(),  # type: ignore[arg-type]
    )
    result = await graph.ainvoke(
        {"run_id": "test", "question": "列出前五条订单", "status": "streaming"}
    )

    assert result["status"] == "completed"
    assert len(result["result_rows"]) == 5
    assert result["result_schema"][1]["name"] == "total_amount"
    assert result["chart_spec"]["yField"] == "total_amount"
    assert result["model"] == "deepseek-flash"


def test_chart_spec_requires_numeric_measure() -> None:
    chart = build_chart_spec(
        [{"region": "华东", "orders": 12}],
        [
            {"name": "region", "type": "string", "label": "区域"},
            {"name": "orders", "type": "number", "label": "订单数"},
        ],
        "各区域订单数",
    )
    assert chart is not None
    assert chart["type"] == "bar"
    assert chart["yField"] == "orders"


@pytest.mark.asyncio
async def test_deepseek_adapter_requires_a_configured_key(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = DeepSeekModelAdapter()
    monkeypatch.setattr(get_settings(), "deepseek_api_key", "")
    with pytest.raises(ModelConfigurationError, match="DEEPSEEK_API_KEY"):
        await adapter.complete_json(model="deepseek-flash", system="test", user="test")
