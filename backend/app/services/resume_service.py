"""
Resume Service — Business logic for CV upload and management.

Handles file storage, triggers the CV Profiler agent for parsing,
and manages resume CRUD operations with proper user isolation.
"""

import os
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import UploadFile
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.cv_profiler import CVProfilerAgent
from app.config import get_settings
from app.models.resume import ParsedResume
from app.models.user import User
from app.utils.exceptions import NotFoundError, raise_http_exception

settings = get_settings()
logger = logging.getLogger(__name__)


class ResumeService:
    """Handles resume-related business logic.

    Methods:
        upload_and_parse: Save file, trigger CV Profiler, store results.
        list_user_resumes: Retrieve all resumes for a user.
        get_user_resume: Get specific resume by ID.
        update_resume: Apply manual corrections to parsed data.
        delete_resume: Remove resume and associated files.
        set_active_resume: Set a resume as the user's active CV.
    """

    def __init__(self):
        """Initialize the Resume Service."""
        self.cv_profiler = CVProfilerAgent()
        self.upload_dir = Path(settings.upload_dir)

        # Ensure upload directory exists
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Resume upload directory: {self.upload_dir.absolute()}")

    async def upload_and_parse(
        self,
        db: AsyncSession,
        user: User,
        file: UploadFile
    ) -> ParsedResume:
        """Upload CV file, parse with AI, and store results.

        Args:
            db: Database session.
            user: Authenticated user uploading the CV.
            file: Uploaded file (PDF or DOCX).

        Returns:
            ParsedResume: Created resume record with parsed data.

        Raises:
            ValueError: If file validation fails or parsing errors occur.
            Exception: If file storage or database operations fail.
        """
        try:
            # Generate unique filename
            file_id = str(uuid.uuid4())
            file_extension = Path(file.filename).suffix.lower()
            stored_filename = f"{file_id}{file_extension}"
            file_path = self.upload_dir / stored_filename

            # Save uploaded file to disk
            logger.info(f"Saving CV file for user {user.id}: {file.filename}")
            with open(file_path, "wb") as buffer:
                content = await file.read()
                buffer.write(content)

            # Parse CV with AI agent
            logger.info(f"Parsing CV with AI: {file.filename}")
            parsed_data = await self.cv_profiler.parse(str(file_path), file.filename)

            # Deactivate other resumes if this is the first one
            existing_count = await self._count_user_resumes(db, user.id)
            is_active = existing_count == 0  # First resume is automatically active

            # Create resume record in database
            resume = ParsedResume(
                user_id=user.id,
                original_filename=file.filename,
                file_url=str(file_path),  # Local file path (can be replaced with S3 URL later)
                parsed_data=parsed_data,
                is_active=is_active
            )

            db.add(resume)
            await db.flush()
            await db.refresh(resume)

            logger.info(f"Resume processed successfully: {resume.id}")
            return resume

        except ValueError as e:
            # Clean up file if parsing failed
            if file_path.exists():
                file_path.unlink()
            logger.error(f"Resume processing validation error: {e}")
            raise
        except Exception as e:
            # Clean up file if processing failed
            if file_path.exists():
                file_path.unlink()
            logger.error(f"Resume processing failed: {e}")
            raise Exception(f"Resume processing failed: {str(e)}")

    async def list_user_resumes(self, db: AsyncSession, user_id: uuid.UUID) -> List[ParsedResume]:
        """Retrieve all resumes for a user ordered by creation date.

        Args:
            db: Database session.
            user_id: User's UUID.

        Returns:
            List[ParsedResume]: User's resumes, newest first.
        """
        result = await db.execute(
            select(ParsedResume)
            .where(ParsedResume.user_id == user_id)
            .order_by(ParsedResume.created_at.desc())
        )
        return result.scalars().all()

    async def get_user_resume(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        resume_id: uuid.UUID
    ) -> ParsedResume:
        """Get specific resume by ID with user ownership validation.

        Args:
            db: Database session.
            user_id: User's UUID (for ownership validation).
            resume_id: Resume's UUID.

        Returns:
            ParsedResume: The requested resume.

        Raises:
            NotFoundError: If resume doesn't exist or user doesn't own it.
        """
        result = await db.execute(
            select(ParsedResume).where(
                ParsedResume.id == resume_id,
                ParsedResume.user_id == user_id
            )
        )
        resume = result.scalar_one_or_none()

        if not resume:
            raise NotFoundError("Resume", str(resume_id))

        return resume

    async def update_resume(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        resume_id: uuid.UUID,
        parsed_data: Optional[dict] = None,
        is_active: Optional[bool] = None
    ) -> ParsedResume:
        """Update resume with manual corrections or active status.

        Args:
            db: Database session.
            user_id: User's UUID (for ownership validation).
            resume_id: Resume's UUID.
            parsed_data: Updated parsed CV data (optional).
            is_active: Set as active resume (optional).

        Returns:
            ParsedResume: Updated resume.

        Raises:
            NotFoundError: If resume doesn't exist or user doesn't own it.
        """
        # Verify ownership
        resume = await self.get_user_resume(db, user_id, resume_id)

        # Prepare update fields
        update_fields = {
            "updated_at": datetime.now(timezone.utc)
        }

        if parsed_data is not None:
            update_fields["parsed_data"] = parsed_data

        if is_active is not None:
            if is_active:
                # Deactivate other resumes first
                await self._deactivate_user_resumes(db, user_id)
            update_fields["is_active"] = is_active

        # Apply updates
        await db.execute(
            update(ParsedResume)
            .where(ParsedResume.id == resume_id)
            .values(**update_fields)
        )

        # Refresh and return
        await db.refresh(resume)
        return resume

    async def delete_resume(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        resume_id: uuid.UUID
    ) -> None:
        """Delete resume and associated files.

        Args:
            db: Database session.
            user_id: User's UUID (for ownership validation).
            resume_id: Resume's UUID.

        Raises:
            NotFoundError: If resume doesn't exist or user doesn't own it.
        """
        # Verify ownership and get resume
        resume = await self.get_user_resume(db, user_id, resume_id)

        # Delete physical file if it exists
        if resume.file_url:
            file_path = Path(resume.file_url)
            if file_path.exists():
                try:
                    file_path.unlink()
                    logger.info(f"Deleted CV file: {file_path}")
                except Exception as e:
                    logger.warning(f"Failed to delete CV file {file_path}: {e}")

        # Delete database record
        await db.delete(resume)
        logger.info(f"Deleted resume record: {resume_id}")

    async def set_active_resume(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        resume_id: uuid.UUID
    ) -> ParsedResume:
        """Set a resume as the user's active CV.

        Args:
            db: Database session.
            user_id: User's UUID.
            resume_id: Resume's UUID to activate.

        Returns:
            ParsedResume: The activated resume.

        Raises:
            NotFoundError: If resume doesn't exist or user doesn't own it.
        """
        # Deactivate all user resumes first
        await self._deactivate_user_resumes(db, user_id)

        # Activate the specified resume
        return await self.update_resume(db, user_id, resume_id, is_active=True)

    async def get_active_resume(self, db: AsyncSession, user_id: uuid.UUID) -> Optional[ParsedResume]:
        """Get user's currently active resume.

        Args:
            db: Database session.
            user_id: User's UUID.

        Returns:
            ParsedResume | None: Active resume or None if no active resume.
        """
        result = await db.execute(
            select(ParsedResume).where(
                ParsedResume.user_id == user_id,
                ParsedResume.is_active == True
            )
        )
        return result.scalar_one_or_none()

    # =====================================================================
    # Private Helper Methods
    # =====================================================================

    async def _count_user_resumes(self, db: AsyncSession, user_id: uuid.UUID) -> int:
        """Count total resumes for a user."""
        result = await db.execute(
            select(ParsedResume).where(ParsedResume.user_id == user_id)
        )
        return len(result.scalars().all())

    async def _deactivate_user_resumes(self, db: AsyncSession, user_id: uuid.UUID) -> None:
        """Deactivate all resumes for a user."""
        await db.execute(
            update(ParsedResume)
            .where(
                ParsedResume.user_id == user_id,
                ParsedResume.is_active == True
            )
            .values(is_active=False, updated_at=datetime.now(timezone.utc))
        )