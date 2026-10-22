import json
from collections.abc import Awaitable, Callable
from typing import Any

from langgraph.graph import END, START, StateGraph
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.agent.authorization import authorize_read_query, load_policies
from app.agent.chart import build_chart_spec
from app.agent.executor import execute_read_query, explain_query
from app.agent.metadata import retrieve_context
from app.agent.model import DeepSeekModelAdapter
from app.agent.prompts import CLASSIFY_SYSTEM, PLAN_SYSTEM, SQL_SYSTEM, SUMMARY_SYSTEM
from app.agent.state import QueryRunState
from app.agent.telemetry import get_tracer
from app.core.config import get_settings
from app.semantic.mapper import resolve_semantic_context
from app.sql.validator import UnsafeQueryError, validate_read_query


def build_workflow(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    engine: AsyncEngine,
    adapter: DeepSeekModelAdapter,
) -> Any:
    tracer = get_tracer()

    def traced(
        name: str, node: Callable[[QueryRunState], Awaitable[dict[str, Any]]]
    ) -> Callable[[QueryRunState], Awaitable[dict[str, Any]]]:
        async def invoke(state: QueryRunState) -> dict[str, Any]:
            with tracer.start_as_current_span(f"agent.node.{name}") as span:
                span.set_attribute("agent.node", name)
                return await node(state)

        return invoke

    async def classify(state: QueryRunState) -> dict[str, Any]:
        result = await adapter.complete_json(
            model=adapter.model_for("simple"),
            system=CLASSIFY_SYSTEM,
            user=state["question"],
        )
        complexity = result.get("complexity", "moderate")
        if complexity not in {"simple", "moderate", "complex"}:
            complexity = "moderate"
        return {
            "intent": str(result.get("intent", "数据查询")),
            "complexity": complexity,
            "model": adapter.model_for(complexity),
            "needs_clarification": bool(result.get("needs_clarification", False)),
            "clarification": str(result.get("clarification", "")),
        }

    async def retrieve(state: QueryRunState) -> dict[str, Any]:
        async with session_factory() as session:
            context = await retrieve_context(session, state["question"])
        return {"context": context}

    async def semantic_map(state: QueryRunState) -> dict[str, Any]:
        async with session_factory() as session:
            semantic_context = await resolve_semantic_context(session, state["question"])
        return {"semantic_context": semantic_context}

    async def plan(state: QueryRunState) -> dict[str, Any]:
        semantic_context = state.get("semantic_context", "")
        result = await adapter.complete_json(
            model=state["model"],
            system=PLAN_SYSTEM,
            user=(
                f"问题：{state['question']}\n"
                f"标准语义：\n{semantic_context}\n"
                f"Metadata：\n{state['context']}"
            ),
        )
        return {"plan": str(result.get("plan", ""))}

    async def generate_sql(state: QueryRunState) -> dict[str, Any]:
        semantic_context = state.get("semantic_context", "")
        result = await adapter.complete_json(
            model=state["model"],
            system=SQL_SYSTEM,
            user=(
                f"问题：{state['question']}\n"
                f"标准语义：\n{semantic_context}\n"
                f"查询计划：{state['plan']}\n"
                f"Metadata：\n{state['context']}"
            ),
        )
        return {
            "sql": str(result.get("sql", "")),
            "sql_explanation": str(result.get("explanation", "")),
        }

    async def validate(state: QueryRunState) -> dict[str, Any]:
        sql = state.get("sql", "")
        try:
            validated = validate_read_query(sql)
            return {"candidate_sql": validated.sql, "sql": validated.sql}
        except UnsafeQueryError as first_error:
            repaired = await adapter.complete_json(
                model=state["model"],
                system=SQL_SYSTEM,
                user=(
                    f"请修复下列 SQL 安全或语法问题，只输出符合格式的 JSON。\n"
                    f"原始 SQL：{sql}\n校验错误：{first_error}\n"
                    f"问题：{state['question']}\nMetadata：\n{state['context']}"
                ),
            )
            repaired_sql = str(repaired.get("sql", ""))
            validated = validate_read_query(repaired_sql)
            return {"candidate_sql": validated.sql, "sql": validated.sql}

    async def authorize(state: QueryRunState) -> dict[str, Any]:
        user_id = state.get("user_id")
        async with session_factory() as session:
            policies = await load_policies(session, user_id)
        authorized_sql = authorize_read_query(
            state["sql"],
            policies,
            user_id=user_id,
            allow_anonymous=get_settings().agent_demo_anonymous_read,
        )
        validated = validate_read_query(authorized_sql)
        update: dict[str, Any] = {
            "authorized_sql": validated.sql,
            "sql": validated.sql,
            "authorization_policies": [policy.as_dict() for policy in policies],
        }
        if state.get("approved") and validated.sql != validate_read_query(state["sql"]).sql:
            update["approved"] = False
        return update

    async def cost_check(state: QueryRunState) -> dict[str, Any]:
        cost = await explain_query(engine, state["sql"])
        if cost > get_settings().cost_approval_threshold and not state.get("approved", False):
            return {
                "query_cost": cost,
                "status": "awaiting_approval",
                "approval_reason": f"预计查询成本 {cost:.0f}，超过审批阈值。",
            }
        return {"query_cost": cost}

    async def execute(state: QueryRunState) -> dict[str, Any]:
        sql = state["sql"]
        try:
            rows, schema = await execute_read_query(engine, sql)
        except Exception as first_error:
            if state.get("retry_count", 0) >= 1:
                raise
            repaired = await adapter.complete_json(
                model=state["model"],
                system=SQL_SYSTEM,
                user=(
                    f"请修复 SQL 执行错误，只输出符合格式的 JSON。\nSQL：{sql}\n"
                    f"数据库错误：{str(first_error)[:500]}\n问题：{state['question']}\n"
                    f"Metadata：\n{state['context']}"
                ),
            )
            sql = validate_read_query(str(repaired.get("sql", ""))).sql
            user_id = state.get("user_id")
            async with session_factory() as session:
                policies = await load_policies(session, user_id)
            sql = validate_read_query(
                authorize_read_query(
                    sql,
                    policies,
                    user_id=user_id,
                    allow_anonymous=get_settings().agent_demo_anonymous_read,
                )
            ).sql
            cost = await explain_query(engine, sql)
            approved_same_sql = state.get("approved", False) and sql == state.get("sql")
            if cost > get_settings().cost_approval_threshold and not approved_same_sql:
                return {
                    "sql": sql,
                    "query_cost": cost,
                    "retry_count": 1,
                    "status": "awaiting_approval",
                    "approval_reason": f"修复后的查询成本 {cost:.0f} 超过审批阈值。",
                }
            rows, schema = await execute_read_query(engine, sql)
            return {
                "sql": sql,
                "result_rows": rows,
                "result_schema": schema,
                "result_total": len(rows),
                "retry_count": 1,
            }
        return {"sql": sql, "result_rows": rows, "result_schema": schema, "result_total": len(rows)}

    async def summarize(state: QueryRunState) -> dict[str, Any]:
        result_json = json.dumps(state.get("result_rows", []), ensure_ascii=False)
        result = await adapter.complete_json(
            model=state["model"],
            system=SUMMARY_SYSTEM,
            user=f"问题：{state['question']}\n结果：{result_json}",
        )
        return {"insight": str(result.get("insight", "查询已完成。"))}

    async def chart(state: QueryRunState) -> dict[str, Any]:
        return {
            "chart_spec": build_chart_spec(
                state.get("result_rows", []), state.get("result_schema", []), state["question"]
            )
        }

    async def completed(state: QueryRunState) -> dict[str, Any]:
        return {"status": "completed"}

    async def clarification(state: QueryRunState) -> dict[str, Any]:
        return {"status": "awaiting_clarification"}

    def after_classify(state: QueryRunState) -> str:
        return "clarification" if state.get("needs_clarification") else "retrieve"

    def after_cost(state: QueryRunState) -> str:
        return "approval" if state.get("status") == "awaiting_approval" else "execute"

    def after_execute(state: QueryRunState) -> str:
        return "approval" if state.get("status") == "awaiting_approval" else "summarize"

    async def approval(state: QueryRunState) -> dict[str, Any]:
        return {"status": "awaiting_approval"}

    graph = StateGraph(QueryRunState)
    graph.add_node("classify", traced("classify", classify))
    graph.add_node("ask_clarification", traced("ask_clarification", clarification))
    graph.add_node("retrieve_context", traced("retrieve_context", retrieve))
    graph.add_node("semantic_map", traced("semantic_map", semantic_map))
    graph.add_node("build_query_plan", traced("build_query_plan", plan))
    graph.add_node("generate_sql", traced("generate_sql", generate_sql))
    graph.add_node("validate_sql", traced("validate_sql", validate))
    graph.add_node("authorize_sql", traced("authorize_sql", authorize))
    graph.add_node("cost_check", traced("cost_check", cost_check))
    graph.add_node("approval_required", traced("approval_required", approval))
    graph.add_node("execute_query", traced("execute_query", execute))
    graph.add_node("summarize_result", traced("summarize_result", summarize))
    graph.add_node("generate_chart_spec", traced("generate_chart_spec", chart))
    graph.add_node("completed", traced("completed", completed))

    def start_route(state: QueryRunState) -> str:
        return "validate_sql" if state.get("approved") and state.get("sql") else "classify"

    graph.add_conditional_edges(
        START,
        start_route,
        {"classify": "classify", "validate_sql": "validate_sql"},
    )
    graph.add_conditional_edges(
        "classify",
        after_classify,
        {"clarification": "ask_clarification", "retrieve": "retrieve_context"},
    )
    graph.add_edge("ask_clarification", END)
    graph.add_edge("retrieve_context", "semantic_map")
    graph.add_edge("semantic_map", "build_query_plan")
    graph.add_edge("build_query_plan", "generate_sql")
    graph.add_edge("generate_sql", "validate_sql")
    graph.add_edge("validate_sql", "authorize_sql")
    graph.add_edge("authorize_sql", "cost_check")
    graph.add_conditional_edges(
        "cost_check", after_cost, {"approval": "approval_required", "execute": "execute_query"}
    )
    graph.add_edge("approval_required", END)
    graph.add_conditional_edges(
        "execute_query",
        after_execute,
        {"approval": "approval_required", "summarize": "summarize_result"},
    )
    graph.add_edge("summarize_result", "generate_chart_spec")
    graph.add_edge("generate_chart_spec", "completed")
    graph.add_edge("completed", END)
    return graph.compile()
