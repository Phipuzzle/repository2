from typing import Any, Literal, TypedDict


class QueryRunState(TypedDict, total=False):
    run_id: str
    user_id: str | None
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
    intent: dict[str, Any] | str
    complexity: Literal["simple", "moderate", "complex"]
    model: str
    needs_clarification: bool
    clarification: str
    retrieved_context: list[dict[str, Any]]
    query_plan: dict[str, Any] | str | None
    candidate_sql: str | None
    authorized_sql: str | None
    retry_count: int
    error: dict[str, Any] | str | None
    # Compatibility aliases used by the API event serializer.
    context: str
    semantic_context: str
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
    authorization_policies: list[dict[str, Any]]
