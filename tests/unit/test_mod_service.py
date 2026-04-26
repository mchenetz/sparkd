import pytest

from sparkd.errors import NotFoundError, ValidationError
from sparkd.schemas.mod import ModSpec
from sparkd.services.mod import ModService


@pytest.fixture
def svc(sparkd_home):
    return ModService()


def test_save_then_load_mod(svc):
    m = ModSpec(
        name="patch-a",
        target_models=["llama"],
        description="d",
        files={"patch.diff": "--- a\n+++ b\n", "hook.sh": "#!/bin/sh\n"},
    )
    svc.save(m)
    got = svc.load("patch-a")
    assert got.files["patch.diff"].startswith("--- a")


def test_list_returns_all(svc):
    svc.save(ModSpec(name="a", target_models=[]))
    svc.save(ModSpec(name="b", target_models=[]))
    names = sorted(m.name for m in svc.list())
    assert names == ["a", "b"]


def test_load_missing_raises(svc):
    with pytest.raises(NotFoundError):
        svc.load("nope")


def test_save_rejects_traversal(svc):
    with pytest.raises(ValidationError):
        svc.save(ModSpec(name="../evil", target_models=[]))


def test_save_rejects_traversal_in_filename(svc):
    with pytest.raises(ValidationError):
        svc.save(
            ModSpec(name="m", target_models=[], files={"../etc/passwd": "x"})
        )


def test_delete_mod(svc):
    svc.save(ModSpec(name="a", target_models=[]))
    svc.delete("a")
    with pytest.raises(NotFoundError):
        svc.load("a")
