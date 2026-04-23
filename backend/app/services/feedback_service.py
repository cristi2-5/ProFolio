"""
Feedback Service — persistence + aggregation for user feedback.

Thin orchestration layer over the ``feedback`` table. Keeps the router
honest (no raw ORM in endpoint handlers) and centralises the aggregate
query so stats consumers don't have to re-derive the bucketing logic.
"""

from __future__ import annotations

import logging
from typing import Dict, List

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.feedback import Feedback
from app.models.user import User
from app.schemas.feedback import FeedbackCreateRequest

logger = logging.getLogger(__name__)


class FeedbackService:
    """Business logic for feedback collection + aggregation."""

    async def create(
        self, *, user: User, payload: FeedbackCreateRequest, db: AsyncSession
    ) -> Feedback:
        """Persist a single feedback row for the given user."""
        row = Feedback(
            user_id=user.id,
            content_type=payload.content_type.value,
            content_id=payload.content_id,
            rating=payload.rating,
            comment=payload.comment,
        )
        db.add(row)
        try:
            await db.commit()
            await db.refresh(row)
        except Exception:
            await db.rollback()
            raise
        logger.info(
            "Feedback recorded user=%s type=%s rating=%d",
            user.id,
            payload.content_type.value,
            payload.rating,
        )
        return row

    async def list_for_user(
        self, *, user: User, db: AsyncSession, limit: int = 50
    ) -> List[Feedback]:
        """Return the user's own feedback history."""
        stmt = (
            select(Feedback)
            .where(Feedback.user_id == user.id)
            .order_by(Feedback.created_at.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def aggregate_stats(self, *, db: AsyncSession) -> List[Dict[str, object]]:
        """Return count / mean / low-rating count bucketed by content type.

        Intentionally unrestricted by user — this is the view used for
        product QA during the beta. The router is responsible for any
        authZ gating (e.g. restrict to staff) before calling this.
        """
        low_rating_expr = func.count().filter(Feedback.rating <= 2)
        stmt = (
            select(
                Feedback.content_type,
                func.count().label("count"),
                func.avg(Feedback.rating).label("average"),
                low_rating_expr.label("low_rating_count"),
            )
            .group_by(Feedback.content_type)
            .order_by(Feedback.content_type)
        )
        result = await db.execute(stmt)
        return [
            {
                "content_type": row.content_type,
                "count": int(row.count),
                "average_rating": float(round(row.average or 0.0, 2)),
                "low_rating_count": int(row.low_rating_count or 0),
            }
            for row in result.all()
        ]
