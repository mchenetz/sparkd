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
