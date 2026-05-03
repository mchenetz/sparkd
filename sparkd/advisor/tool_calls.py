"""Determine whether a Hugging Face model supports tool calling, and which
vLLM `--tool-call-parser` to use for it.

Pure inference from the model id — no network calls. Substring-matched
against a curated mapping of family → parser. The advisor surfaces this
as a fact in its prompt so Claude (or any LLM advisor) doesn't have to
guess and produce inconsistent configurations like
`--tool-call-parser=qwen3_coder` without `--enable-auto-tool-choice`.

Updating the mapping: add a new (substring, parser) tuple to
_PARSER_PATTERNS. Order matters — more-specific substrings first
(e.g. `qwen3-coder` before `qwen3`). Patterns are case-insensitive."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolCallSupport:
    """Result of `infer_tool_call_config(model_id)`.

    `supports` is True when the model family is known to ship a chat
    template + tokenizer config that vLLM's `--tool-call-parser` can
    parse. `parser` is the value to pass to `--tool-call-parser` when
    `supports=True`; `None` otherwise.
    """

    supports: bool
    parser: str | None


# (substring, parser) — substrings are matched against the lowercased
# model id (org/name). Listed more-specific first because the loop
# returns on first match. Updates: when vLLM adds a new parser, add a
# row here for the matching family.
_PARSER_PATTERNS: list[tuple[str, str]] = [
    # Qwen — the qwen3 line uses the same parser; qwen2.5 has its own.
    ("qwen3-coder", "qwen3_coder"),
    ("qwen3.5", "qwen3_coder"),
    ("qwen3.6", "qwen3_coder"),
    ("qwen3", "qwen3_coder"),
    ("qwen2.5", "qwen2_5"),
    # Llama 3.x — tool calling via JSON-mode parser.
    ("llama-3.1", "llama3_json"),
    ("llama-3.2", "llama3_json"),
    ("llama-3.3", "llama3_json"),
    ("llama-4", "llama3_json"),  # forward-compat best guess
    # Mistral / Mixtral — same parser.
    ("mistral-large", "mistral"),
    ("mistral-7b-instruct-v0.3", "mistral"),
    ("mistral-nemo", "mistral"),
    ("mixtral", "mistral"),
    # NousResearch Hermes fine-tunes.
    ("hermes-2-pro", "hermes"),
    ("hermes-3", "hermes"),
    # InternLM 2.5+
    ("internlm2_5", "internlm"),
    ("internlm3", "internlm"),
    # IBM Granite 3+
    ("granite-3", "granite"),
    # Microsoft Phi-4 Mini
    ("phi-4-mini", "phi4_mini_json"),
    # DeepSeek
    ("deepseek-v3", "deepseek_v3"),
    ("deepseek-r1", "deepseek_v3"),  # R1 shares V3 tool-call format
]

# Markers in the model id that indicate a base / pretraining-only model
# — even if the family supports tool calling, the base variant doesn't
# have the instruction-tuned chat template needed for it.
_BASE_MARKERS: tuple[str, ...] = (
    "-base",
    "-pretrain",
    "/pythia-",
    "-completion",
)


def infer_tool_call_config(model_id: str) -> ToolCallSupport:
    """Infer tool-call support from a HF model id. Returns ToolCallSupport.

    Heuristic, by design — we keep this dependency-free (no HF fetch) so
    it runs in the prompt builder without latency. False negatives mean
    the advisor won't propose tool calling for a model that actually
    supports it; false positives mean the advisor proposes a parser
    that vLLM might reject. The curated mapping should be kept current
    against vLLM's released parsers.
    """
    lower = model_id.lower()
    # Base/pretraining variants never support tool calling, even when
    # the family does.
    if any(m in lower for m in _BASE_MARKERS):
        return ToolCallSupport(supports=False, parser=None)
    for substr, parser in _PARSER_PATTERNS:
        if substr in lower:
            return ToolCallSupport(supports=True, parser=parser)
    return ToolCallSupport(supports=False, parser=None)


def render_tool_call_block(model_id: str) -> str:
    """Format the inference result as a single line for embedding in
    advisor prompts. Concrete fact; no advisory hedging — the prompt
    relies on this to avoid the "guess and configure inconsistently"
    failure mode."""
    tc = infer_tool_call_config(model_id)
    if tc.supports:
        return (
            f"Tool calling: SUPPORTED. Use "
            f'--tool-call-parser: "{tc.parser}" '
            'AND --enable-auto-tool-choice: "true". Set both or neither.'
        )
    return (
        "Tool calling: NOT detected for this model family. Do NOT set "
        "--tool-call-parser or --enable-auto-tool-choice."
    )
