"""
Interview Coach Service — Orchestrates the interview-prep flow.

Responsibilities:
    - Load user background (active CV) when requested.
    - Resolve the UserJob row for the (user, job) pair.
    - Delegate generation to ``InterviewCoachAgent``.
    - Persist the bundle on ``UserJob.interview_prep`` as JSONB.

Keeps request-shaping logic out of the router and data-access details out
of the agent.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.interview_coach import InterviewCoachAgent
from app.models.job import ScrapedJob, UserJob
from app.models.user import User
from app.services.peer_data import load_active_resume

logger = logging.getLogger(__name__)


class InterviewCoachService:
    """Business-layer entrypoint for the Interview Coach."""

    def __init__(self) -> None:
        self.interview_coach = InterviewCoachAgent()

    async def generate_interview_prep_materials(
        self,
        *,
        user: User,
        job: ScrapedJob,
        db: AsyncSession,
        include_user_background: bool = True,
        technical_count: int = 3,
        behavioral_count: int = 2,
    ) -> Dict[str, Any]:
        """Generate and persist interview prep for a user/job pair.

        Raises:
            ValueError: If no UserJob row exists for the pair.
            Exception: Propagates any LLM failure (after rolling back the tx).
        """
        try:
            user_background: Optional[Dict[str, Any]] = None
            if include_user_background:
                active_resume = await load_active_resume(user, db)
                if active_resume and active_resume.parsed_data:
                    user_background = active_resume.parsed_data

            user_job = await self._get_user_job(user, job, db)
            if not user_job:
                raise ValueError("No UserJob record found for this user and job")

            materials = await self.interview_coach.generate_interview_prep_materials(
                job_description=job.description or "",
                job_title=job.job_title,
                company_name=job.company_name,
                user_experience_level=getattr(user, "seniority_level", None),
                user_background=user_background,
                technical_count=technical_count,
                behavioral_count=behavioral_count,
            )

            materials["generated_at"] = datetime.now(timezone.utc).isoformat()
            user_job.interview_prep = materials
            user_job.updated_at = datetime.now(timezone.utc)

            await db.commit()
            await db.refresh(user_job)

            logger.info(
                "Interview prep generated for user=%s job=%s", user.id, job.id
            )
            return materials

        except Exception:
            await db.rollback()
            raise

    async def get_interview_prep_materials(
        self,
        *,
        user: User,
        job_id: str,
        db: AsyncSession,
    ) -> Optional[Dict[str, Any]]:
        """Return the stored prep bundle for a user/job, or None."""
        user_job = await self._get_user_job_by_job_id(user, job_id, db)
        if not user_job:
            raise ValueError("No interview prep materials found for this job")
        return user_job.interview_prep

    async def update_interview_prep_materials(
        self,
        *,
        user: User,
        job_id: str,
        updated_materials: Dict[str, Any],
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """Merge-update the stored prep bundle with user edits."""
        try:
            user_job = await self._get_user_job_by_job_id(user, job_id, db)
            if not user_job:
                raise ValueError("No interview prep materials found for this job")

            if user_job.interview_prep:
                merged = {**user_job.interview_prep, **updated_materials}
            else:
                merged = dict(updated_materials)

            user_job.interview_prep = merged
            user_job.updated_at = datetime.now(timezone.utc)

            await db.commit()
            await db.refresh(user_job)
            return user_job.interview_prep

        except Exception:
            await db.rollback()
            raise

    async def get_user_interview_preps(
        self,
        *,
        user: User,
        db: AsyncSession,
    ) -> List[Dict[str, Any]]:
        """Return a flat summary of every prep bundle belonging to the user."""
        stmt = (
            select(UserJob)
            .options(selectinload(UserJob.job))
            .where(
                UserJob.user_id == user.id,
                UserJob.interview_prep.is_not(None),
            )
            .order_by(UserJob.updated_at.desc())
        )
        result = await db.execute(stmt)
        user_jobs = result.scalars().all()

        summaries: List[Dict[str, Any]] = []
        for user_job in user_jobs:
            job = user_job.job
            if not job:
                continue
            prep = user_job.interview_prep or {}
            summaries.append(
                {
                    "user_job_id": str(user_job.id),
                    "job_id": str(job.id),
                    "job_title": job.job_title,
                    "company_name": job.company_name,
                    "match_score": user_job.match_score,
                    "status": user_job.status,
                    "updated_at": user_job.updated_at.isoformat(),
                    "has_technical_questions": bool(prep.get("technical_questions")),
                    "has_behavioral_questions": bool(prep.get("behavioral_questions")),
                    "has_cheat_sheet": bool(prep.get("technology_cheat_sheet")),
                }
            )
        return summaries

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _get_user_job(
        self, user: User, job: ScrapedJob, db: AsyncSession
    ) -> Optional[UserJob]:
        stmt = select(UserJob).where(
            UserJob.user_id == user.id,
            UserJob.job_id == job.id,
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_user_job_by_job_id(
        self, user: User, job_id: str, db: AsyncSession
    ) -> Optional[UserJob]:
        stmt = select(UserJob).where(
            UserJob.user_id == user.id,
            UserJob.job_id == job_id,
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()
