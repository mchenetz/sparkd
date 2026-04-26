"""save_recipe_raw round-trips upstream-format YAML byte-identical."""

import pytest

from sparkd.errors import ValidationError
from sparkd.services.library import LibraryService


UPSTREAM_YAML = """recipe_version: 1
name: qwen3.5-35b-a3b-fp8
description: Qwen 3.5 35B A3B FP8 quantization
model: zai-org/Qwen3.5-35B-A3B-FP8
container: vllm/vllm-openai:latest
mods:
  - mods/qwen-marlin-fix
  - mods/fp8-kv
defaults:
  port: 8000
  host: 0.0.0.0
  tensor_parallel: 2
  gpu_memory_utilization: 0.92
  max_model_len: 32768
env:
  VLLM_MARLIN_USE_ATOMIC_ADD: "1"
command: |
  vllm serve {model}
    --tensor-parallel-size {tensor_parallel}
    --gpu-memory-utilization {gpu_memory_utilization}
"""


@pytest.fixture
def lib(sparkd_home):
    return LibraryService()


def test_save_raw_preserves_yaml_byte_for_byte(lib):
    spec = lib.save_recipe_raw("qwen3.5-35b-a3b-fp8", UPSTREAM_YAML)
    assert spec.name == "qwen3.5-35b-a3b-fp8"
    assert spec.model == "zai-org/Qwen3.5-35B-A3B-FP8"
    text = lib.load_recipe_text("qwen3.5-35b-a3b-fp8")
    assert text == UPSTREAM_YAML


def test_save_raw_preserves_name_field_in_yaml_but_view_uses_filename(lib):
    yaml_text = "name: not-the-filename\nmodel: x/y\n"
    spec = lib.save_recipe_raw("real-name", yaml_text)
    # Parsed view: filename wins.
    assert spec.name == "real-name"
    # On-disk: YAML untouched.
    assert lib.load_recipe_text("real-name") == yaml_text


def test_save_raw_rejects_missing_model(lib):
    with pytest.raises(ValidationError):
        lib.save_recipe_raw("x", "name: x\ndescription: no model\n")


def test_save_raw_rejects_non_mapping(lib):
    with pytest.raises(ValidationError):
        lib.save_recipe_raw("x", "- a\n- b\n")


def test_has_recipe(lib):
    assert lib.has_recipe("nope") is False
    lib.save_recipe_raw("yep", "name: yep\nmodel: m\n")
    assert lib.has_recipe("yep") is True


def test_load_recipe_text_prefers_override(lib):
    lib.save_recipe_raw("r1", "name: r1\nmodel: a/b\n")
    # Construct an override the same way LibraryService does.
    from sparkd import paths

    override_dir = paths.boxes_dir() / "box-x" / "overrides" / "recipes"
    override_dir.mkdir(parents=True, exist_ok=True)
    (override_dir / "r1.yaml").write_text("name: r1\nmodel: a/b-override\n")
    assert "b-override" in lib.load_recipe_text("r1", box_id="box-x")
    assert "b-override" not in lib.load_recipe_text("r1")
