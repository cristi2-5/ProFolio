"""
Job Pydantic Schemas — Request/Response validation.
"""

import uuid
from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field, model_validator


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
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    job_type: Optional[str] = None

    model_config = {"from_attributes": True}


class UserJobResponse(BaseModel):
    """Schema for user-job relationship in API responses.

    Includes match score, status, applied_at timestamp, and AI-generated content.
    The nested job details are flattened into the top-level for frontend convenience.
    """

    id: uuid.UUID
    user_id: uuid.UUID
    job_id: uuid.UUID
    match_score: Optional[int]
    status: str
    optimized_cv: Optional[dict[str, Any]]
    cover_letter: Optional[str]
    interview_prep: Optional[dict[str, Any]]
    applied_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    # Flattened job fields
    job_title: str = ""
    company_name: str = ""
    location: Optional[str] = None
    external_url: Optional[str] = None
    description: Optional[str] = None
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    job_type: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def flatten_job_details(cls, data: Any) -> Any:
        """Flatten nested job details into the top-level UserJobResponse object."""
        # Handle SQLAlchemy model instance (look for 'job' relationship)
        if hasattr(data, "job") and data.job:
            # Add fields from ScrapedJob to the data source
            setattr(data, "job_title", getattr(data.job, "job_title", ""))
            setattr(data, "company_name", getattr(data.job, "company_name", ""))
            setattr(data, "location", getattr(data.job, "location", None))
            setattr(data, "external_url", getattr(data.job, "external_url", None))
            setattr(data, "description", getattr(data.job, "description", None))
            setattr(data, "salary_min", getattr(data.job, "salary_min", None))
            setattr(data, "salary_max", getattr(data.job, "salary_max", None))
            setattr(data, "job_type", getattr(data.job, "job_type", None))
        return data

    model_config = {"from_attributes": True}


class UserJobListResponse(BaseModel):
    """Paginated list of user-job relationships.

    Attributes:
        jobs: List of matched jobs for the current page.
        total_count: Total number of jobs matching the query (for pagination).
    """

    jobs: List[UserJobResponse]
    total_count: int


class UserJobStatusUpdate(BaseModel):
    """Schema for updating a user-job status.

    Attributes:
        status: New status (new, applied, saved, hidden, duplicate).
    """

    status: str = Field(..., pattern="^(new|applied|saved|hidden|duplicate)$")
