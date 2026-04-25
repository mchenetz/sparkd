import pytest

from sparkd.services.cluster import ClusterService


async def test_cluster_launch_returns_not_implemented():
    svc = ClusterService()
    with pytest.raises(NotImplementedError):
        await svc.launch_across(boxes=["a", "b"], recipe="r")


async def test_cluster_topology_returns_empty():
    svc = ClusterService()
    assert await svc.topology() == {"nodes": [], "edges": []}
