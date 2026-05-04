from sparkd.services.status import DockerContainer, reconcile


def _c(cid: str, label_launch: str | None = None) -> DockerContainer:
    return DockerContainer(
        id=cid,
        image="vllm",
        labels={"sparkd.launch": label_launch} if label_launch else {},
        state="running",
    )


def test_running_with_dashboard_launch_marked_dashboard():
    snap = reconcile(
        containers=[_c("c1", "L1")],
        launches={"L1": "r1"},
        vllm_models=["meta-llama/Llama-3.1-8B-Instruct"],
        vllm_healthy=True,
    )
    assert len(snap.running_models) == 1
    assert snap.running_models[0].source == "dashboard"
    assert snap.running_models[0].healthy is True


def test_external_container_appears_with_external_source():
    snap = reconcile(
        containers=[_c("c1", None)],
        launches={},
        vllm_models=[],
        vllm_healthy=False,
    )
    assert snap.running_models[0].source == "external"
    assert snap.running_models[0].healthy is False


def test_drift_when_launch_record_has_no_container():
    snap = reconcile(
        containers=[],
        launches={"L1": "r1"},
        vllm_models=[],
        vllm_healthy=False,
    )
    assert "L1" in snap.drift_missing_container


def _vllm_node(cid: str) -> DockerContainer:
    return DockerContainer(id=cid, image="vllm-node", labels={}, state="running")


def test_cluster_worker_recipe_marks_vllm_node_container_as_worker():
    """When this box is a cluster worker and the cluster has an active
    launch (recipe passed via cluster_worker_recipe), the worker's
    vllm-node container shows source='cluster-worker' with the cluster
    launch's recipe name attached — not 'external'/None which is what
    the user saw on the BoxDetail page (DOWN/EXTERNAL labels) before
    this fix."""
    snap = reconcile(
        containers=[_vllm_node("worker-cid-1")],
        launches={},  # no launch is filed under THIS (worker) box
        vllm_models=["org/m"],
        vllm_healthy=True,  # the head's /health was probed and is up
        cluster_worker_recipe="qwen3-122b-cluster",
    )
    rm = snap.running_models[0]
    assert rm.source == "cluster-worker"
    assert rm.recipe_name == "qwen3-122b-cluster"
    # The "healthy" flag reflects the head's health, since vLLM only
    # serves on the head — this is the truth the UI should render.
    assert rm.healthy is True


def test_non_vllm_container_on_cluster_worker_still_external():
    """A non-vllm-node image on a cluster worker is genuine drift —
    the cluster_worker_recipe hint only matches vllm-node containers."""
    snap = reconcile(
        containers=[
            DockerContainer(
                id="random123", image="redis:7", labels={}, state="running"
            )
        ],
        launches={},
        vllm_models=[],
        vllm_healthy=False,
        cluster_worker_recipe="qwen3-122b-cluster",
    )
    assert snap.running_models[0].source == "external"
    assert snap.running_models[0].recipe_name is None


def test_no_cluster_hint_keeps_legacy_external_behavior():
    """When cluster_worker_recipe is None (not a worker, or no cluster
    launch active), unlabeled vllm-node containers stay 'external' —
    same as before this change."""
    snap = reconcile(
        containers=[_vllm_node("c1")],
        launches={},
        vllm_models=[],
        vllm_healthy=False,
    )
    assert snap.running_models[0].source == "external"
