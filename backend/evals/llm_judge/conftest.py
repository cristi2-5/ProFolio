"""DeepEval-specific conftest — rate-limit cooldown between tests.

Gemini Flash free tier enforces 5 RPM as a 60-second rolling window.
Each DeepEval test in this folder makes ~2 LLM calls (1 agent under
test + 1 judge), so 3 active tests back-to-back would pack 6 calls
into ~30 seconds — well over the 5 RPM ceiling.

Solution: a function-scoped autouse fixture that sleeps for
``INTER_TEST_COOLDOWN_S`` seconds AFTER each test, except the last.
With 30 s between tests + ~10 s of agent/judge time inside each test,
the rolling 60-second window stays below 5 LLM calls.

The cooldown is skipped when the API key is mock/dummy (we never hit
the real API in that case) so PR-time deterministic runs aren't
slowed down — only main-branch / workflow_dispatch `evals-llm` runs
pay the cooldown.
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import Iterator

import pytest


# 30 s between tests keeps a rolling 60-s window at ≤4 LLM calls when
# each test fires 2 sequential calls within ~10 s. Tightening this
# requires either fewer calls per test or a paid-tier quota bump.
INTER_TEST_COOLDOWN_S: float = 30.0


def _is_mock_key() -> bool:
    """Return True when the env API key would cause LLM tests to skip."""
    key = os.environ.get("OPENAI_API_KEY", "")
    return not key or key.startswith("test-") or "dummy" in key


@pytest.fixture(autouse=True)
def _llm_judge_cooldown(request: pytest.FixtureRequest) -> Iterator[None]:
    """Pause between consecutive LLM-judge tests to respect 5 RPM.

    Implemented as a per-test fixture rather than a hook so pytest's
    output keeps the "PASSED" line right after the test finishes —
    if we slept in ``pytest_runtest_teardown`` the user would see the
    PASS message lag by 30 s with no signal that the suite is still
    healthy.
    """
    yield  # let the test run first
    # Sleep AFTER the test so the next test's first call respects
    # the rolling window. Skip on mock keys + on the final test of a
    # session — pytest doesn't expose "is last" cheaply, so we just
    # eat one extra cooldown at session end (max 30 s wasted).
    if _is_mock_key():
        return
    # pytest-asyncio drives async tests on its own event loop; using
    # ``time.sleep`` here is correct because we're between tests, not
    # inside an asyncio coroutine.
    time.sleep(INTER_TEST_COOLDOWN_S)
