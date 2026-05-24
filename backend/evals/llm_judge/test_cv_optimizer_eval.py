"""LLM-judge eval for ``CVOptimizerAgent.optimize_cv_for_job``.

What's enforced (and where the bar is set):

    JSONSchemaMetric — actual_output must round-trip through OptimizedCV.
      Deterministic, threshold 1.0 from thresholds.yaml. Burns zero quota.

    NoFabricationGEval — custom criterion mirroring the agent's
      NO_FABRICATION system-prompt contract. Threshold strict (≥ 0.9)
      because the rule is contractually non-negotiable.

Quota budget:
    1 agent call + 1 NoFabrication judge call = **2 LLM calls per run**.
    HallucinationMetric was considered and intentionally dropped —
    NoFabricationGEval is a strictly stronger contract for this agent,
    so paying for both is redundant on a free-tier budget.

    Single parametrised case (strong-match pair) covers the happy path.
    Re-add partial/weak cases under ``llm_judge_paid_tier`` marker once
    quota allows.

Mark inheritance:
    Tagged ``@pytest.mark.eval`` + ``@pytest.mark.llm_judge`` by
    ``conftest.pytest_collection_modifyitems`` — no per-test markers.
"""

from __future__ import annotations

import json

import pytest

# DeepEval is installed on-demand in the ``evals-llm`` CI job only —
# see ``requirements-dev.txt`` for why. ``importorskip`` makes pytest
# collection survive on machines (and CI jobs) that don't have it.
pytest.importorskip("deepeval", reason="deepeval optional; install for LLM-judge layer")

from app.agents.cv_optimizer import CVOptimizerAgent
from app.schemas.cv_optimizer import OptimizedCV
from deepeval import assert_test
from deepeval.test_case import LLMTestCase

from evals.conftest import load_cv_fixture, load_jd_fixture, load_thresholds
from evals.llm_judge.judge import build_judge
from evals.llm_judge.metrics.json_schema_metric import JSONSchemaMetric
from evals.llm_judge.metrics.no_fabrication import NoFabricationGEval


# Single canonical strong-match case. Adding partial/weak parametrise
# entries would more than double quota burn (each case = 1 agent + 1
# judge = 2 calls). On free tier 20 RPD that's prohibitive when other
# eval files also need to run in the same CI invocation.
_CV_NAME = "mid_backend_python"
_JD_NAME = "senior_python_backend"


@pytest.mark.asyncio
async def test_optimize_cv_meets_no_fabrication_threshold(
    llm_judge_requires_real_key: None,
) -> None:
    cv = load_cv_fixture(_CV_NAME)
    jd = load_jd_fixture(_JD_NAME)
    thresholds = load_thresholds()["cv_optimizer"]

    # Run the real agent (single LLM call) — no mocks here.
    agent = CVOptimizerAgent()
    optimized = await agent.optimize_cv_for_job(
        parsed_cv=cv,
        job_description=jd,
        job_title=_JD_NAME.replace("_", " ").title(),
        company_name="EvalCo",
    )

    # DeepEval expects strings for ACTUAL_OUTPUT; serialise the dict.
    actual_output = json.dumps(optimized, ensure_ascii=False)

    test_case = LLMTestCase(
        input=jd,
        actual_output=actual_output,
        # Context is the source-of-truth CV — the judge compares
        # actual_output against this when scoring fabrication.
        context=[json.dumps(cv, ensure_ascii=False)],
    )

    judge = build_judge()

    # Schema gate first — if the output isn't valid JSON there's no
    # point burning judge quota on NoFabrication.
    schema_metric = JSONSchemaMetric(OptimizedCV, threshold=thresholds["json_schema_min"])
    no_fabrication = NoFabricationGEval(
        threshold=thresholds["no_fabrication_min"], model=judge
    )

    assert_test(test_case, [schema_metric, no_fabrication])
