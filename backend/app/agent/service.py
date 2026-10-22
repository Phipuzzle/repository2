import asyncio
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.agent.model import DeepSeekModelAdapter
from app.agent.telemetry import configure_telemetry, get_tracer
from app.agent.workflow import build_workflow
from app.core.config import get_settings
from app.db.models import QueryRun
from app.db.session import SessionLocal, engine
from app.services.query_service import add_audit, add_event

_tasks: dict[UUID, asyncio.Task[None]] = {}


async def shutdown_agent_runs() -> None:
    tasks = list(_tasks.values())
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    _tasks.clear()


EVENTS = {
    "classify": ("intent_detected", "已识别查询意图"),
    "ask_clarification": ("clarification_required", "需要补充查询条件"),
    "retrieve_context": ("context_retrieved", "已检索指标和数据表上下文"),
    "semantic_map": ("semantic_mapped", "已完成标准指标和维度映射"),
    "build_query_plan": ("query_plan_ready", "已生成查询计划"),
    "generate_sql": ("sql_generated", "已生成只读 SQL"),
    "validate_sql": ("sql_validated", "SQL 只读安全校验通过"),
    "authorize_sql": ("sql_authorized", "SQL 权限校验通过"),
    "cost_check": ("cost_checked", "已完成查询成本检查"),
    "approval_required": ("approval_required", "查询成本较高，等待确认"),
    "execute_query": ("query_started", "已执行只读查询"),
    "summarize_result": ("insight_ready", "已生成结果分析"),
    "generate_chart_spec": ("chart_spec_ready", "已生成图表配置"),
    "completed": ("run_completed", "查询已完成"),
}


def schedule_agent_run(run_id: UUID, *, approved: bool = False) -> None:
    previous = _tasks.get(run_id)
    if previous and not previous.done():
        previous.cancel()
    task = asyncio.create_task(run_agent(run_id, approved=approved))
    _tasks[run_id] = task
    task.add_done_callback(
        lambda completed: _tasks.pop(run_id, None) if _tasks.get(run_id) is completed else None
    )


def cancel_agent_run(run_id: UUID) -> None:
    task = _tasks.get(run_id)
    if task and not task.done():
        task.cancel()


async def _apply_update(run: QueryRun, update: dict[str, Any]) -> None:
    for key in (
        "sql",
        "result_rows",
        "result_schema",
        "result_total",
        "chart_spec",
        "insight",
        "clarification",
        "approval_reason",
        "status",
    ):
        if key in update:
            setattr(run, key, update[key])


async def _conversation_context(session: Any, run: QueryRun) -> str:
    if run.conversation_id is None or run.turn_index == 0:
        return ""
    previous_runs = (
        await session.scalars(
            select(QueryRun)
            .where(
                QueryRun.conversation_id == run.conversation_id,
                QueryRun.turn_index < run.turn_index,
                QueryRun.status == "completed",
            )
            .order_by(QueryRun.turn_index.desc())
            .limit(get_settings().conversation_context_turns)
        )
    ).all()
    previous_runs = list(reversed(previous_runs))
    if not previous_runs:
        return ""
    lines = ["对话语义摘要："]
    lines.extend(
        f"- 第 {item.turn_index} 轮问题：{item.question}；结论：{item.insight or '无'}"
        for item in previous_runs
    )
    return "\n".join(lines)


async def run_agent(run_id: UUID, *, approved: bool = False) -> None:
    tracer = get_tracer()
    try:
        configure_telemetry()
        with tracer.start_as_current_span("agent.run") as span:
            span.set_attribute("query_run.id", str(run_id))
            async with SessionLocal() as session:
                run = await session.get(QueryRun, run_id)
                if run is None or run.status == "cancelled":
                    return
                run.status = "streaming"
                conversation_context = await _conversation_context(session, run)
                await add_event(session, run, "agent_started", "Agent 工作流已启动")
                await session.commit()
                state = {
                    "run_id": str(run.id),
                    "user_id": str(run.user_id) if run.user_id is not None else None,
                    "question": run.question,
                    "status": "streaming",
                    "approved": approved,
                    "sql": run.sql,
                    "conversation_context": conversation_context,
                    "model": DeepSeekModelAdapter().model_for("complex" if approved else "simple"),
                }

            adapter = DeepSeekModelAdapter()
            graph = build_workflow(
                session_factory=SessionLocal,
                engine=engine,
                adapter=adapter,
            )
            async for chunk in graph.astream(state, stream_mode="updates"):
                node_name, update = next(iter(chunk.items()))
                async with SessionLocal() as event_session:
                    current = await event_session.get(QueryRun, run_id)
                    if current is None or current.status == "cancelled":
                        return
                    await _apply_update(current, update)
                    event_type, message = EVENTS.get(node_name, (f"agent_{node_name}", node_name))
                    details = {
                        key: value
                        for key, value in update.items()
                        if key in {"model", "query_cost", "status"}
                    }
                    await add_event(event_session, current, event_type, message, details or None)
                    if node_name == "completed":
                        current.completed_at = datetime.now(UTC)
                    await event_session.commit()
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        async with SessionLocal() as session:
            run = await session.get(QueryRun, run_id)
            if run is None or run.status == "cancelled":
                return
            run.status = "failed"
            run.error = str(exc)[:1000]
            run.completed_at = datetime.now(UTC)
            await add_event(
                session, run, "run_failed", "Agent 执行失败", {"code": type(exc).__name__}
            )
            await add_audit(
                session,
                "query_run.failed",
                run_id,
                {"error_type": type(exc).__name__},
                user_id=run.user_id,
            )
            await session.commit()
