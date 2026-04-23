"""
Tests for the Async Task Manager (Phase 7 — async agent execution).

Focuses on:
    * Submission lifecycle: PENDING → RUNNING → SUCCEEDED / FAILED.
    * SSE stream order and terminal event.
    * Ownership enforcement (User A can't read User B's task).
    * Worker exceptions become FAILED with error text, not crashes.
"""

from __future__ import annotations

import asyncio

import pytest

from app.services.task_manager import (
    AsyncTaskManager,
    TaskContext,
    TaskStatus,
    reset_task_manager_for_tests,
)


@pytest.fixture(autouse=True)
def _reset_manager():
    """Each test gets a fresh singleton."""
    reset_task_manager_for_tests()
    yield
    reset_task_manager_for_tests()


@pytest.fixture
def manager() -> AsyncTaskManager:
    return AsyncTaskManager()


async def _drain(stream):
    out = []
    async for event in stream:
        out.append(event)
    return out


class TestSubmissionLifecycle:
    @pytest.mark.asyncio
    async def test_success_path_reports_result(self, manager) -> None:
        async def worker(ctx: TaskContext) -> dict:
            await ctx.progress(0.5, message="half")
            return {"ok": True}

        task_id = await manager.submit(owner_user_id="u1", worker=worker)
        # Wait for the background task to finish.
        await asyncio.sleep(0.05)
        snapshot = await manager.get(task_id)
        assert snapshot is not None
        assert snapshot.status == TaskStatus.SUCCEEDED
        assert snapshot.progress == 1.0
        assert snapshot.result == {"ok": True}
        assert snapshot.error is None

    @pytest.mark.asyncio
    async def test_worker_exception_becomes_failed(self, manager) -> None:
        async def worker(ctx: TaskContext) -> dict:
            await ctx.progress(0.25)
            raise RuntimeError("boom")

        task_id = await manager.submit(owner_user_id="u1", worker=worker)
        await asyncio.sleep(0.05)
        snapshot = await manager.get(task_id)
        assert snapshot.status == TaskStatus.FAILED
        assert "boom" in snapshot.error
        assert snapshot.result is None

    @pytest.mark.asyncio
    async def test_missing_task_returns_none(self, manager) -> None:
        assert await manager.get("does-not-exist") is None

    @pytest.mark.asyncio
    async def test_progress_clamped_to_unit_interval(self, manager) -> None:
        async def worker(ctx: TaskContext) -> int:
            await ctx.progress(-5)
            await ctx.progress(99)
            return 0

        task_id = await manager.submit(owner_user_id="u1", worker=worker)
        await asyncio.sleep(0.05)
        snapshot = await manager.get(task_id)
        assert 0.0 <= snapshot.progress <= 1.0


class TestStreamEvents:
    @pytest.mark.asyncio
    async def test_sse_stream_yields_ordered_events(self, manager) -> None:
        async def worker(ctx: TaskContext) -> str:
            await ctx.progress(0.3, message="first")
            await ctx.progress(0.6, message="second")
            return "done"

        task_id = await manager.submit(owner_user_id="u1", worker=worker)
        events = await _drain(manager.stream_events(task_id, owner_user_id="u1"))

        # First event is the replay of current state (at minimum)
        statuses = [e.status for e in events]
        assert statuses[-1] == TaskStatus.SUCCEEDED
        progresses = [e.progress for e in events]
        assert progresses[-1] == 1.0
        # The success event carries the final result
        assert events[-1].result == "done"

    @pytest.mark.asyncio
    async def test_stream_closes_on_failure(self, manager) -> None:
        async def worker(ctx: TaskContext) -> str:
            raise ValueError("nope")

        task_id = await manager.submit(owner_user_id="u1", worker=worker)
        events = await _drain(manager.stream_events(task_id, owner_user_id="u1"))
        assert events[-1].status == TaskStatus.FAILED
        assert "nope" in events[-1].error

    @pytest.mark.asyncio
    async def test_wrong_owner_gets_empty_stream(self, manager) -> None:
        async def worker(ctx: TaskContext) -> int:
            return 42

        task_id = await manager.submit(owner_user_id="u1", worker=worker)
        # Other user should see nothing.
        events = await _drain(manager.stream_events(task_id, owner_user_id="u2"))
        assert events == []


class TestSingleton:
    def test_reset_helper_drops_instance(self) -> None:
        from app.services.task_manager import get_task_manager, reset_task_manager_for_tests

        reset_task_manager_for_tests()
        first = get_task_manager()
        reset_task_manager_for_tests()
        second = get_task_manager()
        assert first is not second
