from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.query_run import MetricResponse
from app.services.query_service import list_metrics

router = APIRouter(prefix="/api/v1/metrics", tags=["metrics"])


@router.get("", response_model=list[MetricResponse], summary="List metric definitions")
async def get_metrics(session: AsyncSession = Depends(get_db)) -> list[MetricResponse]:
    return await list_metrics(session)
