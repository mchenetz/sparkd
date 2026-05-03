"""Unit tests for the `_extract_reason` helper that distills a one-line
explanation out of a launch log tail. This is what the UI surfaces inline
on a launch row when the reconciler marks a launch interrupted/failed."""

from sparkd.services.launch import _extract_reason, _truncate


def test_extract_reason_picks_python_exception_line():
    tail = [
        "INFO some startup chatter",
        "Traceback (most recent call last):",
        "  File ...",
        "OSError: Can't load image processor for 'foo/bar'.",
        "Stopping cluster...",
    ]
    reason = _extract_reason(tail)
    assert "OSError" in reason
    assert "image processor" in reason


def test_extract_reason_prefers_last_exception_when_multiple():
    """A traceback often has nested exceptions. We want the LAST one
    because it's typically the actual cause (vs intermediate wrappers)."""
    tail = [
        "ValueError: failed to parse",  # earlier — wrapper
        "  ...handling above exception...",
        "RuntimeError: torch.cuda OOM during placement",  # later — root cause
    ]
    reason = _extract_reason(tail)
    assert "RuntimeError" in reason
    assert "OOM" in reason


def test_extract_reason_falls_back_to_vllm_warning_class():
    """No Python exception lines, but a known fatal vLLM symptom."""
    tail = [
        "INFO loading...",
        "WARNING [ray_utils.py:556] Tensor parallel size (2) exceeds available GPUs",
    ]
    reason = _extract_reason(tail)
    assert "Tensor parallel" in reason


def test_extract_reason_falls_back_to_last_line_when_nothing_matches():
    tail = [
        "INFO model loaded",
        "INFO server starting on 8000",
        "Stopping cluster — admin requested shutdown",
    ]
    reason = _extract_reason(tail)
    assert reason == "Stopping cluster — admin requested shutdown"


def test_extract_reason_empty_tail_returns_empty():
    assert _extract_reason([]) == ""


def test_extract_reason_truncates_to_200_chars():
    long_msg = "OSError: " + "x" * 500
    reason = _extract_reason([long_msg])
    assert len(reason) <= 200
    assert reason.endswith("…")


def test_truncate_short_string_unchanged():
    assert _truncate("short") == "short"


def test_truncate_long_string_ellipsizes():
    s = "a" * 250
    out = _truncate(s, n=200)
    assert len(out) == 200
    assert out.endswith("…")
