import pytest
from sqlalchemy import select

from sparkd.db.engine import init_engine, session_scope
from sparkd.db.models import AdvisorSessionRow


@pytest.fixture
async def db(sparkd_home):
    await init_engine(create_all=True)
    yield


async def test_insert_and_read_session(db):
    async with session_scope() as s:
        s.add(
            AdvisorSessionRow(
                id="s1",
                kind="recipe",
                target_box_id=None,
                hf_model_id="meta-llama/Llama-3.1-8B-Instruct",
                messages_json=[{"role": "user", "content": "hi"}],
                input_tokens=10,
                output_tokens=20,
            )
        )
    async with session_scope() as s:
        rows = (await s.execute(select(AdvisorSessionRow))).scalars().all()
    assert len(rows) == 1
    assert rows[0].kind == "recipe"
    assert rows[0].messages_json[0]["role"] == "user"
