"""
Feedback Schemas — request/response types for feedback submission
and aggregate stats.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.models.feedback import ContentType


class FeedbackCreateRequest(BaseModel):
    """Body for POST /api/feedback."""

    content_type: ContentType
    content_id: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Optional reference to the specific artefact (UserJob id, etc.)",
    )
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Optional free-text feedback (max 2000 chars)",
    )


class FeedbackResponse(BaseModel):
    """Single feedback record returned to the submitter."""

    id: str
    user_id: str
    content_type: ContentType
    content_id: Optional[str]
    rating: int
    comment: Optional[str]
    created_at: datetime


class FeedbackStatsEntry(BaseModel):
    """Aggregate stats bucketed by content type."""

    content_type: ContentType
    count: int
    average_rating: float = Field(ge=0.0, le=5.0)
    low_rating_count: int = Field(description="Ratings of 1 or 2")


class FeedbackStatsResponse(BaseModel):
    """Aggregate view across all content types."""

    entries: List[FeedbackStatsEntry]
    total_count: int
