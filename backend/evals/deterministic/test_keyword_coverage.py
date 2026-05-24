"""Keyword coverage — JD-relevant terms appear in the optimized CV.

Deterministic eval, no LLM required. We monkeypatch the agent's API call
to return a hand-crafted ``OptimizedCV`` response that *claims* to have
integrated JD keywords. The test then asserts that the published metric
— intersection of normalised token sets — would actually pass for that
output. This catches regressions in the agent's post-processing layer
(``OptimizedCV(**parsed_json).model_dump()``, fabrication detector,
field shape) that could strip integrated keywords before they reach the
caller.

Why deterministic and not real-LLM:
    Phase 1 ships green CI without burning quota. The metric *itself* is
    deterministic — token-set intersection — so it's testable against
    any output shape. Phase 3 wires the same metric onto real Gemini
    output via DeepEval (``test_cv_optimizer_eval.py``).
"""

from __future__ import annotations

import re
from unittest.mock import AsyncMock, patch

import pytest

from app.agents.cv_optimizer import CVOptimizerAgent


pytestmark = pytest.mark.eval


# ----------------------------------------------------------------------
# Token extraction — shared with the real eval metric in Phase 3
# ----------------------------------------------------------------------


# Mirror the agent's own token regex from app.agents.cv_optimizer so the
# metric speaks the same dialect as production. We keep a copy here so
# the deterministic eval is self-contained and immune to ``cv_optimizer``
# internal refactors that rename private symbols.
_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9+.#\-]{2,}")


def _tokens(text: str) -> set[str]:
    """Normalised, lowercased token set."""
    return {m.group(0).lower() for m in _TOKEN_RE.finditer(text or "")}


def _flatten_optimized_cv(optimized: dict) -> str:
    """Concatenate summary + experience descriptions + skills + keywords."""
    parts: list[str] = []
    if isinstance(optimized.get("summary"), str):
        parts.append(optimized["summary"])
    for exp in optimized.get("experience") or []:
        if isinstance(exp, dict):
            for key in ("role", "description"):
                value = exp.get(key)
                if isinstance(value, str):
                    parts.append(value)
    for key in ("skills", "optimized_keywords"):
        for item in optimized.get(key) or []:
            if isinstance(item, str):
                parts.append(item)
    return "\n".join(parts)


def keyword_coverage(optimized_cv: dict, jd_keywords: list[str]) -> float:
    """Fraction of ``jd_keywords`` (lowercased) present in the optimized CV."""
    flat = _tokens(_flatten_optimized_cv(optimized_cv))
    if not jd_keywords:
        return 1.0
    expected = {kw.lower() for kw in jd_keywords if kw}
    if not expected:
        return 1.0
    hit = expected & flat
    return len(hit) / len(expected)


# ----------------------------------------------------------------------
# Tests — coverage metric itself
# ----------------------------------------------------------------------


def test_coverage_metric_perfect_hit() -> None:
    optimized = {
        "summary": "Python backend developer building FastAPI services.",
        "experience": [],
        "skills": ["Python", "FastAPI", "PostgreSQL"],
        "optimized_keywords": ["Python", "FastAPI"],
    }
    assert keyword_coverage(optimized, ["Python", "FastAPI", "PostgreSQL"]) == 1.0


def test_coverage_metric_partial() -> None:
    optimized = {
        "summary": "Python developer.",
        "experience": [],
        "skills": ["Python"],
        "optimized_keywords": [],
    }
    score = keyword_coverage(optimized, ["Python", "Kubernetes", "Terraform"])
    assert 0.0 < score < 1.0
    assert pytest.approx(score, abs=1e-6) == 1 / 3


def test_coverage_metric_empty_keywords_does_not_divide_by_zero() -> None:
    assert keyword_coverage({"summary": "x"}, []) == 1.0
    assert keyword_coverage({"summary": "x"}, [""]) == 1.0


def test_coverage_metric_case_insensitive() -> None:
    optimized = {"summary": "PYTHON developer using fastapi"}
    assert keyword_coverage(optimized, ["python", "FastAPI"]) == 1.0


# ----------------------------------------------------------------------
# Integration — the agent's post-processing preserves JD keywords
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_agent_preserves_jd_keywords_through_post_processing() -> None:
    """Mock the LLM to claim keyword integration; assert it survives.

    Scenario: we hand the agent a sample CV + a JD whose keyword set is
    {"Python", "FastAPI", "PostgreSQL"}. The mocked LLM returns an
    ``OptimizedCV`` that integrates all three. We then check that after
    the agent's normal post-processing (Pydantic round-trip, fabrication
    scan, ``potential_fabrications`` list assembly), every keyword still
    appears in the published output.

    A regression here means the post-processor accidentally stripped
    integrated keywords — e.g. by lower-casing or by dropping fields.
    """
    agent = CVOptimizerAgent()

    # Force real (non-mock) code path so we exercise the validator,
    # fabrication scan, and post-processing — but stub the actual LLM
    # call so no network traffic happens.
    agent.is_development = False
    agent.client = object()  # truthy stub; never .called because we patch _make_api_call

    fake_llm_payload = {
        "summary": "Backend engineer with Python + FastAPI + PostgreSQL.",
        "experience": [
            {
                "company": "Acme",
                "role": "Backend Engineer",
                "duration": "2020-2024",
                "description": "Built Python/FastAPI services on PostgreSQL.",
            }
        ],
        "skills": ["Python", "FastAPI", "PostgreSQL"],
        "education": [],
        "optimized_keywords": ["Python", "FastAPI", "PostgreSQL"],
        "changes_summary": ["Surfaced Python+FastAPI from prior backend bullet."],
    }

    with patch.object(
        agent, "_make_api_call", new=AsyncMock(return_value=fake_llm_payload)
    ):
        optimized = await agent.optimize_cv_for_job(
            parsed_cv={
                "summary": "Backend engineer.",
                "experience": [
                    {
                        "company": "Acme",
                        "role": "Backend Engineer",
                        "duration": "2020-2024",
                        "description": "Built Python services.",
                    }
                ],
                "skills": ["Python", "FastAPI", "PostgreSQL"],
            },
            job_description="Senior role needing Python + FastAPI + PostgreSQL.",
            job_title="Senior Backend Engineer",
            company_name="TestCo",
        )

    # Every JD keyword must still be visible somewhere in the optimized CV.
    score = keyword_coverage(optimized, ["Python", "FastAPI", "PostgreSQL"])
    assert score == 1.0, f"keyword coverage degraded to {score:.2f} — fields stripped?"

    # Sanity: post-processing didn't drop ``changes_summary`` (NO_FABRICATION audit trail).
    assert optimized.get("changes_summary"), "changes_summary stripped — UI loses audit trail."
