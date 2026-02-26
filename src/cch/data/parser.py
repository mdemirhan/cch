"""Provider-aware session parser for Claude/Codex/Gemini session files."""

from __future__ import annotations

import json
import logging
from collections.abc import Generator
from pathlib import Path

from cch.models.messages import ContentBlock, ParsedMessage, TokenUsage, ToolUseBlock

logger = logging.getLogger(__name__)


def parse_session_file(
    path: Path,
    *,
    provider: str = "claude",
    session_id: str = "",
) -> Generator[ParsedMessage]:
    """Stream-parse a provider session file and yield normalized messages."""
    normalized_provider = provider.strip().lower() or "claude"
    fallback_session = session_id or path.stem

    match normalized_provider:
        case "codex":
            yield from _parse_codex_session(path, fallback_session)
        case "gemini":
            yield from _parse_gemini_session(path, fallback_session)
        case _:
            yield from _parse_claude_session(path, fallback_session)


def _parse_claude_session(path: Path, session_key: str) -> Generator[ParsedMessage]:
    sequence = 0
    with open(path, encoding="utf-8") as file:
        for line_num, line in enumerate(file, 1):
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
                    parsed = _parse_claude_conversation_message(raw, sequence)
                    if parsed is None:
                        continue
                case "summary":
                    parsed = _parse_summary_message(raw, sequence)
                case "system":
                    parsed = _parse_system_message(raw, sequence)
                case "progress" | "file-history-snapshot" | "queue-operation":
                    continue
                case _:
                    continue

            if not parsed.uuid:
                parsed.uuid = _fallback_uuid(session_key, sequence)
            sequence += 1
            yield parsed


def _parse_codex_session(path: Path, session_key: str) -> Generator[ParsedMessage]:
    sequence = 0
    current_model = ""

    with open(path, encoding="utf-8") as file:
        for line_num, line in enumerate(file, 1):
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("Invalid JSON at %s:%d", path, line_num)
                continue

            timestamp = _as_str(raw.get("timestamp"))
            msg_type = _as_str(raw.get("type"))

            if msg_type == "turn_context":
                payload = raw.get("payload")
                if isinstance(payload, dict):
                    current_model = _as_str(payload.get("model"))
                continue

            if msg_type != "response_item":
                continue

            payload = raw.get("payload")
            if not isinstance(payload, dict):
                continue

            payload_type = _as_str(payload.get("type"))
            parsed: ParsedMessage | None = None

            if payload_type == "message":
                role = _as_str(payload.get("role"))
                if role not in {"user", "assistant"}:
                    continue
                blocks, text = _parse_codex_content(payload.get("content"))
                parsed = ParsedMessage(
                    uuid=_as_str(payload.get("id")) or _fallback_uuid(session_key, sequence),
                    type="assistant" if role == "assistant" else "user",
                    role=role,
                    model=current_model,
                    content_blocks=blocks,
                    content_text=text,
                    timestamp=timestamp,
                    sequence_num=sequence,
                )

            elif payload_type == "function_call":
                tool_name = _as_str(payload.get("name")) or "tool"
                call_id = _as_str(payload.get("call_id")) or _fallback_tool_id(
                    session_key, sequence
                )
                arguments = payload.get("arguments")
                input_json = _safe_json_string(arguments)
                parsed = ParsedMessage(
                    uuid=_fallback_uuid(session_key, sequence),
                    type="assistant",
                    role="assistant",
                    model=current_model,
                    content_blocks=[
                        ContentBlock(
                            type="tool_use",
                            tool_use=ToolUseBlock(
                                tool_use_id=call_id,
                                name=tool_name,
                                input_json=input_json,
                            ),
                        )
                    ],
                    content_text="",
                    timestamp=timestamp,
                    sequence_num=sequence,
                )

            elif payload_type == "function_call_output":
                output = _extract_codex_function_output(payload.get("output"))
                parsed = ParsedMessage(
                    uuid=_fallback_uuid(session_key, sequence),
                    type="user",
                    role="user",
                    model=current_model,
                    content_blocks=[ContentBlock(type="tool_result", text=output)],
                    content_text=output,
                    timestamp=timestamp,
                    sequence_num=sequence,
                )

            elif payload_type == "reasoning":
                thinking_text = _extract_codex_reasoning(payload)
                if thinking_text:
                    parsed = ParsedMessage(
                        uuid=_fallback_uuid(session_key, sequence),
                        type="assistant",
                        role="assistant",
                        model=current_model,
                        content_blocks=[ContentBlock(type="thinking", text=thinking_text)],
                        content_text=thinking_text,
                        timestamp=timestamp,
                        sequence_num=sequence,
                    )

            if parsed is None:
                continue
            sequence += 1
            yield parsed


def _parse_gemini_session(path: Path, session_key: str) -> Generator[ParsedMessage]:
    try:
        with open(path, encoding="utf-8") as file:
            payload = json.load(file)
    except (json.JSONDecodeError, OSError):
        logger.warning("Invalid Gemini JSON file: %s", path)
        return

    if not isinstance(payload, dict):
        return

    messages = payload.get("messages")
    if not isinstance(messages, list):
        return

    sequence = 0
    for raw in messages:
        if not isinstance(raw, dict):
            continue

        msg_type = _as_str(raw.get("type")).lower()
        timestamp = _as_str(raw.get("timestamp"))
        model = _as_str(raw.get("model"))
        uuid = _as_str(raw.get("id")) or _fallback_uuid(session_key, sequence)
        usage = _parse_gemini_usage(raw.get("tokens"))

        parsed: ParsedMessage | None = None

        if msg_type == "user":
            text = _extract_gemini_content_text(raw.get("content"))
            parsed = ParsedMessage(
                uuid=uuid,
                type="user",
                role="user",
                model=model,
                content_blocks=[ContentBlock(type="text", text=text)] if text else [],
                content_text=text,
                timestamp=timestamp,
                usage=usage,
                sequence_num=sequence,
            )
        elif msg_type in {"gemini", "assistant", "model"}:
            text = _extract_gemini_content_text(raw.get("content"))
            thoughts = _extract_gemini_thoughts(raw.get("thoughts"))
            blocks: list[ContentBlock] = []
            text_parts: list[str] = []
            if thoughts:
                blocks.append(ContentBlock(type="thinking", text=thoughts))
                text_parts.append(thoughts)
            if text:
                blocks.append(ContentBlock(type="text", text=text))
                text_parts.append(text)
            parsed = ParsedMessage(
                uuid=uuid,
                type="assistant",
                role="assistant",
                model=model,
                content_blocks=blocks,
                content_text="\n".join(text_parts),
                timestamp=timestamp,
                usage=usage,
                sequence_num=sequence,
            )
        elif msg_type == "info":
            text = _extract_gemini_content_text(raw.get("content"))
            parsed = ParsedMessage(
                uuid=uuid,
                type="system",
                role="system",
                content_blocks=[ContentBlock(type="text", text=text)] if text else [],
                content_text=text,
                timestamp=timestamp,
                sequence_num=sequence,
            )

        if parsed is None:
            continue
        sequence += 1
        yield parsed


def _parse_claude_conversation_message(raw: dict[str, object], seq: int) -> ParsedMessage | None:
    msg = raw.get("message")
    if not isinstance(msg, dict):
        return None

    msg_type = _as_str(raw.get("type"))
    role = _as_str(msg.get("role"))
    model = _as_str(msg.get("model"))
    uuid = _as_str(raw.get("uuid"))
    parent_uuid = _as_optional_str(raw.get("parentUuid"))
    timestamp = _as_str(raw.get("timestamp"))
    is_sidechain = bool(raw.get("isSidechain", False))

    usage_raw = msg.get("usage")
    usage_dict = usage_raw if isinstance(usage_raw, dict) else {}
    usage = TokenUsage(
        input_tokens=_int(usage_dict.get("input_tokens", 0)),
        output_tokens=_int(usage_dict.get("output_tokens", 0)),
        cache_read_tokens=_int(usage_dict.get("cache_read_input_tokens", 0)),
        cache_creation_tokens=_int(usage_dict.get("cache_creation_input_tokens", 0)),
    )

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
                parsed_block = _parse_claude_content_block(block)
                content_blocks.append(parsed_block)
                if parsed_block.type in {"text", "thinking"} and parsed_block.text:
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


def _parse_claude_content_block(block: dict[str, object]) -> ContentBlock:
    block_type = _as_str(block.get("type")) or "unknown"

    match block_type:
        case "text":
            return ContentBlock(type="text", text=_as_str(block.get("text")))
        case "thinking":
            return ContentBlock(type="thinking", text=_as_str(block.get("thinking")))
        case "tool_use":
            tool_id = _as_str(block.get("id"))
            tool_name = _as_str(block.get("name"))
            tool_input = block.get("input", {})
            input_json = json.dumps(tool_input) if tool_input else "{}"
            return ContentBlock(
                type="tool_use",
                tool_use=ToolUseBlock(tool_use_id=tool_id, name=tool_name, input_json=input_json),
            )
        case "tool_result":
            content = block.get("content", "")
            return ContentBlock(type="tool_result", text=_extract_content_text(content))
        case _:
            return ContentBlock(type=block_type, text=_as_str(block.get("text")))


def _parse_summary_message(raw: dict[str, object], seq: int) -> ParsedMessage:
    summary_text = _as_str(raw.get("summary"))
    return ParsedMessage(
        uuid=_as_str(raw.get("uuid")),
        type="summary",
        role="system",
        content_text=summary_text,
        content_blocks=[ContentBlock(type="text", text=summary_text)],
        timestamp=_as_str(raw.get("timestamp")),
        sequence_num=seq,
    )


def _parse_system_message(raw: dict[str, object], seq: int) -> ParsedMessage:
    text = _as_str(raw.get("text"))
    return ParsedMessage(
        uuid=_as_str(raw.get("uuid")),
        type="system",
        role="system",
        content_text=text,
        content_blocks=[ContentBlock(type="text", text=text)],
        timestamp=_as_str(raw.get("timestamp")),
        sequence_num=seq,
    )


def _parse_codex_content(raw_content: object) -> tuple[list[ContentBlock], str]:
    if isinstance(raw_content, str):
        return [ContentBlock(type="text", text=raw_content)], raw_content
    if not isinstance(raw_content, list):
        return [], ""

    blocks: list[ContentBlock] = []
    text_parts: list[str] = []
    for block in raw_content:
        if isinstance(block, str):
            blocks.append(ContentBlock(type="text", text=block))
            text_parts.append(block)
            continue
        if not isinstance(block, dict):
            continue
        text = _as_str(block.get("text"))
        if not text:
            continue
        block_type = _as_str(block.get("type"))
        if block_type in {"input_text", "output_text"}:
            blocks.append(ContentBlock(type="text", text=text))
        else:
            blocks.append(ContentBlock(type=block_type or "text", text=text))
        text_parts.append(text)

    return blocks, "\n".join(text_parts)


def _extract_codex_function_output(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        output = value.get("output")
        if isinstance(output, str):
            return output
        return json.dumps(value, ensure_ascii=False)
    return _as_str(value)


def _extract_codex_reasoning(payload: dict[str, object]) -> str:
    summary = payload.get("summary")
    if isinstance(summary, list):
        parts: list[str] = []
        for block in summary:
            if not isinstance(block, dict):
                continue
            text = _as_str(block.get("text"))
            if text:
                parts.append(text)
        if parts:
            return "\n".join(parts)
    return _as_str(payload.get("content"))


def _extract_gemini_content_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        return _as_str(content.get("text"))
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
                continue
            if isinstance(block, dict):
                text = _as_str(block.get("text"))
                if text:
                    parts.append(text)
        return "\n".join(parts)
    return ""


def _extract_gemini_thoughts(thoughts: object) -> str:
    if isinstance(thoughts, str):
        return thoughts
    if isinstance(thoughts, list):
        parts: list[str] = []
        for item in thoughts:
            if isinstance(item, str):
                parts.append(item)
        return "\n".join(parts)
    return ""


def _parse_gemini_usage(tokens: object) -> TokenUsage:
    if not isinstance(tokens, dict):
        return TokenUsage()
    return TokenUsage(
        input_tokens=_int(tokens.get("input", 0)),
        output_tokens=_int(tokens.get("output", 0)),
        cache_read_tokens=_int(tokens.get("cached", 0)),
        cache_creation_tokens=0,
    )


def _extract_content_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(_as_str(item.get("text")))
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts)
    return _as_str(content)


def _safe_json_string(value: object) -> str:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or "{}"
    if value is None:
        return "{}"
    try:
        return json.dumps(value, ensure_ascii=False)
    except TypeError:
        return "{}"


def _fallback_uuid(session_key: str, seq: int) -> str:
    return f"{session_key}:msg:{seq}"


def _fallback_tool_id(session_key: str, seq: int) -> str:
    return f"{session_key}:tool:{seq}"


def _as_str(value: object) -> str:
    return value if isinstance(value, str) else ""


def _as_optional_str(value: object) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None


def _int(val: object) -> int:
    if isinstance(val, bool):
        return int(val)
    if isinstance(val, int):
        return val
    if isinstance(val, float):
        return int(val)
    if isinstance(val, str):
        try:
            return int(float(val))
        except ValueError:
            return 0
    return 0
