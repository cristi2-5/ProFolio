"""
Prompt Cache — LLM response cache for cost/latency optimization.

Caches LLM responses keyed by a hash of the full request surface
(model + system prompt + user prompt + response_format + temperature).

Two backends, chosen at runtime:

    * Redis (preferred in production) — if ``settings.redis_url`` is
      configured AND the ``redis`` package is importable.
    * In-memory LRU — always available, per-process, bounded. Used
      automatically when Redis isn't configured.

The public surface is two async methods — ``get`` and ``set`` — so
agents don't need to know which backend is active.

Design notes:
    * Keys hash both prompts + model + format so temperature changes
      never serve stale responses from a different config.
    * Cached values are JSON-serialised; structured responses (dicts
      from ``response_format=json_object``) round-trip cleanly.
    * No exception from the cache layer should ever break the agent —
      every error is logged and the cache call acts as a miss.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Optional

from app.config import get_settings

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Key derivation
# ----------------------------------------------------------------------


def build_cache_key(
    *,
    model: str,
    system_prompt: str,
    user_prompt: str,
    response_format: Optional[str] = None,
    temperature: Optional[float] = None,
    namespace: str = "promptcache",
) -> str:
    """Derive a stable cache key from the request surface.

    SHA-256 gives a collision-resistant 64-char hex; prepending the
    namespace makes it easy to scan/flush a single cache family in
    Redis (``KEYS promptcache:*``).
    """
    payload = json.dumps(
        {
            "model": model,
            "system": system_prompt,
            "user": user_prompt,
            "format": response_format,
            "temperature": temperature,
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"{namespace}:{digest}"


# ----------------------------------------------------------------------
# Backends
# ----------------------------------------------------------------------


@dataclass
class _InMemoryBackend:
    """Bounded LRU cache for single-process fallback / tests."""

    max_entries: int = 1024
    _store: "OrderedDict[str, str]" = None  # type: ignore[assignment]
    _lock: asyncio.Lock = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self._store = OrderedDict()
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[str]:
        async with self._lock:
            if key not in self._store:
                return None
            self._store.move_to_end(key)
            return self._store[key]

    async def set(self, key: str, value: str, ttl_seconds: Optional[int]) -> None:
        # TTL is a no-op for the in-memory backend — bound by max_entries.
        # The interface accepts it so the Redis backend can honour it.
        async with self._lock:
            self._store[key] = value
            self._store.move_to_end(key)
            while len(self._store) > self.max_entries:
                self._store.popitem(last=False)

    async def clear(self) -> None:
        async with self._lock:
            self._store.clear()


class _RedisBackend:
    """Thin wrapper over ``redis.asyncio`` — only imported if configured."""

    def __init__(self, url: str):
        import redis.asyncio as redis_async  # lazy import: optional dep

        self._client = redis_async.from_url(url, decode_responses=True)

    async def get(self, key: str) -> Optional[str]:
        try:
            return await self._client.get(key)
        except Exception as exc:
            logger.warning("Redis GET failed — treating as cache miss: %s", exc)
            return None

    async def set(self, key: str, value: str, ttl_seconds: Optional[int]) -> None:
        try:
            if ttl_seconds and ttl_seconds > 0:
                await self._client.set(key, value, ex=ttl_seconds)
            else:
                await self._client.set(key, value)
        except Exception as exc:
            logger.warning("Redis SET failed — cache write skipped: %s", exc)

    async def clear(self) -> None:
        try:
            await self._client.flushdb()
        except Exception as exc:
            logger.warning("Redis FLUSHDB failed: %s", exc)


# ----------------------------------------------------------------------
# Public cache
# ----------------------------------------------------------------------


class PromptCache:
    """User-facing cache object shared by agents."""

    def __init__(
        self,
        *,
        backend: Any,
        ttl_seconds: int,
        enabled: bool,
    ):
        self._backend = backend
        self._ttl_seconds = ttl_seconds
        self._enabled = enabled

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def get(self, key: str) -> Optional[Any]:
        if not self._enabled:
            return None
        try:
            raw = await self._backend.get(key)
        except Exception as exc:
            logger.warning("Cache backend error during GET: %s", exc)
            return None
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (TypeError, json.JSONDecodeError) as exc:
            logger.warning("Failed to decode cached payload; treating as miss: %s", exc)
            return None

    async def set(self, key: str, value: Any) -> None:
        if not self._enabled:
            return
        try:
            serialised = json.dumps(value, ensure_ascii=False)
        except (TypeError, ValueError) as exc:
            logger.warning("Prompt cache value is not JSON-serialisable: %s", exc)
            return
        try:
            await self._backend.set(key, serialised, self._ttl_seconds)
        except Exception as exc:
            logger.warning("Cache backend error during SET: %s", exc)

    async def clear(self) -> None:
        try:
            await self._backend.clear()
        except Exception as exc:
            logger.warning("Cache backend error during CLEAR: %s", exc)


# ----------------------------------------------------------------------
# Factory / singleton
# ----------------------------------------------------------------------


_cache_singleton: Optional[PromptCache] = None


def get_prompt_cache() -> PromptCache:
    """Return the process-wide cache, instantiating it on first use."""
    global _cache_singleton
    if _cache_singleton is not None:
        return _cache_singleton

    settings = get_settings()
    ttl = settings.prompt_cache_ttl_seconds
    enabled = settings.prompt_cache_enabled

    backend: Any
    if enabled and getattr(settings, "redis_url", ""):
        try:
            backend = _RedisBackend(settings.redis_url)
            logger.info("Prompt cache: using Redis backend at %s", settings.redis_url)
        except Exception as exc:
            logger.warning(
                "Redis backend unavailable, falling back to in-memory cache: %s", exc
            )
            backend = _InMemoryBackend()
    else:
        backend = _InMemoryBackend()
        if enabled:
            logger.info("Prompt cache: using in-memory backend (no REDIS_URL set)")

    _cache_singleton = PromptCache(backend=backend, ttl_seconds=ttl, enabled=enabled)
    return _cache_singleton


def reset_prompt_cache_for_tests() -> None:
    """Drop the module-level singleton — test helper only."""
    global _cache_singleton
    _cache_singleton = None
