"""
Jobs Router — Job listing, filtering, and status management.

Provides endpoints for viewing matched jobs, filtering duplicates,
and updating application status.
"""

import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import JobPreference, User
from app.models.job import UserJob
from app.schemas.user import JobPreferenceCreate, JobPreferenceResponse
from app.schemas.job import UserJobStatusUpdate, UserJobResponse
from app.services.job_service import JobService

router = APIRouter(prefix="/api/jobs", tags=["Jobs"])

# Initialize logger and job service
logger = logging.getLogger(__name__)
job_service = JobService()


# ================================================================
# Job Preferences Management
# ================================================================

@router.post(
    "/preferences",
    response_model=JobPreferenceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Save or update job search criteria",
)
async def save_job_preferences(
    preferences: JobPreferenceCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JobPreferenceResponse:
    """Save or update job search preferences for the authenticated user.

    Creates new preferences if none exist, or updates existing ones.
    Users can only have one set of preferences at a time.

    Args:
        preferences: Job search criteria (title, location, keywords).
        current_user: Authenticated user (injected).
        db: Database session (injected).

    Returns:
        JobPreferenceResponse: Created or updated preferences.
    """
    # Check if user already has preferences
    stmt = select(JobPreference).where(JobPreference.user_id == current_user.id)
    result = await db.execute(stmt)
    existing_preference = result.scalar_one_or_none()

    if existing_preference:
        # Update existing preferences
        existing_preference.desired_title = preferences.desired_title
        existing_preference.location_type = preferences.location_type
        existing_preference.keywords = preferences.keywords
        job_preference = existing_preference
    else:
        # Create new preferences
        job_preference = JobPreference(
            user_id=current_user.id,
            desired_title=preferences.desired_title,
            location_type=preferences.location_type,
            keywords=preferences.keywords,
        )
        db.add(job_preference)

    await db.commit()
    await db.refresh(job_preference)
    return job_preference


@router.get(
    "/preferences",
    response_model=JobPreferenceResponse | None,
    summary="Get current job search criteria",
)
async def get_job_preferences(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JobPreferenceResponse | None:
    """Retrieve the authenticated user's job search preferences.

    Args:
        current_user: Authenticated user (injected).
        db: Database session (injected).

    Returns:
        JobPreferenceResponse | None: User's preferences or None if not set.
    """
    stmt = select(JobPreference).where(JobPreference.user_id == current_user.id)
    result = await db.execute(stmt)
    job_preference = result.scalar_one_or_none()
    return job_preference


# ================================================================
# Job Listing & Management
# ================================================================

@router.get(
    "/",
    response_model=list[UserJobResponse],
    summary="List matched jobs for the current user",
)
async def list_jobs(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status_filter: Annotated[Optional[str], Query(description="Filter by job status")] = None,
    limit: Annotated[int, Query(ge=1, le=100, description="Maximum number of jobs to return")] = 50,
) -> list[UserJobResponse]:
    """List jobs matched to the authenticated user.

    Returns jobs sorted by match score, with optional status filtering.
    Jobs are ordered by match score (highest first) and creation date.

    Args:
        current_user: Authenticated user (injected).
        db: Database session (injected).
        status_filter: Optional status filter (new, applied, saved, hidden, duplicate).
        limit: Maximum number of jobs to return (1-100).

    Returns:
        list[UserJobResponse]: List of matched jobs with scores and status.

    Raises:
        HTTPException: 400 if invalid status filter provided.
    """
    # Validate status filter if provided
    valid_statuses = {"new", "applied", "saved", "hidden", "duplicate"}
    if status_filter and status_filter not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status filter. Must be one of: {', '.join(valid_statuses)}",
        )

    try:
        user_jobs = await job_service.list_user_jobs(
            user_id=str(current_user.id),
            db=db,
            status_filter=status_filter,
            limit=limit,
        )
        return user_jobs

    except Exception as e:
        logger.error(f"Error listing jobs for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch job listings",
        )


@router.patch(
    "/{user_job_id}/status",
    response_model=UserJobResponse,
    summary="Update job application status",
)
async def update_job_status(
    user_job_id: str,
    status_update: UserJobStatusUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserJobResponse:
    """Update status of a user-job relationship.

    Valid statuses: new, applied, saved, hidden, duplicate.
    Only the job owner can update their job status.

    Args:
        user_job_id: UUID of the UserJob record to update.
        status_update: New status data.
        current_user: Authenticated user (injected).
        db: Database session (injected).

    Returns:
        UserJobResponse: Updated user-job with new status.

    Raises:
        HTTPException: 404 if job not found, 403 if not owner, 400 if invalid status.
    """
    try:
        # Validate that UserJob exists and belongs to current user
        stmt = (
            select(UserJob)
            .options(selectinload(UserJob.job))
            .where(UserJob.id == user_job_id, UserJob.user_id == current_user.id)
        )
        result = await db.execute(stmt)
        user_job = result.scalar_one_or_none()

        if not user_job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found or you don't have permission to update it",
            )

        # Update status using job service
        updated_user_job = await job_service.update_job_status(
            user_job_id=user_job_id,
            new_status=status_update.status,
            db=db,
        )

        if not updated_user_job:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update job status",
            )

        return updated_user_job

    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        logger.error(f"Error updating job status for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update job status",
        )


@router.get(
    "/scan",
    response_model=dict,
    summary="Trigger job scan for current user",
)
async def trigger_job_scan(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Manually trigger job scan for the authenticated user.

    Useful for testing or immediate job discovery without waiting for cron.
    Requires user to have job preferences configured.

    Args:
        current_user: Authenticated user (injected).
        db: Database session (injected).

    Returns:
        dict: Scan results with job count and status.

    Raises:
        HTTPException: 400 if no preferences set, 500 if scan fails.
    """
    from app.agents.job_scanner import JobScannerAgent

    try:
        # Check if user has preferences
        stmt = select(JobPreference).where(JobPreference.user_id == current_user.id)
        result = await db.execute(stmt)
        preferences = result.scalar_one_or_none()

        if not preferences:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please set job preferences before scanning for jobs",
            )

        # Trigger scan
        scanner = JobScannerAgent()
        new_jobs = await scanner.scan(str(current_user.id), db)

        return {
            "status": "success",
            "jobs_found": len(new_jobs),
            "message": f"Found {len(new_jobs)} new jobs matching your preferences",
            "jobs": new_jobs[:5] if new_jobs else [],  # Return first 5 as preview
        }

    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        logger.error(f"Manual job scan failed for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Job scan failed. Please try again later.",
        )
