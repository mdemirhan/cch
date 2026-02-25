"""Generator-based JSONL parser with match/case dispatch."""

from __future__ import annotations

import json
import logging
from collections.abc import Generator
from pathlib import Path

from cch.models.messages import ContentBlock, ParsedMessage, TokenUsage, ToolUseBlock

logger = logging.getLogger(__name__)


def parse_session_file(path: Path) -> Generator[ParsedMessage]:
    """Stream-parse a JSONL session file, yielding typed messages.

    Args:
        path: Path to the JSONL session file.

    Yields:
        ParsedMessage for each user/assistant/summary/system line.
    """
    sequence = 0
    with open(path) as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("Invalid JSON at %s:%d", path, line_num)
                continue

            msg_type = raw.get("type", "")
            match msg_type:
                case "user" | "assistant":
                    parsed = _parse_conversation_message(raw, sequence)
                    if parsed is not None:
                        sequence += 1
                        yield parsed
                case "summary":
                    parsed = _parse_summary_message(raw, sequence)
                    sequence += 1
                    yield parsed
                case "system":
                    parsed = _parse_system_message(raw, sequence)
                    sequence += 1
                    yield parsed
                case "progress" | "file-history-snapshot" | "queue-operation":
                    continue
                case _:
                    continue


def _parse_conversation_message(raw: dict[str, object], seq: int) -> ParsedMessage | None:
    """Parse a user or assistant message from raw JSONL data."""
    msg = raw.get("message")
    if not isinstance(msg, dict):
        return None

    msg_type = raw.get("type", "")
    assert isinstance(msg_type, str)
    role = msg.get("role", "")
    assert isinstance(role, str)
    model = msg.get("model") or ""
    assert isinstance(model, str)

    uuid = raw.get("uuid", "")
    assert isinstance(uuid, str)
    parent_uuid = raw.get("parentUuid")
    if parent_uuid is not None:
        assert isinstance(parent_uuid, str)

    timestamp = raw.get("timestamp") or ""
    assert isinstance(timestamp, str)

    is_sidechain_val = raw.get("isSidechain", False)
    is_sidechain = bool(is_sidechain_val)

    # Parse usage
    usage_raw = msg.get("usage", {})
    assert isinstance(usage_raw, dict)
    usage = TokenUsage(
        input_tokens=_int(usage_raw.get("input_tokens", 0)),
        output_tokens=_int(usage_raw.get("output_tokens", 0)),
        cache_read_tokens=_int(usage_raw.get("cache_read_input_tokens", 0)),
        cache_creation_tokens=_int(usage_raw.get("cache_creation_input_tokens", 0)),
    )

    # Parse content blocks
    raw_content = msg.get("content", [])
    content_blocks: list[ContentBlock] = []
    text_parts: list[str] = []

    if isinstance(raw_content, str):
        content_blocks.append(ContentBlock(type="text", text=raw_content))
        text_parts.append(raw_content)
    elif isinstance(raw_content, list):
        for block in raw_content:
            if isinstance(block, str):
                content_blocks.append(ContentBlock(type="text", text=block))
                text_parts.append(block)
            elif isinstance(block, dict):
                parsed_block = _parse_content_block(block)
                content_blocks.append(parsed_block)
                if parsed_block.type == "text" or parsed_block.type == "thinking":
                    text_parts.append(parsed_block.text)

    return ParsedMessage(
        uuid=uuid,
        parent_uuid=parent_uuid,
        type=msg_type,
        role=role,
        model=model,
        content_blocks=content_blocks,
        content_text="\n".join(text_parts),
        usage=usage,
        timestamp=timestamp,
        is_sidechain=is_sidechain,
        sequence_num=seq,
    )


def _parse_content_block(block: dict[str, object]) -> ContentBlock:
    """Parse a single content block dict."""
    block_type = str(block.get("type", "unknown"))

    match block_type:
        case "text":
            return ContentBlock(type="text", text=str(block.get("text", "")))
        case "thinking":
            return ContentBlock(type="thinking", text=str(block.get("thinking", "")))
        case "tool_use":
            tool_id = str(block.get("id", ""))
            tool_name = str(block.get("name", ""))
            tool_input = block.get("input", {})
            input_json = json.dumps(tool_input) if tool_input else "{}"
            return ContentBlock(
                type="tool_use",
                tool_use=ToolUseBlock(
                    tool_use_id=tool_id,
                    name=tool_name,
                    input_json=input_json,
                ),
            )
        case "tool_result":
            content = block.get("content", "")
            text = ""
            if isinstance(content, str):
                text = content
            elif isinstance(content, list):
                parts = []
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        parts.append(str(item.get("text", "")))
                    elif isinstance(item, str):
                        parts.append(item)
                text = "\n".join(parts)
            return ContentBlock(type="tool_result", text=text)
        case _:
            return ContentBlock(type=block_type, text=str(block.get("text", "")))


def _parse_summary_message(raw: dict[str, object], seq: int) -> ParsedMessage:
    """Parse a summary message."""
    summary_text = str(raw.get("summary", ""))
    uuid = str(raw.get("uuid", ""))
    timestamp = str(raw.get("timestamp", ""))
    return ParsedMessage(
        uuid=uuid,
        type="summary",
        role="system",
        content_text=summary_text,
        content_blocks=[ContentBlock(type="text", text=summary_text)],
        timestamp=timestamp,
        sequence_num=seq,
    )


def _parse_system_message(raw: dict[str, object], seq: int) -> ParsedMessage:
    """Parse a system message."""
    uuid = str(raw.get("uuid", ""))
    timestamp = str(raw.get("timestamp", ""))
    text = str(raw.get("text", ""))
    return ParsedMessage(
        uuid=uuid,
        type="system",
        role="system",
        content_text=text,
        content_blocks=[ContentBlock(type="text", text=text)],
        timestamp=timestamp,
        sequence_num=seq,
    )


def _int(val: object) -> int:
    """Safely convert to int."""
    if isinstance(val, int):
        return val
    if isinstance(val, float):
        return int(val)
    return 0
