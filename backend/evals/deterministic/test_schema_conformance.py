"""Schema conformance — every agent returns output matching its Pydantic schema.

This is a deterministic eval: it exercises the agents in mock mode
(``OPENAI_API_KEY=test-*``) so no real LLM is called, and asserts that
the canned mock responses still round-trip cleanly through the agents'
declared output schemas.

Why this matters:
    The agents' mock responses are hand-crafted in code. If the agent's
    schema evolves (e.g. a new required field on ``ParsedCVData``) but
    the mock isn't updated, every downstream test that uses the mock
    silently passes but ships broken contracts. This test catches that
    drift on every PR.

Failure mode:
    ``ValidationError`` from Pydantic. The test surfaces the exact field
    that drifted so the author can update either the schema or the mock.
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from app.agents.cv_optimizer import CVOptimizerAgent
from app.agents.cv_profiler import CVProfilerAgent, ParsedCVData
from app.schemas.cv_optimizer import OptimizedCV


pytestmark = pytest.mark.eval


# ----------------------------------------------------------------------
# CV Profiler — mock CV parse
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cv_profiler_mock_response_matches_schema(tmp_path) -> None:
    """Mock CV-profiler output round-trips through ``ParsedCVData``.

    We bypass the real PDF extraction by constructing a tiny on-disk PDF
    via the existing reportlab pattern (same generator used in
    ``tests/test_cv_profiler_edge_cases.py``) and rely on the agent's
    ``test-`` key short-circuit to return the canned mock.
    """
    pytest.importorskip("reportlab")
    from reportlab.pdfgen import canvas

    pdf_path = tmp_path / "schema_probe.pdf"
    c = canvas.Canvas(str(pdf_path))
    c.drawString(72, 720, "John Doe — Software Engineer")
    c.showPage()
    c.save()

    agent = CVProfilerAgent()
    # When ``openai_client`` is None (mock mode) the agent returns its
    # canned Pydantic ``ParsedCVData`` mock. We assert the dict shape
    # validates against the public schema unmodified.
    parsed = await agent.parse(str(pdf_path), "schema_probe.pdf")

    # Round-trip — raises ValidationError on schema drift.
    ParsedCVData.model_validate(parsed)


# ----------------------------------------------------------------------
# CV Optimizer — mock optimize_cv_for_job
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cv_optimizer_mock_response_matches_schema() -> None:
    """Mock optimizer output round-trips through ``OptimizedCV``.

    Forces dev-mode on the constructed agent regardless of env config —
    we want to validate the **canned mock contract**, not the real LLM.
    The mock is what ships when ``OPENAI_API_KEY=test-...`` is set;
    if it drifts away from the public schema, downstream tests built on
    mock mode (and the dev experience itself) silently break.
    """
    agent = CVOptimizerAgent()
    agent.is_development = True
    agent.client = None

    sample_cv = {
        "summary": "Backend engineer with 4 years building Python services.",
        "experience": [
            {
                "company": "Acme",
                "role": "Backend Engineer",
                "duration": "2020-2024",
                "description": "Owned the order-processing API.",
            }
        ],
        "skills": ["Python", "PostgreSQL", "FastAPI"],
    }

    optimized = await agent.optimize_cv_for_job(
        parsed_cv=sample_cv,
        job_description="We need a Senior Python developer fluent in FastAPI.",
        job_title="Senior Python Developer",
        company_name="TestCorp",
    )

    # The agent always passes its raw response through ``OptimizedCV(**...).model_dump()``,
    # so re-validating here is a tight contract — fails loudly if the
    # mock and the schema drift apart.
    OptimizedCV.model_validate(optimized)

    # changes_summary is mandatory in the NO_FABRICATION contract. The
    # mock should keep this populated or downstream UI breaks silently.
    assert isinstance(optimized.get("changes_summary"), list)


# ----------------------------------------------------------------------
# CV Optimizer — mock cover letter
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cv_optimizer_mock_cover_letter_shape() -> None:
    """Mock cover letter is a non-trivial string we can sanity-check."""
    agent = CVOptimizerAgent()
    agent.is_development = True
    agent.client = None

    cover_letter = await agent.generate_cover_letter(
        parsed_cv={
            "personal_info": {"full_name": "Ana Popescu"},
            "experience": [
                {
                    "role": "Senior Engineer",
                    "company": "Acme",
                    "description": "x" * 60,
                }
            ],
            "skills": ["Python", "FastAPI"],
        },
        job_description="We're hiring a Senior Engineer fluent in Python.",
        job_title="Senior Engineer",
        company_name="TargetCo",
        user_name="Ana Popescu",
    )

    # The agent's own runtime guard enforces >=200 chars. We re-assert
    # so that if someone shortens the mock and bypasses the runtime path
    # via dev-mode, the schema-conformance gate still catches it.
    assert isinstance(cover_letter, str)
    assert len(cover_letter) >= 200, "Mock cover letter too short — UI assumes paragraphs."
    # Cover letters render in the UI as paragraphs split on double-newlines.
    # If the mock collapses them we want to know before integration.
    assert "\n" in cover_letter, "Mock cover letter must contain newlines."


# ----------------------------------------------------------------------
# Drift detector — Pydantic JSON-schema fingerprint
# ----------------------------------------------------------------------


def test_optimized_cv_schema_fingerprint_is_recorded() -> None:
    """Loud failure when ``OptimizedCV`` fields evolve without an explicit fixture update.

    Fingerprint = the set of top-level property keys. Adding/removing
    fields changes the fingerprint; the test then forces the author to
    update fixtures and thresholds rather than letting evals silently
    re-pass against stale data.

    To update: read the assertion error, copy the new ``actual`` value
    into ``expected`` below, and commit alongside the fixture changes.
    """
    expected = {
        "summary",
        "experience",
        "skills",
        "education",
        "optimized_keywords",
        "changes_summary",
        "potential_fabrications",
    }
    actual = set(OptimizedCV.model_json_schema()["properties"].keys())
    missing = expected - actual
    new_fields = actual - expected
    assert not missing and not new_fields, (
        "OptimizedCV schema changed. Update evals fixtures and re-record "
        f"this fingerprint.\n  missing: {sorted(missing)}\n  new: {sorted(new_fields)}"
    )


def test_parsed_cv_schema_fingerprint_is_recorded() -> None:
    """Same drift detector for ``ParsedCVData``."""
    expected = {
        "full_name",
        "email",
        "phone",
        "location",
        "summary",
        "skills",
        "technologies",
        "experience",
        "education",
        "certifications",
        "languages",
        "total_years_experience",
        "senior_technologies",
    }
    actual = set(ParsedCVData.model_json_schema()["properties"].keys())
    missing = expected - actual
    new_fields = actual - expected
    assert not missing and not new_fields, (
        "ParsedCVData schema changed. Update evals fixtures and re-record "
        f"this fingerprint.\n  missing: {sorted(missing)}\n  new: {sorted(new_fields)}"
    )


def test_validation_error_is_actionable_on_bad_input() -> None:
    """A schema validator that swallows ``ValidationError`` would mask drift.

    Confirms Pydantic still raises a typed exception when handed garbage —
    a guardrail against well-meaning future refactors that wrap the
    validator in a broad ``try/except``.
    """
    with pytest.raises(ValidationError):
        OptimizedCV.model_validate({"summary": 123, "experience": "not a list"})

    with pytest.raises((ValidationError, ValueError, TypeError)):
        ParsedCVData.model_validate(json.loads('{"skills": "not a list"}'))
