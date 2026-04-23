"""
CV Optimizer Agent — ATS optimization and cover letter generation.

Uses OpenAI GPT-4 to rewrite resumes for better ATS compatibility and
generate personalized cover letters matching job requirements.
"""

import logging
from typing import Any, Dict, Optional

from app.config import get_settings
from app.utils.token_guard import truncate_for_budget
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)
settings = get_settings()


class CVOptimizerAgent:
    """AI-powered CV optimization and cover letter generation.

    Uses GPT-4 to analyze job requirements and optimize user resumes for
    better ATS (Applicant Tracking System) scoring. Also generates
    personalized cover letters tailored to specific job applications.

    Attributes:
        model: OpenAI model to use for optimization.
        max_tokens: Maximum tokens for AI responses.
        temperature: AI creativity level (lower = more focused).
    """

    def __init__(self):
        """Initialize CV Optimizer against the Gemini OpenAI-compat endpoint."""
        api_key = settings.openai_api_key
        if not api_key:
            logger.warning(
                "LLM API key not configured. AI features will be disabled. "
                "Set OPENAI_API_KEY to your Gemini API key."
            )
            self.client = None
            self.is_development = False
        else:
            # Only treat explicit placeholder keys as dev-mode; a real key
            # is a real key regardless of ENVIRONMENT.
            self.is_development = api_key.startswith("test-")
            self.client = (
                None
                if self.is_development
                else AsyncOpenAI(
                    api_key=api_key,
                    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                )
            )

            if self.is_development:
                logger.warning("Running in development mode with test API key. AI features will return mock responses.")

        self.model = "gemini-2.0-flash"  # Cheap JSON-capable model on Gemini
        self.max_tokens = 3000
        self.temperature = 0.3

    async def optimize_cv_for_job(
        self,
        parsed_cv: Dict[str, Any],
        job_description: str,
        job_title: str,
        company_name: str,
    ) -> Dict[str, Any]:
        """Optimize a parsed CV for a specific job posting.

        Analyzes job requirements and rewrites CV sections to improve
        ATS compatibility and keyword matching while maintaining accuracy.

        Args:
            parsed_cv: User's parsed CV data from CV profiler.
            job_description: Target job description text.
            job_title: Job title for context.
            company_name: Company name for personalization.

        Returns:
            dict: Optimized CV with improved ATS compatibility.
                Contains rewritten sections: summary, experience, skills.

        Raises:
            ValueError: If CV data is invalid or missing required fields.
            Exception: If OpenAI API request fails.

        Example:
            >>> optimizer = CVOptimizerAgent()
            >>> optimized = await optimizer.optimize_cv_for_job(
            ...     parsed_cv=user_cv_data,
            ...     job_description="Software Engineer position requiring Python...",
            ...     job_title="Senior Python Developer",
            ...     company_name="TechCorp Inc"
            ... )
            >>> print(optimized["summary"])
            "Experienced Python developer with 5+ years..."
        """
        logger.info(f"Starting CV optimization for {job_title} at {company_name}")

        try:
            # Validate API configuration
            if not self.client and not self.is_development:
                raise ValueError("OpenAI API key not configured. Set OPENAI_API_KEY to use AI features.")

            # Validate input CV data
            if not parsed_cv or not isinstance(parsed_cv, dict):
                raise ValueError("Invalid CV data: must be a non-empty dictionary")

            required_fields = ["summary", "experience", "skills"]
            for field in required_fields:
                if field not in parsed_cv:
                    logger.warning(f"Missing CV field: {field}")

            # Build optimization prompt
            system_prompt = self._build_cv_optimization_system_prompt()
            user_prompt = self._build_cv_optimization_user_prompt(
                parsed_cv, job_description, job_title, company_name
            )            # Call OpenAI API for CV optimization
            result = await self._make_api_call(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                response_format={"type": "json_object"},
                mock_response={
                    "summary": f"Experienced professional optimized for {job_title} role at {company_name}",
                    "experience": [
                        {
                            "company": "Previous Company",
                            "role": "Senior Developer",
                            "description": f"Led development projects relevant to {job_title} requirements"
                        }
                    ],
                    "skills": ["Python", "JavaScript", "React", "FastAPI", "Machine Learning"],
                    "optimized_keywords": ["Python", "API Development", "Full Stack"]
                }
            )
            
            if isinstance(result, str):
                import json
                optimized_cv = json.loads(result)
            else:
                optimized_cv = result

            # Validate optimized CV structure
            self._validate_optimized_cv(optimized_cv)

            logger.info(f"CV optimization completed for {job_title}")
            return optimized_cv

        except Exception as e:
            logger.error(f"CV optimization failed: {e}")
            raise

    async def generate_cover_letter(
        self,
        parsed_cv: Dict[str, Any],
        job_description: str,
        job_title: str,
        company_name: str,
        user_name: Optional[str] = None,
        user_motivation: Optional[str] = None,
    ) -> str:
        """Generate personalized cover letter for job application.

        Creates a tailored cover letter highlighting relevant experience
        and demonstrating knowledge of the company and role requirements.
        Supports an optional personal motivation statement from the user.

        Args:
            parsed_cv: User's parsed CV data.
            job_description: Job posting description.
            job_title: Target job title.
            company_name: Target company name.
            user_name: User's full name for personalization.
            user_motivation: Optional personal motivation statement to incorporate
                authentically into the cover letter opening or body.

        Returns:
            str: Generated cover letter text in professional format.

        Raises:
            ValueError: If required data is missing.
            Exception: If AI generation fails.

        Example:
            >>> letter = await optimizer.generate_cover_letter(
            ...     parsed_cv=cv_data,
            ...     job_description="We are seeking...",
            ...     job_title="Frontend Developer",
            ...     company_name="InnovateTech",
            ...     user_name="John Doe",
            ...     user_motivation="I have been following InnovateTech's work in..."
            ... )
            >>> print(letter[:100])
            "Dear Hiring Manager,\\n\\nI am writing to express..."
        """
        logger.info(f"Generating cover letter for {job_title} at {company_name}")

        try:
            # Validate API configuration
            if not self.client and not self.is_development:
                raise ValueError("OpenAI API key not configured. Set OPENAI_API_KEY to use AI features.")

            # Validate inputs
            if not parsed_cv:
                raise ValueError("CV data is required for cover letter generation")
            if not job_description or not job_title or not company_name:
                raise ValueError("Job details (description, title, company) are required")

            # Extract user's name from CV if not provided
            if not user_name:
                user_name = parsed_cv.get("personal_info", {}).get("full_name", "")
                if not user_name:
                    user_name = "[Your Name]"  # Placeholder if name not available

            # Build cover letter generation prompt (with optional user motivation)
            system_prompt = self._build_cover_letter_system_prompt()
            user_prompt = self._build_cover_letter_user_prompt(
                parsed_cv, job_description, job_title, company_name, user_name,
                user_motivation=user_motivation,
            )

            # Call OpenAI API for cover letter generation
            mock_cover_letter = f"""Dear Hiring Manager,

I am writing to express my strong interest in the {job_title} position at {company_name}. 

With my proven background and technical expertise, I am confident in my ability to make an immediate impact on your team. I have consistently delivered high-quality results in my previous roles, focusing on scalability, clean code, and effective collaboration. My experience aligns perfectly with the requirements mentioned in the job description.

I would welcome the opportunity to discuss how my skills and experiences can contribute to {company_name}'s continued success. Thank you for considering my application.

Sincerely,
[Your Name]"""

            cover_letter = await self._make_api_call(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=1500,
                temperature=0.4,
                mock_response=mock_cover_letter
            )
            if not cover_letter:
                raise Exception("Empty cover letter from OpenAI API")

            # Basic validation and cleanup
            cover_letter = cover_letter.strip()
            if len(cover_letter) < 200:
                raise Exception("Generated cover letter is too short")

            logger.info(f"Cover letter generated successfully for {job_title}")
            return cover_letter

        except Exception as e:
            logger.error(f"Cover letter generation failed: {e}")
            raise


    # Legacy method name for backward compatibility
    async def optimize_cv(self, parsed_cv: dict, job_description: str) -> dict:
        """Legacy wrapper for optimize_cv_for_job method."""
        return await self.optimize_cv_for_job(
            parsed_cv=parsed_cv,
            job_description=job_description,
            job_title="Unknown Position",
            company_name="Target Company"
        )

    def _build_cv_optimization_system_prompt(self) -> str:
        """Build system prompt for CV optimization task with strict NO_FABRICATION rules."""
        return """You are an expert ATS (Applicant Tracking System) optimization specialist and career counselor. Your role is to optimize resumes to improve their chances of passing ATS screening while maintaining complete factual accuracy.

⛔ NO_FABRICATION RULES (MANDATORY — violations are unacceptable):
1. You MUST NOT invent, fabricate, or hallucinate ANY experience, skill, achievement, company, date, or qualification.
2. You MUST NOT add years of experience the candidate does not have.
3. You MUST NOT claim technologies or certifications not present in the original CV.
4. You MUST ONLY rephrase, reorder, and integrate keywords from the JD into EXISTING content.
5. Every bullet point in the output MUST correspond to an existing bullet point in the input CV.

✅ ALLOWED optimizations:
- Rephrase existing bullet points to include relevant JD keywords naturally
- Reorder skills to prioritize job-relevant technologies first
- Update the summary to reference relevant JD terms using candidate’s actual experience
- Strengthen quantified results that are already present (do NOT invent numbers)
- Reorganize section order to match what the JD prioritizes

Return the optimized CV as a JSON object with this EXACT structure:
{
  "summary": "<optimized summary string>",
  "experience": [
    {
      "company": "<same as original>",
      "role": "<same as original>",
      "duration": "<same as original>",
      "description": "<rephrased bullets only using existing facts>"
    }
  ],
  "skills": ["<reordered and keyword-enhanced, NO new skills added>"],
  "education": [<unchanged or minor keyword additions only>],
  "optimized_keywords": ["<keywords from JD that were naturally integrated>"],
  "changes_summary": [
    "<description of change 1, e.g., 'Added JD keyword Python to existing backend experience bullet'>",
    "<description of change 2>"
  ]
}

The changes_summary field is MANDATORY and must list every modification made for user review."""

    def _build_cv_optimization_user_prompt(
        self,
        parsed_cv: Dict[str, Any],
        job_description: str,
        job_title: str,
        company_name: str,
    ) -> str:
        """Build user prompt for CV optimization with specific job context and NO_FABRICATION enforcement."""
        return f"""OPTIMIZATION REQUEST:
Job Title: {job_title}
Company: {company_name}

JOB DESCRIPTION (extract keywords and requirements from this):
{truncate_for_budget(job_description, token_budget=500).text}

ORIGINAL CV DATA (this is the ONLY source of truth — do NOT add anything not present here):
{parsed_cv}

INSTRUCTIONS — follow NO_FABRICATION rules strictly:
1. Extract key skills, technologies, and keywords from the JD above
2. Identify which keywords ALREADY EXIST in the original CV (even implicitly)
3. Rephrase existing bullet points to surface those keywords naturally
4. Reorder the skills list to put JD-relevant skills first
5. Update the summary using ONLY the candidate's actual experience
6. List every change made in the changes_summary field for user review
7. NEVER add experience, tools, or achievements not in the original CV

Return the optimized CV JSON with all required fields including changes_summary."""

    def _build_cover_letter_system_prompt(self) -> str:
        """Build system prompt for cover letter generation with NO_FABRICATION constraints."""
        return """You are a professional career counselor and expert cover letter writer. Create compelling, personalized cover letters that effectively connect candidate qualifications to job requirements.

⛔ NO_FABRICATION RULES (MANDATORY):
1. Base ALL claims ONLY on the candidate background provided — do NOT invent achievements.
2. Do NOT claim industry awards, publications, or certifications not in the CV.
3. Do NOT exaggerate years of experience beyond what the CV states.
4. If the user provided personal motivation, incorporate it authentically without embellishment.

✅ Cover Letter Guidelines:
1. **Professional Format**: Standard business letter structure
2. **Engaging Opening**: Hook the reader with genuine enthusiasm for the specific role
3. **Relevant Experience**: Highlight 2-3 most relevant ACTUAL achievements from the CV
4. **Company Knowledge**: Show understanding of company/role from the JD
5. **Personal Motivation**: Incorporate the user's stated motivation naturally if provided
6. **Strong Closing**: Clear call-to-action and enthusiasm
7. **Appropriate Length**: 3-4 paragraphs, 250-400 words

Write in a professional, confident, yet personable tone. Avoid generic phrases."""

    def _build_cover_letter_user_prompt(
        self,
        parsed_cv: Dict[str, Any],
        job_description: str,
        job_title: str,
        company_name: str,
        user_name: str,
        user_motivation: Optional[str] = None,
    ) -> str:
        """Build user prompt for cover letter generation with optional personal motivation."""
        # Extract key CV information for the prompt
        experience_summary = ""
        if "experience" in parsed_cv and parsed_cv["experience"]:
            experience_summary = "\n".join([
                f"- {exp.get('role', 'N/A')} at {exp.get('company', 'N/A')}: {exp.get('description', '')[:100]}..."
                for exp in parsed_cv["experience"][:3]  # Top 3 experiences
            ])

        skills_summary = ""
        if "skills" in parsed_cv and parsed_cv["skills"]:
            skills_summary = ", ".join(parsed_cv["skills"][:8])  # Top 8 skills

        motivation_section = ""
        if user_motivation:
            motivation_section = f"""
CANDIDATE'S PERSONAL MOTIVATION (incorporate authentically into the opening or body):
{user_motivation}
"""

        return f"""COVER LETTER REQUEST:
Name: {user_name}
Target Position: {job_title}
Target Company: {company_name}

JOB DESCRIPTION:
{truncate_for_budget(job_description, token_budget=375).text}

CANDIDATE BACKGROUND (use ONLY this — do NOT fabricate):

Key Experience:
{experience_summary}

Top Skills: {skills_summary}
{motivation_section}
INSTRUCTIONS:
Write a compelling cover letter that:
1. Opens with genuine enthusiasm for the specific role at {company_name}
2. Highlights the most relevant experience from the candidate's ACTUAL background
3. Shows understanding of the company's needs based on the job description
4. Demonstrates how the candidate's REAL skills solve the company's challenges
5. Incorporates the personal motivation naturally (if provided)
6. Closes with a professional request for an interview

Keep it engaging, specific, and professional. Base every claim on the candidate background above."""

    async def _make_api_call(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        temperature: float,
        response_format: Optional[Dict[str, str]] = None,
        mock_response: Any = None,
    ) -> Any:
        """Centralized method for making OpenAI API calls with development mode support."""
        if self.is_development:
            logger.info("Operating in development mode; returning mock response.")
            return mock_response

        if not self.client:
            raise ValueError("OpenAI client not initialized. Check API key configuration.")

        try:
            kwargs = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            if response_format:
                kwargs["response_format"] = response_format

            response = await self.client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content
            if content is None:
                raise ValueError("Empty response from OpenAI API")
            return content
        except Exception as e:
            logger.error(f"OpenAI API call failed: {e}")
            raise

    def _validate_optimized_cv(self, optimized_cv: Dict[str, Any]) -> None:
        """Validate structure of optimized CV returned by AI."""
        if not isinstance(optimized_cv, dict):
            raise ValueError("Optimized CV must be a dictionary")

        # Check for required sections (flexible since input CVs may vary)
        expected_sections = ["summary", "experience", "skills"]
        for section in expected_sections:
            if section in optimized_cv:
                if not optimized_cv[section]:
                    logger.warning(f"Empty section in optimized CV: {section}")

        logger.debug("Optimized CV structure validation passed")

    async def get_optimization_suggestions(
        self,
        parsed_cv: Dict[str, Any],
        job_description: str,
    ) -> Dict[str, Any]:
        """Generate specific suggestions for CV improvement without full rewrite.

        Provides actionable recommendations for improving ATS compatibility
        and job relevance without modifying the original CV content.

        Args:
            parsed_cv: Current CV data.
            job_description: Target job requirements.

        Returns:
            dict: Structured suggestions for CV improvements.
                Contains sections: keywords_to_add, sections_to_enhance,
                formatting_tips, and overall_score.
        """
        logger.info("Generating CV optimization suggestions")

        try:
            # Validate API configuration
            if not self.client and not self.is_development:
                raise ValueError("OpenAI API key not configured. Set OPENAI_API_KEY to use AI features.")

            system_prompt = """You are an ATS expert providing CV improvement suggestions. Analyze the CV and job requirements to provide specific, actionable recommendations.

Return suggestions as JSON with this structure:
{
    "keywords_to_add": ["keyword1", "keyword2"],
    "sections_to_enhance": {
        "experience": "Specific suggestions for experience section",
        "skills": "Specific suggestions for skills section"
    },
    "formatting_tips": ["tip1", "tip2"],
    "match_score": 85,
    "priority_improvements": ["Most important change", "Second priority"]
}"""

            user_prompt = f"""ANALYSIS REQUEST:
Current CV: {parsed_cv}
Job Description: {truncate_for_budget(job_description, token_budget=250).text}

Provide specific suggestions for improving ATS compatibility and job relevance."""

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=1000,
                temperature=0.2,
                response_format={"type": "json_object"}
            )

            import json
            content = response.choices[0].message.content
            if content is None:
                raise ValueError("Empty response from OpenAI API")
            suggestions = json.loads(content)
            logger.info("CV optimization suggestions generated successfully")
            return suggestions

        except Exception as e:
            logger.error(f"Failed to generate optimization suggestions: {e}")
            raise
