"""
Task Manager — async agent execution with SSE progress updates.

Lets the frontend fire an agent in the background and stream progress
updates over Server-Sent Events (SSE) instead of holding an HTTP
connection open for 10+ seconds.

Storage is in-process: a single ``AsyncTaskManager`` instance holds a
dict of live tasks keyed by UUID. Each task carries:

    * ``status`` — one of pending / running / succeeded / failed
    * ``progress`` — 0.0-1.0
    * ``result`` — whatever the worker coroutine returned (on success)
    * ``error`` — stringified exception (on failure)
    * an ``asyncio.Queue`` that publishes events for SSE subscribers

The choice of in-process storage is intentional: the platform runs a
single uvicorn worker today, and the SSE contract only requires
delivering events to the user who launched the task (same process).
Swapping to Redis Streams + pubsub is a two-file change when the
deployment needs multiple workers.

Finished tasks are garbage-collected after ``RESULT_TTL_SECONDS`` so the
dict never grows unbounded even if clients forget to fetch results.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Awaitable, Callable, Dict, Optional

logger = logging.getLogger(__name__)

RESULT_TTL_SECONDS = 30 * 60  # 30 minutes — plenty for a user to fetch
_EVENT_SENTINEL_TERMINAL = "__terminal__"


class TaskStatus(str, Enum):
    """Lifecycle states for a managed async task."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass
class TaskEvent:
    """Single progress event — pushed onto the per-task queue."""

    status: TaskStatus
    progress: float
    message: Optional[str] = None
    result: Any = None
    error: Optional[str] = None

    def to_payload(self) -> Dict[str, Any]:
        """Serializable payload for SSE wire format."""
        payload: Dict[str, Any] = {
            "status": self.status.value,
            "progress": round(self.progress, 3),
        }
        if self.message is not None:
            payload["message"] = self.message
        if self.result is not None:
            payload["result"] = self.result
        if self.error is not None:
            payload["error"] = self.error
        return payload


@dataclass
class _TaskRecord:
    """Mutable state for one managed task."""

    task_id: str
    owner_user_id: str
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0
    result: Any = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    finished_at: Optional[float] = None
    events: asyncio.Queue = field(default_factory=asyncio.Queue)
    handle: Optional[asyncio.Task] = None


@dataclass
class TaskProgress:
    """Public snapshot returned to polling clients (GET /api/tasks/{id})."""

    task_id: str
    status: TaskStatus
    progress: float
    result: Any
    error: Optional[str]
    owner_user_id: str


class AsyncTaskManager:
    """Process-wide registry of async tasks with SSE streaming."""

    def __init__(self, *, result_ttl_seconds: int = RESULT_TTL_SECONDS) -> None:
        self._records: Dict[str, _TaskRecord] = {}
        self._lock = asyncio.Lock()
        self._result_ttl = result_ttl_seconds

    # ------------------------------------------------------------------
    # Submission / lifecycle
    # ------------------------------------------------------------------

    async def submit(
        self,
        *,
        owner_user_id: str,
        worker: Callable[["TaskContext"], Awaitable[Any]],
    ) -> str:
        """Register a new task and start it in the background.

        The worker coroutine receives a ``TaskContext`` it can use to
        publish progress events. Exceptions are captured and reflected
        on the record as ``FAILED``.
        """
        await self._garbage_collect()
        task_id = str(uuid.uuid4())
        record = _TaskRecord(task_id=task_id, owner_user_id=owner_user_id)
        async with self._lock:
            self._records[task_id] = record

        record.handle = asyncio.create_task(
            self._run(record=record, worker=worker), name=f"task-{task_id}"
        )
        return task_id

    async def _run(
        self,
        *,
        record: _TaskRecord,
        worker: Callable[["TaskContext"], Awaitable[Any]],
    ) -> None:
        ctx = TaskContext(record=record)
        await ctx.publish(status=TaskStatus.RUNNING, progress=0.0, message="Starting…")
        try:
            result = await worker(ctx)
            record.result = result
            record.status = TaskStatus.SUCCEEDED
            record.progress = 1.0
            record.finished_at = time.time()
            await ctx.publish(
                status=TaskStatus.SUCCEEDED, progress=1.0, result=result, message="Done"
            )
        except Exception as exc:  # noqa: BLE001 — we record + bubble up to clients
            logger.exception("Task %s failed", record.task_id)
            record.status = TaskStatus.FAILED
            record.error = f"{type(exc).__name__}: {exc}"
            record.finished_at = time.time()
            await ctx.publish(
                status=TaskStatus.FAILED, progress=record.progress, error=record.error
            )
        finally:
            # Tell SSE subscribers to close out.
            await record.events.put(_EVENT_SENTINEL_TERMINAL)

    # ------------------------------------------------------------------
    # Read access
    # ------------------------------------------------------------------

    async def get(self, task_id: str) -> Optional[TaskProgress]:
        await self._garbage_collect()
        record = self._records.get(task_id)
        if record is None:
            return None
        return TaskProgress(
            task_id=record.task_id,
            status=record.status,
            progress=record.progress,
            result=record.result,
            error=record.error,
            owner_user_id=record.owner_user_id,
        )

    async def stream_events(
        self, task_id: str, *, owner_user_id: str
    ) -> AsyncIterator[TaskEvent]:
        """Yield events for SSE until the task finishes (or is missing).

        Enforces ownership so User A can't peek at User B's task. Replays
        the current state only when the task is already past PENDING so
        late subscribers catch up, without emitting a redundant event for
        brand-new subscribers (the worker's own RUNNING event arrives
        moments later).
        """
        record = self._records.get(task_id)
        if record is None or record.owner_user_id != owner_user_id:
            return

        if record.status != TaskStatus.PENDING:
            yield TaskEvent(
                status=record.status,
                progress=record.progress,
                result=record.result,
                error=record.error,
            )
            if record.status in {TaskStatus.SUCCEEDED, TaskStatus.FAILED}:
                return

        while True:
            item = await record.events.get()
            if item == _EVENT_SENTINEL_TERMINAL:
                return
            assert isinstance(item, TaskEvent)
            yield item
            if item.status in {TaskStatus.SUCCEEDED, TaskStatus.FAILED}:
                return

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    async def _garbage_collect(self) -> None:
        now = time.time()
        async with self._lock:
            expired = [
                task_id
                for task_id, rec in self._records.items()
                if rec.finished_at is not None
                and now - rec.finished_at > self._result_ttl
            ]
            for task_id in expired:
                del self._records[task_id]


class TaskContext:
    """Handle passed to worker coroutines for publishing progress."""

    def __init__(self, *, record: _TaskRecord) -> None:
        self._record = record

    @property
    def task_id(self) -> str:
        return self._record.task_id

    async def publish(
        self,
        *,
        status: TaskStatus,
        progress: float,
        message: Optional[str] = None,
        result: Any = None,
        error: Optional[str] = None,
    ) -> None:
        self._record.status = status
        self._record.progress = max(0.0, min(1.0, progress))
        event = TaskEvent(
            status=status,
            progress=self._record.progress,
            message=message,
            result=result,
            error=error,
        )
        await self._record.events.put(event)

    async def progress(self, fraction: float, *, message: Optional[str] = None) -> None:
        """Convenience helper for progress-only updates."""
        await self.publish(
            status=TaskStatus.RUNNING, progress=fraction, message=message
        )


# ----------------------------------------------------------------------
# Singleton
# ----------------------------------------------------------------------


_manager_singleton: Optional[AsyncTaskManager] = None


def get_task_manager() -> AsyncTaskManager:
    """Return (and lazily construct) the process-wide task manager."""
    global _manager_singleton
    if _manager_singleton is None:
        _manager_singleton = AsyncTaskManager()
    return _manager_singleton


def reset_task_manager_for_tests() -> None:
    """Drop the singleton — test helper only."""
    global _manager_singleton
    _manager_singleton = None
