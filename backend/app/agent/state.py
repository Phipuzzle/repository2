from typing import Any, Literal, TypedDict


class QueryRunState(TypedDict, total=False):
    run_id: str
    question: str
    status: Literal[
        "submitting",
        "streaming",
        "awaiting_clarification",
        "awaiting_approval",
        "completed",
        "failed",
        "cancelled",
    ]
    intent: str
    complexity: Literal["simple", "moderate", "complex"]
    model: str
    needs_clarification: bool
    clarification: str
    context: str
    plan: str
    sql: str
    sql_explanation: str
    query_cost: float
    approval_reason: str
    approved: bool
    result_rows: list[dict[str, Any]]
    result_schema: list[dict[str, str]]
    result_total: int
    insight: str
    chart_spec: dict[str, Any] | None
    error: str
