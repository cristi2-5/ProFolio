"""
Job authorization dependency helpers.

Provides reusable helpers to enforce per-user ownership of ``ScrapedJob``
rows via the ``UserJob`` join table. Prevents IDOR (Insecure Direct
Object Reference) vulnerabilities where any authenticated user could
otherwise access any global job by ID.
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import ScrapedJob, UserJob
from app.models.user import User


async def get_user_job_or_403(
    job_id: str | uuid.UUID,
    current_user: User,
    db: AsyncSession,
) -> tuple[ScrapedJob, UserJob]:
    """Fetch a ScrapedJob and verify current_user has a UserJob link to it.

    Performs a single SQL query joining ``scraped_jobs`` and ``user_jobs``
    to fetch both rows in one round-trip when the user is authorized. If
    the join yields nothing, falls back to a second query to disambiguate
    "job does not exist" (404) from "job exists but user is not linked"
    (403).

    Args:
        job_id: UUID of the target ScrapedJob (str or UUID accepted).
        current_user: The authenticated user.
        db: Active async database session.

    Returns:
        tuple[ScrapedJob, UserJob]: The job and the user's link record.

    Raises:
        HTTPException: 404 if the job does not exist.
        HTTPException: 403 if the job exists but the user has no UserJob
            row referencing it.
    """
    stmt = (
        select(ScrapedJob, UserJob)
        .join(UserJob, UserJob.job_id == ScrapedJob.id)
        .where(
            ScrapedJob.id == job_id,
            UserJob.user_id == current_user.id,
        )
    )
    result = await db.execute(stmt)
    row = result.first()

    if row is not None:
        job, user_job = row
        return job, user_job

    # No (job, user_job) pair: figure out whether the job is missing
    # entirely (404) or simply not linked to this user (403).
    job = await db.get(ScrapedJob, job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have access to this job",
    )
