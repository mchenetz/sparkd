from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

from sparkd.advisor import AdvisorPort
from sparkd.advisor.prompts import parse_mod_draft, parse_recipe_draft
from sparkd.db.engine import session_scope
from sparkd.db.models import AdvisorSessionRow
from sparkd.errors import NotFoundError, UpstreamError
from sparkd.schemas.advisor import AdvisorMessage, AdvisorSession
from sparkd.schemas.box import BoxCapabilities
from sparkd.schemas.hf import HFModelInfo
from sparkd.schemas.recipe import RecipeSpec


def _row_to_session(row: AdvisorSessionRow) -> AdvisorSession:
    return AdvisorSession(
        id=row.id,
        kind=row.kind,
        target_box_id=row.target_box_id,
        target_recipe_name=row.target_recipe_name,
        hf_model_id=row.hf_model_id,
        messages=[AdvisorMessage(**m) for m in (row.messages_json or [])],
        input_tokens=row.input_tokens,
        output_tokens=row.output_tokens,
        created_at=row.created_at,
    )


class AdvisorService:
    def __init__(self, port: AdvisorPort | None) -> None:
        self.port = port

    async def create_session(
        self,
        *,
        kind: str,
        target_box_id: str | None = None,
        target_recipe_name: str | None = None,
        hf_model_id: str | None = None,
    ) -> str:
        sid = uuid.uuid4().hex[:12]
        async with session_scope() as s:
            s.add(
                AdvisorSessionRow(
                    id=sid,
                    kind=kind,
                    target_box_id=target_box_id,
                    target_recipe_name=target_recipe_name,
                    hf_model_id=hf_model_id,
                    messages_json=[],
                )
            )
        return sid

    async def get_session(self, session_id: str) -> AdvisorSession:
        async with session_scope() as s:
            row = await s.get(AdvisorSessionRow, session_id)
            if row is None:
                raise NotFoundError("advisor_session", session_id)
            return _row_to_session(row)

    async def _load_history(self, session_id: str) -> list[AdvisorMessage]:
        sess = await self.get_session(session_id)
        return sess.messages

    async def _persist_turn(
        self,
        session_id: str,
        *,
        user_msg: str,
        assistant_text: str,
        in_tokens: int,
        out_tokens: int,
    ) -> None:
        async with session_scope() as s:
            row = await s.get(AdvisorSessionRow, session_id)
            if row is None:
                raise NotFoundError("advisor_session", session_id)
            existing = list(row.messages_json or [])
            existing.append({"role": "user", "content": user_msg})
            existing.append({"role": "assistant", "content": assistant_text})
            row.messages_json = existing
            row.input_tokens = (row.input_tokens or 0) + in_tokens
            row.output_tokens = (row.output_tokens or 0) + out_tokens

    async def _drive(
        self,
        session_id: str,
        user_msg: str,
        chunks_iter: AsyncIterator,
        parse_kind: str,
    ) -> AsyncIterator[dict[str, Any]]:
        buf: list[str] = []
        in_tok = 0
        out_tok = 0
        async for ch in chunks_iter:
            if ch.final:
                in_tok = ch.input_tokens
                out_tok = ch.output_tokens
                continue
            if ch.delta:
                buf.append(ch.delta)
                yield {"type": "delta", "text": ch.delta}
        full = "".join(buf)
        await self._persist_turn(
            session_id,
            user_msg=user_msg,
            assistant_text=full,
            in_tokens=in_tok,
            out_tokens=out_tok,
        )
        try:
            if parse_kind == "recipe":
                draft = parse_recipe_draft(full)
                yield {"type": "draft", "draft": draft.model_dump()}
            elif parse_kind == "mod":
                draft = parse_mod_draft(full)
                yield {"type": "draft", "draft": draft.model_dump()}
        except Exception as exc:  # noqa: BLE001
            yield {"type": "error", "message": f"could not parse {parse_kind}: {exc}"}

    def _require_port(self) -> AdvisorPort:
        if self.port is None:
            raise UpstreamError("advisor not configured (no Anthropic key)")
        return self.port

    async def generate_recipe(
        self,
        session_id: str,
        *,
        info: HFModelInfo,
        caps: BoxCapabilities,
        user_msg: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        port = self._require_port()
        history = await self._load_history(session_id)
        msg = user_msg or f"Generate a recipe for {info.id}"
        try:
            chunks = port.stream_recipe(info=info, caps=caps, history=history)
        except Exception as exc:  # noqa: BLE001
            raise UpstreamError(f"advisor: {exc}") from exc
        async for ev in self._drive(session_id, msg, chunks, "recipe"):
            yield ev

    async def optimize_recipe(
        self,
        session_id: str,
        *,
        recipe: RecipeSpec,
        caps: BoxCapabilities,
        goals: list[str],
        user_msg: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        port = self._require_port()
        history = await self._load_history(session_id)
        msg = user_msg or f"Optimize recipe {recipe.name} for goals: {', '.join(goals)}"
        try:
            chunks = port.stream_optimize(
                recipe=recipe, caps=caps, goals=goals, history=history
            )
        except Exception as exc:  # noqa: BLE001
            raise UpstreamError(f"advisor: {exc}") from exc
        async for ev in self._drive(session_id, msg, chunks, "recipe"):
            yield ev

    async def propose_mod(
        self,
        session_id: str,
        *,
        error_log: str,
        model_id: str,
        user_msg: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        port = self._require_port()
        history = await self._load_history(session_id)
        msg = user_msg or f"Propose a mod for {model_id} addressing the error log."
        try:
            chunks = port.stream_mod(
                error_log=error_log, model_id=model_id, history=history
            )
        except Exception as exc:  # noqa: BLE001
            raise UpstreamError(f"advisor: {exc}") from exc
        async for ev in self._drive(session_id, msg, chunks, "mod"):
            yield ev
