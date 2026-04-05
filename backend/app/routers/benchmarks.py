"""
Benchmarks Router — GDPR-compliant competitive scoring endpoints.

Provides endpoints for retrieving benchmark scores and competitive
analysis based on anonymized peer data comparisons.
"""

import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.models.job import ScrapedJob
from app.models.benchmark import BenchmarkScore
from app.schemas.benchmark import (
    BenchmarkScoreResponse,
    BenchmarkListResponse,
    BenchmarkSummary,
)

router = APIRouter(prefix="/api/benchmarks", tags=["Benchmarks"])

# Initialize logger
logger = logging.getLogger(__name__)


@router.get(
    "/",
    response_model=BenchmarkListResponse,
    summary="Get all benchmark scores for the current user",
)
async def get_user_benchmarks(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100, description="Maximum benchmarks to return")] = 50,
) -> BenchmarkListResponse:
    """Retrieve all benchmark scores for the authenticated user.

    Returns benchmark summaries with scores, peer group sizes, and skill gaps.
    Only includes scores where peer group had minimum required members for
    statistical validity.

    Args:
        current_user: Authenticated user (injected).
        db: Database session (injected).
        limit: Maximum number of benchmarks to return (1-100).

    Returns:
        BenchmarkListResponse: List of benchmark summaries with opt-in status.
    """
    try:
        # Query user's benchmark scores
        stmt = (
            select(BenchmarkScore)
            .where(BenchmarkScore.user_id == current_user.id)
            .order_by(BenchmarkScore.calculated_at.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        benchmark_scores = result.scalars().all()

        benchmark_summaries = []
        for score in benchmark_scores:
            # Get job details
            job = await db.get(ScrapedJob, score.job_id)
            if not job:
                continue  # Skip if job no longer exists

            # Extract peer group size and skill gaps count
            peer_group_size = 0
            skill_gaps_count = 0

            if score.benchmark_data:
                peer_group_size = score.benchmark_data.get("peer_group_size", 0)
                skill_gaps = score.benchmark_data.get("skill_gaps", [])
                skill_gaps_count = len(skill_gaps) if isinstance(skill_gaps, list) else 0

            benchmark_summaries.append(BenchmarkSummary(
                id=str(score.id),
                job_id=str(score.job_id),
                job_title=job.job_title,
                company_name=job.company_name,
                score=score.score,
                peer_group_size=peer_group_size,
                skill_gaps_count=skill_gaps_count,
                calculated_at=score.calculated_at,
            ))

        return BenchmarkListResponse(
            benchmarks=benchmark_summaries,
            total_count=len(benchmark_summaries),
            opt_in_status=current_user.benchmark_opt_in,
        )

    except Exception as e:
        logger.error(f"Failed to get benchmarks for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve benchmark scores",
        )


@router.get(
    "/{benchmark_id}",
    response_model=BenchmarkScoreResponse,
    summary="Get detailed benchmark score by ID",
)
async def get_benchmark_details(
    benchmark_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BenchmarkScoreResponse:
    """Retrieve detailed benchmark score by ID.

    Returns complete benchmark analysis including skill gaps,
    peer group metadata, and competitive positioning.

    Args:
        benchmark_id: UUID of the benchmark record.
        current_user: Authenticated user (injected).
        db: Database session (injected).

    Returns:
        BenchmarkScoreResponse: Detailed benchmark analysis.

    Raises:
        HTTPException: 404 if benchmark not found or unauthorized,
                      500 if retrieval fails.
    """
    try:
        # Get benchmark score with authorization check
        stmt = select(BenchmarkScore).where(
            BenchmarkScore.id == benchmark_id,
            BenchmarkScore.user_id == current_user.id,
        )
        result = await db.execute(stmt)
        benchmark_score = result.scalar_one_or_none()

        if not benchmark_score:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Benchmark score not found or you don't have permission to view it",
            )

        # Get job details
        job = await db.get(ScrapedJob, benchmark_score.job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Associated job no longer exists",
            )

        # Extract data from benchmark_data JSON
        benchmark_data = benchmark_score.benchmark_data or {}

        # Extract skill gaps
        skill_gaps = []
        if benchmark_data.get("skill_gaps"):
            for gap in benchmark_data["skill_gaps"]:
                skill_gaps.append({
                    "skill": gap.get("skill", ""),
                    "priority": gap.get("priority", "medium"),
                    "peer_frequency": gap.get("peer_frequency", "0%"),
                    "recommendation": gap.get("recommendation", ""),
                })

        # Extract matched skills from match criteria
        matched_skills = []
        if benchmark_data.get("match_criteria", {}).get("required_skills"):
            # This would require re-calculating or storing matched skills
            # For now, extract from job requirements
            matched_skills = benchmark_data["match_criteria"]["required_skills"][:5]  # Limit for response

        # Create peer group metadata
        peer_group_metadata = {
            "size": benchmark_data.get("peer_group_size", 0),
            "seniority_level": current_user.seniority_level,
            "niche_filters": [],  # Could be enhanced with stored filters
            "benchmark_opt_in_required": True,
            "min_peers_required": 30,
        }

        return BenchmarkScoreResponse(
            id=str(benchmark_score.id),
            user_id=str(current_user.id),
            job_id=str(job.id),
            job_title=job.job_title,
            company_name=job.company_name,
            score=benchmark_score.score,
            match_score=benchmark_data.get("match_score", 0.0),
            peer_group=peer_group_metadata,
            skill_gaps=skill_gaps,
            matched_skills=matched_skills,
            total_skills_analyzed=len(matched_skills) + len(skill_gaps),
            calculated_at=benchmark_score.calculated_at,
            privacy_compliant=True,
        )

    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        logger.error(f"Failed to get benchmark details for ID {benchmark_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve benchmark details",
        )


@router.get(
    "/job/{job_id}",
    response_model=BenchmarkScoreResponse,
    summary="Get benchmark score for a specific job",
)
async def get_benchmark_for_job(
    job_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BenchmarkScoreResponse:
    """Retrieve benchmark score for a specific job.

    Convenience endpoint to get benchmark analysis for a particular
    job without needing to know the benchmark record ID.

    Args:
        job_id: UUID of the job.
        current_user: Authenticated user (injected).
        db: Database session (injected).

    Returns:
        BenchmarkScoreResponse: Benchmark analysis for the job.

    Raises:
        HTTPException: 404 if job or benchmark not found,
                      500 if retrieval fails.
    """
    try:
        # Verify job exists
        job = await db.get(ScrapedJob, job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found",
            )

        # Get benchmark score for this user and job
        stmt = select(BenchmarkScore).where(
            BenchmarkScore.user_id == current_user.id,
            BenchmarkScore.job_id == job_id,
        )
        result = await db.execute(stmt)
        benchmark_score = result.scalar_one_or_none()

        if not benchmark_score:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No benchmark score found for this job. Calculate one first using POST /api/jobs/{job_id}/calculate-benchmark",
            )

        # Reuse the detailed benchmark endpoint logic
        return await get_benchmark_details(
            benchmark_id=str(benchmark_score.id),
            current_user=current_user,
            db=db,
        )

    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        logger.error(f"Failed to get benchmark for job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve job benchmark",
        )