from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from sparkd.services.jobs import JobRegistry

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _reg(request: Request) -> JobRegistry:
    return request.app.state.jobs


@router.get("/{job_id}")
def get_job(job_id: str, reg: JobRegistry = Depends(_reg)) -> dict:
    return reg.get(job_id).model_dump(mode="json")
