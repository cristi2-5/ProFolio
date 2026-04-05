"""
Jobs Router — Job listing, filtering, and status management.

Provides endpoints for viewing matched jobs, filtering duplicates,
and updating application status.
"""

import logging
from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import JobPreference, User
from app.models.job import UserJob, ScrapedJob
from app.schemas.user import JobPreferenceCreate, JobPreferenceResponse
from app.schemas.job import UserJobStatusUpdate, UserJobResponse
from app.schemas.interview_coach import (
    InterviewPrepGenerateRequest,
    InterviewPrepResponse,
    InterviewPrepUpdateRequest,
    AdditionalQuestionsRequest,
    AdditionalQuestionsResponse,
    InterviewPrepListResponse,
)
from app.schemas.benchmark import (
    BenchmarkCalculateRequest,
    BenchmarkScoreResponse,
    InsufficientPeersResponse,
)
from app.services.job_service import JobService
from app.services.interview_coach_service import InterviewCoachService
from app.services.benchmark_service import BenchmarkService, InsufficientPeersError

router = APIRouter(prefix="/api/jobs", tags=["Jobs"])

# Initialize logger and services
logger = logging.getLogger(__name__)
job_service = JobService()
interview_coach_service = InterviewCoachService()
benchmark_service = BenchmarkService()


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


@router.post(
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

        # TODO: Temporarily return mock data for testing
        # This bypasses the Adzuna API which requires valid credentials
        logger.info(f"Job scan triggered for user {current_user.id} (mock mode)")

        mock_jobs = [
            {
                "id": "mock-1",
                "company_name": "TechCorp Inc.",
                "job_title": "Senior Python Developer",
                "location": "Remote",
                "external_url": "https://example.com/job1"
            },
            {
                "id": "mock-2",
                "company_name": "StartupXYZ",
                "job_title": "Full Stack Engineer",
                "location": "Remote",
                "external_url": "https://example.com/job2"
            }
        ]

        return {
            "status": "success",
            "jobs_found": len(mock_jobs),
            "message": f"Found {len(mock_jobs)} new jobs matching your preferences (mock data)",
            "jobs": mock_jobs,
        }

    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        logger.error(f"Manual job scan failed for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Job scan failed. Please try again later.",
        )


# ================================================================
# Interview Coach & Preparation Materials
# ================================================================

@router.post(
    "/{job_id}/generate-interview-prep",
    response_model=InterviewPrepResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate comprehensive interview preparation materials",
)
async def generate_interview_prep_materials(
    job_id: str,
    request: InterviewPrepGenerateRequest,
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
        # Get job details
        job = await db.get(ScrapedJob, job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found",
            )

        # Generate interview prep materials
        prep_materials = await interview_coach_service.generate_interview_prep_materials(
            user=current_user,
            job=job,
            db=db,
            include_user_background=request.include_user_background,
        )

        # Convert to response model
        response_data = prep_materials.copy()
        response_data.update({
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "job_title": job.job_title,
            "company_name": job.company_name,
        })

        return InterviewPrepResponse(**response_data)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to generate interview prep for job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate interview preparation materials",
        )


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
        # Get job details
        job = await db.get(ScrapedJob, job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found",
            )

        # Get prep materials
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

        # Convert to response model
        response_data = prep_materials.copy()
        response_data.update({
            "generated_at": response_data.get("generated_at", datetime.now(timezone.utc).isoformat()),
            "job_title": job.job_title,
            "company_name": job.company_name,
        })

        return InterviewPrepResponse(**response_data)

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
        # Get job details
        job = await db.get(ScrapedJob, job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found",
            )

        # Convert Pydantic model to dict, excluding None values
        updates_dict = updates.dict(exclude_none=True)

        # Update prep materials
        updated_materials = await interview_coach_service.update_interview_prep_materials(
            user=current_user,
            job_id=job_id,
            updated_materials=updates_dict,
            db=db,
        )

        # Convert to response model
        response_data = updated_materials.copy()
        response_data.update({
            "generated_at": response_data.get("generated_at", datetime.now(timezone.utc).isoformat()),
            "job_title": job.job_title,
            "company_name": job.company_name,
        })

        return InterviewPrepResponse(**response_data)

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


@router.post(
    "/{job_id}/generate-additional-questions",
    response_model=AdditionalQuestionsResponse,
    summary="Generate additional interview questions of a specific type",
)
async def generate_additional_questions(
    job_id: str,
    request: AdditionalQuestionsRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdditionalQuestionsResponse:
    """Generate additional interview questions of a specific type.

    Useful for expanding existing preparation materials with more
    technical, behavioral, or company-specific questions.

    Args:
        job_id: UUID of the target job.
        request: Question type and count preferences.
        current_user: Authenticated user (injected).
        db: Database session (injected).

    Returns:
        AdditionalQuestionsResponse: Additional questions of requested type.

    Raises:
        HTTPException: 404 if job not found, 400 if invalid question type.
    """
    try:
        # Get job details
        job = await db.get(ScrapedJob, job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found",
            )

        # Generate additional questions
        additional_content = await interview_coach_service.generate_additional_questions(
            user=current_user,
            job=job,
            question_type=request.question_type,
            count=request.count,
            db=db,
        )

        return AdditionalQuestionsResponse(
            question_type=request.question_type,
            questions=additional_content[f"additional_{request.question_type}_questions"],
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to generate additional questions for job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate additional questions",
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


# ================================================================
# Benchmark Scoring & Competitive Analysis
# ================================================================

@router.post(
    "/{job_id}/calculate-benchmark",
    response_model=BenchmarkScoreResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Calculate GDPR-compliant benchmark score for a job",
    responses={
        422: {"model": InsufficientPeersResponse, "description": "Not enough peers for reliable scoring"},
        400: {"description": "User not opted into benchmarking"},
    }
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
        # Get job details
        job = await db.get(ScrapedJob, job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found",
            )

        # Calculate benchmark score using service
        benchmark_score = await benchmark_service.calculate_benchmark_score(
            user=current_user,
            job=job,
            db=db,
        )

        # Extract required skills for response
        job_requirements = benchmark_service._extract_job_requirements(job)
        user_profile = await benchmark_service._get_user_profile(current_user, db)
        user_skills = benchmark_service._extract_user_skills(user_profile) if user_profile else []

        # Find matched skills
        matched_skills = []
        if user_skills and job_requirements["required_skills"]:
            user_skills_lower = [skill.lower() for skill in user_skills]
            matched_skills = [
                skill for skill in job_requirements["required_skills"]
                if skill.lower() in user_skills_lower
            ]

        # Calculate match score for response
        match_score = benchmark_service._calculate_match_score(
            user_profile, job_requirements, current_user.seniority_level
        ) if user_profile else 0

        # Convert skill gaps to response format
        skill_gaps = []
        if benchmark_score.benchmark_data and benchmark_score.benchmark_data.get("skill_gaps"):
            for gap in benchmark_score.benchmark_data["skill_gaps"]:
                skill_gaps.append({
                    "skill": gap["skill"],
                    "priority": gap["priority"],
                    "peer_frequency": gap["peer_frequency"],
                    "recommendation": gap["recommendation"],
                })

        # Create peer group metadata
        peer_group_metadata = {
            "size": benchmark_score.benchmark_data.get("peer_group_size", 0),
            "seniority_level": current_user.seniority_level,
            "niche_filters": [],  # Could extract from benchmark_data if needed
            "benchmark_opt_in_required": True,
            "min_peers_required": benchmark_service.MINIMUM_PEER_COUNT,
        }

        return BenchmarkScoreResponse(
            id=str(benchmark_score.id),
            user_id=str(current_user.id),
            job_id=str(job.id),
            job_title=job.job_title,
            company_name=job.company_name,
            score=benchmark_score.score,
            match_score=match_score,
            peer_group=peer_group_metadata,
            skill_gaps=skill_gaps,
            matched_skills=matched_skills,
            total_skills_analyzed=len(user_skills),
            calculated_at=benchmark_score.calculated_at,
            privacy_compliant=True,
        )

    except InsufficientPeersError as e:
        # Extract peer count from error message
        import re
        match = re.search(r'(\d+) users found', str(e))
        peers_found = int(match.group(1)) if match else 0

        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "insufficient_peers",
                "message": str(e),
                "peers_found": peers_found,
                "peers_required": benchmark_service.MINIMUM_PEER_COUNT,
                "suggestions": [
                    "Wait for more users to join the platform",
                    "Try again later when more users have opted into benchmarking",
                    f"Consider expanding to a broader seniority level if you're {current_user.seniority_level}",
                ]
            }
        )

    except ValueError as e:
        if "not opted into benchmarking" in str(e):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You must opt into benchmarking to calculate competitive scores. Update your preferences in account settings.",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )

    except Exception as e:
        logger.error(f"Failed to calculate benchmark for job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to calculate benchmark score. Please try again later.",
        )
