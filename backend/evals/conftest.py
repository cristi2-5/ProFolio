"""Eval-suite conftest — session-level setup independent of ``tests/``.

Why this lives separately from ``backend/tests/conftest.py``:
    The tests conftest registers ``_reset_phase7_singletons`` as
    ``autouse=True``, which clears the prompt cache between *every* test.
    Evals need the opposite — a single session-level reset so within-run
    cache hits are preserved. Keeping conftest scopes separate avoids
    cross-suite autouse bleed.

Phase 1 surface:
    * Session-start guard for the LLM API key (skips suite on mock keys
      so deterministic evals stay honest in CI mock mode).
    * Fixture loaders for ``cvs/``, ``jds/``, and ``pairs.yaml``.
    * Cache reset at session start only.

Phase 3+ will extend this with a Gemini ``DeepEvalBaseLLM`` judge fixture.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterator

import pytest

# Allow ``import app...`` to resolve from this conftest's location.
# ``backend/`` is the package root; running ``pytest evals/`` from
# ``backend/`` already places it on sys.path, but the explicit env
# fallback keeps editor runners (PyCharm, VS Code) honest too.

EVALS_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = EVALS_DIR / "fixtures"
CVS_DIR = FIXTURES_DIR / "cvs"
JDS_DIR = FIXTURES_DIR / "jds"
PAIRS_FILE = FIXTURES_DIR / "pairs.yaml"
REPORTS_DIR = EVALS_DIR / "reports"
THRESHOLDS_FILE = EVALS_DIR / "thresholds.yaml"


# ----------------------------------------------------------------------
# Session-level setup
# ----------------------------------------------------------------------


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Auto-mark everything under ``llm_judge/`` as ``@pytest.mark.llm_judge``.

    Saves authors from having to remember the marker on every test in the
    DeepEval layer. Deterministic tests must opt in to ``eval`` explicitly
    so we don't accidentally include unrelated helpers in the suite.
    """
    deepeval_root = EVALS_DIR / "deepeval"
    for item in items:
        item_path = Path(str(item.fspath)).resolve()
        try:
            item_path.relative_to(deepeval_root)
        except ValueError:
            continue
        item.add_marker(pytest.mark.llm_judge)
        item.add_marker(pytest.mark.eval)


@pytest.fixture(scope="session", autouse=True)
def _reset_eval_singletons() -> Iterator[None]:
    """One-shot prompt-cache reset at the start of the eval session.

    Unlike ``tests/conftest.py:_reset_phase7_singletons`` (per-test), this
    fires exactly once. Within-run cache hits across multiple eval files
    are intentional — they keep judge calls deterministic across reruns.
    """
    from app.utils.prompt_cache import reset_prompt_cache_for_tests

    reset_prompt_cache_for_tests()
    yield
    reset_prompt_cache_for_tests()


@pytest.fixture(scope="session")
def llm_judge_requires_real_key() -> None:
    """Skip an individual ``llm_judge`` test when the API key is a mock.

    Deterministic tests are happy with the dummy/test-prefixed key the
    base CI sets. LLM-judge tests need a real key — they call Gemini.
    Tests opt in by listing this fixture as a dependency.
    """
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key or api_key.startswith("test-") or "dummy" in api_key:
        pytest.skip(
            "LLM-judge evals require a real OPENAI_API_KEY (Gemini). "
            "Set it locally with `export OPENAI_API_KEY=<real>` or add a "
            "GitHub repo secret for the evals-llm CI job."
        )


# ----------------------------------------------------------------------
# Fixture loaders
# ----------------------------------------------------------------------


def load_cv_fixture(name: str) -> dict:
    """Read one ``cvs/<name>.json`` parsed-resume fixture.

    Returns the dict shape consumed by every downstream agent (matches
    ``ParsedCVData``). Single source of truth — DeepEval and Promptfoo
    both load through here.
    """
    path = CVS_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"CV fixture not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_jd_fixture(name: str) -> str:
    """Read one ``jds/<name>.txt`` raw job description fixture."""
    path = JDS_DIR / f"{name}.txt"
    if not path.exists():
        raise FileNotFoundError(f"JD fixture not found: {path}")
    return path.read_text(encoding="utf-8")


def iter_pairs() -> list[dict]:
    """Yield canonical CV×JD pairings from ``pairs.yaml``.

    Returns a list (not a generator) so pytest's parametrize can use it.
    Falls back to an empty list when ``pairs.yaml`` is absent — Phase 1
    deterministic tests work without it; Phase 2 lands it.
    """
    if not PAIRS_FILE.exists():
        return []
    try:
        import yaml  # PyYAML ships with FastAPI / Alembic via transitive deps.
    except ImportError as exc:
        raise RuntimeError(
            "PyYAML missing — required to load pairs.yaml. Add it to "
            "requirements-dev.txt or install with `pip install pyyaml`."
        ) from exc
    raw = yaml.safe_load(PAIRS_FILE.read_text(encoding="utf-8")) or {}
    return raw.get("pairs", [])


# Cached once per session — ``thresholds.yaml`` is small and stable.
_THRESHOLDS_CACHE: dict | None = None


def load_thresholds() -> dict:
    """Read and cache ``thresholds.yaml``.

    Returns the parsed YAML as a dict. Phase 3 LLM-judge tests read
    per-agent pass thresholds from this file (e.g.
    ``load_thresholds()["cv_optimizer"]["hallucination_max"]``).

    Raises ``RuntimeError`` if the file is missing — Phase 3 tests
    cannot run without thresholds, and silently defaulting would hide
    a real misconfiguration.
    """
    global _THRESHOLDS_CACHE
    if _THRESHOLDS_CACHE is not None:
        return _THRESHOLDS_CACHE
    if not THRESHOLDS_FILE.exists():
        raise RuntimeError(
            "thresholds.yaml missing at " + str(THRESHOLDS_FILE) + ". "
            "Phase 3 LLM-judge tests require it. See evals/README.md "
            "for recalibration instructions."
        )
    import yaml

    parsed = yaml.safe_load(THRESHOLDS_FILE.read_text(encoding="utf-8")) or {}
    _THRESHOLDS_CACHE = parsed
    return parsed
