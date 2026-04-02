"""
Resume Pydantic Schemas — Request/Response validation.
"""

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class ResumeResponse(BaseModel):
    """Schema for parsed resume data in API responses.

    Attributes:
        id: Resume UUID.
        user_id: Owning user's UUID.
        original_filename: Uploaded filename.
        parsed_data: Structured CV data extracted by CV Profiler.
        is_active: Whether this is the current active resume.
        created_at: Upload timestamp.
        updated_at: Last modification timestamp.
    """

    id: uuid.UUID
    user_id: uuid.UUID
    original_filename: Optional[str]
    parsed_data: dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ResumeUpdate(BaseModel):
    """Schema for manual corrections to parsed resume data.

    Attributes:
        parsed_data: Corrected structured CV data.
        is_active: Whether to set this as the active resume.
    """

    parsed_data: Optional[dict[str, Any]] = None
    is_active: Optional[bool] = None
