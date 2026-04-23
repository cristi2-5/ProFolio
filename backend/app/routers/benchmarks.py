"""
Benchmarks Router — read-side endpoints for competitive benchmarking.

Exposes the read side of the competitive-benchmarking feature (the write
side — POST /jobs/{job_id}/calculate-benchmark — lives in the jobs
router where it fits the existing URL space). Also hosts the cross-JD
recommendations endpoint (US 5.3).
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.benchmark import BenchmarkScore
from app.models.job import ScrapedJob
from app.models.user import User
from app.schemas.benchmark import (
    BenchmarkListResponse,
    BenchmarkScoreResponse,
    BenchmarkSummary,
    PeerGroupMetadata,
    RecommendationsResponse,
    RecommendedKeyword,
    RecommendedSkill,
    SkillGap,
)
from app.services.benchmark_service import MINIMUM_PEER_COUNT
from app.services.recommendations_service import RecommendationsService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/benchmarks", tags=["Benchmarks"])
recommendations_service = RecommendationsService()


# ----------------------------------------------------------------------
# List — used by the Benchmarks dashboard
# ----------------------------------------------------------------------


@router.get(
    "/",
    response_model=BenchmarkListResponse,
    summary="List all benchmark scores for the current user",
)
async def list_user_benchmarks(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> BenchmarkListResponse:
    """Return the user's benchmark rows in calculation-order (newest first)."""
    stmt = (
        select(BenchmarkScore)
        .options(selectinload(BenchmarkScore.job))
        .where(BenchmarkScore.user_id == current_user.id)
        .order_by(BenchmarkScore.calculated_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()

    summaries: list[BenchmarkSummary] = []
    for row in rows:
        job = row.job
        if not job:
            continue
        summaries.append(
            BenchmarkSummary(
                id=str(row.id),
                job_id=str(row.job_id),
                job_title=job.job_title,
                company_name=job.company_name,
                score=row.score,
                peer_group_size=row.peer_group_size or 0,
                skill_gaps_count=len(row.skill_gap_items()),
                calculated_at=row.calculated_at,
            )
        )

    return BenchmarkListResponse(
        benchmarks=summaries,
        total_count=len(summaries),
        opt_in_status=current_user.benchmark_opt_in,
    )


# ----------------------------------------------------------------------
# Recommendations (US 5.3) — must come BEFORE dynamic {benchmark_id} route
# ----------------------------------------------------------------------


@router.get(
    "/recommendations",
    response_model=RecommendationsResponse,
    summary="Aggregated skill recommendations across the user's saved JDs",
)
async def get_recommendations(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RecommendationsResponse:
    """Top 3 missing skills + ATS keywords derived from every saved JD.

    Falls back gracefully when the peer pool is too small: still returns
    JD-demand-weighted recommendations but flags ``insufficient_peers`` so
    the UI can soften language ("based on your saved jobs" vs "vs peers").
    """
    try:
        result = await recommendations_service.generate_recommendations(
            user=current_user, db=db
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return RecommendationsResponse(
        top_missing_skills=[RecommendedSkill(**item) for item in result.top_missing_skills],
        recommended_keywords=[RecommendedKeyword(**item) for item in result.recommended_keywords],
        jobs_analyzed=result.jobs_analyzed,
        peer_group_size=result.peer_group_size,
        insufficient_peers=result.insufficient_peers,
    )


# ----------------------------------------------------------------------
# By-job and by-id fetchers
# ----------------------------------------------------------------------


@router.get(
    "/job/{job_id}",
    response_model=BenchmarkScoreResponse,
    summary="Get the stored benchmark score for a specific job",
)
async def get_benchmark_for_job(
    job_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BenchmarkScoreResponse:
    job = await db.get(ScrapedJob, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    stmt = select(BenchmarkScore).where(
        BenchmarkScore.user_id == current_user.id,
        BenchmarkScore.job_id == job_id,
    )
    result = await db.execute(stmt)
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "No benchmark score found for this job. "
                "Calculate one first via POST /api/jobs/{job_id}/calculate-benchmark"
            ),
        )
    return _row_to_response(row, job=job, current_user=current_user)


@router.get(
    "/{benchmark_id}",
    response_model=BenchmarkScoreResponse,
    summary="Get a benchmark row by id",
)
async def get_benchmark_details(
    benchmark_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BenchmarkScoreResponse:
    stmt = select(BenchmarkScore).where(
        BenchmarkScore.id == benchmark_id,
        BenchmarkScore.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Benchmark score not found or you don't have permission to view it",
        )
    job = await db.get(ScrapedJob, row.job_id) if row.job_id else None
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Associated job no longer exists",
        )
    return _row_to_response(row, job=job, current_user=current_user)


def _row_to_response(
    row: BenchmarkScore, *, job: ScrapedJob, current_user: User
) -> BenchmarkScoreResponse:
    skill_gap_raw = row.skill_gap_items()
    keyword_payload = row.keyword_payload()

    skill_gaps = [
        SkillGap(
            skill=item.get("skill", ""),
            priority=item.get("priority", "medium"),
            peer_frequency=float(item.get("peer_frequency") or 0.0),
            recommendation=item.get("recommendation", ""),
        )
        for item in skill_gap_raw
    ]

    return BenchmarkScoreResponse(
        id=str(row.id),
        user_id=str(current_user.id),
        job_id=str(job.id),
        job_title=job.job_title,
        company_name=job.company_name,
        score=row.score,
        user_match_score=float(keyword_payload.get("user_match_score") or 0.0),
        peer_mean_match_score=float(keyword_payload.get("peer_mean_match_score") or 0.0),
        peer_group=PeerGroupMetadata(
            size=row.peer_group_size or 0,
            seniority_level=row.seniority_level,
            niche=row.niche,
            min_peers_required=MINIMUM_PEER_COUNT,
            benchmark_opt_in_required=True,
        ),
        matched_skills=list(keyword_payload.get("matched") or []),
        skill_gaps=skill_gaps,
        recommended_keywords=list(keyword_payload.get("items") or []),
        calculated_at=row.calculated_at,
        privacy_compliant=True,
    )
