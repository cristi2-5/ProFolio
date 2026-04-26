"""
Interview Coach Schemas — Pydantic models for the interview-prep
endpoints (technical + behavioral questions with guidance + tech
cheat sheet).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# ----------------------------------------------------------------------
# Atoms
# ----------------------------------------------------------------------


class TechnicalQuestion(BaseModel):
    """A single technical interview question with ideal-answer guidance."""

    question: str
    difficulty: str = Field(description="easy | medium | hard")
    topics: List[str] = Field(default_factory=list)
    guidance: str = Field(description="Short guide on what an ideal answer covers")
    sample_answer: Optional[str] = Field(
        default=None, description="Example of a strong answer (2-4 sentences)"
    )


class BehavioralQuestion(BaseModel):
    """A behavioral question tied to a company-culture cue from the JD."""

    question: str
    scenario: str = Field(description="Which competency this question probes")
    star_guidance: str = Field(description="How to structure the STAR answer")
    company_context: Optional[str] = Field(
        default=None,
        description="Which culture signal from the JD justifies this question",
    )


class TechnologyConcept(BaseModel):
    """One cheat-sheet entry: a technology with a concise definition."""

    concept: str
    definition: str = Field(description="One-paragraph definition (~2-4 sentences)")
    key_points: List[str] = Field(default_factory=list)
    practical_example: Optional[str] = None


class ExtractedTechnology(BaseModel):
    """Raw output of the deterministic tech extractor."""

    name: str
    category: str
    mentions: int


# ----------------------------------------------------------------------
# Responses
# ----------------------------------------------------------------------


class InterviewPrepResponse(BaseModel):
    """Full interview-prep bundle returned by the coach endpoint."""

    technical_questions: List[TechnicalQuestion] = Field(default_factory=list)
    behavioral_questions: List[BehavioralQuestion] = Field(default_factory=list)
    technology_cheat_sheet: List[TechnologyConcept] = Field(default_factory=list)
    extracted_technologies: List[ExtractedTechnology] = Field(default_factory=list)
    generated_at: str
    job_title: str
    company_name: str
    jd_truncated: bool = Field(
        default=False,
        description="Whether the JD was truncated to fit the prompt token budget",
    )
    jd_truncation_chars_dropped: int = Field(
        default=0,
        ge=0,
        description="Number of characters dropped from the JD during truncation",
    )


class InterviewPrepSummary(BaseModel):
    """Per-job summary used in list views."""

    user_job_id: str
    job_id: str
    job_title: str
    company_name: str
    match_score: Optional[int] = None
    status: str
    updated_at: str
    has_technical_questions: bool
    has_behavioral_questions: bool
    has_cheat_sheet: bool


class InterviewPrepListResponse(BaseModel):
    """Paginated list of interview preps for a user."""

    preparations: List[InterviewPrepSummary]
    total_count: int


# ----------------------------------------------------------------------
# Requests
# ----------------------------------------------------------------------


class InterviewPrepGenerateRequest(BaseModel):
    """Request body for the generate-interview-prep endpoint."""

    include_user_background: bool = Field(
        default=True,
        description="Include parsed CV data in the prompts for personalization",
    )
    technical_count: int = Field(default=3, ge=1, le=10)
    behavioral_count: int = Field(default=2, ge=1, le=10)


class InterviewPrepUpdateRequest(BaseModel):
    """Request body for partial updates (user customizations)."""

    technical_questions: Optional[List[TechnicalQuestion]] = None
    behavioral_questions: Optional[List[BehavioralQuestion]] = None
    technology_cheat_sheet: Optional[List[TechnologyConcept]] = None
    user_notes: Optional[str] = None


# ----------------------------------------------------------------------
# Errors
# ----------------------------------------------------------------------


class InterviewPrepErrorResponse(BaseModel):
    """Structured error payload for interview prep endpoints."""

    error: str
    message: str
    details: Optional[Dict[str, Any]] = None
