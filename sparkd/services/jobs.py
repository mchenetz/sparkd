from __future__ import annotations

import asyncio
import inspect
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

from sparkd.errors import NotFoundError
from sparkd.schemas.job import Job, JobState


class JobRegistry:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._events: dict[str, asyncio.Event] = {}

    async def submit(
        self,
        kind: str,
        fn: Callable[[], Awaitable[Any] | Any],
        *,
        progress_hook: Callable[[float, str], None] | None = None,
    ) -> str:
        job_id = uuid.uuid4().hex[:12]
        now = datetime.now(timezone.utc)
        self._jobs[job_id] = Job(
            id=job_id, kind=kind, state=JobState.running, started_at=now
        )
        self._events[job_id] = asyncio.Event()

        async def runner() -> None:
            try:
                result = fn() if not inspect.iscoroutinefunction(fn) else await fn()
                if inspect.isawaitable(result):
                    result = await result
                self._jobs[job_id] = self._jobs[job_id].model_copy(
                    update={
                        "state": JobState.succeeded,
                        "result": result if isinstance(result, dict) else {"value": result},
                        "finished_at": datetime.now(timezone.utc),
                        "progress": 1.0,
                    }
                )
            except Exception as exc:
                self._jobs[job_id] = self._jobs[job_id].model_copy(
                    update={
                        "state": JobState.failed,
                        "message": str(exc),
                        "finished_at": datetime.now(timezone.utc),
                    }
                )
            finally:
                self._events[job_id].set()

        self._tasks[job_id] = asyncio.create_task(runner())
        return job_id

    def get(self, job_id: str) -> Job:
        if job_id not in self._jobs:
            raise NotFoundError("job", job_id)
        return self._jobs[job_id]

    def list(self) -> list[Job]:
        return list(self._jobs.values())

    async def wait(self, job_id: str) -> Job:
        if job_id not in self._events:
            raise NotFoundError("job", job_id)
        await self._events[job_id].wait()
        return self._jobs[job_id]
