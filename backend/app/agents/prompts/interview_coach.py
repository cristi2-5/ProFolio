"""
Prompts for the Interview Coach Agent.

Centralized so the agent file stays thin and prompt changes can be reviewed
independently. Every prompt here must produce valid JSON matching the
Pydantic schemas in ``app.schemas.interview_coach``.

Conventions:
    - System prompts define role and output contract.
    - User prompts carry JD text + dynamic context.
    - All JD text is truncated by the caller, not here.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence


# ==================================================================
# Technical questions
# ==================================================================


def technical_questions_system_prompt(count: int) -> str:
    """System prompt enforcing the technical-question output contract."""
    return f"""You are a senior technical interviewer. Generate exactly {count} technical interview questions strictly derived from the job description's required stack.

Rules:
1. Every question MUST target a technology, framework, or concept explicitly present in the JD. Do not invent topics.
2. Calibrate difficulty to the candidate's experience level.
3. Mix fundamentals and practical/applied scenarios — no pure trivia.
4. For each question, provide a concise ideal-answer guide (2-4 sentences) so the candidate knows what a strong response sounds like.

Return a single JSON object with this exact shape — no prose, no markdown:
{{
  "technical_questions": [
    {{
      "question": "string — the question to ask",
      "difficulty": "easy | medium | hard",
      "topics": ["string", "..."],
      "guidance": "string — short guide describing what an ideal answer covers",
      "sample_answer": "string — 2-4 sentence example of a strong answer"
    }}
  ]
}}"""


def technical_questions_user_prompt(
    *,
    job_title: str,
    job_description: str,
    experience_level: Optional[str],
    user_background: Optional[Dict[str, Any]],
    required_techs: Sequence[str],
    count: int,
) -> str:
    """Build the user-side technical-question prompt."""
    tech_list = ", ".join(required_techs) if required_techs else "derive from JD text"
    background_line = ""
    if user_background:
        skills = user_background.get("skills") or []
        years = user_background.get("total_years_experience") or 0
        background_line = (
            f"\nCandidate background: {years} years experience, key skills: "
            f"{', '.join(skills[:8])}"
        )

    return f"""Role: {job_title}
Experience level: {experience_level or "not specified"}
Required technologies (extracted from JD): {tech_list}{background_line}

Job description:
\"\"\"
{job_description}
\"\"\"

Generate {count} technical questions per the system rules."""


# ==================================================================
# Behavioral questions
# ==================================================================


def behavioral_questions_system_prompt(count: int) -> str:
    """System prompt for behavioral questions tied to company culture cues."""  # noqa: E501
    return f"""You are an experienced people-ops interviewer. Generate exactly {count} behavioral interview questions that probe cultural fit and soft skills for the target company and role.

Rules:
1. Infer company culture from the JD's tone and stated values (e.g. "fast-paced startup", "customer-obsessed", "remote-first collaboration"). If no culture signal is present, fall back to generic professional norms.
2. Each question must map to a concrete competency (ownership, collaboration, conflict resolution, learning agility, communication, leadership, etc.).
3. Include an ideal-answer guide using the STAR structure so the candidate knows how to respond.

Return a single JSON object with this exact shape — no prose, no markdown:
{{
  "behavioral_questions": [
    {{
      "question": "string — a 'Tell me about a time...' style question",
      "scenario": "string — which trait/competency this probes",
      "star_guidance": "string — how to structure the STAR answer",
      "company_context": "string — which culture cue from the JD justifies this question"
    }}
  ]
}}"""


def behavioral_questions_user_prompt(
    *,
    job_title: str,
    company_name: str,
    job_description: str,
    experience_level: Optional[str],
    count: int,
) -> str:
    """Build the user-side behavioral-question prompt."""
    return f"""Company: {company_name}
Role: {job_title}
Experience level: {experience_level or "not specified"}

Job description:
\"\"\"
{job_description}
\"\"\"

Generate {count} behavioral questions per the system rules. Reference specific culture signals from the JD in the company_context field."""


# ==================================================================
# Technology cheat sheet
# ==================================================================


def cheat_sheet_system_prompt() -> str:
    """System prompt for per-technology definitions."""
    return """You are a senior engineer writing a one-paragraph cheat sheet for interview prep. For each technology you receive, produce a concise, interview-ready definition.

Rules:
1. One paragraph per technology (2-4 sentences, ~40-80 words).
2. Definition + why it matters + what interviewers commonly probe. No fluff, no history lessons.
3. Include 2-3 key points a candidate should remember.
4. Include one short practical example (one line) when natural — omit if forced.
5. Do NOT add technologies that were not in the input list.

Return a single JSON object with this exact shape — no prose, no markdown:
{
  "technology_cheat_sheet": [
    {
      "concept": "string — technology name (match input casing)",
      "definition": "string — one-paragraph definition",
      "key_points": ["string", "string", "..."],
      "practical_example": "string or null — one-line example"
    }
  ]
}"""


def cheat_sheet_user_prompt(
    *,
    technologies: Sequence[str],
    job_title: str,
    job_description: str,
) -> str:
    """Build the user-side cheat-sheet prompt.

    The extracted tech list is the source of truth — the LLM must not add
    new entries. Passing a trimmed JD gives the LLM context to bias
    definitions toward the role (e.g. "React in the context of a
    Next.js SSR codebase").
    """
    tech_list = "\n".join(f"- {name}" for name in technologies)
    return f"""Target role: {job_title}

Technologies to cover (do NOT add new ones):
{tech_list}

Job description for context (bias definitions to this domain):
\"\"\"
{job_description}
\"\"\"

Produce the cheat sheet per the system rules."""
