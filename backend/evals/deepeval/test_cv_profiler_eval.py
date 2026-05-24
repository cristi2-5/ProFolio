"""LLM-judge eval for ``CVProfilerAgent.parse``.

The CV Profiler reads a PDF/DOCX file and emits structured JSON
matching ``ParsedCVData``. We generate a small reportlab-based PDF in
memory from ``fixtures/golden_pdfs.py``, run the agent, and gate the
parsed output on:

    Deterministic field-level checks (no judge needed):
      * Skill subset ≥ 80% — most expected skills should be detected.
      * total_years_experience within ±1 of expected.
      * At least the expected number of experiences extracted.

    JSONSchemaMetric — agent output round-trips through ParsedCVData.

    FaithfulnessMetric (LLM judge) — extracted fields are grounded in
      the PDF text (vs hallucinating extra companies / years).

Quota budget:
    1 agent call + 1 Faithfulness judge call = **2 LLM calls per run**.

    Single parametrised case keeps quota burn predictable. The
    devops_sre body in golden_pdfs.py is retained for paid-tier
    expansion.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.agents.cv_profiler import CVProfilerAgent, ParsedCVData
from deepeval import assert_test
from deepeval.metrics import FaithfulnessMetric
from deepeval.test_case import LLMTestCase

from evals.conftest import load_thresholds
from evals.deepeval.judge import build_judge
from evals.deepeval.metrics.json_schema_metric import JSONSchemaMetric
from evals.fixtures.golden_pdfs import (
    EXPECTED_FIELDS,
    GOLDEN_CV_BODIES,
    build_pdf,
)


_BODY_KEY = "python_backend"


@pytest.mark.asyncio
async def test_cv_profiler_parses_golden_pdf(
    tmp_path: Path,
    llm_judge_requires_real_key: None,
) -> None:
    body = GOLDEN_CV_BODIES[_BODY_KEY]
    expected = EXPECTED_FIELDS[_BODY_KEY]
    pdf_path = build_pdf(tmp_path, body=body, filename=f"{_BODY_KEY}.pdf")

    thresholds = load_thresholds()["cv_profiler"]

    agent = CVProfilerAgent()
    parsed = await agent.parse(str(pdf_path), f"{_BODY_KEY}.pdf")

    # ---- Deterministic field-level checks ---------------------------
    parsed_skills = {s.lower() for s in (parsed.get("skills") or [])}
    parsed_techs = {t.lower() for t in (parsed.get("technologies") or [])}
    detected = parsed_skills | parsed_techs

    expected_skills_lower = {s.lower() for s in expected["skill_subset"]}
    hit = expected_skills_lower & detected
    coverage = len(hit) / len(expected_skills_lower)
    assert coverage >= 0.80, (
        f"Only {coverage:.0%} of expected skills detected. "
        f"Expected (lower) {expected_skills_lower}, got skills={parsed_skills}, techs={parsed_techs}"
    )

    years_min, years_max = expected["years_range"]
    years = int(parsed.get("total_years_experience") or 0)
    assert years_min <= years <= years_max, (
        f"total_years_experience={years} outside expected band [{years_min}, {years_max}]"
    )

    exp_count = len(parsed.get("experience") or [])
    assert exp_count >= expected["min_experiences"], (
        f"expected ≥{expected['min_experiences']} experiences, got {exp_count}"
    )

    # ---- LLM-judge: faithfulness to the source PDF text -------------
    test_case = LLMTestCase(
        input=f"Parse this CV: {_BODY_KEY}",
        actual_output=json.dumps(parsed, ensure_ascii=False),
        # Retrieval context is the source PDF body — judge asserts
        # that every extracted field appears in (or is directly
        # implied by) the source text.
        retrieval_context=[body],
    )

    judge = build_judge()

    # Schema gate first — if it doesn't validate, we skip the judge.
    schema_metric = JSONSchemaMetric(ParsedCVData, threshold=thresholds["json_schema_min"])
    faithfulness = FaithfulnessMetric(threshold=thresholds["faithfulness_min"], model=judge)

    assert_test(test_case, [schema_metric, faithfulness])
