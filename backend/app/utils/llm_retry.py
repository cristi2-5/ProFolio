"""
LLM retry helper — small wrapper for transient upstream failures.

Maps OpenAI SDK exceptions to our domain exceptions so routers can
return the right HTTP status without each agent re-implementing the
classification.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable

from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    NotFoundError,
    RateLimitError,
)

from app.utils.exceptions import (
    LLMConfigurationError,
    LLMRateLimitError,
    LLMUnavailableError,
)

logger = logging.getLogger(__name__)

# Exponential backoff schedule (seconds) — paired with max_retries=2,
# we attempt: t=0, t+1s, t+4s.
_BACKOFF_SCHEDULE = (1.0, 4.0)

# Model fallback chain — tried in order on RateLimitError or NotFoundError.
# Primary:  gemini-2.5-flash       (best quality, fresh free-tier quota)
# Fallback: gemini-2.0-flash       (stable, separate quota bucket)
# Final:    gemini-1.5-flash       (older but still active, separate quota again)
# Each entry has its own daily quota on the free tier, so chaining across
# versions extends the effective request budget.
GEMINI_FLASH_MODELS: tuple[str, ...] = (
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
)


async def with_retry(
    coro_factory: Callable[[], Awaitable[Any]], max_retries: int = 2
) -> Any:
    """Call an async LLM coroutine factory with retry on transient errors.

    ``coro_factory`` must be a zero-arg callable that returns a fresh
    coroutine on each call — coroutines are single-use, so we can't
    accept the awaitable directly.

    Maps SDK exceptions to domain errors:
        - ``RateLimitError``        → retry, then ``LLMRateLimitError``
        - ``APITimeoutError``       → retry, then ``LLMUnavailableError``
        - ``APIConnectionError``    → retry, then ``LLMUnavailableError``
        - ``AuthenticationError``   → no retry, ``LLMConfigurationError`` (logged CRITICAL)
        - ``BadRequestError``       → no retry, re-raised
    """
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return await coro_factory()
        except AuthenticationError as exc:
            logger.critical(
                "LLM authentication failed — bad or revoked API key: %s", exc
            )
            raise LLMConfigurationError() from exc
        except BadRequestError:
            raise
        except RateLimitError as exc:
            last_exc = exc
            if attempt >= max_retries:
                logger.warning(
                    "LLM rate limit exhausted after %d retries: %s",
                    max_retries,
                    exc,
                )
                raise LLMRateLimitError() from exc
            delay = _BACKOFF_SCHEDULE[min(attempt, len(_BACKOFF_SCHEDULE) - 1)]
            logger.warning(
                "LLM rate limited (attempt %d/%d); sleeping %.1fs",
                attempt + 1,
                max_retries + 1,
                delay,
            )
            await asyncio.sleep(delay)
        except (APITimeoutError, APIConnectionError) as exc:
            last_exc = exc
            if attempt >= max_retries:
                logger.warning(
                    "LLM transport failure after %d retries: %s",
                    max_retries,
                    exc,
                )
                raise LLMUnavailableError() from exc
            delay = _BACKOFF_SCHEDULE[min(attempt, len(_BACKOFF_SCHEDULE) - 1)]
            logger.warning(
                "LLM transport error (attempt %d/%d); sleeping %.1fs: %s",
                attempt + 1,
                max_retries + 1,
                delay,
                exc,
            )
            await asyncio.sleep(delay)

    # Defensive — loop always either returns or raises.
    raise LLMUnavailableError() from last_exc


async def with_model_fallback(
    coro_factory: Callable[[str], Awaitable[Any]],
    models: tuple[str, ...] = GEMINI_FLASH_MODELS,
) -> tuple[Any, str]:
    """Call ``coro_factory(model)`` trying each model in ``models`` in order.

    On ``RateLimitError`` (or ``LLMRateLimitError`` bubbled from ``with_retry``),
    logs a warning and moves to the next model without waiting. All other errors
    propagate immediately from whichever model raised them.

    Args:
        coro_factory: Async callable that accepts a model name string and
            returns a coroutine. Called fresh for each attempt.
        models: Ordered tuple of model names to try.

    Returns:
        Tuple of (result, model_name_used).

    Raises:
        LLMRateLimitError: If every model in the chain is rate-limited.
        Any other exception raised by ``coro_factory``.
    """
    last_exc: Exception | None = None
    for model in models:
        try:
            result = await with_retry(lambda m=model: coro_factory(m))
            return result, model
        except LLMRateLimitError as exc:
            last_exc = exc
            logger.warning("Model %s rate-limited; trying next in chain", model)
        except RateLimitError as exc:
            last_exc = exc
            logger.warning("Model %s rate-limited (raw); trying next in chain", model)
        except NotFoundError as exc:
            last_exc = exc
            logger.warning("Model %s not found; trying next in chain", model)

    logger.error("All models in fallback chain exhausted: %s", models)
    raise LLMRateLimitError(
        f"All models exhausted ({', '.join(models)}). Try again later."
    ) from last_exc
