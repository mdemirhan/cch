"""Direct unit tests for parser helper branches."""

from __future__ import annotations

from dataclasses import dataclass

from cch.data.parser import (
    _as_optional_str,
    _as_str,
    _extract_codex_function_output,
    _extract_codex_reasoning,
    _extract_content_text,
    _extract_gemini_content_text,
    _extract_gemini_thoughts,
    _first_text,
    _int,
    _normalize_parts,
    _parse_claude_content_block,
    _parse_codex_content,
    _parse_gemini_usage,
    _safe_json_string,
    _tool_use_search_text,
)
from cch.models.messages import ContentBlock, TokenUsage, ToolUseBlock


def test_normalize_parts_handles_all_source_types() -> None:
    usage = TokenUsage(input_tokens=10, output_tokens=5)

    system_rows = _normalize_parts(
        session_key="s",
        sequence_start=0,
        base_uuid="",
        parent_uuid=None,
        source_type="summary",
        model="",
        content_blocks=[],
        content_text="summary text",
        usage=usage,
        timestamp="2026-01-01T00:00:00Z",
    )
    assert system_rows[0].type == "system"
    assert system_rows[0].uuid.startswith("s:msg:")

    user_rows = _normalize_parts(
        session_key="s",
        sequence_start=1,
        base_uuid="u-1",
        parent_uuid=None,
        source_type="user",
        model="",
        content_blocks=[
            ContentBlock(type="user", text="hello"),
            ContentBlock(type="tool_result", text="done"),
        ],
        content_text="",
        usage=usage,
        timestamp="2026-01-01T00:00:01Z",
    )
    assert [row.type for row in user_rows] == ["user", "tool_result"]
    assert user_rows[1].usage.input_tokens == 0

    tool_use = ToolUseBlock(tool_use_id="t1", name="Edit", input_json='{"x":1}')
    assistant_rows = _normalize_parts(
        session_key="s",
        sequence_start=3,
        base_uuid="a-1",
        parent_uuid="u-1",
        source_type="assistant",
        model="m",
        content_blocks=[
            ContentBlock(type="thinking", text="think"),
            ContentBlock(type="tool_use", tool_use=tool_use),
            ContentBlock(type="text", text="final"),
        ],
        content_text="",
        usage=usage,
        timestamp="2026-01-01T00:00:02Z",
    )
    assert [row.type for row in assistant_rows] == ["thinking", "tool_use", "assistant"]
    assert assistant_rows[1].content_text == 'Edit\n{"x":1}'
    assert assistant_rows[2].parent_uuid == "a-1#2"

    fallback_rows = _normalize_parts(
        session_key="s",
        sequence_start=6,
        base_uuid="",
        parent_uuid=None,
        source_type="weird",
        model="",
        content_blocks=[],
        content_text="",
        usage=TokenUsage(),
        timestamp="",
    )
    assert fallback_rows[0].type == "system"


def test_parse_claude_content_block_variants() -> None:
    text = _parse_claude_content_block({"type": "text", "text": "hello"})
    assert text.type == "text"
    assert text.text == "hello"

    thinking = _parse_claude_content_block({"type": "thinking", "thinking": "reasoning"})
    assert thinking.type == "thinking"
    assert thinking.text == "reasoning"

    tool_use = _parse_claude_content_block(
        {"type": "tool_use", "id": "t1", "name": "Edit", "input": {"a": 1}}
    )
    assert tool_use.type == "tool_use"
    assert tool_use.tool_use is not None
    assert tool_use.tool_use.input_json == '{"a": 1}'

    tool_result = _parse_claude_content_block(
        {"type": "tool_result", "content": [{"type": "text", "text": "ok"}]}
    )
    assert tool_result.type == "tool_result"
    assert tool_result.text == "ok"

    unknown = _parse_claude_content_block({"type": "x", "text": "v"})
    assert unknown.type == "x"
    assert unknown.text == "v"


def test_codex_and_gemini_helper_extractors() -> None:
    assert _parse_codex_content("one")[1] == "one"
    assert _parse_codex_content(123) == ([], "")
    blocks, text = _parse_codex_content(
        [{"type": "input_text", "text": "a"}, {"type": "x", "text": "b"}, "c"]
    )
    assert len(blocks) == 3
    assert text == "a\nb\nc"

    assert _extract_codex_function_output("ok") == "ok"
    assert _extract_codex_function_output({"output": "done"}) == "done"
    assert _extract_codex_function_output({"status": "ok"}) == '{"status": "ok"}'
    assert _extract_codex_function_output(1) == ""

    assert _extract_codex_reasoning({"summary": [{"text": "a"}, {"text": "b"}]}) == "a\nb"
    assert _extract_codex_reasoning({"content": "fallback"}) == "fallback"

    assert _extract_gemini_content_text("hello") == "hello"
    assert _extract_gemini_content_text({"text": "x"}) == "x"
    assert _extract_gemini_content_text([{"text": "a"}, "b"]) == "a\nb"
    assert _extract_gemini_content_text(99) == ""

    assert _extract_gemini_thoughts("t") == "t"
    assert _extract_gemini_thoughts(["a", "b"]) == "a\nb"
    assert _extract_gemini_thoughts({"x": 1}) == ""

    usage = _parse_gemini_usage({"input": "12", "output": 8.0, "cached": True})
    assert usage.input_tokens == 12
    assert usage.output_tokens == 8
    assert usage.cache_read_tokens == 1
    assert _parse_gemini_usage("bad") == TokenUsage()

    assert _extract_content_text("x") == "x"
    assert _extract_content_text([{"type": "text", "text": "a"}, "b"]) == "a\nb"


def test_small_scalar_helpers() -> None:
    tool_use = ToolUseBlock(tool_use_id="id", name="Edit", input_json='{"k":1}')
    assert _tool_use_search_text(tool_use) == 'Edit\n{"k":1}'
    assert _tool_use_search_text(ToolUseBlock(tool_use_id="", name="", input_json="x")) == "x"

    assert (
        _first_text([ContentBlock(type="text", text=""), ContentBlock(type="text", text="x")])
        == "x"
    )

    assert _safe_json_string("  data  ") == "data"
    assert _safe_json_string(None) == "{}"
    assert _safe_json_string({"a": 1}) == '{"a": 1}'

    @dataclass
    class _X:
        a: int

    assert _safe_json_string(_X(1)) == "{}"

    assert _as_str("x") == "x"
    assert _as_str(1) == ""
    assert _as_optional_str("x") == "x"
    assert _as_optional_str("") is None
    assert _as_optional_str(1) is None

    assert _int(True) == 1
    assert _int(3) == 3
    assert _int(3.9) == 3
    assert _int("5.2") == 5
    assert _int("bad") == 0
