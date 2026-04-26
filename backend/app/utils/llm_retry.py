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
