"""
Resumes Router — Upload, Parse, and CRUD endpoints.

Handles CV file upload (PDF/DOCX) and triggers the CV Profiler agent
for automatic parsing. Also supports manual corrections to parsed data.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

router = APIRouter(prefix="/api/resumes", tags=["Resumes"])


@router.post(
    "/upload",
    status_code=status.HTTP_201_CREATED,
    summary="Upload and parse a CV file",
)
async def upload_resume(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Upload a CV file and trigger automatic parsing.

    Accepts .pdf and .docx files. The CV Profiler agent extracts
    structured data (skills, experience, education, technologies).

    Args:
        db: Async database session (injected).

    Returns:
        dict: Parsed resume data and metadata.

    Raises:
        HTTPException 400: If file format is unsupported.
    """
    # TODO: Implement file upload + CV Profiler in Phase 2
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Resume upload — implementation in Phase 2.",
    )


@router.get(
    "/",
    summary="List user's resumes",
)
async def list_resumes(
    db: AsyncSession = Depends(get_db),
) -> list:
    """List all resumes for the authenticated user.

    Args:
        db: Async database session (injected).

    Returns:
        list: List of parsed resume summaries.
    """
    # TODO: Implement in Phase 2
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Resume listing — implementation in Phase 2.",
    )
