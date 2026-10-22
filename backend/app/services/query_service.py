import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import (
    AuditLog,
    Conversation,
    EvaluationCandidate,
    Feedback,
    Metric,
    QueryEvent,
    QueryRun,
)
from app.schemas.query_run import (
    AuditLogResponse,
    ChartSpecResponse,
    FeedbackCreate,
    FeedbackResponse,
    MetricResponse,
    PaginatedResultResponse,
    QueryResultResponse,
    QueryRunCreate,
    QueryRunListResponse,
    QueryRunResponse,
    ResultSchemaField,
    SSEEventResponse,
)
from app.services.cache_service import (
    build_cache_key,
    cache_expires_at,
    find_cached_run,
    get_data_version,
)

TERMINAL_STATUSES = {"completed", "failed", "cancelled"}
_event_conditions: dict[UUID, asyncio.Condition] = {}


async def notify_event_subscribers(run_id: UUID) -> None:
    condition = _event_conditions.get(run_id)
    if condition is not None:
        async with condition:
            condition.notify_all()


def serialize_event(event: QueryEvent) -> SSEEventResponse:
    return SSEEventResponse(
        id=event.sequence,
        type=event.event_type,
        timestamp=event.created_at,
        message=event.message,
        data=event.data,
    )


def serialize_run(run: QueryRun) -> QueryRunResponse:
    result = None
    if run.result_rows is not None:
        result = QueryResultResponse(
            rows=run.result_rows,
            schema=[ResultSchemaField.model_validate(field) for field in (run.result_schema or [])],
            total=run.result_total or 0,
        )
    return QueryRunResponse(
        id=run.id,
        question=run.question,
        status=run.status,  # type: ignore[arg-type]
        events=[serialize_event(event) for event in run.events],
        sql=run.sql,
        result=result,
        chartSpec=(
            ChartSpecResponse.model_validate(run.chart_spec) if run.chart_spec is not None else None
        ),
        insight=run.insight,
        error=run.error,
        clarification=run.clarification,
        approvalReason=run.approval_reason,
        reconnectCount=run.reconnect_count,
        conversationId=run.conversation_id,
        turnIndex=run.turn_index,
        startedAt=run.created_at,
        completedAt=run.completed_at,
    )


async def add_event(
    session: AsyncSession,
    run: QueryRun,
    event_type: str,
    message: str,
    data: dict[str, Any] | None = None,
) -> QueryEvent:
    await session.scalar(select(QueryRun.id).where(QueryRun.id == run.id).with_for_update())
    sequence = await session.scalar(
        select(func.coalesce(func.max(QueryEvent.sequence), 0)).where(QueryEvent.run_id == run.id)
    )
    event = QueryEvent(
        run_id=run.id,
        sequence=(sequence or 0) + 1,
        event_type=event_type,
        message=message,
        data=data,
    )
    session.add(event)
    return event


async def add_audit(
    session: AsyncSession,
    action: str,
    run_id: UUID | None = None,
    details: dict[str, Any] | None = None,
    user_id: UUID | None = None,
) -> None:
    session.add(AuditLog(user_id=user_id, run_id=run_id, action=action, details=details or {}))


async def resolve_conversation(
    session: AsyncSession,
    conversation_id: UUID | None,
    user_id: UUID,
) -> tuple[UUID, int]:
    if conversation_id is None:
        conversation = Conversation(user_id=user_id)
        session.add(conversation)
        await session.flush()
        return conversation.id, 0

    conversation = await session.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
        )
    )
    if conversation is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "conversation_not_found", "message": "Conversation not found"},
        )
    turn_index = int(
        await session.scalar(
            select(func.max(QueryRun.turn_index)).where(QueryRun.conversation_id == conversation_id)
        )
        or 0
    )
    return conversation.id, turn_index + 1


async def create_run(
    session: AsyncSession,
    payload: QueryRunCreate,
    user_id: UUID,
    *,
    bypass_cache: bool = False,
) -> QueryRunResponse:
    data_version = await get_data_version(session)
    conversation_id, turn_index = await resolve_conversation(
        session, payload.conversation_id, user_id
    )
    if not bypass_cache and payload.conversation_id is None:
        cached = await find_cached_run(
            session,
            user_id=user_id,
            question=payload.question,
            data_version=data_version,
        )
        if cached is not None:
            await session.refresh(cached, attribute_names=["events"])
            return serialize_run(cached)

    run = QueryRun(
        user_id=user_id,
        question=payload.question,
        status="submitting",
        cache_key=build_cache_key(payload.question, data_version),
        data_version=data_version,
        cache_expires_at=cache_expires_at(),
        conversation_id=conversation_id,
        turn_index=turn_index,
    )
    session.add(run)
    await session.flush()
    await add_event(session, run, "submitted", "已提交查询")
    await add_audit(
        session,
        "query_run.created",
        run.id,
        {"question_length": len(run.question)},
        user_id=user_id,
    )
    await session.commit()
    await notify_event_subscribers(run.id)
    settings = get_settings()
    if settings.agent_enabled:
        from app.agent.service import schedule_agent_run

        schedule_agent_run(run.id)
    return await get_run_response(session, run.id, user_id)


async def get_run(session: AsyncSession, run_id: UUID, user_id: UUID) -> QueryRun:
    run = await session.scalar(
        select(QueryRun).where(QueryRun.id == run_id, QueryRun.user_id == user_id)
    )
    if run is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "query_run_not_found", "message": "Query run not found"},
        )
    return run


async def get_run_response(session: AsyncSession, run_id: UUID, user_id: UUID) -> QueryRunResponse:
    run = await get_run(session, run_id, user_id)
    await session.refresh(run, attribute_names=["events"])
    return serialize_run(run)


async def list_runs(
    session: AsyncSession, limit: int, offset: int, user_id: UUID
) -> QueryRunListResponse:
    owned_runs = select(QueryRun).where(QueryRun.user_id == user_id)
    total = int(await session.scalar(select(func.count()).select_from(owned_runs.subquery())) or 0)
    runs = list(
        (
            await session.scalars(
                owned_runs.order_by(QueryRun.created_at.desc()).limit(limit).offset(offset)
            )
        ).all()
    )
    for run in runs:
        await session.refresh(run, attribute_names=["events"])
    return QueryRunListResponse(
        items=[serialize_run(run) for run in runs], total=total, limit=limit, offset=offset
    )


async def result_page(
    session: AsyncSession, run_id: UUID, limit: int, offset: int, user_id: UUID
) -> PaginatedResultResponse:
    run = await get_run(session, run_id, user_id)
    rows = run.result_rows or []
    schema = [ResultSchemaField.model_validate(field) for field in (run.result_schema or [])]
    return PaginatedResultResponse(
        rows=rows[offset : offset + limit],
        schema=schema,
        total=run.result_total or len(rows),
        limit=limit,
        offset=offset,
    )


async def set_run_state(
    session: AsyncSession, run_id: UUID, action: str, user_id: UUID
) -> QueryRunResponse:
    run = await get_run(session, run_id, user_id)
    if run.status in TERMINAL_STATUSES:
        raise HTTPException(
            status_code=409,
            detail={"code": "query_run_terminal", "message": "Query run is already terminal"},
        )
    if action == "approve":
        if run.status != "awaiting_approval":
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "approval_not_required",
                    "message": "Query run is not waiting for approval",
                },
            )
        run.status = "streaming"
        event_type, message = "approval_granted", "已确认执行"
    else:
        run.status = "cancelled"
        run.completed_at = datetime.now(UTC)
        event_type, message = "run_cancelled", "查询已取消"
    await add_event(session, run, event_type, message)
    await add_audit(session, f"query_run.{action}", run.id, user_id=user_id)
    await session.commit()
    await notify_event_subscribers(run.id)
    if action == "cancel":
        from app.agent.service import cancel_agent_run

        cancel_agent_run(run.id)
    if action == "approve" and get_settings().agent_enabled:
        from app.agent.service import schedule_agent_run

        schedule_agent_run(run.id, approved=True)
    return await get_run_response(session, run.id, user_id)


async def list_events(
    session: AsyncSession, run_id: UUID, after_id: int, user_id: UUID
) -> list[QueryEvent]:
    await get_run(session, run_id, user_id)
    return list(
        (
            await session.scalars(
                select(QueryEvent)
                .where(QueryEvent.run_id == run_id, QueryEvent.sequence > after_id)
                .order_by(QueryEvent.sequence)
            )
        ).all()
    )


async def record_reconnect(
    session: AsyncSession, run_id: UUID, after_id: int, user_id: UUID
) -> None:
    run = await get_run(session, run_id, user_id)
    await session.execute(
        update(QueryRun)
        .where(QueryRun.id == run_id, QueryRun.user_id == user_id)
        .values(reconnect_count=QueryRun.reconnect_count + 1)
    )
    await session.refresh(run)
    await add_event(
        session,
        run,
        "reconnected",
        "SSE 已重连，正在恢复事件",
        {"after_id": after_id},
    )
    await add_audit(
        session,
        "query_run.sse_reconnected",
        run.id,
        {"after_id": after_id},
        user_id=user_id,
    )
    await session.commit()
    await notify_event_subscribers(run.id)


async def stream_events(run_id: UUID, after_id: int, user_id: UUID) -> AsyncIterator[str]:
    from app.db.session import SessionLocal

    settings = get_settings()
    last_id = after_id
    last_heartbeat = asyncio.get_running_loop().time()
    condition = asyncio.Condition()
    _event_conditions[run_id] = condition
    try:
        while True:
            async with SessionLocal() as session:
                run = await session.scalar(
                    select(QueryRun).where(QueryRun.id == run_id, QueryRun.user_id == user_id)
                )
                if run is None:
                    return
                events = await list_events(session, run_id, last_id, user_id)
                is_terminal = run.status in TERMINAL_STATUSES
            for event in events:
                last_id = event.sequence
                data = serialize_event(event).model_dump_json()
                yield f"id: {event.sequence}\nevent: {event.event_type}\ndata: {data}\n\n"
            if is_terminal and not events:
                yield "event: stream_end\ndata: {}\n\n"
                return
            now = asyncio.get_running_loop().time()
            if now - last_heartbeat >= settings.sse_heartbeat_seconds:
                yield ": heartbeat\n\n"
                last_heartbeat = now
            try:
                async with condition:
                    await asyncio.wait_for(
                        condition.wait(), timeout=settings.sse_poll_interval_seconds
                    )
            except TimeoutError:
                pass
    finally:
        if _event_conditions.get(run_id) is condition:
            _event_conditions.pop(run_id, None)


async def create_feedback(
    session: AsyncSession, payload: FeedbackCreate, user_id: UUID
) -> FeedbackResponse:
    run = await get_run(session, payload.run_id, user_id)
    feedback = Feedback(
        run_id=run.id, user_id=user_id, rating=payload.rating, comment=payload.comment
    )
    session.add(feedback)
    await session.flush()
    if payload.rating == "negative":
        session.add(
            EvaluationCandidate(
                question=run.question,
                run_id=run.id,
                feedback_id=feedback.id,
                comment=payload.comment,
            )
        )
    await add_audit(
        session, "feedback.created", run.id, {"rating": payload.rating}, user_id=user_id
    )
    await session.commit()
    await session.refresh(feedback)
    return FeedbackResponse(
        id=feedback.id,
        run_id=feedback.run_id,
        rating=feedback.rating,
        comment=feedback.comment,
        created_at=feedback.created_at,
    )


async def list_metrics(session: AsyncSession) -> list[MetricResponse]:
    metrics = (await session.scalars(select(Metric).order_by(Metric.name))).all()
    return [
        MetricResponse(
            name=item.name,
            definition=item.definition,
            source=item.source,
            updatedAt=item.updated_at,
        )
        for item in metrics
    ]


async def list_audit_logs(
    session: AsyncSession, limit: int, offset: int, user_id: UUID
) -> list[AuditLogResponse]:
    items = (
        await session.scalars(
            select(AuditLog)
            .where(AuditLog.user_id == user_id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return [
        AuditLogResponse(
            id=item.id,
            run_id=item.run_id,
            action=item.action,
            details=item.details,
            created_at=item.created_at,
        )
        for item in items
    ]
