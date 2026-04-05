"""
CV Optimizer Service — Business logic for CV optimization and export.

Coordinates CV optimization, cover letter generation, and PDF export
functionality for job-specific application materials.
"""

import logging
import uuid
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.cv_optimizer import CVOptimizerAgent
from app.models.job import ScrapedJob, UserJob
from app.models.resume import ParsedResume
from app.models.user import User
from app.utils.pdf_export import pdf_exporter, PDFExportError

logger = logging.getLogger(__name__)


class CVOptimizerService:
    """Service for CV optimization and application material generation.

    Provides high-level business logic for optimizing CVs for specific jobs,
    generating cover letters, and exporting professional PDF documents.

    Attributes:
        cv_optimizer: AI agent for CV optimization and cover letter generation.
    """

    def __init__(self):
        """Initialize CV optimizer service with AI agent."""
        self.cv_optimizer = CVOptimizerAgent()

    async def optimize_cv_for_job(
        self,
        user: User,
        job: ScrapedJob,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """Optimize user's active CV for a specific job posting.

        Retrieves user's active resume, uses AI to optimize it for the job,
        and stores the optimized version in the UserJob record.

        Args:
            user: User requesting CV optimization.
            job: Target job posting for optimization.
            db: Database session.

        Returns:
            dict: Optimized CV data with ATS improvements.

        Raises:
            ValueError: If user has no active resume or UserJob doesn't exist.
            Exception: If AI optimization fails.
        """
        logger.info(f"Optimizing CV for user {user.id} and job {job.id}")

        try:
            # Get user's active resume
            stmt = (
                select(ParsedResume)
                .where(ParsedResume.user_id == user.id, ParsedResume.is_active == True)
                .order_by(desc(ParsedResume.created_at))
            )
            result = await db.execute(stmt)
            active_resume = result.scalar_one_or_none()

            if not active_resume:
                raise ValueError(f"User {user.id} has no active resume")

            # Get or create UserJob record
            stmt = select(UserJob).where(
                UserJob.user_id == user.id, UserJob.job_id == job.id
            )
            result = await db.execute(stmt)
            user_job = result.scalar_one_or_none()

            if not user_job:
                raise ValueError(f"No UserJob record found for user {user.id} and job {job.id}")

            # Perform AI-powered CV optimization
            optimized_cv = await self.cv_optimizer.optimize_cv_for_job(
                parsed_cv=active_resume.parsed_data,
                job_description=job.description or "",
                job_title=job.job_title,
                company_name=job.company_name,
            )

            # Store optimized CV in UserJob record
            user_job.optimized_cv = optimized_cv
            await db.commit()
            await db.refresh(user_job)

            logger.info(f"CV optimization completed for user {user.id}, job {job.id}")
            return optimized_cv

        except Exception as e:
            logger.error(f"CV optimization failed: {e}")
            await db.rollback()
            raise

    async def generate_cover_letter(
        self,
        user: User,
        job: ScrapedJob,
        db: AsyncSession,
    ) -> str:
        """Generate personalized cover letter for job application.

        Creates AI-generated cover letter tailored to the job requirements
        and user's background, then stores it in the UserJob record.

        Args:
            user: User requesting cover letter generation.
            job: Target job posting.
            db: Database session.

        Returns:
            str: Generated cover letter text.

        Raises:
            ValueError: If user has no active resume or UserJob doesn't exist.
            Exception: If AI generation fails.
        """
        logger.info(f"Generating cover letter for user {user.id} and job {job.id}")

        try:
            # Get user's active resume for context
            stmt = (
                select(ParsedResume)
                .where(ParsedResume.user_id == user.id, ParsedResume.is_active == True)
                .order_by(desc(ParsedResume.created_at))
            )
            result = await db.execute(stmt)
            active_resume = result.scalar_one_or_none()

            if not active_resume:
                raise ValueError(f"User {user.id} has no active resume for cover letter generation")

            # Get UserJob record
            stmt = select(UserJob).where(
                UserJob.user_id == user.id, UserJob.job_id == job.id
            )
            result = await db.execute(stmt)
            user_job = result.scalar_one_or_none()

            if not user_job:
                raise ValueError(f"No UserJob record found for user {user.id} and job {job.id}")

            # Generate AI-powered cover letter
            cover_letter = await self.cv_optimizer.generate_cover_letter(
                parsed_cv=active_resume.parsed_data,
                job_description=job.description or "",
                job_title=job.job_title,
                company_name=job.company_name,
                user_name=user.full_name,
            )

            # Store cover letter in UserJob record
            user_job.cover_letter = cover_letter
            await db.commit()
            await db.refresh(user_job)

            logger.info(f"Cover letter generated for user {user.id}, job {job.id}")
            return cover_letter

        except Exception as e:
            logger.error(f"Cover letter generation failed: {e}")
            await db.rollback()
            raise

    async def export_optimized_cv_pdf(
        self,
        user: User,
        job_id: str,
        db: AsyncSession,
    ) -> Tuple[bytes, str]:
        """Export optimized CV as PDF document.

        Retrieves optimized CV from UserJob record and generates
        a professional PDF document suitable for job applications.

        Args:
            user: User requesting PDF export.
            job_id: Job ID for the optimized CV.
            db: Database session.

        Returns:
            tuple: (PDF binary data, suggested filename)

        Raises:
            ValueError: If optimized CV not found.
            PDFExportError: If PDF generation fails.
        """
        logger.info(f"Exporting optimized CV PDF for user {user.id}, job {job_id}")

        try:
            # Get UserJob record with optimized CV
            stmt = (
                select(UserJob)
                .where(UserJob.user_id == user.id, UserJob.job_id == job_id)
            )
            result = await db.execute(stmt)
            user_job = result.scalar_one_or_none()

            if not user_job or not user_job.optimized_cv:
                raise ValueError("No optimized CV found for this job")

            # Generate PDF from optimized CV data
            pdf_data = pdf_exporter.export_cv_to_pdf(
                optimized_cv=user_job.optimized_cv,
                user_name=user.full_name or "Resume",
            )

            # Generate filename
            safe_name = (user.full_name or "resume").replace(" ", "_")
            filename = f"{safe_name}_optimized_cv.pdf"

            logger.info(f"CV PDF exported successfully: {len(pdf_data)} bytes")
            return pdf_data, filename

        except Exception as e:
            logger.error(f"CV PDF export failed: {e}")
            raise

    async def export_cover_letter_pdf(
        self,
        user: User,
        job: ScrapedJob,
        db: AsyncSession,
    ) -> Tuple[bytes, str]:
        """Export cover letter as PDF document.

        Retrieves cover letter from UserJob record and generates
        a professional PDF document for job applications.

        Args:
            user: User requesting PDF export.
            job: Job posting for the cover letter.
            db: Database session.

        Returns:
            tuple: (PDF binary data, suggested filename)

        Raises:
            ValueError: If cover letter not found.
            PDFExportError: If PDF generation fails.
        """
        logger.info(f"Exporting cover letter PDF for user {user.id}, job {job.id}")

        try:
            # Get UserJob record with cover letter
            stmt = select(UserJob).where(
                UserJob.user_id == user.id, UserJob.job_id == job.id
            )
            result = await db.execute(stmt)
            user_job = result.scalar_one_or_none()

            if not user_job or not user_job.cover_letter:
                raise ValueError("No cover letter found for this job")

            # Generate PDF from cover letter text
            pdf_data = pdf_exporter.export_cover_letter_to_pdf(
                cover_letter_text=user_job.cover_letter,
                user_name=user.full_name or "Applicant",
                job_title=job.job_title,
                company_name=job.company_name,
            )

            # Generate filename
            safe_name = (user.full_name or "cover_letter").replace(" ", "_")
            safe_company = job.company_name.replace(" ", "_").replace("/", "_")
            filename = f"{safe_name}_cover_letter_{safe_company}.pdf"

            logger.info(f"Cover letter PDF exported successfully: {len(pdf_data)} bytes")
            return pdf_data, filename

        except Exception as e:
            logger.error(f"Cover letter PDF export failed: {e}")
            raise

    async def get_optimization_suggestions(
        self,
        user: User,
        job_description: str,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """Get AI-powered suggestions for CV improvement.

        Analyzes user's current CV against job requirements and provides
        specific recommendations without performing full optimization.

        Args:
            user: User requesting suggestions.
            job_description: Target job description for analysis.
            db: Database session.

        Returns:
            dict: Structured improvement suggestions.

        Raises:
            ValueError: If user has no active resume.
        """
        logger.info(f"Generating optimization suggestions for user {user.id}")

        try:
            # Get user's active resume
            stmt = (
                select(ParsedResume)
                .where(ParsedResume.user_id == user.id, ParsedResume.is_active == True)
                .order_by(desc(ParsedResume.created_at))
            )
            result = await db.execute(stmt)
            active_resume = result.scalar_one_or_none()

            if not active_resume:
                raise ValueError(f"User {user.id} has no active resume")

            # Get AI-powered suggestions
            suggestions = await self.cv_optimizer.get_optimization_suggestions(
                parsed_cv=active_resume.parsed_data,
                job_description=job_description,
            )

            logger.info(f"Optimization suggestions generated for user {user.id}")
            return suggestions

        except Exception as e:
            logger.error(f"Failed to generate optimization suggestions: {e}")
            raise

    async def get_user_optimized_materials(
        self,
        user: User,
        db: AsyncSession,
    ) -> list[Dict[str, Any]]:
        """Get all optimized materials (CVs and cover letters) for a user.

        Retrieves all UserJob records with optimized content for the user,
        including job details and optimization status.

        Args:
            user: User to get materials for.
            db: Database session.

        Returns:
            list: List of dictionaries containing job and optimization info.
        """
        logger.info(f"Retrieving optimized materials for user {user.id}")

        try:
            # Get all UserJob records with optimized content
            stmt = (
                select(UserJob)
                .where(
                    UserJob.user_id == user.id,
                    (UserJob.optimized_cv.isnot(None)) | (UserJob.cover_letter.isnot(None))
                )
                .order_by(desc(UserJob.updated_at))
            )
            result = await db.execute(stmt)
            user_jobs = result.scalars().all()

            materials = []
            for user_job in user_jobs:
                # Get job details
                job = await db.get(ScrapedJob, user_job.job_id)
                if job:
                    material_info = {
                        "user_job_id": str(user_job.id),
                        "job_id": str(job.id),
                        "job_title": job.job_title,
                        "company_name": job.company_name,
                        "has_optimized_cv": user_job.optimized_cv is not None,
                        "has_cover_letter": user_job.cover_letter is not None,
                        "match_score": user_job.match_score,
                        "status": user_job.status,
                        "updated_at": user_job.updated_at,
                    }
                    materials.append(material_info)

            logger.info(f"Retrieved {len(materials)} optimized materials for user {user.id}")
            return materials

        except Exception as e:
            logger.error(f"Failed to retrieve optimized materials: {e}")
            raise