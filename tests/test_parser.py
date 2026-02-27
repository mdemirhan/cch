"""Tests for session parser canonicalization."""

from __future__ import annotations

import json
from pathlib import Path

from cch.data.parser import parse_session_file


class TestParseSessionFile:
    def test_parses_messages(self, sample_session_path: Path) -> None:
        messages = list(parse_session_file(sample_session_path))
        # Sample file contains mixed assistant/text/thinking/tool_use/tool_result/system events.
        assert len(messages) >= 7

    def test_canonical_types_from_claude(self, sample_session_path: Path) -> None:
        messages = list(parse_session_file(sample_session_path))
        types = [m.type for m in messages]
        assert "user" in types
        assert "assistant" in types
        assert "thinking" in types
        assert "tool_use" in types
        assert "tool_result" in types
        assert "system" in types

    def test_user_message_content(self, sample_session_path: Path) -> None:
        messages = list(parse_session_file(sample_session_path))
        user_msgs = [m for m in messages if m.type == "user"]
        assert len(user_msgs) >= 1
        assert "help me fix a bug" in user_msgs[0].content_text

    def test_tool_use_details(self, sample_session_path: Path) -> None:
        messages = list(parse_session_file(sample_session_path))
        tool_msgs = [m for m in messages if m.type == "tool_use"]
        assert tool_msgs
        tool_block = [b for b in tool_msgs[0].content_blocks if b.type == "tool_use"][0]
        assert tool_block.tool_use is not None
        assert tool_block.tool_use.name == "Edit"
        assert tool_block.tool_use.tool_use_id == "tool-001"

    def test_thinking_block(self, sample_session_path: Path) -> None:
        messages = list(parse_session_file(sample_session_path))
        thinking_msgs = [m for m in messages if m.type == "thinking"]
        assert len(thinking_msgs) >= 1
        assert "think about" in thinking_msgs[0].content_text

    def test_token_usage_only_first_split_message(self, sample_session_path: Path) -> None:
        messages = list(parse_session_file(sample_session_path))
        # First assistant raw event splits into thinking(uuid-002) and assistant(uuid-002#2).
        first_split = [m for m in messages if m.uuid.startswith("uuid-002")]
        assert len(first_split) >= 2
        assert first_split[0].usage.input_tokens == 100
        assert first_split[0].usage.output_tokens == 50
        assert first_split[1].usage.input_tokens == 0
        assert first_split[1].usage.output_tokens == 0

    def test_summary_message_becomes_system(self, sample_session_path: Path) -> None:
        messages = list(parse_session_file(sample_session_path))
        system_messages = [m for m in messages if m.type == "system"]
        assert system_messages
        assert "Fixed a bug" in system_messages[-1].content_text

    def test_sequence_numbers(self, sample_session_path: Path) -> None:
        messages = list(parse_session_file(sample_session_path))
        seqs = [m.sequence_num for m in messages]
        assert seqs == sorted(seqs)
        assert seqs[0] == 0

    def test_uuid_and_parent(self, sample_session_path: Path) -> None:
        messages = list(parse_session_file(sample_session_path))
        first_user = messages[0]
        assert first_user.uuid == "uuid-001"
        assert first_user.parent_uuid is None

        first_assistant_split = messages[1]
        assert first_assistant_split.uuid == "uuid-002"
        assert first_assistant_split.parent_uuid == "uuid-001"

    def test_model_field(self, sample_session_path: Path) -> None:
        messages = list(parse_session_file(sample_session_path))
        assistant_like = [m for m in messages if m.type in {"assistant", "thinking", "tool_use"}]
        assert assistant_like
        for m in assistant_like:
            assert m.model == "claude-opus-4-6"

    def test_malformed_field_types_do_not_crash(self, tmp_path: Path) -> None:
        malformed = {
            "type": "assistant",
            "uuid": 123,
            "timestamp": 456,
            "message": {
                "role": {"bad": "shape"},
                "model": None,
                "content": ["ok"],
                "usage": "bad-usage",
            },
        }
        path = tmp_path / "malformed.jsonl"
        path.write_text(json.dumps(malformed), encoding="utf-8")

        parsed = list(parse_session_file(path))
        assert len(parsed) == 1
        msg = parsed[0]
        assert msg.uuid.startswith("malformed:msg:")
        assert msg.timestamp == ""
        assert msg.usage.input_tokens == 0

    def test_parses_codex_format(self, tmp_path: Path) -> None:
        lines = [
            {
                "timestamp": "2026-01-01T10:00:00.000Z",
                "type": "session_meta",
                "payload": {"id": "abc", "cwd": "/tmp/proj"},
            },
            {
                "timestamp": "2026-01-01T10:00:00.100Z",
                "type": "turn_context",
                "payload": {"model": "gpt-5-codex"},
            },
            {
                "timestamp": "2026-01-01T10:00:01.000Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "hello"}],
                },
            },
            {
                "timestamp": "2026-01-01T10:00:02.000Z",
                "type": "response_item",
                "payload": {
                    "type": "function_call",
                    "name": "shell",
                    "arguments": '{"command": ["ls"]}',
                    "call_id": "call-1",
                },
            },
            {
                "timestamp": "2026-01-01T10:00:03.000Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "done"}],
                },
            },
        ]
        path = tmp_path / "codex.jsonl"
        path.write_text("\n".join(json.dumps(item) for item in lines), encoding="utf-8")

        messages = list(parse_session_file(path, provider="codex", session_id="codex:abc"))
        assert len(messages) == 3
        assert messages[0].type == "user"
        assert messages[1].type == "tool_use"
        assert messages[2].model == "gpt-5-codex"

    def test_parses_gemini_format(self, tmp_path: Path) -> None:
        payload = {
            "sessionId": "g-1",
            "messages": [
                {
                    "id": "u1",
                    "timestamp": "2026-01-01T10:00:00.000Z",
                    "type": "user",
                    "content": [{"text": "hello"}],
                },
                {
                    "id": "a1",
                    "timestamp": "2026-01-01T10:00:01.000Z",
                    "type": "gemini",
                    "content": "hi",
                    "model": "gemini-3.1-pro-preview",
                    "tokens": {"input": 10, "output": 5, "cached": 3},
                    "thoughts": ["thinking"],
                },
                {
                    "id": "i1",
                    "timestamp": "2026-01-01T10:00:02.000Z",
                    "type": "info",
                    "content": "Request cancelled.",
                },
            ],
        }
        path = tmp_path / "gemini.json"
        path.write_text(json.dumps(payload), encoding="utf-8")

        messages = list(parse_session_file(path, provider="gemini", session_id="gemini:g-1"))
        assert len(messages) == 4
        assert messages[1].type == "thinking"
        assert messages[2].type == "assistant"
        assert messages[1].usage.input_tokens == 10
