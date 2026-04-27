from collections.abc import AsyncIterator
from datetime import datetime, timezone

import pytest

from sparkd.advisor import AdvisorChunk
from sparkd.db.engine import init_engine
from sparkd.schemas.advisor import AdvisorMessage
from sparkd.schemas.box import BoxCapabilities
from sparkd.schemas.hf import HFModelInfo
from sparkd.services.advisor import AdvisorService


class FakePort:
    def __init__(self, text: str, *, in_tok: int = 5, out_tok: int = 10) -> None:
        self.text = text
        self.in_tok = in_tok
        self.out_tok = out_tok
        self.last_history: list[AdvisorMessage] = []

    async def _yield(self, history) -> AsyncIterator[AdvisorChunk]:
        self.last_history = list(history)
        for ch in self.text:
            yield AdvisorChunk(delta=ch)
        yield AdvisorChunk(
            delta="", input_tokens=self.in_tok, output_tokens=self.out_tok, final=True
        )

    async def stream_recipe(self, info, caps, history, *, cluster=None):
        async for c in self._yield(history):
            yield c

    async def stream_optimize(self, recipe, caps, goals, history):
        async for c in self._yield(history):
            yield c

    async def stream_mod(self, error_log, model_id, history):
        async for c in self._yield(history):
            yield c


@pytest.fixture
async def svc(sparkd_home):
    await init_engine(create_all=True)
    text = (
        '```json\n{"name":"llama","model":"meta-llama/Llama-3.1-8B-Instruct",'
        '"args":{"--tensor-parallel-size":"2"},"env":{},"description":"d","rationale":"r"}\n```'
    )
    port = FakePort(text)
    yield AdvisorService(port=port), port


def _info(model_id: str = "x/y") -> HFModelInfo:
    return HFModelInfo(
        id=model_id,
        architecture="X",
        parameters_b=1.0,
        context_length=4096,
    )


def _caps() -> BoxCapabilities:
    return BoxCapabilities(
        gpu_count=2,
        gpu_model="GB10",
        vram_per_gpu_gb=96,
        captured_at=datetime.now(timezone.utc),
    )


async def test_generate_recipe_yields_tokens_then_draft(svc):
    s, _ = svc
    info = _info("meta-llama/Llama-3.1-8B-Instruct")
    sid = await s.create_session(kind="recipe", target_box_id="b1", hf_model_id=info.id)
    deltas: list[str] = []
    final_draft = None
    async for ev in s.generate_recipe(sid, info=info, caps=_caps()):
        if ev["type"] == "delta":
            deltas.append(ev["text"])
        elif ev["type"] == "draft":
            final_draft = ev["draft"]
    assert "".join(deltas)
    assert final_draft is not None
    assert final_draft["name"] == "llama"
    assert final_draft["args"]["--tensor-parallel-size"] == "2"


async def test_followup_via_repeat_call_uses_history(svc):
    s, port = svc
    sid = await s.create_session(kind="recipe", hf_model_id="x/y")
    async for _ in s.generate_recipe(sid, info=_info(), caps=_caps()):
        pass
    # second call should see the prior turn in history
    async for _ in s.generate_recipe(
        sid, info=_info(), caps=_caps(), user_msg="tweak it"
    ):
        pass
    history_roles = [m.role for m in port.last_history]
    assert "user" in history_roles
    assert "assistant" in history_roles


async def test_get_session_returns_persisted_state(svc):
    s, _ = svc
    sid = await s.create_session(kind="recipe", hf_model_id="x/y")
    async for _ in s.generate_recipe(sid, info=_info(), caps=_caps()):
        pass
    sess = await s.get_session(sid)
    assert sess.id == sid
    assert sess.input_tokens > 0
    assert any(m.role == "assistant" for m in sess.messages)
