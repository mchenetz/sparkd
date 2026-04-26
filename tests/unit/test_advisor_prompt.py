from datetime import datetime, timezone

from sparkd.advisor.prompts import (
    SYSTEM_PROMPT,
    build_mod_prompt,
    build_optimize_prompt,
    build_recipe_prompt,
    parse_mod_draft,
    parse_recipe_draft,
)
from sparkd.schemas.box import BoxCapabilities
from sparkd.schemas.hf import HFModelInfo
from sparkd.schemas.recipe import RecipeSpec


def _caps() -> BoxCapabilities:
    return BoxCapabilities(
        gpu_count=2,
        gpu_model="NVIDIA GB10",
        vram_per_gpu_gb=96,
        captured_at=datetime.now(timezone.utc),
    )


def _info() -> HFModelInfo:
    return HFModelInfo(
        id="meta-llama/Llama-3.1-8B-Instruct",
        architecture="LlamaForCausalLM",
        parameters_b=8.0,
        context_length=131072,
        supported_dtypes=["bf16"],
    )


def test_recipe_prompt_includes_facts():
    p = build_recipe_prompt(_info(), _caps())
    assert "GB10" in p
    assert "Llama-3.1-8B" in p
    assert "131072" in p


def test_optimize_prompt_carries_existing_recipe():
    r = RecipeSpec(name="r", model="m", args={"--tp": "1"})
    p = build_optimize_prompt(r, _caps(), goals=["throughput"])
    assert "--tp" in p
    assert "throughput" in p


def test_mod_prompt_carries_error_log():
    p = build_mod_prompt(error_log="ImportError: foo", model_id="x")
    assert "ImportError: foo" in p


def test_parse_recipe_draft_from_json_block():
    text = (
        "Here is the recipe.\n"
        "```json\n"
        '{"name":"r","model":"m","args":{"--tp":"2"},'
        '"env":{},"description":"d","rationale":"r"}\n'
        "```\n"
    )
    draft = parse_recipe_draft(text)
    assert draft.name == "r"
    assert draft.args["--tp"] == "2"


def test_parse_mod_draft_from_json_block():
    text = (
        "```json\n"
        '{"name":"m1","target_models":["llama"],'
        '"files":{"patch.diff":"--- a\\n+++ b\\n"},'
        '"description":"d","rationale":"r"}\n'
        "```"
    )
    d = parse_mod_draft(text)
    assert d.name == "m1"
    assert "patch.diff" in d.files


def test_system_prompt_describes_role():
    assert "DGX Spark" in SYSTEM_PROMPT
