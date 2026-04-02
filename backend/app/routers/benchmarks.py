"""
Benchmarks Router — Competitive scoring endpoints.

Provides endpoints for computing and viewing benchmark scores
based on GDPR-compliant aggregated peer data.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

router = APIRouter(prefix="/api/benchmarks", tags=["Benchmarks"])


@router.get(
    "/",
    summary="Get benchmark scores for the current user",
)
async def get_benchmarks(
    db: AsyncSession = Depends(get_db),
) -> list:
    """Retrieve all benchmark scores for the authenticated user.

    Only returns scores where the peer group had >= 30 members.
    Includes missing skills and recommended keywords per job.

    Args:
        db: Async database session (injected).

    Returns:
        list: List of benchmark score entries.
    """
    # TODO: Implement in Phase 3
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Benchmarks — implementation in Phase 3.",
    )
