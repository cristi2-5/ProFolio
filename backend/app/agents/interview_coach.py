"""
Interview Coach Agent — AI-powered interview preparation.

Given a Job Description, generates technical questions tailored to the
required stack and behavioral questions aligned with the company's
cultural cues, each with an ideal-answer guide; also produces a cheat
sheet with concise one-paragraph definitions of each technology
mentioned in the JD.

Design notes:
    - All OpenAI calls go through ``_make_api_call`` so dev/test mode
      short-circuits to mock data without raising on a missing client.
    - Prompt text lives in ``app.agents.prompts.interview_coach`` so
      prompt tweaks don't churn the agent file.
    - Tech extraction lives in ``app.utils.tech_extractor`` — the same
      extractor drives the cheat-sheet prompt input so the LLM cannot
      silently add technologies the candidate won't be asked about.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI, BadRequestError
from pydantic import ValidationError

from app.agents._prompt_safety import sanitize_user_text, wrap_user_content
from app.agents.prompts import interview_coach as prompts
from app.config import get_settings
from app.schemas.interview_coach import (
    BehavioralQuestion,
    TechnicalQuestion,
    TechnologyConcept,
)
from app.utils.exceptions import InterviewCoachError
from app.utils.llm_retry import GEMINI_FLASH_MODELS, with_model_fallback
from app.utils.prompt_cache import build_cache_key, get_prompt_cache
from app.utils.tech_extractor import ExtractedTech, extract_technologies
from app.utils.token_guard import (
    DEFAULT_JD_TOKEN_BUDGET,
    TruncationResult,
    truncate_for_budget,
)

logger = logging.getLogger(__name__)

# JD token budget for prompt assembly. Tech extraction always runs on the
# full JD before we truncate, so we never drop technologies from the
# cheat-sheet input even if the JD is huge.
_JD_TOKEN_BUDGET = DEFAULT_JD_TOKEN_BUDGET

# Defaults per US 4.1 acceptance criteria.
DEFAULT_TECHNICAL_COUNT = 3
DEFAULT_BEHAVIORAL_COUNT = 2
DEFAULT_CHEATSHEET_TECH_COUNT = 8


class InterviewCoachAgent:
    """AI-powered interview preparation generator.

    Produces a bundle of technical questions, behavioral questions, and a
    per-technology cheat sheet for a given job description.
    """

    def __init__(self) -> None:
        """Initialize against the Gemini OpenAI-compat endpoint, falling back
        to dev mode gracefully when no key is configured."""
        settings = get_settings()
        api_key = settings.openai_api_key

        if not api_key:
            logger.warning(
                "LLM API key not configured; Interview Coach will return mock data."
            )
            self.client: Optional[AsyncOpenAI] = None
            self.is_development = True
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

        self.models = GEMINI_FLASH_MODELS  # fallback chain: 3.0 → 2.5 → 2.0
        self.temperature = 0.4

    # ------------------------------------------------------------------
    # Top-level orchestration
    # ------------------------------------------------------------------

    async def generate_interview_prep_materials(
        self,
        *,
        job_description: str,
        job_title: str,
        company_name: str,
        user_experience_level: Optional[str] = None,
        user_background: Optional[Dict[str, Any]] = None,
        technical_count: int = DEFAULT_TECHNICAL_COUNT,
        behavioral_count: int = DEFAULT_BEHAVIORAL_COUNT,
        cheatsheet_tech_count: int = DEFAULT_CHEATSHEET_TECH_COUNT,
    ) -> Dict[str, Any]:
        """Generate the full interview-prep bundle for a job.

        Args:
            job_description: Full JD text.
            job_title: Target role title.
            company_name: Target company name.
            user_experience_level: Junior/mid/senior (optional).
            user_background: Parsed CV data (optional).
            technical_count: Number of technical questions. Defaults to 3.
            behavioral_count: Number of behavioral questions. Defaults to 2.
            cheatsheet_tech_count: Max technologies to cover in the cheat sheet.

        Returns:
            Dict with keys ``technical_questions``, ``behavioral_questions``,
            ``technology_cheat_sheet``, ``extracted_technologies``.

        Raises:
            ValueError: If any of the required inputs are empty.
        """
        if not job_description or not job_title or not company_name:
            raise ValueError("Job description, title, and company name are required")

        logger.info(
            "Generating interview prep for '%s' at '%s'", job_title, company_name
        )

        # Deterministic extraction runs on the full JD — this is the
        # source of truth for US 4.2.
        extracted = extract_technologies(
            job_description, max_results=cheatsheet_tech_count
        )

        # Compute truncation up-front so we can surface it to the caller.
        truncation = truncate_for_budget(job_description, token_budget=_JD_TOKEN_BUDGET)
        truncation_chars_dropped = max(len(job_description) - len(truncation.text), 0)

        # All three generators are independent — fan out so the user
        # waits for max(t1, t2, t3) instead of t1+t2+t3.
        technical, behavioral, cheat_sheet = await asyncio.gather(
            self.generate_technical_questions(
                job_description=job_description,
                job_title=job_title,
                user_experience_level=user_experience_level,
                user_background=user_background,
                required_techs=[t.name for t in extracted],
                question_count=technical_count,
            ),
            self.generate_behavioral_questions(
                job_description=job_description,
                job_title=job_title,
                company_name=company_name,
                user_experience_level=user_experience_level,
                question_count=behavioral_count,
            ),
            self.generate_technology_cheat_sheet(
                job_description=job_description,
                job_title=job_title,
                extracted_techs=extracted,
            ),
        )

        return {
            "technical_questions": technical,
            "behavioral_questions": behavioral,
            "technology_cheat_sheet": cheat_sheet,
            "extracted_technologies": [
                {"name": t.name, "category": t.category, "mentions": t.mentions}
                for t in extracted
            ],
            "jd_truncated": truncation.was_truncated,
            "jd_truncation_chars_dropped": truncation_chars_dropped,
        }

    # ------------------------------------------------------------------
    # US 4.1 — Technical questions
    # ------------------------------------------------------------------

    async def generate_technical_questions(
        self,
        *,
        job_description: str,
        job_title: str,
        user_experience_level: Optional[str] = None,
        user_background: Optional[Dict[str, Any]] = None,
        required_techs: Optional[List[str]] = None,
        question_count: int = DEFAULT_TECHNICAL_COUNT,
    ) -> List[Dict[str, Any]]:
        """Generate technical interview questions for the JD stack."""
        techs = (
            required_techs
            if required_techs is not None
            else [t.name for t in extract_technologies(job_description)]
        )

        system_prompt = prompts.technical_questions_system_prompt(question_count)
        user_prompt = prompts.technical_questions_user_prompt(
            job_title=job_title,
            job_description=self._trim_jd(job_description),
            experience_level=user_experience_level,
            user_background=user_background,
            required_techs=techs,
            count=question_count,
        )

        mock = {
            "technical_questions": [
                _mock_technical_question(i, techs) for i in range(question_count)
            ]
        }
        data = await self._make_api_call(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=4000,
            response_format={"type": "json_object"},
            mock_response=mock,
        )
        return _validate_items(
            _coerce_list(data, "technical_questions"),
            TechnicalQuestion,
            "technical_questions",
        )

    # ------------------------------------------------------------------
    # US 4.1 — Behavioral questions
    # ------------------------------------------------------------------

    async def generate_behavioral_questions(
        self,
        *,
        job_description: str,
        job_title: str,
        company_name: str,
        user_experience_level: Optional[str] = None,
        question_count: int = DEFAULT_BEHAVIORAL_COUNT,
    ) -> List[Dict[str, Any]]:
        """Generate behavioral questions aligned with company culture cues."""
        system_prompt = prompts.behavioral_questions_system_prompt(question_count)
        user_prompt = prompts.behavioral_questions_user_prompt(
            job_title=job_title,
            company_name=company_name,
            job_description=self._trim_jd(job_description),
            experience_level=user_experience_level,
            count=question_count,
        )

        mock = {
            "behavioral_questions": [
                _mock_behavioral_question(i, company_name)
                for i in range(question_count)
            ]
        }
        data = await self._make_api_call(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=4000,
            response_format={"type": "json_object"},
            mock_response=mock,
        )
        return _validate_items(
            _coerce_list(data, "behavioral_questions"),
            BehavioralQuestion,
            "behavioral_questions",
        )

    # ------------------------------------------------------------------
    # US 4.2 — Technology cheat sheet
    # ------------------------------------------------------------------

    async def generate_technology_cheat_sheet(
        self,
        *,
        job_description: str,
        job_title: str = "",
        extracted_techs: Optional[List[ExtractedTech]] = None,
    ) -> List[Dict[str, Any]]:
        """Generate one definition paragraph per technology mentioned in the JD.

        The technology list comes from the deterministic extractor; the LLM
        only writes definitions. If no technologies are detected, returns an
        empty list (no LLM call).
        """
        techs = (
            extracted_techs
            if extracted_techs is not None
            else extract_technologies(job_description)
        )
        if not techs:
            logger.info("No technologies detected in JD; skipping cheat sheet")
            return []

        system_prompt = prompts.cheat_sheet_system_prompt()
        user_prompt = prompts.cheat_sheet_user_prompt(
            technologies=[t.name for t in techs],
            job_title=job_title,
            job_description=self._trim_jd(job_description),
        )

        mock = {
            "technology_cheat_sheet": [_mock_cheat_sheet_entry(t) for t in techs],
        }
        data = await self._make_api_call(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=4500,
            response_format={"type": "json_object"},
            mock_response=mock,
        )
        return _validate_items(
            _coerce_list(data, "technology_cheat_sheet"),
            TechnologyConcept,
            "technology_cheat_sheet",
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _make_api_call(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        response_format: Optional[Dict[str, str]] = None,
        mock_response: Any = None,
    ) -> Any:
        """Run an OpenAI chat completion with transparent prompt caching.

        Cache lookup happens before the network call; on a hit we skip
        the API entirely. In dev mode the mock response is returned
        without touching the cache (keeps tests deterministic).
        """
        if self.is_development:
            logger.info("Interview Coach in development mode — returning mock response")
            return mock_response

        if not self.client:
            raise ValueError(
                "OpenAI client not initialized. Check OPENAI_API_KEY configuration."
            )

        cache = get_prompt_cache()
        response_format_key = response_format.get("type") if response_format else None
        # Cache key uses the primary model so cache hits are consistent
        cache_key = build_cache_key(
            model=self.models[0],
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_format=response_format_key,
            temperature=self.temperature,
        )

        cached = await cache.get(cache_key)
        if cached is not None:
            logger.debug("Prompt cache hit: %s", cache_key)
            return cached

        base_kwargs: Dict[str, Any] = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": self.temperature,
        }
        if response_format:
            base_kwargs["response_format"] = response_format

        async def _call(model: str) -> Any:
            return await self.client.chat.completions.create(model=model, **base_kwargs)

        try:
            response, used_model = await with_model_fallback(_call, self.models)
            if used_model != self.models[0]:
                logger.info("Interview coach used fallback model: %s", used_model)
        except BadRequestError as exc:
            logger.error("OpenAI rejected interview-coach request: %s", exc)
            raise InterviewCoachError("LLM rejected the request") from exc

        content = response.choices[0].message.content
        if not content:
            raise InterviewCoachError("Empty response from LLM")

        if response_format and response_format.get("type") == "json_object":
            parsed = _parse_llm_json(content)
            if parsed is None:
                logger.error(
                    "Interview-coach LLM returned non-JSON after all repair attempts: raw=%r",
                    content[:800],
                )
                raise InterviewCoachError("LLM returned malformed interview prep")
            await cache.set(cache_key, parsed)
            return parsed

        await cache.set(cache_key, content)
        return content

    # ------------------------------------------------------------------
    # Token-budget protection
    # ------------------------------------------------------------------

    @staticmethod
    def _trim_jd(job_description: str) -> str:
        """Trim an over-budget JD with a head+tail strategy.

        Also sanitizes the trimmed text and wraps it in BEGIN/END
        delimiters so the LLM can't be talked out of treating it as
        untrusted input. Logs a WARNING when truncation happens.
        """
        result: TruncationResult = truncate_for_budget(
            job_description, token_budget=_JD_TOKEN_BUDGET
        )
        if result.was_truncated:
            logger.warning(
                "JD truncated for token budget: %d → %d tokens (budget=%d)",
                result.estimated_tokens_in,
                result.estimated_tokens_out,
                _JD_TOKEN_BUDGET,
            )
        return wrap_user_content("JOB DESCRIPTION", sanitize_user_text(result.text))


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _parse_llm_json(content: str) -> Optional[Dict[str, Any]]:
    """Best-effort JSON parser for LLM output. Returns None on total failure.

    LLMs (especially smaller fallback models) emit "almost-JSON" with common
    issues:
      1. Markdown code fences (```json ... ```)
      2. Trailing commas before } or ]
      3. JS-style comments (// or /* */)
      4. Truncated mid-string when max_tokens is hit
      5. Surrounding prose before/after the actual JSON object

    This function tries each repair strategy in order and returns the first
    that produces a valid JSON object. Logs at WARNING when a repair was
    needed (so we can spot model regressions) and at ERROR when nothing works.
    """
    import re

    text = (content or "").strip()
    if not text:
        return None

    # 1. Strip markdown code fences.
    if text.startswith("```"):
        lines = text.splitlines()
        inner = [ln for ln in lines if not ln.startswith("```")]
        text = "\n".join(inner).strip()

    # 2. Try direct parse.
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 3. Extract first {...} block (handles surrounding prose).
    match = re.search(r"\{.*\}", text, re.DOTALL)
    candidate = match.group() if match else text

    # 4. Repair pass: strip trailing commas + JS comments.
    repaired = re.sub(r",(\s*[}\]])", r"\1", candidate)
    repaired = re.sub(r"//[^\n]*", "", repaired)
    repaired = re.sub(r"/\*.*?\*/", "", repaired, flags=re.DOTALL)
    try:
        result = json.loads(repaired)
        logger.warning("LLM JSON required repair (trailing commas / comments)")
        return result
    except json.JSONDecodeError:
        pass

    # 5. Truncation recovery: walk back from the end, looking for the last
    #    balanced closing brace. This handles the case where the LLM ran out
    #    of tokens mid-output.
    depth = 0
    in_string = False
    escape = False
    last_close_idx = -1
    for i, ch in enumerate(repaired):
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                last_close_idx = i

    if last_close_idx > 0:
        try:
            result = json.loads(repaired[: last_close_idx + 1])
            logger.warning(
                "LLM JSON required truncation recovery (used first %d chars)",
                last_close_idx + 1,
            )
            return result
        except json.JSONDecodeError:
            pass

    return None



def _coerce_list(data: Any, key: str) -> List[Dict[str, Any]]:
    """Accept either a raw list or a ``{key: [...]}`` envelope."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        value = data.get(key)
        if isinstance(value, list):
            return value
    return []


def _validate_items(
    items: List[Dict[str, Any]], model: type, label: str
) -> List[Dict[str, Any]]:
    """Pydantic-validate each list item; drop malformed items.

    Returns the model_dump'd dicts so downstream JSON serialization is
    unchanged from the previous (untyped) shape. With ``extra="ignore"``
    + defaulted fields on the schemas, validation rarely fails — but if a
    single item still fails, we drop it rather than aborting the whole
    bundle. Only if EVERY item fails do we raise InterviewCoachError.
    """
    validated: List[Dict[str, Any]] = []
    failures = 0
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            logger.warning(
                "Interview-coach %s item %d is not a dict (got %s); skipping",
                label, index, type(item).__name__,
            )
            failures += 1
            continue
        try:
            validated.append(model(**item).model_dump())
        except (ValidationError, TypeError) as exc:
            logger.warning(
                "Interview-coach %s item %d failed schema validation; skipping: %s | raw=%r",
                label, index, exc, str(item)[:300],
            )
            failures += 1

    if items and not validated:
        logger.error(
            "Interview-coach %s: all %d items failed validation",
            label, failures,
        )
        raise InterviewCoachError("LLM returned malformed interview prep")
    return validated


def _mock_technical_question(index: int, techs: List[str]) -> Dict[str, Any]:
    """Deterministic mock used when no API key is configured."""
    subject = techs[index % len(techs)] if techs else "the required stack"
    return {
        "question": f"Explain a tradeoff you evaluated when working with {subject}.",
        "difficulty": ["easy", "medium", "hard"][index % 3],
        "topics": [subject],
        "guidance": (
            f"Describe a concrete decision involving {subject}, the constraints "
            "you balanced, and the outcome."
        ),
        "sample_answer": (
            f"In a recent project I chose {subject} because of its fit with the "
            "team's existing skills, at the cost of slower cold starts — I "
            "mitigated that with caching."
        ),
    }


def _mock_behavioral_question(index: int, company_name: str) -> Dict[str, Any]:
    """Deterministic mock behavioral question."""
    competencies = ["ownership", "collaboration"]
    competency = competencies[index % len(competencies)]
    return {
        "question": f"Tell me about a time you demonstrated {competency} on a tough project.",
        "scenario": f"Assessing {competency} under pressure.",
        "star_guidance": (
            "Set the Situation briefly, define the Task, describe concrete "
            "Actions you took, and quantify the Result."
        ),
        "company_context": f"{company_name}'s JD emphasizes {competency}.",
    }


def _mock_cheat_sheet_entry(tech: ExtractedTech) -> Dict[str, Any]:
    """Deterministic mock cheat-sheet entry."""
    return {
        "concept": tech.name,
        "definition": (
            f"{tech.name} is a widely used {tech.category.replace('_', ' ')} "
            "technology. Interviewers typically probe your understanding of its "
            "core model and the tradeoffs it introduces."
        ),
        "key_points": [
            f"Core {tech.category.replace('_', ' ')} use cases",
            "Common failure modes to mention",
        ],
        "practical_example": None,
    }
