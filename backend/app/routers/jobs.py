"""
Jobs Router — Job listing, filtering, and status management.

Provides endpoints for viewing matched jobs, filtering duplicates,
and updating application status.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import JobPreference, User
from app.schemas.user import JobPreferenceCreate, JobPreferenceResponse
from app.schemas.job import UserJobStatusUpdate

router = APIRouter(prefix="/api/jobs", tags=["Jobs"])


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
    response_model=list,
    summary="List matched jobs for the current user",
)
async def list_jobs(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list:
    """List jobs matched to the authenticated user.

    Returns jobs sorted by match score, excluding duplicates
    and already-applied positions.

    Args:
        current_user: Authenticated user (injected).
        db: Async database session (injected).

    Returns:
        list: List of matched jobs with scores and status.
    """
    # TODO: Implement full job listing logic in next commit
    # For now, return empty list since job scanner isn't implemented yet
    return []


@router.patch(
    "/{job_id}/status",
    response_model=dict,
    summary="Update job application status",
)
async def update_job_status(
    job_id: str,
    status_update: UserJobStatusUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Update status of a user-job relationship.

    Valid statuses: new, applied, saved, hidden, duplicate.

    Args:
        job_id: UUID of the job to update.
        status_update: New status data.
        current_user: Authenticated user (injected).
        db: Async database session (injected).

    Returns:
        dict: Updated job status.
    """
    # TODO: Implement full status update logic in next commit
    # For now, return acknowledgment since UserJob model relationships aren't fully implemented yet
    return {"job_id": job_id, "status": status_update.status, "message": "Status update received (implementation pending)"}
