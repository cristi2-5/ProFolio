"""
Benchmark Pydantic Schemas — request/response shapes for competitive
scoring, GDPR opt-in, and cross-JD recommendations.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# ----------------------------------------------------------------------
# Scoring (US 5.1 + 5.2)
# ----------------------------------------------------------------------


class SkillGap(BaseModel):
    skill: str
    priority: str = Field(description="high | medium | low")
    peer_frequency: float = Field(
        ge=0.0,
        le=1.0,
        description="Fraction of peers at this level/niche who have the skill",
    )
    recommendation: str


class PeerGroupMetadata(BaseModel):
    size: int = Field(description="Number of peers used in the comparison")
    seniority_level: Optional[str] = None
    niche: Optional[str] = None
    min_peers_required: int = 30
    benchmark_opt_in_required: bool = True


class BenchmarkScoreResponse(BaseModel):
    """Payload returned by the calculate/fetch endpoints."""

    id: Optional[str] = Field(default=None, description="Benchmark row id")
    user_id: str
    job_id: str
    job_title: str
    company_name: str

    score: int = Field(
        ge=0,
        le=100,
        description="Peer-weighted composite score (0-100), centred on 50",
    )
    user_match_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Raw share of required skills the candidate already has",
    )
    peer_mean_match_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Peer group's mean share of required skills",
    )

    peer_group: PeerGroupMetadata
    matched_skills: List[str] = Field(default_factory=list)
    skill_gaps: List[SkillGap] = Field(
        default_factory=list,
        description="Top 3 missing skills ordered by peer-group frequency",
    )
    recommended_keywords: List[str] = Field(
        default_factory=list,
        description="ATS keywords to surface on the CV for this job",
    )

    calculated_at: datetime
    privacy_compliant: bool = True


class InsufficientPeersResponse(BaseModel):
    """Returned as HTTP 422 when the peer pool is below the threshold."""

    error: str = Field(default="insufficient_peers")
    message: str
    peers_found: int
    peers_required: int = 30
    suggestions: List[str] = Field(default_factory=list)


class BenchmarkCalculateRequest(BaseModel):
    """Request body for POST /jobs/{job_id}/calculate-benchmark."""

    # Currently empty — the user and job are taken from path + auth.
    # Kept as a schema so the endpoint has a stable request-body contract.
    pass


# ----------------------------------------------------------------------
# GDPR opt-in
# ----------------------------------------------------------------------


_PRIVACY_NOTICE = (
    "Your data is used only in anonymized, aggregated benchmarking "
    "calculations. No identifying information leaves your profile. You can "
    "opt out at any time without affecting access to the rest of the platform."
)


class BenchmarkOptInRequest(BaseModel):
    benchmark_opt_in: bool


class BenchmarkOptInResponse(BaseModel):
    user_id: str
    benchmark_opt_in: bool
    updated_at: datetime
    privacy_notice: str = Field(default=_PRIVACY_NOTICE)


# ----------------------------------------------------------------------
# Listing (kept for the existing dashboard)
# ----------------------------------------------------------------------


class BenchmarkSummary(BaseModel):
    id: str
    job_id: str
    job_title: str
    company_name: str
    score: int
    peer_group_size: int
    skill_gaps_count: int
    calculated_at: datetime


class BenchmarkListResponse(BaseModel):
    benchmarks: List[BenchmarkSummary]
    total_count: int
    opt_in_status: bool


# ----------------------------------------------------------------------
# Recommendations (US 5.3)
# ----------------------------------------------------------------------


class RecommendedSkill(BaseModel):
    skill: str
    jd_count: int = Field(description="Number of saved JDs requiring this skill")
    peer_frequency: float = Field(
        ge=0.0,
        le=1.0,
        description="Fraction of peers at same level/niche who list the skill",
    )
    priority: str = Field(description="high | medium | low")
    justification: str


class RecommendedKeyword(BaseModel):
    keyword: str
    jd_count: int
    in_cv: bool


class RecommendationsResponse(BaseModel):
    top_missing_skills: List[RecommendedSkill]
    recommended_keywords: List[RecommendedKeyword]
    jobs_analyzed: int
    peer_group_size: int
    insufficient_peers: bool = Field(
        description="True when fewer than 30 peers were available; still returns "
        "JD-based recommendations but omits peer-frequency signal"
    )


# ----------------------------------------------------------------------
# Errors
# ----------------------------------------------------------------------


class BenchmarkErrorResponse(BaseModel):
    error: str
    message: str
    details: Optional[Dict[str, Any]] = None


# Legacy compatibility — kept so existing callers don't break.
class BenchmarkResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    job_id: Optional[uuid.UUID]
    score: int
    peer_group_size: Optional[int]
    seniority_level: Optional[str]
    niche: Optional[str]
    missing_skills: Optional[Dict[str, Any]]
    recommended_keywords: Optional[Dict[str, Any]]
    calculated_at: datetime

    model_config = {"from_attributes": True}
