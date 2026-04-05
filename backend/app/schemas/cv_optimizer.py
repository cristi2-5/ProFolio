"""
CV Optimizer Pydantic Schemas — Request/Response validation.

Defines data structures for CV optimization, cover letter generation,
and PDF export API interactions.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class CVOptimizationRequest(BaseModel):
    """Schema for CV optimization requests.

    Attributes:
        job_id: UUID of the job to optimize CV for.
    """

    job_id: uuid.UUID


class CVOptimizationResponse(BaseModel):
    """Schema for CV optimization responses.

    Attributes:
        optimized_cv: The AI-optimized CV content.
        job_title: Job title the CV was optimized for.
        company_name: Company name the CV was optimized for.
        optimization_date: When the optimization was performed.
    """

    optimized_cv: Dict[str, Any]
    job_title: str
    company_name: str
    optimization_date: datetime


class CoverLetterRequest(BaseModel):
    """Schema for cover letter generation requests.

    Attributes:
        job_id: UUID of the job to generate cover letter for.
    """

    job_id: uuid.UUID


class CoverLetterResponse(BaseModel):
    """Schema for cover letter generation responses.

    Attributes:
        cover_letter: Generated cover letter text.
        job_title: Job title the letter was generated for.
        company_name: Company name the letter was generated for.
        generation_date: When the cover letter was generated.
    """

    cover_letter: str
    job_title: str
    company_name: str
    generation_date: datetime


class OptimizationSuggestionsRequest(BaseModel):
    """Schema for CV optimization suggestions requests.

    Attributes:
        job_description: Job description to analyze against current CV.
    """

    job_description: str = Field(..., min_length=50, max_length=5000)


class OptimizationSuggestionsResponse(BaseModel):
    """Schema for CV optimization suggestions responses.

    Attributes:
        keywords_to_add: List of keywords that should be added to CV.
        sections_to_enhance: Specific suggestions for each CV section.
        formatting_tips: General formatting improvements.
        match_score: Current CV-job compatibility score (0-100).
        priority_improvements: Most important changes to make.
    """

    keywords_to_add: list[str]
    sections_to_enhance: Dict[str, str]
    formatting_tips: list[str]
    match_score: int = Field(..., ge=0, le=100)
    priority_improvements: list[str]


class OptimizedMaterialsResponse(BaseModel):
    """Schema for listing user's optimized materials.

    Attributes:
        user_job_id: UUID of the UserJob record.
        job_id: UUID of the associated job.
        job_title: Title of the job position.
        company_name: Name of the company.
        has_optimized_cv: Whether optimized CV exists.
        has_cover_letter: Whether cover letter exists.
        match_score: Job compatibility score.
        status: Application status.
        updated_at: Last update timestamp.
    """

    user_job_id: uuid.UUID
    job_id: uuid.UUID
    job_title: str
    company_name: str
    has_optimized_cv: bool
    has_cover_letter: bool
    match_score: Optional[int]
    status: str
    updated_at: datetime


class PDFExportResponse(BaseModel):
    """Schema for PDF export responses.

    Attributes:
        message: Success message.
        filename: Suggested filename for the PDF.
        file_size: Size of the PDF file in bytes.
        export_date: When the PDF was generated.
    """

    message: str
    filename: str
    file_size: int
    export_date: datetime