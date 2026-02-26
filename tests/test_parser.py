"""Tests for JSONL parser."""

from __future__ import annotations

import json
from pathlib import Path

from cch.data.parser import parse_session_file


class TestParseSessionFile:
    def test_parses_messages(self, sample_session_path: Path) -> None:
        messages = list(parse_session_file(sample_session_path))
        # Should skip file-history-snapshot and yield user/assistant/summary messages
        assert len(messages) >= 5

    def test_user_message_content(self, sample_session_path: Path) -> None:
        messages = list(parse_session_file(sample_session_path))
        user_msgs = [m for m in messages if m.type == "user" and m.role == "user"]
        assert len(user_msgs) >= 1
        assert "help me fix a bug" in user_msgs[0].content_text

    def test_assistant_message_with_tool_use(self, sample_session_path: Path) -> None:
        messages = list(parse_session_file(sample_session_path))
        assistant_msgs = [m for m in messages if m.role == "assistant"]
        assert len(assistant_msgs) >= 2

        # Find the message with tool_use
        tool_msg = None
        for m in assistant_msgs:
            for b in m.content_blocks:
                if b.type == "tool_use":
                    tool_msg = m
                    break

        assert tool_msg is not None
        tool_block = [b for b in tool_msg.content_blocks if b.type == "tool_use"][0]
        assert tool_block.tool_use is not None
        assert tool_block.tool_use.name == "Edit"
        assert tool_block.tool_use.tool_use_id == "tool-001"

    def test_thinking_block(self, sample_session_path: Path) -> None:
        messages = list(parse_session_file(sample_session_path))
        assistant_msgs = [m for m in messages if m.role == "assistant"]
        # First assistant message should have thinking block
        first_assistant = assistant_msgs[0]
        thinking_blocks = [b for b in first_assistant.content_blocks if b.type == "thinking"]
        assert len(thinking_blocks) == 1
        assert "think about" in thinking_blocks[0].text

    def test_token_usage(self, sample_session_path: Path) -> None:
        messages = list(parse_session_file(sample_session_path))
        assistant_msgs = [m for m in messages if m.role == "assistant"]
        first = assistant_msgs[0]
        assert first.usage.input_tokens == 100
        assert first.usage.output_tokens == 50
        assert first.usage.cache_read_tokens == 500
        assert first.usage.cache_creation_tokens == 200

    def test_summary_message(self, sample_session_path: Path) -> None:
        messages = list(parse_session_file(sample_session_path))
        summaries = [m for m in messages if m.type == "summary"]
        assert len(summaries) == 1
        assert "Fixed a bug" in summaries[0].content_text

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

        first_assistant = messages[1]
        assert first_assistant.uuid == "uuid-002"
        assert first_assistant.parent_uuid == "uuid-001"

    def test_model_field(self, sample_session_path: Path) -> None:
        messages = list(parse_session_file(sample_session_path))
        assistant_msgs = [m for m in messages if m.role == "assistant"]
        for m in assistant_msgs:
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
        assert msg.role == ""
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
                    "arguments": "{\"command\": [\"ls\"]}",
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
        assert messages[0].role == "user"
        assert messages[1].content_blocks[0].type == "tool_use"
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
        assert len(messages) == 3
        assert messages[1].role == "assistant"
        assert messages[1].usage.input_tokens == 10
        assert messages[1].content_blocks[0].type == "thinking"
