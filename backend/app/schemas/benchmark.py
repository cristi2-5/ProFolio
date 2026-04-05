"""
Benchmark Pydantic Schemas — GDPR-compliant competitive scoring models.

Request/response models for benchmark calculation, opt-in management,
and score retrieval with comprehensive privacy controls.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class BenchmarkCalculateRequest(BaseModel):
    """Request model for calculating benchmark scores."""

    job_id: str = Field(description="Job ID to calculate benchmark for")


class SkillGap(BaseModel):
    """Individual skill gap with analysis."""

    skill: str = Field(description="Missing skill name")
    priority: str = Field(description="Gap priority (high, medium, low)")
    peer_frequency: str = Field(description="Frequency among peers (e.g., '75%')")
    recommendation: str = Field(description="Learning recommendation")


class PeerGroupMetadata(BaseModel):
    """Metadata about the peer group used for comparison."""

    size: int = Field(description="Number of peers in comparison group")
    seniority_level: str = Field(description="Peer group seniority level")
    niche_filters: List[str] = Field(default=[], description="Technology niche filters applied")
    benchmark_opt_in_required: bool = Field(default=True, description="GDPR opt-in requirement")
    min_peers_required: int = Field(default=30, description="Minimum peers for valid calculation")


class BenchmarkScoreResponse(BaseModel):
    """Complete benchmark score response."""

    id: Optional[str] = Field(None, description="Benchmark record ID")
    user_id: str = Field(description="User ID (for authorization)")
    job_id: str = Field(description="Job ID")
    job_title: str = Field(description="Job title for context")
    company_name: str = Field(description="Company name for context")

    # Core scoring
    score: int = Field(description="Percentile rank (1-100)")
    match_score: float = Field(description="Raw match score (0-100)")

    # Peer group information
    peer_group: PeerGroupMetadata = Field(description="Peer group metadata")

    # Skill analysis
    skill_gaps: List[SkillGap] = Field(description="Top 3 skill gaps with recommendations")
    matched_skills: List[str] = Field(description="Skills that matched job requirements")
    total_skills_analyzed: int = Field(description="Total skills considered")

    # Metadata
    calculated_at: datetime = Field(description="When score was calculated")
    privacy_compliant: bool = Field(default=True, description="GDPR compliance confirmation")


class BenchmarkOptInRequest(BaseModel):
    """Request model for benchmark opt-in management."""

    benchmark_opt_in: bool = Field(description="Whether to opt into benchmarking")


class BenchmarkOptInResponse(BaseModel):
    """Response model for benchmark opt-in status."""

    user_id: str = Field(description="User ID")
    benchmark_opt_in: bool = Field(description="Current opt-in status")
    updated_at: datetime = Field(description="When status was last updated")
    privacy_notice: str = Field(
        default="Your data will only be used in anonymized aggregations for benchmarking. You can opt out at any time.",
        description="Privacy notice about data usage"
    )


class BenchmarkSummary(BaseModel):
    """Summary model for benchmark listing."""

    id: str = Field(description="Benchmark record ID")
    job_id: str = Field(description="Job ID")
    job_title: str = Field(description="Job title")
    company_name: str = Field(description="Company name")
    score: int = Field(description="Percentile rank (1-100)")
    peer_group_size: int = Field(description="Number of peers")
    skill_gaps_count: int = Field(description="Number of skill gaps identified")
    calculated_at: datetime = Field(description="Calculation timestamp")


class BenchmarkListResponse(BaseModel):
    """Response model for listing user benchmarks."""

    benchmarks: List[BenchmarkSummary] = Field(description="List of benchmark summaries")
    total_count: int = Field(description="Total number of benchmarks")
    opt_in_status: bool = Field(description="User's current opt-in status")


class InsufficientPeersResponse(BaseModel):
    """Error response when peer group is too small."""

    error: str = Field(default="insufficient_peers")
    message: str = Field(description="Human-readable error message")
    peers_found: int = Field(description="Number of eligible peers found")
    peers_required: int = Field(description="Minimum peers required")
    suggestions: List[str] = Field(description="Suggestions to get more peers")


class BenchmarkErrorResponse(BaseModel):
    """Generic error response for benchmark operations."""

    error: str = Field(description="Error type")
    message: str = Field(description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")


# Legacy schema for backward compatibility
class BenchmarkResponse(BaseModel):
    """Legacy schema for backward compatibility."""

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
