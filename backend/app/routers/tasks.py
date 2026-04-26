"""
Tasks Router — async agent execution endpoints.

Two verbs:
    * GET /api/tasks/{task_id}           — one-shot poll
    * GET /api/tasks/{task_id}/events    — Server-Sent Events stream

Worker submission endpoints live in the domain routers that own the
work (e.g. ``POST /api/jobs/{job_id}/generate-interview-prep-async``
in the jobs router). This file only exposes the read side of the task
manager.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Annotated, AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.dependencies.auth import get_current_user
from app.models.user import User
from app.services.task_manager import (
    AsyncTaskManager,
    TaskEvent,
    TaskStatus,
    get_task_manager,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/tasks", tags=["Tasks"])


@router.get(
    "/{task_id}",
    summary="Poll the current status of an async task",
)
async def get_task_status(
    task_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Return a snapshot of the task's current status, result, or error.

    Ownership is enforced: users can only see their own tasks.
    """
    manager = get_task_manager()
    snapshot = await manager.get(task_id)
    if snapshot is None or snapshot.owner_user_id != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    return {
        "task_id": snapshot.task_id,
        "status": snapshot.status.value,
        "progress": round(snapshot.progress, 3),
        "result": snapshot.result,
        "error": snapshot.error,
    }


@router.get(
    "/{task_id}/events",
    summary="Subscribe to task progress via Server-Sent Events",
)
async def stream_task_events(
    task_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
) -> StreamingResponse:
    """Stream progress updates until the task terminates.

    The response body follows the SSE spec: ``data:`` lines carrying
    JSON payloads, separated by blank lines. The stream closes on
    terminal status (``succeeded`` / ``failed``) or if the task
    disappears between checks.
    """
    manager = get_task_manager()
    snapshot = await manager.get(task_id)
    if snapshot is None or snapshot.owner_user_id != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    return StreamingResponse(
        _sse_generator(manager, task_id=task_id, owner_user_id=str(current_user.id)),
        media_type="text/event-stream",
        headers={
            # Disable intermediate buffering so events reach the browser
            # incrementally. These two headers are widely honoured by
            # reverse proxies.
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


async def _sse_generator(
    manager: AsyncTaskManager, *, task_id: str, owner_user_id: str
) -> AsyncIterator[bytes]:
    """Produce SSE-formatted bytes for each TaskEvent.

    Emits a heartbeat comment every 15 seconds of silence so load
    balancers and browsers don't prematurely close the stream during
    long-running work.
    """
    event_stream = manager.stream_events(task_id, owner_user_id=owner_user_id)
    stream_iter = event_stream.__aiter__()

    while True:
        try:
            event: TaskEvent = await asyncio.wait_for(
                stream_iter.__anext__(), timeout=15.0
            )
        except asyncio.TimeoutError:
            # Heartbeat: SSE ignores lines starting with a colon.
            yield b": keep-alive\n\n"
            continue
        except StopAsyncIteration:
            return

        payload = json.dumps(event.to_payload(), ensure_ascii=False)
        yield f"event: progress\ndata: {payload}\n\n".encode("utf-8")

        if event.status in {TaskStatus.SUCCEEDED, TaskStatus.FAILED}:
            return
