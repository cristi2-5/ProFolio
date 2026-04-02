"""
CV Profiler Agent — Automatic resume parsing.

Extracts structured data from uploaded PDF/DOCX files using
OpenAI GPT-4. Outputs a JSON structure with skills, experience,
education, and technologies.

LLM Provider: OpenAI GPT-4 (selected for structured output quality).
"""

import logging

logger = logging.getLogger(__name__)


class CVProfilerAgent:
    """Parses uploaded CVs and extracts structured candidate data.

    Uses a two-step process:
    1. Text extraction from PDF/DOCX using PyPDF2/python-docx.
    2. Structured data extraction via GPT-4 with a restrictive prompt.

    Output format:
        {
            "skills": ["Python", "React", ...],
            "experience": [
                {"role": "...", "company": "...", "period": "...",
                 "description": "..."}
            ],
            "education": [
                {"degree": "...", "institution": "...", "year": "..."}
            ],
            "technologies": ["Docker", "PostgreSQL", ...]
        }
    """

    async def parse(self, file_path: str) -> dict:
        """Parse a CV file and return structured data.

        Args:
            file_path: Path to the uploaded CV file.

        Returns:
            dict: Structured resume data.

        Raises:
            ValueError: If file format is unsupported or unreadable.
        """
        # TODO: Implement in Phase 2
        logger.info("CVProfilerAgent.parse called for: %s", file_path)
        return {
            "skills": [],
            "experience": [],
            "education": [],
            "technologies": [],
        }
