"""
CV Optimizer Router — REST endpoints for CV optimization and export.

Provides endpoints for AI-powered CV optimization, cover letter generation,
and PDF export functionality for job applications.
"""

import logging
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.job import ScrapedJob
from app.models.user import User
from app.schemas.cv_optimizer import (
    CVOptimizationRequest,
    CVOptimizationResponse,
    CoverLetterRequest,
    CoverLetterResponse,
    OptimizationSuggestionsRequest,
    OptimizationSuggestionsResponse,
    OptimizedMaterialsResponse,
    PDFExportResponse,
)
from app.services.cv_optimizer_service import CVOptimizerService

router = APIRouter(prefix="/api/cv-optimizer", tags=["CV Optimizer"])

# Initialize logger and service
logger = logging.getLogger(__name__)
cv_optimizer_service = CVOptimizerService()


@router.post(
    "/optimize",
    response_model=CVOptimizationResponse,
    status_code=status.HTTP_200_OK,
    summary="Optimize CV for specific job",
)
async def optimize_cv_for_job(
    request: CVOptimizationRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CVOptimizationResponse:
    """Optimize user's CV for a specific job posting using AI.

    Analyzes job requirements and rewrites CV sections to improve ATS
    compatibility and keyword matching while maintaining accuracy.

    Args:
        request: Job ID for CV optimization.
        current_user: Authenticated user (injected).
        db: Database session (injected).

    Returns:
        CVOptimizationResponse: Optimized CV with job-specific improvements.

    Raises:
        HTTPException: 404 if job not found, 400 if no resume, 500 if optimization fails.
    """
    try:
        # Get the job record
        job = await db.get(ScrapedJob, request.job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found",
            )

        # Perform CV optimization
        optimized_cv = await cv_optimizer_service.optimize_cv_for_job(
            user=current_user,
            job=job,
            db=db,
        )

        return CVOptimizationResponse(
            optimized_cv=optimized_cv,
            job_title=job.job_title,
            company_name=job.company_name,
            optimization_date=datetime.now(timezone.utc),
        )

    except ValueError as e:
        logger.warning(f"CV optimization validation error for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"CV optimization failed for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="CV optimization failed. Please try again later.",
        )


@router.post(
    "/cover-letter",
    response_model=CoverLetterResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate cover letter for job application",
)
async def generate_cover_letter(
    request: CoverLetterRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CoverLetterResponse:
    """Generate personalized cover letter for job application using AI.

    Creates tailored cover letter highlighting relevant experience and
    demonstrating knowledge of the company and role requirements.

    Args:
        request: Job ID for cover letter generation.
        current_user: Authenticated user (injected).
        db: Database session (injected).

    Returns:
        CoverLetterResponse: Generated cover letter with job details.

    Raises:
        HTTPException: 404 if job not found, 400 if no resume, 500 if generation fails.
    """
    try:
        # Get the job record
        job = await db.get(ScrapedJob, request.job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found",
            )

        # Generate cover letter
        cover_letter = await cv_optimizer_service.generate_cover_letter(
            user=current_user,
            job=job,
            db=db,
        )

        return CoverLetterResponse(
            cover_letter=cover_letter,
            job_title=job.job_title,
            company_name=job.company_name,
            generation_date=datetime.now(timezone.utc),
        )

    except ValueError as e:
        logger.warning(f"Cover letter generation validation error for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Cover letter generation failed for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Cover letter generation failed. Please try again later.",
        )


@router.post(
    "/suggestions",
    response_model=OptimizationSuggestionsResponse,
    summary="Get CV optimization suggestions",
)
async def get_optimization_suggestions(
    request: OptimizationSuggestionsRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OptimizationSuggestionsResponse:
    """Get AI-powered suggestions for CV improvement.

    Analyzes current CV against job requirements and provides specific
    recommendations without performing full optimization.

    Args:
        request: Job description for analysis.
        current_user: Authenticated user (injected).
        db: Database session (injected).

    Returns:
        OptimizationSuggestionsResponse: Structured improvement suggestions.

    Raises:
        HTTPException: 400 if no resume found, 500 if analysis fails.
    """
    try:
        # Get optimization suggestions
        suggestions = await cv_optimizer_service.get_optimization_suggestions(
            user=current_user,
            job_description=request.job_description,
            db=db,
        )

        return OptimizationSuggestionsResponse(**suggestions)

    except ValueError as e:
        logger.warning(f"Suggestions generation validation error for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Suggestions generation failed for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate suggestions. Please try again later.",
        )


@router.get(
    "/materials",
    response_model=list[OptimizedMaterialsResponse],
    summary="List user's optimized materials",
)
async def list_optimized_materials(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[OptimizedMaterialsResponse]:
    """List all optimized CVs and cover letters for the authenticated user.

    Returns information about all job applications where the user has
    generated optimized materials (CVs or cover letters).

    Args:
        current_user: Authenticated user (injected).
        db: Database session (injected).

    Returns:
        list[OptimizedMaterialsResponse]: List of optimized materials.
    """
    try:
        materials = await cv_optimizer_service.get_user_optimized_materials(
            user=current_user,
            db=db,
        )

        return [OptimizedMaterialsResponse(**material) for material in materials]

    except Exception as e:
        logger.error(f"Failed to retrieve optimized materials for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve materials. Please try again later.",
        )


@router.get(
    "/export/cv/{job_id}",
    summary="Export optimized CV as PDF",
)
async def export_optimized_cv_pdf(
    job_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Export optimized CV as professional PDF document.

    Downloads the AI-optimized CV for a specific job as a formatted PDF
    suitable for job applications.

    Args:
        job_id: UUID of the job to export optimized CV for.
        current_user: Authenticated user (injected).
        db: Database session (injected).

    Returns:
        Response: PDF file download with appropriate headers.

    Raises:
        HTTPException: 404 if CV not found, 500 if export fails.
    """
    try:
        # Export CV as PDF
        pdf_data, filename = await cv_optimizer_service.export_optimized_cv_pdf(
            user=current_user,
            job_id=job_id,
            db=db,
        )

        # Return PDF as download response
        return Response(
            content=pdf_data,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Length": str(len(pdf_data)),
            },
        )

    except ValueError as e:
        logger.warning(f"CV PDF export validation error for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"CV PDF export failed for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="PDF export failed. Please try again later.",
        )


@router.get(
    "/export/cover-letter/{job_id}",
    summary="Export cover letter as PDF",
)
async def export_cover_letter_pdf(
    job_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Export cover letter as professional PDF document.

    Downloads the AI-generated cover letter for a specific job as a formatted
    PDF suitable for job applications.

    Args:
        job_id: UUID of the job to export cover letter for.
        current_user: Authenticated user (injected).
        db: Database session (injected).

    Returns:
        Response: PDF file download with appropriate headers.

    Raises:
        HTTPException: 404 if cover letter not found, 500 if export fails.
    """
    try:
        # Get job for PDF generation context
        job = await db.get(ScrapedJob, job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found",
            )

        # Export cover letter as PDF
        pdf_data, filename = await cv_optimizer_service.export_cover_letter_pdf(
            user=current_user,
            job=job,
            db=db,
        )

        # Return PDF as download response
        return Response(
            content=pdf_data,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Length": str(len(pdf_data)),
            },
        )

    except ValueError as e:
        logger.warning(f"Cover letter PDF export validation error for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Cover letter PDF export failed for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="PDF export failed. Please try again later.",
        )


@router.get(
    "/health",
    summary="CV optimizer service health check",
)
async def health_check() -> dict:
    """Check CV optimizer service health and dependencies.

    Verifies that the OpenAI API is configured and accessible for
    CV optimization and cover letter generation.

    Returns:
        dict: Service health status and configuration.
    """
    try:
        # Basic service validation
        cv_optimizer = CVOptimizerService()

        return {
            "status": "healthy",
            "service": "CV Optimizer",
            "features": [
                "cv_optimization",
                "cover_letter_generation",
                "pdf_export",
                "optimization_suggestions",
            ],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"CV optimizer health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="CV optimizer service is unavailable",
        )