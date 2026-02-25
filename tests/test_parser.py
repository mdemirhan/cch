"""Tests for JSONL parser."""

from __future__ import annotations

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
