"""Gemini-backed LLM judge for DeepEval metrics.

DeepEval ships first-party support for OpenAI, Anthropic, etc. — but it
expects judges to live behind its own ``DeepEvalBaseLLM`` adapter. We
wrap Gemini Flash here using the existing OpenAI-compatible endpoint
the application already uses, so the judge talks to the same provider
as the agents under test.

Same-family-judge caveat (documented in README + agent-evals-strategy):
    Using Gemini Flash for both the agent-under-test AND the judge has
    a known weakness — the judge shares the model's blind spots and
    may rubber-stamp outputs an independent judge would reject. We
    accept this tradeoff for free-tier reasons. The deterministic
    metrics (schema conformance, keyword coverage, fabrication token
    set) are the authoritative bar; the LLM judge is secondary signal.

Quota awareness:
    The user's free tier permits 5 RPM / 20 RPD on gemini-2.5-flash.
    The judge pins to that single model (no model_fallback chain) and
    relies on DeepEval's own internal request deduplication to keep
    call counts bounded. CI gates LLM evals to main + manual dispatch
    so we don't exhaust quota on every PR.
"""

from __future__ import annotations

import logging
from typing import Any

from app.config import get_settings


logger = logging.getLogger(__name__)


def _build_async_client() -> Any:
    """Construct the AsyncOpenAI client pointed at Gemini.

    Returns ``None`` if no real API key is configured — caller is
    responsible for handling that (the ``conftest.llm_judge_requires_real_key``
    fixture pytest-skips tests early in that case).
    """
    settings = get_settings()
    api_key = settings.openai_api_key
    if not api_key or api_key.startswith("test-") or "dummy" in api_key:
        return None

    from openai import AsyncOpenAI

    return AsyncOpenAI(
        api_key=api_key,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    )


class GeminiJudge:
    """``DeepEvalBaseLLM``-compatible judge backed by Gemini Flash.

    Implements the four hooks DeepEval calls:
        * ``load_model()`` — return the underlying client.
        * ``generate(prompt)`` — sync wrapper (DeepEval falls back to
          this when no event loop is available).
        * ``a_generate(prompt)`` — async path (preferred by DeepEval).
        * ``get_model_name()`` — string ID for logging + reports.

    Pinned to ``gemini-2.5-flash`` deliberately — using the model
    fallback chain on the judge would mean different evals get judged
    by different models, making score comparison meaningless across
    runs.
    """

    MODEL_NAME = "gemini-2.5-flash"

    def __init__(self) -> None:
        self._client = _build_async_client()
        if self._client is None:
            logger.warning(
                "GeminiJudge constructed without a real API key. "
                "Calls will fail; tests using this judge should be skipped "
                "via the ``llm_judge_requires_real_key`` fixture."
            )

    # ------------------------------------------------------------------
    # DeepEvalBaseLLM-compatible hooks
    # ------------------------------------------------------------------

    def load_model(self) -> Any:
        return self._client

    def get_model_name(self) -> str:
        return self.MODEL_NAME

    def generate(self, prompt: str, schema: type | None = None, **_: Any) -> str:
        """Synchronous generate — bridges async client via ``asyncio.run``.

        DeepEval calls this when invoked from outside an event loop
        (e.g. plain pytest sync tests). The pytest-asyncio context
        usually routes through ``a_generate`` instead.
        """
        import asyncio

        return asyncio.run(self.a_generate(prompt, schema=schema))

    async def a_generate(self, prompt: str, schema: type | None = None, **_: Any) -> str:
        """Async generate — what DeepEval prefers for pytest-asyncio runs."""
        if self._client is None:
            raise RuntimeError(
                "GeminiJudge has no real client — set OPENAI_API_KEY to a "
                "real Gemini key before invoking LLM-judge evals."
            )

        response = await self._client.chat.completions.create(
            model=self.MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            # DeepEval judges expect deterministic-ish output; the
            # metric scoring code re-parses the response into a JSON
            # verdict + reason. Low temperature keeps that stable.
            temperature=0.0,
            # Cap output — judge prompts produce short structured
            # verdicts (score 0-1 + 1-2 sentences of reasoning).
            max_tokens=512,
        )
        content = response.choices[0].message.content or ""
        return content


def build_judge() -> GeminiJudge:
    """Single entry point used by tests + metric constructors."""
    return GeminiJudge()
