"""
Tests for the Prompt Cache utility (Phase 7 — cost/latency optimization).

Covers:
    * Key-derivation stability under reordering + temperature changes.
    * In-memory backend round-trip.
    * Cache disabled → GET always returns None, SET is a no-op.
    * Malformed serialization is treated as a miss, never crashes.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.utils.prompt_cache import (
    PromptCache,
    _InMemoryBackend,
    build_cache_key,
    get_prompt_cache,
    reset_prompt_cache_for_tests,
)


class TestBuildCacheKey:
    def test_identical_inputs_produce_identical_keys(self) -> None:
        a = build_cache_key(
            model="gpt-4o-mini",
            system_prompt="sys",
            user_prompt="user",
            response_format="json_object",
            temperature=0.4,
        )
        b = build_cache_key(
            model="gpt-4o-mini",
            system_prompt="sys",
            user_prompt="user",
            response_format="json_object",
            temperature=0.4,
        )
        assert a == b

    def test_temperature_changes_break_the_key(self) -> None:
        common = dict(
            model="gpt-4o-mini",
            system_prompt="sys",
            user_prompt="user",
            response_format="json_object",
        )
        assert build_cache_key(**common, temperature=0.4) != build_cache_key(
            **common, temperature=0.6
        )

    def test_namespace_is_included(self) -> None:
        key = build_cache_key(model="x", system_prompt="s", user_prompt="u")
        assert key.startswith("promptcache:")

    def test_different_prompts_yield_different_keys(self) -> None:
        a = build_cache_key(model="m", system_prompt="sys1", user_prompt="usr")
        b = build_cache_key(model="m", system_prompt="sys2", user_prompt="usr")
        assert a != b


class TestInMemoryBackendRoundTrip:
    @pytest.mark.asyncio
    async def test_set_then_get(self) -> None:
        cache = PromptCache(backend=_InMemoryBackend(), ttl_seconds=60, enabled=True)
        await cache.set("k1", {"hello": "world"})
        assert await cache.get("k1") == {"hello": "world"}

    @pytest.mark.asyncio
    async def test_missing_key_returns_none(self) -> None:
        cache = PromptCache(backend=_InMemoryBackend(), ttl_seconds=60, enabled=True)
        assert await cache.get("nothing") is None

    @pytest.mark.asyncio
    async def test_structured_payload_roundtrip(self) -> None:
        """Matches the agent's actual payload shape (list-in-dict)."""
        cache = PromptCache(backend=_InMemoryBackend(), ttl_seconds=60, enabled=True)
        payload = {
            "technical_questions": [
                {"question": "Q1", "difficulty": "medium", "topics": ["Python"]}
            ]
        }
        await cache.set("bundle", payload)
        assert await cache.get("bundle") == payload

    @pytest.mark.asyncio
    async def test_eviction_respects_max_entries(self) -> None:
        backend = _InMemoryBackend(max_entries=3)
        cache = PromptCache(backend=backend, ttl_seconds=60, enabled=True)
        for i in range(5):
            await cache.set(f"k{i}", {"i": i})
        # First two keys should have been evicted by LRU policy.
        assert await cache.get("k0") is None
        assert await cache.get("k1") is None
        assert await cache.get("k4") == {"i": 4}

    @pytest.mark.asyncio
    async def test_lru_touches_on_get(self) -> None:
        backend = _InMemoryBackend(max_entries=2)
        cache = PromptCache(backend=backend, ttl_seconds=60, enabled=True)
        await cache.set("k1", 1)
        await cache.set("k2", 2)
        # Touch k1 so k2 becomes the LRU victim.
        await cache.get("k1")
        await cache.set("k3", 3)
        assert await cache.get("k1") == 1
        assert await cache.get("k2") is None
        assert await cache.get("k3") == 3

    @pytest.mark.asyncio
    async def test_clear(self) -> None:
        cache = PromptCache(backend=_InMemoryBackend(), ttl_seconds=60, enabled=True)
        await cache.set("k1", 1)
        await cache.clear()
        assert await cache.get("k1") is None


class TestDisabledCache:
    @pytest.mark.asyncio
    async def test_disabled_cache_never_stores(self) -> None:
        cache = PromptCache(backend=_InMemoryBackend(), ttl_seconds=60, enabled=False)
        await cache.set("k1", 1)
        assert await cache.get("k1") is None


class TestMalformedData:
    @pytest.mark.asyncio
    async def test_non_json_backend_value_becomes_miss(self) -> None:
        class BogusBackend:
            async def get(self, key):
                return "not json {"

            async def set(self, *args, **kwargs):
                pass

            async def clear(self):
                pass

        cache = PromptCache(backend=BogusBackend(), ttl_seconds=60, enabled=True)
        assert await cache.get("anything") is None

    @pytest.mark.asyncio
    async def test_unserializable_value_set_is_skipped(self) -> None:
        cache = PromptCache(backend=_InMemoryBackend(), ttl_seconds=60, enabled=True)

        class Unserialisable:
            pass

        await cache.set("k1", Unserialisable())
        assert await cache.get("k1") is None


class TestGetPromptCache:
    def test_singleton_reset_works(self) -> None:
        reset_prompt_cache_for_tests()
        first = get_prompt_cache()
        second = get_prompt_cache()
        assert first is second
        reset_prompt_cache_for_tests()
        third = get_prompt_cache()
        assert third is not first
