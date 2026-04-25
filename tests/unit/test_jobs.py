import asyncio

import pytest

from sparkd.schemas.job import JobState
from sparkd.services.jobs import JobRegistry


async def test_submit_and_complete():
    reg = JobRegistry()

    async def work():
        return {"answer": 42}

    job_id = await reg.submit("test", work)
    job = await reg.wait(job_id)
    assert job.state == JobState.succeeded
    assert job.result == {"answer": 42}


async def test_submit_and_fail():
    reg = JobRegistry()

    async def boom():
        raise RuntimeError("nope")

    job_id = await reg.submit("test", boom)
    job = await reg.wait(job_id)
    assert job.state == JobState.failed
    assert "nope" in job.message


async def test_list_returns_active_and_finished():
    reg = JobRegistry()
    job_id = await reg.submit("k", lambda: asyncio.sleep(0))
    await reg.wait(job_id)
    jobs = reg.list()
    assert len(jobs) == 1
