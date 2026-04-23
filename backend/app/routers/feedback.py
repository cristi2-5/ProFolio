"""
Feedback Router — submit/list/stats endpoints for beta feedback.

Three endpoints:
    * POST /api/feedback       — submit feedback on AI-generated content
    * GET  /api/feedback/mine  — fetch the current user's own history
    * GET  /api/feedback/stats — aggregated counts/averages for QA

The ``stats`` route is open to any authenticated user during the beta
so students can see the overall health of the platform; swap for a
role check once a staff role exists.
"""

from __future__ import annotations

import logging
from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.feedback import (
    FeedbackCreateRequest,
    FeedbackResponse,
    FeedbackStatsEntry,
    FeedbackStatsResponse,
)
from app.services.feedback_service import FeedbackService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/feedback", tags=["Feedback"])
feedback_service = FeedbackService()


@router.post(
    "",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit feedback on a piece of AI-generated content",
)
async def submit_feedback(
    payload: FeedbackCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FeedbackResponse:
    try:
        row = await feedback_service.create(
            user=current_user, payload=payload, db=db
        )
    except Exception as exc:
        logger.error("Failed to record feedback: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record feedback",
        )
    return FeedbackResponse(
        id=str(row.id),
        user_id=str(row.user_id),
        content_type=row.content_type,
        content_id=row.content_id,
        rating=row.rating,
        comment=row.comment,
        created_at=row.created_at,
    )


@router.get(
    "/mine",
    response_model=List[FeedbackResponse],
    summary="List the current user's feedback submissions",
)
async def list_my_feedback(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> List[FeedbackResponse]:
    rows = await feedback_service.list_for_user(user=current_user, db=db, limit=limit)
    return [
        FeedbackResponse(
            id=str(row.id),
            user_id=str(row.user_id),
            content_type=row.content_type,
            content_id=row.content_id,
            rating=row.rating,
            comment=row.comment,
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.get(
    "/stats",
    response_model=FeedbackStatsResponse,
    summary="Aggregate feedback stats per content type",
)
async def get_feedback_stats(
    _current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FeedbackStatsResponse:
    stats = await feedback_service.aggregate_stats(db=db)
    entries = [FeedbackStatsEntry(**entry) for entry in stats]
    return FeedbackStatsResponse(
        entries=entries,
        total_count=sum(entry.count for entry in entries),
    )
