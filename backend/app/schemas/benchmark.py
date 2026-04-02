"""
Benchmark Pydantic Schemas — Request/Response validation.
"""

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class BenchmarkResponse(BaseModel):
    """Schema for benchmark score data in API responses.

    Attributes:
        id: Benchmark UUID.
        user_id: Scored user's UUID.
        job_id: Correlated job UUID.
        score: Competitiveness score (0-100).
        peer_group_size: Number of compared peers.
        seniority_level: Level snapshot.
        niche: Niche snapshot.
        missing_skills: Top 3 skill gaps with justifications.
        recommended_keywords: ATS keyword suggestions.
        calculated_at: Score computation timestamp.
    """

    id: uuid.UUID
    user_id: uuid.UUID
    job_id: Optional[uuid.UUID]
    score: int
    peer_group_size: Optional[int]
    seniority_level: Optional[str]
    niche: Optional[str]
    missing_skills: Optional[dict[str, Any]]
    recommended_keywords: Optional[dict[str, Any]]
    calculated_at: datetime

    model_config = {"from_attributes": True}
