import pytest
from pydantic import ValidationError

from sparkd.schemas.advisor import (
    AdvisorMessage,
    AdvisorSession,
    ModDraft,
    RecipeDraft,
)
from sparkd.schemas.hf import HFModelInfo
from sparkd.schemas.mod import ModSpec


def test_hf_model_info_required_fields():
    info = HFModelInfo(
        id="meta-llama/Llama-3.1-8B-Instruct",
        architecture="LlamaForCausalLM",
        parameters_b=8.0,
        context_length=131072,
        supported_dtypes=["bf16", "fp16"],
    )
    assert info.id == "meta-llama/Llama-3.1-8B-Instruct"
    assert info.parameters_b == 8.0


def test_mod_spec_round_trip():
    m = ModSpec(name="patch-x", target_models=["llama"], description="d")
    d = m.model_dump()
    assert ModSpec(**d) == m


def test_recipe_draft_carries_rationale():
    d = RecipeDraft(
        name="r1",
        model="m",
        args={"--tp": "2"},
        env={},
        rationale="Two GPUs available; tp=2 fits.",
    )
    assert d.rationale.startswith("Two")


def test_mod_draft_has_files():
    d = ModDraft(
        name="m1",
        target_models=["llama"],
        files={"patch.diff": "...", "hook.sh": "#!/bin/sh\n"},
        rationale="r",
    )
    assert "patch.diff" in d.files


def test_advisor_message_roles():
    AdvisorMessage(role="user", content="hi")
    AdvisorMessage(role="assistant", content="hello")
    with pytest.raises(ValidationError):
        AdvisorMessage(role="bogus", content="x")


def test_advisor_session_minimum():
    s = AdvisorSession(id="s1", kind="recipe", target_box_id=None)
    assert s.kind == "recipe"
    assert s.messages == []
