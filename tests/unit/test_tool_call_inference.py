"""Curated mapping that decides whether a HF model id supports tool
calling and which vLLM `--tool-call-parser` to use. This is what the
advisor's prompt embeds as a fact so Claude doesn't have to guess and
produce inconsistent configs (parser without enable-auto-tool-choice,
parser for a base/pretraining model, etc.)."""

from sparkd.advisor.tool_calls import (
    ToolCallSupport,
    infer_tool_call_config,
    render_tool_call_block,
)


def test_qwen3_5_uses_qwen3_coder_parser():
    r = infer_tool_call_config("Qwen/Qwen3.5-122B-A10B-FP8")
    assert r == ToolCallSupport(supports=True, parser="qwen3_coder")


def test_qwen3_6_uses_qwen3_coder_parser():
    """Forward-compat: Qwen3.6 series maps to the same parser."""
    r = infer_tool_call_config("mmangkad/Qwen3.6-27B-NVFP4")
    assert r == ToolCallSupport(supports=True, parser="qwen3_coder")


def test_qwen2_5_uses_dedicated_parser():
    r = infer_tool_call_config("Qwen/Qwen2.5-7B-Instruct")
    assert r == ToolCallSupport(supports=True, parser="qwen2_5")


def test_llama3_1_uses_json_parser():
    r = infer_tool_call_config("meta-llama/Llama-3.1-70B-Instruct")
    assert r == ToolCallSupport(supports=True, parser="llama3_json")


def test_mixtral_uses_mistral_parser():
    r = infer_tool_call_config("mistralai/Mixtral-8x22B-Instruct-v0.1")
    assert r == ToolCallSupport(supports=True, parser="mistral")


def test_phi4_mini_dedicated_parser():
    r = infer_tool_call_config("microsoft/Phi-4-Mini-Instruct")
    assert r == ToolCallSupport(supports=True, parser="phi4_mini_json")


def test_deepseek_v3_dedicated_parser():
    r = infer_tool_call_config("deepseek-ai/DeepSeek-V3")
    assert r == ToolCallSupport(supports=True, parser="deepseek_v3")


def test_base_model_returns_no_support():
    """Base / pretraining variants don't ship a chat template — no
    tool calling possible even when the family supports it."""
    r = infer_tool_call_config("Qwen/Qwen3-8B-Base")
    assert r == ToolCallSupport(supports=False, parser=None)


def test_unknown_family_returns_no_support():
    r = infer_tool_call_config("some-org/random-experimental-model")
    assert r == ToolCallSupport(supports=False, parser=None)


def test_render_block_when_supported_includes_both_flag_names():
    """The rendered fact must mention both flags by name so Claude
    can't accidentally set just one."""
    s = render_tool_call_block("Qwen/Qwen3.5-122B-A10B-FP8")
    assert "SUPPORTED" in s
    assert "qwen3_coder" in s
    assert "--tool-call-parser" in s
    assert "--enable-auto-tool-choice" in s
    assert "Set both or neither" in s


def test_render_block_when_unsupported_says_do_not_set():
    """For unsupported models, the line tells Claude explicitly NOT to
    set the flags — preventing the inverse failure mode (advisor enables
    tool calling on a base model that crashes vLLM at startup)."""
    s = render_tool_call_block("Qwen/Qwen3-8B-Base")
    assert "NOT detected" in s
    assert "Do NOT set" in s
    assert "--tool-call-parser" in s
