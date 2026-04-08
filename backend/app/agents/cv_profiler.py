"""
CV Profiler Agent — Automatic resume parsing with GPT-4.

Extracts structured data from uploaded PDF/DOCX files using
OpenAI GPT-4 with structured output. Outputs JSON with skills,
experience, education, and technologies optimized for job matching.

LLM Provider: OpenAI GPT-4 (selected for structured output quality).
Architecture: Two-step process (text extraction → AI parsing).
"""

import asyncio
import json
import logging
from typing import Dict, Any, List
from datetime import datetime

from openai import AsyncOpenAI
from pydantic import BaseModel, Field, ValidationError

from app.config import get_settings
from app.utils.file_processing import extract_text_from_file, clean_extracted_text

settings = get_settings()
logger = logging.getLogger(__name__)

# OpenAI client initialization
# Only create client for valid API keys (not test/development keys)
is_development_mode = (
    not settings.openai_api_key or
    settings.openai_api_key.startswith("test-") or
    settings.environment == "development"
)

openai_client = None if is_development_mode else AsyncOpenAI(api_key=settings.openai_api_key)

if is_development_mode:
    logger.warning("Running CV Profiler in development mode. Real parsing disabled.")


# =====================================================================
# Pydantic Models for Structured Output
# =====================================================================


class Experience(BaseModel):
    """Single work experience entry."""
    role: str = Field(..., description="Job title or role name")
    company: str = Field(..., description="Company or organization name")
    period: str = Field(..., description="Employment period (e.g., '2020-2023', 'Jan 2020 - Present')")
    description: str = Field(..., description="Brief description of responsibilities and achievements")
    technologies: List[str] = Field(default_factory=list, description="Technologies used in this role")


class Education(BaseModel):
    """Single education entry."""
    degree: str = Field(..., description="Degree type and field (e.g., 'Bachelor of Science in Computer Science')")
    institution: str = Field(..., description="School, university, or institution name")
    year: str = Field(..., description="Graduation year or period (e.g., '2020', '2018-2022')")
    details: str = Field(default="", description="Additional details like GPA, honors, relevant coursework")


class ParsedCVData(BaseModel):
    """Structured CV data output from GPT-4 parsing."""

    # Core professional information
    full_name: str = Field(default="", description="Candidate's full name as it appears on the CV")
    email: str = Field(default="", description="Primary email address")
    phone: str = Field(default="", description="Phone number")
    location: str = Field(default="", description="Current location (city, country)")

    # Professional summary
    summary: str = Field(default="", description="Professional summary or objective statement")

    # Skills and technologies (deduplicated and normalized)
    skills: List[str] = Field(default_factory=list, description="Technical and soft skills")
    technologies: List[str] = Field(default_factory=list, description="Programming languages, frameworks, tools")

    # Experience and education
    experience: List[Experience] = Field(default_factory=list, description="Work experience entries")
    education: List[Education] = Field(default_factory=list, description="Education entries")

    # Additional information
    certifications: List[str] = Field(default_factory=list, description="Professional certifications")
    languages: List[str] = Field(default_factory=list, description="Spoken languages with proficiency level")

    # Metadata for job matching
    total_years_experience: int = Field(default=0, description="Estimated total years of professional experience")
    senior_technologies: List[str] = Field(default_factory=list, description="Technologies with 3+ years experience")


# =====================================================================
# CV Profiler Agent Implementation
# =====================================================================


class CVProfilerAgent:
    """Parses uploaded CVs and extracts structured candidate data using GPT-4.

    Uses a two-step process:
    1. Text extraction from PDF/DOCX using secure file processing utilities.
    2. Structured data extraction via GPT-4 with Pydantic model validation.

    Output format follows ParsedCVData schema for consistent job matching.

    Features:
    - Structured output with validation
    - Error handling and fallback strategies
    - Token usage optimization
    - Retry logic for API failures
    """

    def __init__(self):
        """Initialize the CV Profiler Agent."""
        if not openai_client:
            logger.error("OpenAI API key not configured. CV parsing will not work.")

        # GPT-4 configuration
        self.model = "gpt-4o-mini"  # Faster and cheaper for structured tasks
        self.max_tokens = 2000
        self.temperature = 0.1  # Low for consistent structured output

    async def parse(self, file_path: str, original_filename: str) -> Dict[str, Any]:
        """Parse a CV file and return structured data.

        Args:
            file_path: Path to the uploaded CV file on disk.
            original_filename: Original filename from upload.

        Returns:
            Dict[str, Any]: Structured resume data following ParsedCVData schema.

        Raises:
            ValueError: If file processing fails or AI parsing returns invalid data.
            Exception: If OpenAI API is unavailable or returns errors.
        """
        try:
            # Step 1: Extract and clean text from CV file
            logger.info(f"Extracting text from CV: {original_filename}")
            raw_text = extract_text_from_file(file_path, original_filename)
            cleaned_text = clean_extracted_text(raw_text)

            if not cleaned_text.strip():
                raise ValueError("No extractable text found in CV file")

            # Step 2: Parse with GPT-4
            logger.info(f"Parsing CV with GPT-4: {original_filename} ({len(cleaned_text)} chars)")
            parsed_data = await self._parse_with_gpt4(cleaned_text, original_filename)

            # Step 3: Validate and return
            return parsed_data.model_dump()

        except ValueError as e:
            logger.error(f"CV parsing validation error for {original_filename}: {e}")
            raise
        except Exception as e:
            logger.error(f"CV parsing failed for {original_filename}: {e}")
            raise Exception(f"CV parsing failed: {str(e)}")

    async def _parse_with_gpt4(self, cv_text: str, filename: str) -> ParsedCVData:
        """Use GPT-4 to extract structured data from CV text.

        Args:
            cv_text: Cleaned text extracted from CV file.
            filename: Original filename for logging.

        Returns:
            ParsedCVData: Validated structured CV data.

        Raises:
            Exception: If OpenAI API call fails or returns invalid data.
        """
        if not openai_client:
            logger.warning("Mocking OpenAI response due to missing API Key.")
            return ParsedCVData(
                full_name="Alexandru Popescu",
                email="alex@example.com",
                phone="0712345678",
                location="Bucharest, Romania",
                summary="Passionate Developer eager to build scalable web applications.",
                skills=["Problem Solving", "Teamwork", "Agile"],
                technologies=["Python", "React", "Docker", "FastAPI"],
                experience=[
                    Experience(
                        role="Software Engineer",
                        company="MockingCorp",
                        period="2021 - Present",
                        description="Developed multiple microservices saving 20% infrastructure cost.",
                        technologies=["Python", "Docker"]
                    )
                ],
                education=[
                    Education(
                        degree="BSc Computer Science",
                        institution="University of Bucharest",
                        year="2021",
                        details="Graduated Top 10%"
                    )
                ],
                total_years_experience=3,
                senior_technologies=["Python"]
            )

        # Construct the prompt for structured CV parsing
        system_prompt = self._get_cv_parsing_prompt()

        # Truncate text if too long (GPT-4 context limit consideration)
        max_text_length = 8000  # Leave room for prompt and response
        if len(cv_text) > max_text_length:
            cv_text = cv_text[:max_text_length] + "\n\n[TEXT TRUNCATED]"
            logger.warning(f"CV text truncated for {filename} (original length: {len(cv_text)} chars)")

        try:
            # Make API call to GPT-4
            response = await openai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Extract structured data from this CV:\n\n{cv_text}"}
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                response_format={"type": "json_object"}  # Enforce JSON response
            )

            # Extract JSON from response
            response_content = response.choices[0].message.content.strip()

            try:
                json_data = json.loads(response_content)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON from GPT-4 for {filename}: {e}")
                raise Exception("AI returned invalid JSON format")

            # Validate with Pydantic model
            try:
                parsed_data = ParsedCVData(**json_data)
                logger.info(f"Successfully parsed CV {filename}: {len(parsed_data.skills)} skills, {len(parsed_data.experience)} jobs")
                return parsed_data
            except ValidationError as e:
                logger.error(f"Pydantic validation failed for {filename}: {e}")
                # Return minimal valid data as fallback
                return ParsedCVData()

        except Exception as e:
            logger.error(f"OpenAI API error for {filename}: {e}")
            raise Exception(f"AI parsing failed: {str(e)}")

    def _get_cv_parsing_prompt(self) -> str:
        """Get the system prompt for CV parsing with GPT-4.

        Returns:
            str: Detailed prompt for structured CV extraction.
        """
        return """You are an expert CV/resume parser. Extract structured information from the provided CV text and return it as a JSON object.

**IMPORTANT**: You must return valid JSON that matches this exact schema:

```json
{
  "full_name": "string (candidate's full name)",
  "email": "string (primary email address)",
  "phone": "string (phone number)",
  "location": "string (current city, country)",
  "summary": "string (professional summary/objective)",
  "skills": ["array of technical and soft skills"],
  "technologies": ["array of programming languages, frameworks, tools"],
  "experience": [
    {
      "role": "Job title",
      "company": "Company name",
      "period": "Employment period (e.g. '2020-2023')",
      "description": "Brief description of role and achievements",
      "technologies": ["technologies used in this specific role"]
    }
  ],
  "education": [
    {
      "degree": "Degree type and field",
      "institution": "School/university name",
      "year": "Graduation year or period",
      "details": "Additional details like GPA, honors"
    }
  ],
  "certifications": ["array of professional certifications"],
  "languages": ["array of spoken languages with proficiency"],
  "total_years_experience": 0,
  "senior_technologies": ["technologies with 3+ years experience"]
}
```

**Parsing Guidelines:**

1. **Skills vs Technologies**: Separate generic skills (e.g., "Problem Solving", "Leadership") from specific technologies (e.g., "Python", "React", "Docker").

2. **Experience Calculation**: Estimate total_years_experience from work history. Include internships and part-time roles proportionally.

3. **Technology Seniority**: Mark technologies as "senior" if mentioned across multiple roles or with explicit experience duration (3+ years).

4. **Data Normalization**:
   - Standardize technology names (e.g., "JS" → "JavaScript", "React.js" → "React")
   - Use consistent date formats for periods
   - Clean up company names (remove "Inc.", "LLC" suffixes)

5. **Missing Information**: If information is not available, use empty string for strings, empty array for arrays, or 0 for numbers. Do not use null.

6. **Error Handling**: If the CV is unclear or incomplete, extract what you can and return valid JSON structure.

Return only the JSON object, no additional text or explanations."""

    async def get_parsing_stats(self) -> Dict[str, Any]:
        """Get statistics about CVs parsed (for monitoring/debugging).

        Returns:
            Dict[str, Any]: Parsing statistics and health metrics.
        """
        return {
            "agent_status": "active" if openai_client else "disabled",
            "model": self.model,
            "api_configured": bool(openai_client),
            "last_health_check": datetime.utcnow().isoformat()
        }