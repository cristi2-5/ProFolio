"""
CV Optimizer Agent — ATS optimization and cover letter generation.

Uses OpenAI GPT-4 to rewrite resumes for better ATS compatibility and
generate personalized cover letters matching job requirements.
"""

import logging
from typing import Any, Dict, Optional

from app.config import get_settings
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
        """Initialize CV Optimizer with OpenAI configuration."""
        if not settings.openai_api_key:
            raise ValueError("OpenAI API key not configured. Set OPENAI_API_KEY environment variable.")

        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = "gpt-4o-mini"  # Cost-effective model for text optimization
        self.max_tokens = 3000      # Longer output for optimized CVs
        self.temperature = 0.3      # Balanced creativity for professional content

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
            )

            # Call OpenAI API for CV optimization
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                response_format={"type": "json_object"}
            )

            # Parse AI response
            optimized_content = response.choices[0].message.content
            if not optimized_content:
                raise Exception("Empty response from OpenAI API")

            import json
            optimized_cv = json.loads(optimized_content)

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
    ) -> str:
        """Generate personalized cover letter for job application.

        Creates a tailored cover letter highlighting relevant experience
        and demonstrating knowledge of the company and role requirements.

        Args:
            parsed_cv: User's parsed CV data.
            job_description: Job posting description.
            job_title: Target job title.
            company_name: Target company name.
            user_name: User's full name for personalization.

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
            ...     user_name="John Doe"
            ... )
            >>> print(letter[:100])
            "Dear Hiring Manager,\\n\\nI am writing to express..."
        """
        logger.info(f"Generating cover letter for {job_title} at {company_name}")

        try:
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

            # Build cover letter generation prompt
            system_prompt = self._build_cover_letter_system_prompt()
            user_prompt = self._build_cover_letter_user_prompt(
                parsed_cv, job_description, job_title, company_name, user_name
            )

            # Call OpenAI API for cover letter generation
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=1500,  # Cover letters should be concise
                temperature=0.4   # Slightly more creative for personal touch
            )

            cover_letter = response.choices[0].message.content
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
        """Build system prompt for CV optimization task."""
        return """You are an expert ATS (Applicant Tracking System) optimization specialist and career counselor. Your role is to optimize resumes to improve their chances of passing ATS screening while maintaining accuracy and professionalism.

Key principles for CV optimization:
1. **Keyword Integration**: Naturally incorporate relevant keywords from job descriptions
2. **ATS Formatting**: Use clear section headers and standard formatting
3. **Quantifiable Results**: Emphasize measurable achievements and impact
4. **Relevance Prioritization**: Highlight most relevant experience first
5. **Accuracy Maintenance**: Never fabricate experience or skills

Optimize these CV sections:
- **Summary**: 2-3 sentences highlighting relevant expertise
- **Experience**: Rewrite bullet points with job-relevant keywords and quantified results
- **Skills**: Reorganize and enhance skill lists to match job requirements
- **Education**: Keep factual, add relevant coursework if applicable

Return the optimized CV as a JSON object with the same structure as the input, but with improved, ATS-friendly content."""

    def _build_cv_optimization_user_prompt(
        self,
        parsed_cv: Dict[str, Any],
        job_description: str,
        job_title: str,
        company_name: str,
    ) -> str:
        """Build user prompt for CV optimization with specific job context."""
        return f"""OPTIMIZATION REQUEST:
Job Title: {job_title}
Company: {company_name}

JOB DESCRIPTION:
{job_description[:2000]}

CURRENT CV DATA:
{parsed_cv}

INSTRUCTIONS:
1. Analyze the job requirements and identify key skills, technologies, and qualifications
2. Optimize the CV to better match these requirements while maintaining truthfulness
3. Rewrite experience bullet points to emphasize relevant achievements
4. Reorganize skills to prioritize job-relevant technologies
5. Update the summary to highlight the most relevant qualifications
6. Ensure all content is ATS-friendly with clear formatting

Return the optimized CV as a JSON object with the same structure but improved content."""

    def _build_cover_letter_system_prompt(self) -> str:
        """Build system prompt for cover letter generation."""
        return """You are a professional career counselor and expert cover letter writer. Create compelling, personalized cover letters that effectively connect candidate qualifications to job requirements.

Cover Letter Guidelines:
1. **Professional Format**: Standard business letter structure
2. **Engaging Opening**: Hook the reader in the first paragraph
3. **Relevant Experience**: Highlight 2-3 most relevant achievements
4. **Company Knowledge**: Show understanding of company/role
5. **Strong Closing**: Clear call-to-action and enthusiasm
6. **Appropriate Length**: 3-4 paragraphs, 250-400 words

Structure Template:
- Opening: Express interest and mention specific role
- Body 1: Highlight relevant experience with specific examples
- Body 2: Demonstrate company knowledge and cultural fit
- Closing: Request interview and reiterate enthusiasm

Write in a professional, confident, yet personable tone. Avoid generic phrases and ensure each letter feels tailored to the specific opportunity."""

    def _build_cover_letter_user_prompt(
        self,
        parsed_cv: Dict[str, Any],
        job_description: str,
        job_title: str,
        company_name: str,
        user_name: str,
    ) -> str:
        """Build user prompt for cover letter generation."""
        # Extract key CV information for the prompt
        experience_summary = ""
        if "experience" in parsed_cv and parsed_cv["experience"]:
            experience_summary = "\\n".join([
                f"- {exp.get('role', 'N/A')} at {exp.get('company', 'N/A')}: {exp.get('description', '')[:100]}..."
                for exp in parsed_cv["experience"][:3]  # Top 3 experiences
            ])

        skills_summary = ""
        if "skills" in parsed_cv and parsed_cv["skills"]:
            skills_summary = ", ".join(parsed_cv["skills"][:8])  # Top 8 skills

        return f"""COVER LETTER REQUEST:
Name: {user_name}
Target Position: {job_title}
Target Company: {company_name}

JOB DESCRIPTION:
{job_description[:1500]}

CANDIDATE BACKGROUND:

Key Experience:
{experience_summary}

Top Skills: {skills_summary}

INSTRUCTIONS:
Write a compelling cover letter that:
1. Opens with enthusiasm for the specific role at {company_name}
2. Highlights the most relevant experience from the candidate's background
3. Shows understanding of the company's needs based on the job description
4. Demonstrates how the candidate's skills solve the company's challenges
5. Closes with a professional request for an interview

Keep it engaging, specific, and professional. Avoid generic language."""

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
Job Description: {job_description[:1000]}

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
            suggestions = json.loads(response.choices[0].message.content)
            logger.info("CV optimization suggestions generated successfully")
            return suggestions

        except Exception as e:
            logger.error(f"Failed to generate optimization suggestions: {e}")
            raise
