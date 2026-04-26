"""
Resumes Router — Upload, Parse, and CRUD endpoints.

Handles CV file upload (PDF/DOCX) and triggers the CV Profiler agent
for automatic parsing. Also supports manual corrections to parsed data.
"""

import uuid
from typing import Annotated, List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.resume import ResumeResponse, ResumeUpdate
from app.services.resume_service import ResumeService
from app.utils.exceptions import (
    AgentError,
    CVProfilerError,
    NotFoundError,
    raise_http_exception,
)

router = APIRouter(prefix="/api/resumes", tags=["Resumes"])
resume_service = ResumeService()


@router.post(
    "/upload",
    response_model=ResumeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and parse a CV file",
)
async def upload_resume(
    file: UploadFile = File(..., description="CV file (PDF or DOCX, max 10MB)"),
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: AsyncSession = Depends(get_db),
) -> ResumeResponse:
    """Upload a CV file and trigger automatic parsing with AI.

    Accepts .pdf and .docx files up to 10MB. The CV Profiler agent extracts
    structured data (skills, experience, education, technologies) using GPT-4.
    First uploaded resume is automatically set as active.

    Args:
        file: Uploaded CV file (PDF or DOCX format).
        current_user: Authenticated user (from JWT token).
        db: Async database session (injected).

    Returns:
        ResumeResponse: Parsed resume data with metadata.

    Raises:
        HTTPException 400: If file format is unsupported or validation fails.
        HTTPException 401: If user is not authenticated.
        HTTPException 413: If file size exceeds 10MB limit.
        HTTPException 500: If AI parsing or storage fails.
    """
    try:
        # Validate file is provided
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="No file provided"
            )

        # Upload and parse via service layer
        resume = await resume_service.upload_and_parse(db, current_user, file)
        await db.commit()

        return ResumeResponse.model_validate(resume)

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except CVProfilerError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "We couldn't parse your CV — try uploading a clearer "
                "text-based PDF or DOCX"
            ),
        )
    except AgentError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Resume processing failed: {str(e)}",
        )


@router.get(
    "/",
    response_model=List[ResumeResponse],
    summary="List user's resumes",
)
async def list_resumes(
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: AsyncSession = Depends(get_db),
) -> List[ResumeResponse]:
    """List all resumes for the authenticated user.

    Returns resumes ordered by creation date (newest first).
    Each resume includes parsed data and metadata.

    Args:
        current_user: Authenticated user (from JWT token).
        db: Async database session (injected).

    Returns:
        List[ResumeResponse]: List of user's resumes with parsed data.

    Raises:
        HTTPException 401: If user is not authenticated.
    """
    resumes = await resume_service.list_user_resumes(db, current_user.id)
    return [ResumeResponse.model_validate(resume) for resume in resumes]


@router.get(
    "/{resume_id}",
    response_model=ResumeResponse,
    summary="Get specific resume",
)
async def get_resume(
    resume_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: AsyncSession = Depends(get_db),
) -> ResumeResponse:
    """Get a specific resume by ID with full parsed data.

    Args:
        resume_id: UUID of the resume to retrieve.
        current_user: Authenticated user (from JWT token).
        db: Async database session (injected).

    Returns:
        ResumeResponse: Resume with complete parsed data.

    Raises:
        HTTPException 401: If user is not authenticated.
        HTTPException 404: If resume not found or user doesn't own it.
    """
    try:
        resume = await resume_service.get_user_resume(db, current_user.id, resume_id)
        return ResumeResponse.model_validate(resume)
    except NotFoundError as e:
        raise_http_exception(e)


@router.put(
    "/{resume_id}",
    response_model=ResumeResponse,
    summary="Update resume data",
)
async def update_resume(
    resume_id: uuid.UUID,
    update_data: ResumeUpdate,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: AsyncSession = Depends(get_db),
) -> ResumeResponse:
    """Update resume with manual corrections or set as active.

    Allows users to manually correct AI parsing results or change
    which resume is active for job applications.

    Args:
        resume_id: UUID of the resume to update.
        update_data: Fields to update (parsed_data and/or is_active).
        current_user: Authenticated user (from JWT token).
        db: Async database session (injected).

    Returns:
        ResumeResponse: Updated resume data.

    Raises:
        HTTPException 401: If user is not authenticated.
        HTTPException 404: If resume not found or user doesn't own it.
    """
    try:
        resume = await resume_service.update_resume(
            db,
            current_user.id,
            resume_id,
            parsed_data=update_data.parsed_data,
            is_active=update_data.is_active,
        )
        await db.commit()

        return ResumeResponse.model_validate(resume)
    except NotFoundError as e:
        raise_http_exception(e)


@router.delete(
    "/{resume_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete resume",
)
async def delete_resume(
    resume_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a resume and its associated files.

    Permanently removes the resume record and deletes the uploaded file
    from storage. This action cannot be undone.

    Args:
        resume_id: UUID of the resume to delete.
        current_user: Authenticated user (from JWT token).
        db: Async database session (injected).

    Raises:
        HTTPException 401: If user is not authenticated.
        HTTPException 404: If resume not found or user doesn't own it.
    """
    try:
        await resume_service.delete_resume(db, current_user.id, resume_id)
        await db.commit()
    except NotFoundError as e:
        raise_http_exception(e)


@router.post(
    "/{resume_id}/activate",
    response_model=ResumeResponse,
    summary="Set resume as active",
)
async def set_active_resume(
    resume_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: AsyncSession = Depends(get_db),
) -> ResumeResponse:
    """Set a resume as the user's active CV for job applications.

    Only one resume can be active at a time. Setting a new active resume
    will deactivate the previously active one.

    Args:
        resume_id: UUID of the resume to activate.
        current_user: Authenticated user (from JWT token).
        db: Async database session (injected).

    Returns:
        ResumeResponse: The activated resume.

    Raises:
        HTTPException 401: If user is not authenticated.
        HTTPException 404: If resume not found or user doesn't own it.
    """
    try:
        resume = await resume_service.set_active_resume(db, current_user.id, resume_id)
        await db.commit()

        return ResumeResponse.model_validate(resume)
    except NotFoundError as e:
        raise_http_exception(e)


@router.get(
    "/active/current",
    response_model=ResumeResponse,
    summary="Get user's active resume",
)
async def get_active_resume(
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: AsyncSession = Depends(get_db),
) -> ResumeResponse:
    """Get the user's currently active resume.

    Returns the resume marked as active for job applications.
    If no resume is active, returns 404.

    Args:
        current_user: Authenticated user (from JWT token).
        db: Async database session (injected).

    Returns:
        ResumeResponse: The active resume with parsed data.

    Raises:
        HTTPException 401: If user is not authenticated.
        HTTPException 404: If no active resume found.
    """
    resume = await resume_service.get_active_resume(db, current_user.id)

    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active resume found. Please upload and activate a resume first.",
        )

    return ResumeResponse.model_validate(resume)
