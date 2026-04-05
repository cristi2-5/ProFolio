"""
Interview Coach Schemas — Pydantic models for interview preparation.

Request/response models for interview coaching endpoints including
material generation, retrieval, and updates.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class InterviewPrepGenerateRequest(BaseModel):
    """Request model for generating interview preparation materials."""

    include_user_background: bool = Field(
        default=True,
        description="Whether to include user's CV background in preparation"
    )


class TechnicalQuestion(BaseModel):
    """Single technical interview question with guidance."""

    question: str = Field(description="The technical question")
    difficulty: str = Field(description="Question difficulty level")
    topics: List[str] = Field(description="Related technical topics")
    guidance: str = Field(description="How to approach this question")
    sample_answer: Optional[str] = Field(None, description="Example answer structure")


class BehavioralQuestion(BaseModel):
    """Single behavioral interview question with STAR method guidance."""

    question: str = Field(description="The behavioral question")
    scenario: str = Field(description="What the interviewer is looking for")
    star_guidance: str = Field(description="STAR method guidance for this question")
    company_context: Optional[str] = Field(None, description="Company-specific context")


class CompanyInsight(BaseModel):
    """Company research and insight."""

    topic: str = Field(description="Research topic")
    information: str = Field(description="Detailed information")
    talking_points: List[str] = Field(description="Key points to mention in interview")
    questions_to_ask: List[str] = Field(description="Questions to ask the interviewer")


class TechnologyConcept(BaseModel):
    """Technology concept explanation for cheat sheet."""

    concept: str = Field(description="Technology or concept name")
    definition: str = Field(description="Clear, concise definition")
    key_points: List[str] = Field(description="Important points to remember")
    practical_example: Optional[str] = Field(None, description="Real-world usage example")


class PreparationStrategy(BaseModel):
    """Personalized interview preparation strategy."""

    timeline: str = Field(description="Recommended preparation timeline")
    focus_areas: List[str] = Field(description="Areas to focus preparation on")
    practice_recommendations: List[str] = Field(description="Specific practice activities")
    confidence_boosters: List[str] = Field(description="Tips to boost confidence")
    day_of_tips: List[str] = Field(description="Tips for the interview day")


class InterviewPrepResponse(BaseModel):
    """Complete interview preparation materials response."""

    technical_questions: List[TechnicalQuestion] = Field(
        description="Role-specific technical questions"
    )
    behavioral_questions: List[BehavioralQuestion] = Field(
        description="Company-specific behavioral questions"
    )
    company_research: List[CompanyInsight] = Field(
        description="Company research and insights"
    )
    technology_cheat_sheet: List[TechnologyConcept] = Field(
        description="Technology concepts cheat sheet"
    )
    preparation_strategy: PreparationStrategy = Field(
        description="Personalized preparation strategy"
    )
    generated_at: str = Field(description="When materials were generated")
    job_title: str = Field(description="Target job title")
    company_name: str = Field(description="Target company name")


class InterviewPrepUpdateRequest(BaseModel):
    """Request model for updating interview preparation materials."""

    technical_questions: Optional[List[TechnicalQuestion]] = Field(
        None, description="Updated technical questions"
    )
    behavioral_questions: Optional[List[BehavioralQuestion]] = Field(
        None, description="Updated behavioral questions"
    )
    company_research: Optional[List[CompanyInsight]] = Field(
        None, description="Updated company research"
    )
    technology_cheat_sheet: Optional[List[TechnologyConcept]] = Field(
        None, description="Updated technology cheat sheet"
    )
    preparation_strategy: Optional[PreparationStrategy] = Field(
        None, description="Updated preparation strategy"
    )
    user_notes: Optional[str] = Field(
        None, description="User's personal notes and additions"
    )


class AdditionalQuestionsRequest(BaseModel):
    """Request model for generating additional questions."""

    question_type: str = Field(
        description="Type of questions to generate",
        regex="^(technical|behavioral|company)$"
    )
    count: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of additional questions to generate"
    )


class AdditionalQuestionsResponse(BaseModel):
    """Response model for additional questions."""

    question_type: str = Field(description="Type of questions generated")
    questions: List[Dict[str, Any]] = Field(description="Generated questions")
    generated_at: str = Field(description="When questions were generated")


class InterviewPrepSummary(BaseModel):
    """Summary model for user's interview preparation materials."""

    user_job_id: str = Field(description="UserJob ID")
    job_id: str = Field(description="Job ID")
    job_title: str = Field(description="Job title")
    company_name: str = Field(description="Company name")
    match_score: Optional[int] = Field(None, description="Job match score")
    status: str = Field(description="Job application status")
    updated_at: str = Field(description="Last update timestamp")
    has_technical_questions: bool = Field(description="Has technical questions")
    has_behavioral_questions: bool = Field(description="Has behavioral questions")
    has_company_research: bool = Field(description="Has company research")
    has_cheat_sheet: bool = Field(description="Has technology cheat sheet")
    has_preparation_strategy: bool = Field(description="Has preparation strategy")


class InterviewPrepListResponse(BaseModel):
    """Response model for listing user's interview preparations."""

    preparations: List[InterviewPrepSummary] = Field(
        description="List of interview preparation summaries"
    )
    total_count: int = Field(description="Total number of preparations")


class InterviewPrepErrorResponse(BaseModel):
    """Error response model for interview prep operations."""

    error: str = Field(description="Error type")
    message: str = Field(description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")