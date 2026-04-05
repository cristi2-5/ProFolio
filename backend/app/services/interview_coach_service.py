"""
Interview Coach Service — Business logic integration layer.

Coordinates interview preparation generation between the InterviewCoachAgent
and database operations. Handles preparation material storage, retrieval,
and updates for job-specific interview coaching.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.interview_coach import InterviewCoachAgent
from app.models.user import User
from app.models.job import ScrapedJob, UserJob
from app.models.resume import ParsedResume

logger = logging.getLogger(__name__)


class InterviewCoachService:
    """Service for managing interview preparation materials."""

    def __init__(self):
        """Initialize interview coach service with agent."""
        self.interview_coach = InterviewCoachAgent()

    async def generate_interview_prep_materials(
        self,
        user: User,
        job: ScrapedJob,
        db: AsyncSession,
        include_user_background: bool = True,
    ) -> Dict[str, Any]:
        """Generate comprehensive interview preparation materials for a job.

        Args:
            user: User requesting interview prep.
            job: Target job for interview preparation.
            db: Database session for storing results.
            include_user_background: Whether to include user's CV background.

        Returns:
            Dict containing all interview preparation materials.

        Raises:
            ValueError: If user has no active resume and include_user_background=True.
            Exception: If AI generation fails.
        """
        try:
            # Get user's active resume for background context
            user_background = None
            if include_user_background:
                stmt = select(ParsedResume).where(
                    ParsedResume.user_id == user.id,
                    ParsedResume.is_active == True,
                )
                result = await db.execute(stmt)
                active_resume = result.scalar_one_or_none()

                if active_resume and active_resume.parsed_data:
                    user_background = active_resume.parsed_data

            # Get or create UserJob record
            stmt = select(UserJob).where(
                UserJob.user_id == user.id,
                UserJob.job_id == job.id,
            )
            result = await db.execute(stmt)
            user_job = result.scalar_one_or_none()

            if not user_job:
                raise ValueError("No UserJob record found for this user and job")

            # Generate interview preparation materials
            prep_materials = await self.interview_coach.generate_interview_prep_materials(
                job_description=job.description,
                job_title=job.job_title,
                company_name=job.company_name,
                user_experience_level=user.seniority_level,
                user_background=user_background,
            )

            # Store materials in UserJob
            user_job.interview_prep = prep_materials
            user_job.updated_at = datetime.now(timezone.utc)

            await db.commit()
            await db.refresh(user_job)

            logger.info(f"Generated interview prep for user {user.id} and job {job.id}")
            return prep_materials

        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to generate interview prep: {e}")
            raise

    async def get_interview_prep_materials(
        self,
        user: User,
        job_id: str,
        db: AsyncSession,
    ) -> Optional[Dict[str, Any]]:
        """Retrieve existing interview preparation materials.

        Args:
            user: User requesting materials.
            job_id: Job ID to get materials for.
            db: Database session.

        Returns:
            Interview prep materials or None if not found.

        Raises:
            ValueError: If UserJob not found or unauthorized.
        """
        try:
            stmt = select(UserJob).where(
                UserJob.user_id == user.id,
                UserJob.job_id == job_id,
            )
            result = await db.execute(stmt)
            user_job = result.scalar_one_or_none()

            if not user_job:
                raise ValueError("No interview prep materials found for this job")

            return user_job.interview_prep

        except Exception as e:
            logger.error(f"Failed to retrieve interview prep: {e}")
            raise

    async def update_interview_prep_materials(
        self,
        user: User,
        job_id: str,
        updated_materials: Dict[str, Any],
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """Update existing interview preparation materials.

        Allows users to customize AI-generated materials with their own notes,
        additional questions, or modified preparation strategies.

        Args:
            user: User updating materials.
            job_id: Job ID to update materials for.
            updated_materials: New or modified preparation materials.
            db: Database session.

        Returns:
            Updated interview prep materials.

        Raises:
            ValueError: If UserJob not found or unauthorized.
        """
        try:
            stmt = select(UserJob).where(
                UserJob.user_id == user.id,
                UserJob.job_id == job_id,
            )
            result = await db.execute(stmt)
            user_job = result.scalar_one_or_none()

            if not user_job:
                raise ValueError("No interview prep materials found for this job")

            # Merge with existing materials (preserve structure)
            if user_job.interview_prep:
                existing = user_job.interview_prep.copy()
                existing.update(updated_materials)
                user_job.interview_prep = existing
            else:
                user_job.interview_prep = updated_materials

            user_job.updated_at = datetime.now(timezone.utc)

            await db.commit()
            await db.refresh(user_job)

            logger.info(f"Updated interview prep for user {user.id} and job {job_id}")
            return user_job.interview_prep

        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to update interview prep: {e}")
            raise

    async def generate_additional_questions(
        self,
        user: User,
        job: ScrapedJob,
        question_type: str,
        count: int = 5,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """Generate additional interview questions of a specific type.

        Useful for expanding existing preparation materials with more
        technical, behavioral, or company-specific questions.

        Args:
            user: User requesting additional questions.
            job: Target job for questions.
            question_type: Type of questions (technical, behavioral, company).
            count: Number of additional questions to generate.
            db: Database session.

        Returns:
            Dict containing additional questions of the requested type.

        Raises:
            ValueError: If invalid question_type provided.
        """
        try:
            valid_types = ["technical", "behavioral", "company"]
            if question_type not in valid_types:
                raise ValueError(f"Invalid question type. Must be one of: {valid_types}")

            # Generate additional questions based on type
            if question_type == "technical":
                additional_content = await self.interview_coach.generate_technical_questions(
                    job_description=job.description,
                    job_title=job.job_title,
                    user_experience_level=user.seniority_level,
                    question_count=count,
                )
            elif question_type == "behavioral":
                additional_content = await self.interview_coach.generate_behavioral_questions(
                    job_description=job.description,
                    company_name=job.company_name,
                    job_title=job.job_title,
                    question_count=count,
                )
            else:  # company
                additional_content = await self.interview_coach.generate_company_research(
                    company_name=job.company_name,
                    job_title=job.job_title,
                    job_description=job.description,
                )

            logger.info(f"Generated {count} additional {question_type} questions")
            return {f"additional_{question_type}_questions": additional_content}

        except Exception as e:
            logger.error(f"Failed to generate additional questions: {e}")
            raise

    async def get_user_interview_preps(
        self,
        user: User,
        db: AsyncSession,
    ) -> list[Dict[str, Any]]:
        """Get all interview preparation materials for a user.

        Returns summary of all jobs with interview prep materials,
        useful for dashboard overview.

        Args:
            user: User to get materials for.
            db: Database session.

        Returns:
            List of job summaries with interview prep status.
        """
        try:
            stmt = (
                select(UserJob)
                .where(
                    UserJob.user_id == user.id,
                    UserJob.interview_prep.is_not(None),
                )
                .order_by(UserJob.updated_at.desc())
            )
            result = await db.execute(stmt)
            user_jobs = result.scalars().all()

            prep_summaries = []
            for user_job in user_jobs:
                # Get job details
                job = await db.get(ScrapedJob, user_job.job_id)
                if not job:
                    continue

                # Create summary
                prep_summary = {
                    "user_job_id": str(user_job.id),
                    "job_id": str(job.id),
                    "job_title": job.job_title,
                    "company_name": job.company_name,
                    "match_score": user_job.match_score,
                    "status": user_job.status,
                    "updated_at": user_job.updated_at.isoformat(),
                    "has_technical_questions": False,
                    "has_behavioral_questions": False,
                    "has_company_research": False,
                    "has_cheat_sheet": False,
                    "has_preparation_strategy": False,
                }

                # Check what materials are available
                if user_job.interview_prep:
                    prep_data = user_job.interview_prep
                    prep_summary.update({
                        "has_technical_questions": bool(prep_data.get("technical_questions")),
                        "has_behavioral_questions": bool(prep_data.get("behavioral_questions")),
                        "has_company_research": bool(prep_data.get("company_research")),
                        "has_cheat_sheet": bool(prep_data.get("technology_cheat_sheet")),
                        "has_preparation_strategy": bool(prep_data.get("preparation_strategy")),
                    })

                prep_summaries.append(prep_summary)

            return prep_summaries

        except Exception as e:
            logger.error(f"Failed to get user interview preps: {e}")
            raise