"""Resolve a `target` string ("<box_id>" | "cluster:<name>") to a head box
and member list. Used by LaunchService, AdvisorService, and OptimizeService
so the cluster-as-target convention has exactly one implementation.

The CLUSTER_PREFIX is exported here as the canonical source; legacy uses
elsewhere should import from this module."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from sparkd.errors import NotFoundError
from sparkd.schemas.box import BoxSpec

CLUSTER_PREFIX = "cluster:"


@dataclass
class ResolvedTarget:
    kind: Literal["box", "cluster"]
    head_box: BoxSpec        # SSH lands here
    members: list[BoxSpec]   # [head] for single-box; all members for cluster
    cluster_name: str | None


class _BoxesLike(Protocol):
    async def get(self, box_id: str) -> BoxSpec: ...
    async def list_clusters(self) -> dict[str, list[BoxSpec]]: ...


async def resolve_target(target: str, boxes: _BoxesLike) -> ResolvedTarget:
    """Resolve a target string to a ResolvedTarget.

    - "<box_id>" → kind="box", head=that box, members=[that box]
    - "cluster:<name>" → kind="cluster", head=first member, members=all
    - anything falsy → ValueError (callers must pre-validate)
    - unknown box id or unknown cluster name → NotFoundError
    - cluster name with zero members → NotFoundError
    """
    if not target:
        raise ValueError("target is required")
    if target.startswith(CLUSTER_PREFIX):
        name = target[len(CLUSTER_PREFIX):]
        grouped = await boxes.list_clusters()
        members = grouped.get(name) or []
        if not members:
            raise NotFoundError("cluster", name)
        return ResolvedTarget(
            kind="cluster",
            head_box=members[0],
            members=list(members),
            cluster_name=name,
        )
    box = await boxes.get(target)  # raises NotFoundError on miss
    return ResolvedTarget(
        kind="box", head_box=box, members=[box], cluster_name=None
    )
