"""
Job Pydantic Schemas — Request/Response validation.
"""

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class JobResponse(BaseModel):
    """Schema for scraped job data in API responses.

    Attributes:
        id: Job UUID.
        external_url: Original posting URL.
        company_name: Hiring company.
        job_title: Role title.
        description: Full JD text.
        location: Job location.
        source_platform: Discovery source.
        scraped_at: Discovery timestamp.
    """

    id: uuid.UUID
    external_url: Optional[str]
    company_name: str
    job_title: str
    description: Optional[str]
    location: Optional[str]
    source_platform: Optional[str]
    scraped_at: datetime

    model_config = {"from_attributes": True}


class UserJobResponse(BaseModel):
    """Schema for user-job relationship in API responses.

    Includes match score, status, and AI-generated content.
    """

    id: uuid.UUID
    user_id: uuid.UUID
    job_id: uuid.UUID
    match_score: Optional[int]
    status: str
    optimized_cv: Optional[dict[str, Any]]
    cover_letter: Optional[str]
    interview_prep: Optional[dict[str, Any]]
    created_at: datetime
    updated_at: datetime
    job: Optional[JobResponse] = None

    model_config = {"from_attributes": True}


class UserJobStatusUpdate(BaseModel):
    """Schema for updating a user-job status.

    Attributes:
        status: New status (new, applied, saved, hidden, duplicate).
    """

    status: str = Field(..., pattern="^(new|applied|saved|hidden|duplicate)$")
