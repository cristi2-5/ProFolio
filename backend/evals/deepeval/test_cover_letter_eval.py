"""LLM-judge eval for ``CVOptimizerAgent.generate_cover_letter``.

Separate file from ``test_cv_optimizer_eval.py`` because:
    * Different output shape (free-text vs JSON).
    * Different metrics (personalization vs fabrication + schema).
    * Different acceptance bar.

What's enforced:

    Length guard (deterministic) — under 200 chars = template skeleton;
      over 3000 chars = LLM ramble. Both fail the application use case.
      Burns zero quota.

    Placeholder leak guard (deterministic) — explicit string checks for
      ``[Your Name]``, ``[Candidate's Phone Number]``, etc. Calibration
      run 0 surfaced these so we pin against regression.

    NotGenericGEval — our custom criterion. Catches the harder property:
      the letter ties a CV achievement to a JD requirement.
      AnswerRelevancyMetric was considered and dropped — NotGeneric
      captures a strictly stronger property for this agent, so paying
      for both is redundant on a free-tier budget.

Quota budget:
    1 agent call + 1 NotGeneric judge call = **2 LLM calls per run**.
"""

from __future__ import annotations

import pytest

from app.agents.cv_optimizer import CVOptimizerAgent
from deepeval import assert_test
from deepeval.test_case import LLMTestCase

from evals.conftest import load_cv_fixture, load_jd_fixture, load_thresholds
from evals.deepeval.judge import build_judge
from evals.deepeval.metrics.no_fabrication import NotGenericGEval


_CV_NAME = "mid_backend_python"
_JD_NAME = "senior_python_backend"

# Cover letters render in 3-4 paragraphs of ~250-400 words. The bounds
# below catch template skeletons (everything-is-a-placeholder, <200 chars)
# and unbounded LLM rambles (>3000 chars).
MIN_LETTER_CHARS = 200
MAX_LETTER_CHARS = 3000


@pytest.mark.asyncio
async def test_cover_letter_meets_not_generic_threshold(
    llm_judge_requires_real_key: None,
) -> None:
    cv = load_cv_fixture(_CV_NAME)
    jd = load_jd_fixture(_JD_NAME)
    thresholds = load_thresholds()["cover_letter"]

    agent = CVOptimizerAgent()
    letter = await agent.generate_cover_letter(
        parsed_cv=cv,
        job_description=jd,
        job_title=_JD_NAME.replace("_", " ").title(),
        company_name="EvalCo",
        user_name=cv.get("full_name") or "Applicant",
    )

    # Deterministic length guard — catches the worst failure modes
    # without burning a judge call.
    assert MIN_LETTER_CHARS <= len(letter) <= MAX_LETTER_CHARS, (
        f"Cover letter length {len(letter)} outside reasonable bounds "
        f"[{MIN_LETTER_CHARS}, {MAX_LETTER_CHARS}]."
    )

    # No template placeholders. Calibration run 0 surfaced ``[Your Name]``
    # and ``[Candidate's Phone Number]`` style stubs — that's an
    # immediate fail regardless of judge score.
    forbidden_placeholders = [
        "[Your Name]",
        "[Your Address]",
        "[Your Phone Number]",
        "[Your Email]",
        "[Candidate's",
        "[Date]",
        "[Company Address",
    ]
    leaked = [p for p in forbidden_placeholders if p in letter]
    assert not leaked, f"Cover letter leaked template placeholders: {leaked}"

    test_case = LLMTestCase(
        input=jd,
        actual_output=letter,
        context=[
            f"Candidate: {cv.get('full_name')}",
            f"Experience: {cv.get('experience')}",
            f"Skills: {cv.get('skills')} + {cv.get('technologies')}",
        ],
    )

    judge = build_judge()
    not_generic = NotGenericGEval(
        threshold=thresholds["not_generic_min"], model=judge
    )

    assert_test(test_case, [not_generic])
