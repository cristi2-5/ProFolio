"""LLM-judge eval for ``InterviewCoachAgent.generate_interview_prep_materials``.

**Currently skipped by default** — see SKIP_REASON.

The Interview Coach is the most expensive agent to evaluate: its
happy path fans out THREE LLM sub-calls (technical Qs, behavioral Qs,
cheat sheet) plus we'd add one judge call on top. At 4 calls per case,
even a single-case parametrise eats 20% of the daily free-tier budget,
crowding out the other three eval files.

The eval logic below is fully wired and ready to use — just remove the
``pytest.skip`` decorator below when on a paid Gemini tier (or when the
calibration plan budgets specifically for coach evals).

What's enforced (when not skipped):

    Deterministic structural checks (no judge call needed):
      * Exactly 3 technical Qs, 2 behavioral Qs.
      * Each technical Q has non-empty question + guidance.
      * Each behavioral Q has non-empty question + STAR/scenario.
      * Cheat sheet techs ⊆ extracted_technologies (deterministic
        extractor is the source of truth per architecture).

    FaithfulnessMetric (LLM judge) — technical Qs are grounded in the
      JD context.

Quota budget (when not skipped):
    3 agent sub-calls + 1 Faithfulness judge call = **4 LLM calls per
    parametrised case**. The single case below would burn 4 calls per
    run.
"""

from __future__ import annotations

import pytest

# DeepEval is installed on-demand in the ``evals-llm`` CI job only —
# see ``requirements-dev.txt`` for why. ``importorskip`` makes pytest
# collection survive on machines (and CI jobs) that don't have it.
pytest.importorskip("deepeval", reason="deepeval optional; install for LLM-judge layer")

from app.agents.interview_coach import InterviewCoachAgent
from deepeval import assert_test
from deepeval.metrics import FaithfulnessMetric
from deepeval.test_case import LLMTestCase

from evals.conftest import load_cv_fixture, load_jd_fixture, load_thresholds
from evals.llm_judge.judge import build_judge


SKIP_REASON = (
    "Interview Coach eval costs 4 LLM calls/case (3 agent sub-calls + 1 judge); "
    "skipping by default to keep the suite under the free-tier 20 RPD ceiling. "
    "Remove this skip when on paid Gemini tier or run manually via "
    "workflow_dispatch with a fresh daily quota."
)


_CV_NAME = "mid_backend_python"
_JD_NAME = "senior_python_backend"


@pytest.mark.skip(reason=SKIP_REASON)
@pytest.mark.asyncio
async def test_interview_coach_meets_thresholds(
    llm_judge_requires_real_key: None,
) -> None:
    cv = load_cv_fixture(_CV_NAME)
    jd = load_jd_fixture(_JD_NAME)
    thresholds = load_thresholds()["interview_coach"]

    agent = InterviewCoachAgent()
    bundle = await agent.generate_interview_prep_materials(
        job_description=jd,
        job_title=_JD_NAME.replace("_", " ").title(),
        company_name="EvalCo",
        user_background={
            "skills": (cv.get("skills") or []) + (cv.get("technologies") or []),
            "total_years_experience": cv.get("total_years_experience", 0),
        },
    )

    # ---- Deterministic structural assertions ------------------------
    tech_qs = bundle.get("technical_questions") or []
    beh_qs = bundle.get("behavioral_questions") or []
    cheat = bundle.get("technology_cheat_sheet") or []
    extracted = bundle.get("extracted_technologies") or []

    assert len(tech_qs) == 3, f"expected 3 technical Qs, got {len(tech_qs)}"
    assert len(beh_qs) == 2, f"expected 2 behavioral Qs, got {len(beh_qs)}"
    assert cheat, "cheat sheet must be non-empty"
    assert extracted, "extracted_technologies (deterministic) must be non-empty"

    for q in tech_qs:
        assert q.get("question"), f"technical Q missing 'question' field: {q}"
        assert q.get("guidance"), f"technical Q missing 'guidance' field: {q}"

    for q in beh_qs:
        assert q.get("question"), f"behavioral Q missing 'question' field: {q}"
        assert q.get("star_guidance") or q.get("scenario"), (
            f"behavioral Q missing STAR/scenario guidance: {q}"
        )

    extracted_lower = {t.lower() for t in extracted if isinstance(t, str)}
    for entry in cheat:
        concept = entry.get("concept") if isinstance(entry, dict) else None
        if not concept:
            continue
        assert concept.lower() in extracted_lower, (
            f"cheat sheet introduced '{concept}' not in extracted_technologies "
            f"({sorted(extracted_lower)})"
        )

    # ---- LLM-judge: technical Q guidance is grounded in JD ----------
    tech_text = "\n\n".join(
        f"Q: {q['question']}\nGuidance: {q['guidance']}" for q in tech_qs
    )

    test_case = LLMTestCase(
        input=jd,
        actual_output=tech_text,
        retrieval_context=[jd, ", ".join(extracted)],
    )

    judge = build_judge()
    faithfulness = FaithfulnessMetric(
        threshold=thresholds["faithfulness_min"], model=judge
    )

    assert_test(test_case, [faithfulness])
