"""
Interview Coach Agent — Interview preparation material generator.

Generates technical and behavioral interview questions plus
technology cheat sheets based on job description analysis.

LLM Provider: OpenAI GPT-4.
"""

import logging

logger = logging.getLogger(__name__)


class InterviewCoachAgent:
    """Generates interview preparation materials.

    Produces two types of content per job:
    1. Interview questions (3 technical + 2 behavioral) with ideal answers.
    2. Technology cheat sheet (key concept per tech keyword in JD).
    """

    async def generate_questions(self, job_description: str) -> dict:
        """Generate interview questions based on a job description.

        Args:
            job_description: Full job description text.

        Returns:
            dict: Structured questions with answer guides.
                  {"technical": [...], "behavioral": [...]}
        """
        # TODO: Implement in Phase 2
        logger.info("InterviewCoachAgent.generate_questions called")
        return {"technical": [], "behavioral": []}

    async def generate_cheat_sheet(self, job_description: str) -> dict:
        """Generate a technology cheat sheet from job keywords.

        Args:
            job_description: Full job description text.

        Returns:
            dict: Key concepts mapped to tech keywords.
                  {"React": "Component-based UI library...", ...}
        """
        # TODO: Implement in Phase 2
        logger.info("InterviewCoachAgent.generate_cheat_sheet called")
        return {}
