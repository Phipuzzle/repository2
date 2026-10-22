from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authentication import get_current_user
from app.core.config import get_settings
from app.db.models import User
from app.db.session import get_db
from app.schemas.query_run import (
    PaginatedResultResponse,
    QueryRunCreate,
    QueryRunListResponse,
    QueryRunResponse,
)
from app.services.query_service import (
    create_run,
    get_run_response,
    list_events,
    list_runs,
    record_reconnect,
    result_page,
    set_run_state,
    stream_events,
)

router = APIRouter(prefix="/api/v1/query-runs", tags=["query-runs"])
settings = get_settings()


@router.post(
    "",
    response_model=QueryRunResponse,
    status_code=201,
    summary="Create a query run",
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {"example": {"question": "查询今年各区域月销售额并生成趋势图"}}
            }
        }
    },
)
async def post_query_run(
    payload: QueryRunCreate,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> QueryRunResponse:
    return await create_run(session, payload, user.id)


@router.get("", response_model=QueryRunListResponse, summary="List query runs")
async def get_query_runs(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> QueryRunListResponse:
    return await list_runs(session, limit, offset, user.id)


@router.get("/{run_id}", response_model=QueryRunResponse, summary="Get query run")
async def get_query_run(
    run_id: UUID,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> QueryRunResponse:
    return await get_run_response(session, run_id, user.id)


@router.get("/{run_id}/events", summary="Stream query run events")
async def get_query_run_events(
    run_id: UUID,
    last_event_id: int | None = Header(default=None, alias="Last-Event-ID", ge=0),
    after_id: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    await list_events(session, run_id, -1, user.id)
    cursor = max(after_id, last_event_id or 0)
    if cursor > 0:
        await record_reconnect(session, run_id, cursor, user.id)

    async def event_stream() -> AsyncIterator[str]:
        async for event in stream_events(run_id, cursor, user.id):
            yield event

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/{run_id}/result", response_model=PaginatedResultResponse, summary="Get a result page")
async def get_query_result(
    run_id: UUID,
    limit: int = Query(default=settings.query_default_limit, ge=1, le=settings.query_max_limit),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PaginatedResultResponse:
    return await result_page(session, run_id, limit, offset, user.id)


@router.post("/{run_id}/approve", response_model=QueryRunResponse, summary="Approve a query run")
async def approve_query_run(
    run_id: UUID,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> QueryRunResponse:
    return await set_run_state(session, run_id, "approve", user.id)


@router.post("/{run_id}/cancel", response_model=QueryRunResponse, summary="Cancel a query run")
async def cancel_query_run(
    run_id: UUID,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> QueryRunResponse:
    return await set_run_state(session, run_id, "cancel", user.id)
