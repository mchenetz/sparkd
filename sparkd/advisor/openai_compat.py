"""OpenAI-compatible adapter — works for OpenAI, vLLM, Mistral, Gemini's
OpenAI-compat endpoint, Groq, OpenRouter, Together, and friends. All of them
speak the same chat-completions wire format with streaming.
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from openai import AsyncOpenAI

from sparkd.advisor.anthropic_adapter import AdvisorChunk
from sparkd.advisor.prompts import (
    SYSTEM_PROMPT,
    build_mod_prompt,
    build_optimize_prompt,
    build_recipe_prompt,
)
from sparkd.schemas.advisor import AdvisorMessage
from sparkd.schemas.box import BoxCapabilities
from sparkd.schemas.hf import HFModelInfo
from sparkd.schemas.recipe import RecipeSpec


class OpenAICompatAdapter:
    def __init__(
        self,
        api_key: str,
        *,
        model: str,
        base_url: str | None = None,
        max_tokens: int = 4096,
    ) -> None:
        self._client = AsyncOpenAI(
            api_key=api_key or "no-key",  # vLLM and similar servers accept any
            base_url=base_url,
        )
        self._model = model
        self._max_tokens = max_tokens

    async def _stream(
        self, system: str, user: str, history: list[AdvisorMessage]
    ) -> AsyncIterator[AdvisorChunk]:
        messages: list[dict] = [{"role": "system", "content": system}]
        for m in history:
            if m.role in ("user", "assistant"):
                messages.append({"role": m.role, "content": m.content})
        messages.append({"role": "user", "content": user})

        stream = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            max_tokens=self._max_tokens,
            stream=True,
            stream_options={"include_usage": True},
        )

        in_tok = 0
        out_tok = 0
        async for event in stream:
            choices = getattr(event, "choices", None) or []
            if choices:
                delta = getattr(choices[0].delta, "content", None) or ""
                if delta:
                    yield AdvisorChunk(delta=delta)
            usage = getattr(event, "usage", None)
            if usage is not None:
                in_tok = getattr(usage, "prompt_tokens", 0) or 0
                out_tok = getattr(usage, "completion_tokens", 0) or 0
        yield AdvisorChunk(
            delta="", input_tokens=in_tok, output_tokens=out_tok, final=True
        )

    async def stream_recipe(
        self,
        info: HFModelInfo,
        caps: BoxCapabilities,
        history: list[AdvisorMessage],
        *,
        cluster: dict | None = None,
    ) -> AsyncIterator[AdvisorChunk]:
        prompt = build_recipe_prompt(info, caps, cluster=cluster)
        async for c in self._stream(SYSTEM_PROMPT, prompt, history):
            yield c

    async def stream_optimize(
        self,
        recipe: RecipeSpec,
        caps: BoxCapabilities,
        goals: list[str],
        history: list[AdvisorMessage],
    ) -> AsyncIterator[AdvisorChunk]:
        async for c in self._stream(
            SYSTEM_PROMPT, build_optimize_prompt(recipe, caps, goals=goals), history
        ):
            yield c

    async def stream_mod(
        self, error_log: str, model_id: str, history: list[AdvisorMessage]
    ) -> AsyncIterator[AdvisorChunk]:
        async for c in self._stream(
            SYSTEM_PROMPT, build_mod_prompt(error_log=error_log, model_id=model_id), history
        ):
            yield c
