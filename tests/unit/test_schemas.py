import pytest
from pydantic import ValidationError

from sparkd.schemas.box import BoxCreate, BoxSpec
from sparkd.schemas.recipe import RecipeSpec
from sparkd.schemas.launch import LaunchCreate, LaunchState


def test_box_create_minimum():
    b = BoxCreate(name="spark-01", host="10.0.0.5", user="ubuntu")
    assert b.port == 22
    assert b.use_agent is True


def test_box_create_rejects_empty_host():
    with pytest.raises(ValidationError):
        BoxCreate(name="x", host="", user="u")


def test_recipe_spec_round_trip():
    r = RecipeSpec(
        name="llama-8b",
        model="meta-llama/Llama-3.1-8B-Instruct",
        args={"--tensor-parallel-size": "2", "--gpu-memory-utilization": "0.92"},
    )
    assert r.model_dump()["args"]["--tensor-parallel-size"] == "2"


def test_launch_state_values():
    assert LaunchState.starting.value == "starting"
    assert {s.value for s in LaunchState} == {
        "starting", "healthy", "failed", "stopped", "interrupted"
    }


def test_launch_create_requires_recipe_and_box():
    with pytest.raises(ValidationError):
        LaunchCreate(recipe="", box_id="")
