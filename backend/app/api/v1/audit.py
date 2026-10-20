from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.query_run import AuditLogResponse
from app.services.query_service import list_audit_logs

router = APIRouter(prefix="/api/v1/audit-logs", tags=["audit"])


@router.get("", response_model=list[AuditLogResponse], summary="List audit logs")
async def get_audit_logs(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db),
) -> list[AuditLogResponse]:
    return await list_audit_logs(session, limit, offset)
