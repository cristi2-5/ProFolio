"""
Jobs Router — Job listing, filtering, and status management.

Provides endpoints for viewing matched jobs, filtering duplicates,
and updating application status.
"""

import logging
from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.job_scanner import JobScannerAgent
from app.database import async_session_factory, get_db
from app.dependencies.auth import get_current_user
from app.dependencies.jobs import get_user_job_or_403
from app.models.job import ScrapedJob, UserJob
from app.models.user import JobPreference, User
from app.schemas.benchmark import (
    BenchmarkCalculateRequest,
    BenchmarkScoreResponse,
    InsufficientPeersResponse,
)
from app.schemas.interview_coach import (
    InterviewPrepGenerateRequest,
    InterviewPrepListResponse,
    InterviewPrepResponse,
    InterviewPrepUpdateRequest,
)
from app.schemas.job import UserJobListResponse, UserJobResponse, UserJobStatusUpdate
from app.schemas.user import JobPreferenceCreate, JobPreferenceResponse
from app.services.benchmark_service import BenchmarkService, InsufficientPeersError
from app.services.interview_coach_service import InterviewCoachService
from app.services.job_service import JobService
from app.services.task_manager import TaskContext, get_task_manager
from app.utils.exceptions import AgentError
from app.utils.rate_limit import limiter, user_id_key

router = APIRouter(prefix="/api/jobs", tags=["Jobs"])

# Initialize logger and services
logger = logging.getLogger(__name__)
job_service = JobService()
interview_coach_service = InterviewCoachService()
benchmark_service = BenchmarkService()
job_scanner = JobScannerAgent()

# ------------------------------------------------------------------
# In-memory rate-limit cache for POST /jobs/scan
# Key: user_id (str), Value: datetime of last scan
# ------------------------------------------------------------------
_scan_last_called: dict[str, datetime] = {}

# Shared advisory-lock key for /jobs/scan (manual) and the daily cron.
# Same value on both sides — a process holding it blocks the other path.
SCAN_ADVISORY_LOCK = 0xCAFEBABE


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
    response_model=UserJobListResponse,
    summary="List matched jobs for the current user",
)
async def list_jobs(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status_filter: Annotated[
        Optional[str], Query(description="Filter by job status")
    ] = None,
    search: Annotated[
        Optional[str], Query(description="Search by title or company name")
    ] = None,
    sort_by: Annotated[
        str,
        Query(
            description="Sort column (match_score, created_at, company_name, job_title)"
        ),
    ] = "match_score",
    sort_order: Annotated[
        str, Query(description="Sort direction: asc or desc")
    ] = "desc",
    limit: Annotated[int, Query(ge=1, le=100, description="Page size")] = 20,
    offset: Annotated[int, Query(ge=0, description="Pagination offset")] = 0,
) -> UserJobListResponse:
    """List jobs matched to the authenticated user.

    Returns a paginated, filterable, searchable list of job matches.
    Jobs are ordered by the requested sort column and direction.

    Args:
        current_user: Authenticated user (injected).
        db: Database session (injected).
        status_filter: Optional status filter (new, applied, saved, hidden, duplicate).
        search: Optional text search on job title and company name.
        sort_by: Column to sort by.
        sort_order: 'asc' or 'desc'.
        limit: Page size (1-100).
        offset: Number of records to skip.

    Returns:
        UserJobListResponse: Paginated job list with total count.

    Raises:
        HTTPException: 400 if invalid status filter provided.
    """
    # Validate inputs
    valid_statuses = {"new", "applied", "saved", "hidden", "duplicate"}
    if status_filter and status_filter not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status filter. Must be one of: {', '.join(valid_statuses)}",
        )
    valid_sort_cols = {"match_score", "created_at", "company_name", "job_title"}
    if sort_by not in valid_sort_cols:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid sort_by. Must be one of: {', '.join(valid_sort_cols)}",
        )
    if sort_order not in {"asc", "desc"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="sort_order must be 'asc' or 'desc'",
        )

    try:
        jobs, total_count = await job_service.list_user_jobs(
            user_id=str(current_user.id),
            db=db,
            status_filter=status_filter,
            search=search,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=limit,
            offset=offset,
        )
        return UserJobListResponse(jobs=jobs, total_count=total_count)

    except Exception as e:
        logger.error(f"Error listing jobs for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch job listings",
        )


@router.get(
    "/interview-preps",
    response_model=InterviewPrepListResponse,
    summary="List all interview preparations for the current user",
)
async def list_user_interview_preps(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InterviewPrepListResponse:
    """List all interview preparation materials for the authenticated user.

    Provides overview of all jobs with interview prep materials,
    useful for dashboard display.

    Args:
        current_user: Authenticated user (injected).
        db: Database session (injected).

    Returns:
        InterviewPrepListResponse: List of interview prep summaries.
    """
    try:
        prep_summaries = await interview_coach_service.get_user_interview_preps(
            user=current_user,
            db=db,
        )

        return InterviewPrepListResponse(
            preparations=prep_summaries,
            total_count=len(prep_summaries),
        )

    except Exception as e:
        logger.error(f"Failed to list interview preps for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve interview preparations",
        )


@router.get(
    "/{user_job_id}",
    response_model=UserJobResponse,
    summary="Get individual job details",
)
async def get_job_by_id(
    user_job_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserJobResponse:
    """Retrieve details for a single job by its UserJob ID.

    Includes the scraped job content and current application status.

    Args:
        user_job_id: UUID of the UserJob record.
        current_user: Authenticated user (injected).
        db: Database session (injected).

    Returns:
        UserJobResponse: Detailed job information.

    Raises:
        HTTPException: 404 if job not found.
    """
    job = await job_service.get_user_job_by_id(
        user_job_id=user_job_id,
        user_id=str(current_user.id),
        db=db,
    )

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    return job


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

        # Update status using job service. We pass ``user_id`` so the
        # underlying atomic UPDATE is also scoped to the owner, eliminating
        # any TOCTOU window between the ownership SELECT above and the
        # write below.
        updated_user_job = await job_service.update_job_status(
            user_job_id=user_job_id,
            new_status=status_update.status,
            db=db,
            user_id=str(current_user.id),
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


@router.post(
    "/scan",
    response_model=dict,
    summary="Trigger job scan for current user (rate-limited: 1/hour)",
)
async def trigger_job_scan(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Manually trigger a job scan for the authenticated user.

    Calls the real Job Scanner Agent to fetch fresh results from the Adzuna API.
    Rate-limited to once per hour per user to prevent API abuse.
    Requires job preferences to be configured.

    Args:
        current_user: Authenticated user (injected).
        db: Database session (injected).

    Returns:
        dict: Scan results with new job count and status.

    Raises:
        HTTPException: 400 if no preferences set or rate limit exceeded.
                      503 if Adzuna credentials not configured.
                      500 if scan fails.
    """
    from app.config import get_settings as _get_settings

    settings = _get_settings()
    user_id_str = str(current_user.id)

    # --- Rate limiting (1 scan per hour, in-memory) ---
    now = datetime.now(timezone.utc)
    last_scan = _scan_last_called.get(user_id_str)
    if last_scan is not None:
        elapsed_seconds = (now - last_scan).total_seconds()
        limit_seconds = settings.job_scan_rate_limit_hours * 3600
        if elapsed_seconds < limit_seconds:
            remaining = int((limit_seconds - elapsed_seconds) / 60)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Scan rate limit reached. You can trigger a new scan in "
                    f"{remaining} minute(s). The daily cron runs automatically every "
                    f"{settings.job_scan_interval_hours} hours."
                ),
            )

    # --- Preferences check ---
    # Track whether we acquired the cross-process advisory lock so the
    # ``finally`` only releases what we actually took. SQLite tests skip
    # the lock entirely (advisory locks are PG-only).
    use_lock = False
    lock_acquired = False
    try:
        dialect = getattr(db.bind, "dialect", None)
        use_lock = dialect is not None and dialect.name == "postgresql"

        if use_lock:
            # Non-blocking try-lock: if a scan (manual or cron) is already
            # running we want immediate 429 feedback rather than tying up
            # a request worker for minutes.
            result = await db.execute(
                text("SELECT pg_try_advisory_lock(:k)").bindparams(k=SCAN_ADVISORY_LOCK)
            )
            lock_acquired = bool(result.scalar())
            if not lock_acquired:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="A scan is already running. Try again in a moment.",
                )

        stmt = select(JobPreference).where(JobPreference.user_id == current_user.id)
        result = await db.execute(stmt)
        preferences = result.scalar_one_or_none()

        if not preferences:
            # Don't block — the agent falls back to a "developer" query so users
            # without preferences can still browse jobs. Match scoring still
            # works without a CV (it just scores 0).
            logger.info(
                "Scan with no preferences for user %s — using default query",
                user_id_str,
            )

        # Mark the scan timestamp before running so concurrent requests are blocked
        _scan_last_called[user_id_str] = now

        # --- Run real job scanner ---
        logger.info(f"Manual job scan triggered for user {user_id_str}")
        new_jobs = await job_scanner.scan(user_id_str, db)

        return {
            "status": "success",
            "jobs_found": len(new_jobs),
            "message": f"Found {len(new_jobs)} new jobs matching your preferences",
            "jobs": new_jobs,
        }

    except HTTPException:
        # Restore rate-limit timestamp on HTTP errors so user can retry
        _scan_last_called.pop(user_id_str, None)
        raise
    except ValueError as e:
        # Adzuna credentials not configured
        _scan_last_called.pop(user_id_str, None)
        logger.error(f"Job scan config error for user {user_id_str}: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Job scan service is not configured. Please contact support.",
        )
    except Exception as e:
        _scan_last_called.pop(user_id_str, None)
        logger.error(f"Manual job scan failed for user {user_id_str}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Job scan failed. Please try again later.",
        )
    finally:
        if use_lock and lock_acquired:
            try:
                await db.execute(
                    text("SELECT pg_advisory_unlock(:k)").bindparams(
                        k=SCAN_ADVISORY_LOCK
                    )
                )
            except Exception as exc:
                # Don't mask the original exception (if any) — just log.
                # The lock is also session-scoped, so it'll be released
                # when the connection returns to the pool.
                logger.warning(f"Failed to release scan advisory lock: {exc}")


# ================================================================
# Interview Coach & Preparation Materials
# ================================================================


@router.post(
    "/{job_id}/generate-interview-prep",
    response_model=InterviewPrepResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate comprehensive interview preparation materials",
)
@limiter.limit("30/hour", key_func=user_id_key)
async def generate_interview_prep_materials(
    job_id: str,
    request: Request,
    payload: InterviewPrepGenerateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InterviewPrepResponse:
    """Generate AI-powered interview preparation materials for a specific job.

    Creates comprehensive interview prep including technical questions,
    behavioral scenarios, company research, technology cheat sheet,
    and personalized preparation strategy.

    Args:
        job_id: UUID of the target job.
        request: Generation preferences (include user background, etc.).
        current_user: Authenticated user (injected).
        db: Database session (injected).

    Returns:
        InterviewPrepResponse: Complete interview preparation materials.

    Raises:
        HTTPException: 404 if job not found, 400 if no user-job relationship,
                      500 if AI generation fails.
    """
    try:
        job, _ = await get_user_job_or_403(
            job_id=job_id,
            current_user=current_user,
            db=db,
        )

        prep_materials = (
            await interview_coach_service.generate_interview_prep_materials(
                user=current_user,
                job=job,
                db=db,
                include_user_background=payload.include_user_background,
                technical_count=payload.technical_count,
                behavioral_count=payload.behavioral_count,
            )
        )

        return InterviewPrepResponse(
            **prep_materials,
            job_title=job.job_title,
            company_name=job.company_name,
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except AgentError as e:
        logger.warning(f"Interview prep agent error for job {job_id}: {e.message}")
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.error(f"Failed to generate interview prep for job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate interview preparation materials",
        )


@router.post(
    "/{job_id}/generate-interview-prep-async",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Kick off interview prep generation in the background",
)
@limiter.limit("30/hour", key_func=user_id_key)
async def generate_interview_prep_async(
    job_id: str,
    request: Request,
    payload: InterviewPrepGenerateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Start generation on a background task and return a task_id.

    The client subscribes to ``GET /api/tasks/{task_id}/events`` (SSE)
    or polls ``GET /api/tasks/{task_id}`` to receive progress and the
    final result. This keeps the UI responsive for the 10-20 seconds
    the LLM normally blocks.
    """
    job, _ = await get_user_job_or_403(
        job_id=job_id,
        current_user=current_user,
        db=db,
    )

    include_background = payload.include_user_background
    technical_count = payload.technical_count
    behavioral_count = payload.behavioral_count
    user_id_str = str(current_user.id)

    async def worker(ctx: TaskContext) -> dict:
        """Run the service with its own DB session; publish progress."""
        await ctx.progress(0.1, message="Loading profile")
        # New session per task — the request-scoped ``db`` will be closed
        # as soon as we return from this endpoint.
        async with async_session_factory() as task_db:
            # Re-fetch the row bound to the task's session.
            task_job = await task_db.get(ScrapedJob, job_id)
            task_user = await task_db.get(User, current_user.id)
            if task_job is None or task_user is None:
                raise RuntimeError("Job or user disappeared before task could start")

            await ctx.progress(0.25, message="Extracting technologies")
            materials = await interview_coach_service.generate_interview_prep_materials(
                user=task_user,
                job=task_job,
                db=task_db,
                include_user_background=include_background,
                technical_count=technical_count,
                behavioral_count=behavioral_count,
            )
            await ctx.progress(0.95, message="Finalising")
            return {
                **materials,
                "job_title": task_job.job_title,
                "company_name": task_job.company_name,
            }

    task_id = await get_task_manager().submit(owner_user_id=user_id_str, worker=worker)
    return {"task_id": task_id, "status": "pending"}


@router.get(
    "/{job_id}/interview-prep",
    response_model=InterviewPrepResponse,
    summary="Get interview preparation materials for a job",
)
async def get_interview_prep_materials(
    job_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InterviewPrepResponse:
    """Retrieve existing interview preparation materials for a job.

    Args:
        job_id: UUID of the target job.
        current_user: Authenticated user (injected).
        db: Database session (injected).

    Returns:
        InterviewPrepResponse: Existing interview preparation materials.

    Raises:
        HTTPException: 404 if job or prep materials not found,
                      403 if user doesn't have access.
    """
    try:
        job, _ = await get_user_job_or_403(
            job_id=job_id,
            current_user=current_user,
            db=db,
        )

        prep_materials = await interview_coach_service.get_interview_prep_materials(
            user=current_user,
            job_id=job_id,
            db=db,
        )

        if not prep_materials:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No interview preparation materials found for this job",
            )

        response_data = dict(prep_materials)
        response_data.setdefault("generated_at", datetime.now(timezone.utc).isoformat())
        response_data["job_title"] = job.job_title
        response_data["company_name"] = job.company_name
        return InterviewPrepResponse(**response_data)

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to get interview prep for job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve interview preparation materials",
        )


@router.patch(
    "/{job_id}/interview-prep",
    response_model=InterviewPrepResponse,
    summary="Update interview preparation materials",
)
async def update_interview_prep_materials(
    job_id: str,
    updates: InterviewPrepUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InterviewPrepResponse:
    """Update existing interview preparation materials with user customizations.

    Allows users to modify AI-generated content, add personal notes,
    and customize preparation materials to their preferences.

    Args:
        job_id: UUID of the target job.
        updates: Updated preparation materials.
        current_user: Authenticated user (injected).
        db: Database session (injected).

    Returns:
        InterviewPrepResponse: Updated interview preparation materials.

    Raises:
        HTTPException: 404 if job or prep materials not found,
                      403 if user doesn't have access.
    """
    try:
        job, _ = await get_user_job_or_403(
            job_id=job_id,
            current_user=current_user,
            db=db,
        )

        updates_dict = updates.model_dump(exclude_none=True)

        updated_materials = (
            await interview_coach_service.update_interview_prep_materials(
                user=current_user,
                job_id=job_id,
                updated_materials=updates_dict,
                db=db,
            )
        )

        response_data = dict(updated_materials)
        response_data.setdefault("generated_at", datetime.now(timezone.utc).isoformat())
        response_data["job_title"] = job.job_title
        response_data["company_name"] = job.company_name
        return InterviewPrepResponse(**response_data)

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to update interview prep for job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update interview preparation materials",
        )


# ================================================================
# Benchmark Scoring & Competitive Analysis
# ================================================================


@router.post(
    "/{job_id}/calculate-benchmark",
    response_model=BenchmarkScoreResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Calculate GDPR-compliant benchmark score for a job",
    responses={
        422: {
            "model": InsufficientPeersResponse,
            "description": "Not enough peers for reliable scoring",
        },
        400: {"description": "User not opted into benchmarking"},
    },
)
async def calculate_benchmark_score(
    job_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BenchmarkScoreResponse:
    """Calculate competitive benchmark score for a user and specific job.

    Compares user's skills and experience against anonymized peer group
    to generate percentile ranking. Requires user to be opted into
    benchmarking and minimum 30 eligible peers.

    Args:
        job_id: UUID of the target job.
        current_user: Authenticated user (injected).
        db: Database session (injected).

    Returns:
        BenchmarkScoreResponse: Complete benchmark analysis with score and skill gaps.

    Raises:
        HTTPException: 404 if job not found, 400 if not opted in,
                      422 if insufficient peers, 500 if calculation fails.
    """
    try:
        job, _ = await get_user_job_or_403(
            job_id=job_id,
            current_user=current_user,
            db=db,
        )

        result = await benchmark_service.calculate_benchmark_score(
            user=current_user,
            job=job,
            db=db,
        )

        return BenchmarkScoreResponse(
            id=result.benchmark_id,
            user_id=str(current_user.id),
            job_id=str(job.id),
            job_title=job.job_title,
            company_name=job.company_name,
            score=result.score,
            user_match_score=result.user_match_score,
            peer_mean_match_score=result.peer_mean_match_score,
            peer_group={
                "size": result.peer_group_size,
                "seniority_level": result.seniority_level,
                "niche": result.niche,
                "min_peers_required": benchmark_service.MINIMUM_PEER_COUNT,
                "benchmark_opt_in_required": True,
            },
            matched_skills=result.matched_skills,
            skill_gaps=[
                {
                    "skill": item["skill"],
                    "priority": item["priority"],
                    "peer_frequency": item["peer_frequency"],
                    "recommendation": item["recommendation"],
                }
                for item in result.missing_skills
            ],
            recommended_keywords=result.recommended_keywords,
            calculated_at=result.calculated_at,
            privacy_compliant=True,
        )

    except HTTPException:
        raise
    except InsufficientPeersError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "insufficient_peers",
                "message": str(exc),
                "peers_found": exc.peers_found,
                "peers_required": exc.peers_required,
                "suggestions": [
                    "Wait for more users at your seniority/niche to opt in",
                    "Double-check your seniority level and niche in account settings",
                ],
            },
        )

    except ValueError as exc:
        if "not opted into benchmarking" in str(exc):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "You must opt into benchmarking to calculate competitive scores. "
                    "Update your preferences in account settings."
                ),
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    except Exception as exc:
        logger.error(f"Failed to calculate benchmark for job {job_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to calculate benchmark score. Please try again later.",
        )
