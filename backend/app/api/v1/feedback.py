from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authentication import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.schemas.query_run import FeedbackCreate, FeedbackResponse
from app.services.query_service import create_feedback

router = APIRouter(prefix="/api/v1/feedback", tags=["feedback"])


@router.post("", response_model=FeedbackResponse, status_code=201, summary="Submit query feedback")
async def post_feedback(
    payload: FeedbackCreate,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FeedbackResponse:
    return await create_feedback(session, payload, user.id)
