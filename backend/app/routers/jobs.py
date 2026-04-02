"""
Jobs Router — Job listing, filtering, and status management.

Provides endpoints for viewing matched jobs, filtering duplicates,
and updating application status.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

router = APIRouter(prefix="/api/jobs", tags=["Jobs"])


@router.get(
    "/",
    summary="List matched jobs for the current user",
)
async def list_jobs(
    db: AsyncSession = Depends(get_db),
) -> list:
    """List jobs matched to the authenticated user.

    Returns jobs sorted by match score, excluding duplicates
    and already-applied positions.

    Args:
        db: Async database session (injected).

    Returns:
        list: List of matched jobs with scores and status.
    """
    # TODO: Implement in Phase 2
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Job listing — implementation in Phase 2.",
    )


@router.patch(
    "/{job_id}/status",
    summary="Update job application status",
)
async def update_job_status(
    job_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Update status of a user-job relationship.

    Valid statuses: new, applied, saved, hidden, duplicate.

    Args:
        job_id: UUID of the job to update.
        db: Async database session (injected).

    Returns:
        dict: Updated job status.
    """
    # TODO: Implement in Phase 2
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Job status update — implementation in Phase 2.",
    )
