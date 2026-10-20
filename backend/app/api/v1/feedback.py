from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.query_run import FeedbackCreate, FeedbackResponse
from app.services.query_service import create_feedback

router = APIRouter(prefix="/api/v1/feedback", tags=["feedback"])


@router.post("", response_model=FeedbackResponse, status_code=201, summary="Submit query feedback")
async def post_feedback(payload: FeedbackCreate, session: AsyncSession = Depends(get_db)) -> FeedbackResponse:
    return await create_feedback(session, payload)
