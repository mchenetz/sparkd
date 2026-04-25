import pytest
from sqlalchemy import select

from sparkd.db.engine import session_scope, init_engine
from sparkd.db.models import Box, Launch, AuditLog


@pytest.fixture
async def db(tmp_path, monkeypatch):
    monkeypatch.setenv("SPARKD_HOME", str(tmp_path))
    await init_engine(create_all=True)
    yield


async def test_can_insert_and_read_box(db):
    async with session_scope() as s:
        s.add(Box(id="b1", name="spark-01", host="10.0.0.5", user="ubuntu"))
    async with session_scope() as s:
        rows = (await s.execute(select(Box))).scalars().all()
    assert len(rows) == 1
    assert rows[0].host == "10.0.0.5"


async def test_launch_box_relationship(db):
    async with session_scope() as s:
        s.add(Box(id="b1", name="x", host="h", user="u"))
        s.add(
            Launch(
                id="l1",
                box_id="b1",
                recipe_name="r",
                state="starting",
                command="./run-recipe.sh r",
            )
        )
    async with session_scope() as s:
        l = (await s.execute(select(Launch))).scalar_one()
        assert l.box_id == "b1"
        assert l.state == "starting"
