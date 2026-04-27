"""Resolve a string `target` (box id or `cluster:<name>`) to a head box +
member list. Pure logic; no SSH, no DB."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from sparkd.errors import NotFoundError
from sparkd.schemas.box import BoxSpec
from sparkd.services.targets import (
    CLUSTER_PREFIX,
    ResolvedTarget,
    resolve_target,
)


def _box(name: str, host: str, *, cluster: str | None = None) -> BoxSpec:
    return BoxSpec(
        id=f"id-{name}",
        name=name,
        host=host,
        port=22,
        user="u",
        repo_path="~/spark-vllm-docker",
        tags={"cluster": cluster} if cluster else {},
        created_at=datetime.now(timezone.utc),
    )


class FakeBoxes:
    def __init__(self, boxes: list[BoxSpec]) -> None:
        self._boxes = {b.id: b for b in boxes}

    async def get(self, box_id: str) -> BoxSpec:
        if box_id not in self._boxes:
            raise NotFoundError("box", box_id)
        return self._boxes[box_id]

    async def list_clusters(self) -> dict[str, list[BoxSpec]]:
        out: dict[str, list[BoxSpec]] = {}
        for b in self._boxes.values():
            name = b.tags.get("cluster")
            if name:
                out.setdefault(name, []).append(b)
        return out


async def test_resolve_none_target_raises():
    boxes = FakeBoxes([])
    with pytest.raises(ValueError):
        await resolve_target(None, boxes)  # type: ignore[arg-type]


async def test_resolve_single_box_target():
    a = _box("a", "10.0.0.1")
    boxes = FakeBoxes([a])
    r = await resolve_target(a.id, boxes)  # type: ignore[arg-type]
    assert r.kind == "box"
    assert r.head_box.id == a.id
    assert [m.id for m in r.members] == [a.id]
    assert r.cluster_name is None


async def test_resolve_unknown_box_raises():
    boxes = FakeBoxes([])
    with pytest.raises(NotFoundError):
        await resolve_target("ghost", boxes)  # type: ignore[arg-type]


async def test_resolve_cluster_target():
    n1 = _box("n1", "10.0.0.1", cluster="alpha")
    n2 = _box("n2", "10.0.0.2", cluster="alpha")
    n3 = _box("n3", "10.0.0.3", cluster="alpha")
    other = _box("solo", "10.0.0.99")
    boxes = FakeBoxes([n1, n2, n3, other])
    r = await resolve_target(f"{CLUSTER_PREFIX}alpha", boxes)  # type: ignore[arg-type]
    assert r.kind == "cluster"
    assert r.cluster_name == "alpha"
    assert r.head_box.id == n1.id  # first member is head
    assert [m.id for m in r.members] == [n1.id, n2.id, n3.id]


async def test_resolve_unknown_cluster_raises():
    boxes = FakeBoxes([_box("a", "10.0.0.1")])
    with pytest.raises(NotFoundError):
        await resolve_target(f"{CLUSTER_PREFIX}nope", boxes)  # type: ignore[arg-type]


async def test_resolve_empty_cluster_raises():
    """A cluster name was registered (somehow) but has no members. Treat as missing."""
    boxes = FakeBoxes([])  # list_clusters returns {} → "alpha" missing
    with pytest.raises(NotFoundError):
        await resolve_target(f"{CLUSTER_PREFIX}alpha", boxes)  # type: ignore[arg-type]
