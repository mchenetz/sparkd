import pytest

from sparkd.errors import NotFoundError, ValidationError
from sparkd.schemas.recipe import RecipeSpec
from sparkd.services.library import LibraryService


@pytest.fixture
def lib(sparkd_home):
    return LibraryService()


def test_save_then_load_recipe(lib):
    r = RecipeSpec(name="r1", model="m", args={"--foo": "bar"})
    lib.save_recipe(r)
    got = lib.load_recipe("r1")
    assert got.args == {"--foo": "bar"}


def test_load_missing_raises(lib):
    with pytest.raises(NotFoundError):
        lib.load_recipe("nope")


def test_list_recipes_returns_canonical(lib):
    lib.save_recipe(RecipeSpec(name="a", model="m"))
    lib.save_recipe(RecipeSpec(name="b", model="m"))
    names = [r.name for r in lib.list_recipes()]
    assert sorted(names) == ["a", "b"]


def test_effective_view_merges_overrides(lib):
    lib.save_recipe(RecipeSpec(name="r1", model="m", args={"--tp": "1"}))
    lib.save_recipe_override(
        "box-x", RecipeSpec(name="r1", model="m", args={"--tp": "2"})
    )
    eff = lib.load_recipe("r1", box_id="box-x")
    assert eff.args["--tp"] == "2"


def test_save_recipe_rejects_path_traversal(lib):
    with pytest.raises(ValidationError):
        lib.save_recipe(RecipeSpec(name="../evil", model="m"))


def test_delete_recipe(lib):
    lib.save_recipe(RecipeSpec(name="r1", model="m"))
    lib.delete_recipe("r1")
    with pytest.raises(NotFoundError):
        lib.load_recipe("r1")
