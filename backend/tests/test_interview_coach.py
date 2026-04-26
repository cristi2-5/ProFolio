"""
Tests for the Interview Coach Agent (Phase 5 / Epic 4).

Covers:
    US 4.1 — 3 technical + 2 behavioral questions with ideal-answer guidance.
    US 4.2 — Deterministic tech extraction feeding the cheat-sheet prompt.

The OpenAI client is always mocked. Dev-mode mock responses are also
exercised to catch regressions of the previous "client is None" crash bug.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from openai import AsyncOpenAI

from app.agents.interview_coach import (
    DEFAULT_BEHAVIORAL_COUNT,
    DEFAULT_TECHNICAL_COUNT,
    InterviewCoachAgent,
)

# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _mock_openai_response(payload: Dict[str, Any]) -> Mock:
    """Wrap a JSON payload in the OpenAI ChatCompletion response shape."""
    response = Mock()
    response.choices = [Mock()]
    response.choices[0].message.content = json.dumps(payload)
    return response


SAMPLE_JD = """
Senior Backend Engineer — TechCorp (remote-first, customer-obsessed startup)

We're hiring a Python engineer to own our core API. You'll work with
FastAPI, PostgreSQL, Redis, and Docker. Experience with AWS deployments,
CI/CD pipelines, and microservices is required. We value ownership,
pragmatism, and fast iteration.
"""


# ----------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------


@pytest.fixture
def coach_with_client() -> InterviewCoachAgent:
    """Agent wired to a mocked async OpenAI client (non-dev mode)."""
    with patch("app.agents.interview_coach.get_settings") as get_settings:
        settings = Mock()
        settings.openai_api_key = "sk-live-key"
        settings.environment = "production"
        get_settings.return_value = settings

        agent = InterviewCoachAgent()
        assert agent.is_development is False

        client = MagicMock(spec=AsyncOpenAI)
        client.chat = MagicMock()
        client.chat.completions = MagicMock()
        client.chat.completions.create = AsyncMock()
        agent.client = client
        return agent


@pytest.fixture
def coach_in_dev_mode() -> InterviewCoachAgent:
    """Agent running in dev-mode (no API key) — must use mock responses."""
    with patch("app.agents.interview_coach.get_settings") as get_settings:
        settings = Mock()
        settings.openai_api_key = ""
        settings.environment = "development"
        get_settings.return_value = settings

        agent = InterviewCoachAgent()
        assert agent.is_development is True
        assert agent.client is None
        return agent


# ----------------------------------------------------------------------
# US 4.1 — technical questions
# ----------------------------------------------------------------------


class TestTechnicalQuestions:
    """Technical question generation."""

    @pytest.mark.asyncio
    async def test_returns_list_from_envelope_response(self, coach_with_client) -> None:
        payload: List[Dict[str, Any]] = [
            {
                "question": "Explain FastAPI dependency injection.",
                "difficulty": "medium",
                "topics": ["FastAPI", "Python"],
                "guidance": "Cover Depends(), lifetimes, overrides.",
                "sample_answer": "FastAPI's Depends() lets you declare...",
            }
        ]
        coach_with_client.client.chat.completions.create.return_value = (
            _mock_openai_response({"technical_questions": payload})
        )

        result = await coach_with_client.generate_technical_questions(
            job_description=SAMPLE_JD,
            job_title="Backend Engineer",
            question_count=3,
        )

        assert result == payload
        assert coach_with_client.client.chat.completions.create.call_count == 1

    @pytest.mark.asyncio
    async def test_requests_json_object_format(self, coach_with_client) -> None:
        coach_with_client.client.chat.completions.create.return_value = (
            _mock_openai_response({"technical_questions": []})
        )

        await coach_with_client.generate_technical_questions(
            job_description=SAMPLE_JD,
            job_title="Backend Engineer",
        )

        call_kwargs = coach_with_client.client.chat.completions.create.call_args.kwargs
        assert call_kwargs["response_format"] == {"type": "json_object"}
        assert call_kwargs["model"] == "gemini-2.5-flash"  # primary model in fallback chain

    @pytest.mark.asyncio
    async def test_includes_extracted_techs_in_prompt(self, coach_with_client) -> None:
        coach_with_client.client.chat.completions.create.return_value = (
            _mock_openai_response({"technical_questions": []})
        )

        await coach_with_client.generate_technical_questions(
            job_description=SAMPLE_JD,
            job_title="Backend Engineer",
        )

        user_prompt = coach_with_client.client.chat.completions.create.call_args.kwargs[
            "messages"
        ][1]["content"]
        # Extractor should lift Python/FastAPI/PostgreSQL/Docker from the JD
        # and include them in the user prompt.
        assert "Python" in user_prompt
        assert "FastAPI" in user_prompt

    @pytest.mark.asyncio
    async def test_dev_mode_returns_mock_without_calling_api(
        self, coach_in_dev_mode
    ) -> None:
        result = await coach_in_dev_mode.generate_technical_questions(
            job_description=SAMPLE_JD,
            job_title="Backend Engineer",
            question_count=3,
        )
        assert len(result) == 3
        for item in result:
            assert "question" in item
            assert "difficulty" in item
            assert "guidance" in item


# ----------------------------------------------------------------------
# US 4.1 — behavioral questions
# ----------------------------------------------------------------------


class TestBehavioralQuestions:
    """Behavioral question generation."""

    @pytest.mark.asyncio
    async def test_returns_list_with_company_context(self, coach_with_client) -> None:
        payload = [
            {
                "question": "Tell me about a time you took ownership.",
                "scenario": "Ownership under ambiguity",
                "star_guidance": "Situation → Task → Action → Result",
                "company_context": "TechCorp values ownership and pragmatism",
            }
        ]
        coach_with_client.client.chat.completions.create.return_value = (
            _mock_openai_response({"behavioral_questions": payload})
        )

        result = await coach_with_client.generate_behavioral_questions(
            job_description=SAMPLE_JD,
            job_title="Backend Engineer",
            company_name="TechCorp",
            question_count=2,
        )
        assert result == payload
        assert "TechCorp" in result[0]["company_context"]

    @pytest.mark.asyncio
    async def test_company_name_surfaced_in_prompt(self, coach_with_client) -> None:
        coach_with_client.client.chat.completions.create.return_value = (
            _mock_openai_response({"behavioral_questions": []})
        )

        await coach_with_client.generate_behavioral_questions(
            job_description=SAMPLE_JD,
            job_title="Backend Engineer",
            company_name="AcmeCo",
        )
        user_prompt = coach_with_client.client.chat.completions.create.call_args.kwargs[
            "messages"
        ][1]["content"]
        assert "AcmeCo" in user_prompt

    @pytest.mark.asyncio
    async def test_dev_mode_returns_mock(self, coach_in_dev_mode) -> None:
        result = await coach_in_dev_mode.generate_behavioral_questions(
            job_description=SAMPLE_JD,
            job_title="Backend Engineer",
            company_name="TechCorp",
            question_count=2,
        )
        assert len(result) == 2
        for item in result:
            assert item["question"]
            assert item["star_guidance"]


# ----------------------------------------------------------------------
# US 4.2 — cheat sheet
# ----------------------------------------------------------------------


class TestTechnologyCheatSheet:
    """Cheat-sheet generation pipeline (US 4.2)."""

    @pytest.mark.asyncio
    async def test_skips_llm_when_no_techs_found(self, coach_with_client) -> None:
        # Benign JD with no known technologies.
        result = await coach_with_client.generate_technology_cheat_sheet(
            job_description="We want a friendly, curious collaborator.",
        )
        assert result == []
        coach_with_client.client.chat.completions.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_passes_extracted_techs_to_prompt(self, coach_with_client) -> None:
        payload = [
            {
                "concept": "Python",
                "definition": "Python is a high-level language...",
                "key_points": ["Dynamic typing"],
                "practical_example": None,
            }
        ]
        coach_with_client.client.chat.completions.create.return_value = (
            _mock_openai_response({"technology_cheat_sheet": payload})
        )

        result = await coach_with_client.generate_technology_cheat_sheet(
            job_description=SAMPLE_JD,
        )
        assert result == payload

        user_prompt = coach_with_client.client.chat.completions.create.call_args.kwargs[
            "messages"
        ][1]["content"]
        # The extractor-derived tech list should land in the prompt.
        assert "Python" in user_prompt
        assert "FastAPI" in user_prompt

    @pytest.mark.asyncio
    async def test_dev_mode_mocks_one_entry_per_extracted_tech(
        self, coach_in_dev_mode
    ) -> None:
        result = await coach_in_dev_mode.generate_technology_cheat_sheet(
            job_description=SAMPLE_JD,
        )
        assert len(result) > 0
        concepts = {entry["concept"] for entry in result}
        assert "Python" in concepts
        assert "FastAPI" in concepts


# ----------------------------------------------------------------------
# Full bundle
# ----------------------------------------------------------------------


class TestGenerateInterviewPrepMaterials:
    """End-to-end bundle generation."""

    @pytest.mark.asyncio
    async def test_missing_inputs_raise(self, coach_with_client) -> None:
        with pytest.raises(ValueError, match="required"):
            await coach_with_client.generate_interview_prep_materials(
                job_description="",
                job_title="Backend",
                company_name="TechCorp",
            )

    @pytest.mark.asyncio
    async def test_bundle_has_all_sections(self, coach_with_client) -> None:
        coach_with_client.client.chat.completions.create.side_effect = [
            _mock_openai_response(
                {
                    "technical_questions": [
                        {
                            "question": "q1",
                            "difficulty": "medium",
                            "topics": ["Python"],
                            "guidance": "Cover the core tradeoffs.",
                        }
                    ]
                }
            ),
            _mock_openai_response(
                {
                    "behavioral_questions": [
                        {
                            "question": "b1",
                            "scenario": "ownership",
                            "star_guidance": "Use STAR.",
                        }
                    ]
                }
            ),
            _mock_openai_response(
                {
                    "technology_cheat_sheet": [
                        {
                            "concept": "Python",
                            "definition": "Python is a high-level language used here.",
                        }
                    ]
                }
            ),
        ]

        result = await coach_with_client.generate_interview_prep_materials(
            job_description=SAMPLE_JD,
            job_title="Backend Engineer",
            company_name="TechCorp",
        )

        assert {
            "technical_questions",
            "behavioral_questions",
            "technology_cheat_sheet",
            "extracted_technologies",
            "jd_truncated",
            "jd_truncation_chars_dropped",
        } <= set(result.keys())
        assert coach_with_client.client.chat.completions.create.call_count == 3

    @pytest.mark.asyncio
    async def test_respects_default_counts(self, coach_with_client) -> None:
        coach_with_client.client.chat.completions.create.side_effect = [
            _mock_openai_response({"technical_questions": []}),
            _mock_openai_response({"behavioral_questions": []}),
            _mock_openai_response({"technology_cheat_sheet": []}),
        ]

        await coach_with_client.generate_interview_prep_materials(
            job_description=SAMPLE_JD,
            job_title="Backend Engineer",
            company_name="TechCorp",
        )

        # The technical prompt text should reference the default count (3).
        tech_prompt = coach_with_client.client.chat.completions.create.call_args_list[
            0
        ].kwargs["messages"][1]["content"]
        assert f"Generate {DEFAULT_TECHNICAL_COUNT} technical questions" in tech_prompt

        behav_prompt = coach_with_client.client.chat.completions.create.call_args_list[
            1
        ].kwargs["messages"][1]["content"]
        assert (
            f"Generate {DEFAULT_BEHAVIORAL_COUNT} behavioral questions" in behav_prompt
        )

    @pytest.mark.asyncio
    async def test_dev_mode_returns_full_bundle_without_api(
        self, coach_in_dev_mode
    ) -> None:
        # Regression guard: previously the agent crashed in dev mode because
        # company_research / cheat_sheet / strategy bypassed _make_api_call.
        result = await coach_in_dev_mode.generate_interview_prep_materials(
            job_description=SAMPLE_JD,
            job_title="Backend Engineer",
            company_name="TechCorp",
        )

        assert len(result["technical_questions"]) == DEFAULT_TECHNICAL_COUNT
        assert len(result["behavioral_questions"]) == DEFAULT_BEHAVIORAL_COUNT
        assert len(result["technology_cheat_sheet"]) > 0
        assert len(result["extracted_technologies"]) > 0


# ----------------------------------------------------------------------
# Error handling
# ----------------------------------------------------------------------


class TestErrorHandling:
    """API error pathways."""

    @pytest.mark.asyncio
    async def test_openai_error_bubbles_up(self, coach_with_client) -> None:
        coach_with_client.client.chat.completions.create.side_effect = Exception("boom")

        with pytest.raises(Exception, match="boom"):
            await coach_with_client.generate_technical_questions(
                job_description=SAMPLE_JD,
                job_title="Backend",
            )

    @pytest.mark.asyncio
    async def test_empty_response_raises(self, coach_with_client) -> None:
        response = Mock()
        response.choices = [Mock()]
        response.choices[0].message.content = None
        coach_with_client.client.chat.completions.create.return_value = response

        with pytest.raises(Exception, match="Empty response"):
            await coach_with_client.generate_technical_questions(
                job_description=SAMPLE_JD,
                job_title="Backend",
            )
