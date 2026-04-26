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


def test_save_accepts_leading_underscore_and_dot_filenames(svc):
    """Upstream mods include files like `_triton_alloc_setup.pth` and
    `.gitignore` — these must be accepted (they're not path-traversal)."""
    svc.save(
        ModSpec(
            name="m",
            target_models=[],
            files={
                "_triton_alloc_setup.pth": "x",
                ".gitignore": "y",
                "sub/_inner.py": "z",
            },
        )
    )
    got = svc.load("m")
    assert "_triton_alloc_setup.pth" in got.files
    assert ".gitignore" in got.files
    assert "sub/_inner.py" in got.files


def test_save_still_rejects_absolute_path(svc):
    with pytest.raises(ValidationError):
        svc.save(
            ModSpec(name="m", target_models=[], files={"/etc/passwd": "x"})
        )


def test_delete_mod(svc):
    svc.save(ModSpec(name="a", target_models=[]))
    svc.delete("a")
    with pytest.raises(NotFoundError):
        svc.load("a")


def test_save_removes_files_not_in_new_spec(svc):
    """Editing via the UI should be able to remove files."""
    svc.save(ModSpec(name="m", target_models=[], files={"a.sh": "A", "b.sh": "B"}))
    svc.save(ModSpec(name="m", target_models=[], files={"a.sh": "A only"}))
    got = svc.load("m")
    assert "b.sh" not in got.files
    assert got.files == {"a.sh": "A only"}


def test_save_prunes_empty_subdirs(svc):
    """When a file under a subdirectory is removed and the subdir empties,
    the subdir is cleaned up so it doesn't show as a phantom file path."""
    svc.save(
        ModSpec(
            name="m",
            target_models=[],
            files={"sub/x.txt": "X", "top.txt": "T"},
        )
    )
    svc.save(ModSpec(name="m", target_models=[], files={"top.txt": "T"}))
    got = svc.load("m")
    assert got.files == {"top.txt": "T"}
