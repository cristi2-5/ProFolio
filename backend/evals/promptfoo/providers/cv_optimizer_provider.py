"""Promptfoo Python provider for the CV Optimizer agent.

Promptfoo calls this provider for each test case in the YAML config.
We use the **real production agent** rather than re-extracting prompts
into Jinja files (per Phase plan decision) so the eval exercises
exactly the code path that ships to users.

Why standalone fixture loaders (vs reusing ``evals/conftest.py``):
    The ``evals/conftest.py`` module imports pytest at module level —
    Promptfoo invokes Python providers outside any pytest session, so
    that import would crash. We duplicate ~10 lines of fixture loading
    here to keep the provider self-contained.

Promptfoo provider contract:
    ``def call_api(prompt, options, context) -> dict``
    Returns ``{"output": <str>}`` — the agent's optimized CV serialised
    as JSON. Promptfoo's downstream asserts (``is-json``, ``javascript``,
    ``llm-rubric``) operate on this string.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path


# Resolve ``backend/`` so ``from app.agents ...`` works regardless of
# where promptfoo is launched. ``__file__`` is at
# ``backend/evals/promptfoo/providers/cv_optimizer_provider.py``; four
# parents back lands us at ``backend/``.
_BACKEND_DIR = Path(__file__).resolve().parents[3]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))


# Fixture directories — mirrored from ``evals/conftest.py`` but
# without the pytest import.
_FIXTURES = _BACKEND_DIR / "evals" / "fixtures"
_CVS = _FIXTURES / "cvs"
_JDS = _FIXTURES / "jds"


def _load_cv(name: str) -> dict:
    path = _CVS / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jd(name: str) -> str:
    return (_JDS / f"{name}.txt").read_text(encoding="utf-8")


def call_api(prompt: str, options: dict, context: dict) -> dict:
    """Promptfoo entry point — invoked once per test case.

    Args:
        prompt: interpolated prompt template from the YAML
            ``prompts`` section. Acts as a human-readable marker; the
            real work uses ``context.vars`` instead.
        options: provider-level config from the YAML ``providers``
            section. Unused here; reserved for future temperature /
            model overrides.
        context: dict with ``vars`` carrying per-test-case inputs.
            Expected keys: ``cv_name``, ``jd_name``.

    Returns:
        ``{"output": <serialised optimized CV JSON>}`` on success.
        Promptfoo handles exceptions as test-case failures with the
        exception text rendered in the HTML report.
    """
    # Deferred imports — pulling the OpenAI SDK during Promptfoo's
    # module probe slows down config loading; do it lazily.
    from app.agents.cv_optimizer import CVOptimizerAgent

    vars_ = context.get("vars", {}) or {}
    cv_name = vars_.get("cv_name")
    jd_name = vars_.get("jd_name")
    if not cv_name or not jd_name:
        raise ValueError(
            "cv_optimizer_provider requires both `cv_name` and `jd_name` in "
            f"test-case vars; got {vars_!r}"
        )

    cv = _load_cv(cv_name)
    jd = _load_jd(jd_name)

    agent = CVOptimizerAgent()
    # The agent is async; Promptfoo's Python provider hook is sync, so
    # we drive the coroutine ourselves. ``asyncio.run`` per call is
    # acceptable — each test case is a one-shot anyway.
    optimized = asyncio.run(
        agent.optimize_cv_for_job(
            parsed_cv=cv,
            job_description=jd,
            job_title=jd_name.replace("_", " ").title(),
            company_name="EvalCo (Promptfoo)",
        )
    )

    return {"output": json.dumps(optimized, ensure_ascii=False)}
